"""
Server-side list for tags with optional MUI DataGrid sort/filter.
"""

from __future__ import annotations

from typing import Any

from analytiq_data.common.grid_filter import build_filter_match, build_sort_spec

_FIELD_MAP: dict[str, str | None] = {
    "id": "_id",
    "name": "name",
    "description": "description",
    "color": "color",
    "created_at": "created_at",
    "created_by": "created_by",
    # "actions" intentionally absent → skipped
}

_DATETIME_FIELDS = {"created_at"}


async def list_tags_for_org(
    db: Any,
    organization_id: str,
    *,
    skip: int,
    limit: int,
    name_search: str | None,
    sort_model: list | None,
    filter_model: dict | None,
) -> tuple[list[dict[str, Any]], int]:
    query: dict[str, Any] = {"organization_id": organization_id}
    if name_search:
        query["name"] = {"$regex": name_search, "$options": "i"}

    grid_match = await build_filter_match(
        filter_model, _FIELD_MAP,
        db=db, organization_id=organization_id,
        datetime_fields=_DATETIME_FIELDS,
    )
    if grid_match:
        query = {"$and": [query, grid_match]}

    total_count = await db.tags.count_documents(query)
    sort_spec = build_sort_spec(sort_model, _FIELD_MAP, default_sort=[("_id", -1)])
    cursor = db.tags.find(query).sort(sort_spec).skip(skip).limit(limit)
    raw = await cursor.to_list(length=None)

    tags: list[dict[str, Any]] = [
        {
            "id": str(t["_id"]),
            "name": t["name"],
            "color": t.get("color"),
            "description": t.get("description"),
            "created_at": t["created_at"],
            "created_by": t["created_by"],
        }
        for t in raw
    ]
    return tags, total_count
