from __future__ import annotations

"""Queue consumer for `flow_run` messages (executes flow revisions asynchronously)."""

import asyncio
import logging
from datetime import UTC, datetime
from typing import Any

from bson import ObjectId

import analytiq_data as ad


logger = logging.getLogger(__name__)


FLOW_RUN_QUEUE = "flow_run"
HEARTBEAT_INTERVAL_SECS = 5
_ACTIVE_FLOW_EXEC_STATUSES = frozenset({"queued", "running"})


def _as_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def _flow_run_execution_id(msg_doc: dict[str, Any]) -> str:
    payload = msg_doc.get("msg") or {}
    eid = payload.get("execution_id")
    return eid.strip() if isinstance(eid, str) else ""


def should_reclaim_flow_run_message(
    execution: dict[str, Any] | None,
    *,
    lease_cutoff: datetime,
    processing_started_at: datetime | None,
) -> bool:
    """
    Return True when a stale ``flow_run`` queue message should be reclaimed.

    Heartbeat-aware reclaim leaves messages alone when the linked execution is
    still alive. Queued executions without a heartbeat yet are treated as alive
    when ``started_at`` or the message lease is still within the visibility window.
    """
    if execution is None:
        return True

    status = execution.get("status")
    if status not in _ACTIVE_FLOW_EXEC_STATUSES:
        return True

    heartbeat = execution.get("last_heartbeat_at")
    if isinstance(heartbeat, datetime):
        return _as_utc(heartbeat) <= lease_cutoff

    if status == "queued":
        started_at = execution.get("started_at")
        if isinstance(started_at, datetime) and _as_utc(started_at) > lease_cutoff:
            return False
        if isinstance(processing_started_at, datetime) and processing_started_at > lease_cutoff:
            return False
        return True

    return True


async def _load_flow_run_executions_by_id(
    db,
    execution_ids: list[str],
) -> dict[str, dict[str, Any]]:
    oids: list[ObjectId] = []
    for eid in execution_ids:
        if isinstance(eid, str) and ObjectId.is_valid(eid):
            oids.append(ObjectId(eid))
    if not oids:
        return {}

    out: dict[str, dict[str, Any]] = {}
    cursor = db.flow_executions.find(
        {"_id": {"$in": oids}},
        {"status": 1, "last_heartbeat_at": 1, "started_at": 1},
    )
    async for doc in cursor:
        out[str(doc["_id"])] = doc
    return out


async def recv_flow_run_msg(analytiq_client) -> dict[str, Any] | None:
    """
    Receive the next ``flow_run`` message, with heartbeat-aware stale reclaim.

    Pending messages are claimed first. Stale ``processing`` rows are only
    re-claimed when the linked execution is missing, terminal, or has a stale
    heartbeat.
    """
    msg = await ad.queue.recv_pending_msg(analytiq_client, FLOW_RUN_QUEUE)
    if msg:
        return msg

    now = datetime.now(UTC)
    cutoff = ad.queue.lease_cutoff(now)
    db = ad.common.get_async_db(analytiq_client)

    candidates = await ad.queue.list_stale_processing_messages(
        analytiq_client,
        FLOW_RUN_QUEUE,
        cutoff=cutoff,
    )
    if not candidates:
        return None

    execution_ids = [_flow_run_execution_id(c) for c in candidates]
    executions = await _load_flow_run_executions_by_id(db, execution_ids)

    for candidate in candidates:
        execution = executions.get(_flow_run_execution_id(candidate))
        proc_started = candidate.get("processing_started_at")
        if isinstance(proc_started, datetime):
            proc_started = _as_utc(proc_started)
        if not should_reclaim_flow_run_message(
            execution,
            lease_cutoff=cutoff,
            processing_started_at=proc_started,
        ):
            continue

        claimed = await ad.queue.try_reclaim_stale_processing_msg(
            analytiq_client,
            FLOW_RUN_QUEUE,
            candidate["_id"],
            cutoff=cutoff,
        )
        if claimed:
            return claimed

    return None


async def recover_stale_flow_run_messages(analytiq_client) -> int:
    """
    Reset stale ``flow_run`` queue messages to ``pending`` when safe to reclaim.

    Messages linked to executions that are still alive (fresh heartbeat) are
    left alone even when past the queue visibility timeout.
    """
    cutoff = ad.queue.lease_cutoff()
    db = ad.common.get_async_db(analytiq_client)

    candidates = await ad.queue.list_stale_processing_messages(
        analytiq_client,
        FLOW_RUN_QUEUE,
        cutoff=cutoff,
        limit=None,
    )
    if not candidates:
        return 0

    execution_ids = [_flow_run_execution_id(c) for c in candidates]
    executions = await _load_flow_run_executions_by_id(db, execution_ids)

    recovered = 0
    for candidate in candidates:
        execution = executions.get(_flow_run_execution_id(candidate))
        proc_started = candidate.get("processing_started_at")
        if isinstance(proc_started, datetime):
            proc_started = _as_utc(proc_started)
        if not should_reclaim_flow_run_message(
            execution,
            lease_cutoff=cutoff,
            processing_started_at=proc_started,
        ):
            continue

        if await ad.queue.release_stale_processing_msg(
            analytiq_client,
            FLOW_RUN_QUEUE,
            candidate["_id"],
            cutoff=cutoff,
        ):
            recovered += 1

    if recovered:
        logger.info(
            f"Recovered {recovered} stale flow_run messages "
            f"(visibility_timeout={ad.queue.QUEUE_VISIBILITY_TIMEOUT_SECS}s, heartbeat-aware)"
        )
    return recovered


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
    trigger = payload.get("trigger") or {"type": "manual"}

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

    tool_test_raw = exec_doc.get("tool_test_request")
    ui_target_node_id = exec_doc.get("target_node_id")
    run_target_node_id = ui_target_node_id
    if isinstance(tool_test_raw, dict) and ui_target_node_id:
        tool_name = str(tool_test_raw.get("tool_name") or "").strip()
        tool_args = tool_test_raw.get("arguments")
        if not isinstance(tool_args, dict):
            tool_args = {}
        try:
            revision, start_kw, run_target_node_id = ad.flows.prepare_tool_test_run(
                revision=revision,
                tool_node_id=str(ui_target_node_id),
                tool_name=tool_name,
                arguments=tool_args,
            )
            revision_conns = ad.flows.coerce_json_connections_to_dataclasses(revision.get("connections"))
            nodes_list = revision.get("nodes") or []
        except ad.flows.FlowValidationError as e:
            await db.flow_executions.update_one(
                {"_id": ObjectId(exec_id)},
                {
                    "$set": {
                        "status": "error",
                        "finished_at": datetime.now(UTC),
                        "error": ad.flows.execution_error_envelope(e),
                    }
                },
            )
            await ad.queue.delete_msg(analytiq_client, "flow_run", msg_id)
            return

    allowed_pins: frozenset[str] | None = None
    tgt_any = run_target_node_id
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

    exec_mode = str(exec_doc.get("mode") or "manual")
    pin_touched: set[str] = set()
    if ad.flows.pin_data_enabled_for_mode(exec_mode):
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

    flow_log_level = await ad.flows.fetch_org_flow_log_level(db, org_id)

    completed_raw = exec_doc.get("completed_nodes") or []
    completed_nodes = frozenset(str(x) for x in completed_raw if x)
    resumed_from_raw = exec_doc.get("resumed_from")
    resumed_from = str(resumed_from_raw).strip() if resumed_from_raw else None

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
        flow_log_level=flow_log_level,
        completed_nodes=completed_nodes,
        resumed_from=resumed_from,
    )

    try:
        claim = await db.flow_executions.update_one(
            {"_id": ObjectId(exec_id), "status": "queued"},
            {"$set": {"status": "running", "started_at": datetime.now(UTC), "last_heartbeat_at": datetime.now(UTC)}},
        )
        if claim.matched_count == 0:
            # Already claimed or completed by another worker; drop the message.
            await ad.queue.delete_msg(analytiq_client, "flow_run", msg_id)
            return
        heartbeat_task = asyncio.create_task(_heartbeat_loop(db, exec_id))
        try:
            tgt = run_target_node_id
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
        try:
            await ad.docrouter_flows.maybe_capture_docrouter_flow_result(
                db,
                exec_doc=exec_doc,
                revision=revision,
                run_data=context.run_data,
                status=status,
            )
        except Exception as e:
            logger.warning(f"flow_run: failed to capture docrouter flow result for execution {exec_id}: {e}")
        await ad.queue.delete_msg(analytiq_client, "flow_run", msg_id)
    except asyncio.TimeoutError:
        await db.flow_executions.update_one(
            {"_id": ObjectId(exec_id)},
            {
                "$set": {
                    "status": "error",
                    "finished_at": datetime.now(UTC),
                    "error": ad.flows.execution_error_envelope(asyncio.TimeoutError("Execution timed out")),
                }
            },
        )
        await ad.queue.delete_msg(analytiq_client, "flow_run", msg_id)
    except Exception as e:
        err = ad.flows.execution_error_envelope(e, run_data=context.run_data)
        patch: dict[str, Any] = {
            "status": "error",
            "finished_at": datetime.now(UTC),
            "error": err,
        }
        node_id = err.get("node_id")
        if isinstance(node_id, str) and node_id.strip():
            patch["last_node_executed"] = node_id.strip()
        await db.flow_executions.update_one({"_id": ObjectId(exec_id)}, {"$set": patch})
        attempts = msg.get("attempts", 0)
        if attempts >= ad.queue.queue.MAX_QUEUE_ATTEMPTS:
            await ad.queue.move_to_dlq(analytiq_client, "flow_run", msg_id, str(e))
        else:
            await ad.queue.report_last_error(analytiq_client, "flow_run", msg_id, str(e))

