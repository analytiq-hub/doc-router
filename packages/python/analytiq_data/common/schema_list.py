"""
Server-side list for schemas: latest revision per schema_id, optional MUI grid sort/filter.
"""

from __future__ import annotations

from typing import Any

from analytiq_data.common.grid_filter import build_filter_match, build_sort_doc

_FIELD_MAP: dict[str, str | None] = {
    "name": "name",
    "created_at": "created_at",
    "created_by": "created_by",
    "schema_id": "schema_id",
    "schema_revid": "_id",
    # "schema_version" and "fields" intentionally absent → skipped
}

_DATETIME_FIELDS = {"created_at"}


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

    grid_match = await build_filter_match(
        filter_model, _FIELD_MAP,
        db=db, organization_id=organization_id,
        datetime_fields=_DATETIME_FIELDS,
    )
    if grid_match:
        pipeline.append({"$match": grid_match})

    pipeline.append({"$sort": build_sort_doc(sort_model, _FIELD_MAP)})
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
