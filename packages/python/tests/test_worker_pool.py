import asyncio

import pytest

from analytiq_data.system.worker_counts import WorkerCounts
from worker.pool import WorkerPool
from worker.slot import WorkerSlot
from worker import pool as pool_mod


@pytest.mark.asyncio
async def test_worker_pool_scales_up_and_down():
    pool = WorkerPool()

    await pool.reconcile(
        WorkerCounts(
            n_ocr_workers=2,
            n_llm_workers=1,
            n_kb_index_workers=0,
            n_webhook_workers=0,
            n_flow_run_workers=0,
        )
    )
    assert len(pool._queue_tasks["ocr"]) == 2
    assert len(pool._queue_tasks["llm"]) == 1
    assert len(pool._singleton_tasks) == 2

    await pool.reconcile(
        WorkerCounts(
            n_ocr_workers=1,
            n_llm_workers=0,
            n_kb_index_workers=0,
            n_webhook_workers=0,
            n_flow_run_workers=0,
        )
    )
    assert len(pool._queue_tasks["ocr"]) == 1
    assert len(pool._queue_tasks["llm"]) == 0

    await pool.shutdown()
    assert pool.current_counts.total_queue_workers() == 0


@pytest.mark.asyncio
async def test_worker_pool_stops_all_when_zero():
    pool = WorkerPool()
    await pool.reconcile(
        WorkerCounts(
            n_ocr_workers=1,
            n_llm_workers=0,
            n_kb_index_workers=0,
            n_webhook_workers=0,
            n_flow_run_workers=0,
        )
    )
    await pool.reconcile(
        WorkerCounts(
            n_ocr_workers=0,
            n_llm_workers=0,
            n_kb_index_workers=0,
            n_webhook_workers=0,
            n_flow_run_workers=0,
        )
    )
    assert pool._queue_tasks["ocr"] == {}
    assert pool._singleton_tasks == {}


@pytest.mark.asyncio
async def test_worker_pool_waits_for_busy_worker_before_removal(monkeypatch):
    release = asyncio.Event()
    started = asyncio.Event()

    async def fake_ocr(worker_id: str, slot: WorkerSlot | None = None) -> None:
        while True:
            if slot and slot.should_exit_before_poll():
                return
            if slot:
                slot.busy = True
            started.set()
            try:
                await release.wait()
            finally:
                if slot:
                    slot.busy = False
            if slot and slot.should_exit_before_poll():
                return

    monkeypatch.setitem(pool_mod.QUEUE_WORKER_FNS, "ocr", fake_ocr)

    pool = WorkerPool()
    await pool.reconcile(WorkerCounts(n_ocr_workers=1))
    await asyncio.wait_for(started.wait(), timeout=1.0)

    handle = pool._queue_tasks["ocr"][0]
    await pool.reconcile(WorkerCounts(n_ocr_workers=0))

    assert handle.slot.draining is True
    assert not handle.task.cancelled()
    assert 0 in pool._queue_tasks["ocr"]

    release.set()
    await asyncio.wait_for(handle.task, timeout=1.0)
    for _ in range(20):
        if pool._queue_tasks["ocr"] == {}:
            break
        await asyncio.sleep(0.01)
    assert pool._queue_tasks["ocr"] == {}


@pytest.mark.asyncio
async def test_worker_pool_skips_noop_reconcile():
    pool = WorkerPool()
    counts = WorkerCounts(n_ocr_workers=1)
    await pool.reconcile(counts)
    ocr_tasks = dict(pool._queue_tasks["ocr"])
    await pool.reconcile(counts)
    assert pool._queue_tasks["ocr"] == ocr_tasks
    await pool.shutdown()
