from __future__ import annotations

import pytest

import analytiq_data as ad


def test_node_error_envelope_includes_stack() -> None:
    try:
        raise RuntimeError("boom")
    except RuntimeError as e:
        env = ad.flows.node_error_envelope(e, node_id="n1", node_name="Fail", include_stack=True)
    assert env["message"] == "boom"
    assert env["node_id"] == "n1"
    assert env["cause"] == "RuntimeError"
    assert isinstance(env["stack"], str)
    assert "RuntimeError: boom" in env["stack"]


def test_node_error_envelope_skips_stack_for_validation_error() -> None:
    try:
        raise ad.flows.FlowValidationError("bad graph")
    except ad.flows.FlowValidationError as e:
        env = ad.flows.node_error_envelope(e, node_id="n1", node_name="X", include_stack=False)
    assert env["stack"] is None
    assert env["message"] == "bad graph"


def test_execution_error_envelope_prefers_run_data_node_error() -> None:
    run_data = {
        "b1": {
            "status": "error",
            "execution_index": 2,
            "error": {
                "message": "node failed",
                "node_id": "b1",
                "node_name": "B",
                "stack": "Traceback...",
                "cause": "RuntimeError",
            },
        }
    }
    env = ad.flows.execution_error_envelope(RuntimeError("outer"), run_data=run_data)
    assert env["message"] == "node failed"
    assert env["node_id"] == "b1"


@pytest.mark.asyncio
async def test_failed_node_run_data_includes_stack() -> None:
    ad.flows.register_builtin_nodes()

    class _FailNode:
        key = "tests.fail_once"
        label = "Fail"
        description = "Test fail node."
        category = "Test"
        is_trigger = False
        is_merge = False
        min_inputs = 1
        max_inputs = 1
        outputs = 1
        output_labels = ["main"]
        icon_key = None
        parameter_schema = {"type": "object", "properties": {}, "additionalProperties": False}

        def validate_parameters(self, params):
            return []

        async def execute(self, context, node, inputs):
            raise RuntimeError("node boom")

    ad.flows.register(_FailNode())
    nodes = [
        {
            "id": "t1",
            "name": "Start",
            "type": "flows.trigger.manual",
            "position": [0, 0],
            "parameters": {},
            "disabled": False,
            "on_error": "stop",
        },
        {
            "id": "f1",
            "name": "Fail",
            "type": "tests.fail_once",
            "position": [200, 0],
            "parameters": {},
            "disabled": False,
            "on_error": "stop",
        },
    ]
    connections = {"t1": {"main": [[{"dest_node_id": "f1", "connection_type": "main", "index": 0}]]}}
    rev = {"nodes": nodes, "connections": connections, "settings": {}, "pin_data": None}
    ctx = ad.flows.ExecutionContext(
        organization_id="org",
        execution_id="e1",
        flow_id="f1",
        flow_revid="r1",
        mode="manual",
        trigger_data={},
        run_data={},
        analytiq_client=None,
    )
    with pytest.raises(RuntimeError, match="node boom"):
        await ad.flows.run_flow(context=ctx, revision=rev)

    entry = ctx.run_data["f1"]
    assert entry["status"] == "error"
    assert entry["execution_index"] == 2
    err = entry["error"]
    assert err["message"] == "node boom"
    assert isinstance(err["stack"], str)
    assert "RuntimeError" in err["stack"]
