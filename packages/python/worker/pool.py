"""Hot-resizable asyncio worker pool (per queue type)."""

from __future__ import annotations

import asyncio
import logging
import os
from collections.abc import Awaitable, Callable, Coroutine
from typing import Any

import analytiq_data as ad
from analytiq_data.system.worker_counts import FIELD_BY_QUEUE_TYPE, WorkerCounts

from worker.worker import (
    worker_flow_run,
    worker_kb_index,
    worker_llm,
    worker_kb_reconcile,
    worker_flow_cleanup,
    worker_ocr,
    worker_webhook,
)

logger = logging.getLogger(__name__)

WORKER_POOL_RECONCILE_INTERVAL_SECS = float(
    os.getenv("WORKER_POOL_RECONCILE_INTERVAL_SECS", "15")
)

QueueWorkerFn = Callable[[str], Coroutine[Any, Any, None]]

QUEUE_WORKER_FNS: dict[str, QueueWorkerFn] = {
    "ocr": worker_ocr,
    "llm": worker_llm,
    "kb_index": worker_kb_index,
    "webhook": worker_webhook,
    "flow_run": worker_flow_run,
}

SINGLETON_WORKERS: dict[str, QueueWorkerFn] = {
    "kb_reconcile": worker_kb_reconcile,
    "flow_cleanup": worker_flow_cleanup,
}


class WorkerPool:
    """Manage queue poller tasks with independent counts per queue type."""

    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._queue_tasks: dict[str, dict[int, asyncio.Task]] = {
            queue_type: {} for queue_type in QUEUE_WORKER_FNS
        }
        self._singleton_tasks: dict[str, asyncio.Task] = {}
        self._current_counts = WorkerCounts(
            n_ocr_workers=0,
            n_llm_workers=0,
            n_kb_index_workers=0,
            n_webhook_workers=0,
            n_flow_run_workers=0,
        )

    @property
    def current_counts(self) -> WorkerCounts:
        return self._current_counts

    async def reconcile(self, counts: WorkerCounts) -> None:
        async with self._lock:
            if counts == self._current_counts:
                return

            logger.info(
                "Reconciling worker pool: "
                f"ocr={counts.n_ocr_workers} llm={counts.n_llm_workers} "
                f"kb_index={counts.n_kb_index_workers} webhook={counts.n_webhook_workers} "
                f"flow_run={counts.n_flow_run_workers}"
            )

            if counts.total_queue_workers() <= 0:
                await self._stop_queue_workers()
                await self._stop_singleton_workers()
                self._current_counts = counts
                logger.info("Worker pool stopped (all queue worker counts are 0)")
                return

            await self._ensure_singleton_workers()
            for queue_type, worker_fn in QUEUE_WORKER_FNS.items():
                field = FIELD_BY_QUEUE_TYPE[queue_type]
                target = getattr(counts, field)
                await self._reconcile_queue(queue_type, worker_fn, target)

            self._current_counts = counts

    async def shutdown(self) -> None:
        async with self._lock:
            await self._stop_queue_workers()
            await self._stop_singleton_workers()
            self._current_counts = WorkerCounts(
                n_ocr_workers=0,
                n_llm_workers=0,
                n_kb_index_workers=0,
                n_webhook_workers=0,
                n_flow_run_workers=0,
            )

    async def _reconcile_queue(
        self,
        queue_type: str,
        worker_fn: QueueWorkerFn,
        target: int,
    ) -> None:
        tasks = self._queue_tasks[queue_type]
        current_indices = set(tasks.keys())

        for index in range(target):
            if index in current_indices:
                continue
            worker_id = f"{queue_type}_{index}"
            tasks[index] = asyncio.create_task(worker_fn(worker_id), name=worker_id)
            logger.info(f"Started worker task {worker_id}")

        for index in sorted(current_indices, reverse=True):
            if index < target:
                continue
            task = tasks.pop(index)
            task.cancel()
            logger.info(f"Cancelled worker task {task.get_name()}")

    async def _ensure_singleton_workers(self) -> None:
        for name, worker_fn in SINGLETON_WORKERS.items():
            if name in self._singleton_tasks and not self._singleton_tasks[name].done():
                continue
            worker_id = f"{name}_0"
            self._singleton_tasks[name] = asyncio.create_task(
                worker_fn(worker_id),
                name=worker_id,
            )
            logger.info(f"Started singleton worker task {worker_id}")

    async def _stop_queue_workers(self) -> None:
        for queue_type, tasks in self._queue_tasks.items():
            for index in sorted(list(tasks.keys()), reverse=True):
                task = tasks.pop(index)
                task.cancel()
                logger.info(f"Cancelled worker task {task.get_name()} ({queue_type})")

    async def _stop_singleton_workers(self) -> None:
        for name, task in list(self._singleton_tasks.items()):
            task.cancel()
            logger.info(f"Cancelled singleton worker task {name}")
            del self._singleton_tasks[name]


async def run_worker_supervisor(pool: WorkerPool) -> None:
    """Periodically reload worker counts from Mongo and resize the pool."""
    while True:
        try:
            counts = await ad.system.settings.get_worker_counts()
            await pool.reconcile(counts)
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.error(f"Worker pool supervisor reconcile failed: {e}")
        await asyncio.sleep(WORKER_POOL_RECONCILE_INTERVAL_SECS)


async def start_worker_pool() -> tuple[WorkerPool, asyncio.Task]:
    """Initial reconcile plus background supervisor. Used by API and worker process."""
    pool = WorkerPool()
    counts = await ad.system.settings.get_worker_counts()
    await pool.reconcile(counts)
    supervisor = asyncio.create_task(run_worker_supervisor(pool), name="worker_pool_supervisor")
    return pool, supervisor
