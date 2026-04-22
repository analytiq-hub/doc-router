from __future__ import annotations

"""Queue consumer for `flow_run` messages (executes flow revisions asynchronously)."""

import asyncio
import logging
from datetime import datetime, UTC

from bson import ObjectId

import analytiq_data as ad


logger = logging.getLogger(__name__)


HEARTBEAT_INTERVAL_SECS = 5


async def process_flow_run_msg(analytiq_client, msg: dict) -> None:
    """
    Execute a single queued flow run.

    Reads the flow revision and execution document from MongoDB, runs the generic
    engine, persists incremental `run_data`, and updates execution status.
    """

    msg_id = str(msg["_id"])
    payload = msg.get("msg") or {}
    flow_id = payload["flow_id"]
    flow_revid = payload["flow_revid"]
    exec_id = payload["execution_id"]
    org_id = payload["organization_id"]
    trigger = payload.get("trigger") or {"type": "manual", "document_id": None}

    db = ad.common.get_async_db(analytiq_client)

    exec_doc = await db.flow_executions.find_one({"_id": ObjectId(exec_id)})
    if not exec_doc:
        await ad.queue.delete_msg(analytiq_client, "flow_run", msg_id)
        return

    revision = await db.flow_revisions.find_one({"_id": ObjectId(flow_revid), "flow_id": flow_id})
    if not revision:
        await db.flow_executions.update_one(
            {"_id": ObjectId(exec_id)},
            {"$set": {"status": "error", "finished_at": datetime.now(UTC), "error": {"message": "Revision not found", "node_id": None, "node_name": None, "stack": None}}},
        )
        await ad.queue.delete_msg(analytiq_client, "flow_run", msg_id)
        return

    context = ad.flows.ExecutionContext(
        organization_id=org_id,
        execution_id=exec_id,
        flow_id=flow_id,
        flow_revid=flow_revid,
        mode=exec_doc.get("mode") or "manual",
        trigger_data=trigger,
        run_data=exec_doc.get("run_data") or {},
        analytiq_client=analytiq_client,
        stop_requested=bool(exec_doc.get("stop_requested")),
        logger=logger,
    )

    try:
        await db.flow_executions.update_one(
            {"_id": ObjectId(exec_id)},
            {"$set": {"status": "running", "last_heartbeat_at": datetime.now(UTC)}},
        )
        result = await ad.flows.run_flow(context=context, revision=revision)
        status = result.get("status") or "success"
        await db.flow_executions.update_one(
            {"_id": ObjectId(exec_id)},
            {"$set": {"status": status, "finished_at": datetime.now(UTC), "last_heartbeat_at": datetime.now(UTC)}},
        )
        await ad.queue.delete_msg(analytiq_client, "flow_run", msg_id)
    except asyncio.TimeoutError:
        await db.flow_executions.update_one(
            {"_id": ObjectId(exec_id)},
            {"$set": {"status": "error", "finished_at": datetime.now(UTC), "error": {"message": "Execution timed out", "node_id": None, "node_name": None, "stack": None}}},
        )
        await ad.queue.delete_msg(analytiq_client, "flow_run", msg_id)
    except Exception as e:
        await db.flow_executions.update_one(
            {"_id": ObjectId(exec_id)},
            {"$set": {"status": "error", "finished_at": datetime.now(UTC), "error": {"message": str(e), "node_id": None, "node_name": None, "stack": None}}},
        )
        attempts = msg.get("attempts", 0)
        if attempts >= ad.queue.queue.MAX_QUEUE_ATTEMPTS:
            await ad.queue.move_to_dlq(analytiq_client, "flow_run", msg_id, str(e))
        else:
            await ad.queue.report_last_error(analytiq_client, "flow_run", msg_id, str(e))

