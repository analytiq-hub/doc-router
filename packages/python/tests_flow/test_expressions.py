from __future__ import annotations

from typing import Any

import pytest

import analytiq_data as ad


def _n(
    id_: str,
    name: str,
    ntype: str,
    x: int,
    params: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "id": id_,
        "name": name,
        "type": ntype,
        "position": [x, 0],
        "parameters": params or {},
        "webhook_id": None,
        "disabled": False,
        "on_error": "stop",
        "retry_on_fail": False,
        "max_tries": 1,
        "wait_between_tries_ms": 1000,
        "notes": None,
    }


class _EchoParamNode:
    """Test-only node that emits a single item with `json.value = parameters.value`."""

    key = "tests.echo_param"
    label = "Echo param"
    description = "Test-only: output parameters.value"
    category = "Test"
    is_trigger = False
    is_merge = False
    min_inputs = 1
    max_inputs = 1
    outputs = 1
    output_labels = ["output"]
    parameter_schema: dict[str, Any] = {
        "type": "object",
        "properties": {"value": {}},
        "required": ["value"],
        "additionalProperties": False,
    }

    def validate_parameters(self, params: dict[str, Any]) -> list[str]:
        return []

    async def execute(
        self,
        context: "ad.flows.ExecutionContext",
        node: dict[str, Any],
        inputs: list[list["ad.flows.FlowItem"]],
    ) -> list[list["ad.flows.FlowItem"]]:
        v = (node.get("parameters") or {}).get("value")
        src = inputs[0][0] if inputs and inputs[0] else None
        return [
            [
                ad.flows.FlowItem(
                    json={"value": v},
                    binary=(dict(src.binary) if src is not None else {}),
                    meta=(dict(src.meta) if src is not None else {}),
                    paired_item=None,
                )
            ]
        ]


class _MultiItemTriggerNode:
    """Trigger that emits two items with distinct json + binary."""

    key = "tests.trigger.multi"
    label = "Multi trigger"
    description = "Test-only: emits two items."
    category = "Test"
    is_trigger = True
    is_merge = False
    min_inputs = 0
    max_inputs = 0
    outputs = 1
    output_labels = ["output"]
    parameter_schema: dict[str, Any] = {"type": "object", "properties": {}, "additionalProperties": False}

    def validate_parameters(self, params: dict[str, Any]) -> list[str]:
        return []

    async def execute(
        self,
        context: "ad.flows.ExecutionContext",
        node: dict[str, Any],
        inputs: list[list["ad.flows.FlowItem"]],
    ) -> list[list["ad.flows.FlowItem"]]:
        a = ad.flows.FlowItem(
            json={"x": 1},
            binary={"f": ad.flows.BinaryRef(mime_type="text/plain", file_name="a.txt")},
            meta={},
            paired_item=None,
        )
        b = ad.flows.FlowItem(
            json={"x": 2},
            binary={"f": ad.flows.BinaryRef(mime_type="text/plain", file_name="b.txt")},
            meta={},
            paired_item=None,
        )
        return [[a, b]]


@pytest.fixture(autouse=True)
def _register_nodes() -> None:
    ad.flows.register_builtin_nodes()
    ad.flows.register(_EchoParamNode())
    ad.flows.register(_MultiItemTriggerNode())


@pytest.mark.asyncio
async def test_expression_resolves_json() -> None:
    nodes = [
        _n("t1", "Start", "flows.trigger.manual", 0),
        _n("e1", "Echo", "tests.echo_param", 200, {"value": "=$json['trigger']['x']"}),
    ]
    conns = {"t1": {"main": [[ad.flows.NodeConnection(dest_node_id="e1", connection_type="main", index=0)]]}}
    ctx = ad.flows.ExecutionContext(
        organization_id="org",
        execution_id="exec",
        flow_id="flow",
        flow_revid="rev",
        mode="manual",
        trigger_data={"x": 5},
        run_data={},
        analytiq_client=None,
        stop_requested=False,
        logger=None,
    )
    res = await ad.flows.run_flow(context=ctx, revision={"nodes": nodes, "connections": conns, "settings": {}, "pin_data": None})
    assert res["status"] == "success"
    out = ctx.run_data["e1"]["data"]["main"][0][0]
    assert out.json["value"] == 5


@pytest.mark.asyncio
async def test_expression_resolves_node_from_prior_run_data() -> None:
    nodes = [
        _n("t1", "Start", "flows.trigger.manual", 0),
        _n("c1", "Code", "flows.code", 200, {"python_code": "def run(items, context):\n    return [{'x': items[0]['trigger']['x']}]\n", "timeout_seconds": 2}),
        _n("e1", "Echo", "tests.echo_param", 400, {"value": "=$node['c1']['main'][0][0]['x']"}),
    ]
    conns = {
        "t1": {"main": [[ad.flows.NodeConnection(dest_node_id="c1", connection_type="main", index=0)]]},
        "c1": {"main": [[ad.flows.NodeConnection(dest_node_id="e1", connection_type="main", index=0)]]},
    }
    ctx = ad.flows.ExecutionContext(
        organization_id="org",
        execution_id="exec",
        flow_id="flow",
        flow_revid="rev",
        mode="manual",
        trigger_data={"x": 7},
        run_data={},
        analytiq_client=None,
        stop_requested=False,
        logger=None,
    )
    res = await ad.flows.run_flow(context=ctx, revision={"nodes": nodes, "connections": conns, "settings": {}, "pin_data": None})
    assert res["status"] == "success"
    out = ctx.run_data["e1"]["data"]["main"][0][0]
    assert out.json["value"] == 7


@pytest.mark.asyncio
async def test_expression_undefined_key_respects_on_error_continue() -> None:
    nodes = [
        _n("t1", "Start", "flows.trigger.manual", 0),
        {**_n("e1", "Echo", "tests.echo_param", 200, {"value": "=$json['nope']"}), "on_error": "continue"},
    ]
    conns = {"t1": {"main": [[ad.flows.NodeConnection(dest_node_id="e1", connection_type="main", index=0)]]}}
    ctx = ad.flows.ExecutionContext(
        organization_id="org",
        execution_id="exec",
        flow_id="flow",
        flow_revid="rev",
        mode="manual",
        trigger_data={},
        run_data={},
        analytiq_client=None,
        stop_requested=False,
        logger=None,
    )
    res = await ad.flows.run_flow(context=ctx, revision={"nodes": nodes, "connections": conns, "settings": {}, "pin_data": None})
    assert res["status"] == "success"
    env = ctx.run_data["e1"]["data"]["main"][0][0]
    assert "_error" in env.json


@pytest.mark.asyncio
async def test_expression_rejects_unsafe_call() -> None:
    nodes = [
        _n("t1", "Start", "flows.trigger.manual", 0),
        {**_n("e1", "Echo", "tests.echo_param", 200, {"value": "=__import__('os')"}), "on_error": "continue"},
    ]
    conns = {"t1": {"main": [[ad.flows.NodeConnection(dest_node_id="e1", connection_type="main", index=0)]]}}
    ctx = ad.flows.ExecutionContext(
        organization_id="org",
        execution_id="exec",
        flow_id="flow",
        flow_revid="rev",
        mode="manual",
        trigger_data={},
        run_data={},
        analytiq_client=None,
        stop_requested=False,
        logger=None,
    )
    res = await ad.flows.run_flow(context=ctx, revision={"nodes": nodes, "connections": conns, "settings": {}, "pin_data": None})
    assert res["status"] == "success"
    env = ctx.run_data["e1"]["data"]["main"][0][0]
    assert "_error" in env.json


@pytest.mark.asyncio
async def test_expression_can_see_pin_data_outputs_via_node() -> None:
    nodes = [
        _n("t1", "Start", "flows.trigger.manual", 0),
        _n("p1", "Pinned", "tests.echo_param", 200, {"value": "literal"}),
        _n("e1", "Echo", "tests.echo_param", 400, {"value": "=$node['p1']['main'][0][0]['a']"}),
    ]
    conns = {
        "t1": {"main": [[ad.flows.NodeConnection(dest_node_id="p1", connection_type="main", index=0)]]},
        "p1": {"main": [[ad.flows.NodeConnection(dest_node_id="e1", connection_type="main", index=0)]]},
    }
    pin_data = {"p1": [{"json": {"a": 9}, "binary": {}, "meta": {}, "paired_item": None}]}
    ctx = ad.flows.ExecutionContext(
        organization_id="org",
        execution_id="exec",
        flow_id="flow",
        flow_revid="rev",
        mode="manual",
        trigger_data={},
        run_data={},
        analytiq_client=None,
        stop_requested=False,
        logger=None,
    )
    res = await ad.flows.run_flow(context=ctx, revision={"nodes": nodes, "connections": conns, "settings": {}, "pin_data": pin_data})
    assert res["status"] == "success"
    out = ctx.run_data["e1"]["data"]["main"][0][0]
    assert out.json["value"] == 9


def test_rewrite_vars_does_not_touch_string_literals() -> None:
    # `$json` inside quotes should remain literal; outside should be rewritten.
    rewritten = ad.flows.expressions._rewrite_vars("'$json' + $json['x']")
    assert rewritten == "'$json' + _json['x']"


@pytest.mark.asyncio
async def test_expressions_resolve_per_item_including_binary() -> None:
    nodes = [
        _n("t1", "Start", "tests.trigger.multi", 0),
        _n("j1", "EchoJson", "tests.echo_param", 200, {"value": "=$json['x']"}),
        _n("b1", "EchoBin", "tests.echo_param", 400, {"value": "=$binary['f']['file_name']"}),
    ]
    conns = {
        "t1": {"main": [[ad.flows.NodeConnection(dest_node_id="j1", connection_type="main", index=0)]]},
        "j1": {"main": [[ad.flows.NodeConnection(dest_node_id="b1", connection_type="main", index=0)]]},
    }
    ctx = ad.flows.ExecutionContext(
        organization_id="org",
        execution_id="exec",
        flow_id="flow",
        flow_revid="rev",
        mode="manual",
        trigger_data={},
        run_data={},
        analytiq_client=None,
        stop_requested=False,
        logger=None,
    )
    res = await ad.flows.run_flow(context=ctx, revision={"nodes": nodes, "connections": conns, "settings": {}, "pin_data": None})
    assert res["status"] == "success"

    j_out = ctx.run_data["j1"]["data"]["main"][0]
    assert [it.json["value"] for it in j_out] == [1, 2]

    b_out = ctx.run_data["b1"]["data"]["main"][0]
    assert [it.json["value"] for it in b_out] == ["a.txt", "b.txt"]

