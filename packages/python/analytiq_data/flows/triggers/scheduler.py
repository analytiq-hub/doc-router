from __future__ import annotations

"""Cron and anchored-interval scheduling for active flow triggers."""

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, UTC
from typing import Awaitable, Callable
from zoneinfo import ZoneInfo

from croniter import croniter

from .cron_exprs import next_anchored_run


logger = logging.getLogger(__name__)

TickCallback = Callable[[], Awaitable[None]]


@dataclass
class _CronJob:
    job_id: str
    cron_expr: str
    timezone: str
    callback: TickCallback
    task: asyncio.Task | None = None


@dataclass
class _IntervalJob:
    job_id: str
    interval_secs: float
    anchor: datetime
    callback: TickCallback
    task: asyncio.Task | None = None


class FlowScheduler:
    """
    Registers asyncio cron loops and anchored fixed-interval loops.

    Interval schedules fire at ``anchor + n * interval`` (relative to configuration
    time), not on wall-clock minute/hour/day boundaries.
    """

    def __init__(self) -> None:
        self._cron_jobs: dict[str, _CronJob] = {}
        self._interval_jobs: dict[str, _IntervalJob] = {}

    def job_count(self) -> int:
        return len(self._cron_jobs) + len(self._interval_jobs)

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
        self._cron_jobs[job_id] = job
        logger.debug(f"Registered flow cron job {job_id!r} expr={cron_expr!r} tz={timezone!r}")
        if run_immediately:
            asyncio.create_task(
                self._invoke_callback(job.callback, job_id, reason="immediate"),
                name=f"flow_cron_immediate:{job_id}",
            )

    async def register_interval(
        self,
        job_id: str,
        interval_secs: float,
        callback: TickCallback,
        *,
        anchor: datetime,
        run_immediately: bool = False,
    ) -> None:
        await self.deregister(job_id)
        if anchor.tzinfo is None:
            anchor = anchor.replace(tzinfo=UTC)
        else:
            anchor = anchor.astimezone(UTC)
        job = _IntervalJob(
            job_id=job_id,
            interval_secs=interval_secs,
            anchor=anchor,
            callback=callback,
        )
        job.task = asyncio.create_task(
            self._interval_loop(job, skip_first=run_immediately),
            name=f"flow_interval:{job_id}",
        )
        self._interval_jobs[job_id] = job
        logger.debug(
            f"Registered flow interval job {job_id!r} every={interval_secs}s anchor={anchor.isoformat()!r}"
        )
        if run_immediately:
            asyncio.create_task(
                self._invoke_callback(job.callback, job_id, reason="immediate"),
                name=f"flow_interval_immediate:{job_id}",
            )

    async def deregister(self, job_id: str) -> None:
        cron_job = self._cron_jobs.pop(job_id, None)
        if cron_job and cron_job.task:
            cron_job.task.cancel()
            try:
                await cron_job.task
            except asyncio.CancelledError:
                pass
            logger.debug(f"Deregistered flow cron job {job_id!r}")
            return

        interval_job = self._interval_jobs.pop(job_id, None)
        if interval_job and interval_job.task:
            interval_job.task.cancel()
            try:
                await interval_job.task
            except asyncio.CancelledError:
                pass
            logger.debug(f"Deregistered flow interval job {job_id!r}")

    async def deregister_prefix(self, prefix: str) -> None:
        for job_id in list(self._cron_jobs.keys()):
            if job_id.startswith(prefix):
                await self.deregister(job_id)
        for job_id in list(self._interval_jobs.keys()):
            if job_id.startswith(prefix):
                await self.deregister(job_id)

    async def shutdown(self) -> None:
        for job_id in list(self._cron_jobs.keys()):
            await self.deregister(job_id)
        for job_id in list(self._interval_jobs.keys()):
            await self.deregister(job_id)

    async def _invoke_callback(self, callback: TickCallback, job_id: str, *, reason: str) -> None:
        if job_id not in self._cron_jobs and job_id not in self._interval_jobs:
            return
        try:
            await callback()
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception(f"Flow scheduled job {job_id!r} {reason} tick failed")

    async def _cron_loop(self, job: _CronJob) -> None:
        tz = ZoneInfo(job.timezone or "UTC")
        while True:
            try:
                now = datetime.now(tz)
                itr = croniter(job.cron_expr, now)
                next_run = itr.get_next(datetime)
                delay = max(0.0, (next_run - now).total_seconds())
                await asyncio.sleep(delay)
                if job.job_id not in self._cron_jobs:
                    return
                await self._invoke_callback(job.callback, job.job_id, reason="scheduled")
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception(f"Flow cron job {job.job_id!r} loop failed")
                await asyncio.sleep(5.0)

    async def _interval_loop(self, job: _IntervalJob, *, skip_first: bool) -> None:
        if skip_first:
            next_run = job.anchor + timedelta(seconds=job.interval_secs)
        else:
            next_run = next_anchored_run(job.anchor, job.interval_secs)
        while True:
            try:
                now = datetime.now(UTC)
                delay = max(0.0, (next_run - now).total_seconds())
                await asyncio.sleep(delay)
                if job.job_id not in self._interval_jobs:
                    return
                await self._invoke_callback(job.callback, job.job_id, reason="scheduled")
                next_run = next_run + timedelta(seconds=job.interval_secs)
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception(f"Flow interval job {job.job_id!r} loop failed")
                await asyncio.sleep(5.0)
