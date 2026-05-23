from __future__ import annotations

"""Enqueue a scheduled/poll-triggered flow execution."""

import hashlib
from datetime import datetime, UTC
from typing import Any

from bson import ObjectId

import analytiq_data as ad


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


def _binary_ref_to_trigger_dict(ref: "ad.flows.BinaryRef") -> dict[str, Any]:
    out: dict[str, Any] = {
        "mime_type": ref.mime_type,
        "file_name": ref.file_name,
        "storage_id": ref.storage_id,
    }
    if ref.file_size is not None:
        out["file_size"] = ref.file_size
    return out


async def serialize_flow_items_for_trigger(
    items: list[list["ad.flows.FlowItem"]],
    *,
    execution_id: str,
    trigger_node_id: str,
    analytiq_client: Any,
) -> list[list[dict[str, Any]]]:
    """
    Serialize poll/schedule trigger items for MongoDB + queue delivery.

    Inline ``BinaryRef.data`` is uploaded to GridFS ``flow_blobs`` under
    ``{execution_id}/trigger/{trigger_node_id}/…`` so attachments survive enqueue.
    """

    out: list[list[dict[str, Any]]] = []
    for slot_idx, slot in enumerate(items):
        lane: list[dict[str, Any]] = []
        for item_idx, item in enumerate(slot):
            binary_out: dict[str, Any] = {}
            for prop, raw_ref in (item.binary or {}).items():
                ref = (
                    raw_ref
                    if isinstance(raw_ref, ad.flows.BinaryRef)
                    else ad.flows.coerce_binary_ref(raw_ref)
                )
                if ref.data is not None and not ref.storage_id:
                    key = f"{execution_id}/trigger/{trigger_node_id}/{slot_idx}/{item_idx}/{prop}"
                    blob = bytes(ref.data) if not isinstance(ref.data, bytearray) else bytes(ref.data)
                    ref.file_size = len(blob)
                    await ad.mongodb.blob.save_blob_async(
                        analytiq_client,
                        bucket="flow_blobs",
                        key=key,
                        blob=blob,
                        metadata={
                            "mime_type": ref.mime_type,
                            "file_name": ref.file_name or "",
                            "file_size": ref.file_size,
                        },
                    )
                    ref.storage_id = f"flow_blobs:{key}"
                    ref.data = None
                elif ref.data is not None and ref.storage_id:
                    ref.data = None
                if ref.storage_id:
                    binary_out[prop] = _binary_ref_to_trigger_dict(ref)
            lane.append(
                {
                    "json": dict(item.json or {}),
                    "binary": binary_out,
                    "meta": dict(item.meta or {}),
                    "paired_item": item.paired_item,
                }
            )
        out.append(lane)
    return out


def _serialize_flow_items(items: list[list["ad.flows.FlowItem"]]) -> list[list[dict[str, Any]]]:
    """Legacy sync serializer (json/meta only). Prefer ``serialize_flow_items_for_trigger``."""

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

    dedupe_key = _trigger_dedupe_key(
        flow_id=flow_id,
        trigger_node_id=trigger_node_id,
        tick_key=tick_key,
        rule_index=rule_index,
    )

    db = ad.common.get_async_db(analytiq_client)

    if dedupe_key:
        existing = await db.flow_executions.find_one({"trigger.dedupe_key": dedupe_key})
        if existing:
            return str(existing["_id"])

    exec_oid = ObjectId()
    exec_id = str(exec_oid)

    serialized = await serialize_flow_items_for_trigger(
        items,
        execution_id=exec_id,
        trigger_node_id=trigger_node_id,
        analytiq_client=analytiq_client,
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

    exec_doc: dict[str, Any] = {
        "_id": exec_oid,
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

    await db.flow_executions.insert_one(exec_doc)

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
