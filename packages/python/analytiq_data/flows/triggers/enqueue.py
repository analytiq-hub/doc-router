from __future__ import annotations

"""Enqueue a scheduled/poll-triggered flow execution."""

import hashlib
from datetime import datetime, UTC
from typing import Any

from bson import ObjectId

import analytiq_data as ad


def _serialize_flow_items(items: list[list["ad.flows.FlowItem"]]) -> list[list[dict[str, Any]]]:
    out: list[list[dict[str, Any]]] = []
    for slot in items:
        lane: list[dict[str, Any]] = []
        for item in slot:
            lane.append(
                {
                    "json": dict(item.json or {}),
                    "binary": {},
                    "meta": dict(item.meta or {}),
                    "paired_item": item.paired_item,
                }
            )
        out.append(lane)
    return out


def _trigger_dedupe_key(
    *,
    flow_id: str,
    trigger_node_id: str,
    tick_key: str | None,
    rule_index: int | None,
) -> str | None:
    if not tick_key:
        return None
    raw = f"{flow_id}:{trigger_node_id}:{tick_key}:{rule_index if rule_index is not None else 0}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


async def enqueue_scheduled_flow_run(
    analytiq_client,
    *,
    organization_id: str,
    flow_id: str,
    flow_revid: str,
    trigger_node_id: str,
    trigger_type: str,
    items: list[list["ad.flows.FlowItem"]],
    tick_key: str | None = None,
    rule_index: int | None = None,
) -> str:
    """
    Insert a queued ``flow_executions`` document and enqueue ``flow_run``.

    Returns the new execution id (or an existing one when ``dedupe_key`` matches).
    """

    serialized = _serialize_flow_items(items)
    dedupe_key = _trigger_dedupe_key(
        flow_id=flow_id,
        trigger_node_id=trigger_node_id,
        tick_key=tick_key,
        rule_index=rule_index,
    )

    trigger: dict[str, Any] = {
        "type": trigger_type,
        "node_id": trigger_node_id,
        "items": serialized,
        "tick_key": tick_key,
        "rule_index": rule_index,
    }
    if dedupe_key:
        trigger["dedupe_key"] = dedupe_key

    db = ad.common.get_async_db(analytiq_client)

    if dedupe_key:
        existing = await db.flow_executions.find_one({"trigger.dedupe_key": dedupe_key})
        if existing:
            return str(existing["_id"])

    exec_doc: dict[str, Any] = {
        "flow_id": flow_id,
        "flow_revid": flow_revid,
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
    }

    res = await db.flow_executions.insert_one(exec_doc)
    exec_id = str(res.inserted_id)

    await ad.queue.send_msg(
        analytiq_client,
        "flow_run",
        msg={
            "flow_id": flow_id,
            "flow_revid": flow_revid,
            "execution_id": exec_id,
            "organization_id": organization_id,
            "trigger": trigger,
        },
    )
    return exec_id
