"""Knowledge Base Tool dispatch tests (mocked search)."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import analytiq_data as ad
from analytiq_data.flows.agent_loop.dispatch import execute_tool_call
from analytiq_data.flows.agent_loop.types import NormalizedToolCall
from analytiq_data.flows.tool_wiring import WiredTool, default_kb_tool_name


def _wired_kb(*, kb_id: str = "kb1", tool_name: str = "search_docs") -> WiredTool:
    return WiredTool(
        name=tool_name,
        description="Search docs",
        parameters_schema={"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]},
        node_id="kb-node",
        node_type="flows.kb_tool",
        node={
            "id": "kb-node",
            "parameters": {
                "knowledge_base_id": kb_id,
                "tool_name": tool_name,
                "tool_description": "Search docs",
                "default_top_k": 3,
            },
        },
    )


@pytest.fixture
def ctx() -> ad.flows.ExecutionContext:
    return ad.flows.ExecutionContext(
        organization_id="org1",
        execution_id="exec1",
        flow_id="flow1",
        flow_revid="rev1",
        mode="manual",
        trigger_data={},
        run_data={},
        analytiq_client=MagicMock(),
    )


def test_default_kb_tool_name_deduplicates() -> None:
    used: set[str] = set()
    first = default_kb_tool_name("Product Docs", used=used)
    used.add(first)
    second = default_kb_tool_name("Product Docs", used=used)
    assert first == "search_product_docs"
    assert second == "search_product_docs_2"


@pytest.mark.asyncio
async def test_kb_dispatch_returns_formatted_results(ctx: ad.flows.ExecutionContext) -> None:
    wired = _wired_kb()
    tc = NormalizedToolCall(id="1", name="search_docs", arguments={"query": "hello"})

    with patch(
        "analytiq_data.flows.agent_loop.dispatch.ad.kb.search.search_knowledge_base",
        new_callable=AsyncMock,
        return_value={"results": [{"text": "chunk one", "score": 0.9}]},
    ), patch(
        "analytiq_data.flows.agent_loop.dispatch.ad.kb.format_kb_search_results_for_llm",
        return_value="formatted hits",
    ):
        raw = await execute_tool_call(
            tc,
            wired,
            ctx,
            consumer_node_id="agent-1",
            parent_item=ad.flows.FlowItem(json={}, binary={}, meta={}),
            upstream_nodes_snapshot={},
        )

    assert raw == "formatted hits"


@pytest.mark.asyncio
async def test_kb_dispatch_missing_query(ctx: ad.flows.ExecutionContext) -> None:
    wired = _wired_kb()
    tc = NormalizedToolCall(id="1", name="search_docs", arguments={})

    raw = await execute_tool_call(
        tc,
        wired,
        ctx,
        consumer_node_id="agent-1",
        parent_item=ad.flows.FlowItem(json={}, binary={}, meta={}),
        upstream_nodes_snapshot={},
    )

    assert json.loads(raw) == {"error": "query is required"}


@pytest.mark.asyncio
async def test_kb_dispatch_inactive_kb(ctx: ad.flows.ExecutionContext) -> None:
    wired = _wired_kb()
    tc = NormalizedToolCall(id="1", name="search_docs", arguments={"query": "x"})

    with patch(
        "analytiq_data.flows.agent_loop.dispatch.ad.kb.search.search_knowledge_base",
        new_callable=AsyncMock,
        side_effect=RuntimeError("Knowledge base is not active"),
    ):
        raw = await execute_tool_call(
            tc,
            wired,
            ctx,
            consumer_node_id="agent-1",
            parent_item=ad.flows.FlowItem(json={}, binary={}, meta={}),
            upstream_nodes_snapshot={},
        )

    assert json.loads(raw) == {"error": "Knowledge base is not active"}


@pytest.mark.asyncio
async def test_kb_dispatch_empty_results(ctx: ad.flows.ExecutionContext) -> None:
    wired = _wired_kb()
    tc = NormalizedToolCall(id="1", name="search_docs", arguments={"query": "nothing"})

    with patch(
        "analytiq_data.flows.agent_loop.dispatch.ad.kb.search.search_knowledge_base",
        new_callable=AsyncMock,
        return_value={"results": []},
    ), patch(
        "analytiq_data.flows.agent_loop.dispatch.ad.kb.format_kb_search_results_for_llm",
        return_value="No results found.",
    ):
        raw = await execute_tool_call(
            tc,
            wired,
            ctx,
            consumer_node_id="agent-1",
            parent_item=ad.flows.FlowItem(json={}, binary={}, meta={}),
            upstream_nodes_snapshot={},
        )

    assert raw == "No results found."


@pytest.mark.asyncio
async def test_kb_dispatch_not_configured(ctx: ad.flows.ExecutionContext) -> None:
    wired = _wired_kb(kb_id="")
    tc = NormalizedToolCall(id="1", name="search_docs", arguments={"query": "x"})

    raw = await execute_tool_call(
        tc,
        wired,
        ctx,
        consumer_node_id="agent-1",
        parent_item=ad.flows.FlowItem(json={}, binary={}, meta={}),
        upstream_nodes_snapshot={},
    )

    assert json.loads(raw) == {"error": "Knowledge base not configured"}
