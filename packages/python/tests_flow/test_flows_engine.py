from __future__ import annotations

from typing import Any

import pytest

from analytiq_data.flows.engine import validate_revision, FlowValidationError
from analytiq_data.flows.connections import NodeConnection
from analytiq_data.flows.node_registry import register
from analytiq_data.flows.register_builtin import register_builtin_nodes
from analytiq_data.flows.context import ExecutionContext
from analytiq_data.flows.items import FlowItem


class _PassThroughNode:
    key = "tests.passthrough"
    label = "Passthrough"
    description = "Test-only passthrough node."
    category = "Test"
    is_trigger = False
    min_inputs = 1
    max_inputs = 1
    outputs = 1
    output_labels = ["output"]
    parameter_schema: dict[str, Any] = {
        "type": "object",
        "properties": {},
        "additionalProperties": False,
    }

    def validate_parameters(self, params: dict[str, Any]) -> list[str]:
        return []

    async def execute(
        self, context: ExecutionContext, node: dict[str, Any], inputs: list[list[FlowItem]]
    ) -> list[list[FlowItem]]:
        return [inputs[0]]


@pytest.fixture(autouse=True)
def _register_nodes() -> None:
    # Overwrite-safe: register() replaces by key.
    register_builtin_nodes()
    register(_PassThroughNode())


def test_validate_revision_accepts_simple_dag() -> None:
    nodes = [
        {
            "id": "t1",
            "name": "Start",
            "type": "flows.trigger.manual",
            "position": [0, 0],
            "parameters": {},
            "webhook_id": None,
            "disabled": False,
            "on_error": "stop",
            "retry_on_fail": False,
            "max_tries": 1,
            "wait_between_tries_ms": 1000,
            "notes": None,
        },
        {
            "id": "n1",
            "name": "Next",
            "type": "tests.passthrough",
            "position": [200, 0],
            "parameters": {},
            "webhook_id": None,
            "disabled": False,
            "on_error": "stop",
            "retry_on_fail": False,
            "max_tries": 1,
            "wait_between_tries_ms": 1000,
            "notes": None,
        },
    ]
    connections = {
        "t1": {
            "main": [
                [NodeConnection(node="n1", connection_type="main", index=0)],
            ]
        }
    }
    validate_revision(nodes, connections, settings={}, pin_data=None)


def test_validate_revision_rejects_cycle() -> None:
    nodes = [
        {"id": "t1", "name": "Start", "type": "flows.trigger.manual", "position": [0, 0], "parameters": {}, "webhook_id": None, "disabled": False, "on_error": "stop", "retry_on_fail": False, "max_tries": 1, "wait_between_tries_ms": 1000, "notes": None},
        {"id": "a1", "name": "A", "type": "tests.passthrough", "position": [200, 0], "parameters": {}, "webhook_id": None, "disabled": False, "on_error": "stop", "retry_on_fail": False, "max_tries": 1, "wait_between_tries_ms": 1000, "notes": None},
        {"id": "b1", "name": "B", "type": "tests.passthrough", "position": [400, 0], "parameters": {}, "webhook_id": None, "disabled": False, "on_error": "stop", "retry_on_fail": False, "max_tries": 1, "wait_between_tries_ms": 1000, "notes": None},
    ]
    connections = {
        "t1": {"main": [[NodeConnection(node="a1", connection_type="main", index=0)]]},
        "a1": {"main": [[NodeConnection(node="b1", connection_type="main", index=0)]]},
        "b1": {"main": [[NodeConnection(node="a1", connection_type="main", index=0)]]},
    }
    with pytest.raises(FlowValidationError, match="cycle|DAG"):
        validate_revision(nodes, connections, settings={}, pin_data=None)

