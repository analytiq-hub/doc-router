"""
Server-side list for forms: latest ``form_revisions`` row per ``form_id`` for an org,
with optional MUI grid sort/filter. ``form_version`` and ``actions`` are not sortable/filterable.
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


def _map_sort_field(field: str | None) -> str | None:
    if field is None:
        return None
    if str(field) in ("form_version", "actions"):
        return None
    return {
        "name": "name",
        "form_id": "form_id",
        "tag_ids": "tag_ids",
        "created_at": "created_at",
        "created_by": "created_by",
        "form_revid": "_id",
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
    if str(field) in ("form_version", "actions"):
        return None
    return {
        "name": "name",
        "form_id": "form_id",
        "tag_ids": "tag_ids",
        "created_at": "created_at",
        "created_by": "created_by",
        "form_revid": "_id",
    }.get(str(field))


async def _match_from_filter_model(
    filter_model: dict | None,
    organization_id: str,
    db: Any,
) -> dict[str, Any] | None:
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
            elif mf == "tag_ids":
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
        return None
    if logic == "or":
        return {"$or": clauses} if len(clauses) > 1 else clauses[0]
    return {"$and": clauses} if len(clauses) > 1 else clauses[0]


async def list_forms_for_org(
    db: Any,
    organization_id: str,
    *,
    skip: int,
    limit: int,
    name_search: str | None,
    filter_tag_ids: list[str] | None,
    sort_model: list | None,
    filter_model: dict | None,
) -> tuple[list[dict[str, Any]], int]:
    forms_query: dict[str, Any] = {"organization_id": organization_id}
    if name_search:
        forms_query["name"] = {"$regex": name_search, "$options": "i"}

    org_forms = await db.forms.find(forms_query, {"_id": 1, "name": 1}).to_list(None)
    if not org_forms:
        return [], 0

    form_ids = [str(f["_id"]) for f in org_forms]
    form_id_to_name = {str(f["_id"]): f.get("name") or "" for f in org_forms}

    pipeline: list[dict[str, Any]] = [
        {"$match": {"form_id": {"$in": form_ids}}},
    ]
    if filter_tag_ids:
        pipeline.append({"$match": {"tag_ids": {"$in": filter_tag_ids}}})

    pipeline.extend(
        [
            {"$sort": {"_id": -1}},
            {"$group": {"_id": "$form_id", "doc": {"$first": "$$ROOT"}}},
            {"$replaceRoot": {"newRoot": "$doc"}},
            {
                "$lookup": {
                    "from": "forms",
                    "let": {"fidStr": "$form_id"},
                    "pipeline": [
                        {"$match": {"$expr": {"$eq": [{"$toString": "$_id"}, "$$fidStr"]}}},
                        {"$match": {"organization_id": organization_id}},
                        {"$project": {"name": 1}},
                    ],
                    "as": "_fn",
                }
            },
            {
                "$addFields": {
                    "name": {"$ifNull": [{"$arrayElemAt": ["$_fn.name", 0]}, "Unknown"]},
                }
            },
            {"$project": {"_fn": 0}},
        ]
    )

    grid_match = await _match_from_filter_model(filter_model, organization_id, db)
    if grid_match:
        pipeline.append({"$match": grid_match})

    pipeline.append({"$sort": _build_sort_doc(sort_model)})
    pipeline.append(
        {
            "$facet": {
                "total": [{"$count": "count"}],
                "forms": [{"$skip": skip}, {"$limit": limit}],
            }
        }
    )

    result = await db.form_revisions.aggregate(pipeline).to_list(length=1)
    result = result[0] if result else {"total": [], "forms": []}
    total_count = result["total"][0]["count"] if result.get("total") else 0
    forms = result.get("forms") or []

    for form in forms:
        form["form_revid"] = str(form.pop("_id"))
        fid = form.get("form_id")
        if fid and form.get("name") in (None, "Unknown"):
            form["name"] = form_id_to_name.get(str(fid), form.get("name") or "Unknown")

    return forms, total_count
