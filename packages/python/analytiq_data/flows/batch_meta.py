from __future__ import annotations

from typing import Any

BATCH_META_KEYS = ("items_total", "items_completed", "items_failed", "items_skipped_on_resume")


def partial_main_from_entry(entry: Any) -> list[Any] | None:
    """Return ``data.main`` when a run entry holds non-empty partial batch output."""

    if not isinstance(entry, dict):
        return None
    data = entry.get("data")
    if not isinstance(data, dict):
        return None
    main = data.get("main")
    if not isinstance(main, list) or not main:
        return None
    if not any(isinstance(lane, list) and lane for lane in main):
        return None
    return main


def completed_count_from_out_lists(out_lists: list[Any]) -> int:
    if not out_lists:
        return 0
    lane = out_lists[0]
    return len(lane) if isinstance(lane, list) else 0


def batch_output_is_incomplete(prior_entry: Any, out_lists: list[Any]) -> bool:
    """True when a batch node stopped before all ``items_total`` items finished."""

    if not isinstance(prior_entry, dict):
        return False
    items_total = prior_entry.get("items_total")
    if not isinstance(items_total, int) or items_total <= 0:
        return False
    completed = completed_count_from_out_lists(out_lists)
    prior_completed = prior_entry.get("items_completed")
    if isinstance(prior_completed, int):
        completed = max(completed, prior_completed)
    return completed < items_total


def merge_batch_meta_for_final_persist(
    prior_entry: Any,
    out_lists: list[Any],
) -> dict[str, Any]:
    """Copy batch counters from a checkpoint entry onto the engine's final node persist."""

    meta: dict[str, Any] = {}
    if not isinstance(prior_entry, dict):
        return meta
    for key in BATCH_META_KEYS:
        if key in prior_entry:
            meta[key] = prior_entry[key]
    if "items_total" in meta:
        completed = completed_count_from_out_lists(out_lists)
        prior_completed = prior_entry.get("items_completed")
        if isinstance(prior_completed, int):
            completed = max(completed, prior_completed)
        meta["items_completed"] = completed
    return meta
