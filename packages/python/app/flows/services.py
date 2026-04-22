from __future__ import annotations

"""
DocRouter flow service APIs (global functions).

These functions are the DocRouter-specific integration boundary used by flow
nodes (document fetch, OCR, LLM extraction, tagging, and runtime state).
"""

import logging
from datetime import datetime, UTC
from typing import Any

from bson import ObjectId

import analytiq_data as ad


logger = logging.getLogger(__name__)

async def get_document(analytiq_client, org_id: str, doc_id: str) -> dict:
    """Load a document and verify it belongs to `org_id`."""

    doc = await ad.common.doc.get_doc(analytiq_client, doc_id)
    if not doc:
        raise ValueError(f"Document not found: {doc_id}")
    if doc.get("organization_id") != org_id:
        raise ValueError("Document does not belong to organization")
    doc["_id"] = str(doc["_id"])
    return doc


async def run_ocr(analytiq_client, org_id: str, doc_id: str) -> dict:
    """
    Ensure OCR exists for the document and return a small status payload.

    Runs organization-configured OCR (Textract/Mistral/LLM/PyMuPDF) and persists
    OCR JSON + derived text using existing DocRouter helpers.
    """

    existing = await ad.ocr.get_ocr_json(analytiq_client, doc_id)
    if existing is not None:
        return {"document_id": doc_id, "ocr": "exists"}

    doc = await get_document(analytiq_client, org_id, doc_id)
    pdf_file_name = doc.get("pdf_file_name")
    if not pdf_file_name:
        raise ValueError("Document missing pdf_file_name")

    pdf_bytes = await ad.common.get_file_async(analytiq_client, pdf_file_name)
    if pdf_bytes is None:
        raise ValueError("PDF blob not found")

    cfg = await ad.ocr.ocr_config.fetch_org_ocr_config(analytiq_client, org_id)
    payload = await ad.ocr.ocr_runners.run_document_ocr(
        analytiq_client,
        pdf_bytes,
        org_id=org_id,
        document_id=doc_id,
        cfg=cfg,
    )

    metadata: dict[str, Any] = {"org_id": org_id, "ocr_type": cfg.mode}
    await ad.ocr.save_ocr_json(analytiq_client, doc_id, payload, metadata=metadata, encoding="json")
    await ad.ocr.save_ocr_text_from_json(
        analytiq_client,
        doc_id,
        payload,
        metadata=metadata,
        force=True,
        org_id=org_id,
        ocr_type=cfg.mode if cfg.mode != "mistral_vertex" else "mistral",
    )
    await ad.common.doc.update_doc_state(analytiq_client, doc_id, ad.common.doc.DOCUMENT_STATE_OCR_COMPLETED)
    return {"document_id": doc_id, "ocr": "completed", "mode": cfg.mode}


async def run_llm_extract(
    analytiq_client, org_id: str, doc_id: str, prompt_id: str, schema_id: str
) -> dict:
    """
    Run a prompt-based extraction for a document.

    Resolves the latest prompt revision for `prompt_id` and uses the existing LLM
    runner (`run_llm_for_prompt_revids`) to execute it.
    """

    db = ad.common.get_async_db(analytiq_client)
    pr = await db.prompt_revisions.find_one({"prompt_id": prompt_id}, sort=[("prompt_version", -1)])
    if not pr:
        raise ValueError(f"Prompt not found: {prompt_id}")
    prompt_revid = str(pr["_id"])

    if schema_id:
        sr = await db.schema_revisions.find_one({"schema_id": schema_id}, sort=[("schema_version", -1)])
        if not sr:
            raise ValueError(f"Schema not found: {schema_id}")

    results = await ad.llm.run_llm_for_prompt_revids(analytiq_client, doc_id, [prompt_revid], force=True)
    if not results:
        return {"document_id": doc_id, "prompt_id": prompt_id, "result": None}
    r0 = results[0]
    if isinstance(r0, Exception):
        raise r0
    return {"document_id": doc_id, "prompt_id": prompt_id, "result": r0}


async def set_tags(analytiq_client, org_id: str, doc_id: str, tags: list[str]) -> None:
    """Replace the document tag list after validating tag ids belong to `org_id`."""

    db = ad.common.get_async_db(analytiq_client)
    if tags:
        existing = await db.tags.find(
            {"_id": {"$in": [ObjectId(t) for t in tags]}, "organization_id": org_id}
        ).to_list(length=None)
        if len(existing) != len(set(tags)):
            raise ValueError("One or more tag ids are invalid for organization")

    await db.docs.update_one(
        {"_id": ObjectId(doc_id), "organization_id": org_id},
        {"$set": {"tag_ids": list(tags), "updated_at": datetime.now(UTC)}},
    )


async def get_runtime_state(analytiq_client, flow_id: str, node_id: str) -> dict:
    """Fetch cross-run state for a `(flow_id, node_id)` pair (empty dict if missing)."""

    db = ad.common.get_async_db(analytiq_client)
    doc = await db.flow_runtime_state.find_one({"flow_id": flow_id, "node_id": node_id})
    return (doc or {}).get("data") or {}


async def set_runtime_state(analytiq_client, flow_id: str, node_id: str, data: dict) -> None:
    """Upsert cross-run state for a `(flow_id, node_id)` pair."""

    db = ad.common.get_async_db(analytiq_client)
    await db.flow_runtime_state.update_one(
        {"flow_id": flow_id, "node_id": node_id},
        {"$set": {"data": data, "updated_at": datetime.now(UTC)}},
        upsert=True,
    )

