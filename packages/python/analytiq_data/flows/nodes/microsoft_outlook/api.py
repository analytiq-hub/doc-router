"""Outlook credential binding and Graph requests with shared-mailbox support."""

from __future__ import annotations

from typing import Any

import analytiq_data as ad

from analytiq_data.flows.integrations.microsoft import (
    graph_mailbox_base_url,
    graph_request,
    graph_request_all_items,
    resolve_graph_oauth_token,
)

_OUTLOOK_CREDENTIAL_SLOT = "microsoftOutlookOAuth2Api"
_PRODUCT_LABEL = "Microsoft Outlook"


async def resolve_outlook_auth(
    context: "ad.flows.ExecutionContext",
    node: dict[str, Any],
) -> tuple[str, dict[str, Any], str]:
    """Return ``(access_token, credential_fields, mailbox_base_url)``."""

    organization_id = context.organization_id
    bindings = node.get("credentials") if isinstance(node.get("credentials"), dict) else {}
    cred_id = bindings.get(_OUTLOOK_CREDENTIAL_SLOT)
    if not cred_id:
        raise RuntimeError(
            f"{_PRODUCT_LABEL} requires a {_OUTLOOK_CREDENTIAL_SLOT} credential on the node."
        )
    _kind, fields = await ad.flows.fetch_credential_kind_and_fields(
        organization_id, str(cred_id)
    )
    token = await resolve_graph_oauth_token(
        organization_id,
        node,
        _OUTLOOK_CREDENTIAL_SLOT,
        product_label=_PRODUCT_LABEL,
    )
    mailbox_base = graph_mailbox_base_url(fields)
    return token, fields, mailbox_base


async def outlook_request(
    context: "ad.flows.ExecutionContext",
    token: str,
    mailbox_base: str,
    method: str,
    path: str,
    **kwargs: Any,
) -> Any:
    return await graph_request(
        token,
        method,
        path,
        mailbox_base=mailbox_base,
        context=context,
        trace_node_id=context.active_trace_node_id,
        **kwargs,
    )


async def outlook_request_all_items(
    context: "ad.flows.ExecutionContext",
    token: str,
    mailbox_base: str,
    method: str,
    path: str,
    *,
    query: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    return await graph_request_all_items(
        context,
        token,
        method,
        path,
        query=query,
        mailbox_base=mailbox_base,
        trace_node_id=context.active_trace_node_id,
    )
