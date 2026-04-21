"""
Server-side list for tags with optional MUI DataGrid sort/filter.
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any

from bson import ObjectId


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
    if str(field) == "actions":
        return None
    return {
        "id": "_id",
        "name": "name",
        "description": "description",
        "color": "color",
        "created_at": "created_at",
        "created_by": "created_by",
    }.get(str(field))


def _map_sort_field(field: str | None) -> str:
    if field is None:
        return "_id"
    return {
        "id": "_id",
        "name": "name",
        "description": "description",
        "color": "color",
        "created_at": "created_at",
        "created_by": "created_by",
    }.get(str(field), "_id")


def _merge_filter_model(
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
            if mf == "description":
                clauses.append({"$or": [{mf: ""}, {mf: None}, {mf: {"$exists": False}}]})
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


def _build_sort_spec(sort_model: list | None) -> list[tuple[str, int]]:
    spec: list[tuple[str, int]] = []
    if sort_model:
        for item in sort_model:
            if not isinstance(item, dict):
                continue
            mf = _map_sort_field(item.get("field"))
            direction = 1 if str(item.get("sort", "")).lower() == "asc" else -1
            spec.append((mf, direction))
    if not spec:
        spec = [("_id", -1)]
    elif not any(f == "_id" for f, _ in spec):
        spec.append(("_id", -1))
    return spec


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
    query = _merge_filter_model(query, filter_model)

    total_count = await db.tags.count_documents(query)
    sort_spec = _build_sort_spec(sort_model)
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
