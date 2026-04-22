"""
Server-side list for prompts: latest revision per prompt, optional grid sort/filter.
"""

from __future__ import annotations

import logging
from typing import Any

from analytiq_data.common.grid_filter import build_filter_match, build_sort_doc

logger = logging.getLogger(__name__)

_FIELD_MAP: dict[str, str | None] = {
    "name": "name",
    "model": "model",
    "schema_id": "schema_id",
    "tag_ids": "tag_ids",
    "created_at": "created_at",
    "prompt_revid": "_id",
    # "prompt_version" intentionally absent → skipped
}

_DATETIME_FIELDS = {"created_at"}
_TAG_ID_FIELDS = {"tag_ids"}
_REF_NAME_FIELDS = {"schema_id": "schemas"}


async def list_prompts_for_org(
    db: Any,
    organization_id: str,
    *,
    skip: int,
    limit: int,
    name_search: str | None,
    tag_ids_param: list[str] | None,
    sort_model: list | None,
    filter_model: dict | None,
    pre_grid_stages: list[dict[str, Any]] | None = None,
) -> tuple[list[dict[str, Any]], int]:
    """
    Returns (prompt_revision_docs_with_prompt_revid_str, total_count) for one org page.
    Each doc includes ``name`` from ``prompts`` (via aggregation).
    """
    prompts_query: dict[str, Any] = {"organization_id": organization_id}
    if name_search:
        prompts_query["name"] = {"$regex": name_search, "$options": "i"}

    org_prompts = await db.prompts.find(prompts_query, {"_id": 1, "name": 1}).to_list(None)
    if not org_prompts:
        return [], 0

    prompt_id_to_name = {str(p["_id"]): p.get("name") or "" for p in org_prompts}

    pipeline: list[dict[str, Any]] = [
        {
            "$match": {
                "prompt_id": {"$in": [str(p["_id"]) for p in org_prompts]},
                "organization_id": organization_id,
            }
        },
        {"$sort": {"_id": -1}},
        {"$group": {"_id": "$prompt_id", "doc": {"$first": "$$ROOT"}}},
        {"$replaceRoot": {"newRoot": "$doc"}},
        {
            "$lookup": {
                "from": "prompts",
                "let": {"pidStr": "$prompt_id"},
                "pipeline": [
                    {"$match": {"$expr": {"$eq": [{"$toString": "$_id"}, "$$pidStr"]}}},
                    {"$match": {"organization_id": organization_id}},
                    {"$project": {"name": 1}},
                ],
                "as": "_pn",
            }
        },
        {
            "$addFields": {
                "name": {"$ifNull": [{"$arrayElemAt": ["$_pn.name", 0]}, "Unknown"]},
            }
        },
        {"$project": {"_pn": 0}},
    ]

    if pre_grid_stages:
        pipeline.extend(pre_grid_stages)

    grid_match = await build_filter_match(
        filter_model, _FIELD_MAP,
        db=db, organization_id=organization_id,
        datetime_fields=_DATETIME_FIELDS,
        tag_id_fields=_TAG_ID_FIELDS,
        ref_name_fields=_REF_NAME_FIELDS,
    )
    if grid_match:
        pipeline.append({"$match": grid_match})

    if tag_ids_param:
        pipeline.append({"$match": {"tag_ids": {"$all": tag_ids_param}}})

    pipeline.append({"$sort": build_sort_doc(sort_model, _FIELD_MAP)})
    pipeline.append(
        {
            "$facet": {
                "total": [{"$count": "count"}],
                "prompts": [{"$skip": skip}, {"$limit": limit}],
            }
        }
    )

    result = await db.prompt_revisions.aggregate(pipeline).to_list(length=1)
    result = result[0] if result else {"total": [], "prompts": []}
    total_count = result["total"][0]["count"] if result.get("total") else 0
    prompts = result.get("prompts") or []

    for prompt in prompts:
        prompt["prompt_revid"] = str(prompt.pop("_id"))
        pid = prompt.get("prompt_id")
        if pid and prompt.get("name") in (None, "Unknown"):
            prompt["name"] = prompt_id_to_name.get(str(pid), prompt.get("name") or "Unknown")

    return prompts, total_count
