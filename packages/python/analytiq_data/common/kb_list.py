"""
Server-side list for knowledge bases with optional MUI DataGrid sort/filter.
``document_count``, ``chunk_count``, and ``actions`` are not supported for sort/filter.
"""

from __future__ import annotations

from typing import Any

from analytiq_data.common.grid_filter import build_filter_match, build_sort_spec

_FIELD_MAP: dict[str, str | None] = {
    "kb_id": "_id",
    "name": "name",
    "description": "description",
    "status": "status",
    "embedding_model": "embedding_model",
    "tag_ids": "tag_ids",
    "created_at": "created_at",
    "updated_at": "updated_at",
    "last_reconciled_at": "last_reconciled_at",
    # "document_count", "chunk_count", "actions" intentionally absent → skipped
}

_DATETIME_FIELDS = {"created_at", "updated_at", "last_reconciled_at"}
_TAG_ID_FIELDS = {"tag_ids"}
# last_reconciled_at is an optional datetime; isEmpty should not check for ""
_NULL_ONLY_EMPTY_FIELDS = {"last_reconciled_at"}


async def list_knowledge_base_docs_for_org(
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
        tag_id_fields=_TAG_ID_FIELDS,
        null_only_empty_fields=_NULL_ONLY_EMPTY_FIELDS,
    )
    if grid_match:
        query = {"$and": [query, grid_match]}

    total_count = await db.knowledge_bases.count_documents(query)
    sort_spec = build_sort_spec(
        sort_model, _FIELD_MAP,
        default_sort=[("created_at", -1)],
        tiebreaker="_id",
    )
    cursor = db.knowledge_bases.find(query).sort(sort_spec).skip(skip).limit(limit)
    kbs = await cursor.to_list(length=None)
    return kbs, total_count
