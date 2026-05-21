"""Google Drive API v3 HTTP client for ``flows.google_drive``."""

from __future__ import annotations

import json
import secrets
import uuid
from typing import Any

import httpx

import analytiq_data as ad

_API_ROOT = "https://www.googleapis.com"
_UPLOAD_ROOT = "https://www.googleapis.com/upload"


class GoogleDriveApiError(RuntimeError):
    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


async def resolve_oauth_access_token(
    context: "ad.flows.ExecutionContext",
    node: dict[str, Any],
) -> str:
    bindings = node.get("credentials") if isinstance(node.get("credentials"), dict) else {}
    cred_id = bindings.get("googleDriveOAuth2Api")
    if not cred_id:
        raise RuntimeError(
            "Google Drive requires a googleDriveOAuth2Api credential on the node."
        )
    _kind, fields = await ad.flows.fetch_credential_kind_and_fields(
        context.organization_id, str(cred_id)
    )
    token = str(fields.get("oauthAccessToken") or "").strip()
    if not token:
        raise RuntimeError(
            "Google Drive OAuth2 credential has no access token. Connect the credential and try again."
        )
    return token


async def google_api_request(
    token: str,
    method: str,
    path: str,
    *,
    body: Any = None,
    query: dict[str, Any] | None = None,
    url: str | None = None,
    headers: dict[str, str] | None = None,
    expect_json: bool = True,
) -> Any:
    """Call ``www.googleapis.com`` (or upload host when *path* starts with ``/upload``)."""

    qs = {k: v for k, v in (query or {}).items() if v is not None and v != ""}
    if url:
        req_url = url
    else:
        base = _UPLOAD_ROOT if path.startswith("/upload") else _API_ROOT
        req_url = f"{base}{path}"
    hdrs = {"Authorization": f"Bearer {token}"}
    if headers:
        hdrs.update(headers)
    if body is not None and "Content-Type" not in hdrs:
        hdrs["Content-Type"] = "application/json"

    async with httpx.AsyncClient(timeout=120.0) as client:
        resp = await client.request(
            method.upper(),
            req_url,
            params=qs,
            content=None if body is None else (body if isinstance(body, (bytes, str)) else None),
            json=None if body is None or isinstance(body, (bytes, str)) else body,
            headers=hdrs,
        )
    if resp.status_code >= 400:
        detail = resp.text[:500]
        raise GoogleDriveApiError(
            f"Google Drive API {method} {path} failed ({resp.status_code}): {detail}",
            status_code=resp.status_code,
        )
    if not expect_json:
        return resp.content
    if not resp.content:
        return {}
    return resp.json()


async def google_api_request_all_items(
    token: str,
    method: str,
    path: str,
    property_name: str,
    *,
    body: Any = None,
    query: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    qs = dict(query or {})
    qs.setdefault("pageSize", qs.pop("maxResults", None) or qs.get("pageSize") or 100)
    out: list[dict[str, Any]] = []
    while True:
        data = await google_api_request(token, method, path, body=body, query=qs)
        if not isinstance(data, dict):
            break
        chunk = data.get(property_name)
        if isinstance(chunk, list):
            out.extend(x for x in chunk if isinstance(x, dict))
        token_page = data.get("nextPageToken")
        if not token_page:
            break
        qs["pageToken"] = token_page
    return out


def multipart_related_body(metadata: dict[str, Any], data: bytes, mime_type: str) -> tuple[bytes, str]:
    boundary = secrets.token_hex(16)
    meta_part = (
        f"--{boundary}\r\n"
        "Content-Type: application/json; charset=UTF-8\r\n\r\n"
        f"{json.dumps(metadata)}\r\n"
    ).encode()
    data_part = (
        f"--{boundary}\r\n"
        f"Content-Type: {mime_type}\r\n\r\n"
    ).encode() + data + f"\r\n--{boundary}--\r\n".encode()
    body = meta_part + data_part
    content_type = f"multipart/related; boundary={boundary}"
    return body, content_type


async def upload_multipart_file(
    token: str,
    metadata: dict[str, Any],
    data: bytes,
    mime_type: str,
) -> dict[str, Any]:
    body, content_type = multipart_related_body(metadata, data, mime_type)
    result = await google_api_request(
        token,
        "POST",
        "/upload/drive/v3/files",
        body=body,
        query={"uploadType": "multipart", "supportsAllDrives": True},
        headers={"Content-Type": content_type},
    )
    return result if isinstance(result, dict) else {}


async def resumable_upload(
    token: str,
    metadata: dict[str, Any],
    data: bytes,
    mime_type: str,
) -> str:
    """Resumable upload; returns file id."""

    async with httpx.AsyncClient(timeout=300.0) as client:
        init = await client.post(
            f"{_UPLOAD_ROOT}/upload/drive/v3/files",
            params={"uploadType": "resumable", "supportsAllDrives": "true"},
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
                "X-Upload-Content-Type": mime_type,
            },
            json=metadata,
        )
        if init.status_code >= 400:
            raise GoogleDriveApiError(
                f"Google Drive resumable upload init failed ({init.status_code}): {init.text[:500]}",
                status_code=init.status_code,
            )
        upload_url = init.headers.get("Location")
        if not upload_url:
            raise GoogleDriveApiError("Google Drive resumable upload missing Location header")

        chunk_size = 2048 * 1024
        offset = 0
        length = len(data)
        file_id: str | None = None
        while offset < length:
            chunk = data[offset : offset + chunk_size]
            end = offset + len(chunk) - 1
            put = await client.put(
                upload_url,
                content=chunk,
                headers={
                    "Content-Length": str(len(chunk)),
                    "Content-Range": f"bytes {offset}-{end}/{length}",
                },
            )
            if put.status_code == 308:
                offset += len(chunk)
                continue
            if put.status_code >= 400:
                raise GoogleDriveApiError(
                    f"Google Drive resumable upload chunk failed ({put.status_code}): {put.text[:500]}",
                    status_code=put.status_code,
                )
            if put.content:
                try:
                    parsed = put.json()
                    if isinstance(parsed, dict) and parsed.get("id"):
                        file_id = str(parsed["id"])
                except json.JSONDecodeError:
                    pass
            offset += len(chunk)
        if not file_id:
            raise GoogleDriveApiError("Google Drive resumable upload did not return a file id")
        return file_id


def new_drive_request_id() -> str:
    return str(uuid.uuid4())
