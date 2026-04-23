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
    is_merge = False
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


class _TagItemNode:
    """Test-only node: tags each item with `path_tag` from parameters (for merge ordering)."""

    key = "tests.tag"
    label = "Tag"
    description = "Test-only: copy items and set json['path_tag']."
    category = "Test"
    is_trigger = False
    is_merge = False
    min_inputs = 1
    max_inputs = 1
    outputs = 1
    output_labels = ["output"]
    parameter_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "tag": {"type": "string"},
        },
        "required": ["tag"],
        "additionalProperties": False,
    }

    def validate_parameters(self, params: dict[str, Any]) -> list[str]:
        if not isinstance(params.get("tag"), str) or not params.get("tag"):
            return ["parameters.tag must be a non-empty string"]
        return []

    async def execute(
        self,
        context: "ad.flows.ExecutionContext",
        node: dict[str, Any],
        inputs: list[list["ad.flows.FlowItem"]],
    ) -> list[list["ad.flows.FlowItem"]]:
        tag = node.get("parameters", {}).get("tag", "")
        out: list[ad.flows.FlowItem] = []
        for it in inputs[0]:
            j = {**it.json, "path_tag": tag}
            out.append(
                ad.flows.FlowItem(
                    json=j,
                    binary=it.binary,
                    meta=it.meta,
                    paired_item=it.paired_item,
                )
            )
        return [out]


class _ListParamsEchoNode:
    """Test-only node: echoes list-typed `ids` from parameters in output `json` (ignores input items)."""

    key = "tests.listparams"
    label = "List params"
    description = "Test-only: emit parameters.ids in output for list-parameter coverage."
    category = "Test"
    is_trigger = False
    is_merge = False
    min_inputs = 1
    max_inputs = 1
    outputs = 1
    output_labels = ["output"]
    parameter_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "ids": {
                "type": "array",
                "items": {"type": "string"},
            },
        },
        "required": ["ids"],
        "additionalProperties": False,
    }

    def validate_parameters(self, params: dict[str, Any]) -> list[str]:
        ids = params.get("ids")
        if not isinstance(ids, list):
            return ["parameters.ids must be a list"]
        if not all(isinstance(x, str) for x in ids):
            return ["parameters.ids must be a list of strings"]
        return []

    async def execute(
        self,
        context: "ad.flows.ExecutionContext",
        node: dict[str, Any],
        inputs: list[list["ad.flows.FlowItem"]],
    ) -> list[list["ad.flows.FlowItem"]]:
        ids = list(node.get("parameters", {}).get("ids", []))
        item = ad.flows.FlowItem(
            json={"ids": ids},
            binary={},
            meta={},
            paired_item=None,
        )
        return [[item]]


class _BinaryAttachNode:
    """Test-only node: add a `BinaryRef` to each item (preserves `json`)."""

    key = "tests.attach_binary"
    label = "Attach binary"
    description = "Test-only: set FlowItem.binary for propagation tests."
    category = "Test"
    is_trigger = False
    is_merge = False
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
        self,
        context: "ad.flows.ExecutionContext",
        node: dict[str, Any],
        inputs: list[list["ad.flows.FlowItem"]],
    ) -> list[list["ad.flows.FlowItem"]]:
        ref = ad.flows.BinaryRef(
            mime_type="text/plain",
            data=b"flow-test-bytes",
            file_name="t.bin",
        )
        out: list[ad.flows.FlowItem] = []
        for it in inputs[0]:
            b = {**it.binary, "f": ref}
            out.append(
                ad.flows.FlowItem(
                    json=it.json,
                    binary=b,
                    meta=it.meta,
                    paired_item=it.paired_item,
                )
            )
        return [out]


@pytest.fixture(autouse=True)
def _register_nodes() -> None:
    """Register built-ins and the test node for each test."""

    # Overwrite-safe: register() replaces by key.
    ad.flows.register_builtin_nodes()
    ad.flows.register(_PassThroughNode())
    ad.flows.register(_TagItemNode())
    ad.flows.register(_ListParamsEchoNode())
    ad.flows.register(_BinaryAttachNode())


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


@pytest.mark.asyncio
async def test_run_flow_list_shaped_node_parameters() -> None:
    """List-typed `parameters` (e.g. string arrays) are passed through to node execution."""

    nodes = [
        _n("t1", "Start", "flows.trigger.manual", 0),
        _n("l1", "List", "tests.listparams", 200, {"ids": ["a", "b", "c"]}),
    ]
    connections = {
        "t1": {
            "main": [
                [ad.flows.NodeConnection(dest_node_id="l1", connection_type="main", index=0)],
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
    res = await ad.flows.run_flow(
        context=ctx, revision={"nodes": nodes, "connections": connections, "settings": {}, "pin_data": None}
    )
    assert res["status"] == "success"
    out = ctx.run_data["l1"]["data"]["main"][0]
    assert len(out) == 1
    assert out[0].json["ids"] == ["a", "b", "c"]


@pytest.mark.asyncio
async def test_run_flow_merge_both_inputs_concat_in_slot_order() -> None:
    """
    When merge receives data on all input slots, output order is slot 0 then slot 1, ...
    (per `flows.merge` implementation).
    """

    nodes = [
        _n("t1", "Start", "flows.trigger.manual", 0),
        _n("g1", "T1", "tests.tag", 200, {"tag": "first"}),
        _n("g2", "T2", "tests.tag", 200, {"tag": "second"}),
        _n("m1", "Merge", "flows.merge", 400, {}),
    ]
    connections = {
        "t1": {
            "main": [
                [
                    ad.flows.NodeConnection(dest_node_id="g1", connection_type="main", index=0),
                    ad.flows.NodeConnection(dest_node_id="g2", connection_type="main", index=0),
                ],
            ]
        },
        "g1": {
            "main": [[ad.flows.NodeConnection(dest_node_id="m1", connection_type="main", index=0)]],
        },
        "g2": {
            "main": [[ad.flows.NodeConnection(dest_node_id="m1", connection_type="main", index=1)]],
        },
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
    res = await ad.flows.run_flow(
        context=ctx, revision={"nodes": nodes, "connections": connections, "settings": {}, "pin_data": None}
    )
    assert res["status"] == "success"
    merged = ctx.run_data["m1"]["data"]["main"][0]
    assert [it.json.get("path_tag") for it in merged] == ["first", "second"]


@pytest.mark.asyncio
async def test_run_flow_branch_true_and_false_outputs_by_trigger_field() -> None:
    """
    Branch must route items explicitly to `main[0]` (true) vs `main[1]` (false),
    not only by implicit wiring. Manual trigger places payload under `json['trigger']`.
    """

    async def _run(equals: dict[str, Any]) -> dict[str, Any]:
        nodes = [
            _n("t1", "Start", "flows.trigger.manual", 0),
            _n("b1", "Branch", "flows.branch", 200, {"field": "trigger", "equals": equals}),
        ]
        connections = {
            "t1": {
                "main": [[ad.flows.NodeConnection(dest_node_id="b1", connection_type="main", index=0)]],
            }
        }
        ctx = ad.flows.ExecutionContext(
            organization_id="org",
            execution_id="exec",
            flow_id="flow",
            flow_revid="rev",
            mode="manual",
            trigger_data={"k": 1},
            run_data={},
            analytiq_client=None,
            stop_requested=False,
            logger=None,
        )
        res = await ad.flows.run_flow(
            context=ctx, revision={"nodes": nodes, "connections": connections, "settings": {}, "pin_data": None}
        )
        assert res["status"] == "success"
        return ctx.run_data

    data_true = await _run({"k": 1})
    b_true = data_true["b1"]["data"]["main"]
    assert [len(b_true[0]), len(b_true[1])] == [1, 0]

    data_false = await _run({"k": 0})
    b_false = data_false["b1"]["data"]["main"]
    assert [len(b_false[0]), len(b_false[1])] == [0, 1]


@pytest.mark.asyncio
async def test_run_flow_flowitem_binary_propagates_through_passthrough() -> None:
    """`FlowItem.binary` is preserved when nodes pass items through the graph."""

    nodes = [
        _n("t1", "Start", "flows.trigger.manual", 0),
        _n("a1", "Attach", "tests.attach_binary", 200),
        _n("p1", "Pass", "tests.passthrough", 400),
    ]
    connections = {
        "t1": {
            "main": [[ad.flows.NodeConnection(dest_node_id="a1", connection_type="main", index=0)]],
        },
        "a1": {
            "main": [[ad.flows.NodeConnection(dest_node_id="p1", connection_type="main", index=0)]],
        },
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
    res = await ad.flows.run_flow(
        context=ctx, revision={"nodes": nodes, "connections": connections, "settings": {}, "pin_data": None}
    )
    assert res["status"] == "success"
    b_a = ctx.run_data["a1"]["data"]["main"][0][0]
    b_p = ctx.run_data["p1"]["data"]["main"][0][0]
    assert b_a.binary["f"].data == b"flow-test-bytes"
    assert b_p.binary["f"].data == b"flow-test-bytes"


@pytest.mark.asyncio
async def test_run_flow_pin_data_coerces_raw_dict_items_to_flowitems() -> None:
    """
    `pin_data` loaded from storage can be plain dicts; engine must coerce them to `FlowItem`
    so downstream nodes can access `.json` / `.binary` / `.meta` attributes.
    """

    nodes = [
        _n("t1", "Start", "flows.trigger.manual", 0),
        _n("p1", "Pinned", "tests.passthrough", 200),
        _n("g1", "Tag", "tests.tag", 400, {"tag": "ok"}),
    ]
    connections = {
        "t1": {"main": [[ad.flows.NodeConnection(dest_node_id="p1", connection_type="main", index=0)]]},
        "p1": {"main": [[ad.flows.NodeConnection(dest_node_id="g1", connection_type="main", index=0)]]},
    }
    pin_data = {
        "p1": [
            {"json": {"hello": "world"}, "binary": {}, "meta": {"m": 1}, "paired_item": None},
        ]
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
    res = await ad.flows.run_flow(
        context=ctx,
        revision={"nodes": nodes, "connections": connections, "settings": {}, "pin_data": pin_data},
    )
    assert res["status"] == "success"

    pinned_out = ctx.run_data["p1"]["data"]["main"][0]
    assert isinstance(pinned_out[0], ad.flows.FlowItem)
    assert pinned_out[0].json["hello"] == "world"

    tagged = ctx.run_data["g1"]["data"]["main"][0]
    assert tagged[0].json["path_tag"] == "ok"


@pytest.mark.asyncio
async def test_run_flow_pin_data_coerces_binary_ref_dicts() -> None:
    """Pinned dict binary refs must become `BinaryRef` objects in `FlowItem.binary`."""

    nodes = [
        _n("t1", "Start", "flows.trigger.manual", 0),
        _n("p1", "Pinned", "tests.passthrough", 200),
    ]
    connections = {
        "t1": {"main": [[ad.flows.NodeConnection(dest_node_id="p1", connection_type="main", index=0)]]},
    }
    pin_data = {
        "p1": [
            {
                "json": {"x": 1},
                "binary": {
                    "f": {
                        "mime_type": "text/plain",
                        "file_name": "x.txt",
                        "data": b"abc",
                        "storage_id": "s1",
                    }
                },
                "meta": {},
                "paired_item": None,
            }
        ]
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
    res = await ad.flows.run_flow(
        context=ctx,
        revision={"nodes": nodes, "connections": connections, "settings": {}, "pin_data": pin_data},
    )
    assert res["status"] == "success"

    pinned_item = ctx.run_data["p1"]["data"]["main"][0][0]
    assert isinstance(pinned_item, ad.flows.FlowItem)
    assert isinstance(pinned_item.binary["f"], ad.flows.BinaryRef)
    assert pinned_item.binary["f"].mime_type == "text/plain"
    assert pinned_item.binary["f"].file_name == "x.txt"
    assert pinned_item.binary["f"].data == b"abc"
    assert pinned_item.binary["f"].storage_id == "s1"


@pytest.mark.asyncio
async def test_flows_code_context_includes_nodes_materialized_run_data() -> None:
    """`flows.code` gets context['nodes'][node_id]['main'] with JSON-only prior outputs."""

    nodes = [
        _n("t1", "Start", "flows.trigger.manual", 0),
        _n("p1", "Pinned", "tests.passthrough", 200),
        _n(
            "c1",
            "Code",
            "flows.code",
            400,
            {
                "python_code": (
                    "def run(items, context):\n"
                    "    a = context['nodes']['p1']['main'][0][0]['a']\n"
                    "    return [{'y': a + 1}]\n"
                ),
                "timeout_seconds": 2,
            },
        ),
    ]
    connections = {
        "t1": {"main": [[ad.flows.NodeConnection(dest_node_id="p1", connection_type="main", index=0)]]},
        "p1": {"main": [[ad.flows.NodeConnection(dest_node_id="c1", connection_type="main", index=0)]]},
    }
    pin_data = {"p1": [{"json": {"a": 41}, "binary": {}, "meta": {}, "paired_item": None}]}

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
    res = await ad.flows.run_flow(
        context=ctx,
        revision={"nodes": nodes, "connections": connections, "settings": {}, "pin_data": pin_data},
    )
    assert res["status"] == "success"
    out = ctx.run_data["c1"]["data"]["main"][0]
    assert out[0].json["y"] == 42

