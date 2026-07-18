"""Mongo singleton store for the deployment license."""

from __future__ import annotations

import logging
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import analytiq_data as ad

logger = logging.getLogger(__name__)

LICENSE_DOC_ID = "deployment"
LICENSE_COLLECTION = "license"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _db():
    return ad.common.get_async_db()


async def get_license_document() -> Optional[dict[str, Any]]:
    return await _db()[LICENSE_COLLECTION].find_one({"_id": LICENSE_DOC_ID})


async def ensure_installation_id() -> str:
    """Return stable installation_id, creating the singleton if needed."""
    db = _db()
    existing = await db[LICENSE_COLLECTION].find_one(
        {"_id": LICENSE_DOC_ID},
        {"installation_id": 1},
    )
    if existing and existing.get("installation_id"):
        return existing["installation_id"]

    env_id = (os.getenv("INSTALLATION_ID") or "").strip()
    installation_id = env_id if env_id else f"inst_{uuid.uuid4().hex}"

    await db[LICENSE_COLLECTION].update_one(
        {"_id": LICENSE_DOC_ID},
        {
            "$setOnInsert": {
                "_id": LICENSE_DOC_ID,
                "installation_id": installation_id,
                "created_at": _utcnow(),
            }
        },
        upsert=True,
    )

    doc = await db[LICENSE_COLLECTION].find_one(
        {"_id": LICENSE_DOC_ID},
        {"installation_id": 1},
    )
    return doc["installation_id"]


async def update_license_state(
    *,
    state: str,
    state_code: Optional[str] = None,
    state_message: Optional[str] = None,
) -> None:
    await ensure_installation_id()
    await _db()[LICENSE_COLLECTION].update_one(
        {"_id": LICENSE_DOC_ID},
        {
            "$set": {
                "state": state,
                "state_code": state_code,
                "state_message": state_message,
                "checked_at": _utcnow(),
            }
        },
        upsert=True,
    )


async def put_license_key_raw(
    license_key: str,
    *,
    state: str,
    state_code: Optional[str] = None,
    state_message: Optional[str] = None,
    updated_by_user_id: Optional[str] = None,
) -> dict[str, Any]:
    installation_id = await ensure_installation_id()
    now = _utcnow()
    await _db()[LICENSE_COLLECTION].update_one(
        {"_id": LICENSE_DOC_ID},
        {
            "$set": {
                "license_key": license_key.strip(),
                "installation_id": installation_id,
                "state": state,
                "state_code": state_code,
                "state_message": state_message,
                "checked_at": now,
                "updated_at": now,
                "updated_by_user_id": updated_by_user_id,
            },
            "$setOnInsert": {
                "_id": LICENSE_DOC_ID,
                "created_at": now,
            },
        },
        upsert=True,
    )
    doc = await get_license_document()
    assert doc is not None
    return doc


async def bootstrap_license_if_needed() -> Optional[str]:
    """If Mongo has no key, bootstrap from LICENSE_KEY or LICENSE_FILE.

    Returns the raw key if one is present after bootstrap, else None.
    Does not verify here — caller should refresh state after.
    """
    await ensure_installation_id()
    doc = await get_license_document()
    if doc and doc.get("license_key"):
        return doc["license_key"]

    env_key = (os.getenv("LICENSE_KEY") or "").strip()
    if env_key:
        await put_license_key_raw(
            env_key,
            state="disabled",
            state_code="LICENSE_PENDING",
            state_message="Bootstrapped from LICENSE_KEY; pending verify",
        )
        logger.info("Bootstrapped license_key from LICENSE_KEY env")
        return env_key

    file_path = (os.getenv("LICENSE_FILE") or "").strip()
    if file_path:
        path = Path(file_path)
        if path.is_file():
            key = path.read_text(encoding="utf-8").strip()
            if key:
                await put_license_key_raw(
                    key,
                    state="disabled",
                    state_code="LICENSE_PENDING",
                    state_message="Bootstrapped from LICENSE_FILE; pending verify",
                )
                logger.info(f"Bootstrapped license_key from LICENSE_FILE={file_path}")
                return key
        else:
            logger.warning(f"LICENSE_FILE set but not found: {file_path}")

    return None
