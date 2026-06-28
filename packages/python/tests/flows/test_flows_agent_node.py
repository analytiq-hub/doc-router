"""FlowsAgentNode adapter tests — mock FlowAgentLoop.run at the boundary."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import analytiq_data as ad
from analytiq_data.flows.agent_loop.types import FlowAgentResult, ToolCallRecord
from analytiq_data.flows.nodes.agent import FlowsAgentNode
from analytiq_data.flows.tool_wiring import WiredTool, WiredToolRegistry


@pytest.fixture(autouse=True)
def _register_nodes() -> None:
    ad.flows.register_builtin_nodes()
    ad.flows.register_docrouter_nodes()


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


def _agent_node(**params: object) -> dict:
    base = {
        "model": "gpt-4o-mini",
        "prompt_source": "from_input",
        "prompt_field": "query",
        "response_field": "agent_output",
        "include_tool_trace": True,
    }
    base.update(params)
    return {
        "id": "agent-1",
        "name": "Agent",
        "type": "flows.agent",
        "position": [0, 0],
        "parameters": base,
        "disabled": False,
        "on_error": "stop",
    }


@pytest.mark.asyncio
async def test_agent_node_maps_loop_result_to_output_item(ctx: ad.flows.ExecutionContext) -> None:
    fake_result = FlowAgentResult(
        text="Answer text",
        tool_calls=[
            ToolCallRecord(
                round=1,
                tool="lookup",
                arguments={"q": "x"},
                result_preview='{"echo": "x"}',
                duration_ms=12,
                success=True,
            )
        ],
        rounds_used=2,
    )

    with patch(
        "analytiq_data.flows.nodes.agent.FlowAgentLoop.run",
        new_callable=AsyncMock,
        return_value=fake_result,
    ) as mock_run:
        out = await FlowsAgentNode().execute(
            ctx,
            _agent_node(),
            [[ad.flows.FlowItem(json={"query": "What is X?"}, binary={}, meta={})]],
        )

    mock_run.assert_awaited_once()
    assert len(out) == 1
    assert len(out[0]) == 1
    payload = out[0][0].json
    assert payload["agent_output"] == "Answer text"
    assert payload["max_rounds_reached"] is False
    assert len(payload["agent_tool_calls"]) == 1
    assert payload["agent_tool_calls"][0]["tool"] == "lookup"


@pytest.mark.asyncio
async def test_agent_node_all_items_mode(ctx: ad.flows.ExecutionContext) -> None:
    fake_result = FlowAgentResult(text="Batch answer", rounds_used=1)

    with patch(
        "analytiq_data.flows.nodes.agent.FlowAgentLoop.run",
        new_callable=AsyncMock,
        return_value=fake_result,
    ) as mock_run:
        items = [
            ad.flows.FlowItem(json={"query": "a"}, binary={}, meta={}),
            ad.flows.FlowItem(json={"query": "b"}, binary={}, meta={}),
        ]
        out = await FlowsAgentNode().execute(ctx, _agent_node(mode="all_items"), [items])

    assert len(out[0]) == 1
    assert out[0][0].json["agent_output"] == "Batch answer"
    config = mock_run.await_args.args[0]
    assert "a" in config.user_message
    assert "b" in config.user_message


@pytest.mark.asyncio
async def test_agent_node_error_raises_when_on_error_stop(ctx: ad.flows.ExecutionContext) -> None:
    fake_result = FlowAgentResult(text="", error="LLM failed", rounds_used=1)

    with patch(
        "analytiq_data.flows.nodes.agent.FlowAgentLoop.run",
        new_callable=AsyncMock,
        return_value=fake_result,
    ):
        with pytest.raises(RuntimeError, match="LLM failed"):
            await FlowsAgentNode().execute(
                ctx,
                _agent_node(),
                [[ad.flows.FlowItem(json={"query": "x"}, binary={}, meta={})]],
            )


@pytest.mark.asyncio
async def test_agent_node_passes_wired_registry(ctx: ad.flows.ExecutionContext) -> None:
    wired = WiredTool(
        name="lookup",
        description="Lookup",
        parameters_schema={"type": "object", "properties": {}},
        node_id="tool-1",
        node_type="flows.tool_code",
        node={"id": "tool-1", "parameters": {}},
    )
    ctx.tool_consumer_wiring = {"agent-1": [wired]}

    with patch(
        "analytiq_data.flows.nodes.agent.FlowAgentLoop.run",
        new_callable=AsyncMock,
        return_value=FlowAgentResult(text="ok", rounds_used=1),
    ), patch(
        "analytiq_data.flows.nodes.agent.WiredToolRegistry",
        wraps=WiredToolRegistry,
    ) as registry_cls:
        await FlowsAgentNode().execute(
            ctx,
            _agent_node(),
            [[ad.flows.FlowItem(json={"query": "x"}, binary={}, meta={})]],
        )

    registry_cls.assert_called_once()
    assert registry_cls.call_args.args[0][0].name == "lookup"


def test_agent_parameter_schema_prompt_visibility() -> None:
    props = FlowsAgentNode().parameter_schema["properties"]
    assert props["prompt_text"]["x-ui-show-when"] == {"field": "prompt_source", "equals": "fixed"}
    assert props["prompt_field"]["x-ui-show-when"] == {"field": "prompt_source", "equals": "from_input"}
