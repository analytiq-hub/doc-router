"""
Server-side list for prompts: latest revision per prompt, optional grid sort/filter.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, UTC
from typing import Any

from bson import ObjectId

from analytiq_data.common.tag_grid_filters import resolve_tag_filter_values_to_ids

logger = logging.getLogger(__name__)


def _parse_dt(v: Any) -> datetime | None:
    if v is None:
        return None
    if isinstance(v, datetime):
        return v
    s = str(v).strip()
    if not s:
        return None
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(s)
    except Exception:
        try:
            return datetime.fromisoformat(s + "T00:00:00+00:00")
        except Exception:
            return None


def _map_sort_field(field: str | None) -> str | None:
    if field is None:
        return None
    if str(field) == "prompt_version":
        return None
    return {
        "name": "name",
        "model": "model",
        "schema_id": "schema_id",
        "tag_ids": "tag_ids",
        "created_at": "created_at",
        "prompt_revid": "_id",
    }.get(str(field))


def _build_sort_doc(sort_model: list | None) -> dict[str, int]:
    sort_doc: dict[str, int] = {}
    if sort_model:
        for item in sort_model:
            if not isinstance(item, dict):
                continue
            mf = _map_sort_field(item.get("field"))
            if not mf:
                continue
            direction = -1 if item.get("sort") == "desc" else 1
            sort_doc[mf] = direction
    if not sort_doc:
        sort_doc["_id"] = -1
    elif "_id" not in sort_doc:
        sort_doc["_id"] = -1
    return sort_doc


def _as_list_value(v: Any) -> list[str]:
    if v is None:
        return []
    if isinstance(v, list):
        return [str(x) for x in v if str(x).strip()]
    s = str(v)
    if "," in s:
        return [p.strip() for p in s.split(",") if p.strip()]
    return [s.strip()] if s.strip() else []


async def _match_from_filter_model(
    filter_model: dict | None,
    organization_id: str,
    db: Any,
) -> dict[str, Any] | None:
    if not filter_model or not isinstance(filter_model, dict):
        return None
    items = filter_model.get("items") or []
    logic = (filter_model.get("logicOperator") or "and").lower()

    def mongo_field(field: str) -> str | None:
        if str(field) == "prompt_version":
            return None
        return {
            "name": "name",
            "model": "model",
            "schema_id": "schema_id",
            "tag_ids": "tag_ids",
            "created_at": "created_at",
        }.get(str(field))

    clauses: list[dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        field = item.get("field")
        op = item.get("operator") or item.get("operatorValue")
        value = item.get("value")
        if not field or not op:
            continue

        mf = mongo_field(str(field))
        if not mf:
            continue

        op = str(op)
        str_value = "" if value is None else str(value)

        if op in ("isEmpty", "is empty"):
            clauses.append({"$or": [{mf: ""}, {mf: None}, {mf: {"$exists": False}}]})
            continue
        if op in ("isNotEmpty", "is not empty"):
            clauses.append({"$and": [{mf: {"$exists": True}}, {mf: {"$nin": ["", None]}}]})
            continue

        if op in ("isAnyOf", "is any of"):
            values = _as_list_value(value)
            if not values:
                continue
            if mf == "tag_ids":
                tag_id_strs = await resolve_tag_filter_values_to_ids(db, organization_id, values)
                if not tag_id_strs:
                    clauses.append({"_id": {"$exists": False}})
                    continue
                clauses.append({mf: {"$in": tag_id_strs}})
            else:
                clauses.append({mf: {"$in": values}})
            continue

        if mf == "created_at":
            dt = _parse_dt(value)
            if op in ("is", "equals") and dt:
                clauses.append({mf: dt})
            elif op in ("not", "doesNotEqual", "does not equal") and dt:
                clauses.append({mf: {"$ne": dt}})
            elif op in ("after",) and dt:
                clauses.append({mf: {"$gt": dt}})
            elif op in ("onOrAfter", "on or after") and dt:
                clauses.append({mf: {"$gte": dt}})
            elif op in ("before",) and dt:
                clauses.append({mf: {"$lt": dt}})
            elif op in ("onOrBefore", "on or before") and dt:
                clauses.append({mf: {"$lte": dt}})
            continue

        if mf == "tag_ids" and str_value.strip():
            name_query: dict[str, Any] | None = None
            if op == "contains":
                name_query = {"$regex": re.escape(str_value), "$options": "i"}
            elif op in ("startsWith", "starts with"):
                name_query = {"$regex": f"^{re.escape(str_value)}", "$options": "i"}
            elif op in ("endsWith", "ends with"):
                name_query = {"$regex": f"{re.escape(str_value)}$", "$options": "i"}
            elif op in ("equals", "=", "is"):
                name_query = {"$regex": f"^{re.escape(str_value)}$", "$options": "i"}
            elif op in ("doesNotContain", "does not contain"):
                name_query = {"$regex": re.escape(str_value), "$options": "i"}
            elif op in ("doesNotEqual", "does not equal"):
                name_query = str_value

            if name_query is not None:
                tag_docs = await db.tags.find(
                    {"organization_id": organization_id, "name": name_query},
                    {"_id": 1},
                ).limit(200).to_list(length=200)
                tag_id_strs = [str(t["_id"]) for t in tag_docs]
                if not tag_id_strs:
                    if op in ("doesNotContain", "does not contain", "doesNotEqual", "does not equal"):
                        continue
                    clauses.append({"_id": {"$exists": False}})
                    continue

                if op in ("doesNotContain", "does not contain", "doesNotEqual", "does not equal"):
                    clauses.append({mf: {"$nin": tag_id_strs}})
                else:
                    clauses.append({mf: {"$in": tag_id_strs}})
                continue

        # Prompts store stable schema_id (string); the grid column shows schema *name*.
        # Resolve text operators against `schemas.name`, like tag_ids vs `tags.name`.
        # For equals / doesNotEqual only: valid ObjectId strings match the stable id, not the display name.
        if (
            mf == "schema_id"
            and str_value.strip()
            and ObjectId.is_valid(str_value)
            and op in ("equals", "doesNotEqual", "does not equal")
        ):
            oid_str = str(ObjectId(str_value))
            doc = await db.schemas.find_one(
                {"_id": ObjectId(str_value), "organization_id": organization_id},
                {"_id": 1},
            )
            if op in ("equals",):
                if doc:
                    clauses.append({mf: oid_str})
                else:
                    clauses.append({"_id": {"$exists": False}})
                continue
            if doc:
                clauses.append({mf: {"$ne": oid_str}})
            continue

        if mf == "schema_id" and str_value.strip():
            schema_name_query: dict[str, Any] | None = None
            if op == "contains":
                schema_name_query = {"$regex": re.escape(str_value), "$options": "i"}
            elif op in ("startsWith", "starts with"):
                schema_name_query = {"$regex": f"^{re.escape(str_value)}", "$options": "i"}
            elif op in ("endsWith", "ends with"):
                schema_name_query = {"$regex": f"{re.escape(str_value)}$", "$options": "i"}
            elif op == "equals":
                schema_name_query = str_value
            elif op in ("doesNotContain", "does not contain"):
                schema_name_query = {"$regex": re.escape(str_value), "$options": "i"}
            elif op in ("doesNotEqual", "does not equal"):
                schema_name_query = str_value

            if schema_name_query is not None:
                schema_docs = await db.schemas.find(
                    {"organization_id": organization_id, "name": schema_name_query},
                    {"_id": 1},
                ).limit(200).to_list(length=200)
                schema_id_strs = [str(s["_id"]) for s in schema_docs]
                if not schema_id_strs:
                    if op in ("doesNotContain", "does not contain", "doesNotEqual", "does not equal"):
                        continue
                    clauses.append({"_id": {"$exists": False}})
                    continue

                if op in ("doesNotContain", "does not contain", "doesNotEqual", "does not equal"):
                    clauses.append({mf: {"$nin": schema_id_strs}})
                else:
                    clauses.append({mf: {"$in": schema_id_strs}})
                continue

        if op in ("contains",):
            if not str_value.strip():
                continue
            clauses.append({mf: {"$regex": re.escape(str_value), "$options": "i"}})
            continue
        if op in ("doesNotContain", "does not contain"):
            if not str_value.strip():
                continue
            clauses.append({mf: {"$not": {"$regex": re.escape(str_value), "$options": "i"}}})
            continue
        if op in ("equals",):
            clauses.append({mf: str_value})
            continue
        if op in ("doesNotEqual", "does not equal"):
            clauses.append({mf: {"$ne": str_value}})
            continue
        if op in ("startsWith", "starts with"):
            if not str_value.strip():
                continue
            clauses.append({mf: {"$regex": f"^{re.escape(str_value)}", "$options": "i"}})
            continue
        if op in ("endsWith", "ends with"):
            if not str_value.strip():
                continue
            clauses.append({mf: {"$regex": f"{re.escape(str_value)}$", "$options": "i"}})
            continue

    if not clauses:
        return None
    if logic == "or":
        return {"$or": clauses} if len(clauses) > 1 else clauses[0]
    return {"$and": clauses} if len(clauses) > 1 else clauses[0]


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

    prompt_ids = [p["_id"] for p in org_prompts]
    prompt_id_to_name = {str(p["_id"]): p.get("name") or "" for p in org_prompts}

    pipeline: list[dict[str, Any]] = [
        {
            "$match": {
                "prompt_id": {"$in": [str(pid) for pid in prompt_ids]},
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

    grid_match = await _match_from_filter_model(filter_model, organization_id, db)
    if grid_match:
        pipeline.append({"$match": grid_match})

    if tag_ids_param:
        pipeline.append({"$match": {"tag_ids": {"$all": tag_ids_param}}})

    sort_doc = _build_sort_doc(sort_model)
    pipeline.append({"$sort": sort_doc})

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
