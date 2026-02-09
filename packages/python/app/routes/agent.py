# agent.py — Document chat agent endpoints (chat + approve).

import json
import logging
from typing import Any

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Body
from pydantic import BaseModel, Field

import analytiq_data as ad
from app.auth import get_org_user
from app.models import User

logger = logging.getLogger(__name__)

agent_router = APIRouter(tags=["agent"])


class ChatMessage(BaseModel):
    role: str = Field(..., description="user or assistant")
    content: str | None = None
    tool_calls: list[dict] | None = None
    tool_call_id: str | None = None


class MentionRef(BaseModel):
    type: str = Field(..., description="schema, prompt, or tag")
    id: str = Field(..., description="schema_revid, prompt_revid, or tag_id")


class ChatRequest(BaseModel):
    messages: list[ChatMessage] = Field(..., description="Conversation history")
    mentions: list[MentionRef] = Field(default_factory=list, description="Resolved @ mention refs")
    model: str = Field(default="claude-sonnet-4-20250514", description="LLM model")
    stream: bool = Field(default=False, description="Stream response (SSE)")
    auto_approve: bool = Field(default=False, description="Execute all tool calls without pausing")


class ApproveRequest(BaseModel):
    turn_id: str = Field(..., description="Turn ID from previous chat response")
    approvals: list[dict] = Field(..., description="List of { call_id, approved }")


async def _resolve_mentions(
    analytiq_client,
    organization_id: str,
    mentions: list[dict],
) -> list[dict]:
    """Resolve mention refs to full content for system message."""
    if not mentions:
        return []
    db = ad.common.get_async_db(analytiq_client)
    resolved = []
    for m in mentions:
        typ = m.get("type")
        mid = m.get("id")
        if not typ or not mid:
            continue
        name = ""
        content = ""
        if typ == "schema":
            rev = await db.schema_revisions.find_one({"_id": ObjectId(mid)})
            if rev:
                schema_doc = await db.schemas.find_one(
                    {"_id": ObjectId(rev["schema_id"]), "organization_id": organization_id}
                )
                name = schema_doc["name"] if schema_doc else "Unknown"
                content = json.dumps(rev.get("response_format", {}), indent=2)
            resolved.append({"type": "schema", "name": name, "content": content or "(not found)"})
        elif typ == "prompt":
            rev = await db.prompt_revisions.find_one({"_id": ObjectId(mid)})
            if rev:
                name = rev.get("name", "Unknown")
                content = f"Content:\n{rev.get('content', '')}\n\nSchema ID: {rev.get('schema_id')}\nModel: {rev.get('model')}\nTag IDs: {rev.get('tag_ids', [])}"
            resolved.append({"type": "prompt", "name": name, "content": content or "(not found)"})
        elif typ == "tag":
            tag = await db.tags.find_one(
                {"_id": ObjectId(mid), "organization_id": organization_id}
            )
            if tag:
                name = tag.get("name", "")
                content = f"Name: {name}\nColor: {tag.get('color')}\nDescription: {tag.get('description')}"
            resolved.append({"type": "tag", "name": name or "Unknown", "content": content or "(not found)"})
    return resolved


@agent_router.post("/v0/orgs/{organization_id}/documents/{document_id}/chat")
async def post_chat(
    organization_id: str,
    document_id: str,
    request: ChatRequest = Body(...),
    current_user: User = Depends(get_org_user),
):
    """
    Start or continue a chat turn. If the agent returns tool calls and auto_approve is false,
    the response includes turn_id and tool_calls; use POST .../chat/approve to submit approvals.
    """
    analytiq_client = ad.common.get_analytiq_client()
    doc = await ad.common.doc.get_doc(analytiq_client, document_id, organization_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    mentions_data = [m.model_dump() for m in request.mentions]
    resolved = await _resolve_mentions(analytiq_client, organization_id, mentions_data)
    messages = [m.model_dump() for m in request.messages]
    # Phase 1: streaming not implemented; allow auto_approve without stream. When SSE is added, require stream=True when auto_approve=True.
    result = await ad.agent.run_agent_turn(
        analytiq_client=analytiq_client,
        organization_id=organization_id,
        document_id=document_id,
        user_id=current_user.user_id,
        messages=messages,
        model=request.model,
        auto_approve=request.auto_approve,
        resolved_mentions=resolved,
    )
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@agent_router.post("/v0/orgs/{organization_id}/documents/{document_id}/chat/approve")
async def post_chat_approve(
    organization_id: str,
    document_id: str,
    request: ApproveRequest = Body(...),
    current_user: User = Depends(get_org_user),
):
    """Submit approvals/rejections for pending tool calls; continues the agent turn."""
    doc = await ad.common.doc.get_doc(
        ad.common.get_analytiq_client(), document_id, organization_id
    )
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    result = await ad.agent.run_agent_approve(
        turn_id=request.turn_id,
        approvals=request.approvals,
    )
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result
