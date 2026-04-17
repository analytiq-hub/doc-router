# azure.py — Microsoft Entra service principal in cloud_config (type azure)

import re
from datetime import UTC, datetime

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


class AzureServicePrincipalRequest(BaseModel):
    tenant_id: str
    client_id: str
    client_secret: str


class AzureServicePrincipalResponse(BaseModel):
    """Masked values; full secrets are never returned."""

    tenant_id: str
    client_id: str
    client_secret: str


@azure_router.post("/v0/account/azure_config")
async def create_azure_config(
    config: AzureServicePrincipalRequest,
    current_user: User = Depends(get_admin_user),
):
    """Create or update Azure Entra service principal (admin only)."""
    tenant_id = (config.tenant_id or "").strip()
    client_id = (config.client_id or "").strip()
    client_secret = (config.client_secret or "").strip()

    if not tenant_id or not client_id or not client_secret:
        raise HTTPException(
            status_code=400,
            detail="tenant_id, client_id, and client_secret are required",
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

    db = ad.common.get_async_db()
    now = datetime.now(UTC)
    update_data = {
        "type": "azure",
        "user_id": current_user.user_id,
        "tenant_id": ad.crypto.encrypt_token(tenant_id),
        "client_id": ad.crypto.encrypt_token(client_id),
        "client_secret": ad.crypto.encrypt_token(client_secret),
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
    """Get Azure service principal status (admin only). Values are masked."""
    db = ad.common.get_async_db()
    doc = await db.cloud_config.find_one({"type": "azure", "user_id": current_user.user_id})
    if not doc or not doc.get("tenant_id"):
        doc = await db.cloud_config.find_one({"type": "azure"})
    if not doc or not doc.get("tenant_id"):
        raise HTTPException(status_code=404, detail="Azure configuration not found")

    def masked(field: str) -> str:
        raw = ad.crypto.decrypt_token(doc[field])
        return mask_secret_plaintext(raw) or ""

    return AzureServicePrincipalResponse(
        tenant_id=masked("tenant_id"),
        client_id=masked("client_id"),
        client_secret=masked("client_secret"),
    )


@azure_router.delete("/v0/account/azure_config")
async def delete_azure_config(current_user: User = Depends(get_admin_user)):
    """Delete Azure configuration (admin only)."""
    db = ad.common.get_async_db()
    result = await db.cloud_config.delete_one({"type": "azure", "user_id": current_user.user_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Azure configuration not found")
    return {"message": "Azure configuration deleted successfully"}
