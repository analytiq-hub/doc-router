from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class BinaryRef:
    mime_type: str
    file_name: str | None = None
    data: bytes | None = None
    storage_id: str | None = None


@dataclass
class FlowItem:
    json: dict[str, Any]
    binary: dict[str, BinaryRef]
    meta: dict[str, Any]
    paired_item: int | list[int] | None = None

