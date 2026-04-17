"""
Microsoft Foundry (litellm ``azure_ai``) authentication via Entra service principal.

Uses AsyncClientSecretCredential from azure.identity.aio.  Tokens are cached
inside the credential (~60 min lifetime, auto-refreshed by the Azure Identity client).
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

FOUNDRY_DEFAULT_TOKEN_SCOPE = "https://ai.azure.com/.default"

from azure.identity.aio import ClientSecretCredential

_credential: ClientSecretCredential | None = None
_credential_key: tuple | None = None


async def add_azure_params(params: dict) -> None:
    """
    For ``azure_ai`` models: remove ``api_key``, attach an async ``azure_ad_token_provider``
    backed by Azure service principal credentials from cloud_config.
    """
    global _credential, _credential_key

    import analytiq_data as ad
    from analytiq_data.cloud.cloud_config import get_azure_service_principal_dict

    params.pop("api_key", None)
    creds = await get_azure_service_principal_dict(ad.common.get_analytiq_client())
    tenant_id = (creds.get("tenant_id") or "").strip()
    client_id = (creds.get("client_id") or "").strip()
    client_secret = (creds.get("client_secret") or "").strip()
    if not tenant_id or not client_id or not client_secret:
        raise ValueError(
            "Microsoft Foundry (azure_ai) requires Azure service principal credentials. "
            "Configure Account → Development → Azure setup, or set "
            "AZURE_TENANT_ID, AZURE_CLIENT_ID, and AZURE_CLIENT_SECRET."
        )

    api_base = (creds.get("api_base") or "").strip()
    if not api_base:
        raise ValueError(
            "Microsoft Foundry (azure_ai) requires api_base (Foundry endpoint URL). "
            "Set AZURE_API_BASE or add API base in Account → Development → Azure setup."
        )

    key = (tenant_id, client_id, client_secret)
    if _credential_key != key:
        if _credential is not None:
            await _credential.close()
        _credential = ClientSecretCredential(
            tenant_id=tenant_id,
            client_id=client_id,
            client_secret=client_secret,
        )
        _credential_key = key
        logger.debug("Created AsyncClientSecretCredential for Microsoft Foundry (azure_ai)")

    token = (await _credential.get_token(FOUNDRY_DEFAULT_TOKEN_SCOPE)).token
    params["azure_ad_token_provider"] = lambda: token  # litellm requires a callable, not a string
    params["api_version"] = "2024-05-01-preview"
    params["api_base"] = api_base
