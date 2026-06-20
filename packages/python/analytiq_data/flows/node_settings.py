from __future__ import annotations

"""Common per-node settings (revision ``nodes[]`` entries)."""

from typing import Any

FLOW_NODE_BATCH_SIZE_DEFAULT = 1
FLOW_NODE_BATCH_SIZE_MIN = 1
FLOW_NODE_BATCH_SIZE_MAX = 32


def resolve_node_batch_size(node: dict[str, Any] | None) -> int:
    """Return batch size for nodes that process input items in batches."""

    node = node or {}
    raw = node.get("batch_size")
    if raw is None:
        raw = node.get("item_concurrency")  # legacy name (pre batch_size rename)
    if raw is None:
        return FLOW_NODE_BATCH_SIZE_DEFAULT
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return FLOW_NODE_BATCH_SIZE_DEFAULT
    return max(FLOW_NODE_BATCH_SIZE_MIN, min(FLOW_NODE_BATCH_SIZE_MAX, value))


def validate_node_batch_size(node: dict[str, Any]) -> list[str]:
    """Validate ``batch_size`` when present on a node."""

    errors: list[str] = []
    if "batch_size" in node and node.get("batch_size") is not None:
        raw = node.get("batch_size")
        try:
            value = int(raw)
        except (TypeError, ValueError):
            errors.append("batch_size must be an integer")
        else:
            if value < FLOW_NODE_BATCH_SIZE_MIN or value > FLOW_NODE_BATCH_SIZE_MAX:
                errors.append(
                    f"batch_size must be between {FLOW_NODE_BATCH_SIZE_MIN} "
                    f"and {FLOW_NODE_BATCH_SIZE_MAX}"
                )
    if "item_concurrency" in node and node.get("item_concurrency") is not None:
        errors.append("item_concurrency is deprecated; use batch_size instead")
    return errors
