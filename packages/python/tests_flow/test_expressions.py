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
    icon_key = None
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
    icon_key = None
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


class _SetXNode:
    """Test-only node that outputs json.x = parameters.x (ignores input json)."""

    key = "tests.set_x"
    label = "Set x"
    description = "Test-only: set json.x"
    category = "Test"
    is_trigger = False
    is_merge = False
    min_inputs = 1
    max_inputs = 1
    outputs = 1
    output_labels = ["output"]
    icon_key = None
    parameter_schema: dict[str, Any] = {
        "type": "object",
        "properties": {"x": {"type": "number"}},
        "required": ["x"],
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
        x = (node.get("parameters") or {}).get("x")
        src = inputs[0][0] if inputs and inputs[0] else None
        return [
            [
                ad.flows.FlowItem(
                    json={"x": x},
                    binary=(dict(src.binary) if src is not None else {}),
                    meta=(dict(src.meta) if src is not None else {}),
                    paired_item=None,
                )
            ]
        ]


class _MergeEchoParamNode:
    """Test-only merge node that emits json.value = parameters.value."""

    key = "tests.merge_echo_param"
    label = "Merge echo param"
    description = "Test-only: merge node that outputs parameters.value"
    category = "Test"
    is_trigger = False
    is_merge = True
    min_inputs = 2
    max_inputs = None
    outputs = 1
    output_labels = ["output"]
    icon_key = None
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
        return [[ad.flows.FlowItem(json={"value": v}, binary={}, meta={}, paired_item=None)]]


@pytest.fixture(autouse=True)
def _register_nodes() -> None:
    ad.flows.register_builtin_nodes()
    ad.flows.register(_EchoParamNode())
    ad.flows.register(_MultiItemTriggerNode())
    ad.flows.register(_SetXNode())
    ad.flows.register(_MergeEchoParamNode())


@pytest.mark.asyncio
async def test_expression_resolves_json() -> None:
    nodes = [
        _n("t1", "Start", "flows.trigger.manual", 0),
        _n("e1", "Echo", "tests.echo_param", 200, {"value": "=_json['x']"}),
    ]
    conns = {"t1": {"main": [[ad.flows.NodeConnection(dest_node_id="e1", connection_type="main", index=0)]]}}
    pin_data = {"t1": [{"json": {"x": 5}, "binary": {}, "meta": {}, "paired_item": None}]}
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
    res = await ad.flows.run_flow(
        context=ctx,
        revision={"nodes": nodes, "connections": conns, "settings": {}, "pin_data": pin_data},
    )
    assert res["status"] == "success"
    out = ctx.run_data["e1"]["data"]["main"][0][0]
    assert out.json["value"] == 5


@pytest.mark.asyncio
async def test_merge_node_expression_can_reference_all_inputs() -> None:
    nodes = [
        _n("t1", "Start", "flows.trigger.manual", 0),
        _n("a1", "A", "tests.set_x", 200, {"x": 1}),
        _n("b1", "B", "tests.set_x", 200, {"x": 2}),
        _n(
            "m1",
            "MergeEcho",
            "tests.merge_echo_param",
            400,
            {"value": "=_input['all'][1][0]['json']['x']"},
        ),
    ]
    conns = {
        "t1": {
            "main": [
                [
                    ad.flows.NodeConnection(dest_node_id="a1", connection_type="main", index=0),
                    ad.flows.NodeConnection(dest_node_id="b1", connection_type="main", index=0),
                ]
            ]
        },
        "a1": {"main": [[ad.flows.NodeConnection(dest_node_id="m1", connection_type="main", index=0)]]},
        "b1": {"main": [[ad.flows.NodeConnection(dest_node_id="m1", connection_type="main", index=1)]]},
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
    out = ctx.run_data["m1"]["data"]["main"][0][0]
    assert out.json["value"] == 2


@pytest.mark.asyncio
async def test_per_item_expression_can_access_current_input_item_via_input_item() -> None:
    nodes = [
        _n("t1", "Start", "tests.trigger.multi", 0),
        _n("e1", "Echo", "tests.echo_param", 200, {"value": "=_input['item']['json']['x']"}),
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
    out_items = ctx.run_data["e1"]["data"]["main"][0]
    assert [it.json["value"] for it in out_items] == [1, 2]


@pytest.mark.asyncio
async def test_expression_resolves_node_from_prior_run_data() -> None:
    nodes = [
        _n("t1", "Start", "flows.trigger.manual", 0),
        _n(
            "c1",
            "Code",
            "flows.code",
            200,
            {"python_code": "def run(items, context):\n    return [{'x': context['trigger']['x']}]\n", "timeout_seconds": 2},
        ),
        _n("e1", "Echo", "tests.echo_param", 400, {"value": "=_node['Code'].json['x']"}),
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
        {**_n("e1", "Echo", "tests.echo_param", 200, {"value": "=_json['nope']"}), "on_error": "continue"},
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
        _n("e1", "Echo", "tests.echo_param", 400, {"value": "=_node['Pinned'].json['a']"}),
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


def test_materialize_node_data_preserves_timing_fields() -> None:
    rd = {
        "n1": {
            "status": "success",
            "start_time": "2026-04-30T23:26:46.907441+00:00",
            "execution_time_ms": 52,
            "data": {"main": [[]]},
        },
    }
    m = ad.flows.expressions.materialize_node_data(rd)
    assert m["n1"]["status"] == "success"
    assert m["n1"]["start_time"] == "2026-04-30T23:26:46.907441+00:00"
    assert m["n1"]["execution_time_ms"] == 52


def test_materialize_node_data_unwraps_json_wrapped_items() -> None:
    rd = {
        "c1": {
            "status": "success",
            "data": {"main": [[{"json": {"url": "https://mit.edu"}, "binary": {}}]]},
        },
    }
    m = ad.flows.expressions.materialize_node_data(rd)
    assert m["c1"]["main"][0][0]["url"] == "https://mit.edu"


def test_preview_parameter_expression_resolves_json() -> None:
    val, err = ad.flows.preview_parameter_expression(
        "=_json['url']",
        run_data={},
        input_items_json=[{"url": "https://mit.edu"}],
        preview_item_index=0,
        execution_refs=None,
    )
    assert err is None
    assert val == "https://mit.edu"


def test_preview_parameter_expression_resolves_node_main_from_serialized_run_data() -> None:
    run_data = {"c1": {"status": "success", "data": {"main": [[{"json": {"x": 40}, "binary": {}}]]}}}
    val, err = ad.flows.preview_parameter_expression(
        '=_node["Code"].json["x"]',
        run_data=run_data,
        input_items_json=[{}],
        preview_item_index=0,
        execution_refs=None,
        revision_nodes=[_n("c1", "Code", "flows.code", 0)],
    )
    assert err is None
    assert val == 40


def test_eval_expression_errors_on_node_json_when_item_index_unset() -> None:
    run_data = {
        "c1": {
            "status": "success",
            "data": {"main": [[{"json": {"x": 1}, "binary": {}}]]},
        }
    }
    rev = [_n("c1", "Code", "flows.code", 0)]
    with pytest.raises(ad.flows.ExpressionError, match="item_index"):
        ad.flows.eval_expression(
            "_node['Code'].json['x']",
            item=None,
            run_data=run_data,
            input_context={"all": [], "item": None, "input_index": None, "item_index": None},
            revision_nodes=rev,
        )


@pytest.mark.asyncio
async def test_merge_node_parameter_resolution_errors_on_node_json_without_item_index() -> None:
    nodes = [
        _n("t1", "Start", "flows.trigger.manual", 0),
        _n("a1", "LaneA", "tests.set_x", 200, {"x": 1}),
        _n("b1", "LaneB", "tests.set_x", 200, {"x": 2}),
        _n("m1", "MergeEcho", "tests.merge_echo_param", 400, {"value": "=_node['LaneA'].json['x']"}),
    ]
    conns = {
        "t1": {
            "main": [
                [
                    ad.flows.NodeConnection(dest_node_id="a1", connection_type="main", index=0),
                    ad.flows.NodeConnection(dest_node_id="b1", connection_type="main", index=0),
                ]
            ]
        },
        "a1": {"main": [[ad.flows.NodeConnection(dest_node_id="m1", connection_type="main", index=0)]]},
        "b1": {"main": [[ad.flows.NodeConnection(dest_node_id="m1", connection_type="main", index=1)]]},
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
    with pytest.raises(ad.flows.ExpressionError, match="item_index"):
        await ad.flows.run_flow(context=ctx, revision={"nodes": nodes, "connections": conns, "settings": {}, "pin_data": None})


def test_expression_allowlists_safe_builtin_calls_like_str() -> None:
    item = ad.flows.FlowItem(json={"foo": 42}, binary={}, meta={}, paired_item=None)
    got = ad.flows.eval_expression('str(_json["foo"])', item=item, run_data={})
    assert got == "42"


def test_expression_rejects_disallowed_builtin_calls() -> None:
    item = ad.flows.FlowItem(json={}, binary={}, meta={}, paired_item=None)
    with pytest.raises(ad.flows.ExpressionError, match="not allowed"):
        ad.flows.eval_expression('open(".")', item=item, run_data={})


def test_expression_rejects_f_string_prefix_with_hint() -> None:
    item = ad.flows.FlowItem(json={"x": 1}, binary={}, meta={}, paired_item=None)
    with pytest.raises(ad.flows.ExpressionError, match="f-strings"):
        ad.flows.eval_expression('f"{_json}"', item=item, run_data={})


def test_expression_syntaxerror_fstring_maps_to_hint() -> None:
    item = ad.flows.FlowItem(json={"x": 1}, binary={}, meta={}, paired_item=None)
    with pytest.raises(ad.flows.ExpressionError, match="f-string syntax"):
        # Does not start with ``f`` (prefix guard skipped), but still triggers the parser's f-string diagnostic.
        ad.flows.eval_expression('""+f"{1+}"', item=item, run_data={})


@pytest.mark.asyncio
async def test_expressions_resolve_per_item_including_binary() -> None:
    nodes = [
        _n("t1", "Start", "tests.trigger.multi", 0),
        _n("j1", "EchoJson", "tests.echo_param", 200, {"value": "=_json['x']"}),
        _n("b1", "EchoBin", "tests.echo_param", 400, {"value": "=_binary['f']['file_name']"}),
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


@pytest.mark.asyncio
async def test_expression_can_read_execution_refs() -> None:
    nodes = [
        _n("t1", "Start", "flows.trigger.manual", 0),
        _n(
            "e1",
            "Echo",
            "tests.echo_param",
            200,
            {"value": "=_execution['execution_id'] + '|' + _execution['flow_id'] + '|' + _execution['flow_revid']"},
        ),
    ]
    conns = {"t1": {"main": [[ad.flows.NodeConnection(dest_node_id="e1", connection_type="main", index=0)]]}}
    ctx = ad.flows.ExecutionContext(
        organization_id="org",
        execution_id="exec-abc",
        flow_id="flow-xyz",
        flow_revid="rev-222",
        mode="manual",
        trigger_data={},
        run_data={},
        analytiq_client=None,
        stop_requested=False,
        logger=None,
    )
    res = await ad.flows.run_flow(context=ctx, revision={"nodes": nodes, "connections": conns, "settings": {}, "pin_data": None})
    assert res["status"] == "success"
    assert ctx.run_data["e1"]["data"]["main"][0][0].json["value"] == "exec-abc|flow-xyz|rev-222"


@pytest.mark.asyncio
async def test_expression_reads_source_run_timing() -> None:
    nodes = [
        _n("t1", "Start", "flows.trigger.manual", 0),
        _n("e_st", "EchoStart", "tests.echo_param", 200, {"value": "=_start_time"}),
        _n("e_et", "EchoMs", "tests.echo_param", 400, {"value": "=_execution_time"}),
    ]
    conns = {
        "t1": {
            "main": [
                [
                    ad.flows.NodeConnection(dest_node_id="e_st", connection_type="main", index=0),
                    ad.flows.NodeConnection(dest_node_id="e_et", connection_type="main", index=0),
                ]
            ]
        }
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
    st = ctx.run_data["t1"].get("start_time")
    et = ctx.run_data["t1"].get("execution_time_ms")
    assert isinstance(st, str) and len(st) > 0
    assert isinstance(et, int)
    assert ctx.run_data["e_st"]["data"]["main"][0][0].json["value"] == st
    assert ctx.run_data["e_et"]["data"]["main"][0][0].json["value"] == et

