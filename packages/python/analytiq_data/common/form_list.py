"""
Server-side list for forms: latest ``form_revisions`` row per ``form_id`` for an org,
with optional MUI grid sort/filter. ``form_version`` and ``actions`` are not sortable/filterable.
"""

from __future__ import annotations

from typing import Any

from analytiq_data.common.grid_filter import build_filter_match, build_sort_doc

_FIELD_MAP: dict[str, str | None] = {
    "name": "name",
    "form_id": "form_id",
    "tag_ids": "tag_ids",
    "created_at": "created_at",
    "created_by": "created_by",
    "form_revid": "_id",
    # "form_version" and "actions" intentionally absent → skipped
}

_DATETIME_FIELDS = {"created_at"}
_TAG_ID_FIELDS = {"tag_ids"}


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

    grid_match = await build_filter_match(
        filter_model, _FIELD_MAP,
        db=db, organization_id=organization_id,
        datetime_fields=_DATETIME_FIELDS,
        tag_id_fields=_TAG_ID_FIELDS,
    )
    if grid_match:
        pipeline.append({"$match": grid_match})

    pipeline.append({"$sort": build_sort_doc(sort_model, _FIELD_MAP)})
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
