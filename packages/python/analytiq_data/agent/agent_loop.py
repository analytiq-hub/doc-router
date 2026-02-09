"""
Core agent loop: LLM call -> tool_calls -> pause (or execute if auto_approve) -> loop.
Used by chat and approve endpoints.
"""
from __future__ import annotations

import json
import logging
from typing import Any

import analytiq_data as ad
import litellm

from .session import generate_turn_id, set_turn_state, get_turn_state, clear_turn_state
from .system_prompt import build_system_message
from .tool_registry import TOOL_DEFINITIONS, execute_tool

logger = logging.getLogger(__name__)

MAX_TOOL_ROUNDS = 10


def _tool_call_to_dict(tc: Any) -> dict:
    """Convert litellm tool_call object to dict with id, function.name, function.arguments."""
    tid = getattr(tc, "id", None) or getattr(tc, "id", "")
    name = tc.function.name if hasattr(tc, "function") else tc.get("function", {}).get("name", "")
    args = tc.function.arguments if hasattr(tc, "function") else tc.get("function", {}).get("arguments", "{}")
    return {"id": tid, "name": name, "arguments": args}


def _tool_call_ids(msg: dict) -> list[str]:
    """Extract tool call ids from an assistant message."""
    tcs = msg.get("tool_calls") or []
    return [
        tc.get("id") if isinstance(tc, dict) else getattr(tc, "id", "")
        for tc in tcs
        if tc
    ]


def _sanitize_messages_for_llm(messages: list[dict]) -> list[dict]:
    """
    Ensure every assistant message with tool_calls is immediately followed by
    tool_result (role "tool") messages. If not (e.g. after reload from thread),
    drop tool_calls from that assistant message so the API receives a valid sequence.
    """
    out: list[dict] = []
    i = 0
    while i < len(messages):
        m = messages[i]
        role = m.get("role")
        if role != "assistant" or not m.get("tool_calls"):
            # Forward user, tool, or assistant-without-tool-calls as-is
            if role == "user" and m.get("content") is not None:
                out.append({"role": "user", "content": m.get("content")})
            elif role == "assistant":
                out.append({"role": "assistant", "content": m.get("content") or ""})
            elif role == "tool":
                out.append({"role": "tool", "tool_call_id": m["tool_call_id"], "content": m["content"]})
            i += 1
            continue
        # Assistant with tool_calls: need matching tool results next
        want_ids = set(_tool_call_ids(m))
        if not want_ids:
            out.append({"role": "assistant", "content": m.get("content")})
            i += 1
            continue
        # Peek ahead for role "tool" messages that cover want_ids
        got_ids: set[str] = set()
        j = i + 1
        while j < len(messages) and messages[j].get("role") == "tool":
            got_ids.add(messages[j].get("tool_call_id") or "")
            j += 1
        if got_ids >= want_ids:
            # Full set of tool results present; append assistant + tool messages
            out.append({
                "role": "assistant",
                "content": m.get("content"),
                "tool_calls": m["tool_calls"],
            })
            i += 1
            while i < len(messages) and messages[i].get("role") == "tool":
                out.append({"role": "tool", "tool_call_id": messages[i]["tool_call_id"], "content": messages[i]["content"]})
                i += 1
        else:
            # Missing tool results (e.g. user navigated away and came back); send assistant as content-only
            out.append({"role": "assistant", "content": m.get("content") or ""})
            i += 1
    return out


async def _execute_tool_calls(
    context: dict,
    tool_calls: list[dict],
    approvals: dict[str, bool] | None = None,
) -> tuple[list[dict], list[dict]]:
    """
    Execute tool calls. approvals: call_id -> True (approve) or False (reject).
    If approvals is None, treat all as approved.
    Returns (assistant_message, tool_result_messages).
    """
    assistant_msg = {
        "role": "assistant",
        "content": None,
        "tool_calls": [
            {
                "id": tc["id"],
                "type": "function",
                "function": {"name": tc["name"], "arguments": tc["arguments"]},
            }
            for tc in tool_calls
        ],
    }
    tool_messages = []
    for tc in tool_calls:
        call_id = tc["id"]
        approved = approvals is None or approvals.get(call_id, False)
        if approved:
            result_str = await execute_tool(tc["name"], context, tc["arguments"])
            tool_messages.append({"role": "tool", "tool_call_id": call_id, "content": result_str})
        else:
            tool_messages.append({
                "role": "tool",
                "tool_call_id": call_id,
                "content": json.dumps({"error": "User rejected this action."}),
            })
    return assistant_msg, tool_messages


async def run_agent_turn(
    analytiq_client: Any,
    organization_id: str,
    document_id: str,
    user_id: str,
    messages: list[dict],
    model: str,
    auto_approve: bool,
    resolved_mentions: list[dict] | None = None,
    working_state: dict | None = None,
) -> dict[str, Any]:
    """
    Run one or more agent steps. If auto_approve is False and the LLM returns tool_calls,
    saves state and returns turn_id + pending tool_calls. If auto_approve is True or
    no tool_calls, runs until done and returns text (and optionally tool_calls for audit).
    """
    if working_state is None:
        working_state = {"schema_revid": None, "prompt_revid": None, "extraction": None}
    context = {
        "analytiq_client": analytiq_client,
        "organization_id": organization_id,
        "document_id": document_id,
        "created_by": user_id,
        "working_state": working_state,
    }
    system_content = await build_system_message(
        analytiq_client, organization_id, document_id, working_state, resolved_mentions
    )
    sanitized = _sanitize_messages_for_llm(messages)
    llm_messages = [{"role": "system", "content": system_content}]
    for m in sanitized:
        role = m.get("role")
        content = m.get("content")
        if role == "user" and content is not None:
            llm_messages.append({"role": "user", "content": content})
        elif role == "assistant" and m.get("tool_calls"):
            llm_messages.append({
                "role": "assistant",
                "content": m.get("content"),
                "tool_calls": m["tool_calls"],
            })
        elif role == "assistant" and content is not None:
            llm_messages.append({"role": "assistant", "content": content})
        elif role == "tool":
            llm_messages.append({"role": "tool", "tool_call_id": m["tool_call_id"], "content": m["content"]})

    llm_provider = ad.llm.get_llm_model_provider(model)
    api_key = await ad.llm.get_llm_key(analytiq_client, llm_provider)
    if not api_key:
        return {"error": f"No API key for model {model}"}
    aws_access_key_id = aws_secret_access_key = aws_region_name = None
    if llm_provider == "bedrock":
        aws = await ad.aws.get_aws_client_async(analytiq_client, region_name="us-east-1")
        aws_access_key_id = aws.aws_access_key_id
        aws_secret_access_key = aws.aws_secret_access_key
        aws_region_name = aws.region_name

    iteration = 0
    while iteration < MAX_TOOL_ROUNDS:
        iteration += 1
        try:
            spu_cost = await ad.payments.get_spu_cost(model)
            await ad.payments.check_spu_limits(organization_id, spu_cost)
        except Exception as e:
            return {"error": str(e)}
        response = await ad.llm.agent_completion(
            model=model,
            messages=llm_messages,
            api_key=api_key,
            aws_access_key_id=aws_access_key_id,
            aws_secret_access_key=aws_secret_access_key,
            aws_region_name=aws_region_name,
            tools=TOOL_DEFINITIONS,
            tool_choice="auto",
        )
        message = response.choices[0].message
        tool_calls = message.tool_calls if hasattr(message, "tool_calls") and message.tool_calls else []
        text = (message.content or "").strip()

        if not tool_calls:
            return {"text": text, "working_state": working_state}

        pending = [_tool_call_to_dict(tc) for tc in tool_calls]
        if not auto_approve:
            turn_id = generate_turn_id()
            set_turn_state(turn_id, {
                "messages": messages,
                "llm_messages": llm_messages,
                "pending_tool_calls": pending,
                "working_state": dict(working_state),
                "model": model,
                "organization_id": organization_id,
                "document_id": document_id,
                "user_id": user_id,
                "resolved_mentions": resolved_mentions,
                "system_content": system_content,
            })
            return {
                "turn_id": turn_id,
                "text": text,
                "tool_calls": pending,
                "working_state": working_state,
            }

        assistant_msg, tool_msgs = await _execute_tool_calls(context, pending, approvals=None)
        llm_messages.append(assistant_msg)
        for tm in tool_msgs:
            llm_messages.append(tm)

    return {"text": "(Max tool rounds reached.)", "working_state": working_state}


async def run_agent_approve(
    turn_id: str,
    approvals: list[dict],
) -> dict[str, Any]:
    """
    Continue from a paused turn: apply approvals, execute tools, call LLM once.
    Returns either final text or a new turn_id + pending tool_calls (one LLM step per approve).
    Intentional: the approve path does not loop; each POST /chat/approve is one round.
    approvals: [ {"call_id": "...", "approved": true|false}, ... ]
    """
    state = get_turn_state(turn_id)
    if not state:
        return {"error": "Turn expired or not found"}
    clear_turn_state(turn_id)
    approval_map = {a["call_id"]: a["approved"] for a in approvals if "call_id" in a and "approved" in a}
    context = {
        "analytiq_client": ad.common.get_analytiq_client(),
        "organization_id": state["organization_id"],
        "document_id": state["document_id"],
        "created_by": state["user_id"],
        "working_state": state["working_state"],
    }
    llm_messages = list(state["llm_messages"])
    pending = state["pending_tool_calls"]
    assistant_msg, tool_msgs = await _execute_tool_calls(context, pending, approval_map)
    llm_messages.append(assistant_msg)
    for tm in tool_msgs:
        llm_messages.append(tm)

    model = state["model"]
    llm_provider = ad.llm.get_llm_model_provider(model)
    api_key = await ad.llm.get_llm_key(context["analytiq_client"], llm_provider)
    aws_access_key_id = aws_secret_access_key = aws_region_name = None
    if llm_provider == "bedrock":
        aws = await ad.aws.get_aws_client_async(context["analytiq_client"], region_name="us-east-1")
        aws_access_key_id, aws_secret_access_key = aws.aws_access_key_id, aws.aws_secret_access_key
        aws_region_name = aws.region_name

    try:
        spu_cost = await ad.payments.get_spu_cost(model)
        await ad.payments.check_spu_limits(state["organization_id"], spu_cost)
    except Exception as e:
        return {"error": str(e)}

    response = await ad.llm.agent_completion(
        model=model,
        messages=llm_messages,
        api_key=api_key,
        aws_access_key_id=aws_access_key_id,
        aws_secret_access_key=aws_secret_access_key,
        aws_region_name=aws_region_name,
        tools=TOOL_DEFINITIONS,
        tool_choice="auto",
    )
    message = response.choices[0].message
    tool_calls = message.tool_calls if hasattr(message, "tool_calls") and message.tool_calls else []
    text = (message.content or "").strip()

    if not tool_calls:
        return {"text": text, "working_state": state["working_state"]}

    pending = [_tool_call_to_dict(tc) for tc in tool_calls]
    new_turn_id = generate_turn_id()
    set_turn_state(new_turn_id, {
        "messages": state["messages"],
        "llm_messages": llm_messages,
        "pending_tool_calls": pending,
        "working_state": dict(state["working_state"]),
        "model": model,
        "organization_id": state["organization_id"],
        "document_id": state["document_id"],
        "user_id": state["user_id"],
        "resolved_mentions": state.get("resolved_mentions"),
        "system_content": state.get("system_content"),
    })
    return {
        "turn_id": new_turn_id,
        "text": text,
        "tool_calls": pending,
        "working_state": state["working_state"],
    }
