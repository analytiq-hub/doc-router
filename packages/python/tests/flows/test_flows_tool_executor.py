"""Path A: Tool Executor node — dispatch wired tools with explicit arguments."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from bson import ObjectId

import analytiq_data as ad
from analytiq_data.flows.connections import NodeConnection
from analytiq_data.flows.nodes.tool_executor import FlowsToolExecutorNode
from analytiq_data.flows.tool_wiring import tool_consumer_wiring

_ECHO_CODE = "def run(params, context):\n  return {'echo': params.get('q', '')}\n"


def _node(node_id: str, node_type: str, **extra: object) -> dict:
    base = {
        "id": node_id,
        "name": node_id,
        "type": node_type,
        "position": [0, 0],
        "parameters": {},
        "disabled": False,
        "on_error": "stop",
    }
    base.update(extra)
    return base


def _tool_graph(*, arguments_source: str = "fixed", arguments: dict | None = None) -> tuple[list[dict], dict]:
    nodes = [
        _node("t1", "flows.trigger.manual"),
        _node(
            "exec",
            "flows.tool_executor",
            parameters={
                "tool_name": "lookup",
                "arguments_source": arguments_source,
                "arguments": arguments or {"q": "hello"},
                "arguments_field": "tool_arguments",
            },
        ),
        _node(
            "tool",
            "flows.tool_code",
            parameters={
                "tool_name": "lookup",
                "tool_description": "Echo lookup",
                "parameters_schema": {
                    "type": "object",
                    "properties": {"q": {"type": "string"}},
                    "required": ["q"],
                },
                "python_code": _ECHO_CODE,
                "timeout_seconds": 5,
            },
        ),
    ]
    connections = {
        "t1": {"main": [[NodeConnection(dest_node_id="exec", connection_type="main", index=0)]]},
        "tool": {"main": [[NodeConnection(dest_node_id="exec", connection_type="flows.tool", index=0)]]},
    }
    return nodes, connections


@pytest.fixture(autouse=True)
def _register_nodes() -> None:
    ad.flows.register_builtin_nodes()
    ad.flows.register_docrouter_nodes()


@pytest.fixture
def ctx() -> ad.flows.ExecutionContext:
    return ad.flows.ExecutionContext(
        organization_id="org1",
        execution_id=str(ObjectId()),
        flow_id=str(ObjectId()),
        flow_revid=str(ObjectId()),
        mode="manual",
        trigger_data={},
        run_data={},
        analytiq_client=MagicMock(),
    )


@pytest.fixture(autouse=True)
def _noop_persist_run_data() -> None:
    with patch("analytiq_data.flows.engine.persist_run_data", new_callable=AsyncMock):
        yield


@pytest.mark.asyncio
async def test_tool_executor_fixed_arguments(ctx: ad.flows.ExecutionContext) -> None:
    nodes, connections = _tool_graph(arguments_source="fixed", arguments={"q": "fixed-arg"})
    ctx.tool_consumer_wiring = tool_consumer_wiring(nodes, connections)

    out = await FlowsToolExecutorNode().execute(
        ctx,
        next(n for n in nodes if n["id"] == "exec"),
        [[ad.flows.FlowItem(json={}, binary={}, meta={})]],
    )

    assert len(out) == 1
    assert len(out[0]) == 1
    row = out[0][0].json
    assert row["success"] is True
    assert row["tool_name"] == "lookup"
    assert row["tool_result"] == {"echo": "fixed-arg"}
    assert ctx.run_data["tool"]["status"] == "success"
    assert ctx.run_data["tool"]["data"]["main"][0][0].json == {"echo": "fixed-arg"}


@pytest.mark.asyncio
async def test_tool_executor_from_input_arguments(ctx: ad.flows.ExecutionContext) -> None:
    nodes, connections = _tool_graph(arguments_source="from_input")
    ctx.tool_consumer_wiring = tool_consumer_wiring(nodes, connections)

    out = await FlowsToolExecutorNode().execute(
        ctx,
        next(n for n in nodes if n["id"] == "exec"),
        [[ad.flows.FlowItem(json={"q": "from-input"}, binary={}, meta={})]],
    )

    assert out[0][0].json["success"] is True
    assert out[0][0].json["tool_result"] == {"echo": "from-input"}


@pytest.mark.asyncio
async def test_tool_executor_input_field_arguments(ctx: ad.flows.ExecutionContext) -> None:
    nodes, connections = _tool_graph(arguments_source="input_field")
    ctx.tool_consumer_wiring = tool_consumer_wiring(nodes, connections)

    out = await FlowsToolExecutorNode().execute(
        ctx,
        next(n for n in nodes if n["id"] == "exec"),
        [[ad.flows.FlowItem(json={"tool_arguments": {"q": "field-arg"}}, binary={}, meta={})]],
    )

    assert out[0][0].json["tool_result"] == {"echo": "field-arg"}


@pytest.mark.asyncio
async def test_tool_executor_unknown_tool_raises(ctx: ad.flows.ExecutionContext) -> None:
    nodes, connections = _tool_graph()
    exec_node = next(n for n in nodes if n["id"] == "exec")
    exec_node["parameters"]["tool_name"] = "missing"
    ctx.tool_consumer_wiring = tool_consumer_wiring(nodes, connections)

    with pytest.raises(Exception, match="Unknown tool"):
        await FlowsToolExecutorNode().execute(
            ctx,
            exec_node,
            [[ad.flows.FlowItem(json={}, binary={}, meta={})]],
        )


@pytest.mark.asyncio
async def test_tool_executor_continue_on_fail(ctx: ad.flows.ExecutionContext) -> None:
    nodes, connections = _tool_graph()
    exec_node = next(n for n in nodes if n["id"] == "exec")
    exec_node["parameters"]["tool_name"] = "missing"
    exec_node["on_error"] = "continue"
    ctx.tool_consumer_wiring = tool_consumer_wiring(nodes, connections)

    out = await FlowsToolExecutorNode().execute(
        ctx,
        exec_node,
        [[ad.flows.FlowItem(json={}, binary={}, meta={})]],
    )

    assert out[0][0].json["success"] is False
    assert "error" in out[0][0].json["tool_result"]


@pytest.mark.asyncio
async def test_tool_executor_dispatch_error_json_is_failure(ctx: ad.flows.ExecutionContext) -> None:
    nodes, connections = _tool_graph()
    exec_node = next(n for n in nodes if n["id"] == "exec")
    ctx.tool_consumer_wiring = tool_consumer_wiring(nodes, connections)

    with patch(
        "analytiq_data.flows.nodes.tool_executor.execute_tool_call",
        new_callable=AsyncMock,
        return_value='{"error": "Knowledge base not found"}',
    ):
        out = await FlowsToolExecutorNode().execute(
            ctx,
            exec_node,
            [[ad.flows.FlowItem(json={}, binary={}, meta={})]],
        )

    assert out[0][0].json["success"] is False
    assert out[0][0].json["tool_result"] == {"error": "Knowledge base not found"}
    assert ctx.run_data["tool"]["status"] == "error"


@pytest.mark.asyncio
async def test_tool_executor_all_items_from_input_combines_rows(ctx: ad.flows.ExecutionContext) -> None:
    nodes, connections = _tool_graph(arguments_source="from_input")
    exec_node = next(n for n in nodes if n["id"] == "exec")
    exec_node["parameters"]["mode"] = "all_items"
    ctx.tool_consumer_wiring = tool_consumer_wiring(nodes, connections)

    items = [
        ad.flows.FlowItem(json={"q": "first"}, binary={}, meta={}),
        ad.flows.FlowItem(json={"q": "second"}, binary={}, meta={}),
    ]

    with patch(
        "analytiq_data.flows.nodes.tool_executor.execute_tool_call",
        new_callable=AsyncMock,
        return_value='{"ok": true}',
    ) as mock_dispatch:
        out = await FlowsToolExecutorNode().execute(ctx, exec_node, [items])

    assert len(out[0]) == 1
    assert out[0][0].json["success"] is True
    mock_dispatch.assert_awaited_once()
    tc = mock_dispatch.await_args.args[0]
    assert tc.arguments == {"items": [{"q": "first"}, {"q": "second"}]}


@pytest.mark.asyncio
async def test_tool_executor_all_items_input_field_combines_rows(ctx: ad.flows.ExecutionContext) -> None:
    nodes, connections = _tool_graph(arguments_source="input_field")
    exec_node = next(n for n in nodes if n["id"] == "exec")
    exec_node["parameters"]["mode"] = "all_items"
    ctx.tool_consumer_wiring = tool_consumer_wiring(nodes, connections)

    items = [
        ad.flows.FlowItem(json={"tool_arguments": {"q": "alpha"}}, binary={}, meta={}),
        ad.flows.FlowItem(json={"tool_arguments": {"q": "beta"}}, binary={}, meta={}),
    ]

    with patch(
        "analytiq_data.flows.nodes.tool_executor.execute_tool_call",
        new_callable=AsyncMock,
        return_value='{"ok": true}',
    ) as mock_dispatch:
        out = await FlowsToolExecutorNode().execute(ctx, exec_node, [items])

    assert len(out[0]) == 1
    tc = mock_dispatch.await_args.args[0]
    assert tc.arguments == {"items": [{"q": "alpha"}, {"q": "beta"}]}


@pytest.mark.asyncio
async def test_tool_executor_per_item_dispatches_once_per_row(ctx: ad.flows.ExecutionContext) -> None:
    nodes, connections = _tool_graph(arguments_source="from_input")
    exec_node = next(n for n in nodes if n["id"] == "exec")
    exec_node["parameters"]["mode"] = "per_item"
    ctx.tool_consumer_wiring = tool_consumer_wiring(nodes, connections)

    items = [
        ad.flows.FlowItem(json={"q": "first"}, binary={}, meta={}),
        ad.flows.FlowItem(json={"q": "second"}, binary={}, meta={}),
    ]

    with patch(
        "analytiq_data.flows.nodes.tool_executor.execute_tool_call",
        new_callable=AsyncMock,
        return_value='{"echo": "x"}',
    ) as mock_dispatch:
        out = await FlowsToolExecutorNode().execute(ctx, exec_node, [items])

    assert len(out[0]) == 2
    assert mock_dispatch.await_count == 2
    assert mock_dispatch.await_args_list[0].args[0].arguments == {"q": "first"}
    assert mock_dispatch.await_args_list[1].args[0].arguments == {"q": "second"}
