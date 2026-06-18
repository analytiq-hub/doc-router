from __future__ import annotations

"""
DocRouter flow service APIs (global functions).

These functions are the DocRouter-specific integration boundary used by flow
nodes (document fetch, OCR, LLM extraction, tagging, and runtime state).
"""

import json
import logging
from collections import OrderedDict
from datetime import datetime, UTC
from typing import Any

import litellm
from bson import ObjectId

import analytiq_data as ad
from analytiq_data.llm.llm_output_utils import process_llm_resp_content
from analytiq_data.ocr.ocr_config import TEXTRACT_FEATURES


logger = logging.getLogger(__name__)

# Single source for flow OCR provider enum (manifest ``ocr.manifest.json`` must stay in sync).
OCR_PROVIDER_CHOICES = ("textract", "mistral", "pymupdf")
TEXTRACT_FEATURE_CHOICES = tuple(sorted(TEXTRACT_FEATURES))


def normalize_textract_feature_types(values: list[str] | None) -> list[str]:
    """Validate and de-duplicate Textract AnalyzeDocument feature types."""

    if not values:
        return []
    out: list[str] = []
    seen: set[str] = set()
    for raw in values:
        ft = (raw or "").strip()
        if not ft or ft in seen:
            continue
        if ft not in TEXTRACT_FEATURES:
            raise ValueError(f"Unsupported Textract feature type: {raw!r}")
        seen.add(ft)
        out.append(ft)
    return out


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


async def run_flow_ocr_on_pdf(
    analytiq_client,
    org_id: str,
    pdf_bytes: bytes,
    *,
    ocr_provider: str,
    execution_id: str,
    textract_feature_types: list[str] | None = None,
) -> tuple[dict[str, Any], list[str]]:
    """
    Run OCR on in-memory PDF bytes for a flow execution.

    Returns ``(ocr_json_payload, ocr_pages)`` without persisting to the document OCR store.
    ``execution_id`` is passed to OCR runners as the correlation label (logs / Textract metadata).
    Textract feature types and SPU billing follow the same rules as document OCR.
    """

    provider = (ocr_provider or "").strip()
    if provider not in OCR_PROVIDER_CHOICES:
        raise ValueError(f"Unsupported ocr_provider: {ocr_provider!r}")

    cfg = await ad.ocr.ocr_config.fetch_org_ocr_config(analytiq_client, org_id)
    cfg_updates: dict[str, Any] = {}
    if cfg.mode != provider:
        cfg_updates["mode"] = provider
    if provider == "textract":
        feats = normalize_textract_feature_types(textract_feature_types)
        cfg_updates["textract"] = cfg.textract.model_copy(update={"feature_types": feats})
    if cfg_updates:
        cfg = cfg.model_copy(update=cfg_updates)

    exec_id = (execution_id or "").strip()
    if not exec_id:
        raise ValueError("execution_id is required for flow OCR")
    payload = await ad.ocr.ocr_runners.run_document_ocr(
        analytiq_client,
        pdf_bytes,
        org_id=org_id,
        document_id=exec_id,
        cfg=cfg,
    )
    pages = ad.ocr.ocr_pages_plain_text_list(payload)
    return payload, pages


async def _resolve_latest_prompt_revision(analytiq_client, prompt_id: str) -> dict[str, Any]:
    """Return the latest ``prompt_revisions`` document for a logical ``prompt_id``."""

    db = ad.common.get_async_db(analytiq_client)
    pr = await db.prompt_revisions.find_one({"prompt_id": prompt_id}, sort=[("prompt_version", -1)])
    if not pr:
        raise ValueError(f"Prompt not found: {prompt_id}")
    return pr


def _build_flow_llm_messages(
    instruction: str,
    item_json: dict[str, Any],
    ocr_text: str | None,
) -> list[dict[str, Any]]:
    """Assemble chat messages for a flow-scoped LLM run."""

    parts = [
        "You are analyzing a flow item.",
        "",
        "Instruction:",
        instruction,
        "",
        "Flow item data:",
        json.dumps(item_json, indent=2, default=str),
    ]
    if ocr_text:
        parts.extend(["", "ocr_text:", ocr_text])
    user_content = "\n".join(parts)
    system_prompt = (
        "You are a helpful assistant that extracts document information into JSON format. "
        "Always respond with valid JSON only, no other text. "
        "Format your entire response as a JSON object."
    )
    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_content},
    ]


async def run_flow_llm_run(
    analytiq_client,
    org_id: str,
    *,
    prompt_id: str,
    item_json: dict[str, Any],
    ocr_pages: list[str] | None = None,
) -> dict[str, Any]:
    """
    Run a prompt against flow item JSON with optional OCR page text.

    Does not persist to ``llm_runs`` or read document OCR from storage.
    """

    pr = await _resolve_latest_prompt_revision(analytiq_client, prompt_id)
    prompt_revid = str(pr["_id"])
    instruction = await ad.common.get_prompt_content(analytiq_client, prompt_revid)

    ocr_text = "\n".join(ocr_pages) if ocr_pages else None
    messages = _build_flow_llm_messages(instruction, item_json, ocr_text)

    llm_model = await ad.llm.get_llm_model(analytiq_client, prompt_revid)
    if not ad.llm.is_chat_model(llm_model) and not ad.llm.is_supported_model(llm_model):
        llm_model = "gpt-4o-mini"

    llm_provider = ad.llm.get_llm_model_provider(llm_model)
    if llm_provider is None:
        llm_model = "gpt-4o-mini"
        llm_provider = "openai"

    api_key = await ad.llm.get_llm_key(analytiq_client, llm_provider)

    num_pages = len(ocr_pages) if ocr_pages else 1
    llm_min_spus = ad.payments.spu_llm_min_for_page_count(num_pages)
    await ad.payments.check_spu_limits(org_id, llm_min_spus)

    response_format: dict[str, Any] | None = None
    if litellm.supports_response_schema(model=llm_model):
        response_format = await ad.common.get_prompt_response_format(analytiq_client, prompt_revid)

    response = await ad.llm.agent_completion(
        analytiq_client,
        model=llm_model,
        messages=messages,
        api_key=api_key,
        response_format=response_format,
    )

    total_prompt_tokens = 0
    total_completion_tokens = 0
    total_cost = 0.0
    if hasattr(response, "usage") and response.usage:
        total_prompt_tokens = response.usage.prompt_tokens if hasattr(response.usage, "prompt_tokens") else 0
        total_completion_tokens = (
            response.usage.completion_tokens if hasattr(response.usage, "completion_tokens") else 0
        )
        total_cost = litellm.completion_cost(completion_response=response) if hasattr(response, "usage") else 0.0

    total_tokens = total_prompt_tokens + total_completion_tokens
    spus_to_charge = ad.payments.compute_spu_to_charge(total_cost, min_spu=llm_min_spus)
    await ad.payments.record_spu_usage(
        org_id,
        spus_to_charge,
        llm_provider=llm_provider,
        llm_model=llm_model,
        prompt_tokens=total_prompt_tokens,
        completion_tokens=total_completion_tokens,
        total_tokens=total_tokens,
        actual_cost=total_cost,
        operation="flow_llm",
    )

    resp_content = response.choices[0].message.content
    if resp_content is None:
        raise ValueError("LLM response has no content")

    resp_content1 = process_llm_resp_content(resp_content, llm_provider)
    try:
        resp_dict = json.loads(resp_content1)
    except json.JSONDecodeError as e:
        raise ValueError(f"LLM response was not valid JSON: {e}") from e

    if response_format and response_format.get("type") == "json_schema":
        schema = response_format["json_schema"]["schema"]
        ordered_properties = list(schema.get("properties", {}).keys())
        ordered_resp = OrderedDict()
        for key in ordered_properties:
            if key in resp_dict:
                ordered_resp[key] = resp_dict[key]
        for key in resp_dict:
            if key not in ordered_resp:
                ordered_resp[key] = resp_dict[key]
        resp_dict = dict(ordered_resp)

    return resp_dict


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
