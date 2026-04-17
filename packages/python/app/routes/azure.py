# azure.py — Microsoft Entra service principal in cloud_config (type azure)

import re
from datetime import UTC, datetime
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

import analytiq_data as ad
from app.auth import get_admin_user
from app.models import User
from app.secret_mask import mask_secret_plaintext

azure_router = APIRouter(tags=["account/azure"])

# Microsoft Entra directory (tenant) and application (client) IDs are GUIDs.
_GUID_RE = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)


def _valid_https_api_base(url: str) -> bool:
    u = urlparse(url.strip())
    return u.scheme == "https" and bool(u.netloc)


class AzureServicePrincipalRequest(BaseModel):
    tenant_id: str
    client_id: str
    client_secret: str
    #: LiteLLM / Foundry base URL (e.g. ``https://<resource>.services.ai.azure.com``). Stored plaintext in MongoDB.
    api_base: str


class AzureServicePrincipalResponse(BaseModel):
    """``tenant_id``, ``client_id``, and ``api_base`` are returned in full. Only ``client_secret`` is masked."""

    tenant_id: str
    client_id: str
    client_secret: str
    api_base: str


@azure_router.post("/v0/account/azure_config")
async def create_azure_config(
    config: AzureServicePrincipalRequest,
    current_user: User = Depends(get_admin_user),
):
    """Create or update Azure Entra service principal (admin only)."""
    tenant_id = (config.tenant_id or "").strip()
    client_id = (config.client_id or "").strip()
    client_secret = (config.client_secret or "").strip()
    api_base_in = (config.api_base or "").strip().rstrip("/")

    if not tenant_id or not client_id or not client_secret or not api_base_in:
        raise HTTPException(
            status_code=400,
            detail="tenant_id, client_id, client_secret, and api_base are required",
        )
    if not _GUID_RE.match(tenant_id):
        raise HTTPException(status_code=400, detail="tenant_id must be a valid GUID")
    if not _GUID_RE.match(client_id):
        raise HTTPException(status_code=400, detail="client_id must be a valid GUID")
    if len(client_secret) < 8:
        raise HTTPException(
            status_code=400,
            detail="client_secret is too short",
        )

    if not _valid_https_api_base(api_base_in):
        raise HTTPException(
            status_code=400,
            detail="api_base must be a valid https URL (Foundry / Azure AI endpoint)",
        )

    db = ad.common.get_async_db()
    now = datetime.now(UTC)
    update_data = {
        "type": "azure",
        "user_id": current_user.user_id,
        "tenant_id": ad.crypto.encrypt_token(tenant_id),
        "client_id": ad.crypto.encrypt_token(client_id),
        "client_secret": ad.crypto.encrypt_token(client_secret),
        "api_base": api_base_in,
        "created_at": now,
    }

    await db.cloud_config.update_one(
        {"type": "azure", "user_id": current_user.user_id},
        {"$set": update_data},
        upsert=True,
    )
    return {"message": "Azure configuration saved successfully"}


@azure_router.get(
    "/v0/account/azure_config",
    response_model=AzureServicePrincipalResponse,
    response_model_exclude_none=True,
)
async def get_azure_config(current_user: User = Depends(get_admin_user)):
    """Get Azure config (admin only). Only ``client_secret`` is masked for display."""
    db = ad.common.get_async_db()
    doc = await db.cloud_config.find_one({"type": "azure", "user_id": current_user.user_id})
    if not doc or not doc.get("tenant_id"):
        doc = await db.cloud_config.find_one({"type": "azure"})
    if not doc or not doc.get("tenant_id"):
        raise HTTPException(status_code=404, detail="Azure configuration not found")

    def decrypted_field(field: str) -> str:
        raw = doc.get(field) or ""
        if not raw:
            return ""
        try:
            return ad.crypto.decrypt_token(raw) or ""
        except Exception:
            return ""

    secret_plain = decrypted_field("client_secret")
    client_secret_masked = mask_secret_plaintext(secret_plain) or ""

    return AzureServicePrincipalResponse(
        tenant_id=decrypted_field("tenant_id"),
        client_id=decrypted_field("client_id"),
        client_secret=client_secret_masked,
        api_base=(doc.get("api_base") or "").strip(),
    )


@azure_router.delete("/v0/account/azure_config")
async def delete_azure_config(current_user: User = Depends(get_admin_user)):
    """Delete Azure configuration (admin only)."""
    db = ad.common.get_async_db()
    result = await db.cloud_config.delete_one({"type": "azure", "user_id": current_user.user_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Azure configuration not found")
    return {"message": "Azure configuration deleted successfully"}
