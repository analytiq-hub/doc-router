"""Validate client-supplied `run_data` seeds for partial / execute-step runs."""

from __future__ import annotations

from typing import Any


class RunDataSeedValidationError(ValueError):
    """Raised when a seed entry is malformed (caller maps to HTTP 422)."""


def _validate_one_entry(node_id: str, entry: Any) -> None:
    if not isinstance(entry, dict):
        raise RunDataSeedValidationError(f"run_data[{node_id!r}] must be an object")
    status = entry.get("status")
    if status not in ("success", "error", "skipped"):
        raise RunDataSeedValidationError(f"run_data[{node_id!r}].status must be success, error, or skipped")
    data = entry.get("data")
    if not isinstance(data, dict):
        raise RunDataSeedValidationError(f"run_data[{node_id!r}].data must be an object")
    main = data.get("main")
    if not isinstance(main, list):
        raise RunDataSeedValidationError(f"run_data[{node_id!r}].data.main must be an array")
    for li, lane in enumerate(main):
        if lane is None:
            continue
        if not isinstance(lane, list):
            raise RunDataSeedValidationError(f"run_data[{node_id!r}].data.main[{li}] must be an array")
        for ii, item in enumerate(lane):
            if item is None:
                continue
            if not isinstance(item, dict):
                raise RunDataSeedValidationError(
                    f"run_data[{node_id!r}].data.main[{li}][{ii}] must be an object or null"
                )
            if "json" not in item:
                raise RunDataSeedValidationError(
                    f"run_data[{node_id!r}].data.main[{li}][{ii}] must contain a json field"
                )


def validate_and_filter_run_data_seed(
    *,
    known_node_ids: set[str],
    seed: dict[str, Any] | None,
) -> dict[str, Any]:
    """
    Strip unknown node ids; validate each known entry shape.

    Returns a new dict suitable for `initial_run_data` / merging into execution context.
    """

    if not seed:
        return {}
    out: dict[str, Any] = {}
    for k, v in seed.items():
        if k not in known_node_ids:
            continue
        _validate_one_entry(k, v)
        out[k] = v
    return out
