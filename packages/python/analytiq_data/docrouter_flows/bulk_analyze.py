"""
Bulk analysis of which document-flow pairs need event-trigger flow re-runs.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Literal

from bson import ObjectId

from analytiq_data.common.doc import list_all_matching_docs
from analytiq_data.docrouter_flows.event_dispatch import (
    DOCROUTER_TRIGGER_TYPE,
    FLOW_TRIGGERS_COLLECTION,
    tag_filter_matches_document,
)
from analytiq_data.docrouter_flows.flow_results import FLOW_RESULTS_COLLECTION

logger = logging.getLogger(__name__)

ExecutionMode = Literal["all", "missing", "outdated"]
RunReason = Literal["missing", "outdated", "forced"]


@dataclass(frozen=True)
class FlowTriggerInfo:
    flow_id: str
    flow_name: str
    active_version: int
    event_type: str | None
    revision: dict[str, Any]


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


def _matching_trigger_for_document(
    revision: dict[str, Any],
    doc_tag_ids: set[str],
    *,
    anchor_tag_id: str | None = None,
) -> dict[str, Any] | None:
    """First non-disabled docrouter.trigger matching document tags (sidebar rule)."""
    for node in revision.get("nodes") or []:
        if node.get("disabled"):
            continue
        if (node.get("type") or "") != DOCROUTER_TRIGGER_TYPE:
            continue
        params = node.get("parameters") or {}
        if params.get("report_result", True) is False:
            continue
        configured_tags = _normalized_tag_ids(params.get("tag_ids"))
        if anchor_tag_id and anchor_tag_id not in configured_tags:
            continue
        if not tag_filter_matches_document(configured_tags, doc_tag_ids):
            continue
        event_type = params.get("event_type")
        return {
            "tag_ids": configured_tags,
            "event_type": event_type if isinstance(event_type, str) else None,
        }
    return None


def flow_pair_needs_run(
    mode: ExecutionMode,
    *,
    has_result: bool,
    stored_version: int | None,
    active_version: int,
) -> tuple[bool, RunReason | None]:
    """Mirror Bulk LLM ``_needs_execution``: ``outdated`` includes missing pairs."""
    if mode == "all":
        return True, "forced"
    if not has_result:
        if mode in ("missing", "outdated"):
            return True, "missing"
        return False, None
    if mode == "missing":
        return False, None
    if stored_version is None or stored_version < active_version:
        return True, "outdated"
    return False, None


async def discover_event_flows_for_tag(db: Any, org_id: str, tag_id: str) -> list[str]:
    """Active flows with a flow_triggers row whose tag_ids contain tag_id."""
    rows = await db[FLOW_TRIGGERS_COLLECTION].find(
        {
            "org_id": org_id,
            "tag_ids": tag_id,
            "report_result": {"$ne": False},
        },
        {"flow_id": 1},
    ).to_list(length=None)
    flow_ids = list({str(r["flow_id"]) for r in rows if r.get("flow_id")})
    if not flow_ids:
        return []

    oids = [ObjectId(fid) for fid in flow_ids if ObjectId.is_valid(fid)]
    if not oids:
        return []

    headers = await db.flows.find(
        {
            "_id": {"$in": oids},
            "organization_id": org_id,
            "active": True,
            "active_flow_revid": {"$exists": True, "$nin": ["", None]},
        },
        {"_id": 1},
    ).to_list(length=None)
    return [str(h["_id"]) for h in headers]


async def _load_active_flow_headers(
    db: Any,
    org_id: str,
    flow_ids: list[str],
) -> dict[str, dict[str, Any]]:
    oids = [ObjectId(fid) for fid in flow_ids if ObjectId.is_valid(fid)]
    if not oids:
        return {}
    rows = await db.flows.find(
        {
            "_id": {"$in": oids},
            "organization_id": org_id,
            "active": True,
            "active_flow_revid": {"$exists": True, "$nin": ["", None]},
        }
    ).to_list(length=None)
    out: dict[str, dict[str, Any]] = {}
    for row in rows:
        active_revid = str(row.get("active_flow_revid") or "")
        if not ObjectId.is_valid(active_revid):
            continue
        out[str(row["_id"])] = row
    return out


async def get_active_flow_trigger_info(
    db: Any,
    org_id: str,
    flow_id: str,
    hdr: dict[str, Any] | None = None,
) -> FlowTriggerInfo | None:
    if hdr is None:
        if not ObjectId.is_valid(flow_id):
            return None
        hdr = await db.flows.find_one(
            {"_id": ObjectId(flow_id), "organization_id": org_id, "active": True}
        )
    if not hdr or not hdr.get("active"):
        return None

    active_revid = str(hdr.get("active_flow_revid") or "")
    if not ObjectId.is_valid(active_revid):
        return None

    revision = await db.flow_revisions.find_one(
        {"_id": ObjectId(active_revid), "flow_id": flow_id}
    )
    if not revision:
        return None

    trigger_row = await db[FLOW_TRIGGERS_COLLECTION].find_one(
        {"flow_id": flow_id, "report_result": {"$ne": False}}
    )
    event_type = None
    if trigger_row:
        raw = trigger_row.get("trigger_type")
        event_type = raw if isinstance(raw, str) else None

    return FlowTriggerInfo(
        flow_id=flow_id,
        flow_name=str(hdr.get("name") or "Flow"),
        active_version=int(revision.get("flow_version") or 0),
        event_type=event_type,
        revision=revision,
    )


async def batch_flow_result_stored_versions(
    db: Any,
    execution_ids: list[str],
) -> dict[str, int]:
    """Map execution_id -> flow_version from the execution's revision."""
    valid_oids = [ObjectId(eid) for eid in execution_ids if ObjectId.is_valid(eid)]
    if not valid_oids:
        return {}

    exec_rows = await db.flow_executions.find(
        {"_id": {"$in": valid_oids}},
        {"flow_revid": 1},
    ).to_list(length=None)

    rev_ids: list[ObjectId] = []
    exec_to_revid: dict[str, str] = {}
    for row in exec_rows:
        exec_id = str(row["_id"])
        flow_revid = str(row.get("flow_revid") or "")
        if ObjectId.is_valid(flow_revid):
            exec_to_revid[exec_id] = flow_revid
            rev_ids.append(ObjectId(flow_revid))

    if not rev_ids:
        return {}

    rev_rows = await db.flow_revisions.find(
        {"_id": {"$in": rev_ids}},
        {"flow_version": 1},
    ).to_list(length=None)
    version_by_revid = {str(r["_id"]): int(r.get("flow_version") or 0) for r in rev_rows}

    out: dict[str, int] = {}
    for exec_id, rev_id in exec_to_revid.items():
        if rev_id in version_by_revid:
            out[exec_id] = version_by_revid[rev_id]
    return out


async def _batch_document_tag_ids(db: Any, doc_ids: list[str]) -> dict[str, set[str]]:
    oids = [ObjectId(d) for d in doc_ids if ObjectId.is_valid(d)]
    if not oids:
        return {}
    rows = await db.docs.find({"_id": {"$in": oids}}, {"tag_ids": 1}).to_list(length=None)
    return {
        str(row["_id"]): {str(t) for t in (row.get("tag_ids") or []) if t is not None}
        for row in rows
    }


def _resolve_candidate_flow_ids(
    *,
    tag_id: str | None,
    flow_ids: list[str],
    discovered: list[str],
) -> list[str]:
    if tag_id and flow_ids:
        discovered_set = set(discovered)
        return [fid for fid in flow_ids if fid in discovered_set]
    if flow_ids:
        return flow_ids
    return discovered


async def bulk_analyze_flow_executions(
    analytiq_client,
    organization_id: str,
    mode: ExecutionMode,
    *,
    tag_id: str | None = None,
    flow_ids: list[str] | None = None,
    tag_ids: list[str] | None = None,
    name_search: str | None = None,
    metadata_search: dict[str, str] | None = None,
    filter_model: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Determine which document-flow pairs need re-run for bulk Run Flows.

    Requires at least one of tag_id or non-empty flow_ids.
    """
    anchor_tag = (tag_id or "").strip() or None
    explicit_flow_ids = [f.strip() for f in (flow_ids or []) if isinstance(f, str) and f.strip()]
    if not anchor_tag and not explicit_flow_ids:
        raise ValueError("tag_id or flow_ids is required")

    db = analytiq_client.mongodb_async[analytiq_client.env]

    discovered: list[str] = []
    if anchor_tag:
        discovered = await discover_event_flows_for_tag(db, organization_id, anchor_tag)

    candidate_ids = _resolve_candidate_flow_ids(
        tag_id=anchor_tag,
        flow_ids=explicit_flow_ids,
        discovered=discovered,
    )
    if not candidate_ids:
        return {"total_executions": 0, "groups": []}

    headers_by_id = await _load_active_flow_headers(db, organization_id, candidate_ids)
    candidate_ids = list(headers_by_id.keys())
    if not candidate_ids:
        return {"total_executions": 0, "groups": []}

    doc_tag_filter = list(tag_ids or [])
    if anchor_tag and anchor_tag not in doc_tag_filter:
        doc_tag_filter.append(anchor_tag)

    documents = await list_all_matching_docs(
        analytiq_client,
        organization_id,
        tag_ids=doc_tag_filter or None,
        name_search=name_search,
        metadata_search=metadata_search,
        filter_model=filter_model,
    )
    if not documents:
        return {"total_executions": 0, "groups": []}

    doc_ids = [d["id"] for d in documents]
    doc_name_by_id = {d["id"]: d.get("document_name") or "" for d in documents}
    doc_tags_by_id = await _batch_document_tag_ids(db, doc_ids)

    flow_infos: dict[str, FlowTriggerInfo] = {}
    for fid in candidate_ids:
        info = await get_active_flow_trigger_info(
            db, organization_id, fid, hdr=headers_by_id.get(fid)
        )
        if info:
            flow_infos[fid] = info

    if not flow_infos:
        return {"total_executions": 0, "groups": []}

    result_rows = await db[FLOW_RESULTS_COLLECTION].find(
        {
            "org_id": organization_id,
            "document_id": {"$in": doc_ids},
            "flow_id": {"$in": list(flow_infos.keys())},
        }
    ).to_list(length=None)
    results_by_pair: dict[tuple[str, str], dict[str, Any]] = {}
    for row in result_rows:
        doc_id = str(row.get("document_id") or "")
        flow_id = str(row.get("flow_id") or "")
        if doc_id and flow_id:
            results_by_pair[(doc_id, flow_id)] = row

    stored_versions_by_exec: dict[str, int] = {}
    if mode == "outdated":
        execution_ids = [
            str(row.get("execution_id") or "")
            for row in result_rows
            if row.get("execution_id")
        ]
        stored_versions_by_exec = await batch_flow_result_stored_versions(db, execution_ids)

    groups: list[dict[str, Any]] = []
    total_executions = 0

    for flow_id, info in flow_infos.items():
        executions: list[dict[str, Any]] = []
        for doc_id in doc_ids:
            doc_tags = doc_tags_by_id.get(doc_id, set())
            if not _matching_trigger_for_document(
                info.revision, doc_tags, anchor_tag_id=anchor_tag
            ):
                continue

            result_row = results_by_pair.get((doc_id, flow_id))
            has_result = result_row is not None
            stored_version: int | None = None
            if result_row:
                exec_id = str(result_row.get("execution_id") or "")
                if exec_id:
                    stored_version = stored_versions_by_exec.get(exec_id)

            include, reason = flow_pair_needs_run(
                mode,
                has_result=has_result,
                stored_version=stored_version,
                active_version=info.active_version,
            )
            if not include:
                continue

            row: dict[str, Any] = {
                "document_id": doc_id,
                "document_name": doc_name_by_id.get(doc_id, ""),
            }
            if reason:
                row["reason"] = reason
            executions.append(row)

        if executions:
            groups.append({
                "flow_id": flow_id,
                "flow_name": info.flow_name,
                "flow_version": info.active_version,
                "trigger_type": "docrouter.trigger",
                "event_type": info.event_type,
                "executions": executions,
            })
            total_executions += len(executions)

    logger.info(
        f"bulk_analyze_flow_executions(): org={organization_id} mode={mode} "
        f"flows={len(flow_infos)} docs={len(documents)} executions={total_executions}"
    )
    return {"total_executions": total_executions, "groups": groups}
