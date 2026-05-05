from __future__ import annotations

"""Flow CRUD + execution routes (v1 scaffolding) as defined in `docs/flows.md`."""

import json
import logging
import asyncio
from datetime import datetime, UTC
from typing import Any, Optional, List, Literal

from bson import ObjectId
from bson.errors import InvalidId
from fastapi import APIRouter, Depends, HTTPException, Query, Body, Request
from starlette.responses import Response
from uuid import uuid4
from datetime import timedelta
from pydantic import BaseModel, Field, ConfigDict

import analytiq_data as ad

from app.auth import get_org_user
from app.models import User


logger = logging.getLogger(__name__)
flows_router = APIRouter(tags=["flows"])

# Preview: cap serialized JSON per run_data node entry to limit memory/CPU from pathological payloads.
_MAX_PREVIEW_RUN_DATA_ENTRY_BYTES = 512_000

_REDACT_TRIGGER_HEADER_KEYS = frozenset(
    {
        "authorization",
        "proxy-authorization",
        "cookie",
        "set-cookie",
        "x-api-key",
        "x-auth-token",
        "x-amz-security-token",
        "x-amzn-authorization",
    }
)


def _sanitize_inbound_webhook_headers(request: Request) -> dict[str, str]:
    """Avoid persisting secrets from inbound webhook HTTP headers into execution documents."""

    out: dict[str, str] = {}
    for k, v in request.headers.items():
        lk = k.lower()
        if lk in _REDACT_TRIGGER_HEADER_KEYS or lk.startswith("x-amz-") or lk.startswith("x-forwarded-authorization"):
            out[k] = "[redacted]"
        else:
            out[k] = v
    return out


def _inbound_webhook_canonical_public_url(request: Request) -> str:
    """
    Client-facing webhook URL as seen beyond reverse proxies.

    Prefer ``X-Forwarded-Proto`` / ``X-Forwarded-Host`` when present so stored URLs match
    what Postman/callers hit (``https`` + public host).
    """

    xf_proto = request.headers.get("x-forwarded-proto")
    proto = ""
    if isinstance(xf_proto, str) and xf_proto.strip():
        proto = xf_proto.strip().split(",")[0].strip().lower()
    if not proto:
        proto = (request.url.scheme or "https").lower()

    xf_host = request.headers.get("x-forwarded-host")
    host = ""
    if isinstance(xf_host, str) and xf_host.strip():
        host = xf_host.strip().split(",")[0].strip()
    if not host:
        hh = request.headers.get("host")
        if isinstance(hh, str) and hh.strip():
            host = hh.strip()
    if not host:
        host = request.url.netloc or "localhost"

    path = request.url.path or ""
    query = request.url.query
    if query:
        return f"{proto}://{host}{path}?{query}"
    return f"{proto}://{host}{path}"


def _safe_webhook_blob_segment(part: str) -> str:
    """Single path segment for GridFS keys (no slashes)."""

    p = "".join(c if (c.isalnum() or c in "._-") else "_" for c in part)
    return (p[:120] if p else "file")


async def _webhook_finalize_pending_uploads(
    db: Any,
    aq_client: Any,
    exec_id: str,
    trigger: dict[str, Any],
    pending: list[tuple[str, bytes, str, str | None]],
) -> dict[str, Any]:
    """Upload ``pending`` blobs to ``flow_blobs`` and merge ``binary_properties`` into ``trigger``."""

    if not pending:
        return trigger
    binary_props: list[dict[str, Any]] = []
    for i, (field, blob_bytes, mime, fname) in enumerate(pending):
        seg_f = _safe_webhook_blob_segment(field)
        seg_n = _safe_webhook_blob_segment(fname or field or "file")
        gfs_key = f"{exec_id}/webhook/incoming/{i}_{seg_f}/{seg_n}"
        await ad.mongodb.blob.save_blob_async(
            aq_client,
            bucket="flow_blobs",
            key=gfs_key,
            blob=blob_bytes,
            metadata={
                "mime_type": mime,
                "webhook_field": field,
                "file_name": fname or "",
            },
        )
        binary_props.append(
            {
                "name": field,
                "mime_type": mime,
                "file_name": fname,
                "storage_id": f"flow_blobs:{gfs_key}",
                "file_size": len(blob_bytes),
            }
        )
    merged = {**trigger, "binary_properties": binary_props}
    await db.flow_executions.update_one(
        {"_id": ObjectId(exec_id)},
        {"$set": {"trigger": merged}},
    )
    return merged


def _extract_webhook_leaf_from_nodes(nodes: list[dict[str, Any]]) -> str | None:
    """Return webhook trigger leaf if present on the revision nodes."""
    for n in nodes:
        if not isinstance(n, dict):
            continue
        if n.get("type") != "flows.trigger.webhook":
            continue
        params = n.get("parameters") or {}
        if not isinstance(params, dict):
            return None
        leaf = params.get("webhook_leaf")
        if not isinstance(leaf, str):
            return None
        s = leaf.strip()
        return s or None
    return None


async def _upsert_flow_webhook_route_leaf(
    db: Any,
    *,
    leaf: str,
    flow_id: str,
    organization_id: str,
) -> None:
    """
    Ensure `flow_webhook_routes[_id=leaf]` is owned by this flow.

    The leaf must be system-wide unique, so if another flow already owns it,
    raise 409.
    """
    existing = await db.flow_webhook_routes.find_one({"_id": leaf})
    if existing:
        prod = existing.get("production") if isinstance(existing.get("production"), dict) else {}
        test = existing.get("test") if isinstance(existing.get("test"), dict) else {}
        owner_flow = prod.get("flow_id") or test.get("flow_id")
        if owner_flow and owner_flow != flow_id:
            raise HTTPException(status_code=409, detail="Webhook URL leaf is already in use")
    await db.flow_webhook_routes.update_one(
        {"_id": leaf},
        {
            "$setOnInsert": {"created_at": _now()},
            "$set": {
                "leaf": leaf,
                "production.flow_id": flow_id,
                "production.organization_id": organization_id,
                "updated_at": _now(),
            },
        },
        upsert=True,
    )


async def _clear_other_webhook_route_leaves_for_flow(db: Any, *, flow_id: str, keep_leaf: str) -> None:
    """If a flow changes its webhook leaf, clear old mappings for this flow."""
    cursor = db.flow_webhook_routes.find(
        {
            "_id": {"$ne": keep_leaf},
            "$or": [{"production.flow_id": flow_id}, {"test.flow_id": flow_id}],
        }
    )
    async for doc in cursor:
        old_leaf = doc.get("_id")
        if not old_leaf:
            continue
        # Unset only the parts owned by this flow.
        unset: dict[str, str] = {}
        if isinstance(doc.get("production"), dict) and doc.get("production", {}).get("flow_id") == flow_id:
            unset["production"] = ""
        if isinstance(doc.get("test"), dict) and doc.get("test", {}).get("flow_id") == flow_id:
            unset["test"] = ""
        if unset:
            await db.flow_webhook_routes.update_one(
                {"_id": old_leaf},
                {"$unset": unset, "$set": {"updated_at": _now()}},
            )


def _raise_if_run_data_entries_oversized(run_data: dict[str, Any]) -> None:
    for nid, entry in run_data.items():
        try:
            blob = json.dumps(entry, default=str).encode("utf-8")
        except TypeError:
            blob = repr(entry).encode("utf-8")
        if len(blob) > _MAX_PREVIEW_RUN_DATA_ENTRY_BYTES:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"run_data entry for node {nid!r} exceeds maximum size "
                    f"({_MAX_PREVIEW_RUN_DATA_ENTRY_BYTES} bytes) for preview"
                ),
            )


class FlowHeader(BaseModel):
    flow_id: str
    organization_id: str
    name: str
    active: bool
    active_flow_revid: Optional[str] = None
    flow_version: int
    created_at: datetime
    created_by: str
    updated_at: datetime
    updated_by: str


class FlowRevision(BaseModel):
    flow_revid: str
    flow_id: str
    flow_version: int
    nodes: list[dict[str, Any]]
    connections: dict[str, Any]
    settings: dict[str, Any] = {}
    pin_data: dict[str, Any] | None = None
    graph_hash: str
    engine_version: int = 1
    created_at: datetime
    created_by: str


class CreateFlowRequest(BaseModel):
    name: str


class CreateFlowResponse(BaseModel):
    flow: FlowHeader


class ListFlowsResponse(BaseModel):
    items: list[dict[str, Any]]
    total: int


class PatchFlowRequest(BaseModel):
    name: str


class SaveFlowRequest(BaseModel):
    base_flow_revid: str
    name: str
    nodes: list[dict[str, Any]]
    connections: dict[str, Any]
    settings: dict[str, Any] = {}
    pin_data: dict[str, Any] | None = None


class SaveFlowResponse(BaseModel):
    flow: FlowHeader
    revision: FlowRevision | None = None


class ListenWebhookTestRequest(BaseModel):
    webhook_leaf: str | None = None
    revision_snapshot: FlowRevisionSnapshotRequest


class ListenWebhookTestResponse(BaseModel):
    webhook_leaf: str
    test_path: str
    production_path: str


class StopWebhookTestRequest(BaseModel):
    """Optional hints for tearing down `/webhook-test/{leaf}` without requiring a snapshot."""

    webhook_leaf: str | None = None
    revision_snapshot: FlowRevisionSnapshotRequest | None = None


class ActivateFlowRequest(BaseModel):
    flow_revid: str | None = None


class FlowRevisionSnapshotRequest(BaseModel):
    """Immutable graph copied from the editor (like n8n's `workflowData` on `/run`)."""
    nodes: list[dict[str, Any]]
    connections: dict[str, Any]
    settings: dict[str, Any] = Field(default_factory=dict)
    pin_data: dict[str, Any] | None = None


class RunFlowRequest(BaseModel):
    flow_revid: str | None = None
    document_id: str | None = None
    """When set, run only the upstream subgraph through this node (execute step)."""

    target_node_id: str | None = None
    """Client-supplied prior outputs keyed by node id (validated); merged into execution before run."""
    run_data: dict[str, Any] | None = None
    """Node ids whose seed entries are ignored so those nodes re-execute."""
    dirty_node_ids: list[str] | None = None
    """Editor graph to execute immediately (unsaved or dirty). Overrides DB revision when present."""
    revision_snapshot: FlowRevisionSnapshotRequest | None = None


async def _resolve_flow_revid_lineage(flow_id: str, flow_revid: str | None, db: Any) -> str:
    """Return `flow_revid` only if it is a valid revision id on this flow; else empty (e.g. never saved yet)."""

    fid = (flow_revid or "").strip()
    if not fid:
        return ""
    try:
        oid = ObjectId(fid)
    except Exception:
        return ""
    doc = await db.flow_revisions.find_one({"_id": oid, "flow_id": flow_id})
    return fid if doc else ""


class FlowExecution(BaseModel):
    model_config = ConfigDict(extra="ignore")

    execution_id: str
    flow_id: str
    flow_revid: str
    organization_id: str
    mode: str
    status: str
    started_at: datetime
    finished_at: datetime | None = None
    last_heartbeat_at: datetime | None = None
    stop_requested: bool = False
    last_node_executed: str | None = None
    run_data: dict[str, Any] = {}
    error: dict[str, Any] | None = None
    trigger: dict[str, Any]
    target_node_id: str | None = None
    initial_run_data: dict[str, Any] | None = None
    #: Present on list responses when joined from ``flows`` (org-wide execution views).
    flow_name: str | None = None


class ListExecutionsResponse(BaseModel):
    items: list[FlowExecution]
    total: int


class PreviewFlowExpressionRequest(BaseModel):
    expression: str = Field(..., max_length=16_384)
    run_data: dict[str, Any] = Field(default_factory=dict)
    """Plain JSON rows for inbound slot 0 (same shape as INPUT tab / ``itemsJson`` previews)."""

    input_items: list[dict[str, Any]] = Field(default_factory=list)
    preview_item_index: int = Field(0, ge=0, le=50_000)
    execution_refs: dict[str, Any] | None = None
    """Revision ``nodes`` for name-keyed ``_node`` in expressions (same shape as flow revision nodes)."""

    nodes: list[dict[str, Any]] = Field(default_factory=list)


class PreviewFlowExpressionResponse(BaseModel):
    skipped: bool = False
    ok: bool
    preview_text: str | None = None
    value: Any | None = None
    error: str | None = None


async def _get_db():
    return ad.common.get_async_db()


def _execution_doc_to_list_item(d: dict[str, Any]) -> FlowExecution:
    """Serialize a `flow_executions` document for list responses (ISO timestamps for JSON)."""

    fn = d.get("flow_name")
    return FlowExecution(
        execution_id=str(d["_id"]),
        flow_id=d["flow_id"],
        flow_revid=d["flow_revid"],
        organization_id=d["organization_id"],
        mode=d["mode"],
        status=d["status"],
        started_at=d["started_at"].replace(tzinfo=UTC).isoformat()
        if isinstance(d["started_at"], datetime)
        else d["started_at"],
        finished_at=(
            d["finished_at"].replace(tzinfo=UTC).isoformat()
            if isinstance(d.get("finished_at"), datetime)
            else d.get("finished_at")
        ),
        last_heartbeat_at=(
            d["last_heartbeat_at"].replace(tzinfo=UTC).isoformat()
            if isinstance(d.get("last_heartbeat_at"), datetime)
            else d.get("last_heartbeat_at")
        ),
        stop_requested=bool(d.get("stop_requested")),
        last_node_executed=d.get("last_node_executed"),
        run_data=d.get("run_data") or {},
        error=d.get("error"),
        trigger=d.get("trigger") or {},
        target_node_id=d.get("target_node_id"),
        initial_run_data=d.get("initial_run_data"),
        flow_name=str(fn) if fn is not None else None,
    )


def _now() -> datetime:
    return datetime.now(UTC)


@flows_router.get("/v0/orgs/{organization_id}/flows/node-types")
async def list_node_types(organization_id: str, current_user: User = Depends(get_org_user)):
    # Node types are global; org is for auth scoping and future filtering.
    items = []
    for nt in ad.flows.list_all():
        slots = getattr(nt, "credential_slots", None)
        items.append(
            {
                "key": nt.key,
                "label": nt.label,
                "description": nt.description,
                "category": nt.category,
                "is_trigger": nt.is_trigger,
                "min_inputs": nt.min_inputs,
                "max_inputs": nt.max_inputs,
                "outputs": nt.outputs,
                "output_labels": nt.output_labels,
                "parameter_schema": nt.parameter_schema,
                "icon_key": nt.icon_key,
                "credential_slots": slots if isinstance(slots, list) else [],
            }
        )
    return {"items": items, "total": len(items)}


@flows_router.post(
    "/v0/orgs/{organization_id}/flows/preview-expression",
    response_model=PreviewFlowExpressionResponse,
)
async def preview_flow_expression(
    organization_id: str,
    req: PreviewFlowExpressionRequest,
    current_user: User = Depends(get_org_user),
):
    # Auth only (org scoped); evaluator is sandboxed in analytiq_data.
    if len(req.run_data) > 120:
        raise HTTPException(status_code=400, detail="run_data has too many node entries for preview")
    if len(req.nodes) > 400:
        raise HTTPException(status_code=400, detail="nodes list is too large for preview")
    _raise_if_run_data_entries_oversized(req.run_data)

    val, err = ad.flows.preview_parameter_expression(
        req.expression,
        run_data=req.run_data,
        input_items_json=req.input_items,
        preview_item_index=req.preview_item_index,
        execution_refs=req.execution_refs,
        revision_nodes=req.nodes,
    )
    if val is None and err is None:
        return PreviewFlowExpressionResponse(skipped=True, ok=True)

    if err is not None:
        return PreviewFlowExpressionResponse(skipped=False, ok=False, error=err)

    preview_body: str
    try:
        preview_body = json.dumps(val, default=str)
    except TypeError:
        preview_body = str(val)
    max_len = 4000
    if len(preview_body) > max_len:
        preview_body = f"{preview_body[:max_len]}…"

    return PreviewFlowExpressionResponse(skipped=False, ok=True, preview_text=preview_body, value=val)


@flows_router.post("/v0/orgs/{organization_id}/flows", response_model=CreateFlowResponse)
async def create_flow(organization_id: str, req: CreateFlowRequest, current_user: User = Depends(get_org_user)):
    db = await _get_db()
    created_at = _now()
    res = await db.flows.insert_one(
        {
            "organization_id": organization_id,
            "name": req.name,
            "active": False,
            "active_flow_revid": None,
            "flow_version": 0,
            "created_at": created_at,
            "created_by": current_user.user_id,
            "updated_at": created_at,
            "updated_by": current_user.user_id,
        }
    )
    flow_id = str(res.inserted_id)
    header = await db.flows.find_one({"_id": ObjectId(flow_id)})
    _raw = {k: header[k] for k in header if k != "_id"}
    hdr = {k: (v.replace(tzinfo=UTC) if isinstance(v, datetime) else v) for k, v in _raw.items()}
    return {"flow": FlowHeader(flow_id=flow_id, **hdr)}


@flows_router.get("/v0/orgs/{organization_id}/flows", response_model=ListFlowsResponse)
async def list_flows(
    organization_id: str,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_org_user),
):
    db = await _get_db()
    total = await db.flows.count_documents({"organization_id": organization_id})
    pipeline = [
        {"$match": {"organization_id": organization_id}},
        {"$sort": {"updated_at": -1}},
        {"$skip": offset},
        {"$limit": limit},
        {
            "$lookup": {
                "from": "flow_revisions",
                "let": {"fid": {"$toString": "$_id"}},
                "pipeline": [
                    {"$match": {"$expr": {"$eq": ["$flow_id", "$$fid"]}}},
                    {"$sort": {"flow_version": -1}},
                    {"$limit": 1},
                    {"$project": {"_id": 1, "flow_version": 1, "graph_hash": 1}},
                ],
                "as": "_latest",
            }
        },
    ]
    rows = await db.flows.aggregate(pipeline).to_list(limit)
    items: list[dict[str, Any]] = []
    for h in rows:
        fid = str(h["_id"])
        latest = h["_latest"][0] if h.get("_latest") else None
        items.append(
            {
                "flow": {
                    "flow_id": fid,
                    "organization_id": h["organization_id"],
                    "name": h["name"],
                    "active": bool(h.get("active")),
                    "active_flow_revid": h.get("active_flow_revid"),
                    "flow_version": int(h.get("flow_version") or 0),
                    "created_at": h["created_at"].replace(tzinfo=UTC).isoformat()
                    if isinstance(h["created_at"], datetime)
                    else h["created_at"],
                    "created_by": h["created_by"],
                    "updated_at": h["updated_at"].replace(tzinfo=UTC).isoformat()
                    if isinstance(h["updated_at"], datetime)
                    else h["updated_at"],
                    "updated_by": h["updated_by"],
                },
                "latest_revision": None if not latest else {
                    "flow_revid": str(latest["_id"]),
                    "flow_version": latest["flow_version"],
                    "graph_hash": latest.get("graph_hash"),
                },
            }
        )
    return {"items": items, "total": total}


@flows_router.get("/v0/orgs/{organization_id}/flows/{flow_id}")
async def get_flow(organization_id: str, flow_id: str, current_user: User = Depends(get_org_user)):
    db = await _get_db()
    h = await db.flows.find_one({"_id": ObjectId(flow_id), "organization_id": organization_id})
    if not h:
        raise HTTPException(status_code=404, detail="Flow not found")
    latest = await db.flow_revisions.find_one({"flow_id": flow_id}, sort=[("flow_version", -1)])
    return {
        "flow": {
            "flow_id": flow_id,
            "organization_id": h["organization_id"],
            "name": h["name"],
            "active": bool(h.get("active")),
            "active_flow_revid": h.get("active_flow_revid"),
            "flow_version": int(h.get("flow_version") or 0),
            "created_at": h["created_at"].replace(tzinfo=UTC),
            "created_by": h["created_by"],
            "updated_at": h["updated_at"].replace(tzinfo=UTC),
            "updated_by": h["updated_by"],
        },
        "latest_revision": None if not latest else {"flow_revid": str(latest["_id"]), "flow_version": latest["flow_version"], "graph_hash": latest.get("graph_hash")},
    }


@flows_router.patch("/v0/orgs/{organization_id}/flows/{flow_id}")
async def patch_flow_name(organization_id: str, flow_id: str, req: PatchFlowRequest, current_user: User = Depends(get_org_user)):
    db = await _get_db()
    res = await db.flows.update_one(
        {"_id": ObjectId(flow_id), "organization_id": organization_id},
        {"$set": {"name": req.name, "updated_at": _now(), "updated_by": current_user.user_id}},
    )
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Flow not found")
    return await get_flow(organization_id, flow_id, current_user)


@flows_router.delete("/v0/orgs/{organization_id}/flows/{flow_id}")
async def delete_flow(organization_id: str, flow_id: str, current_user: User = Depends(get_org_user)):
    """
    Delete a flow header document.

    v1 behavior: only deletes from the `flows` collection. Revisions/executions are left
    intact for now (can be cleaned up by a later admin task / cascading delete).
    """

    db = await _get_db()
    res = await db.flows.delete_one({"_id": ObjectId(flow_id), "organization_id": organization_id})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Flow not found")
    return {"ok": True}


@flows_router.get("/v0/orgs/{organization_id}/flows/{flow_id}/revisions")
async def list_revisions(
    organization_id: str,
    flow_id: str,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_org_user),
):
    db = await _get_db()
    h = await db.flows.find_one({"_id": ObjectId(flow_id), "organization_id": organization_id})
    if not h:
        raise HTTPException(status_code=404, detail="Flow not found")
    total = await db.flow_revisions.count_documents({"flow_id": flow_id})
    revs = await db.flow_revisions.find({"flow_id": flow_id}).sort([("flow_version", -1)]).skip(offset).limit(limit).to_list(limit)
    items = []
    for r in revs:
        items.append(
            {
                "flow_revid": str(r["_id"]),
                "flow_version": r["flow_version"],
                "graph_hash": r.get("graph_hash"),
                "created_at": r["created_at"].replace(tzinfo=UTC).isoformat()
                if isinstance(r["created_at"], datetime)
                else r["created_at"],
                "created_by": r["created_by"],
            }
        )
    return {"items": items, "total": total}


@flows_router.get("/v0/orgs/{organization_id}/flows/{flow_id}/revisions/{flow_revid}")
async def get_revision(organization_id: str, flow_id: str, flow_revid: str, current_user: User = Depends(get_org_user)):
    db = await _get_db()
    h = await db.flows.find_one({"_id": ObjectId(flow_id), "organization_id": organization_id})
    if not h:
        raise HTTPException(status_code=404, detail="Flow not found")
    r = await db.flow_revisions.find_one({"_id": ObjectId(flow_revid), "flow_id": flow_id})
    if not r:
        raise HTTPException(status_code=404, detail="Revision not found")
    out = {**r, "_id": str(r["_id"])}
    for k, v in list(out.items()):
        if isinstance(v, datetime):
            out[k] = v.replace(tzinfo=UTC)
    return out


@flows_router.put("/v0/orgs/{organization_id}/flows/{flow_id}", response_model=SaveFlowResponse)
async def save_revision(organization_id: str, flow_id: str, req: SaveFlowRequest, current_user: User = Depends(get_org_user)):
    db = await _get_db()
    h = await db.flows.find_one({"_id": ObjectId(flow_id), "organization_id": organization_id})
    if not h:
        raise HTTPException(status_code=404, detail="Flow not found")

    latest = await db.flow_revisions.find_one({"flow_id": flow_id}, sort=[("flow_version", -1)])
    if latest and str(latest["_id"]) != req.base_flow_revid:
        raise HTTPException(status_code=409, detail="base_flow_revid is not the latest revision")

    nodes = req.nodes
    try:
        connections = ad.flows.coerce_json_connections_to_dataclasses(req.connections)
    except (KeyError, TypeError, ValueError) as e:
        raise HTTPException(status_code=400, detail=f"Invalid connections: {e}") from e
    settings = req.settings or {}
    pin_data = req.pin_data

    try:
        ad.flows.validate_revision(nodes, connections, settings, pin_data)
    except ad.flows.FlowValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Ensure webhook trigger leaf is persisted and system-wide unique (if this graph uses webhook trigger).
    leaf = _extract_webhook_leaf_from_nodes(nodes)
    if leaf is None:
        # If the trigger exists but leaf is missing, generate one so the editor always gets URLs.
        if any(isinstance(n, dict) and n.get("type") == "flows.trigger.webhook" for n in nodes):
            leaf = str(uuid4())
            for n in nodes:
                if isinstance(n, dict) and n.get("type") == "flows.trigger.webhook":
                    p = n.get("parameters")
                    if not isinstance(p, dict):
                        n["parameters"] = {"webhook_leaf": leaf}
                    else:
                        p.setdefault("webhook_leaf", leaf)
                    break
    if leaf:
        await _upsert_flow_webhook_route_leaf(db, leaf=leaf, flow_id=flow_id, organization_id=organization_id)
        await _clear_other_webhook_route_leaves_for_flow(db, flow_id=flow_id, keep_leaf=leaf)

    ghash = ad.flows.canonical_graph_hash(nodes, req.connections, settings)

    def _stable_pin_json(p: Any) -> str:
        return json.dumps(p, sort_keys=True, separators=(",", ":"), default=str)

    pin_same = latest is not None and _stable_pin_json(latest.get("pin_data")) == _stable_pin_json(pin_data)

    # graph_hash excludes pin_data; require matching pin_data so pin-only edits still persist as a new revision.
    if latest and latest.get("graph_hash") == ghash and pin_same:
        if req.name != h.get("name"):
            await db.flows.update_one(
                {"_id": ObjectId(flow_id)},
                {"$set": {"name": req.name, "updated_at": _now(), "updated_by": current_user.user_id}},
            )
        h2 = await db.flows.find_one({"_id": ObjectId(flow_id)})
        _raw = {k: h2[k] for k in h2 if k != "_id"}
        hdr = {k: (v.replace(tzinfo=UTC) if isinstance(v, datetime) else v) for k, v in _raw.items()}
        return {
            "flow": FlowHeader(flow_id=flow_id, **hdr),
            "revision": None,
        }

    next_version = int(h.get("flow_version") or 0) + 1
    created_at = _now()
    res = await db.flow_revisions.insert_one(
        {
            "flow_id": flow_id,
            "flow_version": next_version,
            "nodes": nodes,
            "connections": req.connections,  # store JSON-friendly shape
            "settings": settings,
            "pin_data": pin_data,
            "graph_hash": ghash,
            "engine_version": 1,
            "created_at": created_at,
            "created_by": current_user.user_id,
        }
    )
    flow_revid = str(res.inserted_id)
    await db.flows.update_one(
        {"_id": ObjectId(flow_id)},
        {
            "$set": {
                "name": req.name,
                "flow_version": next_version,
                "updated_at": created_at,
                "updated_by": current_user.user_id,
            }
        },
    )
    h2 = await db.flows.find_one({"_id": ObjectId(flow_id)})
    r = await db.flow_revisions.find_one({"_id": ObjectId(flow_revid)})
    _raw = {k: h2[k] for k in h2 if k != "_id"}
    hdr = {k: (v.replace(tzinfo=UTC) if isinstance(v, datetime) else v) for k, v in _raw.items()}
    rev = FlowRevision(
        flow_revid=flow_revid,
        flow_id=flow_id,
        flow_version=r["flow_version"],
        nodes=r["nodes"],
        connections=r["connections"],
        settings=r.get("settings") or {},
        pin_data=r.get("pin_data"),
        graph_hash=r["graph_hash"],
        engine_version=r.get("engine_version") or 1,
        created_at=r["created_at"].replace(tzinfo=UTC),
        created_by=r["created_by"],
    )
    return {"flow": FlowHeader(flow_id=flow_id, **hdr), "revision": rev}


@flows_router.post("/v0/orgs/{organization_id}/flows/{flow_id}/activate")
async def activate_flow(organization_id: str, flow_id: str, req: ActivateFlowRequest = Body(default={}), current_user: User = Depends(get_org_user)):
    db = await _get_db()
    h = await db.flows.find_one({"_id": ObjectId(flow_id), "organization_id": organization_id})
    if not h:
        raise HTTPException(status_code=404, detail="Flow not found")
    target = req.flow_revid
    if not target:
        latest = await db.flow_revisions.find_one({"flow_id": flow_id}, sort=[("flow_version", -1)])
        if not latest:
            raise HTTPException(status_code=400, detail="Flow has no revisions")
        target = str(latest["_id"])
    r = await db.flow_revisions.find_one({"_id": ObjectId(target), "flow_id": flow_id})
    if not r:
        raise HTTPException(status_code=404, detail="Revision not found")
    await db.flows.update_one(
        {"_id": ObjectId(flow_id)},
        {"$set": {"active": True, "active_flow_revid": target, "updated_at": _now(), "updated_by": current_user.user_id}},
    )
    return await get_flow(organization_id, flow_id, current_user)


@flows_router.post("/v0/orgs/{organization_id}/flows/{flow_id}/deactivate")
async def deactivate_flow(organization_id: str, flow_id: str, current_user: User = Depends(get_org_user)):
    db = await _get_db()
    res = await db.flows.update_one(
        {"_id": ObjectId(flow_id), "organization_id": organization_id},
        {"$set": {"active": False, "active_flow_revid": None, "updated_at": _now(), "updated_by": current_user.user_id}},
    )
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Flow not found")
    return await get_flow(organization_id, flow_id, current_user)


@flows_router.post(
    "/v0/orgs/{organization_id}/flows/{flow_id}/webhook-test/listen",
    response_model=ListenWebhookTestResponse,
)
async def listen_webhook_test(
    organization_id: str,
    flow_id: str,
    req: ListenWebhookTestRequest,
    current_user: User = Depends(get_org_user),
):
    """
    Store a short-lived draft snapshot for `/webhook-test/{leaf}`.

    This is what the editor uses for "Listen for test event": it should execute the current
    unsaved graph (`revision_snapshot`) rather than the activated production revision.
    """
    db = await _get_db()
    h = await db.flows.find_one({"_id": ObjectId(flow_id), "organization_id": organization_id})
    if not h:
        raise HTTPException(status_code=404, detail="Flow not found")

    leaf = (req.webhook_leaf or "").strip() or _extract_webhook_leaf_from_nodes(req.revision_snapshot.nodes) or str(uuid4())
    await _upsert_flow_webhook_route_leaf(db, leaf=leaf, flow_id=flow_id, organization_id=organization_id)
    await _clear_other_webhook_route_leaves_for_flow(db, flow_id=flow_id, keep_leaf=leaf)

    # Persist snapshot for test calls.
    await db.flow_webhook_routes.update_one(
        {"_id": leaf},
        {
            "$set": {
                "test.flow_id": flow_id,
                "test.organization_id": organization_id,
                "test.revision_snapshot": req.revision_snapshot.model_dump(),
                "test.expires_at": _now() + timedelta(hours=2),
                "updated_at": _now(),
            }
        },
        upsert=True,
    )
    return ListenWebhookTestResponse(
        webhook_leaf=leaf,
        test_path=f"/webhook-test/{leaf}",
        production_path=f"/webhook/{leaf}",
    )


@flows_router.post("/v0/orgs/{organization_id}/flows/{flow_id}/webhook-test/stop")
async def stop_listen_webhook_test(
    organization_id: str,
    flow_id: str,
    req: StopWebhookTestRequest | None = Body(default=None),
    current_user: User = Depends(get_org_user),
):
    """
    Tear down editor test-mode listening so `/webhook-test/{leaf}` yields 404 again.

    Optionally pass `webhook_leaf` explicitly; otherwise the server tries to infer from the webhook node
    snapshot in ``req.revision_snapshot``.
    """

    db = await _get_db()
    h = await db.flows.find_one({"_id": ObjectId(flow_id), "organization_id": organization_id})
    if not h:
        raise HTTPException(status_code=404, detail="Flow not found")

    leaf_any = ""
    if req:
        leaf_any = (req.webhook_leaf or "").strip() or ""
        snap = req.revision_snapshot
        if not leaf_any and snap and snap.nodes:
            leaf_any = (_extract_webhook_leaf_from_nodes(snap.nodes) or "").strip()

    leaf = leaf_any
    doc = await db.flow_webhook_routes.find_one({"_id": leaf}) if leaf else None

    # Best-effort: if caller didn't pass snapshot/leaf (or doc missing), locate any routes owned by this flow in test mode.
    if not doc:
        cand = await db.flow_webhook_routes.find_one({"test.flow_id": flow_id, "test.organization_id": organization_id})
        doc = cand
        leaf = str(doc["_id"]) if cand and cand.get("_id") else leaf

    if not doc:
        # Nothing to remove.
        return {"ok": True}

    test_any = doc.get("test") if isinstance(doc.get("test"), dict) else None
    if not test_any:
        return {"ok": True}
    if test_any.get("flow_id") != flow_id or test_any.get("organization_id") != organization_id:
        raise HTTPException(status_code=403, detail="Cannot stop webhook test listener for another flow")

    lid = doc.get("_id")
    await db.flow_webhook_routes.update_one(
        {"_id": lid},
        {"$unset": {"test": ""}, "$set": {"updated_at": _now()}},
    )
    leftover = await db.flow_webhook_routes.find_one({"_id": lid})
    if leftover and not isinstance(leftover.get("production"), dict) and not isinstance(leftover.get("test"), dict):
        await db.flow_webhook_routes.delete_one({"_id": lid})
    return {"ok": True}


@flows_router.post("/v0/orgs/{organization_id}/flows/{flow_id}/run")
async def run_flow(organization_id: str, flow_id: str, req: RunFlowRequest, current_user: User = Depends(get_org_user)):
    db = await _get_db()
    h = await db.flows.find_one({"_id": ObjectId(flow_id), "organization_id": organization_id})
    if not h:
        raise HTTPException(status_code=404, detail="Flow not found")

    rev: dict[str, Any] | None = None
    revision_snapshot: dict[str, Any] | None = None
    flow_revid_linage: str = ""

    if req.revision_snapshot is not None:
        snap = req.revision_snapshot
        nodes = snap.nodes
        try:
            conns_dc = ad.flows.coerce_json_connections_to_dataclasses(snap.connections)
        except (KeyError, TypeError, ValueError) as e:
            raise HTTPException(status_code=400, detail=f"Invalid connections: {e}") from e
        settings = snap.settings or {}
        pin_data = snap.pin_data
        try:
            ad.flows.validate_revision(nodes, conns_dc, settings, pin_data)
        except ad.flows.FlowValidationError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e
        revision_snapshot = {
            "nodes": nodes,
            "connections": snap.connections,
            "settings": settings,
            "pin_data": pin_data,
        }
        flow_revid_linage = await _resolve_flow_revid_lineage(flow_id, req.flow_revid, db)
    else:
        flow_revid = (req.flow_revid or "").strip()
        if not flow_revid:
            latest = await db.flow_revisions.find_one({"flow_id": flow_id}, sort=[("flow_version", -1)])
            if not latest:
                raise HTTPException(status_code=400, detail="Flow has no revisions")
            flow_revid = str(latest["_id"])

        rev = await db.flow_revisions.find_one({"_id": ObjectId(flow_revid), "flow_id": flow_id})
        if not rev:
            raise HTTPException(status_code=404, detail="Revision not found")
        flow_revid_linage = flow_revid

    known_nodes = (revision_snapshot or rev or {}).get("nodes") or []
    known_node_ids = {str(n["id"]) for n in known_nodes if n.get("id")}
    if req.target_node_id and req.target_node_id not in known_node_ids:
        raise HTTPException(status_code=400, detail="target_node_id is not a node on the selected revision")

    if req.run_data and not req.target_node_id:
        raise HTTPException(status_code=400, detail="target_node_id is required when run_data is supplied")

    try:
        seed_filtered = ad.flows.validate_and_filter_run_data_seed(
            known_node_ids=known_node_ids,
            seed=req.run_data,
        )
    except ad.flows.RunDataSeedValidationError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e

    dirty_clean = ad.flows.finalized_dirty_node_ids(
        dirty_node_ids=req.dirty_node_ids,
        target_node_id=req.target_node_id,
        known_node_ids=known_node_ids,
    )

    exec_doc = {
        "flow_id": flow_id,
        "flow_revid": flow_revid_linage,
        "organization_id": organization_id,
        "mode": "manual",
        "status": "queued",
        "started_at": _now(),
        "finished_at": None,
        "last_heartbeat_at": None,
        "stop_requested": False,
        "last_node_executed": None,
        "wait_till": None,
        "retry_of": None,
        "parent_execution_id": None,
        "run_data": {},
        "error": None,
        "trigger": {"type": "manual", "document_id": req.document_id},
        "target_node_id": req.target_node_id,
        "initial_run_data": seed_filtered or None,
        "dirty_node_ids": dirty_clean or None,
    }
    if revision_snapshot is not None:
        exec_doc["revision_snapshot"] = revision_snapshot
    res_ins = await db.flow_executions.insert_one(exec_doc)
    exec_id = str(res_ins.inserted_id)

    await ad.queue.send_msg(ad.common.get_analytiq_client(), "flow_run", msg={
        "flow_id": flow_id,
        "flow_revid": flow_revid_linage or "",
        "execution_id": exec_id,
        "organization_id": organization_id,
        "trigger": exec_doc["trigger"],
    })
    return {"execution_id": exec_id}


@flows_router.get("/v0/orgs/{organization_id}/executions", response_model=ListExecutionsResponse)
async def list_executions(
    organization_id: str,
    flow_id: str | None = Query(None, description="When set, only executions for this flow"),
    status: str | None = Query(None, description="Filter by execution status"),
    mode: str | None = Query(None, description="Filter by execution mode"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_org_user),
):
    """List flow executions for the organization; optionally narrow by flow and filters."""

    _ = current_user
    db = await _get_db()
    query: dict[str, Any] = {"organization_id": organization_id}
    if flow_id:
        query["flow_id"] = flow_id
    if status:
        query["status"] = status
    if mode:
        query["mode"] = mode
    total = await db.flow_executions.count_documents(query)
    pipeline: list[dict[str, Any]] = [
        {"$match": query},
        {"$sort": {"started_at": -1}},
        {"$skip": offset},
        {"$limit": limit},
        {
            "$lookup": {
                "from": "flows",
                "let": {"fid": "$flow_id"},
                "pipeline": [
                    {"$match": {"$expr": {"$eq": [{"$toString": "$_id"}, "$$fid"]}}},
                    {"$limit": 1},
                    {"$project": {"_id": 0, "name": 1}},
                ],
                "as": "_flow_join",
            }
        },
        {
            "$set": {
                "flow_name": {
                    "$let": {
                        "vars": {"fn": {"$arrayElemAt": ["$_flow_join.name", 0]}},
                        "in": "$$fn",
                    }
                }
            }
        },
        {"$project": {"_flow_join": 0}},
    ]
    docs = await db.flow_executions.aggregate(pipeline).to_list(limit)
    items = [_execution_doc_to_list_item(d) for d in docs]
    return {"items": items, "total": total}


@flows_router.get("/v0/orgs/{organization_id}/flows/{flow_id}/executions/{exec_id}", response_model=FlowExecution)
async def get_execution(organization_id: str, flow_id: str, exec_id: str, current_user: User = Depends(get_org_user)):
    db = await _get_db()
    d = await db.flow_executions.find_one({"_id": ObjectId(exec_id), "flow_id": flow_id, "organization_id": organization_id})
    if not d:
        raise HTTPException(status_code=404, detail="Execution not found")
    return FlowExecution(
        execution_id=str(d["_id"]),
        flow_id=d["flow_id"],
        flow_revid=d["flow_revid"],
        organization_id=d["organization_id"],
        mode=d["mode"],
        status=d["status"],
        started_at=d["started_at"].replace(tzinfo=UTC),
        finished_at=d["finished_at"].replace(tzinfo=UTC) if isinstance(d.get("finished_at"), datetime) else d.get("finished_at"),
        last_heartbeat_at=d["last_heartbeat_at"].replace(tzinfo=UTC)
        if isinstance(d.get("last_heartbeat_at"), datetime)
        else d.get("last_heartbeat_at"),
        stop_requested=bool(d.get("stop_requested")),
        last_node_executed=d.get("last_node_executed"),
        run_data=d.get("run_data") or {},
        error=d.get("error"),
        trigger=d.get("trigger") or {},
        target_node_id=d.get("target_node_id"),
        initial_run_data=d.get("initial_run_data"),
    )


@flows_router.get("/v0/orgs/{organization_id}/flows/{flow_id}/executions/{exec_id}/blob")
async def get_execution_blob(
    organization_id: str,
    flow_id: str,
    exec_id: str,
    storage_id: str = Query(..., min_length=1, description='BinaryRef.storage_id (bucket:key), e.g. flow_blobs:execId/node/item/prop'),
    current_user: User = Depends(get_org_user),
):
    """Return bytes for an item binary stored under this execution (`flow_blobs` GridFS keys are scoped per execution)."""

    _ = current_user
    try:
        oid = ObjectId(exec_id)
    except InvalidId:
        raise HTTPException(status_code=404, detail="Execution not found")

    db = await _get_db()
    doc = await db.flow_executions.find_one({"_id": oid, "flow_id": flow_id, "organization_id": organization_id})
    if not doc:
        raise HTTPException(status_code=404, detail="Execution not found")

    sid = storage_id.strip()
    parts = sid.split(":", 1)
    if len(parts) != 2 or parts[0] != "flow_blobs" or not parts[1]:
        raise HTTPException(status_code=400, detail="Invalid storage_id")
    key = parts[1]
    if not key.startswith(f"{exec_id}/"):
        raise HTTPException(status_code=403, detail="Blob key does not belong to this execution")

    aq_client = ad.common.get_analytiq_client()
    result = await ad.mongodb.blob.get_blob_async(aq_client, bucket="flow_blobs", key=key)
    if not result:
        raise HTTPException(status_code=404, detail="Blob not found")
    blob_raw = result.get("blob")
    if blob_raw is None:
        raise HTTPException(status_code=404, detail="Blob payload missing")
    blob = blob_raw if isinstance(blob_raw, (bytes, bytearray)) else bytes(blob_raw)

    meta_raw = result.get("metadata") or {}
    meta: dict[str, Any] = meta_raw if isinstance(meta_raw, dict) else {}
    mime = meta.get("mime_type") if isinstance(meta.get("mime_type"), str) else "application/octet-stream"
    fname = meta.get("file_name") if isinstance(meta.get("file_name"), str) else ""
    headers: dict[str, str] = {}
    if fname.strip():
        safe = "".join(ch if ch.isascii() and ch not in {'\\', '"'} else "_" for ch in fname.strip())[:240]
        headers["Content-Disposition"] = f'attachment; filename="{safe}"'
    return Response(content=blob, media_type=mime, headers=headers)


@flows_router.post("/v0/orgs/{organization_id}/flows/{flow_id}/executions/{exec_id}/stop")
async def stop_execution(organization_id: str, flow_id: str, exec_id: str, current_user: User = Depends(get_org_user)):
    db = await _get_db()
    res = await db.flow_executions.update_one(
        {"_id": ObjectId(exec_id), "flow_id": flow_id, "organization_id": organization_id},
        {"$set": {"stop_requested": True}},
    )
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Execution not found")
    return {"ok": True}


async def _inbound_webhook_common(
    *,
    db: Any,
    leaf: str,
    request: Request,
    mode: Literal["production", "test"],
) -> Response:
    """
    Shared inbound implementation for:
    - `/webhook/{leaf}` (production, activated revision)
    - `/webhook-test/{leaf}` (test, editor snapshot)
    """
    route = await db.flow_webhook_routes.find_one({"_id": leaf})
    if not route:
        raise HTTPException(status_code=404, detail="Unknown webhook")

    route_mode = route.get(mode) if isinstance(route.get(mode), dict) else None
    if not route_mode:
        raise HTTPException(status_code=404, detail="Unknown webhook")

    flow_id = route_mode.get("flow_id")
    org_id = route_mode.get("organization_id")
    if not flow_id or not org_id:
        raise HTTPException(status_code=404, detail="Unknown webhook")

    revision_doc: dict | None = None
    revision_snapshot: dict | None = None
    flow_revid_for_exec: str = ""

    if mode == "production":
        # Production: always run the activated saved revision.
        flow_doc = await db.flows.find_one({"_id": ObjectId(flow_id), "organization_id": org_id})
        if not flow_doc:
            raise HTTPException(status_code=404, detail="Flow not found")
        if not flow_doc.get("active") or not flow_doc.get("active_flow_revid"):
            raise HTTPException(status_code=409, detail="Flow is not active")
        flow_revid_for_exec = str(flow_doc["active_flow_revid"])
        try:
            revision_doc = await db.flow_revisions.find_one({"_id": ObjectId(flow_revid_for_exec), "flow_id": flow_id})
        except InvalidId:
            revision_doc = None
    else:
        # Test: run latest editor snapshot registered by /webhook-test/listen.
        expires_at = route_mode.get("expires_at")
        if isinstance(expires_at, datetime) and expires_at.replace(tzinfo=UTC) < _now():
            raise HTTPException(status_code=404, detail="Test webhook listener expired")
        snap_any = route_mode.get("revision_snapshot")
        revision_snapshot = dict(snap_any) if isinstance(snap_any, dict) else None

    params = ad.flows.webhook_params.extract_webhook_params_from_revision(revision_snapshot or revision_doc)
    response_mode = (params.get("response_mode") or "on_received").strip() if isinstance(params.get("response_mode"), str) else "on_received"

    allowed = ad.flows.webhook_params.allowed_http_methods_snapshot(params)
    if allowed is not None and request.method.upper() not in allowed:
        raise HTTPException(status_code=405, detail="Method not allowed")

    hops, direct_ip = ad.flows.webhook_params.request_ip_candidates(request)
    if not ad.flows.webhook_params.is_ip_whitelisted(params.get("ip_whitelist"), hops, direct_ip):
        raise HTTPException(status_code=403, detail="IP is not whitelisted to access the webhook")

    if params.get("ignore_bots") and ad.flows.webhook_params.user_agent_looks_like_bot(
        request.headers.get("user-agent")
    ):
        raise HTTPException(status_code=403, detail="Bots are not allowed for this webhook")

    raw_body = bool(params.get("raw_body"))
    bpf = params.get("binary_property_name")
    binary_pn = bpf.strip() if isinstance(bpf, str) else "data"
    parsed = await ad.flows.webhook_parse.parse_webhook_request(
        request,
        raw_body=raw_body,
        binary_property_name=binary_pn,
    )

    trigger: dict[str, Any] = {
        "type": "webhook",
        "webhook_leaf": leaf,
        "webhook_mode": mode,
        "method": request.method,
        "headers": _sanitize_inbound_webhook_headers(request),
        "query": parsed.query or {},
        "body": parsed.body,
        "form": parsed.form,
        "binary_properties": [],
        # Used only when building webhook trigger ``FlowItem.json`` (`webhookUrl` field).
        "webhook_url": _inbound_webhook_canonical_public_url(request),
        # Raw body bytes live in binary output only (`FlowItem.binary`), not ``json.body``.
        "body_stashed_as_binary": bool(getattr(parsed, "body_stashed_as_binary", False)),
    }
    exec_doc = {
        "flow_id": flow_id,
        "flow_revid": flow_revid_for_exec,
        "organization_id": org_id,
        "mode": "webhook" if mode == "production" else "webhook_test",
        "status": "queued",
        "started_at": _now(),
        "finished_at": None,
        "last_heartbeat_at": None,
        "stop_requested": False,
        "last_node_executed": None,
        "wait_till": None,
        "retry_of": None,
        "parent_execution_id": None,
        "run_data": {},
        "error": None,
        "trigger": trigger,
    }
    if revision_snapshot is not None:
        exec_doc["revision_snapshot"] = revision_snapshot
    res = await db.flow_executions.insert_one(exec_doc)
    exec_id = str(res.inserted_id)

    aq_client = ad.common.get_analytiq_client()
    trigger = await _webhook_finalize_pending_uploads(db, aq_client, exec_id, trigger, parsed.pending_binaries)

    # Synchronous response modes: execute in-process and return response payload.
    if response_mode in ("respond_to_webhook", "last_node"):
        ctx = ad.flows.ExecutionContext(
            organization_id=org_id,
            execution_id=exec_id,
            flow_id=flow_id,
            flow_revid=flow_revid_for_exec,
            mode="webhook",
            trigger_data=trigger,
            run_data={},
            analytiq_client=aq_client,
            stop_requested=False,
            logger=None,
        )

        rev_for_run = revision_snapshot or revision_doc
        if not isinstance(rev_for_run, dict):
            raise HTTPException(status_code=500, detail="Missing flow revision for webhook execution")

        # Bound synchronous webhook execution time; keep a conservative default.
        try:
            await asyncio.wait_for(ad.flows.run_flow(context=ctx, revision=rev_for_run), timeout=25.0)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Webhook execution failed: {e}") from e

        # Prefer explicit Respond to Webhook node payload.
        resp_any = ctx.trigger_data.get("_webhook_response")
        if response_mode == "respond_to_webhook" and isinstance(resp_any, dict):
            sc = resp_any.get("status_code")
            try:
                status = int(sc) if sc is not None else 200
            except (TypeError, ValueError):
                status = 200
            hdrs = resp_any.get("headers")
            headers = dict(hdrs) if isinstance(hdrs, dict) else {}
            if resp_any.get("body_is_none"):
                return Response(status_code=status, headers=headers)
            body_txt = resp_any.get("body_bytes_utf8")
            body_bytes = (body_txt if isinstance(body_txt, str) else "").encode("utf-8")
            return Response(content=body_bytes, status_code=status, headers=headers)

        if response_mode == "respond_to_webhook":
            # No responder node found; fall back to default ack.
            sync_status, hdr_map, payload = ad.flows.webhook_params.synchronous_http_response(exec_id, params)
            if payload is None:
                return Response(status_code=sync_status, headers=dict(hdr_map))
            return Response(content=payload, status_code=sync_status, headers=dict(hdr_map))

        # last_node: return first JSON of last executed node (best-effort).
        keys = [k for k in ctx.run_data.keys() if isinstance(k, str) and not k.startswith("_")]
        last_node_id = keys[-1] if keys else None
        out_json: Any = {"execution_id": exec_id}
        if isinstance(last_node_id, str):
            ent = ctx.run_data.get(last_node_id) or {}
            try:
                main = ent.get("data", {}).get("main")  # type: ignore[union-attr]
                if isinstance(main, list) and main and isinstance(main[0], list) and main[0]:
                    it = main[0][0]
                    out_json = it.json if hasattr(it, "json") else out_json
            except Exception:
                pass
        body = json.dumps(out_json, default=str).encode("utf-8")
        return Response(content=body, status_code=200, headers={"Content-Type": "application/json"})

    await ad.queue.send_msg(
        aq_client,
        "flow_run",
        msg={
            "flow_id": flow_id,
            "flow_revid": flow_revid_for_exec,
            "execution_id": exec_id,
            "organization_id": org_id,
            "trigger": trigger,
        },
    )
    sync_status, hdr_map, payload = ad.flows.webhook_params.synchronous_http_response(exec_id, params)
    if payload is None:
        return Response(status_code=sync_status, headers=dict(hdr_map))
    return Response(content=payload, status_code=sync_status, headers=dict(hdr_map))


@flows_router.api_route("/webhook/{leaf}", methods=["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD"])
async def inbound_webhook_production(leaf: str, request: Request):
    db = await _get_db()
    return await _inbound_webhook_common(db=db, leaf=leaf, request=request, mode="production")

@flows_router.api_route(
    "/v0/orgs/{organization_id}/flows/webhook/{leaf}",
    methods=["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD"],
)
async def inbound_webhook_production_scoped(organization_id: str, leaf: str, request: Request):
    db = await _get_db()
    # The leaf is system-wide unique; org id here is for URL shape parity and logging.
    return await _inbound_webhook_common(db=db, leaf=leaf, request=request, mode="production")


@flows_router.api_route("/webhook-test/{leaf}", methods=["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD"])
async def inbound_webhook_test(leaf: str, request: Request):
    db = await _get_db()
    return await _inbound_webhook_common(db=db, leaf=leaf, request=request, mode="test")

@flows_router.api_route(
    "/v0/orgs/{organization_id}/flows/webhook-test/{leaf}",
    methods=["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD"],
)
async def inbound_webhook_test_scoped(organization_id: str, leaf: str, request: Request):
    db = await _get_db()
    return await _inbound_webhook_common(db=db, leaf=leaf, request=request, mode="test")


# Backward-compatible route (deprecated): `/v0/webhooks/{id}` used older webhook ids.
@flows_router.api_route("/v0/webhooks/{webhook_id}", methods=["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD"])
async def inbound_webhook(webhook_id: str, request: Request):
    db = await _get_db()
    return await _inbound_webhook_common(db=db, leaf=webhook_id, request=request, mode="production")

