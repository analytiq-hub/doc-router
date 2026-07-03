"""Queue worker process lifecycle (API and standalone worker entrypoints)."""

from __future__ import annotations

from analytiq_data.system.worker_counts import docrouter_queue_workers_enabled_in_process

__all__ = (
    "docrouter_queue_workers_enabled_in_process",
    "recover_on_worker_startup",
    "start_worker_pool",
)


async def recover_on_worker_startup(analytiq_client) -> None:
    from worker.worker import recover_on_worker_startup as _recover

    await _recover(analytiq_client)


async def start_worker_pool():
    from worker.pool import start_worker_pool as _start

    return await _start()
