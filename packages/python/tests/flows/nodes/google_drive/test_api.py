from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

import pytest

from analytiq_data.flows.nodes.google_drive.api import (
    GoogleDriveApiError,
    google_api_request_all_items,
    google_export_file_bytes,
    is_export_size_limit_error,
    multipart_related_body,
    upload_multipart_file,
)

_GOOGLE_EXPORT_SIZE_LIMIT_BODY = {
    "error": {
        "code": 403,
        "message": "This file is too large to be exported.",
        "errors": [
            {
                "domain": "global",
                "reason": "exportSizeLimitExceeded",
                "message": "This file is too large to be exported.",
            }
        ],
        "status": "PERMISSION_DENIED",
    }
}

_GOOGLE_INSUFFICIENT_PERMISSIONS_BODY = {
    "error": {
        "code": 403,
        "message": "Insufficient permissions for this file.",
        "errors": [
            {
                "domain": "global",
                "reason": "insufficientFilePermissions",
                "message": "Insufficient permissions for this file.",
            }
        ],
        "status": "PERMISSION_DENIED",
    }
}


def _drive_api_error_from_response(
    method: str,
    path: str,
    status_code: int,
    body: dict,
) -> GoogleDriveApiError:
    """Mirror ``google_api_request`` error formatting for realistic API bodies."""

    detail = json.dumps(body, separators=(",", ":"))
    return GoogleDriveApiError(
        f"Google Drive API {method} {path} failed ({status_code}): {detail}",
        status_code=status_code,
    )


def test_is_export_size_limit_error() -> None:
    assert is_export_size_limit_error(
        GoogleDriveApiError("export failed (403): exportSizeLimitExceeded", status_code=403)
    )
    assert not is_export_size_limit_error(
        GoogleDriveApiError("not found", status_code=404)
    )


def test_is_export_size_limit_error_google_json_body() -> None:
    exc = _drive_api_error_from_response(
        "GET",
        "/drive/v3/files/abc/export",
        403,
        _GOOGLE_EXPORT_SIZE_LIMIT_BODY,
    )
    assert is_export_size_limit_error(exc)


def test_is_export_size_limit_error_rejects_other_403_reasons() -> None:
    exc = _drive_api_error_from_response(
        "GET",
        "/drive/v3/files/abc/export",
        403,
        _GOOGLE_INSUFFICIENT_PERMISSIONS_BODY,
    )
    assert not is_export_size_limit_error(exc)


def test_multipart_related_body_has_boundary() -> None:
    body, content_type = multipart_related_body({"name": "x"}, b"data", "text/plain")
    assert b"name" in body
    assert b"data" in body
    assert "multipart/related" in content_type
    assert "boundary=" in content_type


@pytest.mark.asyncio
async def test_export_falls_back_on_size_limit() -> None:
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
            None, "tok", "file-id", doc_mime, {}
        )
    assert content == b"ok"
    assert out_mime == "text/html"
    assert calls[0] == (
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )
    assert "text/html" in calls


@pytest.mark.asyncio
async def test_export_reraises_non_size_limit_403_without_fallback() -> None:
    doc_mime = "application/vnd.google-apps.document"
    perm_err = _drive_api_error_from_response(
        "GET",
        "/drive/v3/files/file-id/export",
        403,
        _GOOGLE_INSUFFICIENT_PERMISSIONS_BODY,
    )
    calls: list[str] = []

    async def fake_request(token, method, path, **kwargs):
        calls.append(kwargs["query"]["mimeType"])
        raise perm_err

    with patch(
        "analytiq_data.flows.nodes.google_drive.api.google_api_request",
        new_callable=AsyncMock,
        side_effect=fake_request,
    ):
        with pytest.raises(GoogleDriveApiError, match="Insufficient permissions"):
            await google_export_file_bytes(None, "tok", "file-id", doc_mime, {})
    assert len(calls) == 1


@pytest.mark.asyncio
async def test_export_falls_back_on_google_json_size_limit() -> None:
    doc_mime = "application/vnd.google-apps.document"
    size_err = _drive_api_error_from_response(
        "GET",
        "/drive/v3/files/file-id/export",
        403,
        _GOOGLE_EXPORT_SIZE_LIMIT_BODY,
    )
    calls: list[str] = []

    async def fake_request(token, method, path, **kwargs):
        export_mime = kwargs["query"]["mimeType"]
        calls.append(export_mime)
        if export_mime == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
            raise size_err
        return b"ok"

    with patch(
        "analytiq_data.flows.nodes.google_drive.api.google_api_request",
        new_callable=AsyncMock,
        side_effect=fake_request,
    ):
        content, out_mime = await google_export_file_bytes(
            None, "tok", "file-id", doc_mime, {}
        )
    assert content == b"ok"
    assert out_mime == "text/html"
    assert len(calls) >= 2


@pytest.mark.asyncio
async def test_upload_multipart_uses_google_upload_path() -> None:
    captured: dict[str, str] = {}

    async def fake_request(token, method, path, **kwargs):
        captured["path"] = path
        return {"id": "new-file"}

    with patch(
        "analytiq_data.flows.nodes.google_drive.api.google_api_request",
        new_callable=AsyncMock,
        side_effect=fake_request,
    ):
        out = await upload_multipart_file(None, "tok", {"name": "x"}, b"data", "text/plain")
    assert out["id"] == "new-file"
    assert captured["path"] == "/upload/drive/v3/files"


@pytest.mark.asyncio
async def test_google_api_request_all_items_paginates() -> None:
    async def fake_request(token, method, path, **kwargs):
        if "pageToken" not in (kwargs.get("query") or {}):
            return {
                "drives": [{"id": "d1"}],
                "nextPageToken": "page-2",
            }
        return {"drives": [{"id": "d2"}]}

    with patch(
        "analytiq_data.flows.nodes.google_drive.api.google_api_request",
        new_callable=AsyncMock,
        side_effect=fake_request,
    ):
        items = await google_api_request_all_items(
            None, "tok", "GET", "/drive/v3/drives", "drives"
        )
    assert [d["id"] for d in items] == ["d1", "d2"]
