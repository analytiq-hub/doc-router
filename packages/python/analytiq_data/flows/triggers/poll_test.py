from __future__ import annotations

"""Editor test run for poll triggers (one poll without activating)."""

from datetime import datetime, UTC
from typing import Any

import analytiq_data as ad

from .enqueue import _serialize_flow_items
from .static_data import load_node_static_data, save_node_static_data


async def enqueue_poll_trigger_test_run(
    analytiq_client,
    *,
    organization_id: str,
    flow_id: str,
    flow_revid_lineage: str,
    revision_snapshot: dict[str, Any],
    trigger_node_id: str,
) -> str:
    """
    Call ``poll()`` once for the given trigger node and enqueue a test run.

    Uses ``revision_snapshot`` (editor graph) and does not require the flow to be active.
    """

    nodes = revision_snapshot.get("nodes") or []
    node = next((n for n in nodes if isinstance(n, dict) and n.get("id") == trigger_node_id), None)
    if not node:
        raise ad.flows.FlowValidationError(f"Trigger node not found: {trigger_node_id!r}")

    node_type_key = node.get("type") or ""
    try:
        nt = ad.flows.get(node_type_key)
    except KeyError as e:
        raise ad.flows.FlowValidationError(f"Unknown node type: {node_type_key!r}") from e
    if not getattr(nt, "polling", False):
        raise ad.flows.FlowValidationError(f"Node {trigger_node_id!r} is not a poll trigger")

    poll_fn = getattr(nt, "poll", None)
    if poll_fn is None:
        raise ad.flows.FlowValidationError(f"Poll trigger {trigger_node_id!r} has no poll() implementation")

    db = ad.common.get_async_db(analytiq_client)
    static_data = await load_node_static_data(db, flow_id, trigger_node_id)
    ctx = ad.flows.PollContext(
        organization_id=organization_id,
        flow_id=flow_id,
        flow_revid=flow_revid_lineage,
        node_id=trigger_node_id,
        mode="manual",
        analytiq_client=analytiq_client,
        tick_meta={"rule_index": 0, "tick_key": "test", "test": True},
        static_data=static_data,
    )
    items = await poll_fn(ctx, node)
    if ctx.data_changed:
        await save_node_static_data(db, flow_id, trigger_node_id, ctx.static_data)

    if not items or all(not lane for lane in items):
        raise ad.flows.FlowValidationError("Poll trigger test produced no items")

    trigger: dict[str, Any] = {
        "type": "poll",
        "node_id": trigger_node_id,
        "items": _serialize_flow_items(items),
        "tick_key": "test",
        "rule_index": 0,
        "test": True,
    }

    exec_doc: dict[str, Any] = {
        "flow_id": flow_id,
        "flow_revid": flow_revid_lineage,
        "organization_id": organization_id,
        "mode": "schedule",
        "status": "queued",
        "started_at": datetime.now(UTC),
        "finished_at": None,
        "last_heartbeat_at": None,
        "stop_requested": False,
        "last_node_executed": None,
        "wait_till": None,
        "retry_of": None,
        "parent_execution_id": None,
        "run_data": {},
        "error": None,
        "trigger": trigger,
        "start_trigger_node_id": trigger_node_id,
        "target_node_id": None,
        "initial_run_data": None,
        "dirty_node_ids": None,
        "revision_snapshot": revision_snapshot,
    }

    res = await db.flow_executions.insert_one(exec_doc)
    exec_id = str(res.inserted_id)

    await ad.queue.send_msg(
        analytiq_client,
        "flow_run",
        msg={
            "flow_id": flow_id,
            "flow_revid": flow_revid_lineage or "",
            "execution_id": exec_id,
            "organization_id": organization_id,
            "trigger": trigger,
        },
    )
    return exec_id
