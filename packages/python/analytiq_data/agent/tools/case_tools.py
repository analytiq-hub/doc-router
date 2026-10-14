"""Case tools for the agent (org-scoped case collation)."""

from __future__ import annotations

from typing import Any

import analytiq_data as ad


def _case_to_dict(case: dict, document_count: int = 0) -> dict[str, Any]:
    created = case.get("created_at")
    updated = case.get("updated_at")
    if hasattr(created, "isoformat"):
        created = created.isoformat()
    if hasattr(updated, "isoformat"):
        updated = updated.isoformat()
    return {
        "case_id": case["case_id"],
        "display_name": case.get("display_name") or case["case_id"],
        "tag_ids": case.get("tag_ids") or [],
        "metadata": case.get("metadata") or {},
        "document_count": document_count,
        "created_by": case.get("created_by", ""),
        "created_at": created,
        "updated_at": updated,
    }


async def list_cases(context: dict, params: dict) -> dict[str, Any]:
    org_id = context.get("organization_id")
    if not org_id:
        return {"error": "No organization context"}
    skip = int(params.get("skip", 0))
    limit = min(max(int(params.get("limit", 10)), 1), 200)
    case_search = params.get("case_id_search") or params.get("search")
    tag_ids = params.get("tag_ids")
    if isinstance(tag_ids, str):
        tag_ids = [t.strip() for t in tag_ids.split(",") if t.strip()]
    metadata_search = params.get("metadata_search")
    if isinstance(metadata_search, dict):
        pass
    elif isinstance(metadata_search, str) and metadata_search.strip():
        metadata_search = {}
        for pair in metadata_search.split(","):
            pair = pair.strip()
            if "=" in pair:
                k, v = pair.split("=", 1)
                metadata_search[k.strip()] = v.strip()
    else:
        metadata_search = None

    aq = context["analytiq_client"]
    cases, total = await ad.common.list_cases(
        aq,
        org_id,
        skip=skip,
        limit=limit,
        case_id_search=case_search,
        tag_ids=tag_ids,
        metadata_search=metadata_search,
    )
    counts = await ad.common.count_documents_in_cases(
        aq, org_id, [c["case_id"] for c in cases]
    )
    return {
        "cases": [_case_to_dict(c, counts.get(c["case_id"], 0)) for c in cases],
        "total_count": total,
        "skip": skip,
    }


async def get_case(context: dict, params: dict) -> dict[str, Any]:
    org_id = context.get("organization_id")
    if not org_id:
        return {"error": "No organization context"}
    case_id = params.get("case_id")
    if not case_id:
        return {"error": "case_id is required"}
    try:
        ad.common.validate_case_id(str(case_id))
    except ValueError as e:
        return {"error": str(e)}
    aq = context["analytiq_client"]
    db = ad.common.get_async_db(aq)
    row = await db.cases.find_one(
        {"organization_id": org_id, "case_id": case_id, "deleting_at": None}
    )
    if not row:
        return {"error": "Case not found"}
    count = await ad.common.count_documents_in_case(aq, org_id, case_id)
    return _case_to_dict(row, count)


async def assign_documents_to_case(context: dict, params: dict) -> dict[str, Any]:
    org_id = context.get("organization_id")
    if not org_id:
        return {"error": "No organization context"}
    case_id = params.get("case_id")
    document_ids = params.get("document_ids")
    if not case_id:
        return {"error": "case_id is required"}
    if not document_ids or not isinstance(document_ids, list):
        return {"error": "document_ids must be a non-empty list"}
    create_if_missing = bool(params.get("create_case_if_missing", False))
    user_id = context.get("user_id") or ""
    try:
        await ad.common.assign_documents_to_case(
            context["analytiq_client"],
            org_id,
            [str(d) for d in document_ids],
            str(case_id),
            create_case_if_missing=create_if_missing,
            created_by=user_id,
        )
    except (ValueError, LookupError) as e:
        return {"error": str(e)}
    return {"message": "Documents assigned", "count": len(set(document_ids))}
