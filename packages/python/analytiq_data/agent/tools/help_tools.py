"""
Help tools: return guidance for creating schemas and prompts (callable tools).
Reads from docs/knowledge_base when available, otherwise returns embedded summary.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Try repo root: from packages/python/analytiq_data/agent/tools -> 6 levels up
def _knowledge_base_path(filename: str) -> Path | None:
    base = Path(__file__).resolve().parent
    for _ in range(6):
        base = base.parent
        candidate = base / "docs" / "knowledge_base" / filename
        if candidate.exists():
            return candidate
    return None


async def help_schemas(context: dict, params: dict) -> dict[str, Any]:
    """Returns detailed guidance on creating schemas (format, constraints, examples)."""
    path = _knowledge_base_path("schemas.md")
    if path:
        try:
            text = path.read_text(encoding="utf-8")
            # Cap size for LLM context (~8k chars is enough for key sections)
            if len(text) > 12000:
                text = text[:12000] + "\n\n[... truncated ...]"
            return {"content": text}
        except Exception as e:
            logger.warning("Could not read schemas.md: %s", e)
    return {
        "content": (
            "DocRouter Schema Guidelines:\n"
            "- Use OpenAI Structured Outputs JSON Schema format: type 'json_schema', json_schema.name, json_schema.schema (Draft 7).\n"
            "- Set json_schema.strict: true. All properties must be in 'required'; use additionalProperties: false at every level.\n"
            "- Field types: string, integer, number, boolean, array, object. Use 'description' for each property.\n"
            "- For missing data use empty string, zero, false, or empty array/object.\n"
            "- See full docs in docs/knowledge_base/schemas.md."
        )
    }


async def help_prompts(context: dict, params: dict) -> dict[str, Any]:
    """Returns detailed guidance on creating prompts (format, linking to schemas, model selection)."""
    path = _knowledge_base_path("prompts.md")
    if path:
        try:
            text = path.read_text(encoding="utf-8")
            if len(text) > 12000:
                text = text[:12000] + "\n\n[... truncated ...]"
            return {"content": text}
        except Exception as e:
            logger.warning("Could not read prompts.md: %s", e)
    return {
        "content": (
            "DocRouter Prompt Guidelines:\n"
            "- Prompt has: name, content (instruction text), optional schema_id/schema_version, optional model (default gpt-4o-mini), optional tag_ids.\n"
            "- Content should be clear and specific; reference schema fields when a schema is linked.\n"
            "- Linking a schema ensures structured output and validation.\n"
            "- See full docs in docs/knowledge_base/prompts.md."
        )
    }
