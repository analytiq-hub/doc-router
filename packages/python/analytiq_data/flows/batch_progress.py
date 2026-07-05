from __future__ import annotations

"""Partial batch-node progress: persist completed items at checkpoints and on stop/error."""

import time
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Any, TypeVar

from bson import ObjectId

import analytiq_data as ad

from .engine import _bson_serialize_value, offload_flow_items_binary_refs, persist_run_data
from .node_settings import node_uses_batch_partial_persist

T = TypeVar("T")

BATCH_CHECKPOINT_MIN_INTERVAL_SECS = 1.0

DOCROUTER_BATCH_CONTINUE_ON_ITEM_ERROR_TYPES = frozenset({"docrouter.ocr", "docrouter.llm_run"})


def continue_on_item_error_for_node(node: dict[str, Any]) -> bool:
    node_type_key = str(node.get("type") or "")
    if node_type_key not in DOCROUTER_BATCH_CONTINUE_ON_ITEM_ERROR_TYPES:
        return False
    return (node.get("on_error") or "stop") == "continue"


def completed_items_from_results(results: list[Any | None]) -> list[Any]:
    """Return successfully finished items in input order (skip ``None`` placeholders)."""

    return [item for item in results if item is not None]


def _lane_main0(entry: dict[str, Any]) -> list[Any]:
    data = entry.get("data")
    if not isinstance(data, dict):
        return []
    main = data.get("main")
    if not isinstance(main, list) or not main:
        return []
    lane = main[0]
    return list(lane) if isinstance(lane, list) else []


def prior_completed_count_from_entry(entry: Any) -> int:
    """How many completed items are already stored for a batch node entry."""

    if not isinstance(entry, dict):
        return 0
    items_completed = entry.get("items_completed")
    if isinstance(items_completed, int):
        return items_completed
    return len(_lane_main0(entry))


def batch_run_entry_is_resumable(entry: Any) -> bool:
    """True when a node run entry has incomplete batch output that can be resumed."""

    if not isinstance(entry, dict):
        return False
    status = entry.get("status")
    if status not in ("partial", "error", "running"):
        return False
    items_total = entry.get("items_total")
    items_completed = entry.get("items_completed")
    if isinstance(items_total, int) and items_total > 0 and isinstance(items_completed, int):
        return items_completed < items_total
    lane = _lane_main0(entry)
    if not lane:
        return False
    if isinstance(items_total, int) and items_total > 0:
        return len(lane) < items_total
    return status == "partial"


def run_data_has_resumable_batch(run_data: dict[str, Any] | None) -> bool:
    if not isinstance(run_data, dict):
        return False
    return any(batch_run_entry_is_resumable(entry) for entry in run_data.values())


def completed_item_indices_from_entry(entry: dict[str, Any]) -> set[int]:
    indices: set[int] = set()
    for item in _lane_main0(entry):
        if not isinstance(item, ad.flows.FlowItem):
            item = ad.flows.coerce_flow_item(item)
        meta = item.meta if isinstance(item.meta, dict) else {}
        raw = meta.get("item_index")
        if isinstance(raw, int):
            indices.add(raw)
    return indices


def load_batch_resume_items(entry: Any) -> dict[int, ad.flows.FlowItem]:
    """Map ``item_index`` → existing ``FlowItem`` from a resumable partial run entry."""

    if not batch_run_entry_is_resumable(entry):
        return {}
    out: dict[int, ad.flows.FlowItem] = {}
    for raw in _lane_main0(entry):
        item = raw if isinstance(raw, ad.flows.FlowItem) else ad.flows.coerce_flow_item(raw)
        meta = item.meta if isinstance(item.meta, dict) else {}
        raw_idx = meta.get("item_index")
        if isinstance(raw_idx, int):
            out[raw_idx] = item
    return out


def batch_items_remaining(entry: dict[str, Any]) -> int | None:
    items_total = entry.get("items_total")
    items_completed = entry.get("items_completed")
    if isinstance(items_total, int) and isinstance(items_completed, int):
        return max(0, items_total - items_completed)
    lane = _lane_main0(entry)
    if isinstance(items_total, int) and items_total > len(lane):
        return items_total - len(lane)
    return None


def _build_batch_node_entry(
    context: Any,
    node_id: str,
    *,
    items_total: int,
    completed: list[Any],
    status: str,
    existing_dict: dict[str, Any],
    items_failed: int | None,
    error: dict[str, Any] | None,
    items_skipped_on_resume: int | None,
) -> dict[str, Any]:
    start_time = existing_dict.get("start_time") or datetime.now(UTC).isoformat()
    entry: dict[str, Any] = {
        "status": status,
        "start_time": start_time,
        "execution_index": context.execution_index,
        "items_total": items_total,
        "items_completed": len(completed),
        "data": {"main": [completed]},
        "error": error if error is not None else existing_dict.get("error"),
        "source": existing_dict.get("source"),
        "logs": existing_dict.get("logs"),
        "trace": existing_dict.get("trace"),
    }
    if items_failed is not None:
        entry["items_failed"] = items_failed
    if items_skipped_on_resume is not None:
        entry["items_skipped_on_resume"] = items_skipped_on_resume
    return entry


async def _persist_batch_node_delta_mongo(
    context: Any,
    node_id: str,
    entry: dict[str, Any],
    delta_items: list[Any],
    *,
    prior_completed_count: int,
) -> None:
    """Append only new completed items to Mongo instead of rewriting the full lane."""

    if context.analytiq_client is None:
        return

    db = ad.common.get_async_db(context.analytiq_client)
    if delta_items:
        await offload_flow_items_binary_refs(
            delta_items,
            execution_id=context.execution_id,
            node_id=node_id,
            base_lane_index=prior_completed_count,
            analytiq_client=context.analytiq_client,
        )

    node_path = f"run_data.{node_id}"
    set_patch: dict[str, Any] = {
        f"{node_path}.status": entry["status"],
        f"{node_path}.start_time": entry["start_time"],
        f"{node_path}.execution_index": entry["execution_index"],
        f"{node_path}.items_total": entry["items_total"],
        f"{node_path}.items_completed": entry["items_completed"],
        "last_heartbeat_at": datetime.now(UTC),
        "last_node_executed": node_id,
    }
    for key in ("error", "source", "logs", "trace", "items_failed", "items_skipped_on_resume"):
        if key in entry:
            set_patch[f"{node_path}.{key}"] = entry[key]

    update: dict[str, Any] = {"$set": set_patch}
    if delta_items:
        serialized_delta = [_bson_serialize_value(x) for x in delta_items]
        if prior_completed_count == 0:
            set_patch[f"{node_path}.data"] = {"main": [serialized_delta]}
        else:
            update["$push"] = {f"{node_path}.data.main.0": {"$each": serialized_delta}}

    await db.flow_executions.update_one(
        {"_id": ObjectId(context.execution_id)},
        update,
    )


async def persist_batch_node_partial(
    context: Any,
    node_id: str,
    *,
    items_total: int,
    results: list[Any | None],
    status: str = "running",
    items_failed: int | None = None,
    error: dict[str, Any] | None = None,
    items_skipped_on_resume: int | None = None,
    mongo_delta_from: int | None = None,
) -> int:
    """
    Write partial batch output into ``context.run_data[node_id]`` and persist to Mongo.

    Includes the full list of completed items in ``data.main[0]`` in memory (never counters-only).

    When ``mongo_delta_from`` is set (checkpoint path), only items from that index onward in the
    completed list are appended to Mongo. Returns ``len(completed)`` so callers can pass it as
    the next ``mongo_delta_from``.
    """

    completed = completed_items_from_results(results)
    existing = context.run_data.get(node_id)
    existing_dict = existing if isinstance(existing, dict) else {}
    entry = _build_batch_node_entry(
        context,
        node_id,
        items_total=items_total,
        completed=completed,
        status=status,
        existing_dict=existing_dict,
        items_failed=items_failed,
        error=error,
        items_skipped_on_resume=items_skipped_on_resume,
    )

    context.run_data[node_id] = entry

    if mongo_delta_from is not None:
        delta_items = completed[mongo_delta_from:]
        await _persist_batch_node_delta_mongo(
            context,
            node_id,
            entry,
            delta_items,
            prior_completed_count=mongo_delta_from,
        )
    else:
        await persist_run_data(
            context,
            context.run_data,
            last_node_executed=node_id,
            record_checkpoint=False,
        )

    return len(completed)


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
    prior_completed = prior_completed_count_from_entry(context.run_data.get(node_id))

    async def on_checkpoint(_completed: int, total: int, results: list[T | None]) -> None:
        nonlocal last_persist_at, prior_completed
        now = time.monotonic()
        if last_persist_at and (now - last_persist_at) < min_interval_secs:
            return
        last_persist_at = now
        prior_completed = await persist_batch_node_partial(
            context,
            node_id,
            items_total=total,
            results=results,
            status="running",
            mongo_delta_from=prior_completed,
        )

    return on_checkpoint


def make_batch_fatal_error_callback(
    context: Any,
    node: dict[str, Any],
    node_type: Any,
) -> Callable[[int, int, list[T | None], BaseException], Awaitable[None]] | None:
    """Persist all completed items when the first fatal item error occurs."""

    if not node_uses_batch_partial_persist(node, node_type):
        return None

    node_id = str(node["id"])

    async def on_fatal(_completed: int, total: int, results: list[T | None], exc: BaseException) -> None:
        from .errors import node_error_envelope

        node_label = ad.flows.node_name(node)
        error_env = node_error_envelope(
            exc,
            node_id=node_id,
            node_name=node_label,
            include_stack=True,
        )
        await persist_batch_node_partial(
            context,
            node_id,
            items_total=total,
            results=results,
            status="error",
            items_failed=1,
            error=error_env,
        )

    return on_fatal
