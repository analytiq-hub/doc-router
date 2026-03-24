"""
Format knowledge-base search hits for LLM tool context.

Merges overlapping indexed-text spans per document so chunk overlap is not duplicated.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional


def _has_indexed_spans(r: Dict[str, Any]) -> bool:
    s = r.get("indexed_text_start")
    e = r.get("indexed_text_end")
    return s is not None and e is not None and isinstance(s, int) and isinstance(e, int) and e > s


def _merge_span_chunks_for_document(chunks: List[Dict[str, Any]]) -> str:
    """
    Merge chunk texts using [start, end) offsets in the shared indexed document string.
    When chunk text length matches span length, skip overlap via index arithmetic; otherwise
    use proportional skip as a fallback.
    """
    if not chunks:
        return ""
    ordered = sorted(
        chunks,
        key=lambda r: (r.get("indexed_text_start", 0), r.get("chunk_index", 0)),
    )
    coverage_end: Optional[int] = None
    parts: List[str] = []

    for r in ordered:
        start = r["indexed_text_start"]
        end = r["indexed_text_end"]
        text = r.get("content") or ""
        span_len = end - start
        if span_len <= 0:
            continue

        if coverage_end is None:
            parts.append(text)
            coverage_end = end
            continue

        if start >= coverage_end:
            parts.append("\n\n")
            parts.append(text)
            coverage_end = end
            continue

        # Overlap: indexed [start, end) overlaps previous coverage
        overlap_in_index = coverage_end - start
        if overlap_in_index <= 0:
            parts.append(text)
            coverage_end = max(coverage_end, end)
            continue

        if len(text) == span_len:
            skip = overlap_in_index
        else:
            # Proportional skip if stored text length != span (normalization / bugs)
            skip = int(round(overlap_in_index * len(text) / span_len))
        skip = max(0, min(skip, len(text)))
        if skip >= len(text):
            coverage_end = max(coverage_end, end)
            continue
        parts.append(text[skip:])
        coverage_end = max(coverage_end, end)

    return "".join(parts)


def format_kb_search_results_for_llm(results: List[Dict[str, Any]]) -> str:
    """
    Build the \"Knowledge Base Search Results\" string for tool messages.

    Results with ``indexed_text_start`` / ``indexed_text_end`` are merged per ``document_id``
    so overlapping regions are not repeated. Results without spans are emitted separately.
    """
    if not results:
        return "Knowledge Base Search Results:\n(no results)\n"

    first_order: List[str] = []
    seen: set = set()
    for r in results:
        doc_id = r.get("document_id") or ""
        if doc_id not in seen:
            seen.add(doc_id)
            first_order.append(doc_id)

    by_doc: Dict[str, List[Dict[str, Any]]] = {}
    for r in results:
        doc_id = r.get("document_id") or ""
        by_doc.setdefault(doc_id, []).append(r)

    lines: List[str] = ["Knowledge Base Search Results:"]
    block_index = 0

    for doc_id in first_order:
        group = by_doc[doc_id]
        with_spans = [r for r in group if _has_indexed_spans(r)]

        if with_spans:
            block_index += 1
            merged = _merge_span_chunks_for_document(with_spans)
            source = with_spans[0].get("source", "Unknown")
            lines.append(f"\n[{block_index}] {merged}\n")
            lines.append(f"Source: {source}\n")
            rels = [r.get("relevance") for r in with_spans if r.get("relevance") is not None]
            if rels:
                best = max(float(x) for x in rels)
                lines.append(f"Relevance: {best:.6f}\n")

        # Preserve global search ranking order for chunks without stored spans
        for r in results:
            if (r.get("document_id") or "") != doc_id:
                continue
            if _has_indexed_spans(r):
                continue
            block_index += 1
            lines.append(f"\n[{block_index}] {r.get('content', '')}\n")
            lines.append(f"Source: {r.get('source', 'Unknown')}\n")
            rel = r.get("relevance")
            if rel is not None:
                lines.append(f"Relevance: {float(rel):.6f}\n")

    return "".join(lines)
