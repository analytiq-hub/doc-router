"""
Shared MUI DataGrid filter/sort helpers for MongoDB.

Each *_list module defines its own field_map; the builders here handle operator
dispatch, ObjectId coercion, datetime comparisons, tag-name resolution, and
display-name→ID resolution for arbitrary ref fields.
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any

from bson import ObjectId

from analytiq_data.common.tag_grid_filters import resolve_tag_filter_values_to_ids


def parse_dt(v: Any) -> datetime | None:
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


def as_list_value(v: Any) -> list[str]:
    if v is None:
        return []
    if isinstance(v, list):
        return [str(x) for x in v if str(x).strip()]
    s = str(v)
    if "," in s:
        return [p.strip() for p in s.split(",") if p.strip()]
    return [s.strip()] if s.strip() else []


def _oid_text_clause(field: str, op: str, sv: str) -> dict[str, Any] | None:
    """Build a $expr/$regexMatch clause for text operators on an ObjectId field."""
    if op in ("contains",):
        pattern = re.escape(sv)
    elif op in ("doesNotContain", "does not contain"):
        pattern = re.escape(sv)
    elif op in ("startsWith", "starts with"):
        pattern = f"^{re.escape(sv)}"
    elif op in ("endsWith", "ends with"):
        pattern = f"{re.escape(sv)}$"
    else:
        return None
    match_expr: dict[str, Any] = {
        "$regexMatch": {"input": {"$toString": f"${field}"}, "regex": pattern, "options": "i"}
    }
    if op in ("doesNotContain", "does not contain"):
        return {"$expr": {"$not": match_expr}}
    return {"$expr": match_expr}


async def build_filter_match(
    filter_model: dict | None,
    field_map: dict[str, str | None],
    *,
    db: Any,
    organization_id: str,
    datetime_fields: set[str] | None = None,
    tag_id_fields: set[str] | None = None,
    ref_name_fields: dict[str, str] | None = None,
    id_field: str | None = "_id",
    null_only_empty_fields: set[str] | None = None,
) -> dict[str, Any] | None:
    """
    Build a MongoDB match expression from an MUI DataGrid filterModel.

    Args:
        filter_model: MUI DataGrid filterModel dict (``{items, logicOperator}``).
        field_map: maps frontend column field name → MongoDB field name (``None`` to skip).
        db: async Motor database.
        organization_id: scopes tag/ref lookups.
        datetime_fields: mongo field names treated as datetimes.
        tag_id_fields: mongo fields that store lists of tag-ID strings; text operators
            resolve tag names → IDs before filtering.
        ref_name_fields: ``{mongo_field: collection_name}`` — like tag_id_fields but for
            arbitrary collections (e.g. ``{"schema_id": "schemas"}``).
        id_field: the mongo field that stores ObjectId values (typically ``"_id"``).
            Set to ``None`` to disable ObjectId handling entirely.
        null_only_empty_fields: fields where isEmpty should match ``null/$exists`` only
            (no empty-string check) — useful for optional datetime fields.

    Returns:
        A MongoDB query dict suitable for ``{"$match": ...}`` or ``None`` if no clauses.
    """
    if not filter_model or not isinstance(filter_model, dict):
        return None

    items = filter_model.get("items") or []
    logic = (filter_model.get("logicOperator") or "and").lower()
    datetime_fields = datetime_fields or set()
    tag_id_fields = tag_id_fields or set()
    ref_name_fields = ref_name_fields or {}
    null_only_empty_fields = null_only_empty_fields or set()

    clauses: list[dict[str, Any]] = []

    for item in items:
        if not isinstance(item, dict):
            continue
        field = item.get("field")
        op = item.get("operator") or item.get("operatorValue")
        value = item.get("value")
        if not field or not op:
            continue

        mf = field_map.get(str(field))
        if not mf:
            continue

        op = str(op)
        str_value = "" if value is None else str(value)

        # isEmpty / isNotEmpty
        if op in ("isEmpty", "is empty"):
            if mf == id_field:
                continue
            if mf in null_only_empty_fields:
                clauses.append({"$or": [{mf: None}, {mf: {"$exists": False}}]})
            else:
                clauses.append({"$or": [{mf: ""}, {mf: None}, {mf: {"$exists": False}}]})
            continue

        if op in ("isNotEmpty", "is not empty"):
            if mf == id_field:
                clauses.append({"$and": [{mf: {"$exists": True}}, {mf: {"$ne": None}}]})
            else:
                clauses.append({"$and": [{mf: {"$exists": True}}, {mf: {"$nin": ["", None]}}]})
            continue

        # isAnyOf
        if op in ("isAnyOf", "is any of"):
            values = as_list_value(value)
            if not values:
                continue
            if mf == id_field:
                oids = [ObjectId(x) for x in values if ObjectId.is_valid(str(x))]
                if not oids:
                    continue
                clauses.append({mf: {"$in": oids}})
            elif mf in tag_id_fields:
                tag_id_strs = await resolve_tag_filter_values_to_ids(db, organization_id, values)
                if not tag_id_strs:
                    clauses.append({"_id": {"$exists": False}})
                    continue
                clauses.append({mf: {"$in": tag_id_strs}})
            else:
                clauses.append({mf: {"$in": values}})
            continue

        # Datetime fields
        if mf in datetime_fields:
            dt = parse_dt(value)
            if op in ("is", "equals") and dt:
                clauses.append({mf: dt})
            elif op in ("not", "doesNotEqual", "does not equal") and dt:
                clauses.append({mf: {"$ne": dt}})
            elif op == "after" and dt:
                clauses.append({mf: {"$gt": dt}})
            elif op in ("onOrAfter", "on or after") and dt:
                clauses.append({mf: {"$gte": dt}})
            elif op == "before" and dt:
                clauses.append({mf: {"$lt": dt}})
            elif op in ("onOrBefore", "on or before") and dt:
                clauses.append({mf: {"$lte": dt}})
            continue

        # tag_ids fields — text operators resolve tag names → IDs
        if mf in tag_id_fields and str_value.strip():
            neg = op in ("doesNotContain", "does not contain", "doesNotEqual", "does not equal")
            if op in ("equals", "=", "is", "doesNotEqual", "does not equal"):
                name_q: dict[str, Any] = {"$regex": f"^{re.escape(str_value)}$", "$options": "i"}
            elif op == "contains" or op in ("doesNotContain", "does not contain"):
                name_q = {"$regex": re.escape(str_value), "$options": "i"}
            elif op in ("startsWith", "starts with"):
                name_q = {"$regex": f"^{re.escape(str_value)}", "$options": "i"}
            elif op in ("endsWith", "ends with"):
                name_q = {"$regex": f"{re.escape(str_value)}$", "$options": "i"}
            else:
                continue

            tag_docs = await db["tags"].find(
                {"organization_id": organization_id, "name": name_q},
                {"_id": 1},
            ).limit(200).to_list(length=200)
            tag_id_strs = [str(t["_id"]) for t in tag_docs]

            if not tag_id_strs:
                if not neg:
                    clauses.append({"_id": {"$exists": False}})
                continue

            clauses.append({mf: {"$nin" if neg else "$in": tag_id_strs}})
            continue

        # ref_name fields — text operators resolve display names → IDs in another collection
        if mf in ref_name_fields and str_value.strip():
            coll = ref_name_fields[mf]
            neg = op in ("doesNotContain", "does not contain", "doesNotEqual", "does not equal")

            # Valid ObjectId value + equality op: match the raw ID string directly
            if ObjectId.is_valid(str_value) and op in ("equals", "doesNotEqual", "does not equal"):
                oid_str = str(ObjectId(str_value))
                doc = await db[coll].find_one(
                    {"_id": ObjectId(str_value), "organization_id": organization_id},
                    {"_id": 1},
                )
                if op == "equals":
                    clauses.append({mf: oid_str} if doc else {"_id": {"$exists": False}})
                elif doc:
                    clauses.append({mf: {"$ne": oid_str}})
                continue

            if op in ("equals", "doesNotEqual", "does not equal"):
                name_q = {"$regex": f"^{re.escape(str_value)}$", "$options": "i"}
            elif op == "contains" or op in ("doesNotContain", "does not contain"):
                name_q = {"$regex": re.escape(str_value), "$options": "i"}
            elif op in ("startsWith", "starts with"):
                name_q = {"$regex": f"^{re.escape(str_value)}", "$options": "i"}
            elif op in ("endsWith", "ends with"):
                name_q = {"$regex": f"{re.escape(str_value)}$", "$options": "i"}
            else:
                continue

            ref_docs = await db[coll].find(
                {"organization_id": organization_id, "name": name_q},
                {"_id": 1},
            ).limit(200).to_list(length=200)
            ref_id_strs = [str(d["_id"]) for d in ref_docs]

            if not ref_id_strs:
                if not neg:
                    clauses.append({"_id": {"$exists": False}})
                continue

            clauses.append({mf: {"$nin" if neg else "$in": ref_id_strs}})
            continue

        # ObjectId identity field (_id or aliased)
        if id_field and mf == id_field:
            sv = str_value.strip()
            if op in ("equals", "=", "is") and ObjectId.is_valid(sv):
                clauses.append({mf: ObjectId(sv)})
                continue
            if op in ("doesNotEqual", "does not equal", "!=") and ObjectId.is_valid(sv):
                clauses.append({mf: {"$ne": ObjectId(sv)}})
                continue
            if sv:
                clause = _oid_text_clause(mf, op, sv)
                if clause:
                    clauses.append(clause)
            continue

        # Generic string operators
        if op == "contains":
            if str_value.strip():
                clauses.append({mf: {"$regex": re.escape(str_value), "$options": "i"}})
        elif op in ("doesNotContain", "does not contain"):
            if str_value.strip():
                clauses.append({mf: {"$not": {"$regex": re.escape(str_value), "$options": "i"}}})
        elif op in ("equals", "=", "is"):
            clauses.append({mf: str_value})
        elif op in ("doesNotEqual", "does not equal", "!="):
            clauses.append({mf: {"$ne": str_value}})
        elif op in ("startsWith", "starts with"):
            if str_value.strip():
                clauses.append({mf: {"$regex": f"^{re.escape(str_value)}", "$options": "i"}})
        elif op in ("endsWith", "ends with"):
            if str_value.strip():
                clauses.append({mf: {"$regex": f"{re.escape(str_value)}$", "$options": "i"}})

    if not clauses:
        return None
    if logic == "or":
        return {"$or": clauses} if len(clauses) > 1 else clauses[0]
    return {"$and": clauses} if len(clauses) > 1 else clauses[0]


def build_sort_doc(
    sort_model: list | None,
    field_map: dict[str, str | None],
    default_tiebreaker: str = "_id",
) -> dict[str, int]:
    """Return a MongoDB sort dict for aggregation ``$sort`` stages."""
    sort_doc: dict[str, int] = {}
    if sort_model:
        for item in sort_model:
            if not isinstance(item, dict):
                continue
            mf = field_map.get(str(item.get("field", "")))
            if not mf:
                continue
            sort_doc[mf] = -1 if str(item.get("sort", "")).lower() == "desc" else 1
    if not sort_doc:
        sort_doc[default_tiebreaker] = -1
    elif default_tiebreaker not in sort_doc:
        sort_doc[default_tiebreaker] = -1
    return sort_doc


def build_sort_spec(
    sort_model: list | None,
    field_map: dict[str, str | None],
    default_sort: list[tuple[str, int]] | None = None,
    tiebreaker: str | None = "_id",
) -> list[tuple[str, int]]:
    """Return a list-of-tuples sort spec for Motor ``cursor.sort()``."""
    spec: list[tuple[str, int]] = []
    if sort_model:
        for item in sort_model:
            if not isinstance(item, dict):
                continue
            mf = field_map.get(str(item.get("field", "")))
            if not mf:
                continue
            direction = 1 if str(item.get("sort", "")).lower() == "asc" else -1
            spec.append((mf, direction))
    if not spec:
        return default_sort if default_sort is not None else [(tiebreaker or "_id", -1)]
    if tiebreaker and not any(f == tiebreaker for f, _ in spec):
        spec.append((tiebreaker, -1))
    return spec
