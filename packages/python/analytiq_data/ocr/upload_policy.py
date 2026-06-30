"""
Upload-time policy: whether to enqueue OCR, LLM, and/or KB indexing on document upload.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from bson import ObjectId

import analytiq_data as ad

OCR_REQUIRED_MESSAGE = "OCR required but not run for this document"

@dataclass(frozen=True)
class UploadPipelinePolicy:
    needs_ocr: bool
    needs_llm: bool
    needs_kb: bool


async def _org_default_prompt_enabled(db, org_id: str) -> bool:
    org = await db.organizations.find_one({"_id": ObjectId(org_id)}, {"default_prompt_enabled": 1})
    if org is None:
        return True
    return bool(org.get("default_prompt_enabled", True))


async def _any_matching_kb(db, org_id: str, tag_ids: list[str]) -> bool:
    if not tag_ids:
        return False
    row = await db.knowledge_bases.find_one(
        {
            "organization_id": org_id,
            "status": {"$in": ["indexing", "active"]},
            "tag_ids": {"$in": tag_ids},
        }
    )
    return row is not None


async def _any_tagged_prompt_exists(db, tag_ids: list[str]) -> bool:
    if not tag_ids:
        return False
    pipeline: list[dict[str, Any]] = [
        {"$match": {"tag_ids": {"$in": tag_ids}}},
        {"$sort": {"prompt_version": -1, "_id": -1}},
        {"$group": {"_id": "$prompt_id", "doc": {"$first": "$$ROOT"}}},
        {"$limit": 1},
        {"$project": {"_id": 1}},
    ]
    rows = await db.prompt_revisions.aggregate(pipeline).to_list(1)
    return bool(rows)


async def _any_tagged_prompt_needs_ocr_text(db, tag_ids: list[str]) -> bool:
    if not tag_ids:
        return False
    pipeline: list[dict[str, Any]] = [
        {"$match": {"tag_ids": {"$in": tag_ids}}},
        {"$sort": {"prompt_version": -1, "_id": -1}},
        {"$group": {"_id": "$prompt_id", "doc": {"$first": "$$ROOT"}}},
        {"$replaceRoot": {"newRoot": "$doc"}},
        {
            "$match": {
                "$or": [
                    {"include.ocr_text": True},
                    {"include.ocr_text": {"$exists": False}},
                    {"include": {"$exists": False}},
                ]
            }
        },
        {"$limit": 1},
        {"$project": {"_id": 1}},
    ]
    rows = await db.prompt_revisions.aggregate(pipeline).to_list(1)
    return bool(rows)


async def resolve_upload_pipeline_policy(
    analytiq_client,
    org_id: str,
    tag_ids: list[str],
    file_name: str,
    *,
    cache: dict[tuple[str, frozenset[str], bool], UploadPipelinePolicy] | None = None,
) -> UploadPipelinePolicy:
    """
    Decide which upload pipeline queues to enqueue for one document.

    ``cache`` is optional per-request dict keyed by ``(org_id, frozenset(tag_ids), ocr_supported)``.
    """
    ocr_sup = ad.common.doc.ocr_supported(file_name)
    key = (org_id, frozenset(tag_ids), ocr_sup)
    store: dict[tuple[str, frozenset[str], bool], UploadPipelinePolicy] = (
        {} if cache is None else cache
    )
    if key in store:
        return store[key]

    db = ad.common.get_async_db(analytiq_client)
    default_enabled = await _org_default_prompt_enabled(db, org_id)
    kb_match = await _any_matching_kb(db, org_id, tag_ids)
    tagged_prompts = await _any_tagged_prompt_exists(db, tag_ids)

    if not ocr_sup:
        policy = UploadPipelinePolicy(
            needs_ocr=False,
            needs_llm=default_enabled or tagged_prompts,
            needs_kb=kb_match,
        )
        store[key] = policy
        return policy

    needs_ocr = False
    if default_enabled:
        needs_ocr = True
    elif kb_match:
        needs_ocr = True
    elif await _any_tagged_prompt_needs_ocr_text(db, tag_ids):
        needs_ocr = True

    policy = UploadPipelinePolicy(
        needs_ocr=needs_ocr,
        needs_llm=default_enabled or tagged_prompts,
        needs_kb=kb_match,
    )
    store[key] = policy
    return policy


async def document_needs_upload_ocr(
    analytiq_client,
    org_id: str,
    tag_ids: list[str],
    file_name: str,
    *,
    cache: dict[tuple[str, frozenset[str], bool], UploadPipelinePolicy] | None = None,
) -> bool:
    policy = await resolve_upload_pipeline_policy(
        analytiq_client, org_id, tag_ids, file_name, cache=cache
    )
    return policy.needs_ocr


async def any_selected_prompt_needs_ocr_text(
    analytiq_client,
    prompt_revids: list[str],
) -> bool:
    for revid in prompt_revids:
        cfg = await ad.common.get_prompt_group_config(analytiq_client, revid)
        if cfg.get("include", {}).get("ocr_text", True):
            return True
    return False


async def ocr_available_for_document(
    analytiq_client,
    document_id: str,
    file_name: str,
) -> bool:
    if not ad.common.doc.ocr_supported(file_name):
        return True
    metadata = await ad.ocr.get_ocr_metadata(analytiq_client, document_id)
    return metadata is not None
