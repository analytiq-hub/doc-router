# agent.py — Document chat agent endpoints (chat + approve).

import asyncio
import json
import logging
from typing import Any

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Body, Query
from fastapi.responses import StreamingResponse
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
    auto_approved_tools: list[str] | None = Field(
        default=None,
        description="Read-write tool names that are auto-approved (no pause). Empty = default (only read-only auto-approved).",
    )
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
    model: str | None = None
    created_at: Any
    updated_at: Any


class CreateThreadBody(BaseModel):
    title: str | None = None


class CreateThreadResponse(BaseModel):
    thread_id: str


class ToolsMetadata(BaseModel):
    read_only: list[str]
    read_write: list[str]


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


async def _append_assistant_to_thread(
    analytiq_client,
    organization_id: str,
    request: ChatRequest,
    messages: list[dict],
    result: dict,
    current_user: User,
):
    """Persist user + assistant messages to thread and optionally update title."""
    user_msg = messages[-1]
    assistant_msg = {
        "role": "assistant",
        "content": result.get("text"),
        "tool_calls": result.get("tool_calls"),
        "thinking": result.get("thinking"),
        "executed_rounds": result.get("executed_rounds"),
    }
    extraction = (result.get("working_state") or {}).get("extraction")
    if request.truncate_thread_to_message_count is not None:
        await ad.agent.agent_threads.truncate_and_append_messages(
            analytiq_client,
            request.thread_id,
            organization_id,
            current_user.user_id,
            request.truncate_thread_to_message_count,
            [user_msg, assistant_msg],
            extraction=extraction,
            model=request.model,
        )
    else:
        await ad.agent.agent_threads.append_messages(
            analytiq_client,
            request.thread_id,
            organization_id,
            current_user.user_id,
            [user_msg, assistant_msg],
            extraction=extraction,
            model=request.model,
        )
    thread_doc = await ad.agent.agent_threads.get_thread(
        analytiq_client, request.thread_id, organization_id, current_user.user_id
    )
    if thread_doc and thread_doc.get("title") == "New chat":
        first_content = None
        for m in thread_doc.get("messages", []):
            if m.get("role") == "user" and m.get("content"):
                first_content = (m.get("content") or "").strip()[:50]
                break
        if first_content:
            await ad.agent.agent_threads.update_thread_title(
                analytiq_client, request.thread_id, organization_id, current_user.user_id, first_content
            )


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
    When stream=True, returns SSE stream of thinking, text_chunk, and done events.
    """
    analytiq_client = ad.common.get_analytiq_client()
    doc = await ad.common.doc.get_doc(analytiq_client, document_id, organization_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    mentions_data = [m.model_dump() for m in request.mentions]
    resolved = await _resolve_mentions(analytiq_client, organization_id, mentions_data)
    messages = [m.model_dump() for m in request.messages]
    auto_approved = set(request.auto_approved_tools) if request.auto_approved_tools is not None else None

    if request.stream:
        logger.info("post_chat stream=True: using SSE streaming response")
        queue: asyncio.Queue[tuple[str, Any]] = asyncio.Queue()
        streamed_done: list[bool] = [False]

        async def stream_handler(event_type: str, payload: Any) -> None:
            if event_type == "done":
                streamed_done[0] = True
            await queue.put((event_type, payload))

        async def run_turn() -> None:
            try:
                result = await ad.agent.run_agent_turn(
                    analytiq_client=analytiq_client,
                    organization_id=organization_id,
                    document_id=document_id,
                    user_id=current_user.user_id,
                    messages=messages,
                    model=request.model,
                    auto_approve=request.auto_approve,
                    resolved_mentions=resolved,
                    auto_approved_tools=auto_approved,
                    stream_handler=stream_handler,
                )
                if "error" in result:
                    await queue.put(("error", result["error"]))
                elif not streamed_done[0]:
                    # Early return (e.g. needs_approval): send full result as done so client can handle it
                    await queue.put(("done", result))
            except Exception as e:
                logger.exception("Agent turn failed during streaming")
                await queue.put(("error", str(e)))

        async def generate_sse():
            task = asyncio.create_task(run_turn())
            try:
                while True:
                    event_type, payload = await queue.get()
                    if event_type == "error":
                        yield f"data: {json.dumps({'type': 'error', 'error': payload})}\n\n"
                        break
                    if event_type == "assistant_text_chunk":
                        p = payload if isinstance(payload, dict) else {"chunk": payload}
                        yield f"data: {json.dumps({'type': 'assistant_text_chunk', 'chunk': p.get('chunk', ''), 'round_index': p.get('round_index', 0)})}\n\n"
                    elif event_type == "thinking_chunk":
                        p = payload if isinstance(payload, dict) else {"chunk": payload}
                        yield f"data: {json.dumps({'type': 'thinking_chunk', 'chunk': p.get('chunk', ''), 'round_index': p.get('round_index', 0)})}\n\n"
                    elif event_type == "assistant_text_done":
                        p = payload if isinstance(payload, dict) else {"full_text": payload}
                        yield f"data: {json.dumps({'type': 'assistant_text_done', 'full_text': p.get('full_text', ''), 'round_index': p.get('round_index', 0)})}\n\n"
                    elif event_type == "thinking_done":
                        p = payload if isinstance(payload, dict) else {"thinking": payload}
                        yield f"data: {json.dumps({'type': 'thinking_done', 'thinking': p.get('thinking', ''), 'round_index': p.get('round_index', 0)})}\n\n"
                    elif event_type == "tool_calls":
                        p = payload if isinstance(payload, dict) else {}
                        yield f"data: {json.dumps({'type': 'tool_calls', 'round_index': p.get('round_index', 0), 'tool_calls': p.get('tool_calls', [])})}\n\n"
                    elif event_type == "tool_result":
                        yield f"data: {json.dumps({'type': 'tool_result', **payload})}\n\n" if isinstance(payload, dict) else f"data: {json.dumps({'type': 'tool_result'})}\n\n"
                    elif event_type == "round_executed":
                        p = payload if isinstance(payload, dict) else {}
                        yield f"data: {json.dumps({'type': 'round_executed', 'round_index': p.get('round_index', 0), 'thinking': p.get('thinking'), 'tool_calls': p.get('tool_calls', [])})}\n\n"
                    elif event_type == "done":
                        # Only persist to thread when this is the final response (no pending approval)
                        if request.thread_id and messages and payload.get("turn_id") is None:
                            await _append_assistant_to_thread(
                                analytiq_client, organization_id, request, messages, payload, current_user
                            )
                        yield f"data: {json.dumps({'type': 'done', 'result': payload})}\n\n"
                        break
            finally:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

        return StreamingResponse(
            generate_sse(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    result = await ad.agent.run_agent_turn(
        analytiq_client=analytiq_client,
        organization_id=organization_id,
        document_id=document_id,
        user_id=current_user.user_id,
        messages=messages,
        model=request.model,
        auto_approve=request.auto_approve,
        resolved_mentions=resolved,
        auto_approved_tools=auto_approved,
    )
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])

    if request.thread_id and messages:
        await _append_assistant_to_thread(
            analytiq_client, organization_id, request, messages, result, current_user
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
            "executed_rounds": result.get("executed_rounds"),
        }
        extraction = (result.get("working_state") or {}).get("extraction")
        model = result.get("model")
        await ad.agent.agent_threads.append_messages(
            ad.common.get_analytiq_client(),
            request.thread_id,
            organization_id,
            current_user.user_id,
            [assistant_msg],
            extraction=extraction,
            model=model,
        )
    return result


@agent_router.get(
    "/v0/orgs/{organization_id}/documents/{document_id}/chat/tools",
    response_model=ToolsMetadata,
)
async def get_chat_tools(
    organization_id: str,
    document_id: str,
    current_user: User = Depends(get_org_user),
):
    """Get tool metadata: read-only vs read-write. Read-only tools never require approval."""
    doc = await ad.common.doc.get_doc(
        ad.common.get_analytiq_client(), document_id, organization_id
    )
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return ToolsMetadata(
        read_only=sorted(ad.agent.tool_registry.READ_ONLY_TOOLS),
        read_write=sorted(ad.agent.tool_registry.READ_WRITE_TOOLS),
    )


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
        ad.common.get_analytiq_client(), organization_id, document_id, current_user.user_id, limit=limit
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
        ad.common.get_analytiq_client(), thread_id, organization_id, current_user.user_id
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
        ad.common.get_analytiq_client(), thread_id, organization_id, current_user.user_id
    )
    if not deleted:
        raise HTTPException(status_code=404, detail="Thread not found")
    return {"ok": True}
