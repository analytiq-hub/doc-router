"""Tests for flows.tool connection validation and tool wiring."""

from __future__ import annotations

import pytest

import analytiq_data as ad
from analytiq_data.flows.connections import NodeConnection
from analytiq_data.flows.engine import FlowValidationError, validate_revision


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


def test_validate_accepts_tool_code_to_executor() -> None:
    nodes = [
        _node("t1", "flows.trigger.manual", "Trigger"),
        _node("exec", "flows.tool_executor", parameters={"tool_name": "lookup"}),
        _node(
            "tool",
            "flows.tool_code",
            parameters={
                "tool_name": "lookup",
                "tool_description": "Look up",
                "parameters_schema": {"type": "object", "properties": {}},
                "python_code": "def run(params, context):\n  return params\n",
            },
        ),
    ]
    connections = {
        "t1": {"main": [[NodeConnection(dest_node_id="exec", connection_type="main", index=0)]]},
        "tool": {
            "main": [
                [NodeConnection(dest_node_id="exec", connection_type="flows.tool", index=0)],
            ],
        },
    }
    validate_revision(nodes, connections, {}, None)


def test_validate_rejects_unwired_tool_provider() -> None:
    nodes = [
        _node("t1", "flows.trigger.manual"),
        _node(
            "tool",
            "flows.tool_code",
            parameters={
                "tool_name": "lookup",
                "tool_description": "Look up",
                "parameters_schema": {"type": "object", "properties": {}},
                "python_code": "def run(params, context):\n  return params\n",
            },
        ),
    ]
    connections = {"t1": {"main": [[]]}}
    with pytest.raises(FlowValidationError, match="must connect to an AI Agent or Tool Executor"):
        validate_revision(nodes, connections, {}, None)


def test_validate_rejects_invalid_tool_name_on_unwired_provider() -> None:
    nodes = [
        _node("t1", "flows.trigger.manual"),
        _node(
            "tool",
            "flows.tool_code",
            parameters={
                "tool_name": "",
                "tool_description": "Look up",
                "parameters_schema": {"type": "object", "properties": {}},
                "python_code": "def run(p,c): return p\n",
            },
        ),
    ]
    connections = {"t1": {"main": [[]]}}
    with pytest.raises(FlowValidationError, match="invalid tool_name"):
        validate_revision(nodes, connections, {}, None)


def test_rewire_graph_for_tool_test_with_dict_connections() -> None:
    from analytiq_data.flows.tool_wiring import rewire_graph_for_tool_test

    nodes = [
        _node("t1", "flows.trigger.manual"),
        _node("exec", "flows.tool_executor", parameters={"tool_name": "lookup"}),
        _node(
            "tool",
            "flows.tool_code",
            parameters={
                "tool_name": "lookup",
                "tool_description": "Look up",
                "parameters_schema": {"type": "object", "properties": {}},
                "python_code": "def run(p,c): return p\n",
            },
        ),
    ]
    connections = {
        "t1": {"main": [[NodeConnection(dest_node_id="exec", connection_type="main", index=0)]]},
        "tool": {"main": [[NodeConnection(dest_node_id="exec", connection_type="flows.tool", index=0)]]},
    }
    new_nodes, new_connections, executor_id = rewire_graph_for_tool_test(
        nodes=nodes,
        connections=connections,
        tool_node_id="tool",
        tool_name="lookup",
        arguments={"q": "test"},
    )
    assert executor_id == "__tool_test_executor__"
    assert any(n["id"] == executor_id for n in new_nodes)
    assert "tool" in new_connections
    tool_edges = new_connections["tool"]["main"][0]
    assert any(c.dest_node_id == executor_id for c in tool_edges)


def test_validate_rejects_duplicate_tool_names_on_consumer() -> None:
    nodes = [
        _node("t1", "flows.trigger.manual"),
        _node("exec", "flows.tool_executor", parameters={"tool_name": "dup"}),
        _node(
            "tool1",
            "flows.tool_code",
            parameters={
                "tool_name": "dup",
                "tool_description": "A",
                "parameters_schema": {"type": "object", "properties": {}},
                "python_code": "def run(p,c): return p\n",
            },
        ),
        _node(
            "tool2",
            "flows.tool_code",
            parameters={
                "tool_name": "dup",
                "tool_description": "B",
                "parameters_schema": {"type": "object", "properties": {}},
                "python_code": "def run(p,c): return p\n",
            },
        ),
    ]
    connections = {
        "t1": {"main": [[NodeConnection(dest_node_id="exec", connection_type="main", index=0)]]},
        "tool1": {"main": [[NodeConnection(dest_node_id="exec", connection_type="flows.tool", index=0)]]},
        "tool2": {"main": [[NodeConnection(dest_node_id="exec", connection_type="flows.tool", index=1)]]},
    }
    with pytest.raises(FlowValidationError, match="Duplicate tool name"):
        validate_revision(nodes, connections, {}, None)
