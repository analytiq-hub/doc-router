# gcp.py — Vertex / GCP service account in cloud_config (type gcp)

import json
import logging
from datetime import datetime, UTC

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

import analytiq_data as ad
from app.auth import get_admin_user
from app.models import User
from app.secret_mask import mask_secret_plaintext

logger = logging.getLogger(__name__)

gcp_router = APIRouter(tags=["account/gcp"])


class GCPConfigRequest(BaseModel):
    service_account_json: str


class GCPConfigResponse(BaseModel):
    """Masked service account JSON (never full key material)."""

    service_account_json: str


@gcp_router.post("/v0/account/gcp_config")
async def create_gcp_config(
    config: GCPConfigRequest,
    current_user: User = Depends(get_admin_user),
):
    """Create or update GCP (Vertex) service account JSON (admin only)."""
    raw = (config.service_account_json or "").strip()
    if not raw:
        raise HTTPException(status_code=400, detail="Service account JSON is required")

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    if not isinstance(parsed, dict):
        raise HTTPException(status_code=400, detail="Service account JSON must be a JSON object")
    if parsed.get("type") != "service_account":
        raise HTTPException(
            status_code=400,
            detail='Expected a Google service account key (type must be "service_account")',
        )
    if not parsed.get("project_id") or not parsed.get("private_key"):
        raise HTTPException(status_code=400, detail="Missing project_id or private_key in service account JSON")

    db = ad.common.get_async_db()
    encrypted = ad.crypto.encrypt_token(raw)
    now = datetime.now(UTC)
    update_data = {
        "type": "gcp",
        "user_id": current_user.user_id,
        "service_account_json": encrypted,
        "created_at": now,
    }

    await db.cloud_config.update_one(
        {"type": "gcp", "user_id": current_user.user_id},
        {"$set": update_data},
        upsert=True,
    )
    return {"message": "GCP configuration saved successfully"}


@gcp_router.get(
    "/v0/account/gcp_config",
    response_model=GCPConfigResponse,
    response_model_exclude_none=True,
)
async def get_gcp_config(current_user: User = Depends(get_admin_user)):
    """Get GCP configuration status (admin only). Secret JSON is masked; full key is never returned."""
    db = ad.common.get_async_db()
    doc = await db.cloud_config.find_one({"type": "gcp", "user_id": current_user.user_id})
    if not doc or not doc.get("service_account_json"):
        doc = await db.cloud_config.find_one({"type": "gcp"})
    if not doc or not doc.get("service_account_json"):
        raise HTTPException(status_code=404, detail="GCP configuration not found")

    raw_json = ad.crypto.decrypt_token(doc["service_account_json"])
    masked = mask_secret_plaintext(raw_json) or ""
    return GCPConfigResponse(service_account_json=masked)


@gcp_router.delete("/v0/account/gcp_config")
async def delete_gcp_config(current_user: User = Depends(get_admin_user)):
    """Delete GCP configuration (admin only)."""
    db = ad.common.get_async_db()
    result = await db.cloud_config.delete_one({"type": "gcp", "user_id": current_user.user_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="GCP configuration not found")
    return {"message": "GCP configuration deleted successfully"}
