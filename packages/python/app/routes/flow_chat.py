"""HTTP routes for Chat Trigger flow execution."""

from __future__ import annotations

import asyncio
import logging
import uuid
from typing import Any

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field

import analytiq_data as ad
from analytiq_data.flows.agent_loop.stream import ndjson_line
from app.auth import User, get_org_user
from app.routes.flows import FlowRevisionSnapshotRequest, _get_db, _now, _resolve_flow_revid_lineage

chat_router = APIRouter()
logger = logging.getLogger(__name__)


class ChatMessageRequest(BaseModel):
    chatInput: str = Field(..., min_length=1)
    sessionId: str | None = None


class ChatTestRequest(BaseModel):
    chatInput: str = Field(..., min_length=1)
    sessionId: str | None = None
    flow_revid: str | None = None
    revision_snapshot: FlowRevisionSnapshotRequest


def _last_node_from_run_data(run_data: dict[str, Any]) -> str | None:
    best_id: str | None = None
    best_idx = -1
    for node_id, raw in run_data.items():
        if not isinstance(raw, dict):
            continue
        idx = raw.get("execution_index")
        if isinstance(idx, int) and idx > best_idx:
            best_idx = idx
            best_id = str(node_id)
    return best_id


def _stored_run_data(run_data: dict[str, Any]) -> dict[str, Any]:
    from analytiq_data.flows.engine import _bson_serialize_run_data

    return _bson_serialize_run_data(run_data)


def _execution_error_from_run_data(run_data: dict[str, Any]) -> dict[str, Any] | None:
    for raw in run_data.values():
        if not isinstance(raw, dict) or raw.get("status") != "error":
            continue
        err = raw.get("error")
        if isinstance(err, dict):
            return err
    return None


def _find_chat_trigger(revision: dict[str, Any]) -> dict[str, Any]:
    nodes = revision.get("nodes") or []
    found: dict[str, Any] | None = None
    for n in nodes:
        if isinstance(n, dict) and n.get("type") == "flows.trigger.chat":
            if found is not None:
                raise HTTPException(status_code=400, detail="Flow has multiple Chat Trigger nodes")
            found = n
    if found is None:
        raise HTTPException(status_code=400, detail="Flow has no Chat Trigger node")
    return found


def _revision_from_snapshot(snap: FlowRevisionSnapshotRequest) -> dict[str, Any]:
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
    return {
        "nodes": nodes,
        "connections": snap.connections,
        "settings": settings,
        "pin_data": pin_data,
    }


async def _assert_flow_in_org(db, *, organization_id: str, flow_id: str) -> None:
    try:
        flow_oid = ObjectId(flow_id)
    except Exception:
        raise HTTPException(status_code=404, detail="Flow not found") from None
    flow_doc = await db.flows.find_one({"_id": flow_oid, "organization_id": organization_id})
    if not flow_doc:
        raise HTTPException(status_code=404, detail="Flow not found")


async def _run_chat_flow(
    *,
    db,
    organization_id: str,
    flow_id: str,
    flow_revid: str,
    revision: dict[str, Any],
    chat_input: str,
    session_id: str,
    revision_snapshot: dict[str, Any] | None = None,
) -> tuple[str, ad.flows.ExecutionContext, dict[str, Any], str]:
    chat_node = _find_chat_trigger(revision)
    params = chat_node.get("parameters") or {}
    response_mode = str(params.get("response_mode") or "streaming")

    exec_id = str(ObjectId())
    trigger_data = {
        "type": "chat",
        "chatInput": chat_input,
        "session_id": session_id,
        "sessionId": session_id,
    }

    exec_doc: dict[str, Any] = {
        "_id": ObjectId(exec_id),
        "flow_id": flow_id,
        "flow_revid": flow_revid,
        "organization_id": organization_id,
        "mode": "chat",
        "status": "running",
        "started_at": _now(),
        "finished_at": None,
        "run_data": {},
        "trigger": trigger_data,
        "start_trigger_node_id": chat_node["id"],
    }
    if revision_snapshot is not None:
        exec_doc["revision_snapshot"] = revision_snapshot

    await db.flow_executions.insert_one(exec_doc)

    aq_client = ad.common.get_analytiq_client()
    ctx = ad.flows.ExecutionContext(
        organization_id=organization_id,
        execution_id=exec_id,
        flow_id=flow_id,
        flow_revid=flow_revid,
        mode="chat",
        trigger_data=trigger_data,
        run_data={},
        analytiq_client=aq_client,
    )
    return exec_id, ctx, chat_node, response_mode


def _streaming_response(
    *,
    db,
    exec_id: str,
    session_id: str,
    ctx: ad.flows.ExecutionContext,
    revision: dict[str, Any],
    chat_node: dict[str, Any],
) -> StreamingResponse:
    queue: asyncio.Queue[dict[str, Any] | None] = asyncio.Queue()

    async def sink(event: dict[str, Any]) -> None:
        await queue.put(event)

    ctx.is_streaming = True
    ctx.stream_sink = sink

    async def run_flow_task() -> None:
        status = "success"
        try:
            result = await ad.flows.run_flow(
                context=ctx,
                revision=revision,
                start_trigger_node_id=str(chat_node["id"]),
            )
            status = str(result.get("status") or "success")
        except Exception as e:
            await queue.put({"type": "error", "message": str(e)})
            status = "error"
        finally:
            try:
                await db.flow_executions.update_one(
                    {"_id": ObjectId(exec_id)},
                    {
                        "$set": {
                            "status": status,
                            "finished_at": _now(),
                            "run_data": _stored_run_data(ctx.run_data),
                            "last_node_executed": _last_node_from_run_data(ctx.run_data),
                            "error": _execution_error_from_run_data(ctx.run_data),
                        }
                    },
                )
            except Exception:
                logger.exception(f"flow chat: failed to finalize execution {exec_id}")
            await queue.put(None)

    asyncio.create_task(run_flow_task())

    async def stream_body():
        yield ndjson_line(
            {
                "type": "meta",
                "execution_id": exec_id,
                "session_id": session_id,
            }
        )
        while True:
            event = await queue.get()
            if event is None:
                break
            yield ndjson_line(event)

    return StreamingResponse(
        stream_body(),
        media_type="application/x-ndjson",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "Transfer-Encoding": "chunked",
        },
    )


async def _buffered_response(
    *,
    db,
    exec_id: str,
    ctx: ad.flows.ExecutionContext,
    revision: dict[str, Any],
    chat_node: dict[str, Any],
    session_id: str,
) -> JSONResponse:
    status = "success"
    try:
        result = await asyncio.wait_for(
            ad.flows.run_flow(
                context=ctx,
                revision=revision,
                start_trigger_node_id=str(chat_node["id"]),
            ),
            timeout=25.0,
        )
        status = str(result.get("status") or "success")
    except asyncio.TimeoutError:
        raise HTTPException(status_code=504, detail="Chat flow execution timed out") from None
    except Exception as e:
        status = "error"
        await db.flow_executions.update_one(
            {"_id": ObjectId(exec_id)},
            {
                "$set": {
                    "status": status,
                    "finished_at": _now(),
                    "run_data": _stored_run_data(ctx.run_data),
                    "error": ad.flows.execution_error_envelope(e),
                }
            },
        )
        raise HTTPException(status_code=500, detail=str(e)) from e

    payload = ad.flows.extract_last_node_output_json(
        ctx.run_data,
        revision,
        start_trigger_node_id=str(chat_node["id"]),
    )
    text = ""
    if isinstance(payload, dict):
        text = str(payload.get("agent_output") or payload.get("text") or "")
    elif payload is not None:
        text = str(payload)

    await db.flow_executions.update_one(
        {"_id": ObjectId(exec_id)},
        {
            "$set": {
                "status": status,
                "finished_at": _now(),
                "run_data": _stored_run_data(ctx.run_data),
                "last_node_executed": _last_node_from_run_data(ctx.run_data),
                "error": _execution_error_from_run_data(ctx.run_data),
            }
        },
    )

    return JSONResponse(
        {"text": text, "session_id": session_id, "execution_id": exec_id},
    )


@chat_router.post("/v0/orgs/{organization_id}/flows/{flow_id}/chat/test")
async def post_flow_chat_test(
    organization_id: str,
    flow_id: str,
    body: ChatTestRequest,
    current_user: User = Depends(get_org_user),
):
    """Run Chat Trigger against an editor snapshot (activation not required)."""

    _ = current_user
    db = await _get_db()
    await _assert_flow_in_org(db, organization_id=organization_id, flow_id=flow_id)

    revision = _revision_from_snapshot(body.revision_snapshot)
    revision_snapshot = {
        "nodes": revision["nodes"],
        "connections": revision["connections"],
        "settings": revision["settings"],
        "pin_data": revision["pin_data"],
    }
    flow_revid = await _resolve_flow_revid_lineage(flow_id, body.flow_revid, db)
    session_id = (body.sessionId or "").strip() or str(uuid.uuid4())

    exec_id, ctx, chat_node, response_mode = await _run_chat_flow(
        db=db,
        organization_id=organization_id,
        flow_id=flow_id,
        flow_revid=flow_revid,
        revision=revision,
        chat_input=body.chatInput,
        session_id=session_id,
        revision_snapshot=revision_snapshot,
    )

    if response_mode == "streaming":
        return _streaming_response(
            db=db,
            exec_id=exec_id,
            session_id=session_id,
            ctx=ctx,
            revision=revision,
            chat_node=chat_node,
        )

    return await _buffered_response(
        db=db,
        exec_id=exec_id,
        ctx=ctx,
        revision=revision,
        chat_node=chat_node,
        session_id=session_id,
    )


@chat_router.post("/v0/orgs/{organization_id}/flows/{flow_id}/chat")
async def post_flow_chat(
    organization_id: str,
    flow_id: str,
    body: ChatMessageRequest,
    current_user: User = Depends(get_org_user),
):
    _ = current_user
    db = await _get_db()
    try:
        flow_oid = ObjectId(flow_id)
    except Exception:
        raise HTTPException(status_code=404, detail="Flow not found")

    flow_doc = await db.flows.find_one({"_id": flow_oid, "organization_id": organization_id})
    if not flow_doc:
        raise HTTPException(status_code=404, detail="Flow not found")
    if not flow_doc.get("active") or not flow_doc.get("active_flow_revid"):
        raise HTTPException(status_code=409, detail="Flow is not active")

    rev_id = str(flow_doc["active_flow_revid"])
    revision_doc = await db.flow_revisions.find_one({"_id": ObjectId(rev_id), "flow_id": flow_id})
    if not revision_doc:
        raise HTTPException(status_code=404, detail="Active revision not found")

    revision = {
        "nodes": revision_doc.get("nodes") or [],
        "connections": revision_doc.get("connections") or {},
        "settings": revision_doc.get("settings") or {},
        "pin_data": revision_doc.get("pin_data"),
    }
    session_id = (body.sessionId or "").strip() or str(uuid.uuid4())

    exec_id, ctx, chat_node, response_mode = await _run_chat_flow(
        db=db,
        organization_id=organization_id,
        flow_id=flow_id,
        flow_revid=rev_id,
        revision=revision,
        chat_input=body.chatInput,
        session_id=session_id,
    )

    if response_mode == "streaming":
        return _streaming_response(
            db=db,
            exec_id=exec_id,
            session_id=session_id,
            ctx=ctx,
            revision=revision,
            chat_node=chat_node,
        )

    return await _buffered_response(
        db=db,
        exec_id=exec_id,
        ctx=ctx,
        revision=revision,
        chat_node=chat_node,
        session_id=session_id,
    )
