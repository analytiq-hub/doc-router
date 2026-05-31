"""
Turn state for the chat/approve loop, stored in MongoDB.
Keyed by turn_id; TTL 5 minutes. Shared across all uvicorn worker processes.
"""
from __future__ import annotations

import logging
import time
import uuid
from typing import Any

import analytiq_data as ad

logger = logging.getLogger(__name__)

_TTL_SEC = 300
_COLLECTION = "agent_turn_states"


def generate_turn_id() -> str:
    return str(uuid.uuid4())


async def set_turn_state(turn_id: str, state: dict[str, Any]) -> None:
    state = dict(state)
    state["_turn_id"] = turn_id
    state["_created_at"] = time.time()
    db = ad.common.get_async_db()
    await db[_COLLECTION].replace_one({"_turn_id": turn_id}, state, upsert=True)


async def get_turn_state(turn_id: str) -> dict[str, Any] | None:
    db = ad.common.get_async_db()
    entry = await db[_COLLECTION].find_one({"_turn_id": turn_id})
    if not entry:
        return None
    if time.time() - entry.get("_created_at", 0) > _TTL_SEC:
        await db[_COLLECTION].delete_one({"_turn_id": turn_id})
        return None
    return entry


async def clear_turn_state(turn_id: str) -> None:
    db = ad.common.get_async_db()
    await db[_COLLECTION].delete_one({"_turn_id": turn_id})
