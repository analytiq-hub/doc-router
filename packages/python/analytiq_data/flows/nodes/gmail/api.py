"""Gmail API v1 HTTP client for ``flows.gmail``."""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any

import httpx

import analytiq_data as ad

if TYPE_CHECKING:
    from analytiq_data.flows.context import ExecutionContext

_API_ROOT = "https://www.googleapis.com"


class GmailApiError(RuntimeError):
    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


async def resolve_oauth_access_token_for_org(organization_id: str, node: dict[str, Any]) -> str:
    """Resolve OAuth access token from a node credential binding."""

    bindings = node.get("credentials") if isinstance(node.get("credentials"), dict) else {}
    cred_id = bindings.get("gmailOAuth2")
    if not cred_id:
        raise RuntimeError("Gmail requires a gmailOAuth2 credential on the node.")
    _kind, fields = await ad.flows.fetch_credential_kind_and_fields(
        organization_id, str(cred_id)
    )
    token = str(fields.get("oauthAccessToken") or "").strip()
    if not token:
        raise RuntimeError(
            "Gmail OAuth2 credential has no access token. Connect the credential and try again."
        )
    return token


async def resolve_oauth_access_token(
    context: "ad.flows.ExecutionContext",
    node: dict[str, Any],
) -> str:
    return await resolve_oauth_access_token_for_org(context.organization_id, node)


async def gmail_api_request(
    token: str,
    method: str,
    path: str,
    *,
    body: Any = None,
    query: dict[str, Any] | None = None,
    context: ExecutionContext | None = None,
    trace_node_id: str | None = None,
) -> Any:
    """Call ``www.googleapis.com/gmail/v1/...``."""

    qs = {k: v for k, v in (query or {}).items() if v is not None and v != ""}
    req_url = f"{_API_ROOT}{path}"
    hdrs = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
    if body is not None:
        hdrs["Content-Type"] = "application/json"

    started = time.monotonic()
    async with httpx.AsyncClient(timeout=120.0) as client:
        resp = await client.request(
            method.upper(),
            req_url,
            params=qs,
            json=body,
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
        raise GmailApiError(
            f"Gmail API {method} {path} failed ({resp.status_code}): {detail}",
            status_code=resp.status_code,
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
    if resp.status_code == 204 or not resp.content:
        return {}
    return resp.json()


async def gmail_api_request_all_items(
    context: ExecutionContext | None,
    token: str,
    method: str,
    path: str,
    property_name: str,
    *,
    body: Any = None,
    query: dict[str, Any] | None = None,
    trace_node_id: str | None = None,
) -> list[dict[str, Any]]:
    qs = dict(query or {})
    qs.setdefault("maxResults", 100)
    out: list[dict[str, Any]] = []
    while True:
        data = await gmail_api_request(
            token,
            method,
            path,
            body=body,
            query=qs,
            context=context,
            trace_node_id=trace_node_id,
        )
        if not isinstance(data, dict):
            break
        chunk = data.get(property_name)
        if isinstance(chunk, list):
            out.extend(x for x in chunk if isinstance(x, dict))
        page = data.get("nextPageToken")
        if not page:
            break
        qs["pageToken"] = page
    return out
