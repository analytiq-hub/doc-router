# webhooks.py

import logging
from datetime import datetime, UTC
from typing import Optional, List, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Body
from pydantic import BaseModel, Field, HttpUrl
from bson import ObjectId

import analytiq_data as ad
from app.auth import get_org_admin_user, get_org_user
from app.models import User

logger = logging.getLogger(__name__)

webhooks_router = APIRouter(tags=["webhooks"])


WebhookEventType = Literal[
    "document.uploaded",
    "document.error",
    "llm.completed",
    "llm.error",
    "webhook.test",
]

WebhookAuthType = Literal["hmac", "header"]

ALLOWED_WEBHOOK_EVENTS = {
    "document.uploaded",
    "document.error",
    "llm.completed",
    "llm.error",
    "webhook.test",
}


def _normalize_webhook_events(events: Optional[List[str]]) -> Optional[List[str]]:
    if not events:
        return events
    normalized: list[str] = []
    for ev in events:
        if ev not in ALLOWED_WEBHOOK_EVENTS:
            continue
        if ev not in normalized:
            normalized.append(ev)
    return normalized


class WebhookConfig(BaseModel):
    enabled: bool = False
    url: Optional[HttpUrl] = None
    events: Optional[List[WebhookEventType]] = None
    # Auth method selection.
    auth_type: WebhookAuthType = "hmac"
    # Optional header auth. If unset, no extra auth header is sent.
    auth_header_name: Optional[str] = None


class WebhookConfigResponse(WebhookConfig):
    # Do not return the secret; just tell UI whether it's set
    secret_set: bool = False
    secret_preview: Optional[str] = None
    # Only returned when a new secret is generated (regeneration). Display once.
    generated_secret: Optional[str] = None
    auth_header_set: bool = False
    auth_header_preview: Optional[str] = None


class WebhookConfigUpdateRequest(BaseModel):
    enabled: Optional[bool] = None
    url: Optional[HttpUrl] = None
    events: Optional[List[WebhookEventType]] = None
    auth_type: Optional[WebhookAuthType] = Field(
        default=None,
        description="Authentication method: 'hmac' (signature) or 'header' (static header).",
    )
    auth_header_name: Optional[str] = Field(
        default=None,
        description="Header name to send for header auth (e.g., 'Authorization' or 'X-Api-Key').",
    )
    auth_header_value: Optional[str] = Field(
        default=None,
        description="Header auth value (plaintext). Empty string clears.",
    )
    # If provided as empty string, regenerate. If omitted, keep existing.
    secret: Optional[str] = Field(default=None, description="Webhook secret (plaintext). Empty string regenerates.")


class WebhookTestResponse(BaseModel):
    status: str
    delivery_id: Optional[str] = None


class WebhookRetryResponse(BaseModel):
    status: str
    delivery_id: str


class WebhookDeliveryItem(BaseModel):
    id: str
    event_id: str
    event_type: str
    status: str
    attempts: int
    max_attempts: int
    document_id: Optional[str] = None
    prompt_revid: Optional[str] = None
    prompt_id: Optional[str] = None
    prompt_version: Optional[int] = None
    last_http_status: Optional[int] = None
    last_error: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    next_attempt_at: Optional[datetime] = None


class ListWebhookDeliveriesResponse(BaseModel):
    deliveries: List[WebhookDeliveryItem]
    total_count: int
    skip: int


@webhooks_router.get("/v0/orgs/{organization_id}/webhook", response_model=WebhookConfigResponse)
async def get_org_webhook_config(
    organization_id: str,
    current_user: User = Depends(get_org_user),
):
    db = ad.common.get_async_db()
    org = await db.organizations.find_one({"_id": ObjectId(organization_id)})
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    cfg = org.get("webhook") or {}
    # Backward-compatible derivation if auth_type not yet stored:
    # - if header auth value exists and signature_enabled is falsy -> header
    # - else -> hmac
    derived_auth_type = cfg.get("auth_type")
    if not derived_auth_type:
        if cfg.get("auth_header_value") and not bool(cfg.get("signature_enabled", False)):
            derived_auth_type = "header"
        else:
            derived_auth_type = "hmac"

    return WebhookConfigResponse(
        enabled=bool(cfg.get("enabled", False)),
        url=cfg.get("url"),
        events=_normalize_webhook_events(cfg.get("events")),
        auth_type=derived_auth_type,
        auth_header_name=cfg.get("auth_header_name"),
        secret_set=bool(cfg.get("secret")),
        secret_preview=cfg.get("secret_preview"),
        auth_header_set=bool(cfg.get("auth_header_value")),
        auth_header_preview=cfg.get("auth_header_preview"),
    )


@webhooks_router.put("/v0/orgs/{organization_id}/webhook", response_model=WebhookConfigResponse)
async def update_org_webhook_config(
    organization_id: str,
    request: WebhookConfigUpdateRequest = Body(...),
    current_user: User = Depends(get_org_admin_user),
):
    db = ad.common.get_async_db()
    org = await db.organizations.find_one({"_id": ObjectId(organization_id)})
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    existing = org.get("webhook") or {}
    update: dict = {}
    generated_secret: str | None = None

    if request.enabled is not None:
        update["webhook.enabled"] = request.enabled
    if request.url is not None:
        update["webhook.url"] = str(request.url)
    if request.events is not None:
        update["webhook.events"] = _normalize_webhook_events(list(request.events))
    if request.auth_type is not None:
        update["webhook.auth_type"] = request.auth_type
        # Keep legacy field in sync for older workers/records.
        update["webhook.signature_enabled"] = request.auth_type == "hmac"

    if request.auth_header_name is not None:
        name = request.auth_header_name.strip() if request.auth_header_name else ""
        update["webhook.auth_header_name"] = name if name else None

    if request.auth_header_value is not None:
        if request.auth_header_value == "":
            update["webhook.auth_header_value"] = None
            update["webhook.auth_header_preview"] = None
        else:
            val = request.auth_header_value
            update["webhook.auth_header_value"] = ad.crypto.encrypt_token(val)
            update["webhook.auth_header_preview"] = f"{val[:5]}..."

    if request.secret is not None:
        if request.secret == "":
            secret_plain = ad.webhooks.generate_webhook_secret()
            generated_secret = secret_plain
        else:
            # User-provided secret: store as-is (no forced prefix).
            secret_plain = request.secret
        update["webhook.secret"] = ad.crypto.encrypt_token(secret_plain)
        update["webhook.secret_preview"] = f"{secret_plain[:16]}..."

    update["webhook.updated_at"] = datetime.now(UTC)
    if "created_at" not in existing:
        update["webhook.created_at"] = datetime.now(UTC)

    if update:
        await db.organizations.update_one({"_id": ObjectId(organization_id)}, {"$set": update})

    # Re-read and return
    org2 = await db.organizations.find_one({"_id": ObjectId(organization_id)})
    cfg = org2.get("webhook") or {}
    return WebhookConfigResponse(
        enabled=bool(cfg.get("enabled", False)),
        url=cfg.get("url"),
        events=_normalize_webhook_events(cfg.get("events")),
        auth_type=cfg.get("auth_type") or ("header" if cfg.get("auth_header_value") and not bool(cfg.get("signature_enabled", False)) else "hmac"),
        auth_header_name=cfg.get("auth_header_name"),
        secret_set=bool(cfg.get("secret")),
        secret_preview=cfg.get("secret_preview"),
        generated_secret=generated_secret,
        auth_header_set=bool(cfg.get("auth_header_value")),
        auth_header_preview=cfg.get("auth_header_preview"),
    )


@webhooks_router.post("/v0/orgs/{organization_id}/webhook/test", response_model=WebhookTestResponse)
async def test_org_webhook(
    organization_id: str,
    current_user: User = Depends(get_org_admin_user),
):
    analytiq_client = ad.common.get_analytiq_client()
    delivery_id = await ad.webhooks.enqueue_event(
        analytiq_client,
        organization_id=organization_id,
        event_type="webhook.test",
        document_id=None,
        error=None,
        llm_output=None,
        prompt=None,
    )
    if not delivery_id:
        raise HTTPException(status_code=400, detail="Webhook is not enabled or URL is not configured")
    return WebhookTestResponse(status="enqueued", delivery_id=delivery_id)


@webhooks_router.get("/v0/orgs/{organization_id}/webhook/deliveries", response_model=ListWebhookDeliveriesResponse)
async def list_webhook_deliveries(
    organization_id: str,
    status: Optional[str] = Query(None, description="Filter by status (pending|processing|delivered|failed)"),
    event_type: Optional[str] = Query(None, description="Filter by event_type"),
    skip: int = Query(0, ge=0),
    limit: int = Query(25, ge=1, le=100),
    current_user: User = Depends(get_org_user),
):
    db = ad.common.get_async_db()
    query: dict = {"organization_id": organization_id}
    if status:
        query["status"] = status
    if event_type:
        query["event_type"] = event_type

    total = await db[ad.webhooks.DELIVERIES_COLLECTION].count_documents(query)
    cursor = (
        db[ad.webhooks.DELIVERIES_COLLECTION]
        .find(query)
        .sort("created_at", -1)
        .skip(skip)
        .limit(limit)
    )
    rows = await cursor.to_list(length=limit)

    deliveries = []
    for row in rows:
        deliveries.append(
            WebhookDeliveryItem(
                id=str(row["_id"]),
                event_id=row.get("event_id", ""),
                event_type=row.get("event_type", ""),
                status=row.get("status", ""),
                attempts=int(row.get("attempts", 0)),
                max_attempts=int(row.get("max_attempts", 0)),
                document_id=row.get("document_id"),
                prompt_revid=row.get("prompt_revid"),
                prompt_id=row.get("prompt_id"),
                prompt_version=row.get("prompt_version"),
                last_http_status=row.get("last_http_status"),
                last_error=row.get("last_error"),
                created_at=row.get("created_at"),
                updated_at=row.get("updated_at"),
                next_attempt_at=row.get("next_attempt_at"),
            )
        )

    return ListWebhookDeliveriesResponse(deliveries=deliveries, total_count=total, skip=skip)


@webhooks_router.get("/v0/orgs/{organization_id}/webhook/deliveries/{delivery_id}")
async def get_webhook_delivery(
    organization_id: str,
    delivery_id: str,
    current_user: User = Depends(get_org_user),
):
    db = ad.common.get_async_db()
    row = await db[ad.webhooks.DELIVERIES_COLLECTION].find_one(
        {"_id": ObjectId(delivery_id), "organization_id": organization_id}
    )
    if not row:
        raise HTTPException(status_code=404, detail="Delivery not found")

    # Return full payload for debugging; never return secret.
    row["id"] = str(row.pop("_id"))
    row.pop("secret_encrypted", None)
    # Decrypt the auth header value if present
    auth_header_value = ad.crypto.decrypt_token(row.get("auth_header_value"))
    if auth_header_value:
        # Truncate the auth header value to 4 characters
        row["auth_header_value"] = auth_header_value[:4] + "..."
    else:
        row["auth_header_value"] = None
   
    return row


@webhooks_router.post("/v0/orgs/{organization_id}/webhook/deliveries/{delivery_id}/retry", response_model=WebhookRetryResponse)
async def retry_webhook_delivery(
    organization_id: str,
    delivery_id: str,
    current_user: User = Depends(get_org_admin_user),
):
    """
    Manually retry a delivery by setting it back to pending and enqueueing a webhook queue message.
    """
    db = ad.common.get_async_db()
    now = datetime.now(UTC)
    row = await db[ad.webhooks.DELIVERIES_COLLECTION].find_one(
        {"_id": ObjectId(delivery_id), "organization_id": organization_id}
    )
    if not row:
        raise HTTPException(status_code=404, detail="Delivery not found")

    await db[ad.webhooks.DELIVERIES_COLLECTION].update_one(
        {"_id": ObjectId(delivery_id), "organization_id": organization_id},
        {"$set": {"status": "pending", "next_attempt_at": now, "updated_at": now}},
    )

    analytiq_client = ad.common.get_analytiq_client()
    await ad.queue.send_msg(analytiq_client, ad.webhooks.WEBHOOK_QUEUE_NAME, msg={"delivery_id": delivery_id})
    return WebhookRetryResponse(status="enqueued", delivery_id=delivery_id)

