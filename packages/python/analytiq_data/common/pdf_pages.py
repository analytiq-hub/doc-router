"""PDF page count for OCR SPU pre-checks."""
from __future__ import annotations

import logging

import fitz  # PyMuPDF (pymupdf)

logger = logging.getLogger(__name__)


def pdf_page_count(pdf_bytes: bytes) -> int | None:
    """
    Return number of pages in a PDF, or None if parsing fails.

    Uses PyMuPDF.
    """
    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        try:
            n = doc.page_count
            return n if n > 0 else None
        finally:
            doc.close()
    except Exception as e:
        logger.warning("pdf_page_count failed: %s", e)
        return None
