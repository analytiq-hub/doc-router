"""Tests for batch node partial progress persistence."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from unittest.mock import AsyncMock

import pytest

import analytiq_data as ad
from analytiq_data.docrouter_flows.nodes.ocr_node import DocRouterOcrNode
from analytiq_data.flows.batch_meta import (
    batch_output_is_incomplete,
    merge_batch_meta_for_final_persist,
    partial_main_from_entry,
)
from analytiq_data.flows.batch_progress import (
    continue_on_item_error_for_node,
    make_batch_checkpoint_callback,
    persist_batch_node_partial,
)
from analytiq_data.flows.node_settings import node_uses_batch_partial_persist


@dataclass
class _FakeContext:
    execution_id: str = "exec-1"
    execution_index: int = 3
    run_data: dict[str, Any] = field(default_factory=dict)
    analytiq_client: Any = None


@pytest.mark.asyncio
async def test_persist_batch_node_partial_writes_full_items(monkeypatch: pytest.MonkeyPatch) -> None:
    ctx = _FakeContext(analytiq_client=object())
    persist_mock = AsyncMock()
    monkeypatch.setattr("analytiq_data.flows.batch_progress.persist_run_data", persist_mock)

    items = [
        ad.flows.FlowItem(json={"i": 0}, binary={}, meta={"item_index": 0}),
        None,
        ad.flows.FlowItem(json={"i": 2}, binary={}, meta={"item_index": 2}),
    ]
    await persist_batch_node_partial(ctx, "ocr-1", items_total=5, results=items)

    entry = ctx.run_data["ocr-1"]
    assert entry["status"] == "running"
    assert entry["items_total"] == 5
    assert entry["items_completed"] == 2
    assert len(entry["data"]["main"][0]) == 2
    assert entry["data"]["main"][0][0].json["i"] == 0
    persist_mock.assert_awaited_once()


def test_node_uses_batch_partial_persist_gate() -> None:
    ocr = DocRouterOcrNode()
    assert node_uses_batch_partial_persist({"batch_size": 32}, ocr) is True
    assert node_uses_batch_partial_persist({"batch_size": 1}, ocr) is False
    assert node_uses_batch_partial_persist({}, ocr) is False


def test_continue_on_item_error_for_node_respects_on_error_setting() -> None:
    assert continue_on_item_error_for_node({"type": "docrouter.ocr", "on_error": "continue"}) is True
    assert continue_on_item_error_for_node({"type": "docrouter.llm_run", "on_error": "continue"}) is True
    assert continue_on_item_error_for_node({"type": "docrouter.ocr", "on_error": "stop"}) is False
    assert continue_on_item_error_for_node({"type": "docrouter.ocr"}) is False
    assert continue_on_item_error_for_node({"type": "tests.echo_param", "on_error": "continue"}) is False


@pytest.mark.asyncio
async def test_make_batch_checkpoint_callback_throttles(monkeypatch: pytest.MonkeyPatch) -> None:
    ctx = _FakeContext(analytiq_client=object())
    persist_mock = AsyncMock()
    monkeypatch.setattr("analytiq_data.flows.batch_progress.persist_run_data", persist_mock)

    node = {"id": "ocr-1", "batch_size": 4}
    cb = make_batch_checkpoint_callback(ctx, node, DocRouterOcrNode(), min_interval_secs=10.0)
    assert cb is not None

    results: list[int | None] = [1, 2, 3, 4]
    await cb(4, 4, results)
    await cb(4, 4, results)
    persist_mock.assert_awaited_once()


@pytest.mark.asyncio
async def test_make_batch_checkpoint_callback_none_for_sequential() -> None:
    ctx = _FakeContext()
    node = {"id": "ocr-1", "batch_size": 1}
    assert make_batch_checkpoint_callback(ctx, node, DocRouterOcrNode()) is None


def test_batch_output_is_incomplete_and_merge_meta() -> None:
    prior = {
        "items_total": 10,
        "items_completed": 6,
        "items_skipped_on_resume": 2,
    }
    out_lists = [[object()] * 5]
    assert batch_output_is_incomplete(prior, out_lists) is True
    meta = merge_batch_meta_for_final_persist(prior, out_lists)
    assert meta["items_total"] == 10
    assert meta["items_completed"] == 6
    assert meta["items_skipped_on_resume"] == 2

    assert batch_output_is_incomplete(prior, [[object()] * 10]) is False
    complete_meta = merge_batch_meta_for_final_persist(prior, [[object()] * 10])
    assert complete_meta["items_completed"] == 10


def test_partial_main_from_entry() -> None:
    assert partial_main_from_entry(None) is None
    assert partial_main_from_entry({"data": {"main": [[]]}}) is None
    lane = [ad.flows.FlowItem(json={"i": 0}, binary={}, meta={})]
    assert partial_main_from_entry({"data": {"main": [lane]}}) == [lane]


@pytest.mark.asyncio
async def test_on_error_continue_preserves_batch_partial_results() -> None:
    """Batch nodes must not discard checkpointed items when on_error=continue."""

    ad.flows.register_builtin_nodes()

    class _BatchPartialFailNode:
        key = "tests.batch_partial_fail"
        label = "Batch partial fail"
        description = "Test batch node that persists partial output then raises."
        category = "Test"
        is_trigger = False
        is_merge = False
        batch_execute_inputs = True
        supports_batch_size = True
        min_inputs = 1
        max_inputs = 1
        outputs = 1
        output_labels = ["main"]
        icon_key = None
        parameter_schema = {"type": "object", "properties": {}, "additionalProperties": False}

        def validate_parameters(self, params: dict) -> list[str]:
            return []

        async def execute(self, context: Any, node: dict[str, Any], inputs: list[list[Any]]) -> list[list[Any]]:
            completed = [
                ad.flows.FlowItem(json={"i": i}, binary={}, meta={"item_index": i})
                for i in range(60)
            ]
            results: list[Any | None] = list(completed) + [None] * 40
            await persist_batch_node_partial(
                context,
                node["id"],
                items_total=100,
                results=results,
                status="error",
                items_failed=1,
            )
            raise RuntimeError("item 41 failed")

    ad.flows.register(_BatchPartialFailNode())

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
            "id": "b1",
            "name": "Batch",
            "type": "tests.batch_partial_fail",
            "position": [200, 0],
            "parameters": {},
            "disabled": False,
            "on_error": "continue",
            "batch_size": 4,
        },
    ]
    connections = {
        "t1": {"main": [[ad.flows.NodeConnection(dest_node_id="b1", connection_type="main", index=0)]]},
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
    assert res["status"] == "success"

    entry = ctx.run_data["b1"]
    assert entry["status"] == "error"
    assert entry["items_total"] == 100
    assert entry["items_completed"] == 60
    lane = entry["data"]["main"][0]
    assert len(lane) == 60
    assert lane[0].json["i"] == 0
    assert lane[59].json["i"] == 59
    assert "_error" not in lane[0].json
