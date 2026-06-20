"""Tests for bounded item parallelism in flow nodes."""

from __future__ import annotations

import asyncio

import pytest

from analytiq_data.flows.item_parallel import map_flow_items_bounded
from analytiq_data.flows.node_settings import (
    FLOW_NODE_BATCH_SIZE_DEFAULT,
    FLOW_NODE_BATCH_SIZE_MAX,
    FLOW_NODE_BATCH_SIZE_MIN,
    resolve_node_batch_size,
    validate_node_batch_size,
)


@pytest.mark.asyncio
async def test_map_flow_items_bounded_preserves_order() -> None:
    async def fn(i: int) -> int:
        await asyncio.sleep(0.01 * (3 - i))
        return i

    results = await map_flow_items_bounded(4, fn)
    assert results == [0, 1, 2, 3]


@pytest.mark.asyncio
async def test_map_flow_items_bounded_caps_concurrency() -> None:
    active = 0
    max_active = 0
    lock = asyncio.Lock()

    async def fn(_i: int) -> int:
        nonlocal active, max_active
        async with lock:
            active += 1
            max_active = max(max_active, active)
        await asyncio.sleep(0.02)
        async with lock:
            active -= 1
        return 1

    await map_flow_items_bounded(12, fn, batch_size=8)
    assert max_active <= 8
    assert max_active >= 2


def test_resolve_node_batch_size_defaults_and_clamps() -> None:
    assert resolve_node_batch_size({}) == FLOW_NODE_BATCH_SIZE_DEFAULT
    assert resolve_node_batch_size({"batch_size": 3}) == 3
    assert resolve_node_batch_size({"batch_size": 0}) == FLOW_NODE_BATCH_SIZE_MIN
    assert resolve_node_batch_size({"batch_size": 999}) == FLOW_NODE_BATCH_SIZE_MAX
    assert resolve_node_batch_size({"batch_size": "bad"}) == FLOW_NODE_BATCH_SIZE_DEFAULT
    assert resolve_node_batch_size({"item_concurrency": 5}) == 5


def test_validate_node_batch_size() -> None:
    assert validate_node_batch_size({}) == []
    assert validate_node_batch_size({"batch_size": 4}) == []
    assert validate_node_batch_size({"batch_size": "x"}) == ["batch_size must be an integer"]
    assert validate_node_batch_size({"batch_size": 0})[0].startswith("batch_size must be between")
    assert validate_node_batch_size({"item_concurrency": 4}) == [
        "item_concurrency is deprecated; use batch_size instead"
    ]
