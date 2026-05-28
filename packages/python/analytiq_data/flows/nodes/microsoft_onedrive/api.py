"""OneDrive OAuth credential binding for ``flows.integrations.microsoft``."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from analytiq_data.flows.integrations.microsoft import resolve_graph_oauth_token

if TYPE_CHECKING:
    from analytiq_data.flows.context import ExecutionContext

_ONEDRIVE_CREDENTIAL_SLOT = "microsoftOneDriveOAuth2Api"
_PRODUCT_LABEL = "Microsoft OneDrive"


async def resolve_oauth_access_token_for_org(
    organization_id: str, node: dict[str, Any]
) -> str:
    return await resolve_graph_oauth_token(
        organization_id,
        node,
        _ONEDRIVE_CREDENTIAL_SLOT,
        product_label=_PRODUCT_LABEL,
    )


async def resolve_oauth_access_token(
    context: "ExecutionContext",
    node: dict[str, Any],
) -> str:
    return await resolve_oauth_access_token_for_org(context.organization_id, node)
