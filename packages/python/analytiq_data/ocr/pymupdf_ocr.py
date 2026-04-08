"""
Embedded PDF text extraction via PyMuPDF + PyMuPDF4LLM (Markdown for RAG/LLM).

Uses ``pymupdf4llm.to_markdown`` with ``use_ocr=False`` so only selectable text is
used (no Tesseract). Output matches the pages-markdown shape used by Mistral/LLM OCR.
"""
from __future__ import annotations

from typing import Any

import fitz  # PyMuPDF
import pymupdf4llm


def extract_pymupdf_pdf(pdf_bytes: bytes) -> dict[str, Any]:
    """
    Return ``{ "ocr_engine": "pymupdf", "pages": [ { "index", "markdown" } ] }``.

    ``markdown`` is GitHub-flavored Markdown from PyMuPDF4LLM (headings, lists, tables
    where detectable), not raw ``Page.get_text()`` plain text.
    """
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    try:
        chunks = pymupdf4llm.to_markdown(
            doc,
            show_progress=False,
            use_ocr=False,
            page_chunks=True,
        )
        pages: list[dict[str, Any]] = []
        if isinstance(chunks, list):
            for i, chunk in enumerate(chunks):
                md = ""
                if isinstance(chunk, dict):
                    md = chunk.get("text") or ""
                pages.append({"index": i, "markdown": md})
        else:
            # Unexpected shape; store whole document as page 0
            pages.append({"index": 0, "markdown": str(chunks or "")})

        return {"ocr_engine": "pymupdf", "pages": pages}
    finally:
        doc.close()
