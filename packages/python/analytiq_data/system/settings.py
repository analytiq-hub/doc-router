"""Deployment-wide operational settings (singleton ``system_settings`` document)."""

from __future__ import annotations

import logging
import os
from datetime import UTC, datetime
from typing import Any

import analytiq_data as ad

logger = logging.getLogger(__name__)

SYSTEM_SETTINGS_ID = "deployment"
TEXTRACT_MAX_CONCURRENT_DEFAULT = 32
TEXTRACT_MAX_CONCURRENT_MIN = 0
TEXTRACT_MAX_CONCURRENT_MAX = 1024
TEXTRACT_MAX_CONCURRENT_REFRESH_EVERY = 25

_cached_textract_max_concurrent: int | None = None
_requests_since_refresh = 0


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


async def load_textract_max_concurrent_from_db() -> int:
    db = ad.common.get_async_db()
    doc = await db.system_settings.find_one({"_id": SYSTEM_SETTINGS_ID})
    if doc is not None and doc.get("textract_max_concurrent") is not None:
        try:
            return clamp_textract_max_concurrent(int(doc["textract_max_concurrent"]))
        except (TypeError, ValueError):
            logger.warning(
                f"Invalid system_settings.textract_max_concurrent={doc.get('textract_max_concurrent')!r}; "
                f"using default"
            )
    return default_textract_max_concurrent()


async def get_textract_max_concurrent() -> int:
    """Return cached Textract concurrency limit, refreshing from Mongo every 25 calls."""
    global _cached_textract_max_concurrent, _requests_since_refresh

    if (
        _cached_textract_max_concurrent is None
        or _requests_since_refresh >= TEXTRACT_MAX_CONCURRENT_REFRESH_EVERY
    ):
        _requests_since_refresh = 0
        try:
            _cached_textract_max_concurrent = await load_textract_max_concurrent_from_db()
        except Exception as e:
            logger.warning(f"Failed to load textract_max_concurrent from system_settings: {e}")
            if _cached_textract_max_concurrent is None:
                _cached_textract_max_concurrent = default_textract_max_concurrent()
    else:
        _requests_since_refresh += 1

    return _cached_textract_max_concurrent


def invalidate_textract_max_concurrent_cache() -> None:
    """Force the next gate acquisition to reload from Mongo."""
    global _requests_since_refresh
    _requests_since_refresh = TEXTRACT_MAX_CONCURRENT_REFRESH_EVERY


async def get_system_settings_document() -> dict[str, Any]:
    db = ad.common.get_async_db()
    doc = await db.system_settings.find_one({"_id": SYSTEM_SETTINGS_ID})
    if doc is None:
        now = datetime.now(UTC)
        return {
            "_id": SYSTEM_SETTINGS_ID,
            "textract_max_concurrent": default_textract_max_concurrent(),
            "created_at": None,
            "updated_at": None,
        }
    return doc


async def update_system_settings(*, textract_max_concurrent: int) -> dict[str, Any]:
    value = clamp_textract_max_concurrent(textract_max_concurrent)
    now = datetime.now(UTC)
    db = ad.common.get_async_db()
    existing = await db.system_settings.find_one({"_id": SYSTEM_SETTINGS_ID})
    update: dict[str, Any] = {
        "textract_max_concurrent": value,
        "updated_at": now,
    }
    if existing is None:
        update["created_at"] = now
    await db.system_settings.update_one(
        {"_id": SYSTEM_SETTINGS_ID},
        {"$set": update},
        upsert=True,
    )
    invalidate_textract_max_concurrent_cache()
    doc = await db.system_settings.find_one({"_id": SYSTEM_SETTINGS_ID})
    return doc or {**update, "_id": SYSTEM_SETTINGS_ID}
