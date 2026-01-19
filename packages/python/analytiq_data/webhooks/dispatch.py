import os
import json
import time
import uuid
import hmac
import hashlib
import logging
import secrets
import random
from datetime import datetime, UTC, timedelta
from typing import Any, Optional

import httpx
from bson import ObjectId

import analytiq_data as ad

logger = logging.getLogger(__name__)

DELIVERIES_COLLECTION = "webhook_deliveries"
WEBHOOK_QUEUE_NAME = "webhook"


def _now_utc() -> datetime:
    return datetime.now(UTC)


def _get_int_env(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except Exception:
        return default


def _get_float_env(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)))
    except Exception:
        return default


def generate_webhook_secret() -> str:
    # URL-safe, copy/paste friendly. Prefix matches token-style identifiers.
    return f"whs_{secrets.token_urlsafe(32)}"


def _json_dumps_compact(payload: dict) -> str:
    # Compact, stable JSON (no extra spaces). Do not sort keys; preserve insertion order.
    return json.dumps(payload, separators=(",", ":"), ensure_ascii=False, default=str)


def _compute_signature(secret: str, ts: int, body: str) -> str:
    msg = f"{ts}.{body}".encode("utf-8")
    mac = hmac.new(secret.encode("utf-8"), msg, hashlib.sha256).hexdigest()
    return f"sha256={mac}"


def _is_retryable_status(status_code: int) -> bool:
    if status_code in (408, 429):
        return True
    return 500 <= status_code <= 599


def _compute_backoff(attempts: int) -> timedelta:
    """
    attempts is 1-based (first attempt => 1).
    """
    base = _get_float_env("WEBHOOK_BACKOFF_BASE_SECS", 5.0)
    cap = _get_float_env("WEBHOOK_BACKOFF_CAP_SECS", 15 * 60.0)

    # Exponential backoff with jitter, capped.
    secs = min(cap, base * (2 ** max(0, attempts - 1)))
    jitter = _get_float_env("WEBHOOK_BACKOFF_JITTER_SECS", 1.0)
    secs = secs + (random.random() * jitter)  # noqa: F821
    return timedelta(seconds=secs)


async def _get_org_webhook_config(analytiq_client, organization_id: str) -> dict | None:
    db = ad.common.get_async_db(analytiq_client)
    org = await db.organizations.find_one({"_id": ObjectId(organization_id)})
    if not org:
        return None
    return org.get("webhook")


def _webhook_enabled_for_event(webhook_cfg: dict | None, event_type: str) -> bool:
    if not webhook_cfg:
        return False
    if not webhook_cfg.get("enabled"):
        return False
    if not webhook_cfg.get("url"):
        return False
    if event_type == "webhook.test":
        return True
    events = webhook_cfg.get("events")
    if not events:
        return True
    normalized_events = set()
    for ev in events:
        normalized_events.add(ev)
    return event_type in normalized_events


def _decrypt_secret_if_needed(secret_encrypted: str | None) -> str | None:
    if not secret_encrypted:
        return None
    try:
        return ad.crypto.decrypt_token(secret_encrypted)
    except Exception:
        # If it's already plaintext (e.g., local dev), accept it.
        return secret_encrypted


def _decrypt_token_if_needed(token_encrypted: str | None) -> str | None:
    if not token_encrypted:
        return None
    try:
        return ad.crypto.decrypt_token(token_encrypted)
    except Exception:
        return token_encrypted


async def _get_document_snapshot(analytiq_client, document_id: str) -> dict | None:
    doc = await ad.common.doc.get_doc(analytiq_client, document_id)
    if not doc:
        return None
    return {
        "document_id": str(doc.get("_id") or document_id),
        "document_name": doc.get("user_file_name") or doc.get("document_name") or "",
        "tag_ids": doc.get("tag_ids", []),
        "metadata": doc.get("metadata", {}),
    }


async def enqueue_event(
    analytiq_client,
    *,
    organization_id: str,
    event_type: str,
    document_id: str | None,
    prompt: dict | None = None,
    llm_output: dict | None = None,
    error: dict | None = None,
) -> str | None:
    """
    Create a webhook delivery record and enqueue it for sending.
    Returns delivery_id if enqueued, otherwise None (webhook disabled/not configured).
    """
    webhook_cfg = await _get_org_webhook_config(analytiq_client, organization_id)
    if not _webhook_enabled_for_event(webhook_cfg, event_type):
        return None

    doc_snapshot = None
    if document_id is not None:
        doc_snapshot = await _get_document_snapshot(analytiq_client, document_id)
        if not doc_snapshot:
            return None

    target_url = webhook_cfg["url"]
    secret_encrypted = webhook_cfg.get("secret")
    auth_type = webhook_cfg.get("auth_type")
    if not auth_type:
        # Backward-compatible: if signature_enabled truthy -> hmac, else header if auth header exists, else hmac
        if bool(webhook_cfg.get("signature_enabled", False)):
            auth_type = "hmac"
        elif webhook_cfg.get("auth_header_value"):
            auth_type = "header"
        else:
            auth_type = "hmac"
    auth_header_name = webhook_cfg.get("auth_header_name")
    auth_header_value = webhook_cfg.get("auth_header_value")
    auth_header_preview = webhook_cfg.get("auth_header_preview")

    event_id = str(uuid.uuid4())
    ts = int(time.time())
    payload: dict[str, Any] = {
        "event_id": event_id,
        "event_type": event_type,
        "timestamp": ts,
        "organization_id": organization_id,
    }
    if doc_snapshot is not None:
        payload["document"] = doc_snapshot
    if prompt is not None:
        payload["prompt"] = prompt
    if llm_output is not None:
        payload["llm_output"] = llm_output
    if error is not None:
        payload["error"] = error

    now = _now_utc()
    delivery_doc = {
        "event_id": event_id,
        "event_type": event_type,
        "organization_id": organization_id,
        "document_id": document_id,
        "prompt_revid": (prompt or {}).get("prompt_revid"),
        "prompt_id": (prompt or {}).get("prompt_id"),
        "prompt_version": (prompt or {}).get("prompt_version"),
        "payload": payload,
        "target_url": target_url,
        "secret_encrypted": secret_encrypted,
        "auth_type": auth_type,
        "auth_header_name": auth_header_name,
        "auth_header_value": auth_header_value,
        "status": "pending",
        "attempts": 0,
        "max_attempts": _get_int_env("WEBHOOK_MAX_ATTEMPTS", 10),
        "next_attempt_at": now,
        "created_at": now,
        "updated_at": now,
    }

    db = ad.common.get_async_db(analytiq_client)
    result = await db[DELIVERIES_COLLECTION].insert_one(delivery_doc)
    delivery_id = str(result.inserted_id)

    await ad.queue.send_msg(
        analytiq_client,
        WEBHOOK_QUEUE_NAME,
        msg={"delivery_id": delivery_id, "event_id": event_id},
    )

    logger.info(f"Webhook enqueued: {delivery_id} {event_type} org={organization_id} doc={document_id}")
    return delivery_id


async def claim_delivery_by_id(analytiq_client, delivery_id: str) -> dict | None:
    db = ad.common.get_async_db(analytiq_client)
    now = _now_utc()
    lease_secs = _get_int_env("WEBHOOK_PROCESSING_LEASE_SECS", 300)
    lease_cutoff = now - timedelta(seconds=lease_secs)
    return await db[DELIVERIES_COLLECTION].find_one_and_update(
        {
            "_id": ObjectId(delivery_id),
            "$or": [
                {"status": "pending", "next_attempt_at": {"$lte": now}},
                {"status": "processing", "last_attempt_at": {"$lte": lease_cutoff}},
            ],
        },
        {
            "$set": {"status": "processing", "last_attempt_at": now, "updated_at": now},
            "$inc": {"attempts": 1},
        },
        return_document=True,
    )


async def claim_next_due_delivery(analytiq_client) -> dict | None:
    db = ad.common.get_async_db(analytiq_client)
    now = _now_utc()
    lease_secs = _get_int_env("WEBHOOK_PROCESSING_LEASE_SECS", 300)
    lease_cutoff = now - timedelta(seconds=lease_secs)
    return await db[DELIVERIES_COLLECTION].find_one_and_update(
        {
            "$or": [
                {"status": "pending", "next_attempt_at": {"$lte": now}},
                {"status": "processing", "last_attempt_at": {"$lte": lease_cutoff}},
            ],
        },
        {
            "$set": {"status": "processing", "last_attempt_at": now, "updated_at": now},
            "$inc": {"attempts": 1},
        },
        sort=[("next_attempt_at", 1), ("created_at", 1)],
        return_document=True,
    )


async def _mark_delivery(
    analytiq_client,
    delivery_id: str,
    *,
    status: str,
    fields: dict[str, Any] | None = None,
) -> None:
    db = ad.common.get_async_db(analytiq_client)
    now = _now_utc()
    update = {"$set": {"status": status, "updated_at": now}}
    if fields:
        update["$set"].update(fields)
    await db[DELIVERIES_COLLECTION].update_one({"_id": ObjectId(delivery_id)}, update)


async def mark_delivered(analytiq_client, delivery_id: str, *, http_status: int, response_text: str | None) -> None:
    await _mark_delivery(
        analytiq_client,
        delivery_id,
        status="delivered",
        fields={
            "delivered_at": _now_utc(),
            "last_http_status": http_status,
            "last_error": None,
            "last_response_text": response_text,
        },
    )


async def mark_failed(
    analytiq_client,
    delivery_id: str,
    *,
    http_status: int | None,
    error: str,
    response_text: str | None,
) -> None:
    fields: dict[str, Any] = {
        "failed_at": _now_utc(),
        "last_http_status": http_status,
        "last_error": error,
        "last_response_text": response_text,
    }
    await _mark_delivery(analytiq_client, delivery_id, status="failed", fields=fields)


async def mark_retry(
    analytiq_client,
    delivery: dict,
    *,
    http_status: int | None,
    error: str,
    response_text: str | None,
) -> None:
    attempts = int(delivery.get("attempts") or 0)
    max_attempts = int(delivery.get("max_attempts") or 10)
    if attempts >= max_attempts:
        await mark_failed(
            analytiq_client,
            str(delivery["_id"]),
            http_status=http_status,
            error=f"max_attempts_exceeded: {error}",
            response_text=response_text,
        )
        return

    next_at = _now_utc() + _compute_backoff(attempts)
    await _mark_delivery(
        analytiq_client,
        str(delivery["_id"]),
        status="pending",
        fields={
            "next_attempt_at": next_at,
            "last_http_status": http_status,
            "last_error": error,
            "last_response_text": response_text,
        },
    )


async def send_delivery(analytiq_client, delivery: dict) -> None:
    delivery_id = str(delivery["_id"])
    payload = delivery.get("payload") or {}
    body = _json_dumps_compact(payload)

    ts = int(time.time())
    auth_type = delivery.get("auth_type") or ("hmac" if bool(delivery.get("signature_enabled", False)) else "header")
    secret = _decrypt_secret_if_needed(delivery.get("secret_encrypted")) or ""
    signature = _compute_signature(secret, ts, body) if auth_type == "hmac" and secret else None

    auth_header_name = delivery.get("auth_header_name")
    auth_header_value = _decrypt_token_if_needed(delivery.get("auth_header_value"))

    headers = {
        "Content-Type": "application/json",
        "X-DocRouter-Event": str(delivery.get("event_type") or ""),
        "X-DocRouter-Event-Id": str(delivery.get("event_id") or ""),
        "X-DocRouter-Timestamp": str(ts),
    }
    if signature:
        headers["X-DocRouter-Signature"] = signature
    if auth_type == "header" and auth_header_name and auth_header_value:
        headers[str(auth_header_name)] = str(auth_header_value)

    timeout_s = _get_float_env("WEBHOOK_TIMEOUT_SECS", 10.0)
    response_text: str | None = None
    try:
        async with httpx.AsyncClient(timeout=timeout_s) as client:
            resp = await client.post(delivery["target_url"], content=body.encode("utf-8"), headers=headers)
        if resp.content:
            response_text = resp.text[:2048]

        if 200 <= resp.status_code <= 299:
            await mark_delivered(analytiq_client, delivery_id, http_status=resp.status_code, response_text=response_text)
            return

        if _is_retryable_status(resp.status_code):
            await mark_retry(
                analytiq_client,
                delivery,
                http_status=resp.status_code,
                error=f"http_{resp.status_code}",
                response_text=response_text,
            )
            return

        await mark_failed(
            analytiq_client,
            delivery_id,
            http_status=resp.status_code,
            error=f"http_{resp.status_code}",
            response_text=response_text,
        )
    except Exception as e:
        await mark_retry(
            analytiq_client,
            delivery,
            http_status=None,
            error=f"exception: {type(e).__name__}: {str(e)}",
            response_text=response_text,
        )

