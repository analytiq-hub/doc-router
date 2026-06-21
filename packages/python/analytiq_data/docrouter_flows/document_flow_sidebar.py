from __future__ import annotations

"""Document-scoped flow listing and captured result lookup."""

from datetime import UTC, datetime
from typing import Any

from bson import ObjectId

from .event_dispatch import DOCROUTER_TRIGGER_TYPE, tag_filter_matches_document
from .flow_results import FLOW_RESULTS_COLLECTION


def _normalized_tag_ids(raw: Any) -> list[str]:
    if not isinstance(raw, list):
        return []
    out: list[str] = []
    for t in raw:
        if isinstance(t, str):
            s = t.strip()
        elif t is not None:
            s = str(t).strip()
        else:
            continue
        if s:
            out.append(s)
    return out


def _event_type_from_revision(revision: dict[str, Any], doc_tag_ids: set[str]) -> str | None:
    for node in revision.get("nodes") or []:
        if node.get("disabled"):
            continue
        if (node.get("type") or "") != DOCROUTER_TRIGGER_TYPE:
            continue
        params = node.get("parameters") or {}
        configured_tags = _normalized_tag_ids(params.get("tag_ids"))
        if not tag_filter_matches_document(configured_tags, doc_tag_ids):
            continue
        raw_event = params.get("event_type")
        return raw_event if isinstance(raw_event, str) else None
    return None


async def _load_document_tag_ids(db, *, org_id: str, document_id: str) -> set[str]:
    document = await db.docs.find_one(
        {"_id": ObjectId(document_id), "organization_id": org_id},
        {"tag_ids": 1},
    )
    if not document:
        raise ValueError("Document not found")
    return {str(t) for t in (document.get("tag_ids") or [])}


async def _load_flow_header(db, *, org_id: str, flow_id: str) -> dict[str, Any] | None:
    return await db.flows.find_one({"_id": ObjectId(flow_id), "organization_id": org_id})


async def _resolve_flow_id_from_revid(db, *, org_id: str, flow_revid: str) -> str | None:
    if not ObjectId.is_valid(flow_revid):
        return None
    rev = await db.flow_revisions.find_one({"_id": ObjectId(flow_revid)}, {"flow_id": 1})
    if not rev:
        return None
    flow_id = str(rev.get("flow_id") or "")
    if not flow_id:
        return None
    hdr = await _load_flow_header(db, org_id=org_id, flow_id=flow_id)
    return flow_id if hdr else None


async def _revision_for_match(
    db,
    hdr: dict[str, Any],
    *,
    flow_revid: str | None = None,
) -> dict[str, Any] | None:
    flow_id = str(hdr["_id"])
    if flow_revid:
        if not ObjectId.is_valid(flow_revid):
            return None
        return await db.flow_revisions.find_one({"_id": ObjectId(flow_revid), "flow_id": flow_id})
    if hdr.get("active") and hdr.get("active_flow_revid"):
        active_revid = str(hdr["active_flow_revid"])
        if ObjectId.is_valid(active_revid):
            rev = await db.flow_revisions.find_one({"_id": ObjectId(active_revid), "flow_id": flow_id})
            if rev:
                return rev
    return await db.flow_revisions.find_one({"flow_id": flow_id}, sort=[("flow_version", -1)])


def _flow_list_item(
    hdr: dict[str, Any],
    revision: dict[str, Any] | None,
    *,
    event_type: str | None,
    has_captured_result: bool,
) -> dict[str, Any]:
    fid = str(hdr["_id"])
    latest = revision
    created_at = hdr["created_at"]
    updated_at = hdr["updated_at"]
    return {
        "flow": {
            "flow_id": fid,
            "organization_id": hdr["organization_id"],
            "name": hdr["name"],
            "active": bool(hdr.get("active")),
            "active_flow_revid": hdr.get("active_flow_revid"),
            "flow_version": int(hdr.get("flow_version") or 0),
            "created_at": created_at.replace(tzinfo=UTC).isoformat()
            if isinstance(created_at, datetime)
            else created_at,
            "created_by": hdr["created_by"],
            "updated_at": updated_at.replace(tzinfo=UTC).isoformat()
            if isinstance(updated_at, datetime)
            else updated_at,
            "updated_by": hdr["updated_by"],
        },
        "latest_revision": None
        if not latest
        else {
            "flow_revid": str(latest["_id"]),
            "flow_version": latest["flow_version"],
            "graph_hash": latest.get("graph_hash"),
        },
        "event_type": event_type,
        "has_captured_result": has_captured_result,
    }


async def list_matching_flows_for_document(
    db,
    *,
    org_id: str,
    document_id: str,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[dict[str, Any]], int]:
    """Flows whose document-event trigger matches ``document_id`` (ListFlowsResponse item shape)."""

    doc_tag_ids = await _load_document_tag_ids(db, org_id=org_id, document_id=document_id)

    result_rows = await db[FLOW_RESULTS_COLLECTION].find(
        {"org_id": org_id, "document_id": document_id}
    ).to_list(length=None)
    results_by_flow = {str(r.get("flow_id") or "") for r in result_rows if r.get("flow_id")}

    headers = await db.flows.find({"organization_id": org_id}).sort("updated_at", -1).to_list(length=None)

    matched: list[dict[str, Any]] = []
    for hdr in headers:
        flow_id = str(hdr["_id"])
        revision = await _revision_for_match(db, hdr)
        if not revision:
            continue
        event_type = _event_type_from_revision(revision, doc_tag_ids)
        if event_type is None:
            continue
        matched.append(
            _flow_list_item(
                hdr,
                revision,
                event_type=event_type,
                has_captured_result=flow_id in results_by_flow,
            )
        )

    total = len(matched)
    page = matched[offset : offset + limit]
    return page, total


async def get_document_flow_result(
    db,
    *,
    org_id: str,
    document_id: str,
    flow_id: str | None = None,
    flow_revid: str | None = None,
) -> dict[str, Any]:
    """
    Captured flow output for ``document_id`` + ``flow_id``.

    ``flow_revid`` optionally selects which revision to use for trigger tag matching
    (defaults to active revision when flow is active, else latest saved).
    """

    await _load_document_tag_ids(db, org_id=org_id, document_id=document_id)

    resolved_flow_id = (flow_id or "").strip()
    if not resolved_flow_id and flow_revid:
        resolved = await _resolve_flow_id_from_revid(db, org_id=org_id, flow_revid=flow_revid.strip())
        if not resolved:
            raise ValueError("Flow revision not found")
        resolved_flow_id = resolved
    if not resolved_flow_id:
        raise ValueError("flow_id or flow_revid is required")

    hdr = await _load_flow_header(db, org_id=org_id, flow_id=resolved_flow_id)
    if not hdr:
        raise ValueError("Flow not found")

    doc_tag_ids = await _load_document_tag_ids(db, org_id=org_id, document_id=document_id)
    revision = await _revision_for_match(db, hdr, flow_revid=flow_revid.strip() if flow_revid else None)
    if not revision:
        raise ValueError("Flow revision not found")
    event_type = _event_type_from_revision(revision, doc_tag_ids)
    if event_type is None:
        raise ValueError("Flow does not match document")

    result_row = await db[FLOW_RESULTS_COLLECTION].find_one(
        {"org_id": org_id, "document_id": document_id, "flow_id": resolved_flow_id}
    )
    if not result_row:
        raise ValueError("Flow result not found")

    execution_id = str(result_row.get("execution_id") or "")
    result_flow_revid: str | None = None
    if execution_id and ObjectId.is_valid(execution_id):
        exec_doc = await db.flow_executions.find_one(
            {"_id": ObjectId(execution_id), "flow_id": resolved_flow_id},
            {"flow_revid": 1},
        )
        if exec_doc and exec_doc.get("flow_revid"):
            result_flow_revid = str(exec_doc["flow_revid"])

    raw_result = result_row.get("result")
    result_dict = dict(raw_result) if isinstance(raw_result, dict) else {}
    created = result_row.get("created_at")
    updated = result_row.get("updated_at") or created
    created_at = None
    updated_at = None
    if isinstance(created, datetime):
        created_at = created.replace(tzinfo=UTC) if created.tzinfo is None else created.astimezone(UTC)
    if isinstance(updated, datetime):
        updated_at = updated.replace(tzinfo=UTC) if updated.tzinfo is None else updated.astimezone(UTC)

    return {
        "flow_id": resolved_flow_id,
        "flow_name": str(hdr.get("name") or "Flow"),
        "flow_revid": result_flow_revid,
        "document_id": document_id,
        "execution_id": execution_id,
        "event_type": event_type,
        "result": result_dict,
        "created_at": created_at,
        "updated_at": updated_at,
    }
