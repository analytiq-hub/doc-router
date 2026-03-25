"""
Knowledge-base chunking preprocessing configuration and named presets.

Values are stored on the KB document and drive ``get_extracted_indexing_text`` /
``chunk_text`` — no document-specific regex literals in code.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Literal

from pydantic import BaseModel, Field, field_validator

ChunkingPresetName = Literal["plain", "structured_doc"]


class ChunkingPreprocessConfig(BaseModel):
    prefer_markdown: bool = Field(
        default=False,
        description="Use per-page OCR markdown linearization instead of plain get_text() when possible",
    )
    strip_page_numbers: bool = Field(
        default=False,
        description="Remove lines that are only digits (page numbers)",
    )
    strip_page_breaks: bool = Field(
        default=False,
        description=r"Replace \n---\n (ambiguous vs markdown rules) with paragraph breaks",
    )
    strip_patterns: List[str] = Field(
        default_factory=list,
        description="Extra regex patterns applied multiline to strip boilerplate",
    )
    heading_split_depth: int = Field(
        default=3,
        ge=1,
        le=6,
        description="Markdown heading levels (# through ### when 3) for recursive splits and breadcrumb depth",
    )
    prepend_heading_path: bool = Field(
        default=False,
        description="Prepend nearest heading breadcrumb to embedding input only (not chunk_text)",
    )

    @field_validator("strip_patterns")
    @classmethod
    def validate_strip_patterns_regex(cls, v: List[str]) -> List[str]:
        for pattern in v:
            if not pattern or not pattern.strip():
                continue
            try:
                re.compile(pattern)
            except re.error as e:
                raise ValueError(f"Invalid strip_patterns regex {pattern!r}: {e}") from e
        return v


def chunking_preprocess_for_preset(name: ChunkingPresetName) -> ChunkingPreprocessConfig:
    """Return baseline preprocessing for a named preset (user overrides via stored config)."""
    if name == "plain":
        return ChunkingPreprocessConfig(
            prefer_markdown=False,
            strip_page_numbers=False,
            strip_page_breaks=False,
            strip_patterns=[],
            heading_split_depth=3,
            prepend_heading_path=False,
        )
    if name == "structured_doc":
        return ChunkingPreprocessConfig(
            prefer_markdown=True,
            strip_page_numbers=True,
            strip_page_breaks=True,
            strip_patterns=[],
            heading_split_depth=3,
            prepend_heading_path=True,
        )
    raise ValueError(f"Unknown chunking preset: {name}")


def chunking_preprocess_from_kb_dict(kb: Dict[str, Any]) -> ChunkingPreprocessConfig:
    """
    Effective preprocessing for a MongoDB ``knowledge_bases`` document.

    Legacy KBs without ``chunking_preprocess`` use all-off defaults (prior behavior).
    """
    raw = kb.get("chunking_preprocess")
    if isinstance(raw, dict) and raw:
        return ChunkingPreprocessConfig.model_validate(raw)
    preset = kb.get("chunking_preset")
    if preset == "plain":
        return chunking_preprocess_for_preset("plain")
    if preset == "structured_doc":
        return chunking_preprocess_for_preset("structured_doc")
    return ChunkingPreprocessConfig()


def preprocess_markdown(text: str, cfg: ChunkingPreprocessConfig) -> str:
    """Apply configured stripping to markdown (or markdown-like) text."""
    if cfg.strip_page_breaks:
        text = re.sub(r"\n---\n", "\n\n", text)
    if cfg.strip_page_numbers:
        text = re.sub(r"^\d+\s*\n", "", text, flags=re.MULTILINE)
    for pattern in cfg.strip_patterns:
        if not pattern.strip():
            continue
        try:
            text = re.sub(pattern, "", text, flags=re.MULTILINE)
        except re.error as e:
            raise ValueError(f"Invalid strip_patterns regex {pattern!r}: {e}") from e
    return text
