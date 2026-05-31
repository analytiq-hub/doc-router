"""
Bulk analysis of which document-prompt pairs need LLM execution.
"""

from __future__ import annotations

import logging
from typing import Any, Literal

from analytiq_data.common.doc import list_all_matching_docs
from analytiq_data.common.prompt_list import list_prompts_for_org

logger = logging.getLogger(__name__)

ExecutionMode = Literal["all", "missing", "outdated"]

_PROMPT_PAGE_SIZE = 100


async def _list_latest_prompts_for_tag(
    db: Any,
    organization_id: str,
    tag_id: str,
) -> list[dict[str, Any]]:
    """Return latest revision per prompt_id for prompts tagged with tag_id."""
    all_prompts: list[dict[str, Any]] = []
    skip = 0

    while True:
        prompts, _total = await list_prompts_for_org(
            db,
            organization_id,
            skip=skip,
            limit=_PROMPT_PAGE_SIZE,
            name_search=None,
            tag_ids_param=[tag_id],
            sort_model=None,
            filter_model=None,
        )
        if not prompts:
            break
        all_prompts.extend(prompts)
        if len(prompts) < _PROMPT_PAGE_SIZE:
            break
        skip += _PROMPT_PAGE_SIZE

    return all_prompts


async def _fetch_max_result_versions(
    db: Any,
    document_ids: list[str],
    prompt_ids: list[str],
) -> dict[tuple[str, str], int]:
    """Map (document_id, prompt_id) -> highest stored prompt_version."""
    if not document_ids or not prompt_ids:
        return {}

    pipeline = [
        {
            "$match": {
                "document_id": {"$in": document_ids},
                "prompt_id": {"$in": prompt_ids},
            }
        },
        {"$sort": {"prompt_version": -1}},
        {
            "$group": {
                "_id": {"document_id": "$document_id", "prompt_id": "$prompt_id"},
                "max_version": {"$first": "$prompt_version"},
            }
        },
    ]
    rows = await db.llm_runs.aggregate(pipeline).to_list(None)
    result: dict[tuple[str, str], int] = {}
    for row in rows:
        key = (row["_id"]["document_id"], row["_id"]["prompt_id"])
        result[key] = int(row["max_version"])
    return result


def _needs_execution(
    mode: ExecutionMode,
    latest_prompt_version: int,
    existing_version: int | None,
) -> bool:
    if mode == "all":
        return True
    if existing_version is None:
        return True
    if mode == "missing":
        return False
    # outdated
    return existing_version < latest_prompt_version


async def bulk_analyze_executions(
    analytiq_client,
    organization_id: str,
    tag_id: str,
    mode: ExecutionMode,
    *,
    tag_ids: list[str] | None = None,
    name_search: str | None = None,
    metadata_search: dict[str, str] | None = None,
    filter_model: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Determine which document-prompt pairs need LLM execution for bulk run.

    Returns:
        {
            "total_executions": int,
            "groups": [
                {
                    "prompt_revid": str,
                    "prompt_id": str,
                    "prompt_version": int,
                    "name": str,
                    "executions": [{"document_id": str, "document_name": str}, ...],
                },
                ...
            ],
        }
    """
    db_name = analytiq_client.env
    db = analytiq_client.mongodb_async[db_name]

    latest_prompts = await _list_latest_prompts_for_tag(db, organization_id, tag_id)
    if not latest_prompts:
        return {"total_executions": 0, "groups": []}

    doc_tag_ids = list(tag_ids or [])
    if tag_id not in doc_tag_ids:
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
        return {"total_executions": 0, "groups": []}

    doc_ids = [d["id"] for d in documents]
    doc_name_by_id = {d["id"]: d["document_name"] for d in documents}
    prompt_ids = [str(p["prompt_id"]) for p in latest_prompts]

    existing_versions: dict[tuple[str, str], int] = {}
    if mode != "all":
        existing_versions = await _fetch_max_result_versions(db, doc_ids, prompt_ids)

    groups: list[dict[str, Any]] = []
    total_executions = 0

    for prompt in latest_prompts:
        prompt_id = str(prompt["prompt_id"])
        prompt_revid = str(prompt["prompt_revid"])
        prompt_version = int(prompt.get("prompt_version") or 1)
        prompt_name = prompt.get("name") or "Unknown"

        executions: list[dict[str, str]] = []
        for doc_id in doc_ids:
            existing = existing_versions.get((doc_id, prompt_id))
            if _needs_execution(mode, prompt_version, existing):
                executions.append({
                    "document_id": doc_id,
                    "document_name": doc_name_by_id.get(doc_id, ""),
                })

        if executions:
            groups.append({
                "prompt_revid": prompt_revid,
                "prompt_id": prompt_id,
                "prompt_version": prompt_version,
                "name": prompt_name,
                "executions": executions,
            })
            total_executions += len(executions)

    logger.info(
        f"bulk_analyze_executions(): org={organization_id} tag={tag_id} mode={mode} "
        f"docs={len(documents)} prompts={len(latest_prompts)} executions={total_executions}"
    )

    return {"total_executions": total_executions, "groups": groups}
