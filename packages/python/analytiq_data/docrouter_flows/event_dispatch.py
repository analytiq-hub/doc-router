from __future__ import annotations

"""Dispatch document lifecycle events to active ``docrouter.trigger`` flows."""

import logging
from datetime import UTC, datetime
from typing import Any

from bson import ObjectId

import analytiq_data as ad

from .document_binary import document_binary_refs, mime_for_storage_key
from .event_types import DOCROUTER_EVENT_TYPES, DOCROUTER_LLM_EVENT_TYPES
from analytiq_data.flows.triggers.enqueue import serialize_flow_items_for_trigger


logger = logging.getLogger(__name__)

FLOW_TRIGGERS_COLLECTION = "flow_triggers"
DOCROUTER_TRIGGER_TYPE = "docrouter.trigger"
DOCROUTER_EVENT_TRIGGER_KIND = "docrouter.event"


def _iso_datetime(value: Any) -> str:
    if isinstance(value, datetime):
        dt = value if value.tzinfo is not None else value.replace(tzinfo=UTC)
        return dt.astimezone(UTC).isoformat()
    return str(value) if value is not None else ""


def _metadata_str_map(raw: Any) -> dict[str, str]:
    if not isinstance(raw, dict):
        return {}
    out: dict[str, str] = {}
    for k, v in raw.items():
        if isinstance(k, str):
            out[k] = "" if v is None else str(v)
    return out


async def ensure_docrouter_flow_trigger_indexes(db) -> None:
    await db[FLOW_TRIGGERS_COLLECTION].create_index(
        [("flow_id", 1), ("trigger_node_id", 1)],
        unique=True,
        name="flow_triggers_flow_node_unique",
    )
    await db[FLOW_TRIGGERS_COLLECTION].create_index(
        [("org_id", 1), ("trigger_type", 1)],
        name="flow_triggers_org_trigger_type",
    )


async def delete_docrouter_flow_triggers(db, *, flow_id: str) -> None:
    await db[FLOW_TRIGGERS_COLLECTION].delete_many({"flow_id": flow_id})


def validate_docrouter_trigger_params(revision: dict[str, Any]) -> None:
    """Validate ``docrouter.trigger`` node parameters without writing ``flow_triggers`` rows."""

    for node in revision.get("nodes") or []:
        if node.get("disabled"):
            continue
        if (node.get("type") or "") != DOCROUTER_TRIGGER_TYPE:
            continue
        params = node.get("parameters") or {}
        event_type = params.get("event_type")
        if event_type not in DOCROUTER_EVENT_TYPES:
            raise ad.flows.FlowValidationError(
                f"DocRouter trigger {ad.flows.node_name(node)}: invalid event_type {event_type!r}"
            )
        try:
            nt = ad.flows.get(DOCROUTER_TRIGGER_TYPE)
            extra = nt.validate_parameters(params)
        except KeyError:
            extra = []
        if extra:
            raise ad.flows.FlowValidationError(
                f"DocRouter trigger {ad.flows.node_name(node)}: {'; '.join(extra)}"
            )


async def sync_docrouter_flow_triggers(
    db,
    *,
    org_id: str,
    flow_id: str,
    flow_revid: str,
    revision: dict[str, Any],
) -> None:
    """Replace ``flow_triggers`` rows for ``docrouter.trigger`` nodes on this flow."""

    validate_docrouter_trigger_params(revision)
    await delete_docrouter_flow_triggers(db, flow_id=flow_id)
    now = datetime.now(UTC)
    for node in revision.get("nodes") or []:
        if node.get("disabled"):
            continue
        if (node.get("type") or "") != DOCROUTER_TRIGGER_TYPE:
            continue
        params = node.get("parameters") or {}
        event_type = params.get("event_type")
        tag_id = params.get("tag_id")
        prompt_id = params.get("prompt_id")
        doc: dict[str, Any] = {
            "org_id": org_id,
            "flow_id": flow_id,
            "flow_revid": flow_revid,
            "trigger_node_id": node["id"],
            "trigger_type": event_type,
            "tag_id": tag_id.strip() if isinstance(tag_id, str) and tag_id.strip() else "",
            "include_retagged": bool(params.get("include_retagged")),
            "prompt_id": prompt_id.strip() if isinstance(prompt_id, str) and prompt_id.strip() else "",
            "updated_at": now,
        }
        await db[FLOW_TRIGGERS_COLLECTION].update_one(
            {"flow_id": flow_id, "trigger_node_id": node["id"]},
            {"$set": doc, "$setOnInsert": {"created_at": now}},
            upsert=True,
        )


def _evaluate_trigger_row(
    row: dict[str, Any],
    *,
    event_type: str,
    doc: dict[str, Any],
    was_retagged: bool,
    prompt_id: str | None,
) -> tuple[bool, str | None]:
    """Return ``(matches, matched_tag_id)`` for a ``flow_triggers`` row."""

    if event_type == "document.uploaded" and was_retagged and not row.get("include_retagged"):
        return False, None

    configured_tag = row.get("tag_id")
    matched_tag_id: str | None = None
    if isinstance(configured_tag, str) and configured_tag.strip():
        tag_ids = doc.get("tag_ids") or []
        if not isinstance(tag_ids, list) or configured_tag not in {str(t) for t in tag_ids}:
            return False, None
        matched_tag_id = configured_tag

    if event_type in DOCROUTER_LLM_EVENT_TYPES:
        configured_prompt = row.get("prompt_id")
        if isinstance(configured_prompt, str) and configured_prompt.strip():
            if (prompt_id or "").strip() != configured_prompt.strip():
                return False, None

    return True, matched_tag_id


async def build_docrouter_event_payload(
    analytiq_client,
    *,
    event_type: str,
    doc: dict[str, Any],
    matched_tag_id: str | None = None,
    was_retagged: bool = False,
    prompt_id: str | None = None,
    prompt_revid: str | None = None,
    llm_run_id: str | None = None,
    trigger_llm_result: Any = None,
    error_message: str | None = None,
    error_code: str | None = None,
) -> dict[str, Any]:
    doc_id = str(doc.get("_id") or doc.get("document_id") or "")
    user_file = doc.get("user_file_name")
    file_name = user_file if isinstance(user_file, str) else ""
    mime_type = mime_for_storage_key(file_name) if file_name else "application/octet-stream"

    payload: dict[str, Any] = {
        "event_type": event_type,
        "document_id": doc_id,
        "file_name": file_name,
        "mime_type": mime_type,
        "upload_date": _iso_datetime(doc.get("upload_date")),
        "tag_ids": [str(t) for t in (doc.get("tag_ids") or []) if t is not None],
        "metadata": _metadata_str_map(doc.get("metadata")),
        "matched_tag_id": matched_tag_id,
    }

    if event_type == "document.uploaded":
        payload["was_retagged"] = bool(was_retagged)
    if event_type in {"llm.completed", "llm.error"}:
        payload["prompt_id"] = prompt_id or ""
        payload["prompt_revid"] = prompt_revid or ""
    if event_type == "llm.completed":
        payload["llm_run_id"] = llm_run_id or ""
        payload["trigger_llm_result"] = trigger_llm_result
    if event_type in {"document.error", "llm.error"}:
        payload["error_message"] = error_message or ""
        payload["error_code"] = error_code

    return payload


def build_docrouter_event_flow_item(
    payload: dict[str, Any],
    doc: dict[str, Any],
    *,
    source_node_id: str,
) -> ad.flows.FlowItem:
    return ad.flows.FlowItem(
        json=dict(payload),
        binary=document_binary_refs(doc),
        meta={"source_node_id": source_node_id, "item_index": 0},
        paired_item=None,
    )


async def enqueue_docrouter_event_flow_run(
    analytiq_client,
    *,
    organization_id: str,
    flow_id: str,
    flow_revid: str,
    trigger_node_id: str,
    payload: dict[str, Any],
    item: ad.flows.FlowItem,
) -> str:
    exec_oid = ObjectId()
    exec_id = str(exec_oid)
    items = [[item]]
    serialized = await serialize_flow_items_for_trigger(
        items,
        execution_id=exec_id,
        trigger_node_id=trigger_node_id,
        analytiq_client=analytiq_client,
    )

    trigger: dict[str, Any] = {
        "type": DOCROUTER_EVENT_TRIGGER_KIND,
        "node_id": trigger_node_id,
        "items": serialized,
        **payload,
    }

    db = ad.common.get_async_db(analytiq_client)
    exec_doc: dict[str, Any] = {
        "_id": exec_oid,
        "flow_id": flow_id,
        "flow_revid": flow_revid,
        "organization_id": organization_id,
        "mode": "event",
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


async def dispatch_docrouter_event(
    analytiq_client,
    *,
    organization_id: str,
    event_type: str,
    document_id: str,
    was_retagged: bool = False,
    prompt_id: str | None = None,
    prompt_revid: str | None = None,
    llm_run_id: str | None = None,
    trigger_llm_result: Any = None,
    error_message: str | None = None,
    error_code: str | None = None,
) -> list[str]:
    """
    Match active ``flow_triggers`` rows and enqueue one ``flow_run`` per match.

    Returns execution ids enqueued (empty when no matches).
    """

    if event_type not in DOCROUTER_EVENT_TYPES:
        logger.warning(f"dispatch_docrouter_event: ignoring unknown event_type={event_type!r}")
        return []

    doc = await ad.common.doc.get_doc(analytiq_client, document_id)
    if not doc:
        logger.warning(f"dispatch_docrouter_event: document {document_id!r} not found")
        return []
    if doc.get("organization_id") != organization_id:
        logger.warning(
            f"dispatch_docrouter_event: document {document_id!r} org mismatch "
            f"(expected {organization_id!r}, got {doc.get('organization_id')!r})"
        )
        return []

    db = ad.common.get_async_db(analytiq_client)
    rows = await db[FLOW_TRIGGERS_COLLECTION].find(
        {"org_id": organization_id, "trigger_type": event_type}
    ).to_list(length=None)

    exec_ids: list[str] = []
    for row in rows:
        flow_id = row.get("flow_id")
        flow_revid = row.get("flow_revid")
        trigger_node_id = row.get("trigger_node_id")
        if not (isinstance(flow_id, str) and isinstance(flow_revid, str) and isinstance(trigger_node_id, str)):
            continue

        hdr = await db.flows.find_one(
            {"_id": ObjectId(flow_id), "organization_id": organization_id, "active": True}
        )
        if not hdr or str(hdr.get("active_flow_revid") or "") != flow_revid:
            logger.debug(
                f"dispatch_docrouter_event: skip flow_id={flow_id!r} "
                f"(active={bool(hdr)}, active_flow_revid={hdr.get('active_flow_revid') if hdr else None!r}, "
                f"row_flow_revid={flow_revid!r})"
            )
            continue

        matches, matched_tag_id = _evaluate_trigger_row(
            row,
            event_type=event_type,
            doc=doc,
            was_retagged=was_retagged,
            prompt_id=prompt_id,
        )
        if not matches:
            continue

        payload = await build_docrouter_event_payload(
            analytiq_client,
            event_type=event_type,
            doc=doc,
            matched_tag_id=matched_tag_id,
            was_retagged=was_retagged,
            prompt_id=prompt_id,
            prompt_revid=prompt_revid,
            llm_run_id=llm_run_id,
            trigger_llm_result=trigger_llm_result,
            error_message=error_message,
            error_code=error_code,
        )
        item = build_docrouter_event_flow_item(
            payload,
            doc,
            source_node_id=trigger_node_id,
        )
        exec_id = await enqueue_docrouter_event_flow_run(
            analytiq_client,
            organization_id=organization_id,
            flow_id=flow_id,
            flow_revid=flow_revid,
            trigger_node_id=trigger_node_id,
            payload=payload,
            item=item,
        )
        exec_ids.append(exec_id)

    return exec_ids


async def send_docrouter_event(
    analytiq_client,
    *,
    organization_id: str,
    event_type: str,
    document_id: str,
    **kwargs: Any,
) -> list[str]:
    """Best-effort dispatch from lifecycle hooks; logs and swallows errors."""

    try:
        return await dispatch_docrouter_event(
            analytiq_client,
            organization_id=organization_id,
            event_type=event_type,
            document_id=document_id,
            **kwargs,
        )
    except Exception as e:
        logger.warning(
            f"docrouter flow dispatch failed for event_type={event_type!r} document_id={document_id!r}: {e}"
        )
        return []


async def send_docrouter_error_event(
    analytiq_client,
    *,
    organization_id: str,
    event_type: str,
    document_id: str,
    error: dict | None = None,
    prompt_id: str | None = None,
    prompt_revid: str | None = None,
) -> list[str]:
    err = error if isinstance(error, dict) else {}
    stage = err.get("stage")
    message = err.get("message")
    return await send_docrouter_event(
        analytiq_client,
        organization_id=organization_id,
        event_type=event_type,
        document_id=document_id,
        prompt_id=prompt_id,
        prompt_revid=prompt_revid,
        error_message=str(message) if message is not None else "",
        error_code=str(stage) if isinstance(stage, str) else None,
    )
