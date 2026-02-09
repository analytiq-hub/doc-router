"""
Builds the system message for the document agent: document context, OCR excerpt,
resolved @ mentions, current extraction, and instructions.
"""
from __future__ import annotations

import json
import logging
from typing import Any

import analytiq_data as ad

logger = logging.getLogger(__name__)

# Approximate token cap for OCR excerpt (~4 chars per token)
OCR_EXCERPT_MAX_CHARS = 8000


def _truncate(s: str, max_chars: int) -> str:
    if len(s) <= max_chars:
        return s
    return s[: max_chars - 50] + "\n\n[... truncated for context ...]"


async def build_system_message(
    analytiq_client: Any,
    organization_id: str,
    document_id: str,
    working_state: dict[str, Any],
    resolved_mentions: list[dict[str, Any]] | None = None,
) -> str:
    """
    Build the system message for one agent turn.
    - Document context (name, type)
    - OCR text excerpt (capped)
    - Resolved @ mentions (full schema/prompt/tag content)
    - Current working extraction if any
    - Short instructions
    """
    parts = [
        "You are a document assistant with access to tools to manage schemas, prompts, tags, and to run or update extractions for the current document.",
        "When the user asks to create or modify a schema, use help_schemas first if needed, then create_schema or update_schema.",
        "When the user asks to create or modify a prompt, use help_prompts first if needed, then create_prompt or update_prompt. You can link a prompt to a schema and run extraction with run_extraction.",
        "Always run extraction after creating or updating a prompt if the user expects to see extracted data.",
        "",
        "## Current document",
    ]
    doc = await ad.common.doc.get_doc(analytiq_client, document_id)
    if doc:
        parts.append(f"- Document ID: {document_id}")
        parts.append(f"- File name: {doc.get('user_file_name', 'unknown')}")
    else:
        parts.append(f"- Document ID: {document_id} (metadata not found)")
    parts.append("")

    # OCR excerpt
    try:
        text = await ad.llm.get_extracted_text(analytiq_client, document_id)
        if text:
            parts.append("## Document text (OCR/content excerpt)")
            parts.append(_truncate(text, OCR_EXCERPT_MAX_CHARS))
        else:
            parts.append("## Document text")
            parts.append("(No extracted text available for this document.)")
    except Exception as e:
        logger.warning("Failed to get OCR text for system prompt: %s", e)
        parts.append("## Document text")
        parts.append("(Could not load document text.)")
    parts.append("")

    # Resolved mentions
    if resolved_mentions:
        parts.append("## Referenced artifacts (from @ mentions)")
        for m in resolved_mentions:
            kind = m.get("type", "unknown")
            name = m.get("name", "")
            content = m.get("content", "")
            parts.append(f"### [{kind}: {name}]")
            parts.append(content)
            parts.append("")
        parts.append("")

    # Current extraction in working state
    extraction = working_state.get("extraction")
    if extraction is not None:
        parts.append("## Current extraction result (from last run_extraction or update)")
        parts.append(json.dumps(extraction, indent=2))
        parts.append("")
    schema_revid = working_state.get("schema_revid")
    prompt_revid = working_state.get("prompt_revid")
    if schema_revid or prompt_revid:
        parts.append("## Working state")
        if schema_revid:
            parts.append(f"- Last schema_revid: {schema_revid}")
        if prompt_revid:
            parts.append(f"- Last prompt_revid: {prompt_revid}")
        parts.append("")

    parts.append("Use the available tools to fulfill the user's request. If the user approves a tool call, execute it and continue.")
    return "\n".join(parts)
