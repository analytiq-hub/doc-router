"""Tests for batch node partial progress persistence."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from unittest.mock import AsyncMock

import pytest

import analytiq_data as ad
from analytiq_data.docrouter_flows.nodes.ocr_node import DocRouterOcrNode
from analytiq_data.flows.batch_meta import batch_output_is_incomplete, merge_batch_meta_for_final_persist
from analytiq_data.flows.batch_progress import (
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
