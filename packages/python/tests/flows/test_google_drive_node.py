from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

import analytiq_data as ad


def _register_nodes() -> None:
    ad.flows.register_builtin_nodes()


@pytest.fixture
def schema() -> dict:
    path = (
        Path(__file__).resolve().parents[2]
        / "analytiq_data"
        / "flows"
        / "nodes"
        / "google_drive"
        / "parameter.schema.json"
    )
    return json.loads(path.read_text(encoding="utf-8"))


def test_google_drive_node_is_experimental() -> None:
    _register_nodes()
    nt = ad.flows.get("flows.google_drive")
    assert getattr(nt, "experimental", False) is True
    assert nt.type_version == 3


def test_drive_file_id_from_docs_url() -> None:
    from analytiq_data.flows.nodes.google_drive.helpers import drive_file_id_from_param

    url = "https://docs.google.com/document/d/1QLUu--7KcnD5HNeY7NaOhtSQV-EH8US7UrtNkM7zigA/edit"
    assert drive_file_id_from_param(url) == "1QLUu--7KcnD5HNeY7NaOhtSQV-EH8US7UrtNkM7zigA"


def test_export_mime_defaults_match_n8n_v2() -> None:
    from analytiq_data.flows.nodes.google_drive.helpers import export_mime_for_google_app

    doc_mime = "application/vnd.google-apps.document"
    assert (
        export_mime_for_google_app(doc_mime, {})
        == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )
    sheet_mime = "application/vnd.google-apps.spreadsheet"
    assert export_mime_for_google_app(sheet_mime, {}) == "text/csv"
    assert (
        export_mime_for_google_app(
            doc_mime,
            {
                "googleFileConversion": {
                    "conversion": {"docsToFormat": "text/plain"},
                }
            },
        )
        == "text/plain"
    )


@pytest.mark.asyncio
async def test_export_falls_back_on_size_limit() -> None:
    from analytiq_data.flows.nodes.google_drive.api import (
        GoogleDriveApiError,
        google_export_file_bytes,
    )

    doc_mime = "application/vnd.google-apps.document"
    heavy = GoogleDriveApiError(
        "export failed (403): exportSizeLimitExceeded",
        status_code=403,
    )
    calls: list[str] = []

    async def fake_request(token, method, path, **kwargs):
        export_mime = kwargs["query"]["mimeType"]
        calls.append(export_mime)
        if export_mime == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
            raise heavy
        return b"ok"

    with patch(
        "analytiq_data.flows.nodes.google_drive.api.google_api_request",
        new_callable=AsyncMock,
        side_effect=fake_request,
    ):
        content, out_mime = await google_export_file_bytes(
            "tok", "file-id", doc_mime, {}
        )
    assert content == b"ok"
    assert out_mime == "text/html"
    assert calls[0] == (
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )
    assert "text/html" in calls


@pytest.mark.asyncio
async def test_file_download_preserves_meta() -> None:
    from analytiq_data.flows.nodes.google_drive.operations import _file_download

    item = ad.flows.FlowItem(json={"x": 1}, binary={}, meta={"trace": "t1"})
    with (
        patch(
            "analytiq_data.flows.nodes.google_drive.operations.google_api_request",
            new_callable=AsyncMock,
            side_effect=[
                {"mimeType": "application/pdf", "name": "report.pdf"},
                b"%PDF-1.4",
            ],
        ),
    ):
        out = await _file_download(
            context=None,  # type: ignore[arg-type]
            token="tok",
            file_id="fid",
            params={},
            item=item,
            options={},
        )
    assert out.meta == {"trace": "t1"}
    assert "data" in out.binary


@pytest.mark.asyncio
async def test_upload_multipart_uses_google_upload_path() -> None:
    from analytiq_data.flows.nodes.google_drive.api import upload_multipart_file

    captured: dict[str, str] = {}

    async def fake_request(token, method, path, **kwargs):
        captured["path"] = path
        return {"id": "new-file"}

    with patch(
        "analytiq_data.flows.nodes.google_drive.api.google_api_request",
        new_callable=AsyncMock,
        side_effect=fake_request,
    ):
        out = await upload_multipart_file("tok", {"name": "x"}, b"data", "text/plain")
    assert out["id"] == "new-file"
    assert captured["path"] == "/upload/drive/v3/files"


def test_parameter_schema_merges_operations(schema: dict) -> None:
    op = schema["properties"]["operation"]
    assert "x-ui-enum-by" in op
    assert "upload" in op["enum"]
    assert "search" in op["enum"]
    keys = list(schema["properties"].keys())
    assert keys.index("fileId") < keys.index("options")
    assert schema["properties"]["fileId"]["title"] == "File"


@pytest.mark.asyncio
async def test_drive_get_calls_api() -> None:
    _register_nodes()
    nt = ad.flows.get("flows.google_drive")
    node = {
        "id": "n1",
        "name": "Drive",
        "type": "flows.google_drive",
        "parameters": {
            "authentication": "oAuth2",
            "resource": "drive",
            "operation": "get",
            "driveId": "abc123",
        },
        "credentials": {"googleDriveOAuth2Api": "cred-1"},
    }
    item = ad.flows.FlowItem(json={}, binary={}, meta={})
    ctx = ad.flows.ExecutionContext(
        execution_id="e1",
        flow_id="f1",
        flow_revid="r1",
        organization_id="org1",
        mode="manual",
        trigger_data={},
        run_data={},
        revision_nodes=[],
        credentials={},
        analytiq_client=None,
    )

    with (
        patch(
            "analytiq_data.flows.nodes.google_drive.operations.resolve_oauth_access_token",
            new_callable=AsyncMock,
            return_value="tok",
        ),
        patch(
            "analytiq_data.flows.nodes.google_drive.operations.google_api_request",
            new_callable=AsyncMock,
            return_value={"id": "abc123", "name": "Team Drive"},
        ) as mock_req,
    ):
        out = await nt.execute(ctx, node, [[item]])
    assert len(out[0]) == 1
    assert out[0][0].json["name"] == "Team Drive"
    mock_req.assert_awaited_once()
    assert mock_req.await_args.args[2] == "/drive/v3/drives/abc123"
