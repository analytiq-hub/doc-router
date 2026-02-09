"""
Document and extraction tools for the agent: OCR text, run extraction, get/update result.
All operate on the current document from context.
"""
from __future__ import annotations

import logging
from typing import Any

import analytiq_data as ad

logger = logging.getLogger(__name__)


def _get_working_state(context: dict) -> dict:
    """Return mutable working_state from context."""
    if "working_state" not in context:
        context["working_state"] = {
            "schema_revid": None,
            "prompt_revid": None,
            "extraction": None,
        }
    return context["working_state"]


async def get_ocr_text(context: dict, params: dict) -> dict[str, Any]:
    """
    Returns OCR text for the current document. Optionally for a specific page (1-based).
    """
    document_id = context.get("document_id")
    if not document_id:
        return {"error": "No document context"}
    page_num = params.get("page_num")
    page_idx = (int(page_num) - 1) if page_num is not None else None
    try:
        text = await ad.common.ocr.get_ocr_text(
            context["analytiq_client"], document_id, page_idx=page_idx
        )
        if text is None:
            return {"error": "OCR text not available for this document"}
        return {"text": text}
    except Exception as e:
        logger.exception("get_ocr_text failed")
        return {"error": str(e)}


async def run_extraction(context: dict, params: dict) -> dict[str, Any]:
    """
    Runs LLM extraction on the current document with the given prompt_revid.
    If prompt_revid is omitted, uses the most recent prompt from working state (or default).
    Updates working_state.prompt_revid and working_state.extraction.
    """
    document_id = context.get("document_id")
    if not document_id:
        return {"error": "No document context"}
    prompt_revid = params.get("prompt_revid")
    working_state = _get_working_state(context)
    if not prompt_revid:
        prompt_revid = working_state.get("prompt_revid") or "default"
    try:
        result = await ad.llm.run_llm(
            context["analytiq_client"],
            document_id=document_id,
            prompt_revid=prompt_revid,
            force=True,
        )
        working_state["prompt_revid"] = prompt_revid
        working_state["extraction"] = result
        return {"prompt_revid": prompt_revid, "extraction": result}
    except Exception as e:
        logger.exception("run_extraction failed")
        return {"error": str(e)}


async def get_extraction_result(context: dict, params: dict) -> dict[str, Any]:
    """
    Returns the current extraction result for the document.
    Uses working_state.extraction if set, otherwise fetches from DB for prompt_revid (or default).
    """
    document_id = context.get("document_id")
    if not document_id:
        return {"error": "No document context"}
    working_state = _get_working_state(context)
    prompt_revid = params.get("prompt_revid") or working_state.get("prompt_revid") or "default"
    if working_state.get("extraction") is not None and working_state.get("prompt_revid") == prompt_revid:
        return {"extraction": working_state["extraction"], "prompt_revid": prompt_revid}
    try:
        row = await ad.llm.get_llm_result(
            context["analytiq_client"], document_id, prompt_revid, fallback=True
        )
        if not row:
            return {"error": f"No extraction result for prompt_revid={prompt_revid}"}
        extraction = row.get("updated_llm_result") or row.get("llm_result") or {}
        return {"extraction": extraction, "prompt_revid": prompt_revid}
    except Exception as e:
        logger.exception("get_extraction_result failed")
        return {"error": str(e)}


def _set_nested(d: dict, path: str, value: Any) -> None:
    """Set d[path] where path is dot-separated (e.g. 'a.b.0'). Creates dicts/lists as needed."""
    if not path.strip():
        return
    parts = path.split(".")
    current = d
    for i, key in enumerate(parts[:-1]):
        if key.isdigit():
            idx = int(key)
            if not isinstance(current, list):
                raise ValueError(f"Path {path}: expected list at '{key}'")
            while len(current) <= idx:
                current.append(None)
            current = current[idx]
        else:
            if key not in current:
                # Next part might be numeric => list
                next_key = parts[i + 1] if i + 1 < len(parts) else None
                current[key] = [] if next_key and next_key.isdigit() else {}
            current = current[key]
    last = parts[-1]
    if last.isdigit():
        idx = int(last)
        if not isinstance(current, list):
            raise ValueError(f"Path {path}: cannot index non-list with {idx}")
        while len(current) <= idx:
            current.append(None)
        current[idx] = value
    else:
        current[last] = value


async def update_extraction_field(context: dict, params: dict) -> dict[str, Any]:
    """
    Patches a single field in the current extraction result. path is dot-separated (e.g. 'invoice_total' or 'line_items.0.amount').
    Updates both working_state and DB.
    """
    document_id = context.get("document_id")
    if not document_id:
        return {"error": "No document context"}
    path = params.get("path")
    value = params.get("value")
    if path is None:
        return {"error": "path is required"}
    working_state = _get_working_state(context)
    prompt_revid = working_state.get("prompt_revid") or "default"
    # Get current full result
    row = await ad.llm.get_llm_result(
        context["analytiq_client"], document_id, prompt_revid, fallback=False
    )
    if not row:
        return {"error": "No extraction result to update"}
    current = row.get("updated_llm_result") or row.get("llm_result") or {}
    if not isinstance(current, dict):
        return {"error": "Extraction result is not an object"}
    try:
        _set_nested(current, path, value)
    except (ValueError, KeyError, IndexError) as e:
        return {"error": f"Invalid path or value: {e}"}
    try:
        await ad.llm.update_llm_result(
            context["analytiq_client"],
            document_id=document_id,
            prompt_revid=prompt_revid,
            updated_llm_result=current,
            is_verified=False,
        )
    except ValueError as e:
        return {"error": str(e)}
    working_state["extraction"] = current
    return {"extraction": current, "prompt_revid": prompt_revid}
