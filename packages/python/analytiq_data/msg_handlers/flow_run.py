from __future__ import annotations

import asyncio
import logging
from datetime import datetime, UTC

from bson import ObjectId

import analytiq_data as ad


logger = logging.getLogger(__name__)


HEARTBEAT_INTERVAL_SECS = 5


async def process_flow_run_msg(analytiq_client, msg: dict) -> None:
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

    async def persist_run_data(execution_id: str, run_data: dict) -> None:
        await db.flow_executions.update_one(
            {"_id": ObjectId(execution_id)},
            {
                "$set": {
                    "run_data": run_data,
                    "last_heartbeat_at": datetime.now(UTC),
                }
            },
        )

    async def read_stop(execution_id: str) -> bool:
        d = await db.flow_executions.find_one({"_id": ObjectId(execution_id)}, {"stop_requested": 1})
        return bool((d or {}).get("stop_requested"))

    revision = await db.flow_revisions.find_one({"_id": ObjectId(flow_revid), "flow_id": flow_id})
    if not revision:
        await db.flow_executions.update_one(
            {"_id": ObjectId(exec_id)},
            {"$set": {"status": "error", "finished_at": datetime.now(UTC), "error": {"message": "Revision not found", "node_id": None, "node_name": None, "stack": None}}},
        )
        await ad.queue.delete_msg(analytiq_client, "flow_run", msg_id)
        return

    # Late-import to avoid circular deps: app layer provides services + node registrations.
    from app.flows.services import FlowServicesImpl

    services = FlowServicesImpl(analytiq_client)
    context = ad.flows.ExecutionContext(
        organization_id=org_id,
        execution_id=exec_id,
        flow_id=flow_id,
        flow_revid=flow_revid,
        mode=exec_doc.get("mode") or "manual",
        trigger_data=trigger,
        run_data=exec_doc.get("run_data") or {},
        services=services,
        stop_requested=bool(exec_doc.get("stop_requested")),
        logger=logger,
    )

    engine = ad.flows.FlowEngine(persist_run_data=persist_run_data, read_stop_requested=read_stop)

    try:
        await db.flow_executions.update_one(
            {"_id": ObjectId(exec_id)},
            {"$set": {"status": "running", "last_heartbeat_at": datetime.now(UTC)}},
        )
        result = await engine.run(context=context, revision=revision)
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

