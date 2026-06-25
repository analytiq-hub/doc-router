from __future__ import annotations

"""Minimal unit tests for the flow engine's revision validation rules."""

import asyncio
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
    icon_key = None
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
    icon_key = None
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
    icon_key = None
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
    icon_key = None
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


class _SlowPassNode:
    """Test-only node: delays before passing items through (parallel-branch timing tests)."""

    key = "tests.slow_pass"
    label = "Slow pass"
    description = "Test-only: asyncio sleep then pass input items through."
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
        "properties": {
            "delay_ms": {"type": "integer", "default": 50},
            "marker": {"type": "string"},
        },
        "required": ["marker"],
        "additionalProperties": False,
    }

    def validate_parameters(self, params: dict[str, Any]) -> list[str]:
        if not isinstance(params.get("marker"), str) or not params.get("marker"):
            return ["parameters.marker must be a non-empty string"]
        return []

    async def execute(
        self,
        context: "ad.flows.ExecutionContext",
        node: dict[str, Any],
        inputs: list[list["ad.flows.FlowItem"]],
    ) -> list[list["ad.flows.FlowItem"]]:
        params = node.get("parameters") or {}
        delay_ms = int(params.get("delay_ms") or 50)
        marker = str(params["marker"])
        await asyncio.sleep(delay_ms / 1000.0)
        out: list[ad.flows.FlowItem] = []
        for it in inputs[0]:
            out.append(
                ad.flows.FlowItem(
                    json={**it.json, "branch_marker": marker},
                    binary=it.binary,
                    meta=it.meta,
                    paired_item=it.paired_item,
                )
            )
        return [out]


class _OptionalMergeRecordNode:
    """Test-only merge node (``min_inputs=1``, ``max_inputs=2``) that records both input slots."""

    key = "tests.optional_merge_record"
    label = "Optional merge record"
    description = "Test-only: merge with optional second input port."
    category = "Test"
    is_trigger = False
    is_merge = True
    min_inputs = 1
    max_inputs = 2
    outputs = 1
    output_labels = ["output"]
    icon_key = None
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
        slot1 = inputs[1] if len(inputs) > 1 else []
        markers = [it.json.get("branch_marker") for it in slot1]
        item = ad.flows.FlowItem(
            json={
                "slot0_count": len(inputs[0]),
                "slot1_count": len(slot1),
                "slot1_markers": markers,
            },
            binary={},
            meta={},
            paired_item=None,
        )
        return [[item]]


@pytest.fixture(autouse=True)
def _register_nodes() -> None:
    """Register built-ins and the test node for each test."""

    # Overwrite-safe: register() replaces by key.
    ad.flows.register_builtin_nodes()
    ad.flows.register(_PassThroughNode())
    ad.flows.register(_TagItemNode())
    ad.flows.register(_ListParamsEchoNode())
    ad.flows.register(_BinaryAttachNode())
    ad.flows.register(_SlowPassNode())
    ad.flows.register(_OptionalMergeRecordNode())


def test_validate_revision_accepts_schedule_trigger_croniter_valid_cron(_register_nodes) -> None:
    nodes = [
        {
            "id": "t1",
            "name": "Schedule",
            "type": "flows.trigger.schedule",
            "position": [0, 0],
            "parameters": {
                "rule": {
                    "interval": [
                        {"field": "cronExpression", "cronExpression": "0 * * * 1,2,3-1"},
                        {"field": "cronExpression", "cronExpression": "0 * * * * 1"},
                    ]
                },
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
    ad.flows.validate_revision(nodes, {}, {}, None)


def test_validate_revision_rejects_schedule_trigger_invalid_cron(_register_nodes) -> None:
    nodes = [
        {
            "id": "t1",
            "name": "Schedule",
            "type": "flows.trigger.schedule",
            "position": [0, 0],
            "parameters": {
                "rule": {"interval": [{"field": "cronExpression", "cronExpression": "not a cron"}]},
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
    with pytest.raises(ad.flows.FlowValidationError, match="Invalid cron expression"):
        ad.flows.validate_revision(nodes, {}, {}, None)


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


def _manual_trig(nid: str, name: str) -> dict[str, Any]:
    return {
        "id": nid,
        "name": name,
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
    }


def _pass_next(nid: str, name: str) -> dict[str, Any]:
    return {
        "id": nid,
        "name": name,
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
    }


def test_validate_revision_rejects_graph_with_no_trigger() -> None:
    nodes = [
        _pass_next("n1", "A"),
    ]
    with pytest.raises(ad.flows.FlowValidationError, match="at least one trigger"):
        ad.flows.validate_revision(nodes, {}, {}, None)


def test_validate_revision_rejects_empty_graph() -> None:
    """A revision must contain at least one trigger; an empty canvas is invalid to persist."""
    with pytest.raises(ad.flows.FlowValidationError, match="at least one trigger"):
        ad.flows.validate_revision([], {}, {}, None)


def test_validate_revision_rejects_empty_graph_with_connections_or_pins() -> None:
    with pytest.raises(ad.flows.FlowValidationError, match="no nodes"):
        ad.flows.validate_revision([], {"x": {"main": [[]]}}, {}, None)
    with pytest.raises(ad.flows.FlowValidationError, match="no nodes"):
        ad.flows.validate_revision([], {}, {}, {"n1": {"main": []}})


def test_validate_revision_accepts_two_disjoint_trigger_subgraphs() -> None:
    nodes = [
        _manual_trig("t1", "One"),
        _manual_trig("t2", "Two"),
        _pass_next("a1", "A"),
        _pass_next("b1", "B"),
    ]
    connections = {
        "t1": {"main": [[ad.flows.NodeConnection(dest_node_id="a1", connection_type="main", index=0)]]},
        "t2": {"main": [[ad.flows.NodeConnection(dest_node_id="b1", connection_type="main", index=0)]]},
    }
    ad.flows.validate_revision(nodes, connections, {}, None)


def test_validate_revision_rejects_orphan_unreachable_from_triggers() -> None:
    nodes = [
        _manual_trig("t1", "One"),
        _manual_trig("t2", "Two"),
        _pass_next("a1", "A"),
        _pass_next("orph", "Lonely"),
    ]
    connections = {
        "t1": {"main": [[ad.flows.NodeConnection(dest_node_id="a1", connection_type="main", index=0)]]},
        "t2": {"main": [[]]},
    }
    with pytest.raises(ad.flows.FlowValidationError, match="not reachable from any trigger"):
        ad.flows.validate_revision(nodes, connections, {}, None)


@pytest.mark.asyncio
async def test_run_flow_full_run_requires_start_trigger_when_multiple() -> None:
    nodes = [
        _manual_trig("t1", "One"),
        _manual_trig("t2", "Two"),
        _pass_next("a1", "A"),
        _pass_next("b1", "B"),
    ]
    connections = {
        "t1": {"main": [[ad.flows.NodeConnection(dest_node_id="a1", connection_type="main", index=0)]]},
        "t2": {"main": [[ad.flows.NodeConnection(dest_node_id="b1", connection_type="main", index=0)]]},
    }
    rev = {"nodes": nodes, "connections": connections, "settings": {}, "pin_data": None}
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
    with pytest.raises(ad.flows.FlowValidationError, match="multiple triggers"):
        await ad.flows.run_flow(context=ctx, revision=rev)


def test_prune_run_data_outside_closure_respects_forward_reachable_multi_trigger_seed() -> None:
    """Full multi-trigger runs scope ``allowed_pins`` to forward reach — prune must use the same set."""

    nodes = [
        _manual_trig("t1", "One"),
        _manual_trig("t2", "Two"),
        _pass_next("a1", "A"),
        _pass_next("b1", "B"),
    ]
    connections = {
        "t1": {"main": [[ad.flows.NodeConnection(dest_node_id="a1", connection_type="main", index=0)]]},
        "t2": {"main": [[ad.flows.NodeConnection(dest_node_id="b1", connection_type="main", index=0)]]},
    }
    conns_dc = ad.flows.coerce_json_connections_to_dataclasses(connections)
    scope = frozenset(ad.flows.trigger_forward_reachable_nodes("t2", conns_dc))
    run_data = {
        "t1": {"status": "success", "data": {"main": [[]]}, "execution_time_ms": 0},
        "a1": {"status": "success", "data": {"main": [[]]}, "execution_time_ms": 0},
        "t2": {"status": "success", "data": {"main": [[]]}, "execution_time_ms": 0},
    }
    ad.flows.prune_run_data_outside_closure(run_data, scope)
    assert set(run_data.keys()) == {"t2"}


def test_trigger_forward_reachable_pins_do_not_seed_other_manual_branch_run_data() -> None:
    """Pins on manual trigger ``t1`` must not preload ``run_data`` when scoping for a ``t2`` full run."""

    nodes = [
        _manual_trig("t1", "One"),
        _manual_trig("t2", "Two"),
        _pass_next("a1", "A"),
        _pass_next("b1", "B"),
    ]
    connections = {
        "t1": {"main": [[ad.flows.NodeConnection(dest_node_id="a1", connection_type="main", index=0)]]},
        "t2": {"main": [[ad.flows.NodeConnection(dest_node_id="b1", connection_type="main", index=0)]]},
    }
    conns_dc = ad.flows.coerce_json_connections_to_dataclasses(connections)
    pin_data = {"t1": [{"json": {"pinned": True}, "binary": {}, "meta": {}, "paired_item": None}]}
    revision = {"nodes": nodes, "connections": connections, "settings": {}, "pin_data": pin_data}

    rd: dict = {}
    scope = frozenset(ad.flows.trigger_forward_reachable_nodes("t2", conns_dc))
    ad.flows.apply_revision_pins_to_run_data(rd, revision, allowed_node_ids=scope)

    assert "t1" not in rd
    assert "a1" not in rd
    assert rd == {}


@pytest.mark.asyncio
async def test_run_flow_two_triggers_with_explicit_start_executes_that_branch_only() -> None:
    """Starting from ``t2`` must not traverse ``t1``'s downstream node."""

    nodes = [
        _manual_trig("t1", "One"),
        _manual_trig("t2", "Two"),
        _pass_next("a1", "A"),
        _pass_next("b1", "B"),
    ]
    connections = {
        "t1": {"main": [[ad.flows.NodeConnection(dest_node_id="a1", connection_type="main", index=0)]]},
        "t2": {"main": [[ad.flows.NodeConnection(dest_node_id="b1", connection_type="main", index=0)]]},
    }
    rev = {"nodes": nodes, "connections": connections, "settings": {}, "pin_data": None}
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
    res = await ad.flows.run_flow(context=ctx, revision=rev, start_trigger_node_id="t2")
    assert res["status"] == "success"
    assert "b1" in ctx.run_data
    assert "a1" not in ctx.run_data


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
                "python_code": "def run(items, context):\n    out=[]\n    td = context.get('trigger') or {}\n    for it in items:\n        row = dict(it['json'])\n        row['x']=td.get('x',0)+1\n        out.append(row)\n    return out\n",
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
async def test_run_flow_code_emits_multiple_items_and_branch_maps_string_equals() -> None:
    """Code returns two dicts while branch `equals` is a UI string (`"1"`) matching numeric `code` (1)."""

    python_code = (
        "def run(items, context):\n"
        "    return [\n"
        '        {\"name\": \"First item\", \"code\": 1},\n'
        '        {\"name\": \"Second item\", \"code\": 2},\n'
        "    ]\n"
    )

    nodes = [
        {"id": "t1", "name": "Start", "type": "flows.trigger.manual", "position": [0, 0], "parameters": {}, "webhook_id": None, "disabled": False, "on_error": "stop", "retry_on_fail": False, "max_tries": 1, "wait_between_tries_ms": 1000, "notes": None},
        {
            "id": "c1",
            "name": "Code",
            "type": "flows.code",
            "position": [100, 0],
            "parameters": {"python_code": python_code, "timeout_seconds": 2},
            "webhook_id": None,
            "disabled": False,
            "on_error": "stop",
            "retry_on_fail": False,
            "max_tries": 1,
            "wait_between_tries_ms": 1000,
            "notes": None,
        },
        {
            "id": "b1",
            "name": "Branch",
            "type": "flows.branch",
            "position": [200, 0],
            "parameters": {"field": "code", "equals": "1"},
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
        "t1": {"main": [[ad.flows.NodeConnection(dest_node_id="c1", connection_type="main", index=0)]]},
        "c1": {"main": [[ad.flows.NodeConnection(dest_node_id="b1", connection_type="main", index=0)]]},
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
    res = await ad.flows.run_flow(context=ctx, revision={"nodes": nodes, "connections": connections, "settings": {}, "pin_data": None})
    assert res["status"] == "success"
    code_out = ctx.run_data["c1"]["data"]["main"][0]
    assert len(code_out) == 2
    br = ctx.run_data["b1"]["data"]["main"]
    assert [len(br[0]), len(br[1])] == [1, 1]
    assert br[0][0].json["name"] == "First item"
    assert br[1][0].json["name"] == "Second item"


@pytest.mark.asyncio
async def test_run_flow_code_batches_all_upstream_items_in_one_execute() -> None:
    """`flows.code` must see every upstream item list in one `run()` call — not invoke once per item."""

    emit_code = "def run(items, context):\n    return [{'i': 0}, {'i': 1}]\n"
    python_code = (
        "def run(items, context):\n"
        "    assert len(items) == 2, len(items)\n"
        '    return [{\"tag\": \"a\"}, {\"tag\": \"b\"}]\n'
    )
    nodes = [
        {"id": "t1", "name": "Start", "type": "flows.trigger.manual", "position": [0, 0], "parameters": {}, "webhook_id": None, "disabled": False, "on_error": "stop", "retry_on_fail": False, "max_tries": 1, "wait_between_tries_ms": 1000, "notes": None},
        {
            "id": "e1",
            "name": "Emit",
            "type": "flows.code",
            "position": [80, 0],
            "parameters": {"python_code": emit_code, "timeout_seconds": 2},
            "webhook_id": None,
            "disabled": False,
            "on_error": "stop",
            "retry_on_fail": False,
            "max_tries": 1,
            "wait_between_tries_ms": 1000,
            "notes": None,
        },
        {
            "id": "c1",
            "name": "Code",
            "type": "flows.code",
            "position": [100, 0],
            "parameters": {"python_code": python_code, "timeout_seconds": 2},
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
        "t1": {"main": [[ad.flows.NodeConnection(dest_node_id="e1", connection_type="main", index=0)]]},
        "e1": {"main": [[ad.flows.NodeConnection(dest_node_id="c1", connection_type="main", index=0)]]},
    }
    ctx = ad.flows.ExecutionContext(
        organization_id="org",
        execution_id="exec",
        flow_id="flow",
        flow_revid="rev",
        mode="manual",
        trigger_data={"type": "manual"},
        run_data={},
        analytiq_client=None,
        stop_requested=False,
        logger=None,
    )
    res = await ad.flows.run_flow(context=ctx, revision={"nodes": nodes, "connections": connections, "settings": {}, "pin_data": None})
    assert res["status"] == "success"
    out_items = ctx.run_data["c1"]["data"]["main"][0]
    assert len(out_items) == 2


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
    m1_source = ctx.run_data["m1"]["source"]
    assert m1_source[0][0]["previous_node_id"] == "g1"
    assert m1_source[1][0]["previous_node_id"] == "g2"


@pytest.mark.asyncio
async def test_merge_waits_for_all_wired_optional_ports() -> None:
    """
    Parallel branches into merge slots 0 and 1: the merge must not run until the slow branch
    (slot 1) arrives — mirrors ``docrouter.llm_run`` main + optional OCR wiring.
    """

    nodes = [
        _n("t1", "Start", "flows.trigger.manual", 0),
        _n("m1", "Merge", "tests.optional_merge_record", 400, {}),
        _n("s1", "Slow", "tests.slow_pass", 200, {"marker": "slow", "delay_ms": 50}),
    ]
    connections = {
        "t1": {
            "main": [
                [
                    ad.flows.NodeConnection(dest_node_id="m1", connection_type="main", index=0),
                    ad.flows.NodeConnection(dest_node_id="s1", connection_type="main", index=0),
                ],
            ]
        },
        "s1": {
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
    out = ctx.run_data["m1"]["data"]["main"][0][0].json
    assert out["slot0_count"] == 1
    assert out["slot1_count"] == 1
    assert out["slot1_markers"] == ["slow"]
    m1_source = ctx.run_data["m1"]["source"]
    assert m1_source[0][0]["previous_node_id"] == "t1"
    assert m1_source[1][0]["previous_node_id"] == "s1"


@pytest.mark.asyncio
async def test_merge_optional_unwired_second_port_runs_after_first() -> None:
    """When only input slot 0 is wired, merge runs as soon as slot 0 is ready."""

    nodes = [
        _n("t1", "Start", "flows.trigger.manual", 0),
        _n("m1", "Merge", "tests.optional_merge_record", 200, {}),
    ]
    connections = {
        "t1": {
            "main": [[ad.flows.NodeConnection(dest_node_id="m1", connection_type="main", index=0)]],
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
    out = ctx.run_data["m1"]["data"]["main"][0][0].json
    assert out["slot0_count"] == 1
    assert out["slot1_count"] == 0


@pytest.mark.asyncio
async def test_run_flow_records_source_on_downstream_node() -> None:
    nodes = [
        _n("t1", "Start", "flows.trigger.manual", 0),
        _n("p1", "Pass", "tests.passthrough", 200),
    ]
    connections = {
        "t1": {"main": [[ad.flows.NodeConnection(dest_node_id="p1", connection_type="main", index=0)]]},
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
    )
    res = await ad.flows.run_flow(
        context=ctx, revision={"nodes": nodes, "connections": connections, "settings": {}, "pin_data": None}
    )
    assert res["status"] == "success"
    assert ctx.run_data["t1"]["source"] == []
    assert ctx.run_data["p1"]["source"] == [
        [{"previous_node_id": "t1", "previous_node_output": 0, "previous_node_run": 0}]
    ]
    p1_item = ctx.run_data["p1"]["data"]["main"][0][0]
    assert p1_item.meta["source_node_id"] == "p1"


@pytest.mark.asyncio
async def test_run_flow_branch_true_and_false_outputs_by_json_field() -> None:
    """
    Branch must route items explicitly to `main[0]` (true) vs `main[1]` (false),
    not only by implicit wiring. Manual trigger emits `{}`; pin_data supplies `k` for the branch.
    """

    async def _run(equals_val: Any) -> dict[str, Any]:
        nodes = [
            _n("t1", "Start", "flows.trigger.manual", 0),
            _n("b1", "Branch", "flows.branch", 200, {"field": "k", "equals": equals_val}),
        ]
        connections = {
            "t1": {
                "main": [[ad.flows.NodeConnection(dest_node_id="b1", connection_type="main", index=0)]],
            }
        }
        pin_data = {"t1": [{"json": {"k": 1}, "binary": {}, "meta": {}, "paired_item": None}]}
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
            revision={
                "nodes": nodes,
                "connections": connections,
                "settings": {},
                "pin_data": pin_data,
            },
        )
        assert res["status"] == "success"
        return ctx.run_data

    data_true = await _run(1)
    b_true = data_true["b1"]["data"]["main"]
    assert [len(b_true[0]), len(b_true[1])] == [1, 0]

    data_false = await _run(0)
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
async def test_run_flow_event_mode_ignores_pin_data() -> None:
    """Production/event runs must execute nodes even when the revision has pin_data."""

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
            {"json": {"hello": "pinned"}, "binary": {}, "meta": {}, "paired_item": None},
        ]
    }
    ctx = ad.flows.ExecutionContext(
        organization_id="org",
        execution_id="exec",
        flow_id="flow",
        flow_revid="rev",
        mode="event",
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

    passthrough_out = ctx.run_data["p1"]["data"]["main"][0]
    assert passthrough_out[0].json == {}
    assert "hello" not in passthrough_out[0].json

    tagged = ctx.run_data["g1"]["data"]["main"][0]
    assert tagged[0].json["path_tag"] == "ok"


def test_pin_data_enabled_for_mode_manual_only() -> None:
    assert ad.flows.pin_data_enabled_for_mode("manual") is True
    for mode in ("event", "webhook", "trigger", "schedule", "error"):
        assert ad.flows.pin_data_enabled_for_mode(mode) is False


@pytest.mark.asyncio
async def test_run_flow_pin_data_accepts_sdk_main_lane_shape() -> None:
    """API / frontend store pins as `{ "main": [[ {json,...}, ... ]] }`; engine lane-0 must match list shape."""

    nodes = [
        _n("t1", "Start", "flows.trigger.manual", 0),
        _n("p1", "Pinned", "tests.passthrough", 200),
        _n("g1", "Tag", "tests.tag", 400, {"tag": "ok"}),
    ]
    connections = {
        "t1": {"main": [[ad.flows.NodeConnection(dest_node_id="p1", connection_type="main", index=0)]]},
        "p1": {"main": [[ad.flows.NodeConnection(dest_node_id="g1", connection_type="main", index=0)]]},
    }
    pin_data = {"p1": {"main": [[{"json": {"hello": "from_pin"}, "binary": {}, "meta": {}, "paired_item": None}]]}}
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
    assert ctx.run_data["p1"]["data"]["main"][0][0].json["hello"] == "from_pin"
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
async def test_persist_run_data_offloads_binaryref_data_and_persists_storage_id(monkeypatch) -> None:
    """
    When persisting run_data with a Mongo-backed client, inline BinaryRef.data must be:
    - uploaded once to GridFS flow_blobs
    - cleared from memory
    - persisted as storage_id only (no bytes in MongoDB payload)
    """

    saved: dict[str, Any] = {}

    async def _fake_save_blob_async(_client, *, bucket: str, key: str, blob: bytes, metadata: dict[str, Any], **_kw):
        saved["bucket"] = bucket
        saved["key"] = key
        saved["blob"] = blob
        saved["metadata"] = metadata

    class _FakeFlowExecutions:
        async def update_one(self, _filter, update):
            saved["update"] = update

    class _FakeDb:
        flow_executions = _FakeFlowExecutions()

    def _fake_get_async_db(_client=None):
        return _FakeDb()

    monkeypatch.setattr(ad.mongodb.blob, "save_blob_async", _fake_save_blob_async)
    monkeypatch.setattr(ad.common, "get_async_db", _fake_get_async_db)

    ref = ad.flows.BinaryRef(mime_type="text/plain", file_name="x.txt", data=b"abc")
    item = ad.flows.FlowItem(json={"k": 1}, binary={"f": ref}, meta={}, paired_item=None)
    run_data = {
        "n1": {
            "status": "success",
            "start_time": "2020-01-01T00:00:00Z",
            "execution_time_ms": 1,
            "data": {"main": [[item]]},
            "error": None,
        }
    }

    exec_id = "64f3a1b2c3d4e5f6a7b8c9d0"
    ctx = ad.flows.ExecutionContext(
        organization_id="org",
        execution_id=exec_id,
        flow_id="flow",
        flow_revid="rev",
        mode="manual",
        trigger_data={},
        run_data=run_data,
        analytiq_client=object(),
        stop_requested=False,
        logger=None,
    )

    await ad.flows.persist_run_data(ctx, run_data)

    # Offload happened.
    assert saved["bucket"] == "flow_blobs"
    assert saved["key"] == f"{exec_id}/n1/0/f"
    assert saved["blob"] == b"abc"
    assert saved["metadata"]["mime_type"] == "text/plain"
    assert saved["metadata"]["file_name"] == "x.txt"

    # In-memory ref mutated: data cleared, storage_id set.
    assert ref.data is None
    assert ref.storage_id == f"flow_blobs:{exec_id}/n1/0/f"

    # Persisted payload contains only storage_id metadata (no inline bytes).
    stored_item = saved["update"]["$set"]["run_data"]["n1"]["data"]["main"][0][0]
    assert stored_item["binary"]["f"]["storage_id"] == f"flow_blobs:{exec_id}/n1/0/f"
    assert "data" not in stored_item["binary"]["f"]


@pytest.mark.asyncio
async def test_save_execution_binary_blob_writes_flow_blobs(monkeypatch) -> None:
    saved: dict[str, Any] = {}

    async def _fake_save_blob_async(_client, *, bucket: str, key: str, blob: bytes, metadata: dict[str, Any], **_kw):
        saved["bucket"] = bucket
        saved["key"] = key
        saved["blob"] = blob
        saved["metadata"] = metadata

    monkeypatch.setattr(ad.mongodb.blob, "save_blob_async", _fake_save_blob_async)

    ref = await ad.flows.save_execution_binary_blob(
        object(),
        execution_id="exec1",
        node_id="ocr1",
        item_index=0,
        property_name="ocr_json",
        blob=b'{"pages":[]}',
        mime_type="application/json",
        file_name="ocr.json",
    )

    assert ref.storage_id == "flow_blobs:exec1/ocr1/0/ocr_json"
    assert ref.data is None
    assert saved["bucket"] == "flow_blobs"
    assert saved["key"] == "exec1/ocr1/0/ocr_json"


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
                    "    a = context['nodes']['p1']['main'][0][0]['json']['a']\n"
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


@pytest.mark.asyncio
async def test_manual_trigger_emits_single_empty_json_item() -> None:
    """`flows.trigger.manual` emits one row with empty JSON (n8n Manual Trigger behavior)."""

    n = ad.flows.FlowsManualTriggerNode()
    ctx = ad.flows.ExecutionContext(
        organization_id="o1",
        execution_id="e1",
        flow_id="f1",
        flow_revid="r1",
        mode="manual",
        trigger_data={"type": "manual", "document_id": "d1"},
        run_data={},
        analytiq_client=None,
        stop_requested=False,
        logger=None,
    )
    out = await n.execute(ctx, {"id": "t1", "parameters": {}}, [[]])
    assert len(out) == 1 and len(out[0]) == 1
    assert out[0][0].json == {}
    assert out[0][0].meta["item_index"] == 0


@pytest.mark.asyncio
async def test_manual_trigger_legacy_stored_payload_is_ignored() -> None:
    """Old revisions may still store `payload` on the manual trigger node; execution ignores it."""

    n = ad.flows.FlowsManualTriggerNode()
    ctx = ad.flows.ExecutionContext(
        organization_id="o1",
        execution_id="e1",
        flow_id="f1",
        flow_revid="r1",
        mode="manual",
        trigger_data={"type": "manual"},
        run_data={},
        analytiq_client=None,
        stop_requested=False,
        logger=None,
    )
    out = await n.execute(
        ctx,
        {"id": "t1", "parameters": {"payload": [{"ignored": True}]}},
        [[]],
    )
    assert out[0][0].json == {}


def test_node_name_prefers_canvas_name() -> None:
    assert (
        ad.flows.node_name({"id": "6580d50a-7149-4fd9-b8c3-d19807eccc94", "name": "  My HTTP  ", "type": "tests.passthrough"})
        == "My HTTP"
    )


def test_node_name_falls_back_to_id_when_name_empty() -> None:
    nid = "6580d50a-7149-4fd9-b8c3-d19807eccc94"
    assert ad.flows.node_name({"id": nid, "name": "", "type": "tests.passthrough"}) == nid


@pytest.mark.asyncio
async def test_run_flow_stops_after_current_per_item_step(monkeypatch) -> None:
    """Cooperative stop should finish the current item, persist partial output, and not run downstream nodes."""

    completed_p1_items = 0
    original_pt_execute = _PassThroughNode.execute

    async def counting_execute(
        self,
        context: "ad.flows.ExecutionContext",
        node: dict[str, Any],
        inputs: list[list["ad.flows.FlowItem"]],
    ) -> list[list["ad.flows.FlowItem"]]:
        nonlocal completed_p1_items
        if node["id"] == "p1":
            completed_p1_items += 1
        return await original_pt_execute(self, context, node, inputs)

    monkeypatch.setattr(_PassThroughNode, "execute", counting_execute)

    async def fake_read_stop(_ctx: "ad.flows.ExecutionContext") -> bool:
        return completed_p1_items >= 2

    monkeypatch.setattr("analytiq_data.flows.engine.read_stop", fake_read_stop)

    emit_code = "def run(items, context):\n    return [{'i': i} for i in range(5)]\n"
    nodes = [
        _manual_trig("t1", "Start"),
        {
            "id": "c1",
            "name": "Code",
            "type": "flows.code",
            "position": [100, 0],
            "parameters": {"python_code": emit_code, "timeout_seconds": 2},
            "webhook_id": None,
            "disabled": False,
            "on_error": "stop",
            "retry_on_fail": False,
            "max_tries": 1,
            "wait_between_tries_ms": 1000,
            "notes": None,
        },
        _pass_next("p1", "Pass"),
        _pass_next("b1", "After"),
    ]
    connections = {
        "t1": {"main": [[ad.flows.NodeConnection(dest_node_id="c1", connection_type="main", index=0)]]},
        "c1": {"main": [[ad.flows.NodeConnection(dest_node_id="p1", connection_type="main", index=0)]]},
        "p1": {"main": [[ad.flows.NodeConnection(dest_node_id="b1", connection_type="main", index=0)]]},
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
        revision={"nodes": nodes, "connections": connections, "settings": {}, "pin_data": None},
    )
    assert res["status"] == "stopped"
    assert len(ctx.run_data["p1"]["data"]["main"][0]) == 2
    assert "b1" not in ctx.run_data


@pytest.mark.asyncio
async def test_run_flow_stops_between_nodes_after_batch_node(monkeypatch) -> None:
    """Post-node ``read_stop`` should stop after a batch node finishes, before downstream nodes run."""

    async def fake_read_stop(ctx: "ad.flows.ExecutionContext") -> bool:
        return "c1" in ctx.run_data

    monkeypatch.setattr("analytiq_data.flows.engine.read_stop", fake_read_stop)

    emit_code = "def run(items, context):\n    return [{'i': i} for i in range(3)]\n"
    nodes = [
        _manual_trig("t1", "Start"),
        {
            "id": "c1",
            "name": "Code",
            "type": "flows.code",
            "position": [100, 0],
            "parameters": {"python_code": emit_code, "timeout_seconds": 2},
            "webhook_id": None,
            "disabled": False,
            "on_error": "stop",
            "retry_on_fail": False,
            "max_tries": 1,
            "wait_between_tries_ms": 1000,
            "notes": None,
        },
        _pass_next("b1", "After"),
    ]
    connections = {
        "t1": {"main": [[ad.flows.NodeConnection(dest_node_id="c1", connection_type="main", index=0)]]},
        "c1": {"main": [[ad.flows.NodeConnection(dest_node_id="b1", connection_type="main", index=0)]]},
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
        revision={"nodes": nodes, "connections": connections, "settings": {}, "pin_data": None},
    )
    assert res["status"] == "stopped"
    assert len(ctx.run_data["c1"]["data"]["main"][0]) == 3
    assert "b1" not in ctx.run_data

