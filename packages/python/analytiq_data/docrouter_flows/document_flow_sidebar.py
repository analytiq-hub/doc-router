from __future__ import annotations

"""Document-scoped flow listing and captured result lookup."""

import logging
from datetime import UTC, datetime
from typing import Any

from bson import ObjectId

import analytiq_data as ad

from .event_dispatch import (
    DOCROUTER_TRIGGER_TYPE,
    build_docrouter_event_flow_item,
    build_docrouter_event_payload,
    enqueue_docrouter_event_flow_run,
    tag_filter_matches_document,
)
from .event_types import DOCROUTER_LLM_EVENT_TYPES
from .flow_results import FLOW_RESULTS_COLLECTION

logger = logging.getLogger(__name__)


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
    flow_version: int | None = None
    if execution_id and ObjectId.is_valid(execution_id):
        exec_doc = await db.flow_executions.find_one(
            {"_id": ObjectId(execution_id), "flow_id": resolved_flow_id},
            {"flow_revid": 1},
        )
        if exec_doc and exec_doc.get("flow_revid"):
            result_flow_revid = str(exec_doc["flow_revid"])
    if result_flow_revid and ObjectId.is_valid(result_flow_revid):
        rev_doc = await db.flow_revisions.find_one(
            {"_id": ObjectId(result_flow_revid), "flow_id": resolved_flow_id},
            {"flow_version": 1},
        )
        if rev_doc is not None:
            flow_version = int(rev_doc.get("flow_version") or 0)

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
        "flow_version": flow_version,
        "document_id": document_id,
        "execution_id": execution_id,
        "event_type": event_type,
        "result": result_dict,
        "created_at": created_at,
        "updated_at": updated_at,
    }


async def _latest_llm_context_for_flow_rerun(
    db,
    *,
    org_id: str,
    document_id: str,
    prompt_id: str | None,
) -> tuple[str | None, str | None, str | None, Any]:
    """Best-effort LLM fields for re-dispatching ``llm.completed`` / ``llm.error`` flows."""

    pid = (prompt_id or "").strip()
    if not pid:
        return None, None, None, None
    run = await db.llm_runs.find_one(
        {"document_id": document_id, "prompt_id": pid},
        sort=[("_id", -1)],
    )
    if not run:
        return pid, None, None, None
    prompt_revid = str(run.get("prompt_revid") or "") or None
    llm_run_id = str(run.get("_id") or "") or None
    trigger_llm_result = run.get("result")
    return pid, prompt_revid, llm_run_id, trigger_llm_result


async def rerun_flow_for_document(
    analytiq_client,
    *,
    org_id: str,
    document_id: str,
    flow_id: str,
    mode: str = "force",
) -> str:
    """
    Re-enqueue a document-event flow for ``document_id`` using the active revision.

    ``mode`` is ``force`` (new run) or ``incomplete_only`` (resume latest partial batch run
    when possible on the active revision; otherwise starts a force rerun).

    Returns the new ``execution_id``.
    """

    db = analytiq_client.mongodb_async[analytiq_client.env]
    doc = await ad.common.doc.get_doc(analytiq_client, document_id)
    if not doc:
        raise ValueError("Document not found")
    if doc.get("organization_id") != org_id:
        raise ValueError("Document not found")

    hdr = await _load_flow_header(db, org_id=org_id, flow_id=flow_id)
    if not hdr:
        raise ValueError("Flow not found")
    if not hdr.get("active"):
        raise ValueError("Flow is not active")

    flow_revid = str(hdr.get("active_flow_revid") or "")
    if not flow_revid or not ObjectId.is_valid(flow_revid):
        raise ValueError("Flow has no active revision")

    if mode == "incomplete_only":
        from analytiq_data.flows.resume import enqueue_resume_execution, find_resumable_batch_execution

        source = await find_resumable_batch_execution(
            db,
            organization_id=org_id,
            flow_id=flow_id,
            document_id=document_id,
        )
        if source and str(source.get("flow_revid") or "") == flow_revid:
            exec_id = await enqueue_resume_execution(analytiq_client, db, source)
            if exec_id:
                return exec_id
        if source is None:
            resume_reason = "no partial execution"
        elif str(source.get("flow_revid") or "") != flow_revid:
            resume_reason = "revision changed"
        else:
            resume_reason = "resume enqueue failed"
        logger.info(
            f"incomplete_only resume unavailable for flow {flow_id} document {document_id} "
            f"({resume_reason}), starting force rerun"
        )

    revision = await db.flow_revisions.find_one({"_id": ObjectId(flow_revid), "flow_id": flow_id})
    if not revision:
        raise ValueError("Flow revision not found")

    doc_tag_ids = await _load_document_tag_ids(db, org_id=org_id, document_id=document_id)
    event_type = _event_type_from_revision(revision, doc_tag_ids)
    if event_type is None:
        raise ValueError("Flow does not match document")

    trigger_node_id: str | None = None
    report_result = True
    prompt_id: str | None = None
    for node in revision.get("nodes") or []:
        if node.get("disabled"):
            continue
        if (node.get("type") or "") != DOCROUTER_TRIGGER_TYPE:
            continue
        params = node.get("parameters") or {}
        configured_tags = _normalized_tag_ids(params.get("tag_ids"))
        if not tag_filter_matches_document(configured_tags, doc_tag_ids):
            continue
        node_event = params.get("event_type")
        if node_event != event_type:
            continue
        trigger_node_id = str(node.get("id") or "")
        report_result = bool(params.get("report_result", True))
        raw_prompt = params.get("prompt_id")
        prompt_id = raw_prompt.strip() if isinstance(raw_prompt, str) and raw_prompt.strip() else None
        break

    if not trigger_node_id:
        raise ValueError("Trigger node not found")

    prompt_revid: str | None = None
    llm_run_id: str | None = None
    trigger_llm_result: Any = None
    error_message: str | None = None
    error_code: str | None = None
    if event_type in DOCROUTER_LLM_EVENT_TYPES:
        pid, prompt_revid, llm_run_id, trigger_llm_result = await _latest_llm_context_for_flow_rerun(
            db,
            org_id=org_id,
            document_id=document_id,
            prompt_id=prompt_id,
        )
        prompt_id = pid
        if event_type == "llm.error" and isinstance(trigger_llm_result, dict):
            error_message = str(trigger_llm_result.get("error_message") or trigger_llm_result.get("message") or "")
            error_code = str(trigger_llm_result.get("error_code") or "") or None

    payload = await build_docrouter_event_payload(
        analytiq_client,
        event_type=event_type,
        doc=doc,
        prompt_id=prompt_id,
        prompt_revid=prompt_revid,
        llm_run_id=llm_run_id,
        trigger_llm_result=trigger_llm_result,
        error_message=error_message,
        error_code=error_code,
    )
    item = build_docrouter_event_flow_item(payload, doc, source_node_id=trigger_node_id)
    return await enqueue_docrouter_event_flow_run(
        analytiq_client,
        organization_id=org_id,
        flow_id=flow_id,
        flow_revid=flow_revid,
        trigger_node_id=trigger_node_id,
        payload=payload,
        item=item,
        report_result=report_result,
    )
