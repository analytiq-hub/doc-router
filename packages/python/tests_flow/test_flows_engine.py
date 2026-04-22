from __future__ import annotations

"""Minimal unit tests for the flow engine's revision validation rules."""

from typing import Any

import pytest

import analytiq_data as ad


class _PassThroughNode:
    """Test-only node used to validate registry/graph rules without DocRouter deps."""

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
        """No additional validation for test node."""

        return []

    async def execute(
        self,
        context: "ad.flows.ExecutionContext",
        node: dict[str, Any],
        inputs: list[list["ad.flows.FlowItem"]],
    ) -> list[list["ad.flows.FlowItem"]]:
        return [inputs[0]]


@pytest.fixture(autouse=True)
def _register_nodes() -> None:
    """Register built-ins and the test node for each test."""

    # Overwrite-safe: register() replaces by key.
    ad.flows.register_builtin_nodes()
    ad.flows.register(_PassThroughNode())


def test_validate_revision_accepts_simple_dag() -> None:
    """A 2-node DAG (trigger -> node) is accepted."""

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
                [ad.flows.NodeConnection(dest_node_id="n1", connection_type="main", index=0)],
            ]
        }
    }
    ad.flows.validate_revision(nodes, connections, settings={}, pin_data=None)


def test_validate_revision_rejects_cycle() -> None:
    """A cycle among non-trigger nodes is rejected."""

    nodes = [
        {"id": "t1", "name": "Start", "type": "flows.trigger.manual", "position": [0, 0], "parameters": {}, "webhook_id": None, "disabled": False, "on_error": "stop", "retry_on_fail": False, "max_tries": 1, "wait_between_tries_ms": 1000, "notes": None},
        {"id": "a1", "name": "A", "type": "tests.passthrough", "position": [200, 0], "parameters": {}, "webhook_id": None, "disabled": False, "on_error": "stop", "retry_on_fail": False, "max_tries": 1, "wait_between_tries_ms": 1000, "notes": None},
        {"id": "b1", "name": "B", "type": "tests.passthrough", "position": [400, 0], "parameters": {}, "webhook_id": None, "disabled": False, "on_error": "stop", "retry_on_fail": False, "max_tries": 1, "wait_between_tries_ms": 1000, "notes": None},
    ]
    connections = {
        "t1": {"main": [[ad.flows.NodeConnection(dest_node_id="a1", connection_type="main", index=0)]]},
        "a1": {"main": [[ad.flows.NodeConnection(dest_node_id="b1", connection_type="main", index=0)]]},
        "b1": {"main": [[ad.flows.NodeConnection(dest_node_id="a1", connection_type="main", index=0)]]},
    }
    with pytest.raises(ad.flows.FlowValidationError, match="cycle|DAG"):
        ad.flows.validate_revision(nodes, connections, settings={}, pin_data=None)


@pytest.mark.asyncio
async def test_run_flow_executes_code_node() -> None:
    """`flows.code` runs in an isolated subprocess and transforms items."""

    nodes = [
        {"id": "t1", "name": "Start", "type": "flows.trigger.manual", "position": [0, 0], "parameters": {}, "webhook_id": None, "disabled": False, "on_error": "stop", "retry_on_fail": False, "max_tries": 1, "wait_between_tries_ms": 1000, "notes": None},
        {
            "id": "c1",
            "name": "Code",
            "type": "flows.code",
            "position": [200, 0],
            "parameters": {
                "python_code": "def run(items, context):\n    out=[]\n    for it in items:\n        it=dict(it)\n        it['x']=it.get('trigger',{}).get('x',0)+1\n        out.append(it)\n    return out\n",
                "timeout_seconds": 2,
            },
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
        "t1": {"main": [[ad.flows.NodeConnection(dest_node_id="c1", connection_type="main", index=0)]]}
    }

    ctx = ad.flows.ExecutionContext(
        organization_id="org",
        execution_id="exec",
        flow_id="flow",
        flow_revid="rev",
        mode="manual",
        trigger_data={"x": 41},
        run_data={},
        analytiq_client=None,
        stop_requested=False,
        logger=None,
    )
    res = await ad.flows.run_flow(context=ctx, revision={"nodes": nodes, "connections": connections, "settings": {}, "pin_data": None})
    assert res["status"] == "success"
    out_items = ctx.run_data["c1"]["data"]["main"][0]
    assert out_items[0].json["x"] == 42


@pytest.mark.asyncio
async def test_run_flow_branch_and_merge_flush_when_one_branch_skipped() -> None:
    """
    Branch emits empty list on one output => that path is skipped.
    Merge is still executed via the merge flush when the queue drains.
    """

    nodes = [
        {"id": "t1", "name": "Start", "type": "flows.trigger.manual", "position": [0, 0], "parameters": {}, "webhook_id": None, "disabled": False, "on_error": "stop", "retry_on_fail": False, "max_tries": 1, "wait_between_tries_ms": 1000, "notes": None},
        {"id": "b1", "name": "Branch", "type": "flows.branch", "position": [200, 0], "parameters": {"field": "x", "equals": 1}, "webhook_id": None, "disabled": False, "on_error": "stop", "retry_on_fail": False, "max_tries": 1, "wait_between_tries_ms": 1000, "notes": None},
        {"id": "m1", "name": "Merge", "type": "flows.merge", "position": [400, 0], "parameters": {}, "webhook_id": None, "disabled": False, "on_error": "stop", "retry_on_fail": False, "max_tries": 1, "wait_between_tries_ms": 1000, "notes": None},
    ]
    connections = {
        "t1": {"main": [[ad.flows.NodeConnection(dest_node_id="b1", connection_type="main", index=0)]]},
        "b1": {
            "main": [
                [ad.flows.NodeConnection(dest_node_id="m1", connection_type="main", index=0)],  # true
                [ad.flows.NodeConnection(dest_node_id="m1", connection_type="main", index=1)],  # false
            ]
        },
    }

    ctx = ad.flows.ExecutionContext(
        organization_id="org",
        execution_id="exec",
        flow_id="flow",
        flow_revid="rev",
        mode="manual",
        trigger_data={"x": 1},
        run_data={},
        analytiq_client=None,
        stop_requested=False,
        logger=None,
    )
    await ad.flows.run_flow(context=ctx, revision={"nodes": nodes, "connections": connections, "settings": {}, "pin_data": None})

    # Merge should have run and produced one item (from the true branch).
    merged = ctx.run_data["m1"]["data"]["main"][0]
    assert len(merged) == 1

