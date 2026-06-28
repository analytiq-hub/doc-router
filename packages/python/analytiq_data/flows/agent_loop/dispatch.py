"""Execute wired tool calls for flow agent and tool executor."""

from __future__ import annotations

import json
import logging
import time
from typing import Any

import analytiq_data as ad

from analytiq_data.flows.agent_loop.constants import (
    LLM_TOOL_RESULT_MAX_CHARS,
    TOOL_CONTEXT_NODES_MAX_BYTES,
)
from analytiq_data.flows.sub_flow import SubFlowError, resolve_subflow_return_json, run_nested_subflow
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
    upstream_nodes_snapshot: dict[str, Any],
) -> dict[str, Any]:
    return {
        "organization_id": ctx.organization_id,
        "flow_id": ctx.flow_id,
        "execution_id": ctx.execution_id,
        "consumer_node_id": consumer_node_id,
        "item": parent_item.to_context_dict(),
        "trigger": dict(ctx.trigger_data or {}),
        "nodes": _cap_nodes_snapshot(upstream_nodes_snapshot),
    }


async def _dispatch_tool_code(
    wired: WiredTool,
    arguments: dict[str, Any],
    ctx: "ad.flows.ExecutionContext",
    *,
    consumer_node_id: str,
    parent_item: "ad.flows.FlowItem",
    upstream_nodes_snapshot: dict[str, Any],
) -> str:
    params = wired.node.get("parameters") or {}
    code = str(params.get("python_code") or "")
    timeout = float(params.get("timeout_seconds") or 30.0)
    tool_ctx = build_tool_context(
        ctx,
        consumer_node_id=consumer_node_id,
        parent_item=parent_item,
        upstream_nodes_snapshot=upstream_nodes_snapshot,
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

    try:
        run = await run_nested_subflow(
            parent_ctx=ctx,
            target_flow_id=target_flow_id,
            trigger_data={"tool_arguments": arguments},
            require_callable_as_tool=True,
            mode="sub_flow_tool",
        )
        value = resolve_subflow_return_json(run)
    except SubFlowError as e:
        return json.dumps({"error": str(e)})
    except Exception as e:
        return json.dumps({"error": str(e)})

    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False, default=str)


async def execute_tool_call(
    tc: NormalizedToolCall,
    wired: WiredTool,
    ctx: "ad.flows.ExecutionContext",
    *,
    consumer_node_id: str,
    parent_item: "ad.flows.FlowItem",
    upstream_nodes_snapshot: dict[str, Any],
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
        )
    elif wired.node_type == "flows.kb_tool":
        raw = await _dispatch_kb_tool(wired, tc.arguments, ctx)
    elif wired.node_type == "flows.flow_tool":
        raw = await _dispatch_flow_tool(wired, tc.arguments, ctx)
    else:
        return json.dumps({"error": f"Unsupported tool type: {wired.node_type}"})

    return _truncate_for_llm(raw)
