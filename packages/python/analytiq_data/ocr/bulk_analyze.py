"""
Bulk analysis of which documents need OCR execution.
"""

from __future__ import annotations

import logging
from typing import Any, Literal

from bson import ObjectId

import analytiq_data as ad
from analytiq_data.common.doc import list_all_matching_docs
from analytiq_data.ocr.ocr_config import OrgOcrConfig, fetch_org_ocr_config, is_ocr_config_outdated

logger = logging.getLogger(__name__)

ExecutionMode = Literal["all", "missing", "outdated"]
OCR_BUCKET = "ocr"


async def batch_get_ocr_text_metadata(
    analytiq_client,
    document_ids: list[str],
) -> dict[str, dict[str, Any] | None]:
    """Map document_id -> GridFS metadata for ``{document_id}_text`` (or None)."""
    if not document_ids:
        return {}
    db = ad.common.get_async_db(analytiq_client)
    keys = [f"{doc_id}_text" for doc_id in document_ids]
    rows = await db[f"{OCR_BUCKET}.files"].find(
        {"filename": {"$in": keys}},
        {"filename": 1, "metadata": 1},
    ).to_list(length=None)
    by_filename = {
        str(row["filename"]): dict(row.get("metadata") or {})
        for row in rows
        if row.get("filename")
    }
    return {
        doc_id: by_filename.get(f"{doc_id}_text")
        for doc_id in document_ids
    }


def _needs_ocr_run(
    mode: ExecutionMode,
    *,
    has_ocr: bool,
    ocr_failed: bool,
    stored_metadata: dict[str, Any] | None,
    current_cfg: OrgOcrConfig,
) -> tuple[bool, str | None]:
    if mode == "all":
        return True, "forced"
    if ocr_failed or not has_ocr:
        return True, "missing"
    if mode == "missing":
        return False, None
    if is_ocr_config_outdated(stored_metadata, current_cfg):
        return True, "outdated"
    return False, None


async def bulk_analyze_ocr_executions(
    analytiq_client,
    organization_id: str,
    mode: ExecutionMode,
    *,
    tag_id: str | None = None,
    tag_ids: list[str] | None = None,
    name_search: str | None = None,
    metadata_search: dict[str, str] | None = None,
    filter_model: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Determine which documents need OCR for bulk run.

    Returns:
        {
            "total_executions": int,
            "executions": [
                {"document_id": str, "document_name": str, "reason": str | None},
                ...
            ],
        }
    """
    doc_tag_ids = list(tag_ids or [])
    if tag_id and tag_id not in doc_tag_ids:
        doc_tag_ids.append(tag_id)

    documents = await list_all_matching_docs(
        analytiq_client,
        organization_id,
        tag_ids=doc_tag_ids or None,
        name_search=name_search,
        metadata_search=metadata_search,
        filter_model=filter_model,
    )
    if not documents:
        return {"total_executions": 0, "executions": []}

    ocr_docs = [
        d for d in documents
        if ad.common.doc.ocr_supported(d.get("document_name") or "")
    ]
    if not ocr_docs:
        return {"total_executions": 0, "executions": []}

    doc_ids = [d["id"] for d in ocr_docs]
    doc_name_by_id = {d["id"]: d.get("document_name") or "" for d in ocr_docs}

    db = ad.common.get_async_db(analytiq_client)
    valid_ids = [ObjectId(doc_id) for doc_id in doc_ids if ObjectId.is_valid(doc_id)]
    state_rows = await db.docs.find(
        {"_id": {"$in": valid_ids}},
        {"state": 1},
    ).to_list(length=None)
    doc_state_by_id = {str(row["_id"]): row.get("state") or "" for row in state_rows}

    metadata_by_id = await batch_get_ocr_text_metadata(analytiq_client, doc_ids)
    current_cfg = await fetch_org_ocr_config(analytiq_client, organization_id)

    executions: list[dict[str, Any]] = []
    for doc_id in doc_ids:
        stored_meta = metadata_by_id.get(doc_id)
        has_ocr = stored_meta is not None
        ocr_failed = doc_state_by_id.get(doc_id) == ad.common.doc.DOCUMENT_STATE_OCR_FAILED
        include, reason = _needs_ocr_run(
            mode,
            has_ocr=has_ocr,
            ocr_failed=ocr_failed,
            stored_metadata=stored_meta,
            current_cfg=current_cfg,
        )
        if include:
            row: dict[str, Any] = {
                "document_id": doc_id,
                "document_name": doc_name_by_id.get(doc_id, ""),
            }
            if reason:
                row["reason"] = reason
            executions.append(row)

    logger.info(
        f"bulk_analyze_ocr_executions(): org={organization_id} mode={mode} "
        f"docs={len(ocr_docs)} executions={len(executions)}"
    )
    return {"total_executions": len(executions), "executions": executions}
