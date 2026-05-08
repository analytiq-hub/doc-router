from __future__ import annotations

"""Queue consumer for `flow_run` messages (executes flow revisions asynchronously)."""

import asyncio
import logging
from datetime import datetime, UTC

from bson import ObjectId

import analytiq_data as ad


logger = logging.getLogger(__name__)


HEARTBEAT_INTERVAL_SECS = 5


async def _heartbeat_loop(db, exec_id: str) -> None:
    """Bump last_heartbeat_at every HEARTBEAT_INTERVAL_SECS while a run is active."""
    while True:
        await asyncio.sleep(HEARTBEAT_INTERVAL_SECS)
        try:
            await db.flow_executions.update_one(
                {"_id": ObjectId(exec_id)},
                {"$set": {"last_heartbeat_at": datetime.now(UTC)}},
            )
        except Exception:
            pass


async def process_flow_run_msg(analytiq_client, msg: dict) -> None:
    """
    Execute a single queued flow run.

    Reads the flow revision and execution document from MongoDB, runs the generic
    engine, persists incremental `run_data`, and updates execution status.
    """

    msg_id = str(msg["_id"])
    payload = msg.get("msg") or {}
    flow_id = payload["flow_id"]
    flow_revid_payload = payload.get("flow_revid") or ""
    exec_id = payload["execution_id"]
    org_id = payload["organization_id"]
    trigger = payload.get("trigger") or {"type": "manual", "document_id": None}

    db = ad.common.get_async_db(analytiq_client)

    exec_doc = await db.flow_executions.find_one({"_id": ObjectId(exec_id)})
    if not exec_doc:
        await ad.queue.delete_msg(analytiq_client, "flow_run", msg_id)
        return

    revision_raw = exec_doc.get("revision_snapshot")
    revision: dict | None = dict(revision_raw) if isinstance(revision_raw, dict) else None
    if revision is None:
        fr = flow_revid_payload.strip() or exec_doc.get("flow_revid")
        fr = fr.strip() if isinstance(fr, str) else ""
        if not fr:
            await db.flow_executions.update_one(
                {"_id": ObjectId(exec_id)},
                {
                    "$set": {
                        "status": "error",
                        "finished_at": datetime.now(UTC),
                        "error": {
                            "message": "Execution has no revision_snapshot and empty flow_revid",
                            "node_id": None,
                            "node_name": None,
                            "stack": None,
                        },
                    }
                },
            )
            await ad.queue.delete_msg(analytiq_client, "flow_run", msg_id)
            return
        revision = await db.flow_revisions.find_one({"_id": ObjectId(fr), "flow_id": flow_id})
        if not revision:
            await db.flow_executions.update_one(
                {"_id": ObjectId(exec_id)},
                {"$set": {"status": "error", "finished_at": datetime.now(UTC), "error": {"message": "Revision not found", "node_id": None, "node_name": None, "stack": None}}},
            )
            await ad.queue.delete_msg(analytiq_client, "flow_run", msg_id)
            return

    run_data: dict = dict(exec_doc.get("run_data") or {})
    initial = exec_doc.get("initial_run_data") or {}
    dirty = frozenset(str(x) for x in (exec_doc.get("dirty_node_ids") or []) if x)
    for k, v in initial.items():
        if k in dirty:
            continue
        run_data[k] = v

    try:
        revision_conns = ad.flows.coerce_json_connections_to_dataclasses(revision.get("connections"))
    except Exception as e:
        logger.warning("flow_run: failed to parse revision connections (%r); pin downstream invalidation may be incomplete", e)
        revision_conns = {}

    nodes_list = revision.get("nodes") or []
    nodes_list = nodes_list if isinstance(nodes_list, list) else []
    st_raw = exec_doc.get("start_trigger_node_id")
    start_kw = str(st_raw).strip() if isinstance(st_raw, str) and str(st_raw).strip() else None

    allowed_pins: frozenset[str] | None = None
    tgt_any = exec_doc.get("target_node_id")
    if tgt_any:
        try:
            trig = ad.flows.resolve_execution_start_trigger(
                nodes=nodes_list,
                connections=revision_conns,
                start_trigger_node_id=start_kw,
                target_node_id=str(tgt_any).strip() if tgt_any else None,
            )
            allowed_pins = frozenset(
                ad.flows.upstream_closure_for_target(trig, str(tgt_any), revision_conns)
            )
        except Exception as e:
            logger.warning("flow_run: pin overlay subgraph failed (%r); applying all revision pins", e)
            allowed_pins = None
    elif start_kw:
        # Full run from an explicit trigger (multi-trigger manual, webhook): do not merge pin_data for
        # other triggers' branches — that would show them as succeeded without executing downstream.
        try:
            allowed_pins = ad.flows.trigger_forward_reachable_nodes(start_kw, revision_conns)
        except Exception as e:
            logger.warning("flow_run: pin forward scope failed (%r); applying all revision pins", e)
            allowed_pins = None

    pin_touched = ad.flows.apply_revision_pins_to_run_data(
        run_data, revision, allowed_node_ids=allowed_pins
    )
    if pin_touched:
        ad.flows.invalidate_run_data_downstream_of_pins(
            run_data, revision_conns, pin_touched, limit_nodes=allowed_pins
        )

    if allowed_pins is not None:
        ad.flows.prune_run_data_outside_closure(run_data, allowed_pins)

    lineage_revid = str(exec_doc.get("flow_revid") or flow_revid_payload or "")

    context = ad.flows.ExecutionContext(
        organization_id=org_id,
        execution_id=exec_id,
        flow_id=flow_id,
        flow_revid=lineage_revid,
        mode=exec_doc.get("mode") or "manual",
        trigger_data=trigger,
        run_data=run_data,
        analytiq_client=analytiq_client,
        stop_requested=bool(exec_doc.get("stop_requested")),
        logger=logger,
        revision_nodes=list(revision.get("nodes") or []),
    )

    try:
        claim = await db.flow_executions.update_one(
            {"_id": ObjectId(exec_id), "status": "queued"},
            {"$set": {"status": "running", "last_heartbeat_at": datetime.now(UTC)}},
        )
        if claim.matched_count == 0:
            # Already claimed or completed by another worker; drop the message.
            await ad.queue.delete_msg(analytiq_client, "flow_run", msg_id)
            return
        heartbeat_task = asyncio.create_task(_heartbeat_loop(db, exec_id))
        try:
            tgt = exec_doc.get("target_node_id")
            target_node_id = str(tgt) if tgt else None
            result = await ad.flows.run_flow(
                context=context,
                revision=revision,
                target_node_id=target_node_id,
                dirty_node_ids=dirty if dirty else None,
                start_trigger_node_id=start_kw,
            )
        finally:
            heartbeat_task.cancel()
            try:
                await heartbeat_task
            except asyncio.CancelledError:
                pass
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

