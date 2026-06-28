"""Unit tests for FlowAgentLoop (mocked LLM)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import analytiq_data as ad
from analytiq_data.flows.agent_loop import FlowAgentConfig, FlowAgentLoop
from analytiq_data.flows.tool_wiring import WiredTool, WiredToolRegistry


@dataclass
class _FakeFn:
    name: str
    arguments: str


@dataclass
class _FakeToolCall:
    id: str
    function: _FakeFn


@dataclass
class _FakeMessage:
    content: str | None
    tool_calls: list[_FakeToolCall] | None = None


@dataclass
class _FakeChoice:
    message: _FakeMessage


@dataclass
class _FakeResponse:
    choices: list[_FakeChoice]
    usage: Any = None


def _wired_tool_code() -> WiredTool:
    return WiredTool(
        name="echo",
        description="Echo tool",
        parameters_schema={"type": "object", "properties": {}},
        node_id="tool-1",
        node_type="flows.tool_code",
        node={
            "id": "tool-1",
            "parameters": {
                "python_code": "def run(params, context):\n  return params\n",
                "timeout_seconds": 30,
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


@pytest.mark.asyncio
async def test_no_tools_single_reply(ctx: ad.flows.ExecutionContext) -> None:
    registry = WiredToolRegistry([])
    item = ad.flows.FlowItem(json={}, binary={}, meta={})
    loop = FlowAgentLoop(
        analytiq_client=ctx.analytiq_client,
        organization_id="org1",
        execution_context=ctx,
        tool_registry=registry,
        consumer_node_id="agent-1",
        parent_item=item,
        upstream_nodes_snapshot={},
    )
    fake = _FakeResponse(choices=[_FakeChoice(message=_FakeMessage(content="Hello"))])

    with patch("analytiq_data.flows.agent_loop.loop.ad.llm.get_llm_model_provider", return_value="openai"), patch(
        "analytiq_data.flows.agent_loop.loop.ad.llm.get_llm_key", new_callable=AsyncMock, return_value="key"
    ), patch(
        "analytiq_data.flows.agent_loop.loop.ad.llm.agent_completion",
        new_callable=AsyncMock,
        return_value=fake,
    ), patch(
        "analytiq_data.flows.agent_loop.billing.check_spu_limits",
        new_callable=AsyncMock,
    ), patch(
        "analytiq_data.flows.agent_loop.billing.record_spu",
        new_callable=AsyncMock,
    ):
        result = await loop.run(
            FlowAgentConfig(model="gpt-4o-mini", system_message="sys", user_message="hi")
        )

    assert result.text == "Hello"
    assert result.rounds_used == 1
    assert result.error is None


@pytest.mark.asyncio
async def test_unknown_tool_continues_loop(ctx: ad.flows.ExecutionContext) -> None:
    registry = WiredToolRegistry([_wired_tool_code()])
    item = ad.flows.FlowItem(json={}, binary={}, meta={})
    loop = FlowAgentLoop(
        analytiq_client=ctx.analytiq_client,
        organization_id="org1",
        execution_context=ctx,
        tool_registry=registry,
        consumer_node_id="agent-1",
        parent_item=item,
        upstream_nodes_snapshot={},
    )

    first = _FakeResponse(
        choices=[
            _FakeChoice(
                message=_FakeMessage(
                    content=None,
                    tool_calls=[_FakeToolCall(id="tc1", function=_FakeFn(name="missing", arguments="{}"))],
                )
            )
        ]
    )
    second = _FakeResponse(choices=[_FakeChoice(message=_FakeMessage(content="Done"))])

    with patch("analytiq_data.flows.agent_loop.loop.ad.llm.get_llm_model_provider", return_value="openai"), patch(
        "analytiq_data.flows.agent_loop.loop.ad.llm.get_llm_key", new_callable=AsyncMock, return_value="key"
    ), patch(
        "analytiq_data.flows.agent_loop.loop.ad.llm.agent_completion",
        new_callable=AsyncMock,
        side_effect=[first, second],
    ), patch(
        "analytiq_data.flows.agent_loop.billing.check_spu_limits",
        new_callable=AsyncMock,
    ), patch(
        "analytiq_data.flows.agent_loop.billing.record_spu",
        new_callable=AsyncMock,
    ):
        result = await loop.run(
            FlowAgentConfig(model="gpt-4o-mini", system_message="sys", user_message="hi")
        )

    assert result.text == "Done"
    assert len(result.tool_calls) == 1
    assert result.tool_calls[0].success is False
