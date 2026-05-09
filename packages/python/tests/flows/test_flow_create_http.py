"""Tests for POST /flows (header-only vs header + first revision)."""

from __future__ import annotations

from unittest.mock import patch

import pytest

import app.routes.flows as flows_routes
from tests.conftest_utils import TEST_ORG_ID, client, get_auth_headers


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


@pytest.mark.asyncio
async def test_post_flow_with_graph_returns_revision_and_appears_in_list(test_db, mock_auth):
    """POST /flows with nodes persists rev 1; default list includes the flow."""

    r = client.post(
        f"/v0/orgs/{TEST_ORG_ID}/flows",
        json={
            "name": "Atomic create graph",
            "nodes": [_std_manual_node()],
            "connections": {},
            "settings": {},
            "pin_data": None,
        },
        headers=get_auth_headers(),
    )
    assert r.status_code == 200, r.text
    body = r.json()
    flow_id = body["flow"]["flow_id"]
    assert body.get("revision") is not None
    assert body["revision"]["flow_id"] == flow_id

    r_list = client.get(
        f"/v0/orgs/{TEST_ORG_ID}/flows",
        params={"limit": 200, "offset": 0},
        headers=get_auth_headers(),
    )
    assert r_list.status_code == 200, r_list.text
    listed = {x["flow"]["flow_id"] for x in r_list.json()["items"]}
    assert flow_id in listed

    r_del = client.delete(
        f"/v0/orgs/{TEST_ORG_ID}/flows/{flow_id}",
        headers=get_auth_headers(),
    )
    assert r_del.status_code == 200, r_del.text


@pytest.mark.asyncio
async def test_post_flow_with_empty_graph_rolls_back_and_returns_400(test_db, mock_auth):
    """Atomic create must not persist a header when the first revision has no trigger."""

    r = client.post(
        f"/v0/orgs/{TEST_ORG_ID}/flows",
        json={
            "name": "Empty canvas",
            "nodes": [],
            "connections": {},
            "settings": {},
            "pin_data": None,
        },
        headers=get_auth_headers(),
    )
    assert r.status_code == 400, r.text
    assert "trigger" in (r.json().get("detail") or "").lower()
    assert await test_db.flows.count_documents({"organization_id": TEST_ORG_ID, "name": "Empty canvas"}) == 0


@pytest.mark.asyncio
async def test_post_flow_with_graph_roll_back_header_on_save_failure(test_db, mock_auth):
    """Any failure inside save_revision rolls back the new header — not only FastAPI HTTPException."""

    fname = "Atomic create rollback"
    with patch.object(flows_routes, "save_revision", side_effect=RuntimeError("simulated infra failure")):
        # TestClient surfaces unhandled ``RuntimeError`` via ``raise_server_exceptions=True`` default.
        with pytest.raises(RuntimeError, match="simulated infra failure"):
            client.post(
                f"/v0/orgs/{TEST_ORG_ID}/flows",
                json={
                    "name": fname,
                    "nodes": [_std_manual_node()],
                    "connections": {},
                    "settings": {},
                    "pin_data": None,
                },
                headers=get_auth_headers(),
            )
    assert await test_db.flows.count_documents({"organization_id": TEST_ORG_ID, "name": fname}) == 0


@pytest.mark.asyncio
async def test_post_flow_name_only_still_supported(test_db, mock_auth):
    """Programmatic callers can POST name-only (no revision yet)."""

    r = client.post(
        f"/v0/orgs/{TEST_ORG_ID}/flows",
        json={"name": "Header only POST"},
        headers=get_auth_headers(),
    )
    assert r.status_code == 200, r.text
    body = r.json()
    flow_id = body["flow"]["flow_id"]
    assert body.get("revision") is None

    r_del = client.delete(
        f"/v0/orgs/{TEST_ORG_ID}/flows/{flow_id}",
        headers=get_auth_headers(),
    )
    assert r_del.status_code == 200, r_del.text
