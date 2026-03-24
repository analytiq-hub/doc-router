"""Tests for KB search → LLM context formatting (overlap merge)."""

from analytiq_data.kb.llm_context import (
    format_kb_search_results_for_llm,
    _merge_span_chunks_for_document,
)


def test_merge_two_overlapping_chunks():
    chunks = [
        {
            "indexed_text_start": 0,
            "indexed_text_end": 100,
            "content": "a" * 100,
            "chunk_index": 0,
        },
        {
            "indexed_text_start": 80,
            "indexed_text_end": 200,
            "content": "a" * 120,
            "chunk_index": 1,
        },
    ]
    merged = _merge_span_chunks_for_document(chunks)
    assert merged == "a" * 200


def test_merge_gap_inserts_separator():
    chunks = [
        {
            "indexed_text_start": 0,
            "indexed_text_end": 10,
            "content": "0123456789",
            "chunk_index": 0,
        },
        {
            "indexed_text_start": 20,
            "indexed_text_end": 25,
            "content": "abcde",
            "chunk_index": 1,
        },
    ]
    merged = _merge_span_chunks_for_document(chunks)
    assert merged == "0123456789\n\nabcde"


def test_format_groups_by_document_and_merges():
    results = [
        {
            "content": "x" * 50,
            "source": "Doc1.pdf",
            "document_id": "d1",
            "relevance": 0.5,
            "chunk_index": 0,
            "indexed_text_start": 0,
            "indexed_text_end": 50,
        },
        {
            "content": "x" * 30,
            "source": "Doc1.pdf",
            "document_id": "d1",
            "relevance": 0.4,
            "chunk_index": 1,
            "indexed_text_start": 40,
            "indexed_text_end": 70,
        },
    ]
    out = format_kb_search_results_for_llm(results)
    assert "Knowledge Base Search Results:" in out
    assert "Doc1.pdf" in out
    assert out.count("[1]") == 1
    # 50 x + 20 new x (overlap 10)
    assert "x" * 70 in out


def test_format_no_spans_passthrough():
    results = [
        {
            "content": "hello",
            "source": "A",
            "document_id": "d1",
            "relevance": 0.1,
            "chunk_index": 0,
        },
    ]
    out = format_kb_search_results_for_llm(results)
    assert "hello" in out
    assert "[1]" in out
