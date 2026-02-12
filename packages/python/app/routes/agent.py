# agent.py — Document chat agent endpoints (chat + approve).

import json
import logging
from typing import Any

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Body, Query
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
    thread_id: str | None = Field(default=None, description="If set, append user+assistant messages to this thread after success")
    truncate_thread_to_message_count: int | None = Field(
        default=None,
        description="If set with thread_id, keep only this many messages in the thread before appending (for resubmit-from-turn).",
    )


class ApproveRequest(BaseModel):
    turn_id: str = Field(..., description="Turn ID from previous chat response")
    approvals: list[dict] = Field(..., description="List of { call_id, approved }")
    thread_id: str | None = Field(default=None, description="If set, append assistant message to this thread after success")


class ThreadSummary(BaseModel):
    id: str
    title: str
    created_at: Any
    updated_at: Any


class ThreadDetail(BaseModel):
    id: str
    title: str
    messages: list[dict]
    extraction: dict
    created_at: Any
    updated_at: Any


class CreateThreadBody(BaseModel):
    title: str | None = None


class CreateThreadResponse(BaseModel):
    thread_id: str


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

    if request.thread_id and messages:
        user_msg = messages[-1]
        assistant_msg = {
            "role": "assistant",
            "content": result.get("text"),
            "tool_calls": result.get("tool_calls"),
            "thinking": result.get("thinking"),
        }
        extraction = (result.get("working_state") or {}).get("extraction")
        if request.truncate_thread_to_message_count is not None:
            await ad.agent.agent_threads.truncate_and_append_messages(
                analytiq_client,
                request.thread_id,
                organization_id,
                request.truncate_thread_to_message_count,
                [user_msg, assistant_msg],
                extraction=extraction,
            )
        else:
            await ad.agent.agent_threads.append_messages(
                analytiq_client,
                request.thread_id,
                organization_id,
                [user_msg, assistant_msg],
                extraction=extraction,
            )
        # Optionally set title from first user message
        thread_doc = await ad.agent.agent_threads.get_thread(
            analytiq_client, request.thread_id, organization_id
        )
        if thread_doc and thread_doc.get("title") == "New chat":
            first_content = None
            for m in thread_doc.get("messages", []):
                if m.get("role") == "user" and m.get("content"):
                    first_content = (m.get("content") or "").strip()[:50]
                    break
            if first_content:
                await ad.agent.agent_threads.update_thread_title(
                    analytiq_client, request.thread_id, organization_id, first_content
                )
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

    if request.thread_id:
        assistant_msg = {
            "role": "assistant",
            "content": result.get("text"),
            "tool_calls": result.get("tool_calls"),
            "thinking": result.get("thinking"),
        }
        extraction = (result.get("working_state") or {}).get("extraction")
        await ad.agent.agent_threads.append_messages(
            ad.common.get_analytiq_client(),
            request.thread_id,
            organization_id,
            [assistant_msg],
            extraction=extraction,
        )
    return result


@agent_router.get(
    "/v0/orgs/{organization_id}/documents/{document_id}/chat/threads",
    response_model=list[ThreadSummary],
)
async def list_threads(
    organization_id: str,
    document_id: str,
    limit: int = Query(50, ge=1, le=100),
    current_user: User = Depends(get_org_user),
):
    """List chat threads for the document, most recent first."""
    doc = await ad.common.doc.get_doc(
        ad.common.get_analytiq_client(), document_id, organization_id
    )
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    items = await ad.agent.agent_threads.list_threads(
        ad.common.get_analytiq_client(), organization_id, document_id, limit=limit
    )
    return [ThreadSummary(**x) for x in items]


@agent_router.post(
    "/v0/orgs/{organization_id}/documents/{document_id}/chat/threads",
    response_model=CreateThreadResponse,
)
async def create_thread(
    organization_id: str,
    document_id: str,
    body: CreateThreadBody | None = Body(None),
    current_user: User = Depends(get_org_user),
):
    """Create a new chat thread for the document."""
    doc = await ad.common.doc.get_doc(
        ad.common.get_analytiq_client(), document_id, organization_id
    )
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    title = body.title if body else None
    thread_id = await ad.agent.agent_threads.create_thread(
        ad.common.get_analytiq_client(),
        organization_id,
        document_id,
        current_user.user_id,
        title=title,
    )
    return CreateThreadResponse(thread_id=thread_id)


@agent_router.get(
    "/v0/orgs/{organization_id}/documents/{document_id}/chat/threads/{thread_id}",
    response_model=ThreadDetail,
)
async def get_thread(
    organization_id: str,
    document_id: str,
    thread_id: str,
    current_user: User = Depends(get_org_user),
):
    """Get a thread with full messages and extraction."""
    doc = await ad.common.doc.get_doc(
        ad.common.get_analytiq_client(), document_id, organization_id
    )
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    thread_doc = await ad.agent.agent_threads.get_thread(
        ad.common.get_analytiq_client(), thread_id, organization_id
    )
    if not thread_doc:
        raise HTTPException(status_code=404, detail="Thread not found")
    return ThreadDetail(**thread_doc)


@agent_router.delete(
    "/v0/orgs/{organization_id}/documents/{document_id}/chat/threads/{thread_id}",
)
async def delete_thread(
    organization_id: str,
    document_id: str,
    thread_id: str,
    current_user: User = Depends(get_org_user),
):
    """Delete a chat thread."""
    doc = await ad.common.doc.get_doc(
        ad.common.get_analytiq_client(), document_id, organization_id
    )
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    deleted = await ad.agent.agent_threads.delete_thread(
        ad.common.get_analytiq_client(), thread_id, organization_id
    )
    if not deleted:
        raise HTTPException(status_code=404, detail="Thread not found")
    return {"ok": True}
