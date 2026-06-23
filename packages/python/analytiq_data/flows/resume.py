from __future__ import annotations

"""Checkpoint resume: enqueue a new execution seeded from a terminal source run."""

import logging
from typing import Any

from bson import ObjectId

import analytiq_data as ad

logger = logging.getLogger(__name__)

TERMINAL_RESUME_SOURCE_STATUSES = frozenset({"stopped", "error", "interrupted"})


def revision_resume_on_restart(revision: dict[str, Any] | None) -> bool:
    if not revision:
        return False
    settings = revision.get("settings") or {}
    if not isinstance(settings, dict):
        return False
    return bool(settings.get("resume_on_restart"))


async def resolve_revision(db, source_doc: dict[str, Any]) -> dict[str, Any] | None:
    revision_raw = source_doc.get("revision_snapshot")
    if isinstance(revision_raw, dict):
        return dict(revision_raw)
    flow_revid = source_doc.get("flow_revid")
    flow_id = source_doc.get("flow_id")
    if not isinstance(flow_revid, str) or not flow_revid.strip() or not flow_id:
        return None
    try:
        rev = await db.flow_revisions.find_one({"_id": ObjectId(flow_revid.strip()), "flow_id": flow_id})
    except Exception:
        return None
    return dict(rev) if rev else None


async def enqueue_resume_execution(
    analytiq_client,
    db,
    source_doc: dict[str, Any],
) -> str | None:
    """
    Clone checkpoint state into a new queued execution and link it to the source.

    Returns the new execution id, or ``None`` if resume is not possible (no checkpoints
    or source already resumed).
    """
    source_oid = source_doc.get("_id")
    if source_oid is None:
        return None

    completed_nodes = list(source_doc.get("completed_nodes") or [])
    if not completed_nodes:
        return None

    if source_doc.get("resumed_by"):
        return None

    source_id = str(source_oid)
    new_oid = ObjectId()
    new_id = str(new_oid)

    run_data = dict(source_doc.get("run_data") or {})
    exec_doc: dict[str, Any] = {
        "_id": new_oid,
        "flow_id": source_doc["flow_id"],
        "flow_revid": source_doc["flow_revid"],
        "organization_id": source_doc["organization_id"],
        "mode": source_doc.get("mode") or "manual",
        "status": "queued",
        "started_at": None,
        "finished_at": None,
        "last_heartbeat_at": None,
        "stop_requested": False,
        "last_node_executed": source_doc.get("last_node_executed"),
        "wait_till": None,
        "retry_of": None,
        "parent_execution_id": None,
        "run_data": run_data,
        "completed_nodes": completed_nodes,
        "resumed_from": source_id,
        "resumed_by": None,
        "error": None,
        "trigger": dict(source_doc.get("trigger") or {}),
        "start_trigger_node_id": source_doc.get("start_trigger_node_id"),
        "target_node_id": source_doc.get("target_node_id"),
        "initial_run_data": None,
        "dirty_node_ids": None,
    }
    revision_snapshot = source_doc.get("revision_snapshot")
    if isinstance(revision_snapshot, dict):
        exec_doc["revision_snapshot"] = revision_snapshot

    await db.flow_executions.insert_one(exec_doc)

    guard = await db.flow_executions.update_one(
        {
            "_id": source_oid,
            "$or": [{"resumed_by": {"$exists": False}}, {"resumed_by": None}],
        },
        {"$set": {"resumed_by": new_id}},
    )
    if guard.modified_count == 0:
        await db.flow_executions.delete_one({"_id": new_oid})
        return None

    await ad.queue.send_msg(
        analytiq_client,
        "flow_run",
        msg={
            "flow_id": exec_doc["flow_id"],
            "flow_revid": exec_doc.get("flow_revid") or "",
            "execution_id": new_id,
            "organization_id": exec_doc["organization_id"],
            "trigger": exec_doc["trigger"],
        },
    )
    logger.info(f"Enqueued resume execution {new_id} from source {source_id}")
    return new_id


async def reset_running_execution_for_scratch_retry(
    db,
    exec_oid: ObjectId,
    *,
    heartbeat_guard: dict[str, Any] | None = None,
) -> bool:
    """Return a scratch-retryable ``running`` execution to ``queued`` (same row, cleared state)."""
    filt: dict[str, Any] = {"_id": exec_oid, "status": "running"}
    if heartbeat_guard is not None:
        filt.update(heartbeat_guard)

    res = await db.flow_executions.update_one(
        filt,
        {
            "$set": {
                "status": "queued",
                "started_at": None,
                "last_heartbeat_at": None,
                "run_data": {},
                "completed_nodes": [],
                "stop_requested": False,
            },
            "$unset": {"finished_at": "", "error": ""},
        },
    )
    return res.modified_count > 0


async def send_flow_run_for_execution(analytiq_client, exec_doc: dict[str, Any]) -> None:
    exec_id = str(exec_doc["_id"])
    await ad.queue.send_msg(
        analytiq_client,
        "flow_run",
        msg={
            "flow_id": exec_doc["flow_id"],
            "flow_revid": exec_doc.get("flow_revid") or "",
            "execution_id": exec_id,
            "organization_id": exec_doc["organization_id"],
            "trigger": dict(exec_doc.get("trigger") or {}),
        },
    )


async def maybe_auto_resume_after_recovery(
    analytiq_client,
    db,
    *,
    source_oid: ObjectId,
    status: str,
) -> str | None:
    """When ``resume_on_restart`` is enabled, resume worker-interrupted runs only."""
    if status != "interrupted":
        return None

    source_doc = await db.flow_executions.find_one({"_id": source_oid})
    if not source_doc:
        return None

    revision = await resolve_revision(db, source_doc)
    if not revision_resume_on_restart(revision):
        return None

    return await enqueue_resume_execution(analytiq_client, db, source_doc)
