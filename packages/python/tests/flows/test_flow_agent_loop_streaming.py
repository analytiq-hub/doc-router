"""FlowAgentLoop streaming tests (mocked agent_completion_stream)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import analytiq_data as ad
from analytiq_data.flows.agent_loop import FlowAgentConfig, FlowAgentLoop
from analytiq_data.flows.tool_wiring import WiredTool, WiredToolRegistry

_ECHO_CODE = "def run(params, context):\n  return {'city': params.get('city', '')}\n"


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


def _wired_tool_code() -> WiredTool:
    return WiredTool(
        name="weather",
        description="Weather lookup",
        parameters_schema={
            "type": "object",
            "properties": {"city": {"type": "string"}},
            "required": ["city"],
        },
        node_id="tool-1",
        node_type="flows.tool_code",
        node={
            "id": "tool-1",
            "parameters": {
                "python_code": _ECHO_CODE,
                "timeout_seconds": 5,
            },
        },
    )


async def _fake_stream_text_only(*_args: Any, **_kwargs: Any):
    yield ("content", "Hello ")
    yield ("content", "world")
    yield ("message", _FakeMessage(content="Hello world"))
    yield ("usage", {"total_tokens": 10})


@pytest.fixture
def ctx() -> ad.flows.ExecutionContext:
    return ad.flows.ExecutionContext(
        organization_id="org1",
        execution_id="exec1",
        flow_id="flow1",
        flow_revid="rev1",
        mode="chat",
        trigger_data={},
        run_data={},
        analytiq_client=MagicMock(),
        is_streaming=True,
    )


@pytest.mark.asyncio
async def test_stream_emits_content_chunks_and_end(ctx: ad.flows.ExecutionContext) -> None:
    events: list[dict[str, Any]] = []

    async def sink(event: dict[str, Any]) -> None:
        events.append(event)

    ctx.stream_sink = sink
    item = ad.flows.FlowItem(json={}, binary={}, meta={})
    loop = FlowAgentLoop(
        analytiq_client=ctx.analytiq_client,
        organization_id="org1",
        execution_context=ctx,
        tool_registry=WiredToolRegistry([]),
        consumer_node_id="agent-1",
        parent_item=item,
        upstream_nodes_snapshot={},
    )

    with patch("analytiq_data.flows.agent_loop.loop.ad.llm.get_llm_model_provider", return_value="openai"), patch(
        "analytiq_data.flows.agent_loop.loop.ad.llm.get_llm_key", new_callable=AsyncMock, return_value="key"
    ), patch(
        "analytiq_data.flows.agent_loop.loop.ad.llm.agent_completion_stream",
        side_effect=_fake_stream_text_only,
    ), patch(
        "analytiq_data.flows.agent_loop.billing.check_spu_limits",
        new_callable=AsyncMock,
    ), patch(
        "analytiq_data.flows.agent_loop.billing.record_spu_from_usage",
        new_callable=AsyncMock,
    ):
        result = await loop.run(
            FlowAgentConfig(
                model="gpt-4o-mini",
                system_message="sys",
                user_message="hi",
                enable_streaming=True,
            )
        )

    assert result.text == "Hello world"
    content_events = [e for e in events if e.get("type") == "content"]
    assert len(content_events) == 2
    assert content_events[0]["chunk"] == "Hello "
    end_events = [e for e in events if e.get("type") == "end"]
    assert len(end_events) == 1
    assert end_events[0]["text"] == "Hello world"


@pytest.mark.asyncio
async def test_stream_tool_round_events(ctx: ad.flows.ExecutionContext) -> None:
    events: list[dict[str, Any]] = []

    async def sink(event: dict[str, Any]) -> None:
        events.append(event)

    ctx.stream_sink = sink
    item = ad.flows.FlowItem(json={}, binary={}, meta={})
    loop = FlowAgentLoop(
        analytiq_client=ctx.analytiq_client,
        organization_id="org1",
        execution_context=ctx,
        tool_registry=WiredToolRegistry([_wired_tool_code()]),
        consumer_node_id="agent-1",
        parent_item=item,
        upstream_nodes_snapshot={},
    )

    round_idx = 0

    async def stream_side_effect(*_args: Any, **_kwargs: Any):
        nonlocal round_idx
        round_idx += 1
        if round_idx == 1:
            yield (
                "message",
                _FakeMessage(
                    content=None,
                    tool_calls=[
                        _FakeToolCall(id="tc1", function=_FakeFn(name="weather", arguments='{"city":"Seattle"}'))
                    ],
                ),
            )
            yield ("usage", {"total_tokens": 20})
        else:
            yield ("content", "It is sunny.")
            yield ("message", _FakeMessage(content="It is sunny."))
            yield ("usage", {"total_tokens": 30})

    with patch("analytiq_data.flows.agent_loop.loop.ad.llm.get_llm_model_provider", return_value="openai"), patch(
        "analytiq_data.flows.agent_loop.loop.ad.llm.get_llm_key", new_callable=AsyncMock, return_value="key"
    ), patch(
        "analytiq_data.flows.agent_loop.loop.ad.llm.agent_completion_stream",
        side_effect=stream_side_effect,
    ), patch(
        "analytiq_data.flows.agent_loop.billing.check_spu_limits",
        new_callable=AsyncMock,
    ), patch(
        "analytiq_data.flows.agent_loop.billing.record_spu_from_usage",
        new_callable=AsyncMock,
    ):
        result = await loop.run(
            FlowAgentConfig(
                model="gpt-4o-mini",
                system_message="sys",
                user_message="weather?",
                enable_streaming=True,
            )
        )

    assert result.text == "It is sunny."
    assert any(e.get("type") == "tool_call" for e in events)
    assert any(e.get("type") == "tool_result" for e in events)


@pytest.mark.asyncio
async def test_stream_error_emitted_on_llm_failure(ctx: ad.flows.ExecutionContext) -> None:
    events: list[dict[str, Any]] = []

    async def sink(event: dict[str, Any]) -> None:
        events.append(event)

    ctx.stream_sink = sink
    loop = FlowAgentLoop(
        analytiq_client=ctx.analytiq_client,
        organization_id="org1",
        execution_context=ctx,
        tool_registry=WiredToolRegistry([]),
        consumer_node_id="agent-1",
        parent_item=ad.flows.FlowItem(json={}, binary={}, meta={}),
        upstream_nodes_snapshot={},
    )

    async def broken_stream(*_args: Any, **_kwargs: Any):
        raise RuntimeError("stream broke")
        yield ("content", "")  # pragma: no cover

    with patch("analytiq_data.flows.agent_loop.loop.ad.llm.get_llm_model_provider", return_value="openai"), patch(
        "analytiq_data.flows.agent_loop.loop.ad.llm.get_llm_key", new_callable=AsyncMock, return_value="key"
    ), patch(
        "analytiq_data.flows.agent_loop.loop.ad.llm.agent_completion_stream",
        side_effect=broken_stream,
    ), patch(
        "analytiq_data.flows.agent_loop.billing.check_spu_limits",
        new_callable=AsyncMock,
    ):
        result = await loop.run(
            FlowAgentConfig(
                model="gpt-4o-mini",
                system_message="sys",
                user_message="hi",
                enable_streaming=True,
            )
        )

    assert result.error == "stream broke"
    assert any(e.get("type") == "error" for e in events)


@pytest.mark.asyncio
async def test_non_streaming_uses_batch_completion(ctx: ad.flows.ExecutionContext) -> None:
    ctx.is_streaming = False
    loop = FlowAgentLoop(
        analytiq_client=ctx.analytiq_client,
        organization_id="org1",
        execution_context=ctx,
        tool_registry=WiredToolRegistry([]),
        consumer_node_id="agent-1",
        parent_item=ad.flows.FlowItem(json={}, binary={}, meta={}),
        upstream_nodes_snapshot={},
    )

    fake_response = MagicMock()
    fake_response.choices = [MagicMock(message=MagicMock(content="Batch reply", tool_calls=None))]
    fake_response.usage = {}

    with patch("analytiq_data.flows.agent_loop.loop.ad.llm.get_llm_model_provider", return_value="openai"), patch(
        "analytiq_data.flows.agent_loop.loop.ad.llm.get_llm_key", new_callable=AsyncMock, return_value="key"
    ), patch(
        "analytiq_data.flows.agent_loop.loop.ad.llm.agent_completion",
        new_callable=AsyncMock,
        return_value=fake_response,
    ) as batch_mock, patch(
        "analytiq_data.flows.agent_loop.loop.ad.llm.agent_completion_stream",
        new_callable=AsyncMock,
    ) as stream_mock, patch(
        "analytiq_data.flows.agent_loop.billing.check_spu_limits",
        new_callable=AsyncMock,
    ), patch(
        "analytiq_data.flows.agent_loop.billing.record_spu",
        new_callable=AsyncMock,
    ):
        result = await loop.run(
            FlowAgentConfig(
                model="gpt-4o-mini",
                system_message="sys",
                user_message="hi",
                enable_streaming=False,
            )
        )

    batch_mock.assert_awaited_once()
    stream_mock.assert_not_awaited()
    assert result.text == "Batch reply"
