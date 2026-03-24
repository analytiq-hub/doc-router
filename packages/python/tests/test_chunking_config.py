"""Tests for ChunkingPreprocessConfig and presets."""

import pytest
from pydantic import ValidationError

from analytiq_data.kb.chunking_config import (
    ChunkingPreprocessConfig,
    chunking_preprocess_for_preset,
    chunking_preprocess_from_kb_dict,
    preprocess_markdown,
)


def test_preprocess_markdown_strip_breaks():
    cfg = ChunkingPreprocessConfig(strip_page_breaks=True)
    assert preprocess_markdown("a\n---\nb", cfg) == "a\n\nb"


def test_invalid_strip_pattern_raises():
    with pytest.raises(ValidationError, match="Invalid strip_patterns"):
        ChunkingPreprocessConfig(strip_patterns=["("])


def test_kb_dict_legacy_empty():
    cfg = chunking_preprocess_from_kb_dict({})
    assert cfg.prefer_markdown is False
    assert cfg.strip_patterns == []


def test_kb_dict_explicit_preprocess():
    cfg = chunking_preprocess_from_kb_dict(
        {"chunking_preprocess": {"prefer_markdown": True, "heading_split_depth": 2}}
    )
    assert cfg.prefer_markdown is True
    assert cfg.heading_split_depth == 2


def test_kb_dict_preset_plain():
    cfg = chunking_preprocess_from_kb_dict({"chunking_preset": "plain"})
    assert cfg.prefer_markdown is False


def test_unknown_preset_falls_back_to_empty_defaults():
    cfg = chunking_preprocess_from_kb_dict({"chunking_preset": "annual_report"})
    assert cfg.prefer_markdown is False
    assert cfg.strip_patterns == []
