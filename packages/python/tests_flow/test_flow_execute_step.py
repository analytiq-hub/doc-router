from __future__ import annotations

"""Partial / execute-step engine coverage (upstream closure, stop-after-target, seed reuse)."""

from typing import Any

import pytest

import analytiq_data as ad
from analytiq_data.flows.engine import _bson_serialize_run_data


@pytest.fixture(autouse=True)
def _register_flow_nodes() -> None:
    ad.flows.register_builtin_nodes()
    from tests_flow.test_flows_engine import (  # noqa: PLC0415 — test-only registry side effect
        _PassThroughNode,
    )

    ad.flows.register(_PassThroughNode())


def _conn(dest: str, index: int = 0) -> ad.flows.NodeConnection:
    return ad.flows.NodeConnection(dest_node_id=dest, connection_type="main", index=index)


def _trigger(nid: str = "t1") -> dict[str, Any]:
    return {
        "id": nid,
        "name": "T",
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


def _pass(nid: str, name: str) -> dict[str, Any]:
    return {
        "id": nid,
        "name": name,
        "type": "tests.passthrough",
        "position": [100, 0],
        "parameters": {},
        "webhook_id": None,
        "disabled": False,
        "on_error": "stop",
        "retry_on_fail": False,
        "max_tries": 1,
        "wait_between_tries_ms": 1000,
        "notes": None,
    }


def _code(nid: str, code: str) -> dict[str, Any]:
    return {
        "id": nid,
        "name": nid,
        "type": "flows.code",
        "position": [200, 0],
        "parameters": {"python_code": code, "timeout_seconds": 5},
        "webhook_id": None,
        "disabled": False,
        "on_error": "stop",
        "retry_on_fail": False,
        "max_tries": 1,
        "wait_between_tries_ms": 1000,
        "notes": None,
    }


def _merge(nid: str) -> dict[str, Any]:
    return {
        "id": nid,
        "name": nid,
        "type": "flows.merge",
        "position": [300, 0],
        "parameters": {},
        "webhook_id": None,
        "disabled": False,
        "on_error": "stop",
        "retry_on_fail": False,
        "max_tries": 1,
        "wait_between_tries_ms": 1000,
        "notes": None,
    }


def _ctx() -> ad.flows.ExecutionContext:
    return ad.flows.ExecutionContext(
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


def _seed_slice(run_data: dict[str, Any], *node_ids: str) -> dict[str, Any]:
    return _bson_serialize_run_data({k: run_data[k] for k in node_ids if k in run_data})


def test_apply_revision_pins_overwrites_stale_execute_step_seed_merge() -> None:
    """Pinned merge lane must replace seeded run_data produced by a prior execution (UI First item vs First item1)."""

    merge_id = "m1"
    run_data = {
        merge_id: {
            "status": "success",
            "start_time": "2026-05-01T00:00:00+00:00",
            "execution_time_ms": 12,
            "data": {
                "main": [
                    [
                        {
                            "json": {"name": "First item"},
                            "binary": {},
                            "meta": {},
                            "paired_item": None,
                        }
                    ]
                ]
            },
            "error": None,
        }
    }
    revision = {
        "nodes": [
            _trigger(),
            _pass("a1", "A"),
            _pass("b1", "B"),
            _merge(merge_id),
            _pass("c1", "C"),
        ],
        "connections": {
            "t1": {"main": [[_conn("a1"), _conn("b1")]]},
            "a1": {"main": [[_conn("m1", 0)]]},
            "b1": {"main": [[_conn("m1", 1)]]},
            "m1": {"main": [[_conn("c1")]]},
        },
        "pin_data": {
            merge_id: {
                "main": [[{"json": {"name": "First item1"}, "binary": {}, "meta": {}, "paired_item": None}]],
            },
        },
    }
    touched = ad.flows.apply_revision_pins_to_run_data(run_data, revision, allowed_node_ids=None)
    assert merge_id in touched
    lane0_json = run_data[merge_id]["data"]["main"][0][0]["json"]
    assert lane0_json["name"] == "First item1"


def test_apply_revision_pins_allowed_filter_skips_out_of_scope_node() -> None:
    merge_id = "m1"
    stale = {"name": "First item"}
    run_data = {
        merge_id: {
            "status": "success",
            "start_time": "2026-05-01T00:00:00+00:00",
            "execution_time_ms": 12,
            "data": {"main": [[{"json": stale, "binary": {}, "meta": {}, "paired_item": None}]]},
            "error": None,
        }
    }
    revision = {
        "nodes": [_trigger(), _pass("a1", "A"), _pass("b1", "B"), _merge(merge_id)],
        "connections": {
            "t1": {"main": [[_conn("a1"), _conn("b1")]]},
            "a1": {"main": [[_conn("m1", 0)]]},
            "b1": {"main": [[_conn("m1", 1)]]},
        },
        "pin_data": {
            merge_id: {
                "main": [[{"json": {"name": "First item1"}, "binary": {}, "meta": {}, "paired_item": None}]],
            },
        },
    }
    touched = ad.flows.apply_revision_pins_to_run_data(run_data, revision, allowed_node_ids=frozenset({"t1"}))
    assert not touched
    assert run_data[merge_id]["data"]["main"][0][0]["json"]["name"] == "First item"


def test_pin_overlay_invalidation_drops_downstream_seed_for_execute_step() -> None:
    """Changing a pin upstream must not leave a reusable seed for the target Code node."""

    u1, c1 = "u1", "c1"
    run_data = {
        u1: {
            "status": "success",
            "data": {"main": [[{"json": {"stale": True}, "binary": {}, "meta": {}, "paired_item": None}]]},
            "error": None,
        },
        c1: {
            "status": "success",
            "data": {"main": [[{"json": {"code_out": "old"}, "binary": {}, "meta": {}, "paired_item": None}]]},
            "error": None,
        },
    }
    revision = {
        "nodes": [_trigger(), _pass(u1, "U"), _code(c1, "def run(items, context):\n    return [dict(x) for x in items]\n")],
        "connections": {
            "t1": {"main": [[_conn(u1)]]},
            u1: {"main": [[_conn(c1)]]},
        },
        "pin_data": {
            u1: {
                "main": [
                    [
                        {
                            "json": {"from_pin": True},
                            "binary": {},
                            "meta": {},
                            "paired_item": None,
                        }
                    ]
                ],
            },
        },
    }
    conns = ad.flows.coerce_json_connections_to_dataclasses(revision["connections"])
    closure = frozenset(
        ad.flows.upstream_closure_for_target("t1", c1, conns),
    )
    touched = ad.flows.apply_revision_pins_to_run_data(run_data, revision, allowed_node_ids=closure)
    assert u1 in touched
    ad.flows.invalidate_run_data_downstream_of_pins(run_data, conns, touched, limit_nodes=closure)
    assert u1 in run_data
    assert run_data[u1]["data"]["main"][0][0]["json"].get("from_pin") is True
    assert c1 not in run_data


@pytest.mark.asyncio
async def test_execute_step_reuses_seed_upstream() -> None:
    """(a) Seed has B; B not re-executed; C runs using B output."""
    nodes = [_trigger(), _pass("b1", "B"), _pass("c1", "C")]
    connections = {
        "t1": {"main": [[_conn("b1")]]},
        "b1": {"main": [[_conn("c1")]]},
    }
    rev = {"nodes": nodes, "connections": connections, "settings": {}, "pin_data": None}

    full = _ctx()
    await ad.flows.run_flow(context=full, revision=rev)
    assert "b1" in full.run_data and "c1" in full.run_data

    step = _ctx()
    seed = _seed_slice(full.run_data, "t1", "b1")
    step.run_data.update(seed)
    await ad.flows.run_flow(context=step, revision=rev, target_node_id="c1")
    assert "c1" in step.run_data
    assert step.run_data["c1"]["status"] == "success"


@pytest.mark.asyncio
async def test_execute_step_runs_missing_upstream() -> None:
    """(b) No seed — A then B then C for target C."""
    nodes = [_trigger(), _pass("b1", "B"), _pass("c1", "C")]
    connections = {"t1": {"main": [[_conn("b1")]]}, "b1": {"main": [[_conn("c1")]]}}
    rev = {"nodes": nodes, "connections": connections, "settings": {}, "pin_data": None}
    ctx = _ctx()
    await ad.flows.run_flow(context=ctx, revision=rev, target_node_id="c1")
    assert set(ctx.run_data.keys()) == {"t1", "b1", "c1"}


@pytest.mark.asyncio
async def test_execute_step_stops_after_target() -> None:
    """(c) Chain A→B→C→D, target B — only t1 and b1."""
    nodes = [_trigger(), _pass("b1", "B"), _pass("c1", "C"), _pass("d1", "D")]
    connections = {
        "t1": {"main": [[_conn("b1")]]},
        "b1": {"main": [[_conn("c1")]]},
        "c1": {"main": [[_conn("d1")]]},
    }
    rev = {"nodes": nodes, "connections": connections, "settings": {}, "pin_data": None}
    ctx = _ctx()
    await ad.flows.run_flow(context=ctx, revision=rev, target_node_id="b1")
    assert set(ctx.run_data.keys()) == {"t1", "b1"}


@pytest.mark.asyncio
async def test_execute_step_diamond_partial_seed() -> None:
    """(d) A→B→D, A→C→D; seed B; A and C run; B reused; D runs."""
    nodes = [_trigger(), _pass("b1", "B"), _pass("c1", "C"), _merge("d1")]
    connections = {
        "t1": {"main": [[_conn("b1"), _conn("c1")]]},
        "b1": {"main": [[_conn("d1", index=0)]]},
        "c1": {"main": [[_conn("d1", index=1)]]},
    }
    rev = {"nodes": nodes, "connections": connections, "settings": {}, "pin_data": None}

    full = _ctx()
    await ad.flows.run_flow(context=full, revision=rev)
    seed = _seed_slice(full.run_data, "t1", "b1")

    step = _ctx()
    step.run_data.update(seed)
    await ad.flows.run_flow(context=step, revision=rev, target_node_id="d1")
    assert "d1" in step.run_data
    assert "c1" in step.run_data
    assert step.run_data["d1"]["status"] == "success"


@pytest.mark.asyncio
async def test_execute_step_merge_missing_branch_seed() -> None:
    """(e) Same diamond; seed only B — C runs; D completes after merge."""
    nodes = [_trigger(), _pass("b1", "B"), _pass("c1", "C"), _merge("d1")]
    connections = {
        "t1": {"main": [[_conn("b1"), _conn("c1")]]},
        "b1": {"main": [[_conn("d1", index=0)]]},
        "c1": {"main": [[_conn("d1", index=1)]]},
    }
    rev = {"nodes": nodes, "connections": connections, "settings": {}, "pin_data": None}

    full = _ctx()
    await ad.flows.run_flow(context=full, revision=rev)
    seed = _seed_slice(full.run_data, "t1", "b1")

    step = _ctx()
    step.run_data.update(seed)
    await ad.flows.run_flow(context=step, revision=rev, target_node_id="d1")
    assert "c1" in step.run_data and "d1" in step.run_data


@pytest.mark.asyncio
async def test_execute_step_precursor_error_skips_target() -> None:
    """(f) B raises; C absent; execution propagates error."""
    code_fail = "def run(items, context):\n    raise RuntimeError('fail')\n"
    nodes = [_trigger(), _code("b1", code_fail), _pass("c1", "C")]
    connections = {"t1": {"main": [[_conn("b1")]]}, "b1": {"main": [[_conn("c1")]]}}
    rev = {"nodes": nodes, "connections": connections, "settings": {}, "pin_data": None}
    ctx = _ctx()
    with pytest.raises(RuntimeError):
        await ad.flows.run_flow(context=ctx, revision=rev, target_node_id="c1")
    assert "b1" in ctx.run_data
    assert ctx.run_data["b1"]["status"] == "error"
    assert "c1" not in ctx.run_data


@pytest.mark.asyncio
async def test_execute_step_dirty_forces_rerun() -> None:
    """Dirty flag ignores seed so B re-executes."""
    nodes = [_trigger(), _pass("b1", "B"), _pass("c1", "C")]
    connections = {"t1": {"main": [[_conn("b1")]]}, "b1": {"main": [[_conn("c1")]]}}
    rev = {"nodes": nodes, "connections": connections, "settings": {}, "pin_data": None}

    full = _ctx()
    await ad.flows.run_flow(context=full, revision=rev)
    seed = _seed_slice(full.run_data, "t1", "b1")
    b1_start_before = full.run_data["b1"]["start_time"]

    step = _ctx()
    step.run_data.update(seed)
    await ad.flows.run_flow(
        context=step,
        revision=rev,
        target_node_id="c1",
        dirty_node_ids=frozenset({"b1"}),
    )
    assert step.run_data["c1"]["status"] == "success"
    assert step.run_data["b1"]["start_time"] != b1_start_before
