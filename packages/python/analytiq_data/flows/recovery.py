from __future__ import annotations

"""Finalize flow executions left in queued/running when a worker process dies."""

import logging
import os
from datetime import UTC, datetime, timedelta
from typing import Any

from bson import ObjectId

import analytiq_data as ad
from analytiq_data.flows.resume import (
    resolve_revision,
    maybe_auto_resume_after_recovery,
    reset_running_execution_for_scratch_retry,
    revision_resume_on_restart,
    send_flow_run_for_execution,
)

logger = logging.getLogger(__name__)


def _get_int_env(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except Exception:
        return default


# Running executions heartbeat every 5s; treat as dead after this gap with no heartbeat.
FLOW_EXECUTION_STALE_SECS = _get_int_env("FLOW_EXECUTION_STALE_SECS", 300)


def _stale_running_cutoff(now: datetime) -> datetime:
    return now - timedelta(seconds=FLOW_EXECUTION_STALE_SECS)


def _interrupted_error() -> dict[str, Any]:
    return {
        "message": "Execution interrupted (worker stopped or heartbeat lost)",
        "node_id": None,
        "node_name": None,
        "stack": None,
    }


async def _maybe_capture_docrouter_result(
    db,
    doc: dict[str, Any],
    *,
    status: str,
) -> None:
    if status not in ("stopped", "interrupted"):
        return
    exec_id = str(doc["_id"])
    revision_raw = doc.get("revision_snapshot")
    revision: dict | None = dict(revision_raw) if isinstance(revision_raw, dict) else None
    if revision is None:
        flow_revid = doc.get("flow_revid")
        if isinstance(flow_revid, str) and flow_revid.strip():
            try:
                revision = await db.flow_revisions.find_one(
                    {"_id": ObjectId(flow_revid.strip()), "flow_id": doc.get("flow_id")}
                )
            except Exception:
                revision = None
    if revision is None:
        return
    try:
        await ad.docrouter_flows.maybe_capture_docrouter_flow_result(
            db,
            exec_doc=doc,
            revision=revision,
            run_data=dict(doc.get("run_data") or {}),
            status=status,
        )
    except Exception as e:
        logger.warning(f"Flow recovery: docrouter flow result capture failed for {exec_id}: {e}")


async def _finalize_running_execution(
    db,
    doc: dict[str, Any],
    *,
    now: datetime,
    status: str,
    heartbeat_guard: dict[str, Any] | None,
) -> bool:
    exec_oid = doc["_id"]
    patch: dict[str, Any] = {
        "status": status,
        "finished_at": now,
        "last_heartbeat_at": now,
    }
    if status == "interrupted":
        patch["error"] = _interrupted_error()

    filt: dict[str, Any] = {"_id": exec_oid, "status": "running"}
    if heartbeat_guard is not None:
        filt.update(heartbeat_guard)

    res = await db.flow_executions.update_one(filt, {"$set": patch})
    if res.modified_count == 0:
        return False

    await _maybe_capture_docrouter_result(db, doc, status=status)
    return True


async def _recover_orphaned_running_doc(
    analytiq_client,
    db,
    doc: dict[str, Any],
    *,
    now: datetime,
    heartbeat_guard: dict[str, Any] | None,
    requeue_scratch_retry: bool,
) -> bool:
    """
    Reclaim one orphaned ``running`` execution.

    ``heartbeat_guard`` is ``None`` on full process startup (any running row), or
    ``{"last_heartbeat_at": {"$lt": cutoff}}`` for periodic stale recovery.
    """
    exec_oid = doc["_id"]
    exec_id = str(exec_oid)
    stop_requested = bool(doc.get("stop_requested"))

    if stop_requested:
        if not await _finalize_running_execution(
            db, doc, now=now, status="stopped", heartbeat_guard=heartbeat_guard
        ):
            return False
        logger.info(f"Recovered orphaned flow execution {exec_id} as stopped (stop requested)")
        return True

    revision = await resolve_revision(db, doc)
    if revision_resume_on_restart(revision):
        completed_nodes = list(doc.get("completed_nodes") or [])
        if completed_nodes:
            if not await _finalize_running_execution(
                db, doc, now=now, status="interrupted", heartbeat_guard=heartbeat_guard
            ):
                return False
            logger.info(
                f"Recovered orphaned flow execution {exec_id} as interrupted "
                f"({len(completed_nodes)} checkpoint(s))"
            )
            try:
                await maybe_auto_resume_after_recovery(
                    analytiq_client,
                    db,
                    source_oid=exec_oid,
                    status="interrupted",
                )
            except Exception as e:
                logger.warning(f"Flow recovery: checkpoint auto-resume failed for {exec_id}: {e}")
            return True

        if not await reset_running_execution_for_scratch_retry(db, exec_oid, heartbeat_guard=heartbeat_guard):
            return False
        logger.info(f"Recovered orphaned flow execution {exec_id} for scratch retry (queued)")
        if requeue_scratch_retry:
            fresh = await db.flow_executions.find_one({"_id": exec_oid})
            if fresh:
                try:
                    await send_flow_run_for_execution(analytiq_client, fresh)
                except Exception as e:
                    logger.warning(f"Flow recovery: scratch retry enqueue failed for {exec_id}: {e}")
        return True

    if not await _finalize_running_execution(
        db, doc, now=now, status="interrupted", heartbeat_guard=heartbeat_guard
    ):
        return False
    logger.info(f"Recovered orphaned flow execution {exec_id} as interrupted (resume_on_restart disabled)")
    return True


async def recover_orphaned_running_flow_executions_at_startup(
    analytiq_client,
    *,
    env: str | None = None,
) -> int:
    """
    After a full process restart, every ``running`` execution is orphaned.

    Call after queue in-flight release and before workers poll. Does not wait for
    heartbeat staleness.
    """
    env_name = env or os.getenv("ENV", "dev")
    db = analytiq_client.mongodb_async[env_name]
    now = datetime.now(UTC)

    recovered = 0
    cursor = db.flow_executions.find(
        {"status": "running"},
        {
            "_id": 1,
            "stop_requested": 1,
            "flow_id": 1,
            "organization_id": 1,
            "flow_revid": 1,
            "run_data": 1,
            "completed_nodes": 1,
            "trigger": 1,
            "revision_snapshot": 1,
        },
    )
    async for doc in cursor:
        if await _recover_orphaned_running_doc(
            analytiq_client,
            db,
            doc,
            now=now,
            heartbeat_guard=None,
            requeue_scratch_retry=False,
        ):
            recovered += 1
    return recovered


async def recover_stale_flow_executions(analytiq_client, *, env: str | None = None) -> int:
    """
    Mark orphaned ``running`` executions when ``last_heartbeat_at`` is stale.

    Uses the same resume / scratch-retry rules as startup recovery. For scratch
    retries, re-enqueues ``flow_run`` because the prior queue message may have been dropped.
    """
    env_name = env or os.getenv("ENV", "dev")
    db = analytiq_client.mongodb_async[env_name]
    now = datetime.now(UTC)
    cutoff = _stale_running_cutoff(now)
    heartbeat_guard = {"last_heartbeat_at": {"$lt": cutoff}}

    recovered = 0
    cursor = db.flow_executions.find(
        {"status": "running", **heartbeat_guard},
        {
            "_id": 1,
            "stop_requested": 1,
            "flow_id": 1,
            "organization_id": 1,
            "flow_revid": 1,
            "run_data": 1,
            "completed_nodes": 1,
            "trigger": 1,
            "revision_snapshot": 1,
        },
    )
    async for doc in cursor:
        if await _recover_orphaned_running_doc(
            analytiq_client,
            db,
            doc,
            now=now,
            heartbeat_guard=heartbeat_guard,
            requeue_scratch_retry=True,
        ):
            recovered += 1
            logger.info(
                f"Recovered stale flow execution {doc['_id']} "
                f"(heartbeat older than {FLOW_EXECUTION_STALE_SECS}s)"
            )
    return recovered
