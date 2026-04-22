from __future__ import annotations

import logging
from datetime import datetime, UTC
from typing import Any, Optional, List, Literal

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Query, Body, Request
from pydantic import BaseModel, Field, ConfigDict

import analytiq_data as ad
from analytiq_data.flows.engine import canonical_graph_hash, validate_revision, FlowValidationError
from analytiq_data.flows.connections import Connections, NodeConnection
from analytiq_data.flows.context import ExecutionContext
from analytiq_data.flows.engine import FlowEngine

from app.auth import get_org_user
from app.models import User
from app.flows.services import FlowServicesImpl


logger = logging.getLogger(__name__)
flows_router = APIRouter(tags=["flows"])


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


class ActivateFlowRequest(BaseModel):
    flow_revid: str | None = None


class RunFlowRequest(BaseModel):
    flow_revid: str | None = None
    document_id: str | None = None


class FlowExecution(BaseModel):
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


class ListExecutionsResponse(BaseModel):
    items: list[FlowExecution]
    total: int


async def _get_db():
    return ad.common.get_async_db()


def _now() -> datetime:
    return datetime.now(UTC)


@flows_router.get("/v0/orgs/{org_id}/flows/node-types")
async def list_node_types(org_id: str, current_user: User = Depends(get_org_user)):
    # Node types are global; org is for auth scoping and future filtering.
    items = []
    for nt in ad.flows.list_all():
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
            }
        )
    return {"items": items, "total": len(items)}


@flows_router.post("/v0/orgs/{org_id}/flows", response_model=CreateFlowResponse)
async def create_flow(org_id: str, req: CreateFlowRequest, current_user: User = Depends(get_org_user)):
    db = await _get_db()
    created_at = _now()
    res = await db.flows.insert_one(
        {
            "organization_id": org_id,
            "name": req.name,
            "active": False,
            "active_flow_revid": None,
            "flow_version": 0,
            "created_at": created_at,
            "created_by": current_user.id,
            "updated_at": created_at,
            "updated_by": current_user.id,
        }
    )
    flow_id = str(res.inserted_id)
    header = await db.flows.find_one({"_id": ObjectId(flow_id)})
    return {"flow": FlowHeader(flow_id=flow_id, **{k: header[k] for k in header if k != "_id"})}


@flows_router.get("/v0/orgs/{org_id}/flows", response_model=ListFlowsResponse)
async def list_flows(
    org_id: str,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_org_user),
):
    db = await _get_db()
    total = await db.flows.count_documents({"organization_id": org_id})
    headers = await db.flows.find({"organization_id": org_id}).sort([("updated_at", -1)]).skip(offset).limit(limit).to_list(limit)
    items: list[dict[str, Any]] = []
    for h in headers:
        fid = str(h["_id"])
        latest = await db.flow_revisions.find_one({"flow_id": fid}, sort=[("flow_version", -1)])
        items.append(
            {
                "flow": {
                    "flow_id": fid,
                    "organization_id": h["organization_id"],
                    "name": h["name"],
                    "active": bool(h.get("active")),
                    "active_flow_revid": h.get("active_flow_revid"),
                    "flow_version": int(h.get("flow_version") or 0),
                    "created_at": h["created_at"],
                    "created_by": h["created_by"],
                    "updated_at": h["updated_at"],
                    "updated_by": h["updated_by"],
                },
                "latest_revision": None if not latest else {"flow_revid": str(latest["_id"]), "flow_version": latest["flow_version"], "graph_hash": latest.get("graph_hash")},
            }
        )
    return {"items": items, "total": total}


@flows_router.get("/v0/orgs/{org_id}/flows/{flow_id}")
async def get_flow(org_id: str, flow_id: str, current_user: User = Depends(get_org_user)):
    db = await _get_db()
    h = await db.flows.find_one({"_id": ObjectId(flow_id), "organization_id": org_id})
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
            "created_at": h["created_at"],
            "created_by": h["created_by"],
            "updated_at": h["updated_at"],
            "updated_by": h["updated_by"],
        },
        "latest_revision": None if not latest else {"flow_revid": str(latest["_id"]), "flow_version": latest["flow_version"], "graph_hash": latest.get("graph_hash")},
    }


@flows_router.patch("/v0/orgs/{org_id}/flows/{flow_id}")
async def patch_flow_name(org_id: str, flow_id: str, req: PatchFlowRequest, current_user: User = Depends(get_org_user)):
    db = await _get_db()
    res = await db.flows.update_one(
        {"_id": ObjectId(flow_id), "organization_id": org_id},
        {"$set": {"name": req.name, "updated_at": _now(), "updated_by": current_user.id}},
    )
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Flow not found")
    return await get_flow(org_id, flow_id, current_user)


@flows_router.get("/v0/orgs/{org_id}/flows/{flow_id}/revisions")
async def list_revisions(
    org_id: str,
    flow_id: str,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_org_user),
):
    db = await _get_db()
    h = await db.flows.find_one({"_id": ObjectId(flow_id), "organization_id": org_id})
    if not h:
        raise HTTPException(status_code=404, detail="Flow not found")
    total = await db.flow_revisions.count_documents({"flow_id": flow_id})
    revs = await db.flow_revisions.find({"flow_id": flow_id}).sort([("flow_version", -1)]).skip(offset).limit(limit).to_list(limit)
    items = []
    for r in revs:
        items.append({"flow_revid": str(r["_id"]), "flow_version": r["flow_version"], "graph_hash": r.get("graph_hash"), "created_at": r["created_at"], "created_by": r["created_by"]})
    return {"items": items, "total": total}


@flows_router.get("/v0/orgs/{org_id}/flows/{flow_id}/revisions/{flow_revid}")
async def get_revision(org_id: str, flow_id: str, flow_revid: str, current_user: User = Depends(get_org_user)):
    db = await _get_db()
    h = await db.flows.find_one({"_id": ObjectId(flow_id), "organization_id": org_id})
    if not h:
        raise HTTPException(status_code=404, detail="Flow not found")
    r = await db.flow_revisions.find_one({"_id": ObjectId(flow_revid), "flow_id": flow_id})
    if not r:
        raise HTTPException(status_code=404, detail="Revision not found")
    r["_id"] = str(r["_id"])
    return r


@flows_router.put("/v0/orgs/{org_id}/flows/{flow_id}", response_model=SaveFlowResponse)
async def save_revision(org_id: str, flow_id: str, req: SaveFlowRequest, current_user: User = Depends(get_org_user)):
    db = await _get_db()
    h = await db.flows.find_one({"_id": ObjectId(flow_id), "organization_id": org_id})
    if not h:
        raise HTTPException(status_code=404, detail="Flow not found")

    latest = await db.flow_revisions.find_one({"flow_id": flow_id}, sort=[("flow_version", -1)])
    if latest and str(latest["_id"]) != req.base_flow_revid:
        raise HTTPException(status_code=409, detail="base_flow_revid is not the latest revision")

    # Coerce connections into NodeConnection dataclasses for validation and storage.
    def _coerce_connections(raw: dict[str, Any]) -> Connections:
        out: Connections = {}
        for src, typed in (raw or {}).items():
            out[src] = {}
            main_slots = (typed or {}).get("main") or []
            slots = []
            for slot in main_slots:
                if slot is None:
                    slots.append(None)
                    continue
                conns = []
                for c in slot:
                    conns.append(NodeConnection(node=c["node"], type=c.get("type") or "main", index=int(c["index"])))
                slots.append(conns)
            out[src]["main"] = slots
        return out

    nodes = req.nodes
    connections = _coerce_connections(req.connections)
    settings = req.settings or {}
    pin_data = req.pin_data

    try:
        validate_revision(nodes, connections, settings, pin_data)
    except FlowValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))

    ghash = canonical_graph_hash(nodes, req.connections, settings)

    # Name-only update if graph unchanged.
    if latest and latest.get("graph_hash") == ghash and req.name != h.get("name"):
        await db.flows.update_one(
            {"_id": ObjectId(flow_id)},
            {"$set": {"name": req.name, "updated_at": _now(), "updated_by": current_user.id}},
        )
        h2 = await db.flows.find_one({"_id": ObjectId(flow_id)})
        return {
            "flow": FlowHeader(flow_id=flow_id, **{k: h2[k] for k in h2 if k != "_id"}),
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
            "created_by": current_user.id,
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
                "updated_by": current_user.id,
            }
        },
    )
    h2 = await db.flows.find_one({"_id": ObjectId(flow_id)})
    r = await db.flow_revisions.find_one({"_id": ObjectId(flow_revid)})
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
        created_at=r["created_at"],
        created_by=r["created_by"],
    )
    return {"flow": FlowHeader(flow_id=flow_id, **{k: h2[k] for k in h2 if k != "_id"}), "revision": rev}


@flows_router.post("/v0/orgs/{org_id}/flows/{flow_id}/activate")
async def activate_flow(org_id: str, flow_id: str, req: ActivateFlowRequest = Body(default={}), current_user: User = Depends(get_org_user)):
    db = await _get_db()
    h = await db.flows.find_one({"_id": ObjectId(flow_id), "organization_id": org_id})
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
        {"$set": {"active": True, "active_flow_revid": target, "updated_at": _now(), "updated_by": current_user.id}},
    )
    return await get_flow(org_id, flow_id, current_user)


@flows_router.post("/v0/orgs/{org_id}/flows/{flow_id}/deactivate")
async def deactivate_flow(org_id: str, flow_id: str, current_user: User = Depends(get_org_user)):
    db = await _get_db()
    res = await db.flows.update_one(
        {"_id": ObjectId(flow_id), "organization_id": org_id},
        {"$set": {"active": False, "active_flow_revid": None, "updated_at": _now(), "updated_by": current_user.id}},
    )
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Flow not found")
    return await get_flow(org_id, flow_id, current_user)


@flows_router.post("/v0/orgs/{org_id}/flows/{flow_id}/run")
async def run_flow(org_id: str, flow_id: str, req: RunFlowRequest, current_user: User = Depends(get_org_user)):
    db = await _get_db()
    h = await db.flows.find_one({"_id": ObjectId(flow_id), "organization_id": org_id})
    if not h:
        raise HTTPException(status_code=404, detail="Flow not found")
    flow_revid = req.flow_revid
    if not flow_revid:
        latest = await db.flow_revisions.find_one({"flow_id": flow_id}, sort=[("flow_version", -1)])
        if not latest:
            raise HTTPException(status_code=400, detail="Flow has no revisions")
        flow_revid = str(latest["_id"])

    exec_doc = {
        "flow_id": flow_id,
        "flow_revid": flow_revid,
        "organization_id": org_id,
        "mode": "manual",
        "status": "running",
        "started_at": _now(),
        "finished_at": None,
        "last_heartbeat_at": _now(),
        "stop_requested": False,
        "last_node_executed": None,
        "wait_till": None,
        "retry_of": None,
        "parent_execution_id": None,
        "run_data": {},
        "error": None,
        "trigger": {"type": "manual", "document_id": req.document_id},
    }
    res = await db.flow_executions.insert_one(exec_doc)
    exec_id = str(res.inserted_id)

    await ad.queue.send_msg(ad.common.get_analytiq_client(), "flow_run", msg={
        "flow_id": flow_id,
        "flow_revid": flow_revid,
        "execution_id": exec_id,
        "organization_id": org_id,
        "trigger": exec_doc["trigger"],
    })
    return {"execution_id": exec_id}


@flows_router.get("/v0/orgs/{org_id}/flows/{flow_id}/executions", response_model=ListExecutionsResponse)
async def list_executions(
    org_id: str,
    flow_id: str,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_org_user),
):
    db = await _get_db()
    total = await db.flow_executions.count_documents({"flow_id": flow_id, "organization_id": org_id})
    docs = await db.flow_executions.find({"flow_id": flow_id, "organization_id": org_id}).sort([("started_at", -1)]).skip(offset).limit(limit).to_list(limit)
    items = []
    for d in docs:
        items.append(
            FlowExecution(
                execution_id=str(d["_id"]),
                flow_id=d["flow_id"],
                flow_revid=d["flow_revid"],
                organization_id=d["organization_id"],
                mode=d["mode"],
                status=d["status"],
                started_at=d["started_at"],
                finished_at=d.get("finished_at"),
                last_heartbeat_at=d.get("last_heartbeat_at"),
                stop_requested=bool(d.get("stop_requested")),
                last_node_executed=d.get("last_node_executed"),
                run_data=d.get("run_data") or {},
                error=d.get("error"),
                trigger=d.get("trigger") or {},
            )
        )
    return {"items": items, "total": total}


@flows_router.get("/v0/orgs/{org_id}/flows/{flow_id}/executions/{exec_id}", response_model=FlowExecution)
async def get_execution(org_id: str, flow_id: str, exec_id: str, current_user: User = Depends(get_org_user)):
    db = await _get_db()
    d = await db.flow_executions.find_one({"_id": ObjectId(exec_id), "flow_id": flow_id, "organization_id": org_id})
    if not d:
        raise HTTPException(status_code=404, detail="Execution not found")
    return FlowExecution(
        execution_id=str(d["_id"]),
        flow_id=d["flow_id"],
        flow_revid=d["flow_revid"],
        organization_id=d["organization_id"],
        mode=d["mode"],
        status=d["status"],
        started_at=d["started_at"],
        finished_at=d.get("finished_at"),
        last_heartbeat_at=d.get("last_heartbeat_at"),
        stop_requested=bool(d.get("stop_requested")),
        last_node_executed=d.get("last_node_executed"),
        run_data=d.get("run_data") or {},
        error=d.get("error"),
        trigger=d.get("trigger") or {},
    )


@flows_router.post("/v0/orgs/{org_id}/flows/{flow_id}/executions/{exec_id}/stop")
async def stop_execution(org_id: str, flow_id: str, exec_id: str, current_user: User = Depends(get_org_user)):
    db = await _get_db()
    res = await db.flow_executions.update_one(
        {"_id": ObjectId(exec_id), "flow_id": flow_id, "organization_id": org_id},
        {"$set": {"stop_requested": True}},
    )
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Execution not found")
    return {"ok": True}


@flows_router.post("/v0/webhooks/{webhook_id}")
async def inbound_webhook(webhook_id: str, request: Request):
    # Minimal v1: route via `flow_webhook_routes` lookup and enqueue.
    db = await _get_db()
    route = await db.flow_webhook_routes.find_one({"_id": webhook_id})
    if not route:
        raise HTTPException(status_code=404, detail="Unknown webhook")
    body = None
    try:
        body = await request.json()
    except Exception:
        body = {"raw": (await request.body()).decode("utf-8", errors="replace")}
    exec_doc = {
        "flow_id": route["flow_id"],
        "flow_revid": route["flow_revid"],
        "organization_id": route["organization_id"],
        "mode": "webhook",
        "status": "running",
        "started_at": _now(),
        "finished_at": None,
        "last_heartbeat_at": _now(),
        "stop_requested": False,
        "last_node_executed": None,
        "wait_till": None,
        "retry_of": None,
        "parent_execution_id": None,
        "run_data": {},
        "error": None,
        "trigger": {"type": "webhook", "webhook_id": webhook_id, "method": request.method, "headers": dict(request.headers), "body": body},
    }
    res = await db.flow_executions.insert_one(exec_doc)
    exec_id = str(res.inserted_id)
    await ad.queue.send_msg(ad.common.get_analytiq_client(), "flow_run", msg={
        "flow_id": route["flow_id"],
        "flow_revid": route["flow_revid"],
        "execution_id": exec_id,
        "organization_id": route["organization_id"],
        "trigger": exec_doc["trigger"],
    })
    return {"execution_id": exec_id}

