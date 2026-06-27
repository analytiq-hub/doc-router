"""NDJSON chunk emitter for chat streaming."""

from __future__ import annotations

import json
from typing import Any, Awaitable, Callable


async def emit_stream_event(
    sink: Callable[[dict[str, Any]], Awaitable[None]] | None,
    event: dict[str, Any],
) -> None:
    if sink is None:
        return
    await sink(event)


def ndjson_line(event: dict[str, Any]) -> bytes:
    return (json.dumps(event, ensure_ascii=False) + "\n").encode("utf-8")
