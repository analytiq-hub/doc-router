"""Tool Code dispatch — sandbox execution at the dispatch boundary."""

from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest

import analytiq_data as ad
from analytiq_data.flows.agent_loop.dispatch import execute_tool_call
from analytiq_data.flows.agent_loop.types import NormalizedToolCall
from analytiq_data.flows.code_runner.parent import CodeExecutionError
from analytiq_data.flows.tool_wiring import WiredTool


def _wired_code(*, code: str, timeout: float = 5.0) -> WiredTool:
    return WiredTool(
        name="echo",
        description="Echo tool",
        parameters_schema={"type": "object", "properties": {"q": {"type": "string"}}},
        node_id="code-1",
        node_type="flows.tool_code",
        node={
            "id": "code-1",
            "parameters": {"python_code": code, "timeout_seconds": timeout},
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


@pytest.mark.asyncio
async def test_tool_code_dispatch_echoes_params(ctx: ad.flows.ExecutionContext) -> None:
    code = "def run(params, context):\n  return {'echo': params.get('q', '')}\n"
    wired = _wired_code(code=code)
    tc = NormalizedToolCall(id="1", name="echo", arguments={"q": "hello"})

    raw = await execute_tool_call(
        tc,
        wired,
        ctx,
        consumer_node_id="agent-1",
        parent_item=ad.flows.FlowItem(json={}, binary={}, meta={}),
        upstream_nodes_snapshot={},
    )

    assert json.loads(raw) == {"echo": "hello"}


@pytest.mark.asyncio
async def test_tool_code_dispatch_missing_run_raises(ctx: ad.flows.ExecutionContext) -> None:
    code = "def helper():\n  pass\n"
    wired = _wired_code(code=code)
    tc = NormalizedToolCall(id="1", name="echo", arguments={"q": "x"})

    with pytest.raises(CodeExecutionError, match="run\\(params, context\\)"):
        await execute_tool_call(
            tc,
            wired,
            ctx,
            consumer_node_id="agent-1",
            parent_item=ad.flows.FlowItem(json={}, binary={}, meta={}),
            upstream_nodes_snapshot={},
        )


@pytest.mark.asyncio
async def test_tool_code_dispatch_timeout(ctx: ad.flows.ExecutionContext) -> None:
    code = (
        "import time\n"
        "def run(params, context):\n"
        "  time.sleep(2)\n"
        "  return {}\n"
    )
    wired = _wired_code(code=code, timeout=0.2)
    tc = NormalizedToolCall(id="1", name="echo", arguments={})

    with pytest.raises(CodeExecutionError):
        await execute_tool_call(
            tc,
            wired,
            ctx,
            consumer_node_id="agent-1",
            parent_item=ad.flows.FlowItem(json={}, binary={}, meta={}),
            upstream_nodes_snapshot={},
        )
