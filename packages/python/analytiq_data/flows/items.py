from __future__ import annotations

"""
Runtime item model for flow execution.

`FlowItem` is the unit of data passed between nodes. It supports a JSON payload,
named binary attachments (by reference), and engine-managed metadata.
"""

from dataclasses import dataclass
from typing import Any


@dataclass
class BinaryRef:
    """Reference to a binary attachment that should not be embedded in persisted run_data."""

    mime_type: str
    file_name: str | None = None
    data: bytes | None = None
    storage_id: str | None = None


@dataclass
class FlowItem:
    """Single item flowing through the graph; nodes read/write `json` and may attach binaries."""

    json: dict[str, Any]
    binary: dict[str, BinaryRef]
    meta: dict[str, Any]
    paired_item: int | list[int] | None = None

