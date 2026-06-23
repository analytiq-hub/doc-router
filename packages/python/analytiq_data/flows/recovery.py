from __future__ import annotations

"""Finalize flow executions left in queued/running when a worker process dies."""

import logging
import os
from datetime import UTC, datetime, timedelta
from typing import Any

from bson import ObjectId

import analytiq_data as ad
from analytiq_data.flows.resume import maybe_auto_resume_after_recovery

logger = logging.getLogger(__name__)


def _get_int_env(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except Exception:
        return default


# Running executions heartbeat every 5s; treat as dead after this gap with no heartbeat.
FLOW_EXECUTION_STALE_SECS = _get_int_env("FLOW_EXECUTION_STALE_SECS", 60)


def _stale_running_cutoff(now: datetime) -> datetime:
    return now - timedelta(seconds=FLOW_EXECUTION_STALE_SECS)


def _interrupted_error() -> dict[str, Any]:
    return {
        "message": "Execution interrupted (worker stopped or heartbeat lost)",
        "node_id": None,
        "node_name": None,
        "stack": None,
    }


async def recover_stale_flow_executions(analytiq_client, *, env: str | None = None) -> int:
    """
    Mark orphaned ``running`` executions terminal when ``last_heartbeat_at`` is stale.

    If ``stop_requested`` is set, status becomes ``stopped``; otherwise ``interrupted``.
    Idempotent: only touches rows still in ``running`` with an expired heartbeat.
    """
    env_name = env or os.getenv("ENV", "dev")
    db = analytiq_client.mongodb_async[env_name]
    now = datetime.now(UTC)
    cutoff = _stale_running_cutoff(now)

    stale_filter: dict[str, Any] = {
        "status": "running",
        "last_heartbeat_at": {"$lt": cutoff},
    }

    recovered = 0
    cursor = db.flow_executions.find(
        stale_filter,
        {
            "_id": 1,
            "stop_requested": 1,
            "flow_id": 1,
            "organization_id": 1,
            "run_data": 1,
            "trigger": 1,
            "revision_snapshot": 1,
            "flow_revid": 1,
        },
    )
    async for doc in cursor:
        exec_oid = doc["_id"]
        exec_id = str(exec_oid)
        stop_requested = bool(doc.get("stop_requested"))
        status = "stopped" if stop_requested else "interrupted"
        patch: dict[str, Any] = {
            "status": status,
            "finished_at": now,
            "last_heartbeat_at": now,
        }
        if status == "interrupted":
            patch["error"] = _interrupted_error()

        res = await db.flow_executions.update_one(
            {"_id": exec_oid, "status": "running", "last_heartbeat_at": {"$lt": cutoff}},
            {"$set": patch},
        )
        if res.modified_count == 0:
            continue

        recovered += 1
        logger.info(
            f"Recovered stale flow execution {exec_id} as {status} "
            f"(heartbeat older than {FLOW_EXECUTION_STALE_SECS}s)"
        )

        if status in ("stopped", "interrupted"):
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
            if revision is not None:
                try:
                    await ad.docrouter_flows.maybe_capture_docrouter_flow_result(
                        db,
                        exec_doc=doc,
                        revision=revision,
                        run_data=dict(doc.get("run_data") or {}),
                        status=status,
                    )
                except Exception as e:
                    logger.warning(f"Stale recovery: docrouter flow result capture failed for {exec_id}: {e}")

        if status == "interrupted":
            try:
                await maybe_auto_resume_after_recovery(
                    analytiq_client,
                    db,
                    source_oid=exec_oid,
                    status=status,
                )
            except Exception as e:
                logger.warning(f"Stale recovery: auto-resume failed for {exec_id}: {e}")

    return recovered
