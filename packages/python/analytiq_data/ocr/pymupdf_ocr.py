"""
Embedded PDF text extraction via PyMuPDF (no cloud OCR).

Output matches the pages-markdown shape used by Mistral/LLM OCR so downstream
``save_ocr_text_from_json`` and indexing can reuse the same path.
"""
from __future__ import annotations

from typing import Any

import fitz  # PyMuPDF


def extract_pymupdf_pdf(pdf_bytes: bytes) -> dict[str, Any]:
    """
    Return ``{ "ocr_engine": "pymupdf", "pages": [ { "index", "markdown" } ] }``.

    ``markdown`` holds plain extracted text per page (no markdown formatting).
    """
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    try:
        pages: list[dict[str, Any]] = []
        for i in range(doc.page_count):
            page = doc.load_page(i)
            text = page.get_text()
            pages.append({"index": i, "markdown": text or ""})
        return {"ocr_engine": "pymupdf", "pages": pages}
    finally:
        doc.close()
