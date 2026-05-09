"""
Server-side list for tags with optional MUI DataGrid sort/filter.
"""

from __future__ import annotations

import re
from typing import Any

from analytiq_data.common.grid_filter import build_filter_match, build_sort_doc

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

    sort_doc: dict[str, Any] = {}
    if name_search:
        name_lower = name_search.lower()
        escaped = re.escape(name_search)
        sort_doc["match_rank"] = 1
    sort_doc.update(build_sort_doc(sort_model, _FIELD_MAP, default_tiebreaker="_id"))

    pipeline: list[dict[str, Any]] = [{"$match": query}]
    if name_search:
        pipeline.append({
            "$addFields": {
                "match_rank": {
                    "$switch": {
                        "branches": [
                            {"case": {"$eq": [{"$toLower": "$name"}, name_lower]}, "then": 0},
                            {"case": {"$regexMatch": {"input": "$name", "regex": f"^{escaped}", "options": "i"}}, "then": 1},
                        ],
                        "default": 2,
                    }
                }
            }
        })
    pipeline.append({"$sort": sort_doc})
    pipeline.append({
        "$facet": {
            "total": [{"$count": "count"}],
            "tags": [{"$skip": skip}, {"$limit": limit}],
        }
    })

    result = await db.tags.aggregate(pipeline).to_list(length=1)
    result = result[0] if result else {"total": [], "tags": []}
    total_count = result["total"][0]["count"] if result.get("total") else 0
    raw = result.get("tags") or []
    for t in raw:
        t.pop("match_rank", None)

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
