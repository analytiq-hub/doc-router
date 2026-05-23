from __future__ import annotations

"""Cron job scheduling for active flow triggers."""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Awaitable, Callable
from zoneinfo import ZoneInfo

from croniter import croniter

logger = logging.getLogger(__name__)

TickCallback = Callable[[], Awaitable[None]]


@dataclass
class _CronJob:
    job_id: str
    cron_expr: str
    timezone: str
    callback: TickCallback
    task: asyncio.Task | None = None


class FlowScheduler:
    """
    Registers asyncio cron loops. Callbacks are invoked on every matching tick;
    callers should gate execution on leader status.
    """

    def __init__(self) -> None:
        self._jobs: dict[str, _CronJob] = {}

    def job_count(self) -> int:
        return len(self._jobs)

    async def register_cron(
        self,
        job_id: str,
        cron_expr: str,
        callback: TickCallback,
        *,
        timezone: str = "UTC",
        run_immediately: bool = False,
    ) -> None:
        await self.deregister(job_id)
        job = _CronJob(job_id=job_id, cron_expr=cron_expr, timezone=timezone, callback=callback)
        job.task = asyncio.create_task(self._cron_loop(job), name=f"flow_cron:{job_id}")
        self._jobs[job_id] = job
        logger.debug(f"Registered flow cron job {job_id!r} expr={cron_expr!r} tz={timezone!r}")
        if run_immediately:
            asyncio.create_task(self._invoke_callback(job, reason="immediate"), name=f"flow_cron_immediate:{job_id}")

    async def deregister(self, job_id: str) -> None:
        job = self._jobs.pop(job_id, None)
        if not job or not job.task:
            return
        job.task.cancel()
        try:
            await job.task
        except asyncio.CancelledError:
            pass
        logger.debug(f"Deregistered flow cron job {job_id!r}")

    async def deregister_prefix(self, prefix: str) -> None:
        for job_id in list(self._jobs.keys()):
            if job_id.startswith(prefix):
                await self.deregister(job_id)

    async def shutdown(self) -> None:
        for job_id in list(self._jobs.keys()):
            await self.deregister(job_id)

    async def _invoke_callback(self, job: _CronJob, *, reason: str) -> None:
        if job.job_id not in self._jobs:
            return
        try:
            await job.callback()
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception(f"Flow cron job {job.job_id!r} {reason} tick failed")

    async def _cron_loop(self, job: _CronJob) -> None:
        tz = ZoneInfo(job.timezone or "UTC")
        while True:
            try:
                now = datetime.now(tz)
                itr = croniter(job.cron_expr, now)
                next_run = itr.get_next(datetime)
                delay = max(0.0, (next_run - now).total_seconds())
                await asyncio.sleep(delay)
                if job.job_id not in self._jobs:
                    return
                await self._invoke_callback(job, reason="scheduled")
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception(f"Flow cron job {job.job_id!r} loop failed")
                await asyncio.sleep(5.0)
