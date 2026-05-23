"""Google Drive API v3 HTTP client for ``flows.google_drive``."""

from __future__ import annotations

import json
import secrets
import time
import uuid
from typing import TYPE_CHECKING, Any

import httpx

import analytiq_data as ad

if TYPE_CHECKING:
    from analytiq_data.flows.context import ExecutionContext

_API_ROOT = "https://www.googleapis.com"


class GoogleDriveApiError(RuntimeError):
    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


def is_export_size_limit_error(exc: BaseException) -> bool:
    """True when Google Drive refused export because the converted file is too large."""

    if not isinstance(exc, GoogleDriveApiError) or exc.status_code != 403:
        return False
    msg = str(exc).lower()
    compact = msg.replace("_", "").lower()
    return "exportsizelimitexceeded" in compact or "too large to be exported" in msg


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
    context: ExecutionContext | None = None,
    trace_node_id: str | None = None,
) -> Any:
    """Call ``www.googleapis.com`` (upload paths use ``/upload/drive/v3/...``)."""

    qs = {k: v for k, v in (query or {}).items() if v is not None and v != ""}
    if url:
        req_url = url
    else:
        # Upload endpoints use ``/upload/drive/v3/...`` under www.googleapis.com (not a separate host path).
        req_url = f"{_API_ROOT}{path}"
    hdrs = {"Authorization": f"Bearer {token}"}
    if headers:
        hdrs.update(headers)
    if body is not None and "Content-Type" not in hdrs:
        hdrs["Content-Type"] = "application/json"

    started = time.monotonic()
    async with httpx.AsyncClient(timeout=120.0) as client:
        resp = await client.request(
            method.upper(),
            req_url,
            params=qs,
            content=None if body is None else (body if isinstance(body, (bytes, str)) else None),
            json=None if body is None or isinstance(body, (bytes, str)) else body,
            headers=hdrs,
        )
    duration_ms = int((time.monotonic() - started) * 1000)
    if resp.status_code >= 400:
        detail = resp.text[:500]
        if context is not None:
            ad.flows.trace_http(
                context,
                trace_node_id,
                method=method,
                url=req_url,
                status_code=resp.status_code,
                duration_ms=duration_ms,
                response_preview=detail,
            )
        raise GoogleDriveApiError(
            f"Google Drive API {method} {path} failed ({resp.status_code}): {detail}",
            status_code=resp.status_code,
        )
    if context is not None:
        ad.flows.trace_http_on_debug(
            context,
            trace_node_id,
            method=method,
            url=req_url,
            status_code=resp.status_code,
            duration_ms=duration_ms,
            response_preview=resp.text[:500] if resp.text else None,
        )
    if not expect_json:
        return resp.content
    if not resp.content:
        return {}
    return resp.json()


async def google_export_file_bytes(
    context: ExecutionContext | None,
    token: str,
    file_id: str,
    google_mime: str,
    options: dict[str, Any],
) -> tuple[bytes, str]:
    """
    Export a native Google file, using n8n-style MIME defaults and lighter fallbacks
    when Google returns ``exportSizeLimitExceeded``.
    """

    from .helpers import export_fallback_mimes, export_mime_for_google_app

    primary = export_mime_for_google_app(google_mime, options)
    candidates = [primary]
    for alt in export_fallback_mimes(google_mime, primary):
        if alt not in candidates:
            candidates.append(alt)

    last_err: GoogleDriveApiError | None = None
    for export_mime in candidates:
        try:
            content = await google_api_request(
                token,
                "GET",
                f"/drive/v3/files/{file_id}/export",
                query={"mimeType": export_mime, "supportsAllDrives": True},
                expect_json=False,
                context=context,
            )
            if not isinstance(content, bytes):
                content = bytes(content) if content is not None else b""
            return content, export_mime
        except GoogleDriveApiError as e:
            if not is_export_size_limit_error(e):
                raise
            last_err = e

    if last_err is not None:
        raise GoogleDriveApiError(
            "This Google file is too large to export in any supported format. "
            "Use **File → Copy** to duplicate it in Drive, or under Download options set "
            "**Google File Conversion** to a lighter format (e.g. Text or HTML for Docs).",
            status_code=403,
        ) from last_err
    raise GoogleDriveApiError("Google Drive export failed", status_code=500)


async def google_api_request_all_items(
    context: ExecutionContext | None,
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
        data = await google_api_request(token, method, path, body=body, query=qs, context=context)
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
    context: ExecutionContext | None,
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
        context=context,
    )
    return result if isinstance(result, dict) else {}


async def resumable_upload(
    context: ExecutionContext | None,
    token: str,
    metadata: dict[str, Any],
    data: bytes,
    mime_type: str,
) -> str:
    """Resumable upload; returns file id."""

    init_url = f"{_API_ROOT}/upload/drive/v3/files"
    started = time.monotonic()
    async with httpx.AsyncClient(timeout=300.0) as client:
        init = await client.post(
            init_url,
            params={"uploadType": "resumable", "supportsAllDrives": "true"},
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
                "X-Upload-Content-Type": mime_type,
            },
            json=metadata,
        )
        if init.status_code >= 400:
            detail = init.text[:500]
            if context is not None:
                ad.flows.trace_http(
                    context,
                    None,
                    method="POST",
                    url=init_url,
                    status_code=init.status_code,
                    duration_ms=int((time.monotonic() - started) * 1000),
                    response_preview=detail,
                )
            raise GoogleDriveApiError(
                f"Google Drive resumable upload init failed ({init.status_code}): {detail}",
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
                detail = put.text[:500]
                if context is not None:
                    ad.flows.trace_http(
                        context,
                        None,
                        method="PUT",
                        url=upload_url,
                        status_code=put.status_code,
                        duration_ms=int((time.monotonic() - started) * 1000),
                        response_preview=detail,
                    )
                raise GoogleDriveApiError(
                    f"Google Drive resumable upload chunk failed ({put.status_code}): {detail}",
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
