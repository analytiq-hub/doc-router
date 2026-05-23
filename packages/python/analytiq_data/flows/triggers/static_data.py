from __future__ import annotations

"""Persist per-(flow, node) trigger static data (poll cursors, etc.)."""

from datetime import datetime, UTC
from typing import Any


async def load_node_static_data(db, flow_id: str, node_id: str) -> dict[str, Any]:
    doc = await db.flow_static_data.find_one({"flow_id": flow_id, "node_id": node_id})
    if not doc:
        return {}
    data = doc.get("data")
    return dict(data) if isinstance(data, dict) else {}


async def save_node_static_data(
    db,
    flow_id: str,
    node_id: str,
    data: dict[str, Any],
) -> None:
    now = datetime.now(UTC)
    await db.flow_static_data.update_one(
        {"flow_id": flow_id, "node_id": node_id},
        {
            "$set": {"data": data, "updated_at": now},
            "$setOnInsert": {"flow_id": flow_id, "node_id": node_id, "created_at": now},
        },
        upsert=True,
    )
