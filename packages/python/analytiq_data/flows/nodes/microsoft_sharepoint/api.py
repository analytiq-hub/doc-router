"""SharePoint OAuth credential binding for ``flows.microsoft_sharepoint``."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import analytiq_data as ad

from analytiq_data.flows.credential_runtime import normalize_sharepoint_subdomain
from analytiq_data.flows.integrations.microsoft import resolve_graph_oauth_token

if TYPE_CHECKING:
    from analytiq_data.flows.context import ExecutionContext

_SHAREPOINT_CREDENTIAL_SLOT = "microsoftSharePointOAuth2Api"
_PRODUCT_LABEL = "Microsoft SharePoint"


async def resolve_sharepoint_subdomain_for_org(
    organization_id: str, node: dict[str, Any]
) -> str:
    bindings = node.get("credentials") if isinstance(node.get("credentials"), dict) else {}
    cred_id = bindings.get(_SHAREPOINT_CREDENTIAL_SLOT)
    if not cred_id:
        raise RuntimeError(
            f"{_PRODUCT_LABEL} requires a {_SHAREPOINT_CREDENTIAL_SLOT} credential on the node."
        )
    _kind, fields = await ad.flows.fetch_credential_kind_and_fields(
        organization_id, str(cred_id)
    )
    slug = normalize_sharepoint_subdomain(fields.get("subdomain"))
    if not slug:
        raise RuntimeError(
            f"{_PRODUCT_LABEL} credential is missing subdomain. "
            "Set the tenant slug from your SharePoint URL on the credential and reconnect."
        )
    return slug


async def resolve_oauth_access_token_for_org(
    organization_id: str, node: dict[str, Any]
) -> str:
    return await resolve_graph_oauth_token(
        organization_id,
        node,
        _SHAREPOINT_CREDENTIAL_SLOT,
        product_label=_PRODUCT_LABEL,
    )


async def resolve_oauth_access_token(
    context: "ExecutionContext",
    node: dict[str, Any],
) -> str:
    return await resolve_oauth_access_token_for_org(context.organization_id, node)


async def resolve_sharepoint_subdomain(
    context: "ExecutionContext",
    node: dict[str, Any],
) -> str:
    return await resolve_sharepoint_subdomain_for_org(context.organization_id, node)
