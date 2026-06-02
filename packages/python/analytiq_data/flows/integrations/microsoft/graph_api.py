"""Microsoft Graph HTTP client for flow integration nodes."""

from __future__ import annotations

import json
import time
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

import httpx

import analytiq_data as ad

if TYPE_CHECKING:
    from analytiq_data.flows.context import ExecutionContext

GRAPH_ME = "https://graph.microsoft.com/v1.0/me"
GRAPH_ROOT = "https://graph.microsoft.com/v1.0"
GRAPH_DRIVE_DELTA_LATEST = f"{GRAPH_ME}/drive/root/delta?token=latest"
GRAPH_DRIVE_DELTA_ROOT = f"{GRAPH_ME}/drive/root/delta"


def graph_mailbox_base_url(credential_fields: dict[str, Any]) -> str:
    """``/me`` or ``/users/{upn}`` for Outlook shared mailbox credentials."""

    use_shared = credential_fields.get("useShared") in (True, "true", "True", 1, "1")
    upn = str(credential_fields.get("userPrincipalName") or "").strip()
    if use_shared and upn:
        from urllib.parse import quote

        return f"{GRAPH_ROOT}/users/{quote(upn, safe='')}"
    return GRAPH_ME


def graph_url_for_path(path: str, *, mailbox_base: str | None = None) -> str:
    base = (mailbox_base or GRAPH_ME).rstrip("/")
    suffix = path if path.startswith("/") else f"/{path}"
    return f"{base}{suffix}"


class MicrosoftGraphApiError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        graph_message: str | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.graph_message = graph_message


def _graph_error_message_from_body(body: str) -> str | None:
    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, dict):
        return None
    err = payload.get("error")
    if not isinstance(err, dict):
        return None
    msg = err.get("message")
    return str(msg).strip() if msg else None


def graph_user_hint(graph_message: str | None) -> str | None:
    if not graph_message:
        return None
    lower = graph_message.lower()
    if "spo license" in lower or "sharepoint online" in lower:
        return (
            "This Microsoft account cannot use OneDrive sync via Graph: the tenant does not "
            "have SharePoint Online / OneDrive for Business. Use a Microsoft 365 user with "
            "OneDrive assigned, or a personal Microsoft account (enable personal accounts on "
            "your Entra app registration)."
        )
    return None


def format_graph_user_error(exc: MicrosoftGraphApiError) -> str:
    hint = graph_user_hint(exc.graph_message)
    if hint:
        return hint
    return str(exc)


async def resolve_graph_oauth_token(
    organization_id: str,
    node: dict[str, Any],
    credential_slot: str,
    *,
    product_label: str,
) -> str:
    bindings = node.get("credentials") if isinstance(node.get("credentials"), dict) else {}
    cred_id = bindings.get(credential_slot)
    if not cred_id:
        raise RuntimeError(
            f"{product_label} requires a {credential_slot} credential on the node."
        )
    _kind, fields = await ad.flows.fetch_credential_kind_and_fields(
        organization_id, str(cred_id)
    )
    token = str(fields.get("oauthAccessToken") or "").strip()
    if not token:
        raise RuntimeError(
            f"{product_label} OAuth2 credential has no access token. "
            "Connect the credential and try again."
        )
    return token


async def graph_request(
    token: str,
    method: str,
    path: str,
    *,
    body: Any = None,
    query: dict[str, Any] | None = None,
    url: str | None = None,
    mailbox_base: str | None = None,
    headers: dict[str, str] | None = None,
    expect_json: bool = True,
    context: ExecutionContext | None = None,
    trace_node_id: str | None = None,
) -> Any:
    qs = {k: v for k, v in (query or {}).items() if v is not None and v != ""}
    req_url = url if url else graph_url_for_path(path, mailbox_base=mailbox_base)
    hdrs: dict[str, str] = {"Authorization": f"Bearer {token}"}
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
        graph_msg = _graph_error_message_from_body(detail)
        raise MicrosoftGraphApiError(
            f"Microsoft Graph {method} {path} failed ({resp.status_code}): {detail}",
            status_code=resp.status_code,
            graph_message=graph_msg,
        )
    if context is not None:
        ad.flows.trace_http_on_success(
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


async def graph_request_with_response(
    token: str,
    method: str,
    path: str,
    *,
    body: Any = None,
    query: dict[str, Any] | None = None,
    url: str | None = None,
    mailbox_base: str | None = None,
    headers: dict[str, str] | None = None,
    context: ExecutionContext | None = None,
    trace_node_id: str | None = None,
) -> httpx.Response:
    qs = {k: v for k, v in (query or {}).items() if v is not None and v != ""}
    req_url = url if url else graph_url_for_path(path, mailbox_base=mailbox_base)
    hdrs: dict[str, str] = {"Authorization": f"Bearer {token}"}
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
        graph_msg = _graph_error_message_from_body(detail)
        raise MicrosoftGraphApiError(
            f"Microsoft Graph {method} {path} failed ({resp.status_code}): {detail}",
            status_code=resp.status_code,
            graph_message=graph_msg,
        )
    if context is not None:
        ad.flows.trace_http_on_success(
            context,
            trace_node_id,
            method=method,
            url=req_url,
            status_code=resp.status_code,
            duration_ms=duration_ms,
            response_preview=resp.text[:500] if resp.text else None,
        )
    return resp


async def graph_request_all_items(
    context: ExecutionContext | None,
    token: str,
    method: str,
    path: str,
    *,
    property_name: str = "value",
    body: Any = None,
    query: dict[str, Any] | None = None,
    mailbox_base: str | None = None,
    trace_node_id: str | None = None,
) -> list[dict[str, Any]]:
    qs = dict(query or {})
    qs.setdefault("$top", 100)
    items: list[dict[str, Any]] = []
    next_url: str | None = None

    while True:
        if next_url:
            page = await graph_request(
                token,
                method,
                "",
                url=next_url,
                body=body,
                context=context,
                trace_node_id=trace_node_id,
            )
        else:
            page = await graph_request(
                token,
                method,
                path,
                body=body,
                query=qs,
                mailbox_base=mailbox_base,
                context=context,
                trace_node_id=trace_node_id,
            )
        if not isinstance(page, dict):
            break
        chunk = page.get(property_name)
        if isinstance(chunk, list):
            items.extend(x for x in chunk if isinstance(x, dict))
        next_url = page.get("@odata.nextLink")
        if not next_url:
            break
        if "$top" in qs:
            del qs["$top"]
    return items


def _parse_graph_datetime(value: str) -> datetime:
    raw = value.strip()
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    return datetime.fromisoformat(raw).astimezone(UTC)


async def graph_request_all_items_delta(
    context: ExecutionContext | None,
    token: str,
    link: str,
    since_iso: str,
    event_type: str,
    *,
    trace_node_id: str | None = None,
) -> tuple[str, list[dict[str, Any]]]:
    since = _parse_graph_datetime(since_iso)
    return_data: list[dict[str, Any]] = []
    delta_link = ""
    uri = link

    while uri:
        page = await graph_request(
            token,
            "GET",
            "",
            url=uri,
            context=context,
            trace_node_id=trace_node_id,
        )
        if not isinstance(page, dict):
            break
        uri = str(page.get("@odata.nextLink") or "")
        values = page.get("value")
        if not isinstance(values, list):
            continue
        for value in values:
            if not isinstance(value, dict):
                continue
            fs = value.get("fileSystemInfo")
            if not isinstance(fs, dict):
                continue
            created_raw = str(fs.get("createdDateTime") or "")
            updated_raw = str(fs.get("lastModifiedDateTime") or "")
            if not created_raw or not updated_raw:
                continue
            created_ts = _parse_graph_datetime(created_raw)
            updated_ts = _parse_graph_datetime(updated_raw)
            if event_type == "created":
                if created_ts >= since:
                    return_data.append(value)
            elif updated_ts >= since and created_ts < since:
                return_data.append(value)
        delta_link = str(page.get("@odata.deltaLink") or delta_link)

    return delta_link, return_data


async def get_drive_folder_path(
    context: ExecutionContext | None,
    token: str,
    folder_id: str,
    *,
    trace_node_id: str | None = None,
) -> str:
    data = await graph_request(
        token,
        "GET",
        f"/drive/items/{folder_id}",
        context=context,
        trace_node_id=trace_node_id,
    )
    if not isinstance(data, dict) or not data.get("folder"):
        raise RuntimeError("Item to watch is not a folder")
    parent = data.get("parentReference")
    parent_path = ""
    if isinstance(parent, dict):
        parent_path = str(parent.get("path") or "")
    name = str(data.get("name") or "")
    return f"{parent_path}/{name}"
