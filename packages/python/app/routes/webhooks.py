# webhooks.py

import logging
from datetime import datetime, UTC
from typing import Any, Optional, List, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Body, Response
from pydantic import BaseModel, Field, HttpUrl
from bson import ObjectId
from bson.errors import InvalidId

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


def _object_id_or_404(value: str, what: str = "resource") -> ObjectId:
    try:
        return ObjectId(value)
    except InvalidId:
        raise HTTPException(status_code=404, detail=f"Invalid {what} id")


def _validate_enabled_requires_url(enabled: bool, url: Optional[str]) -> None:
    if enabled and not (url and str(url).strip()):
        raise HTTPException(
            status_code=422,
            detail="An enabled webhook endpoint requires a non-empty URL",
        )


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


class WebhookTestResponse(BaseModel):
    status: str
    delivery_id: Optional[str] = None


class WebhookRetryResponse(BaseModel):
    status: str
    delivery_id: str


class WebhookEndpointBase(BaseModel):
    name: Optional[str] = Field(
        default=None,
        description="Optional display name for this webhook endpoint.",
    )
    enabled: bool = False
    url: Optional[HttpUrl] = None
    events: Optional[List[WebhookEventType]] = None
    auth_type: WebhookAuthType = "hmac"
    auth_header_name: Optional[str] = None


class WebhookEndpointResponse(WebhookEndpointBase):
    id: str
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    secret_set: bool = False
    secret_preview: Optional[str] = None
    auth_header_set: bool = False
    auth_header_preview: Optional[str] = None
    generated_secret: Optional[str] = Field(
        default=None,
        description="Plaintext secret returned only once when generated via create or update.",
    )


class WebhookEndpointCreateRequest(WebhookEndpointBase):
    # If provided as empty string, generate a new secret. If omitted, keep unset.
    secret: Optional[str] = Field(
        default=None,
        description="Initial secret (plaintext). Empty string generates a new random secret.",
    )
    auth_header_value: Optional[str] = Field(
        default=None,
        description="Header auth value (plaintext). Empty string clears.",
    )


class WebhookEndpointUpdateRequest(BaseModel):
    name: Optional[str] = None
    enabled: Optional[bool] = None
    url: Optional[HttpUrl] = None
    events: Optional[List[WebhookEventType]] = None
    auth_type: Optional[WebhookAuthType] = None
    auth_header_name: Optional[str] = None
    auth_header_value: Optional[str] = None
    secret: Optional[str] = Field(
        default=None,
        description="If provided as empty string, generate a new secret. If omitted, keep existing.",
    )


class WebhookDeliveryItem(BaseModel):
    id: str
    event_id: str
    event_type: str
    webhook_id: Optional[str] = None
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


class WebhookDeliveryDetailResponse(BaseModel):
    """Single delivery for debugging; secrets are never returned."""

    id: str
    event_id: str
    event_type: str
    organization_id: str
    webhook_id: Optional[str] = None
    document_id: Optional[str] = None
    prompt_revid: Optional[str] = None
    prompt_id: Optional[str] = None
    prompt_version: Optional[int] = None
    payload: dict[str, Any] = Field(default_factory=dict)
    target_url: Optional[str] = None
    auth_type: Optional[str] = None
    auth_header_name: Optional[str] = None
    auth_header_value: Optional[str] = Field(
        default=None,
        description="Truncated preview of header auth value when present.",
    )
    status: str
    attempts: int
    max_attempts: int
    last_http_status: Optional[int] = None
    last_error: Optional[str] = None
    last_response_text: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    next_attempt_at: Optional[datetime] = None
    delivered_at: Optional[datetime] = None
    failed_at: Optional[datetime] = None


def _endpoint_doc_to_response(doc: dict, *, generated_secret: Optional[str] = None) -> WebhookEndpointResponse:
    return WebhookEndpointResponse(
        id=str(doc["_id"]),
        name=doc.get("name"),
        enabled=bool(doc.get("enabled", False)),
        url=doc.get("url"),
        events=_normalize_webhook_events(doc.get("events")),
        auth_type=doc.get("auth_type") or ("header" if doc.get("auth_header_value") and not bool(doc.get("signature_enabled", False)) else "hmac"),
        auth_header_name=doc.get("auth_header_name"),
        created_at=doc.get("created_at"),
        updated_at=doc.get("updated_at"),
        secret_set=bool(doc.get("secret")),
        secret_preview=doc.get("secret_preview"),
        auth_header_set=bool(doc.get("auth_header_value")),
        auth_header_preview=doc.get("auth_header_preview"),
        generated_secret=generated_secret,
    )


def _delivery_row_to_detail(row: dict) -> WebhookDeliveryDetailResponse:
    auth_header_value: Optional[str] = None
    enc = row.get("auth_header_value")
    if enc:
        try:
            plain = ad.crypto.decrypt_token(enc)
        except Exception:
            plain = None
        if plain:
            auth_header_value = plain[:4] + "..."
    return WebhookDeliveryDetailResponse(
        id=str(row["_id"]),
        event_id=row.get("event_id", ""),
        event_type=row.get("event_type", ""),
        organization_id=str(row.get("organization_id", "")),
        webhook_id=row.get("webhook_id"),
        document_id=row.get("document_id"),
        prompt_revid=row.get("prompt_revid"),
        prompt_id=row.get("prompt_id"),
        prompt_version=row.get("prompt_version"),
        payload=row.get("payload") if isinstance(row.get("payload"), dict) else {},
        target_url=row.get("target_url"),
        auth_type=row.get("auth_type"),
        auth_header_name=row.get("auth_header_name"),
        auth_header_value=auth_header_value,
        status=str(row.get("status", "")),
        attempts=int(row.get("attempts", 0)),
        max_attempts=int(row.get("max_attempts", 0)),
        last_http_status=row.get("last_http_status"),
        last_error=row.get("last_error"),
        last_response_text=row.get("last_response_text"),
        created_at=row.get("created_at"),
        updated_at=row.get("updated_at"),
        next_attempt_at=row.get("next_attempt_at"),
        delivered_at=row.get("delivered_at"),
        failed_at=row.get("failed_at"),
    )


@webhooks_router.get("/v0/orgs/{organization_id}/webhooks/deliveries", response_model=ListWebhookDeliveriesResponse)
async def list_webhook_deliveries(
    organization_id: str,
    status: Optional[str] = Query(None, description="Filter by status (pending|processing|delivered|failed)"),
    event_type: Optional[str] = Query(None, description="Filter by event_type"),
    webhook_id: Optional[str] = Query(None, description="Filter by webhook endpoint id"),
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
    if webhook_id:
        query["webhook_id"] = webhook_id

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
                webhook_id=row.get("webhook_id"),
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


@webhooks_router.get(
    "/v0/orgs/{organization_id}/webhooks/deliveries/{delivery_id}",
    response_model=WebhookDeliveryDetailResponse,
)
async def get_webhook_delivery(
    organization_id: str,
    delivery_id: str,
    current_user: User = Depends(get_org_user),
):
    db = ad.common.get_async_db()
    did = _object_id_or_404(delivery_id, "delivery")
    row = await db[ad.webhooks.DELIVERIES_COLLECTION].find_one(
        {"_id": did, "organization_id": organization_id}
    )
    if not row:
        raise HTTPException(status_code=404, detail="Delivery not found")

    row.pop("secret_encrypted", None)
    return _delivery_row_to_detail(row)


@webhooks_router.post("/v0/orgs/{organization_id}/webhooks/deliveries/{delivery_id}/retry", response_model=WebhookRetryResponse)
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
    did = _object_id_or_404(delivery_id, "delivery")
    row = await db[ad.webhooks.DELIVERIES_COLLECTION].find_one(
        {"_id": did, "organization_id": organization_id}
    )
    if not row:
        raise HTTPException(status_code=404, detail="Delivery not found")

    await db[ad.webhooks.DELIVERIES_COLLECTION].update_one(
        {"_id": did, "organization_id": organization_id},
        {"$set": {"status": "pending", "next_attempt_at": now, "updated_at": now}},
    )

    analytiq_client = ad.common.get_analytiq_client()
    await ad.queue.send_msg(analytiq_client, ad.webhooks.WEBHOOK_QUEUE_NAME, msg={"delivery_id": delivery_id})
    return WebhookRetryResponse(status="enqueued", delivery_id=delivery_id)


@webhooks_router.get(
    "/v0/orgs/{organization_id}/webhooks",
    response_model=List[WebhookEndpointResponse],
)
async def list_org_webhooks(
    organization_id: str,
    current_user: User = Depends(get_org_user),
):
    db = ad.common.get_async_db()
    cursor = db[ad.webhooks.ENDPOINTS_COLLECTION].find({"organization_id": organization_id}).sort("created_at", 1)
    docs = await cursor.to_list(length=None)
    return [_endpoint_doc_to_response(doc) for doc in docs]


@webhooks_router.post(
    "/v0/orgs/{organization_id}/webhooks",
    response_model=WebhookEndpointResponse,
    status_code=201,
)
async def create_org_webhook(
    organization_id: str,
    request: WebhookEndpointCreateRequest = Body(...),
    current_user: User = Depends(get_org_admin_user),
    response: Response = None,
):
    db = ad.common.get_async_db()
    org_oid = _object_id_or_404(organization_id, "organization")
    org = await db.organizations.find_one({"_id": org_oid})
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    now = datetime.now(UTC)

    url_str = str(request.url) if request.url is not None else None
    _validate_enabled_requires_url(request.enabled, url_str)

    doc: dict = {
        "organization_id": organization_id,
        "name": request.name,
        "enabled": request.enabled,
        "url": url_str,
        "events": _normalize_webhook_events(list(request.events)) if request.events is not None else None,
        "auth_type": request.auth_type,
        "auth_header_name": (request.auth_header_name.strip() if request.auth_header_name else None),
        "signature_enabled": request.auth_type == "hmac",
        "created_at": now,
        "updated_at": now,
    }

    generated_secret: str | None = None

    if request.auth_header_value is not None:
        if request.auth_header_value == "":
            doc["auth_header_value"] = None
            doc["auth_header_preview"] = None
        else:
            val = request.auth_header_value
            doc["auth_header_value"] = ad.crypto.encrypt_token(val)
            doc["auth_header_preview"] = f"{val[:5]}..."

    if request.secret is not None:
        if request.secret == "":
            secret_plain = ad.webhooks.generate_webhook_secret()
            generated_secret = secret_plain
        else:
            secret_plain = request.secret
        doc["secret"] = ad.crypto.encrypt_token(secret_plain)
        doc["secret_preview"] = f"{secret_plain[:16]}..."

    result = await db[ad.webhooks.ENDPOINTS_COLLECTION].insert_one(doc)
    created = await db[ad.webhooks.ENDPOINTS_COLLECTION].find_one({"_id": result.inserted_id})
    if not created:
        raise HTTPException(status_code=500, detail="Failed to create webhook endpoint")

    webhook_id = str(result.inserted_id)
    if response is not None:
        response.headers["Location"] = f"/fastapi/v0/orgs/{organization_id}/webhooks/{webhook_id}"

    return _endpoint_doc_to_response(created, generated_secret=generated_secret)


@webhooks_router.get(
    "/v0/orgs/{organization_id}/webhooks/{webhook_id}",
    response_model=WebhookEndpointResponse,
)
async def get_org_webhook(
    organization_id: str,
    webhook_id: str,
    current_user: User = Depends(get_org_user),
):
    db = ad.common.get_async_db()
    wid = _object_id_or_404(webhook_id, "webhook")
    doc = await db[ad.webhooks.ENDPOINTS_COLLECTION].find_one(
        {"_id": wid, "organization_id": organization_id}
    )
    if not doc:
        raise HTTPException(status_code=404, detail="Webhook not found")
    return _endpoint_doc_to_response(doc)


@webhooks_router.put(
    "/v0/orgs/{organization_id}/webhooks/{webhook_id}",
    response_model=WebhookEndpointResponse,
)
async def update_org_webhook(
    organization_id: str,
    webhook_id: str,
    request: WebhookEndpointUpdateRequest = Body(...),
    current_user: User = Depends(get_org_admin_user),
):
    db = ad.common.get_async_db()
    wid = _object_id_or_404(webhook_id, "webhook")
    existing = await db[ad.webhooks.ENDPOINTS_COLLECTION].find_one(
        {"_id": wid, "organization_id": organization_id}
    )
    if not existing:
        raise HTTPException(status_code=404, detail="Webhook not found")

    update: dict = {}
    generated_secret: str | None = None

    # Use model_fields_set so explicit JSON null clears the field; bare None from omission is ignored.
    if "name" in request.model_fields_set:
        update["name"] = request.name
    if request.enabled is not None:
        update["enabled"] = request.enabled
    if request.url is not None:
        update["url"] = str(request.url)
    if request.events is not None:
        update["events"] = _normalize_webhook_events(list(request.events))
    if request.auth_type is not None:
        update["auth_type"] = request.auth_type
        update["signature_enabled"] = request.auth_type == "hmac"
    if request.auth_header_name is not None:
        name = request.auth_header_name.strip() if request.auth_header_name else ""
        update["auth_header_name"] = name if name else None
    if request.auth_header_value is not None:
        if request.auth_header_value == "":
            update["auth_header_value"] = None
            update["auth_header_preview"] = None
        else:
            val = request.auth_header_value
            update["auth_header_value"] = ad.crypto.encrypt_token(val)
            update["auth_header_preview"] = f"{val[:5]}..."
    if request.secret is not None:
        if request.secret == "":
            secret_plain = ad.webhooks.generate_webhook_secret()
            generated_secret = secret_plain
        else:
            secret_plain = request.secret
        update["secret"] = ad.crypto.encrypt_token(secret_plain)
        update["secret_preview"] = f"{secret_plain[:16]}..."

    update["updated_at"] = datetime.now(UTC)

    eff_enabled = bool(existing.get("enabled", False))
    eff_url = existing.get("url")
    if request.enabled is not None:
        eff_enabled = bool(request.enabled)
    if request.url is not None:
        eff_url = str(request.url) if request.url else None
    _validate_enabled_requires_url(eff_enabled, eff_url)

    if update:
        await db[ad.webhooks.ENDPOINTS_COLLECTION].update_one(
            {"_id": wid, "organization_id": organization_id},
            {"$set": update},
        )

    doc = await db[ad.webhooks.ENDPOINTS_COLLECTION].find_one(
        {"_id": wid, "organization_id": organization_id}
    )
    if not doc:
        raise HTTPException(status_code=404, detail="Webhook not found after update")
    return _endpoint_doc_to_response(doc, generated_secret=generated_secret)


@webhooks_router.delete(
    "/v0/orgs/{organization_id}/webhooks/{webhook_id}",
    status_code=204,
)
async def delete_org_webhook(
    organization_id: str,
    webhook_id: str,
    current_user: User = Depends(get_org_admin_user),
):
    db = ad.common.get_async_db()
    wid = _object_id_or_404(webhook_id, "webhook")
    res = await db[ad.webhooks.ENDPOINTS_COLLECTION].delete_one(
        {"_id": wid, "organization_id": organization_id}
    )
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Webhook not found")
    return None


@webhooks_router.post(
    "/v0/orgs/{organization_id}/webhooks/{webhook_id}/test",
    response_model=WebhookTestResponse,
)
async def test_org_webhook_endpoint(
    organization_id: str,
    webhook_id: str,
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
        webhook_id=webhook_id,
    )
    if not delivery_id:
        raise HTTPException(status_code=400, detail="Webhook is not enabled, URL is not configured, or endpoint not found")
    return WebhookTestResponse(status="enqueued", delivery_id=delivery_id)