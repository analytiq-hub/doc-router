from __future__ import annotations

"""Persist DocRouter event-trigger flow outputs for the document Flows section."""

import logging
from datetime import UTC, datetime
from typing import Any

import analytiq_data as ad

from .event_dispatch import DOCROUTER_EVENT_TRIGGER_KIND, FLOW_TRIGGERS_COLLECTION


logger = logging.getLogger(__name__)

FLOW_RESULTS_COLLECTION = "flow_results"


async def ensure_flow_results_indexes(db) -> None:
    await db[FLOW_RESULTS_COLLECTION].create_index(
        [("document_id", 1), ("flow_id", 1)],
        unique=True,
        name="flow_results_doc_flow_unique",
    )
    await db[FLOW_RESULTS_COLLECTION].create_index(
        [("org_id", 1), ("document_id", 1)],
        name="flow_results_org_document",
    )
    await db[FLOW_RESULTS_COLLECTION].create_index(
        [("org_id", 1), ("flow_id", 1)],
        name="flow_results_org_flow",
    )


async def delete_flow_results_for_document(db, *, document_id: str) -> None:
    await db[FLOW_RESULTS_COLLECTION].delete_many({"document_id": document_id})


async def delete_flow_results_for_flow(db, *, flow_id: str) -> None:
    await db[FLOW_RESULTS_COLLECTION].delete_many({"flow_id": flow_id})


def _report_result_enabled(row: dict[str, Any] | None, trigger: dict[str, Any]) -> bool:
    if isinstance(trigger.get("report_result"), bool):
        return trigger["report_result"]
    if row is not None and isinstance(row.get("report_result"), bool):
        return row["report_result"]
    return True


async def maybe_capture_docrouter_flow_result(
    db,
    *,
    exec_doc: dict[str, Any],
    revision: dict[str, Any],
    run_data: dict[str, Any],
    status: str,
) -> None:
    """
    When a DocRouter event-triggered run succeeds with ``report_result`` enabled,
    upsert the last node's primary-output JSON into ``flow_results``.
    """

    if status != "success":
        return
    if (exec_doc.get("mode") or "") != "event":
        return

    trigger = exec_doc.get("trigger") or {}
    if not isinstance(trigger, dict) or trigger.get("type") != DOCROUTER_EVENT_TRIGGER_KIND:
        return

    document_id = trigger.get("document_id")
    if not isinstance(document_id, str) or not document_id.strip():
        return

    flow_id = exec_doc.get("flow_id")
    org_id = exec_doc.get("organization_id")
    exec_id = str(exec_doc.get("_id") or "")
    if not (isinstance(flow_id, str) and flow_id and isinstance(org_id, str) and org_id and exec_id):
        return

    start_trigger_node_id = exec_doc.get("start_trigger_node_id")
    trigger_node_id = start_trigger_node_id if isinstance(start_trigger_node_id, str) else None
    row = None
    if trigger_node_id:
        row = await db[FLOW_TRIGGERS_COLLECTION].find_one(
            {"flow_id": flow_id, "trigger_node_id": trigger_node_id}
        )
    if not _report_result_enabled(row, trigger):
        return

    result = ad.flows.extract_last_node_output_json(
        run_data,
        revision,
        start_trigger_node_id=trigger_node_id,
    )
    if result is None:
        result = {}

    now = datetime.now(UTC)
    await db[FLOW_RESULTS_COLLECTION].update_one(
        {"document_id": document_id, "flow_id": flow_id},
        {
            "$set": {
                "org_id": org_id,
                "execution_id": exec_id,
                "result": result,
                "updated_at": now,
            },
            "$setOnInsert": {"created_at": now},
        },
        upsert=True,
    )
    logger.info(
        f"Captured flow result for document_id={document_id} flow_id={flow_id} execution_id={exec_id}"
    )
