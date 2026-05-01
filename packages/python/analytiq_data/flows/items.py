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


def coerce_binary_ref(raw: Any) -> BinaryRef:
    """
    Coerce a persisted / JSON-ish representation of a binary ref into `BinaryRef`.

    Accepts:
    - `BinaryRef` (no-op)
    - `dict` with keys `mime_type`, `file_name`, `data`, `storage_id`
    """

    if isinstance(raw, BinaryRef):
        return raw
    if not isinstance(raw, dict):
        raise ValueError(f"BinaryRef must be a BinaryRef or dict, got {type(raw).__name__}")

    mime_type = raw.get("mime_type")
    if not isinstance(mime_type, str) or not mime_type:
        raise ValueError("BinaryRef.mime_type must be a non-empty string")

    file_name = raw.get("file_name")
    if file_name is not None and not isinstance(file_name, str):
        raise ValueError("BinaryRef.file_name must be str | None")

    data = raw.get("data")
    if data is not None and not isinstance(data, (bytes, bytearray)):
        raise ValueError("BinaryRef.data must be bytes | None")

    storage_id = raw.get("storage_id")
    if storage_id is not None and not isinstance(storage_id, str):
        raise ValueError("BinaryRef.storage_id must be str | None")

    return BinaryRef(
        mime_type=mime_type,
        file_name=file_name,
        data=bytes(data) if isinstance(data, bytearray) else data,
        storage_id=storage_id,
    )


def coerce_flow_item(raw: Any) -> FlowItem:
    """
    Coerce a persisted / JSON-ish representation of a flow item into `FlowItem`.

    Accepts:
    - `FlowItem` (no-op)
    - `dict` with keys `json`, `binary`, `meta`, `paired_item`
    """

    if isinstance(raw, FlowItem):
        return raw
    if not isinstance(raw, dict):
        raise ValueError(f"FlowItem must be a FlowItem or dict, got {type(raw).__name__}")

    json_payload = raw.get("json") if raw.get("json") is not None else {}
    if not isinstance(json_payload, dict):
        raise ValueError("FlowItem.json must be a dict")

    meta = raw.get("meta") if raw.get("meta") is not None else {}
    if not isinstance(meta, dict):
        raise ValueError("FlowItem.meta must be a dict")

    raw_binary = raw.get("binary") if raw.get("binary") is not None else {}
    if not isinstance(raw_binary, dict):
        raise ValueError("FlowItem.binary must be a dict")
    binary: dict[str, BinaryRef] = {k: coerce_binary_ref(v) for k, v in raw_binary.items()}

    paired_item = raw.get("paired_item")
    if paired_item is not None and not isinstance(paired_item, (int, list)):
        raise ValueError("FlowItem.paired_item must be int | list[int] | None")
    if isinstance(paired_item, list) and not all(isinstance(x, int) for x in paired_item):
        raise ValueError("FlowItem.paired_item list must contain only ints")

    return FlowItem(
        json=json_payload,
        binary=binary,
        meta=meta,
        paired_item=paired_item,
    )


def coerce_flow_item_list(raw: Any) -> list[FlowItem]:
    """Coerce `raw` into `list[FlowItem]` (accepts a list of FlowItem/dict)."""

    if raw is None:
        return []
    if isinstance(raw, list):
        return [coerce_flow_item(x) for x in raw]
    raise ValueError(f"FlowItem list must be a list, got {type(raw).__name__}")


def coerce_pin_data_node_output(raw: Any) -> list[FlowItem]:
    """
    Coerce a revision ``pin_data`` entry into **lane ``main[0]``** output items.

    Accepts:

    - **List** of ``FlowItem`` / item-shaped dicts (legacy engine tests / hand-written revisons).
    - **Dict** with ``main`` shaped like execution ``data.main`` (frontend / SDK: ``{ main: [[items]] }``).
    """

    if raw is None:
        return []
    if isinstance(raw, list):
        return [coerce_flow_item(x) for x in raw]
    if isinstance(raw, dict):
        main = raw.get("main")
        if main is None:
            return []
        if not isinstance(main, list):
            raise ValueError(f"pin_data.main must be a list or null, got {type(main).__name__}")
        if len(main) == 0:
            return []
        lane0 = main[0]
        if lane0 is None:
            return []
        if not isinstance(lane0, list):
            raise ValueError("pin_data.main[0] must be a list of items or null")
        return [coerce_flow_item(x) for x in lane0]
    raise ValueError(f"pin_data entry must be list or object with main, got {type(raw).__name__}")

