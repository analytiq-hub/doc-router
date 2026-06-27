"""Execute wired tool calls for flow agent and tool executor."""

from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Any

from bson import ObjectId

import analytiq_data as ad

from analytiq_data.flows.agent_loop.constants import (
    FLOW_SUBFLOW_MAX_DEPTH,
    FLOW_SUBFLOW_TIMEOUT_SECONDS,
    LLM_TOOL_RESULT_MAX_CHARS,
    TOOL_CONTEXT_NODES_MAX_BYTES,
)
from analytiq_data.flows.agent_loop.types import NormalizedToolCall
from analytiq_data.flows.tool_wiring import WiredTool

logger = logging.getLogger(__name__)


def _truncate_for_llm(text: str) -> str:
    if len(text) <= LLM_TOOL_RESULT_MAX_CHARS:
        return text
    return text[: LLM_TOOL_RESULT_MAX_CHARS - 1] + "…"


def _cap_nodes_snapshot(nodes: dict[str, Any]) -> dict[str, Any]:
    encoded = json.dumps(nodes, default=str).encode("utf-8")
    if len(encoded) <= TOOL_CONTEXT_NODES_MAX_BYTES:
        return nodes
    trimmed: dict[str, Any] = {}
    total = 0
    for key in nodes:
        entry = json.dumps({key: nodes[key]}, default=str).encode("utf-8")
        if total + len(entry) > TOOL_CONTEXT_NODES_MAX_BYTES:
            break
        trimmed[key] = nodes[key]
        total += len(entry)
    return trimmed


def build_tool_context(
    ctx: "ad.flows.ExecutionContext",
    *,
    consumer_node_id: str,
    parent_item: "ad.flows.FlowItem",
    upstream_nodes_snapshot: dict[str, Any] | None = None,
    trigger_snapshot: dict[str, Any] | None = None,
) -> dict[str, Any]:
    nodes = upstream_nodes_snapshot
    if nodes is None:
        nodes = ctx.upstream_json_snapshot or ad.flows.materialize_node_data(ctx.run_data)
    trigger = trigger_snapshot
    if trigger is None:
        trigger = dict(ctx.trigger_snapshot or ctx.trigger_data or {})
    return {
        "organization_id": ctx.organization_id,
        "flow_id": ctx.flow_id,
        "execution_id": ctx.execution_id,
        "consumer_node_id": consumer_node_id,
        "item": parent_item.to_context_dict(),
        "trigger": dict(trigger),
        "nodes": _cap_nodes_snapshot(nodes),
    }


async def _dispatch_tool_code(
    wired: WiredTool,
    arguments: dict[str, Any],
    ctx: "ad.flows.ExecutionContext",
    *,
    consumer_node_id: str,
    parent_item: "ad.flows.FlowItem",
    upstream_nodes_snapshot: dict[str, Any] | None = None,
    trigger_snapshot: dict[str, Any] | None = None,
) -> str:
    params = wired.node.get("parameters") or {}
    code = str(params.get("python_code") or "")
    timeout = float(params.get("timeout_seconds") or 30.0)
    tool_ctx = build_tool_context(
        ctx,
        consumer_node_id=consumer_node_id,
        parent_item=parent_item,
        upstream_nodes_snapshot=upstream_nodes_snapshot,
        trigger_snapshot=trigger_snapshot,
    )
    result, logs = await ad.flows.run_python_tool(
        code=code,
        params=arguments,
        context=tool_ctx,
        timeout_seconds=timeout,
        analytiq_client=ctx.analytiq_client,
        node_id=wired.node_id,
        execution_id=ctx.execution_id,
    )
    if logs:
        ctx.node_logs.setdefault(wired.node_id, []).extend(logs)
    return json.dumps(result, ensure_ascii=False, default=str)


async def _dispatch_kb_tool(
    wired: WiredTool,
    arguments: dict[str, Any],
    ctx: "ad.flows.ExecutionContext",
) -> str:
    params = wired.node.get("parameters") or {}
    kb_id = str(params.get("knowledge_base_id") or "").strip()
    if not kb_id:
        return json.dumps({"error": "Knowledge base not configured"})

    query = arguments.get("query")
    if not isinstance(query, str) or not query.strip():
        return json.dumps({"error": "query is required"})

    top_k = arguments.get("top_k")
    if top_k is None:
        top_k = params.get("default_top_k", 5)
    try:
        top_k = int(top_k)
    except Exception:
        top_k = 5
    top_k = max(1, min(20, top_k))

    coalesce = arguments.get("coalesce_neighbors")
    if coalesce is None:
        coalesce = params.get("default_coalesce_neighbors")

    metadata_filter = arguments.get("metadata_filter")
    if metadata_filter is not None and not isinstance(metadata_filter, dict):
        metadata_filter = None

    try:
        search_results = await ad.kb.search.search_knowledge_base(
            analytiq_client=ctx.analytiq_client,
            kb_id=kb_id,
            query=query,
            organization_id=ctx.organization_id,
            top_k=top_k,
            metadata_filter=metadata_filter,
            coalesce_neighbors=int(coalesce) if coalesce is not None else None,
        )
    except Exception as e:
        msg = str(e)
        if "not found" in msg.lower():
            return json.dumps({"error": "Knowledge base not found"})
        if "not active" in msg.lower() or "inactive" in msg.lower():
            return json.dumps({"error": "Knowledge base is not active"})
        return json.dumps({"error": msg})

    results = search_results.get("results") if isinstance(search_results, dict) else []
    if not isinstance(results, list):
        results = []
    formatted = ad.kb.format_kb_search_results_for_llm(results)
    return formatted


async def _dispatch_flow_tool(
    wired: WiredTool,
    arguments: dict[str, Any],
    ctx: "ad.flows.ExecutionContext",
) -> str:
    params = wired.node.get("parameters") or {}
    target_flow_id = str(params.get("target_flow_id") or "").strip()
    if not target_flow_id:
        return json.dumps({"error": "target_flow_id is not configured"})

    stack = list(ctx.flow_id_stack or [])
    if target_flow_id in stack:
        return json.dumps({"error": "Sub-flow cycle detected"})
    if len(stack) >= FLOW_SUBFLOW_MAX_DEPTH:
        return json.dumps({"error": "Sub-flow depth limit exceeded"})

    client = ctx.analytiq_client
    if client is None or not hasattr(client, "mongodb_async"):
        return json.dumps({"error": "Sub-flow execution requires database client"})

    db = ad.common.get_async_db(client)
    try:
        flow_oid = ObjectId(target_flow_id)
    except Exception:
        return json.dumps({"error": "Invalid target flow id"})

    flow_doc = await db.flows.find_one(
        {"_id": flow_oid, "organization_id": ctx.organization_id},
    )
    if not flow_doc:
        return json.dumps({"error": "Target flow not found"})
    if not flow_doc.get("callable_as_tool"):
        return json.dumps({"error": "Target flow is not callable as a tool"})
    if not flow_doc.get("active") or not flow_doc.get("active_flow_revid"):
        return json.dumps({"error": "Target flow is not active"})

    rev_id = str(flow_doc["active_flow_revid"])
    try:
        revision_doc = await db.flow_revisions.find_one(
            {"_id": ObjectId(rev_id), "flow_id": target_flow_id},
        )
    except Exception:
        revision_doc = None
    if not revision_doc:
        return json.dumps({"error": "Target flow revision not found"})

    revision = {
        "nodes": revision_doc.get("nodes") or [],
        "connections": revision_doc.get("connections") or {},
        "settings": revision_doc.get("settings") or {},
        "pin_data": revision_doc.get("pin_data"),
    }

    tool_trigger_id: str | None = None
    for n in revision["nodes"]:
        if isinstance(n, dict) and n.get("type") == "flows.trigger.tool":
            tool_trigger_id = str(n.get("id") or "")
            break
    if not tool_trigger_id:
        return json.dumps({"error": "Callable flow missing Tool entry trigger"})

    sub_exec_id = str(ObjectId())
    sub_ctx = ad.flows.ExecutionContext(
        organization_id=ctx.organization_id,
        execution_id=sub_exec_id,
        flow_id=target_flow_id,
        flow_revid=rev_id,
        mode="sub_flow_tool",
        trigger_data={"tool_arguments": arguments},
        run_data={},
        analytiq_client=client,
        flow_id_stack=stack + [ctx.flow_id],
    )
    sub_ctx.sub_flow_tool_result = None

    try:
        await asyncio.wait_for(
            ad.flows.run_flow(
                context=sub_ctx,
                revision=revision,
                start_trigger_node_id=tool_trigger_id,
            ),
            timeout=FLOW_SUBFLOW_TIMEOUT_SECONDS,
        )
    except asyncio.TimeoutError:
        return json.dumps({"error": "Sub-flow execution timed out"})
    except Exception as e:
        return json.dumps({"error": str(e)})

    if sub_ctx.sub_flow_tool_result is None:
        return json.dumps({"error": "Callable flow did not reach Respond to tool"})

    if isinstance(sub_ctx.sub_flow_tool_result, str):
        return sub_ctx.sub_flow_tool_result
    return json.dumps(sub_ctx.sub_flow_tool_result, ensure_ascii=False, default=str)


async def execute_tool_call(
    tc: NormalizedToolCall,
    wired: WiredTool,
    ctx: "ad.flows.ExecutionContext",
    *,
    consumer_node_id: str,
    parent_item: "ad.flows.FlowItem",
    upstream_nodes_snapshot: dict[str, Any] | None = None,
    trigger_snapshot: dict[str, Any] | None = None,
) -> str:
    """Run one tool call and return a string for the LLM tool message."""

    if wired.node.get("disabled"):
        return json.dumps({"error": f"Tool node {wired.name} is disabled"})

    if wired.node_type == "flows.tool_code":
        raw = await _dispatch_tool_code(
            wired,
            tc.arguments,
            ctx,
            consumer_node_id=consumer_node_id,
            parent_item=parent_item,
            upstream_nodes_snapshot=upstream_nodes_snapshot,
            trigger_snapshot=trigger_snapshot,
        )
    elif wired.node_type == "flows.kb_tool":
        raw = await _dispatch_kb_tool(wired, tc.arguments, ctx)
    elif wired.node_type == "flows.flow_tool":
        raw = await _dispatch_flow_tool(wired, tc.arguments, ctx)
    else:
        return json.dumps({"error": f"Unsupported tool type: {wired.node_type}"})

    return _truncate_for_llm(raw)
