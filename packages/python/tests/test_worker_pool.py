import asyncio

import pytest

from analytiq_data.system.worker_counts import WorkerCounts
from worker.pool import WorkerPool


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
async def test_worker_pool_skips_noop_reconcile():
    pool = WorkerPool()
    counts = WorkerCounts(n_ocr_workers=1)
    await pool.reconcile(counts)
    ocr_tasks = dict(pool._queue_tasks["ocr"])
    await pool.reconcile(counts)
    assert pool._queue_tasks["ocr"] == ocr_tasks
    await pool.shutdown()
