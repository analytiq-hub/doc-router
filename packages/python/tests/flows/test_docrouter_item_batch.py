"""Tests for batch item processing in flow nodes."""

from __future__ import annotations

import asyncio
import logging

import pytest

from analytiq_data.flows.item_batch import FlowBatchItemErrors, map_flow_items_batch
from analytiq_data.flows.node_settings import (
    FLOW_NODE_BATCH_SIZE_DEFAULT,
    FLOW_NODE_BATCH_SIZE_MAX,
    FLOW_NODE_BATCH_SIZE_MIN,
    resolve_node_batch_size,
    validate_node_batch_size,
)


@pytest.mark.asyncio
async def test_map_flow_items_batch_preserves_order() -> None:
    async def fn(i: int) -> int:
        await asyncio.sleep(0.01 * (3 - i))
        return i

    results = await map_flow_items_batch(4, fn)
    assert results == [0, 1, 2, 3]


@pytest.mark.asyncio
async def test_map_flow_items_batch_stops_after_current_item() -> None:
    completed = 0

    async def fn(i: int) -> int:
        nonlocal completed
        await asyncio.sleep(0.01)
        completed += 1
        return i

    async def should_stop() -> bool:
        return completed >= 2

    results = await map_flow_items_batch(5, fn, batch_size=1, should_stop=should_stop)
    assert results[:2] == [0, 1]
    assert results[2:] == [None, None, None]


@pytest.mark.asyncio
async def test_map_flow_items_batch_respects_batch_size() -> None:
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

    await map_flow_items_batch(12, fn, batch_size=8)
    assert max_active <= 8
    assert max_active >= 2


@pytest.mark.asyncio
async def test_map_flow_items_batch_logs_parallel_processing(caplog: pytest.LogCaptureFixture) -> None:
    async def fn(i: int) -> int:
        return i

    with caplog.at_level(logging.INFO):
        await map_flow_items_batch(
            5,
            fn,
            batch_size=3,
            execution_id="exec-1",
            node_id="node-1",
            node_type="docrouter.llm_run",
        )

    assert any(
        "Processing 5 items in parallel with batch_size=3" in r.message
        and "execution_id=exec-1" in r.message
        and "node_type=docrouter.llm_run" in r.message
        and "node_id=node-1" in r.message
        for r in caplog.records
    )


@pytest.mark.asyncio
async def test_map_flow_items_batch_skips_parallel_log_when_sequential(caplog: pytest.LogCaptureFixture) -> None:
    async def fn(i: int) -> int:
        return i

    with caplog.at_level(logging.INFO):
        await map_flow_items_batch(5, fn, batch_size=1)

    assert not any("in parallel" in r.message for r in caplog.records)


@pytest.mark.asyncio
async def test_map_flow_items_batch_invokes_checkpoint_on_wave_boundary() -> None:
    calls: list[tuple[int, int, list[int | None]]] = []

    async def fn(i: int) -> int:
        return i

    async def on_checkpoint(completed: int, total: int, results: list[int | None]) -> None:
        calls.append((completed, total, list(results)))

    await map_flow_items_batch(10, fn, batch_size=4, on_items_checkpoint=on_checkpoint)
    assert [c[0] for c in calls] == [4, 8, 10]


@pytest.mark.asyncio
async def test_map_flow_items_batch_checkpoint_on_cooperative_stop() -> None:
    completed = 0
    calls: list[int] = []

    async def fn(i: int) -> int:
        nonlocal completed
        completed += 1
        return i

    async def should_stop() -> bool:
        return completed >= 5

    async def on_checkpoint(done: int, _total: int, _results: list[int | None]) -> None:
        calls.append(done)

    await map_flow_items_batch(10, fn, batch_size=4, should_stop=should_stop, on_items_checkpoint=on_checkpoint)
    assert calls[-1] == 5
    assert 4 in calls


def test_resolve_node_batch_size_defaults_and_clamps() -> None:
    assert resolve_node_batch_size({}) == FLOW_NODE_BATCH_SIZE_DEFAULT
    assert resolve_node_batch_size({"batch_size": 3}) == 3
    assert resolve_node_batch_size({"batch_size": 0}) == FLOW_NODE_BATCH_SIZE_MIN
    assert resolve_node_batch_size({"batch_size": 999}) == FLOW_NODE_BATCH_SIZE_MAX
    assert resolve_node_batch_size({"batch_size": "bad"}) == FLOW_NODE_BATCH_SIZE_DEFAULT
    assert resolve_node_batch_size({"item_concurrency": 5}) == 5


@pytest.mark.asyncio
async def test_map_flow_items_batch_fatal_error_skips_late_checkpoints() -> None:
    checkpoint_calls: list[int] = []
    fatal_calls: list[int] = []

    async def fn(i: int) -> int:
        if i == 1:
            raise RuntimeError("fail")
        await asyncio.sleep(0.03)
        return i

    async def on_fatal(completed: int, _total: int, _results: list, _exc: BaseException) -> None:
        fatal_calls.append(completed)

    async def on_checkpoint(completed: int, _total: int, _results: list) -> None:
        checkpoint_calls.append(completed)

    with pytest.raises(RuntimeError, match="fail"):
        await map_flow_items_batch(
            4,
            fn,
            batch_size=2,
            continue_on_item_error=False,
            on_fatal_item_error=on_fatal,
            on_items_checkpoint=on_checkpoint,
        )

    assert fatal_calls == [1]
    assert checkpoint_calls == []


@pytest.mark.asyncio
async def test_map_flow_items_batch_stop_supersedes_item_errors_on_continue() -> None:
    """Cooperative stop must not be upgraded to a hard error when items also failed."""

    failed = False

    async def fn(i: int) -> int:
        nonlocal failed
        if i == 0:
            failed = True
            raise ValueError("boom")
        return i

    async def should_stop() -> bool:
        return failed

    with pytest.raises(FlowBatchItemErrors):
        await map_flow_items_batch(3, fn, batch_size=1, continue_on_item_error=True)

    results = await map_flow_items_batch(
        3,
        fn,
        batch_size=1,
        should_stop=should_stop,
        continue_on_item_error=True,
    )

    assert results == [None, None, None]


@pytest.mark.asyncio
async def test_map_flow_items_batch_checkpoint_error_stops_and_invokes_fatal() -> None:
    processed: list[int] = []
    fatal_calls: list[tuple[int, BaseException]] = []

    async def fn(i: int) -> int:
        processed.append(i)
        return i

    async def on_checkpoint(_completed: int, _total: int, _results: list) -> None:
        raise ConnectionError("mongo down")

    async def on_fatal(completed: int, _total: int, _results: list, exc: BaseException) -> None:
        fatal_calls.append((completed, exc))

    with pytest.raises(ConnectionError, match="mongo down"):
        await map_flow_items_batch(
            4,
            fn,
            batch_size=1,
            on_items_checkpoint=on_checkpoint,
            on_fatal_item_error=on_fatal,
        )

    assert processed == [0]
    assert len(fatal_calls) == 1
    assert fatal_calls[0][0] == 1
    assert isinstance(fatal_calls[0][1], ConnectionError)


@pytest.mark.asyncio
async def test_map_flow_items_batch_fatal_callback_fires_once_on_parallel_failures() -> None:
    fatal_calls: list[BaseException] = []
    barrier = asyncio.Event()
    started = 0
    lock = asyncio.Lock()

    async def fn(i: int) -> int:
        nonlocal started
        async with lock:
            started += 1
            if started == 2:
                barrier.set()
        await barrier.wait()
        if i == 0:
            raise RuntimeError("first")
        raise RuntimeError("second")

    async def on_fatal(_completed: int, _total: int, _results: list, exc: BaseException) -> None:
        fatal_calls.append(exc)

    with pytest.raises(RuntimeError):
        await map_flow_items_batch(
            4,
            fn,
            batch_size=2,
            continue_on_item_error=False,
            on_fatal_item_error=on_fatal,
        )

    assert len(fatal_calls) == 1
    assert str(fatal_calls[0]) in ("first", "second")


def test_validate_node_batch_size() -> None:
    assert validate_node_batch_size({}) == []
    assert validate_node_batch_size({"batch_size": 4}) == []
    assert validate_node_batch_size({"batch_size": "x"}) == ["batch_size must be an integer"]
    assert validate_node_batch_size({"batch_size": 0})[0].startswith("batch_size must be between")
    assert validate_node_batch_size({"item_concurrency": 4}) == [
        "item_concurrency is deprecated; use batch_size instead"
    ]
