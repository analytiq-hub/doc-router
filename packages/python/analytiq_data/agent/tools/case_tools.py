"""Case tools for the agent (org-scoped case collation)."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

import analytiq_data as ad


def _parse_optional_iso_datetime(value: Any) -> datetime | None:
    if value is None:
        return None
    s = str(value).strip()
    if not s:
        return None
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    dt = datetime.fromisoformat(s)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt


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


def _parse_grid_json(params: dict, key: str) -> tuple[Any | None, dict[str, Any] | None]:
    raw = params.get(key)
    if raw is None or raw == "":
        return None, None
    if isinstance(raw, (dict, list)):
        return raw, None
    if isinstance(raw, str):
        try:
            return json.loads(raw), None
        except json.JSONDecodeError:
            return None, {"error": f"Invalid {key} JSON"}
    return None, {"error": f"Invalid {key}"}


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

    sort_model, err = _parse_grid_json(params, "sort")
    if err:
        return err
    filter_model, err = _parse_grid_json(params, "filters")
    if err:
        return err

    try:
        updated_after = _parse_optional_iso_datetime(params.get("updated_after"))
        updated_before = _parse_optional_iso_datetime(params.get("updated_before"))
    except ValueError as e:
        return {"error": f"Invalid datetime: {e}"}

    aq = context["analytiq_client"]
    cases, total = await ad.common.list_cases(
        aq,
        org_id,
        skip=skip,
        limit=limit,
        case_id_search=case_search,
        tag_ids=tag_ids,
        metadata_search=metadata_search,
        updated_after=updated_after,
        updated_before=updated_before,
        sort_model=sort_model,
        filter_model=filter_model,
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
    row = await ad.common.get_case(aq, org_id, str(case_id))
    if not row:
        return {"error": "Case not found"}
    count = await ad.common.count_documents_in_case(aq, org_id, str(case_id))
    return _case_to_dict(row, count)


async def create_case(context: dict, params: dict) -> dict[str, Any]:
    org_id = context.get("organization_id")
    if not org_id:
        return {"error": "No organization context"}
    user_id = context.get("user_id") or context.get("created_by") or "agent"
    case_id = params.get("case_id")
    display_name = params.get("display_name")
    tag_ids = params.get("tag_ids")
    metadata = params.get("metadata")
    if tag_ids is not None and not isinstance(tag_ids, list):
        return {"error": "tag_ids must be a list"}
    if metadata is not None and not isinstance(metadata, dict):
        return {"error": "metadata must be an object"}
    try:
        row = await ad.common.create_case(
            context["analytiq_client"],
            org_id,
            case_id=str(case_id).strip() if case_id else None,
            display_name=display_name,
            tag_ids=tag_ids,
            metadata=metadata,
            created_by=user_id,
        )
    except ValueError as e:
        return {"error": str(e)}
    return _case_to_dict(row, 0)


async def update_case(context: dict, params: dict) -> dict[str, Any]:
    org_id = context.get("organization_id")
    if not org_id:
        return {"error": "No organization context"}
    case_id = params.get("case_id")
    if not case_id:
        return {"error": "case_id is required"}
    display_name = params.get("display_name")
    tag_ids = params.get("tag_ids")
    metadata = params.get("metadata")
    if tag_ids is not None and not isinstance(tag_ids, list):
        return {"error": "tag_ids must be a list"}
    if metadata is not None and not isinstance(metadata, dict):
        return {"error": "metadata must be an object"}
    try:
        updated = await ad.common.update_case(
            context["analytiq_client"],
            org_id,
            str(case_id),
            display_name=display_name,
            tag_ids=tag_ids,
            metadata=metadata,
        )
    except ValueError as e:
        return {"error": str(e)}
    if not updated:
        return {"error": "Case not found"}
    count = await ad.common.count_documents_in_case(
        context["analytiq_client"], org_id, str(case_id)
    )
    return _case_to_dict(updated, count)


async def delete_case(context: dict, params: dict) -> dict[str, Any]:
    org_id = context.get("organization_id")
    if not org_id:
        return {"error": "No organization context"}
    case_id = params.get("case_id")
    if not case_id:
        return {"error": "case_id is required"}
    cascade = bool(params.get("cascade", False))
    try:
        ad.common.validate_case_id(str(case_id))
    except ValueError as e:
        return {"error": str(e)}
    try:
        deleted = await ad.common.delete_case(
            context["analytiq_client"],
            org_id,
            str(case_id),
            cascade_documents=cascade,
        )
    except ValueError as e:
        return {"error": str(e)}
    if not deleted:
        return {"error": "Case not found"}
    return {
        "message": "Case deleted",
        "case_id": str(case_id),
        "cascade_documents": cascade,
    }


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
