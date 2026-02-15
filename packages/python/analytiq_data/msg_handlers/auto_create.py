"""
Auto-create handler: runs headless agent to propose schema, prompt, and extraction.
Triggered when document has auto_create_enabled and OCR completes.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, UTC
from bson import ObjectId

import analytiq_data as ad

from ..agent.agent_loop import run_agent_turn

logger = logging.getLogger(__name__)

AUTO_CREATE_INITIAL_MESSAGE = (
    "Analyze this document. Create a schema that captures the key, repeatable fields for documents like this "
    "— focus on fields that would be uniform across similar documents, not every detail. "
    "Then create a prompt for extracting those fields, and run the extraction."
)

MAX_AUTO_CREATE_ITERATIONS = 2
AUTO_CREATE_TIMEOUT_SECS = 120


async def process_auto_create_msg(analytiq_client, msg: dict) -> None:
    """
    Run headless agent to auto-create schema, prompt, and extraction.
    Stores results on document as 'proposed' for user review.
    """
    msg_id = msg.get("_id")
    document_id = msg.get("msg", {}).get("document_id")
    if not document_id:
        logger.error("Auto-create msg missing document_id")
        return

    doc = await ad.common.doc.get_doc(analytiq_client, document_id)
    if not doc:
        logger.error(f"Document {document_id} not found for auto-create")
        return

    org_id = doc.get("organization_id")
    if not org_id:
        logger.error(f"Document {document_id} missing organization_id")
        return

    # Only run if document has auto_create_enabled (set on upload)
    if not doc.get("auto_create_enabled"):
        logger.info(f"Document {document_id} does not have auto_create_enabled, skipping")
        return

    # Get a system user for created_by (headless run)
    db = ad.common.get_async_db(analytiq_client)
    org = await db.organizations.find_one({"_id": ObjectId(org_id)})
    created_by = "system"
    if org:
        members = org.get("members", [])
        if members:
            created_by = members[0].get("user_id", "system")

    messages = [{"role": "user", "content": AUTO_CREATE_INITIAL_MESSAGE}]
    agent_log: list[dict] = []

    try:
        result = await asyncio.wait_for(
            run_agent_turn(
                analytiq_client=analytiq_client,
                organization_id=org_id,
                document_id=document_id,
                user_id=created_by,
                messages=messages,
                model="claude-sonnet-4-20250514",
                auto_approve=True,
                resolved_mentions=None,
                working_state=None,
                auto_approved_tools=None,
                stream_handler=None,
            ),
            timeout=AUTO_CREATE_TIMEOUT_SECS,
        )
    except asyncio.TimeoutError:
        logger.error(f"Auto-create timed out for document {document_id}")
        await _set_auto_create_status(
            analytiq_client, document_id, "failed", error="Timeout after 120s"
        )
        return
    except Exception as e:
        logger.error(f"Auto-create failed for document {document_id}: {e}")
        await _set_auto_create_status(
            analytiq_client, document_id, "failed", error=str(e)
        )
        return

    if "error" in result:
        await _set_auto_create_status(
            analytiq_client, document_id, "failed", error=result["error"]
        )
        return

    working_state = result.get("working_state") or {}
    schema_revid = working_state.get("schema_revid")
    prompt_revid = working_state.get("prompt_revid")
    extraction = working_state.get("extraction")

    if not schema_revid or not prompt_revid or extraction is None:
        await _set_auto_create_status(
            analytiq_client,
            document_id,
            "failed",
            error="Agent did not produce schema, prompt, and extraction",
        )
        return

    agent_log.append({"role": "user", "content": AUTO_CREATE_INITIAL_MESSAGE})
    agent_log.append({
        "role": "assistant",
        "content": result.get("text", ""),
        "executed_rounds": result.get("executed_rounds"),
    })

    await ad.common.get_async_db(analytiq_client).documents.update_one(
        {"_id": ObjectId(document_id)},
        {
            "$set": {
                "auto_create_status": "proposed",
                "auto_create_schema_revid": schema_revid,
                "auto_create_prompt_revid": prompt_revid,
                "auto_create_done_at": datetime.now(UTC),
                "auto_create_agent_log": agent_log,
            }
        },
    )
    logger.info(f"Auto-create completed for document {document_id}: schema={schema_revid}, prompt={prompt_revid}")


async def _set_auto_create_status(
    analytiq_client, document_id: str, status: str, error: str | None = None
) -> None:
    """Set auto_create_status and optionally error on document."""
    update: dict = {"auto_create_status": status, "auto_create_done_at": datetime.now(UTC)}
    if error:
        update["auto_create_error"] = error
    await ad.common.get_async_db(analytiq_client).documents.update_one(
        {"_id": ObjectId(document_id)},
        {"$set": update},
    )
