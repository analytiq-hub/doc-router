"""Deployment-wide operational settings (singleton ``system_settings`` document)."""

from __future__ import annotations

import logging
import os
from datetime import UTC, datetime
from typing import Any

import analytiq_data as ad
from analytiq_data.system.worker_counts import (
    QUEUE_WORKER_FIELDS,
    WorkerCounts,
    clamp_worker_count,
    default_worker_counts,
)

logger = logging.getLogger(__name__)

SYSTEM_SETTINGS_ID = "deployment"
TEXTRACT_MAX_CONCURRENT_DEFAULT = 32
TEXTRACT_MAX_CONCURRENT_MIN = 0
TEXTRACT_MAX_CONCURRENT_MAX = 1024
TEXTRACT_MAX_CONCURRENT_REFRESH_EVERY = 25

_cached_textract_max_concurrent: int | None = None
_textract_requests_since_refresh = 0
_cached_worker_counts: WorkerCounts | None = None
_worker_counts_requests_since_refresh = 0
WORKER_COUNTS_REFRESH_EVERY = 25


def _read_env_textract_max_concurrent() -> int | None:
    raw = os.getenv("TEXTRACT_MAX_CONCURRENT")
    if raw is None or not str(raw).strip():
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def default_textract_max_concurrent() -> int:
    """Bootstrap value when no ``system_settings`` document exists."""
    env_value = _read_env_textract_max_concurrent()
    if env_value is not None:
        return clamp_textract_max_concurrent(env_value)
    return TEXTRACT_MAX_CONCURRENT_DEFAULT


def clamp_textract_max_concurrent(value: int) -> int:
    return max(
        TEXTRACT_MAX_CONCURRENT_MIN,
        min(TEXTRACT_MAX_CONCURRENT_MAX, int(value)),
    )


def default_system_settings() -> dict[str, Any]:
    counts = default_worker_counts()
    return {
        "_id": SYSTEM_SETTINGS_ID,
        "textract_max_concurrent": default_textract_max_concurrent(),
        **counts.as_dict(),
        "created_at": None,
        "updated_at": None,
    }


async def _load_settings_document() -> dict[str, Any]:
    db = ad.common.get_async_db()
    doc = await db.system_settings.find_one({"_id": SYSTEM_SETTINGS_ID})
    if doc is None:
        return default_system_settings()
    return doc


def _worker_counts_from_doc(doc: dict[str, Any]) -> WorkerCounts:
    return WorkerCounts.from_dict(doc)


async def load_textract_max_concurrent_from_db() -> int:
    doc = await _load_settings_document()
    if doc.get("textract_max_concurrent") is not None:
        try:
            return clamp_textract_max_concurrent(int(doc["textract_max_concurrent"]))
        except (TypeError, ValueError):
            logger.warning(
                f"Invalid system_settings.textract_max_concurrent={doc.get('textract_max_concurrent')!r}; "
                f"using default"
            )
    return default_textract_max_concurrent()


async def load_worker_counts_from_db() -> WorkerCounts:
    doc = await _load_settings_document()
    return _worker_counts_from_doc(doc)


async def get_textract_max_concurrent() -> int:
    """Return cached Textract concurrency limit, refreshing from Mongo every 25 calls."""
    global _cached_textract_max_concurrent, _textract_requests_since_refresh

    if (
        _cached_textract_max_concurrent is None
        or _textract_requests_since_refresh >= TEXTRACT_MAX_CONCURRENT_REFRESH_EVERY
    ):
        _textract_requests_since_refresh = 0
        try:
            _cached_textract_max_concurrent = await load_textract_max_concurrent_from_db()
        except Exception as e:
            logger.warning(f"Failed to load textract_max_concurrent from system_settings: {e}")
            if _cached_textract_max_concurrent is None:
                _cached_textract_max_concurrent = default_textract_max_concurrent()
    else:
        _textract_requests_since_refresh += 1

    return _cached_textract_max_concurrent


async def get_worker_counts() -> WorkerCounts:
    """Return cached per-queue worker counts, refreshing from Mongo every 25 calls."""
    global _cached_worker_counts, _worker_counts_requests_since_refresh

    if (
        _cached_worker_counts is None
        or _worker_counts_requests_since_refresh >= WORKER_COUNTS_REFRESH_EVERY
    ):
        _worker_counts_requests_since_refresh = 0
        try:
            _cached_worker_counts = await load_worker_counts_from_db()
        except Exception as e:
            logger.warning(f"Failed to load worker counts from system_settings: {e}")
            if _cached_worker_counts is None:
                _cached_worker_counts = default_worker_counts()
    else:
        _worker_counts_requests_since_refresh += 1

    return _cached_worker_counts


def invalidate_textract_max_concurrent_cache() -> None:
    global _textract_requests_since_refresh
    _textract_requests_since_refresh = TEXTRACT_MAX_CONCURRENT_REFRESH_EVERY


def invalidate_worker_counts_cache() -> None:
    global _worker_counts_requests_since_refresh
    _worker_counts_requests_since_refresh = WORKER_COUNTS_REFRESH_EVERY


def invalidate_system_settings_cache() -> None:
    invalidate_textract_max_concurrent_cache()
    invalidate_worker_counts_cache()


async def get_system_settings_document() -> dict[str, Any]:
    doc = await _load_settings_document()
    counts = _worker_counts_from_doc(doc)
    return {
        "_id": SYSTEM_SETTINGS_ID,
        "textract_max_concurrent": clamp_textract_max_concurrent(
            int(doc.get("textract_max_concurrent", default_textract_max_concurrent()))
        ),
        **counts.as_dict(),
        "created_at": doc.get("created_at"),
        "updated_at": doc.get("updated_at"),
    }


async def update_system_settings(
    *,
    textract_max_concurrent: int | None = None,
    n_ocr_workers: int | None = None,
    n_llm_workers: int | None = None,
    n_kb_index_workers: int | None = None,
    n_webhook_workers: int | None = None,
    n_flow_run_workers: int | None = None,
) -> dict[str, Any]:
    current = await get_system_settings_document()
    update: dict[str, Any] = {"updated_at": datetime.now(UTC)}

    if textract_max_concurrent is not None:
        update["textract_max_concurrent"] = clamp_textract_max_concurrent(textract_max_concurrent)
    if n_ocr_workers is not None:
        update["n_ocr_workers"] = clamp_worker_count(n_ocr_workers)
    if n_llm_workers is not None:
        update["n_llm_workers"] = clamp_worker_count(n_llm_workers)
    if n_kb_index_workers is not None:
        update["n_kb_index_workers"] = clamp_worker_count(n_kb_index_workers)
    if n_webhook_workers is not None:
        update["n_webhook_workers"] = clamp_worker_count(n_webhook_workers)
    if n_flow_run_workers is not None:
        update["n_flow_run_workers"] = clamp_worker_count(n_flow_run_workers)

    if len(update) == 1:
        return current

    db = ad.common.get_async_db()
    existing = await db.system_settings.find_one({"_id": SYSTEM_SETTINGS_ID})
    if existing is None:
        seeded = default_system_settings()
        seeded.update(update)
        seeded["created_at"] = update["updated_at"]
        await db.system_settings.update_one(
            {"_id": SYSTEM_SETTINGS_ID},
            {"$set": seeded},
            upsert=True,
        )
    else:
        if existing.get("created_at") is None:
            update["created_at"] = update["updated_at"]
        await db.system_settings.update_one(
            {"_id": SYSTEM_SETTINGS_ID},
            {"$set": update},
            upsert=True,
        )

    invalidate_system_settings_cache()
    return await get_system_settings_document()


async def seed_system_settings_if_missing() -> bool:
    """Insert default deployment settings when the singleton document does not exist."""
    db = ad.common.get_async_db()
    if await db.system_settings.find_one({"_id": SYSTEM_SETTINGS_ID}) is not None:
        return False
    # Any field triggers insert; missing fields come from default_system_settings().
    await update_system_settings(
        textract_max_concurrent=default_textract_max_concurrent(),
    )
    return True
