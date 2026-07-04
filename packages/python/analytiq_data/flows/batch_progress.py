from __future__ import annotations

"""Partial batch-node progress: persist completed items at checkpoints and on stop."""

import time
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Any, TypeVar

from .engine import persist_run_data
from .node_settings import node_uses_batch_partial_persist

T = TypeVar("T")

BATCH_CHECKPOINT_MIN_INTERVAL_SECS = 1.0


def completed_items_from_results(results: list[Any | None]) -> list[Any]:
    """Return successfully finished items in input order (skip ``None`` placeholders)."""

    return [item for item in results if item is not None]


async def persist_batch_node_partial(
    context: Any,
    node_id: str,
    *,
    items_total: int,
    results: list[Any | None],
    status: str = "running",
) -> None:
    """
    Write partial batch output into ``context.run_data[node_id]`` and persist to Mongo.

    Includes the full list of completed items in ``data.main[0]`` (never counters-only).
    """

    completed = completed_items_from_results(results)
    existing = context.run_data.get(node_id)
    existing_dict = existing if isinstance(existing, dict) else {}
    start_time = existing_dict.get("start_time") or datetime.now(UTC).isoformat()

    context.run_data[node_id] = {
        "status": status,
        "start_time": start_time,
        "execution_index": context.execution_index,
        "items_total": items_total,
        "items_completed": len(completed),
        "data": {"main": [completed]},
        "error": existing_dict.get("error"),
        "source": existing_dict.get("source"),
        "logs": existing_dict.get("logs"),
        "trace": existing_dict.get("trace"),
    }
    await persist_run_data(
        context,
        context.run_data,
        last_node_executed=node_id,
        record_checkpoint=False,
    )


def make_batch_checkpoint_callback(
    context: Any,
    node: dict[str, Any],
    node_type: Any,
    *,
    min_interval_secs: float = BATCH_CHECKPOINT_MIN_INTERVAL_SECS,
) -> Callable[[int, int, list[T | None]], Awaitable[None]] | None:
    """
    Return an ``on_items_checkpoint`` hook for ``map_flow_items_batch``, or ``None`` when
    partial persist does not apply (sequential / non-batch node types).
    """

    if not node_uses_batch_partial_persist(node, node_type):
        return None

    node_id = str(node["id"])
    last_persist_at = 0.0

    async def on_checkpoint(_completed: int, total: int, results: list[T | None]) -> None:
        nonlocal last_persist_at
        now = time.monotonic()
        if last_persist_at and (now - last_persist_at) < min_interval_secs:
            return
        last_persist_at = now
        await persist_batch_node_partial(
            context,
            node_id,
            items_total=total,
            results=results,
            status="running",
        )

    return on_checkpoint
