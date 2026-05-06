"""HTTP and helper tests for revision-scoped pin binary upload / download (`flow_pins`)."""

from __future__ import annotations

from io import BytesIO

import pytest

import app.routes.flows as flows_routes
from tests.conftest_utils import TEST_ORG_ID, client, get_auth_headers


def _auth_multipart_headers() -> dict[str, str]:
    return {"Authorization": "Bearer test_token"}


def _std_manual_node() -> dict:
    return {
        "id": "t1",
        "name": "Start",
        "type": "flows.trigger.manual",
        "position": [0, 0],
        "parameters": {},
        "webhook_id": None,
        "disabled": False,
        "on_error": "stop",
        "retry_on_fail": False,
        "max_tries": 1,
        "wait_between_tries_ms": 1000,
        "notes": None,
    }


@pytest.fixture
def flow_with_revision(mock_auth, test_db):
    r0 = client.post(
        f"/v0/orgs/{TEST_ORG_ID}/flows",
        json={"name": "pin binary route test"},
        headers=get_auth_headers(),
    )
    assert r0.status_code == 200, r0.text
    flow_id = r0.json()["flow"]["flow_id"]
    r1 = client.put(
        f"/v0/orgs/{TEST_ORG_ID}/flows/{flow_id}",
        json={
            "base_flow_revid": "",
            "name": "pin binary route test",
            "nodes": [_std_manual_node()],
            "connections": {},
            "settings": {},
            "pin_data": None,
        },
        headers=get_auth_headers(),
    )
    assert r1.status_code == 200, r1.text
    rev_id = r1.json()["revision"]["flow_revid"]
    return flow_id, rev_id


def test_flow_pins_keys_from_pin_data_collects_all_main_lanes() -> None:
    pid = "6579a94b1f1d8f5a8e9caf00"
    k0 = f"pin/{pid}/n/0/0/a/f"
    k1 = f"pin/{pid}/n/1/0/b/f"
    pin_data = {
        "n1": {
            "main": [
                [{"json": {}, "binary": {"a": {"storage_id": f"flow_pins:{k0}"}}}],
                [{"json": {}, "binary": {"b": {"storage_id": f"flow_pins:{k1}"}}}],
            ]
        }
    }
    keys = flows_routes._flow_pins_keys_from_pin_data(pin_data, prefix=f"pin/{pid}/")
    assert keys == {k0, k1}


def test_safe_content_disposition_filename_strips_controls() -> None:
    assert "\n" not in flows_routes._safe_content_disposition_filename('x\ny"z\\')
    assert "\r" not in flows_routes._safe_content_disposition_filename("a\rb\r\nc")
    assert flows_routes._safe_content_disposition_filename("") == "file"


def test_pin_blob_mime_allows_inline() -> None:
    assert flows_routes._pin_blob_mime_allows_inline("image/png")
    assert flows_routes._pin_blob_mime_allows_inline("image/png; charset=binary")
    assert not flows_routes._pin_blob_mime_allows_inline("image/svg+xml")
    assert flows_routes._pin_blob_mime_allows_inline("application/pdf")
    assert not flows_routes._pin_blob_mime_allows_inline("text/html")


def test_mime_essence_strips_params() -> None:
    assert flows_routes._mime_essence("text/html; charset=latin1") == "text/html"
    assert flows_routes._mime_essence(" Application/PDF ; x=y") == "application/pdf"


def test_blob_response_media_type_downgrades_risky_for_attachment() -> None:
    octet = "application/octet-stream"
    assert flows_routes._blob_response_media_type("text/html", content_disposition_is_inline=False) == octet
    assert (
        flows_routes._blob_response_media_type(
            "application/javascript", content_disposition_is_inline=False
        )
        == octet
    )
    assert (
        flows_routes._blob_response_media_type(
            "application/vnd.ms-excel", content_disposition_is_inline=False
        )
        == octet
    )
    assert (
        flows_routes._blob_response_media_type(
            "application/pdf", content_disposition_is_inline=False
        )
        == "application/pdf"
    )


def test_blob_response_media_type_inline_only_safe() -> None:
    assert flows_routes._blob_response_media_type(
        "text/html", content_disposition_is_inline=True
    ) == "application/octet-stream"
    assert flows_routes._blob_response_media_type(
        "image/png", content_disposition_is_inline=True
    ) == "image/png"


def test_upload_pin_binary_invalid_flow_revid_400(flow_with_revision, mock_auth, test_db):
    flow_id, _ = flow_with_revision
    files = {"file": ("t.bin", BytesIO(b"x"), "application/octet-stream")}
    data = {"node_id": "n1", "slot": "0", "item_index": "0", "property": "data"}
    r = client.post(
        f"/v0/orgs/{TEST_ORG_ID}/flows/{flow_id}/revisions/not-a-valid-id/pins/binary",
        data=data,
        files=files,
        headers=_auth_multipart_headers(),
    )
    assert r.status_code == 400, r.text


def test_upload_pin_binary_rejects_oversize(flow_with_revision, mock_auth, test_db, monkeypatch):
    flow_id, rev_id = flow_with_revision
    monkeypatch.setattr(flows_routes, "MAX_PIN_UPLOAD_BYTES", 4)
    files = {"file": ("t.bin", BytesIO(b"12345"), "application/octet-stream")}
    data = {"node_id": "n1", "slot": "0", "item_index": "0", "property": "data"}
    r = client.post(
        f"/v0/orgs/{TEST_ORG_ID}/flows/{flow_id}/revisions/{rev_id}/pins/binary",
        data=data,
        files=files,
        headers=_auth_multipart_headers(),
    )
    assert r.status_code == 413, r.text


def test_pin_binary_upload_get_roundtrip(flow_with_revision, mock_auth, test_db):
    flow_id, rev_id = flow_with_revision
    payload = b"hello-pin"
    files = {"file": ("hello.bin", BytesIO(payload), "application/octet-stream")}
    data = {"node_id": "n1", "slot": "0", "item_index": "0", "property": "data"}
    r_up = client.post(
        f"/v0/orgs/{TEST_ORG_ID}/flows/{flow_id}/revisions/{rev_id}/pins/binary",
        data=data,
        files=files,
        headers=_auth_multipart_headers(),
    )
    assert r_up.status_code == 200, r_up.text
    body = r_up.json()
    storage_id = body["storage_id"]
    assert storage_id.startswith("flow_pins:")

    r_get = client.get(
        f"/v0/orgs/{TEST_ORG_ID}/flows/{flow_id}/revisions/{rev_id}/pins/blob",
        params={"storage_id": storage_id, "action": "download"},
        headers=get_auth_headers(),
    )
    assert r_get.status_code == 200, r_get.text
    assert r_get.content == payload


def test_pin_binary_wrong_revision_forbidden(flow_with_revision, mock_auth, test_db):
    flow_id, rev_id = flow_with_revision
    files = {"file": ("hello.bin", BytesIO(b"a"), "application/octet-stream")}
    data = {"node_id": "n1", "slot": "0", "item_index": "0", "property": "data"}
    r_up = client.post(
        f"/v0/orgs/{TEST_ORG_ID}/flows/{flow_id}/revisions/{rev_id}/pins/binary",
        data=data,
        files=files,
        headers=_auth_multipart_headers(),
    )
    assert r_up.status_code == 200, r_up.text
    storage_id = r_up.json()["storage_id"]

    r0 = client.post(
        f"/v0/orgs/{TEST_ORG_ID}/flows",
        json={"name": "other flow for pin idor test"},
        headers=get_auth_headers(),
    )
    assert r0.status_code == 200, r0.text
    other_flow_id = r0.json()["flow"]["flow_id"]
    r1 = client.put(
        f"/v0/orgs/{TEST_ORG_ID}/flows/{other_flow_id}",
        json={
            "base_flow_revid": "",
            "name": "other",
            "nodes": [_std_manual_node()],
            "connections": {},
            "settings": {},
            "pin_data": None,
        },
        headers=get_auth_headers(),
    )
    assert r1.status_code == 200, r1.text
    other_rev = r1.json()["revision"]["flow_revid"]

    r_bad = client.get(
        f"/v0/orgs/{TEST_ORG_ID}/flows/{other_flow_id}/revisions/{other_rev}/pins/blob",
        params={"storage_id": storage_id, "action": "download"},
        headers=get_auth_headers(),
    )
    assert r_bad.status_code == 403, r_bad.text


def test_pin_binary_view_disposition_for_html_is_attachment(flow_with_revision, mock_auth, test_db):
    flow_id, rev_id = flow_with_revision
    files = {"file": ("x.html", BytesIO(b"<html></html>"), "text/html")}
    data = {"node_id": "n1", "slot": "0", "item_index": "0", "property": "data"}
    r_up = client.post(
        f"/v0/orgs/{TEST_ORG_ID}/flows/{flow_id}/revisions/{rev_id}/pins/binary",
        data=data,
        files=files,
        headers=_auth_multipart_headers(),
    )
    assert r_up.status_code == 200, r_up.text
    storage_id = r_up.json()["storage_id"]
    r_get = client.get(
        f"/v0/orgs/{TEST_ORG_ID}/flows/{flow_id}/revisions/{rev_id}/pins/blob",
        params={"storage_id": storage_id, "action": "view"},
        headers=get_auth_headers(),
    )
    assert r_get.status_code == 200, r_get.text
    cd = r_get.headers.get("content-disposition", "")
    assert "attachment" in cd.lower()
    ctype = r_get.headers.get("content-type", "")
    assert "application/octet-stream" in ctype.lower()
