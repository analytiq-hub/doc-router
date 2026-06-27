"""Path B execute-step: rewire tool_provider + synthetic Tool Executor."""

from __future__ import annotations

import pytest

import analytiq_data as ad
from analytiq_data.flows.connections import NodeConnection
from analytiq_data.flows.engine import FlowValidationError
from analytiq_data.flows.tool_wiring import (
    TOOL_TEST_EXECUTOR_ID,
    TOOL_TEST_MANUAL_ID,
    example_arguments_from_schema,
    prepare_tool_test_run,
)


def _node(node_id: str, node_type: str, name: str | None = None, **extra: object) -> dict:
    base = {
        "id": node_id,
        "name": name or node_id,
        "type": node_type,
        "position": [0, 0],
        "parameters": {},
        "disabled": False,
        "on_error": "stop",
    }
    base.update(extra)
    return base


@pytest.fixture(autouse=True)
def _register_nodes():
    ad.flows.register_builtin_nodes()
    ad.flows.register_docrouter_nodes()


def _agent_tool_graph() -> tuple[list[dict], dict]:
    nodes = [
        _node("t1", "flows.trigger.manual"),
        _node("agent", "flows.agent", parameters={"model": "gpt-4o-mini", "prompt_source": "fixed", "prompt_text": "hi"}),
        _node(
            "tool",
            "flows.tool_code",
            parameters={
                "tool_name": "lookup",
                "tool_description": "Look up",
                "parameters_schema": {
                    "type": "object",
                    "properties": {"q": {"type": "string"}},
                    "required": ["q"],
                },
                "python_code": "def run(p,c): return {'echo': p}\n",
            },
        ),
    ]
    connections = {
        "t1": {"main": [[NodeConnection(dest_node_id="agent", connection_type="main", index=0)]]},
        "tool": {"main": [[NodeConnection(dest_node_id="agent", connection_type="flows.tool", index=0)]]},
    }
    return nodes, connections


def test_example_arguments_from_schema_defaults() -> None:
    schema = {
        "type": "object",
        "properties": {
            "q": {"type": "string"},
            "limit": {"type": "integer", "default": 3},
        },
        "required": ["q"],
    }
    assert example_arguments_from_schema(schema) == {"q": "", "limit": 3}


def test_prepare_tool_test_run_rewires_and_targets_executor() -> None:
    nodes, connections = _agent_tool_graph()
    revision, start_id, run_target = prepare_tool_test_run(
        revision={"nodes": nodes, "connections": connections, "settings": {}, "pin_data": None},
        tool_node_id="tool",
        tool_name="lookup",
        arguments={"q": "hello"},
    )
    assert start_id == TOOL_TEST_MANUAL_ID
    assert run_target == TOOL_TEST_EXECUTOR_ID
    rev_nodes = revision["nodes"]
    assert any(n["id"] == TOOL_TEST_MANUAL_ID for n in rev_nodes)
    assert any(n["id"] == TOOL_TEST_EXECUTOR_ID for n in rev_nodes)
    conns = ad.flows.coerce_json_connections_to_dataclasses(revision["connections"])
    closure = ad.flows.upstream_closure_for_target(start_id, run_target, conns)
    assert TOOL_TEST_MANUAL_ID in closure
    assert TOOL_TEST_EXECUTOR_ID in closure


def test_prepare_tool_test_run_rejects_unwired_tool() -> None:
    nodes, connections = _agent_tool_graph()
    connections = {"t1": connections["t1"]}
    with pytest.raises(FlowValidationError, match="not wired"):
        prepare_tool_test_run(
            revision={"nodes": nodes, "connections": connections, "settings": {}, "pin_data": None},
            tool_node_id="tool",
            tool_name="lookup",
            arguments={},
        )


@pytest.mark.asyncio
async def test_tool_test_execute_step_records_tool_node_run_data() -> None:
    from analytiq_data.flows.context import ExecutionContext

    nodes, connections = _agent_tool_graph()
    revision, start_id, run_target = prepare_tool_test_run(
        revision={"nodes": nodes, "connections": connections, "settings": {}, "pin_data": None},
        tool_node_id="tool",
        tool_name="lookup",
        arguments={"q": "hello"},
    )
    ctx = ExecutionContext(
        organization_id="org1",
        execution_id="ex1",
        flow_id="flow1",
        flow_revid="rev1",
        mode="manual",
        trigger_data={"type": "manual"},
        run_data={},
        analytiq_client=None,
    )
    await ad.flows.run_flow(
        context=ctx,
        revision=revision,
        target_node_id=run_target,
        start_trigger_node_id=start_id,
    )
    tool_entry = ctx.run_data.get("tool")
    assert tool_entry is not None
    assert tool_entry.get("status") == "success"
    main = tool_entry.get("data", {}).get("main")
    assert isinstance(main, list) and main and main[0]
    item = main[0][0]
    assert item.json.get("echo") == {"q": "hello"}
