"""
In-memory turn state for the chat/approve loop.
Keyed by turn_id; TTL 5 minutes. Used when backend pauses on pending tool calls.
"""
from __future__ import annotations

import logging
import time
import uuid
from typing import Any

logger = logging.getLogger(__name__)

# turn_id -> { "created_at", "messages", "pending_tool_calls", "working_state", "model", ... }
_store: dict[str, dict[str, Any]] = {}
_TTL_SEC = 300


def _now() -> float:
    return time.monotonic()


def generate_turn_id() -> str:
    return str(uuid.uuid4())


def set_turn_state(turn_id: str, state: dict[str, Any]) -> None:
    state["_created_at"] = _now()
    _store[turn_id] = state


def get_turn_state(turn_id: str) -> dict[str, Any] | None:
    entry = _store.get(turn_id)
    if not entry:
        return None
    if _now() - entry["_created_at"] > _TTL_SEC:
        del _store[turn_id]
        return None
    return entry


def clear_turn_state(turn_id: str) -> None:
    _store.pop(turn_id, None)
