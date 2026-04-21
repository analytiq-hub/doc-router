"""
Server-side list for knowledge bases with optional MUI DataGrid sort/filter.
``document_count``, ``chunk_count``, and ``actions`` are not supported for sort/filter.
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any

from bson import ObjectId

from analytiq_data.common.tag_grid_filters import resolve_tag_filter_values_to_ids


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


def _as_list_value(v: Any) -> list[str]:
    if v is None:
        return []
    if isinstance(v, list):
        return [str(x) for x in v if str(x).strip()]
    s = str(v)
    if "," in s:
        return [p.strip() for p in s.split(",") if p.strip()]
    return [s.strip()] if s.strip() else []


def _mongo_field(field: str) -> str | None:
    if str(field) in ("document_count", "chunk_count", "actions"):
        return None
    return {
        "kb_id": "_id",
        "name": "name",
        "description": "description",
        "status": "status",
        "embedding_model": "embedding_model",
        "tag_ids": "tag_ids",
        "created_at": "created_at",
        "updated_at": "updated_at",
        "last_reconciled_at": "last_reconciled_at",
    }.get(str(field))


def _map_sort_field(field: str | None) -> str | None:
    if field is None:
        return None
    if str(field) in ("document_count", "chunk_count", "actions"):
        return None
    return {
        "kb_id": "_id",
        "name": "name",
        "description": "description",
        "status": "status",
        "embedding_model": "embedding_model",
        "tag_ids": "tag_ids",
        "created_at": "created_at",
        "updated_at": "updated_at",
        "last_reconciled_at": "last_reconciled_at",
    }.get(str(field))


def _build_sort_spec(sort_model: list | None) -> list[tuple[str, int]]:
    spec: list[tuple[str, int]] = []
    if sort_model:
        for item in sort_model:
            if not isinstance(item, dict):
                continue
            mf = _map_sort_field(item.get("field"))
            if not mf:
                continue
            direction = 1 if str(item.get("sort", "")).lower() == "asc" else -1
            spec.append((mf, direction))
    if not spec:
        spec = [("created_at", -1)]
    elif not any(f == "_id" for f, _ in spec):
        spec.append(("_id", -1))
    return spec


async def _merge_kb_filter_model(
    db: Any,
    organization_id: str,
    query: dict[str, Any],
    filter_model: dict[str, Any] | None,
) -> dict[str, Any]:
    if not filter_model or not isinstance(filter_model, dict):
        return query
    items = filter_model.get("items") or []
    logic = (filter_model.get("logicOperator") or "and").lower()

    clauses: list[dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        field = item.get("field")
        op = item.get("operator") or item.get("operatorValue")
        value = item.get("value")
        if not field or not op:
            continue

        mf = _mongo_field(str(field))
        if not mf:
            continue

        op = str(op)
        str_value = "" if value is None else str(value)

        if op in ("isEmpty", "is empty"):
            if mf == "_id":
                continue
            if mf == "last_reconciled_at":
                clauses.append({"$or": [{mf: None}, {mf: {"$exists": False}}]})
            else:
                clauses.append({"$or": [{mf: ""}, {mf: None}, {mf: {"$exists": False}}]})
            continue
        if op in ("isNotEmpty", "is not empty"):
            if mf == "_id":
                clauses.append({"$and": [{mf: {"$exists": True}}, {mf: {"$ne": None}}]})
            else:
                clauses.append({"$and": [{mf: {"$exists": True}}, {mf: {"$nin": ["", None]}}]})
            continue

        if op in ("isAnyOf", "is any of"):
            values = _as_list_value(value)
            if not values:
                continue
            if mf == "_id":
                oids = [ObjectId(x) for x in values if ObjectId.is_valid(str(x))]
                if not oids:
                    continue
                clauses.append({mf: {"$in": oids}})
            elif mf == "tag_ids":
                tag_id_strs = await resolve_tag_filter_values_to_ids(db, organization_id, values)
                if not tag_id_strs:
                    clauses.append({"_id": {"$exists": False}})
                    continue
                clauses.append({mf: {"$in": tag_id_strs}})
            else:
                clauses.append({mf: {"$in": values}})
            continue

        if mf in ("created_at", "updated_at", "last_reconciled_at"):
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
                tag_docs = await db["tags"].find(
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

        if mf == "_id":
            sv = str_value.strip()
            if op in ("equals", "=", "is") and ObjectId.is_valid(sv):
                clauses.append({mf: ObjectId(sv)})
                continue
            if op in ("doesNotEqual", "does not equal", "!=") and ObjectId.is_valid(sv):
                clauses.append({mf: {"$ne": ObjectId(sv)}})
                continue
            if op == "contains" and sv:
                clauses.append(
                    {"$expr": {"$regexMatch": {"input": {"$toString": "$_id"}, "regex": re.escape(sv), "options": "i"}}}
                )
                continue
            if op in ("doesNotContain", "does not contain") and sv:
                clauses.append(
                    {
                        "$expr": {
                            "$not": {
                                "$regexMatch": {
                                    "input": {"$toString": "$_id"},
                                    "regex": re.escape(sv),
                                    "options": "i",
                                }
                            }
                        }
                    }
                )
                continue
            if op in ("startsWith", "starts with") and sv:
                clauses.append(
                    {
                        "$expr": {
                            "$regexMatch": {
                                "input": {"$toString": "$_id"},
                                "regex": f"^{re.escape(sv)}",
                                "options": "i",
                            }
                        }
                    }
                )
                continue
            if op in ("endsWith", "ends with") and sv:
                clauses.append(
                    {
                        "$expr": {
                            "$regexMatch": {
                                "input": {"$toString": "$_id"},
                                "regex": f"{re.escape(sv)}$",
                                "options": "i",
                            }
                        }
                    }
                )
                continue
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
        if op in ("equals", "=", "is"):
            clauses.append({mf: str_value})
            continue
        if op in ("doesNotEqual", "does not equal", "!="):
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
        return query
    if logic == "or":
        return {"$and": [query, {"$or": clauses}]}
    return {"$and": [query, *clauses]}


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
    query = await _merge_kb_filter_model(db, organization_id, query, filter_model)

    total_count = await db.knowledge_bases.count_documents(query)
    sort_spec = _build_sort_spec(sort_model)
    cursor = db.knowledge_bases.find(query).sort(sort_spec).skip(skip).limit(limit)
    kbs = await cursor.to_list(length=None)
    return kbs, total_count
