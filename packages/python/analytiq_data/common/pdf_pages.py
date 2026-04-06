"""PDF page count for OCR SPU pre-checks."""
from __future__ import annotations

import io
import logging

logger = logging.getLogger(__name__)


def pdf_page_count(pdf_bytes: bytes) -> int | None:
    """
    Return number of pages in a PDF, or None if parsing fails.

    Uses pypdf when available.
    """
    try:
        from pypdf import PdfReader
    except ImportError:
        logger.warning("pypdf not installed; cannot count PDF pages")
        return None
    try:
        reader = PdfReader(io.BytesIO(pdf_bytes))
        return len(reader.pages)
    except Exception as e:
        logger.warning("pdf_page_count failed: %s", e)
        return None
