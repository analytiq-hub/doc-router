"""
Server-side list for schemas: latest revision per schema_id, optional MUI grid sort/filter.
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


def _map_sort_field(field: str | None) -> str | None:
    if field is None:
        return None
    if str(field) in ("schema_version", "fields"):
        return None
    return {
        "name": "name",
        "created_at": "created_at",
        "created_by": "created_by",
        "schema_id": "schema_id",
        "schema_revid": "_id",
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
            direction = -1 if str(item.get("sort", "")).lower() == "desc" else 1
            sort_doc[mf] = direction
    if not sort_doc:
        sort_doc["_id"] = -1
    elif "_id" not in sort_doc:
        sort_doc["_id"] = -1
    return sort_doc


def _mongo_field(field: str) -> str | None:
    if str(field) in ("schema_version", "fields"):
        return None
    return {
        "name": "name",
        "created_at": "created_at",
        "created_by": "created_by",
        "schema_id": "schema_id",
        "schema_revid": "_id",
    }.get(str(field))


def _match_from_filter_model(filter_model: dict | None) -> dict[str, Any] | None:
    if not filter_model or not isinstance(filter_model, dict):
        return None
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
        return None
    if logic == "or":
        return {"$or": clauses} if len(clauses) > 1 else clauses[0]
    return {"$and": clauses} if len(clauses) > 1 else clauses[0]


async def list_schemas_for_org(
    db: Any,
    organization_id: str,
    *,
    skip: int,
    limit: int,
    name_search: str | None,
    sort_model: list | None,
    filter_model: dict | None,
) -> tuple[list[dict[str, Any]], int]:
    """
    Latest ``schema_revisions`` row per ``schema_id`` for schemas in the org.
    Returns revision-shaped dicts (plus ``name`` from ``schemas``) and total row count before pagination.
    """
    schemas_query: dict[str, Any] = {"organization_id": organization_id}
    if name_search:
        schemas_query["name"] = {"$regex": name_search, "$options": "i"}

    org_schemas = await db.schemas.find(schemas_query, {"_id": 1, "name": 1}).to_list(None)
    if not org_schemas:
        return [], 0

    schema_ids = [str(s["_id"]) for s in org_schemas]
    schema_id_to_name = {str(s["_id"]): s.get("name") or "" for s in org_schemas}

    pipeline: list[dict[str, Any]] = [
        {"$match": {"schema_id": {"$in": schema_ids}}},
        {"$sort": {"_id": -1}},
        {"$group": {"_id": "$schema_id", "doc": {"$first": "$$ROOT"}}},
        {"$replaceRoot": {"newRoot": "$doc"}},
        {
            "$lookup": {
                "from": "schemas",
                "let": {"sidStr": "$schema_id"},
                "pipeline": [
                    {"$match": {"$expr": {"$eq": [{"$toString": "$_id"}, "$$sidStr"]}}},
                    {"$match": {"organization_id": organization_id}},
                    {"$project": {"name": 1}},
                ],
                "as": "_sn",
            }
        },
        {
            "$addFields": {
                "name": {"$ifNull": [{"$arrayElemAt": ["$_sn.name", 0]}, "Unknown"]},
            }
        },
        {"$project": {"_sn": 0}},
    ]

    grid_match = _match_from_filter_model(filter_model)
    if grid_match:
        pipeline.append({"$match": grid_match})

    pipeline.append({"$sort": _build_sort_doc(sort_model)})
    pipeline.append(
        {
            "$facet": {
                "total": [{"$count": "count"}],
                "schemas": [{"$skip": skip}, {"$limit": limit}],
            }
        }
    )

    result = await db.schema_revisions.aggregate(pipeline).to_list(length=1)
    result = result[0] if result else {"total": [], "schemas": []}
    total_count = result["total"][0]["count"] if result.get("total") else 0
    schemas = result.get("schemas") or []

    for schema in schemas:
        schema["schema_revid"] = str(schema.pop("_id"))
        sid = schema.get("schema_id")
        if sid and schema.get("name") in (None, "Unknown"):
            schema["name"] = schema_id_to_name.get(str(sid), schema.get("name") or "Unknown")

    return schemas, total_count
