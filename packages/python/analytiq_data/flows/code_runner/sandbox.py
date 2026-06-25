from __future__ import annotations

from typing import Any


def flow_item_to_sandbox_dict(item: Any) -> dict[str, Any]:
    """Serialize a ``FlowItem`` (or dict) for the subprocess boundary."""
    import analytiq_data as ad

    if isinstance(item, ad.flows.FlowItem):
        flow_item = item
    else:
        flow_item = ad.flows.coerce_flow_item(item)

    binary_out: dict[str, dict[str, Any]] = {}
    for name, ref in (flow_item.binary or {}).items():
        binary_out[name] = {
            "mime_type": ref.mime_type,
            "file_name": ref.file_name,
            "storage_id": ref.storage_id,
            "file_size": ref.file_size,
        }
    return {
        "json": dict(flow_item.json),
        "binary": binary_out,
        "meta": dict(flow_item.meta or {}),
        "paired_item": flow_item.paired_item,
    }
