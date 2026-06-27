"""HTTP routes for Chat Trigger flow execution."""

from __future__ import annotations

import asyncio
import json
import uuid
from datetime import UTC, datetime
from typing import Any

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field

import analytiq_data as ad
from analytiq_data.flows.agent_loop.stream import ndjson_line
from app.auth import User, get_org_user
from app.routes.flows import _get_db, _now

chat_router = APIRouter()


class ChatMessageRequest(BaseModel):
    chatInput: str = Field(..., min_length=1)
    sessionId: str | None = None


def _find_chat_trigger(revision: dict[str, Any]) -> dict[str, Any] | None:
    nodes = revision.get("nodes") or []
    found: dict[str, Any] | None = None
    for n in nodes:
        if isinstance(n, dict) and n.get("type") == "flows.trigger.chat":
            if found is not None:
                raise HTTPException(status_code=400, detail="Flow has multiple Chat Trigger nodes")
            found = n
    return found


@chat_router.post("/v0/orgs/{organization_id}/flows/{flow_id}/chat")
async def post_flow_chat(
    organization_id: str,
    flow_id: str,
    body: ChatMessageRequest,
    request: Request,
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
    chat_node = _find_chat_trigger(revision)
    if not chat_node:
        raise HTTPException(status_code=400, detail="Flow has no Chat Trigger node")

    params = chat_node.get("parameters") or {}
    response_mode = str(params.get("response_mode") or "streaming")
    session_id = (body.sessionId or "").strip() or str(uuid.uuid4())

    exec_id = str(ObjectId())
    trigger_data = {
        "type": "chat",
        "chatInput": body.chatInput,
        "session_id": session_id,
        "sessionId": session_id,
    }

    await db.flow_executions.insert_one(
        {
            "_id": ObjectId(exec_id),
            "flow_id": flow_id,
            "flow_revid": rev_id,
            "organization_id": organization_id,
            "mode": "chat",
            "status": "running",
            "started_at": _now(),
            "finished_at": None,
            "run_data": {},
            "trigger": trigger_data,
            "start_trigger_node_id": chat_node["id"],
        }
    )

    aq_client = ad.common.get_analytiq_client()
    ctx = ad.flows.ExecutionContext(
        organization_id=organization_id,
        execution_id=exec_id,
        flow_id=flow_id,
        flow_revid=rev_id,
        mode="chat",
        trigger_data=trigger_data,
        run_data={},
        analytiq_client=aq_client,
    )

    if response_mode == "streaming":
        queue: asyncio.Queue[dict[str, Any] | None] = asyncio.Queue()

        async def sink(event: dict[str, Any]) -> None:
            await queue.put(event)

        ctx.is_streaming = True
        ctx.stream_sink = sink

        async def run_flow_task() -> None:
            try:
                await ad.flows.run_flow(
                    context=ctx,
                    revision=revision,
                    start_trigger_node_id=str(chat_node["id"]),
                )
            except Exception as e:
                await queue.put({"type": "error", "message": str(e)})
            finally:
                await queue.put(None)

        asyncio.create_task(run_flow_task())

        async def stream_body():
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

    try:
        await asyncio.wait_for(
            ad.flows.run_flow(
                context=ctx,
                revision=revision,
                start_trigger_node_id=str(chat_node["id"]),
            ),
            timeout=25.0,
        )
    except asyncio.TimeoutError:
        raise HTTPException(status_code=504, detail="Chat flow execution timed out")

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
        {"$set": {"status": "success", "finished_at": _now(), "run_data": ctx.run_data}},
    )

    return JSONResponse(
        {"text": text, "session_id": session_id, "execution_id": exec_id},
    )
