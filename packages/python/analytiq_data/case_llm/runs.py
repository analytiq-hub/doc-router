"""Case-scoped LLM runs (one prompt over all documents in a case)."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from bson import ObjectId

import analytiq_data as ad

logger = logging.getLogger(__name__)

CASE_LLM_MAX_DOCUMENTS = 50


def _case_llm_runs_coll(analytiq_client):
    db = analytiq_client.mongodb_async[analytiq_client.env]
    return db["case_llm_runs"]


def _doc_sort_key(d: dict) -> tuple:
    created_at = d.get("upload_date") or d.get("created_at")
    if not created_at and isinstance(d.get("_id"), ObjectId):
        created_at = d["_id"].generation_time
    return (created_at or datetime.min.replace(tzinfo=UTC), d.get("_id"))


async def list_case_member_docs(
    analytiq_client,
    organization_id: str,
    case_id: str,
) -> list[dict]:
    """All member documents sorted by upload date ascending (oldest first)."""
    db = analytiq_client.mongodb_async[analytiq_client.env]
    cursor = db.docs.find(
        {"organization_id": organization_id, "case_id": case_id},
    ).sort([("upload_date", 1), ("_id", 1)])
    return await cursor.to_list(length=None)


async def list_case_documents_for_llm(
    analytiq_client,
    organization_id: str,
    case_id: str,
) -> list[dict]:
    """Member documents for a case LLM run (max ``CASE_LLM_MAX_DOCUMENTS``)."""
    docs = await list_case_member_docs(analytiq_client, organization_id, case_id)
    if len(docs) > CASE_LLM_MAX_DOCUMENTS:
        raise ValueError(
            f"Case has more than {CASE_LLM_MAX_DOCUMENTS} documents; "
            "narrow membership before running a case prompt"
        )
    return docs


async def resolve_latest_prompt_revid(analytiq_client, organization_id: str, prompt_id: str) -> dict:
    db = analytiq_client.mongodb_async[analytiq_client.env]
    prompt = await db.prompts.find_one(
        {"_id": ObjectId(prompt_id), "organization_id": organization_id},
    )
    if not prompt:
        raise LookupError("prompt_not_found")
    rev = await db.prompt_revisions.find_one(
        {"prompt_id": prompt_id},
        sort=[("prompt_version", -1)],
    )
    if not rev:
        raise LookupError("prompt_not_found")
    return rev


def _prompt_shares_case_tag(case: dict, prompt_revision: dict) -> bool:
    case_tags = set(case.get("tag_ids") or [])
    if not case_tags:
        return False
    prompt_tags = set(prompt_revision.get("tag_ids") or [])
    return bool(case_tags & prompt_tags)


async def enqueue_case_llm_run(
    analytiq_client,
    organization_id: str,
    case_id: str,
    prompt_id: str,
) -> str:
    """Validate and enqueue a case LLM job. Returns queue message id."""
    case = await ad.common.get_case(analytiq_client, organization_id, case_id)
    if not case:
        raise LookupError("case_not_found")
    if case.get("deleting_at"):
        raise LookupError("case_deleting")

    rev = await resolve_latest_prompt_revid(analytiq_client, organization_id, prompt_id)
    case_tags = case.get("tag_ids") or []
    if not case_tags:
        raise LookupError("case_has_no_tags")
    if not _prompt_shares_case_tag(case, rev):
        raise LookupError("prompt_tag_mismatch")
    docs = await list_case_documents_for_llm(analytiq_client, organization_id, case_id)
    if not docs:
        raise ValueError("Case has no documents")

    msg_id = await ad.queue.send_msg(
        analytiq_client,
        "case_llm",
        {
            "organization_id": organization_id,
            "case_id": case_id,
            "prompt_id": prompt_id,
        },
    )
    return msg_id


async def run_case_llm_from_queue(
    analytiq_client,
    organization_id: str,
    case_id: str,
    prompt_id: str,
) -> None:
    """Worker entry: run latest prompt revision over case documents."""
    rev = await resolve_latest_prompt_revid(analytiq_client, organization_id, prompt_id)
    prompt_revid = str(rev["_id"])

    docs = await list_case_documents_for_llm(analytiq_client, organization_id, case_id)
    if not docs:
        raise ValueError(f"Case {case_id} has no documents for LLM run")

    document_ids = [str(d["_id"]) for d in docs]
    primary_id = document_ids[0]

    if await ad.ocr.any_selected_prompt_needs_ocr_text(analytiq_client, [prompt_revid]):
        for d in docs:
            doc_id = str(d["_id"])
            file_name = d.get("user_file_name", "")
            if not await ad.ocr.ocr_available_for_document(analytiq_client, doc_id, file_name):
                raise RuntimeError(ad.ocr.OCR_REQUIRED_MESSAGE)

    await ad.llm.run_llm(
        analytiq_client,
        document_id=primary_id,
        prompt_revid=prompt_revid,
        force=True,
        ordered_documents=docs,
        case_persist={
            "organization_id": organization_id,
            "case_id": case_id,
            "prompt_id": prompt_id,
            "document_ids": document_ids,
        },
    )


async def save_case_llm_run(
    analytiq_client,
    *,
    organization_id: str,
    case_id: str,
    prompt_id: str,
    prompt_revid: str,
    prompt_version: int,
    document_ids: list[str],
    llm_result: dict,
    run: dict | None,
    status: str,
    error_message: str | None = None,
) -> str:
    coll = _case_llm_runs_coll(analytiq_client)
    now = datetime.now(UTC)
    element: dict[str, Any] = {
        "organization_id": organization_id,
        "case_id": case_id,
        "prompt_id": prompt_id,
        "prompt_revid": prompt_revid,
        "prompt_version": prompt_version,
        "document_ids": document_ids,
        "llm_result": llm_result,
        "status": status,
        "created_at": now,
        "updated_at": now,
    }
    if run is not None:
        element["run"] = run
    if error_message:
        element["error_message"] = error_message

    result = await coll.insert_one(element)
    run_id = str(result.inserted_id)
    logger.info(
        f"Saved case LLM run {run_id} org={organization_id} case={case_id} "
        f"prompt_id={prompt_id} status={status} docs={len(document_ids)}"
    )
    return run_id


async def get_latest_case_llm_run(
    analytiq_client,
    organization_id: str,
    case_id: str,
    prompt_id: str,
) -> dict | None:
    coll = _case_llm_runs_coll(analytiq_client)
    return await coll.find_one(
        {
            "organization_id": organization_id,
            "case_id": case_id,
            "prompt_id": prompt_id,
            "status": "completed",
        },
        sort=[("created_at", -1)],
    )


async def delete_case_llm_runs(
    analytiq_client,
    organization_id: str,
    case_id: str,
) -> int:
    coll = _case_llm_runs_coll(analytiq_client)
    result = await coll.delete_many({"organization_id": organization_id, "case_id": case_id})
    return result.deleted_count


def compute_case_run_stale(
    run: dict | None,
    *,
    current_document_ids: list[str],
    latest_prompt_revid: str,
    member_docs: list[dict],
) -> tuple[bool, list[str]]:
    if run is None:
        return True, ["no_completed_run"]
    reasons: list[str] = []
    run_ids = sorted(run.get("document_ids") or [])
    current_ids = sorted(current_document_ids)
    if run_ids != current_ids:
        reasons.append("membership")
    if run.get("prompt_revid") != latest_prompt_revid:
        reasons.append("prompt_revision")
    run_created = run.get("created_at")
    if run_created is not None:
        for d in member_docs:
            updated = d.get("updated_at")
            if updated and updated > run_created:
                reasons.append("document_updated")
                break
    return (len(reasons) > 0, reasons)


async def build_case_results_payload(
    analytiq_client,
    organization_id: str,
    case_id: str,
    prompt_id: str,
) -> dict[str, Any]:
    rev = await resolve_latest_prompt_revid(analytiq_client, organization_id, prompt_id)
    latest_revid = str(rev["_id"])

    member_docs = await list_case_member_docs(analytiq_client, organization_id, case_id)
    current_document_ids = [str(d["_id"]) for d in member_docs]

    latest_run = await get_latest_case_llm_run(
        analytiq_client, organization_id, case_id, prompt_id
    )
    stale, stale_reasons = compute_case_run_stale(
        latest_run,
        current_document_ids=current_document_ids,
        latest_prompt_revid=latest_revid,
        member_docs=member_docs,
    )

    case_run_out = None
    if latest_run:
        case_run_out = {
            "run_id": str(latest_run["_id"]),
            "prompt_revid": latest_run.get("prompt_revid"),
            "prompt_version": latest_run.get("prompt_version"),
            "document_ids": latest_run.get("document_ids") or [],
            "llm_result": latest_run.get("llm_result"),
            "created_at": latest_run.get("created_at"),
            "status": latest_run.get("status"),
            "run": latest_run.get("run"),
        }

    return {
        "prompt_id": prompt_id,
        "latest_prompt_revid": latest_revid,
        "stale": stale,
        "stale_reasons": stale_reasons,
        "current_document_ids": current_document_ids,
        "case_run": case_run_out,
    }
