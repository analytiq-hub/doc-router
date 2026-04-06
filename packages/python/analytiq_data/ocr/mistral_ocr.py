"""
Native Mistral Document OCR: upload PDF to Mistral Files, then POST /v1/ocr.

Requires ``MISTRAL_API_KEY`` in the environment.
"""
from __future__ import annotations

import logging
import os
from typing import Any

import httpx

logger = logging.getLogger(__name__)

MISTRAL_OCR_MODEL = "mistral-ocr-latest"
MISTRAL_API_BASE = "https://api.mistral.ai/v1"


async def mistral_ocr_pdf(
    pdf_bytes: bytes,
    *,
    filename: str = "document.pdf",
    timeout_s: float = 600.0,
) -> dict[str, Any]:
    """
    Run Mistral OCR on PDF bytes.

    Returns the JSON body of ``OCRResponse`` (``pages``, ``model``, ``usage_info``, ...).
    ``include_image_base64`` is false (no image payloads).
    """
    api_key = os.environ.get("MISTRAL_API_KEY")
    if not api_key:
        raise RuntimeError("MISTRAL_API_KEY is not set; cannot run Mistral OCR")

    headers = {"Authorization": f"Bearer {api_key}"}

    async with httpx.AsyncClient(timeout=timeout_s) as client:
        files = {"file": (filename, pdf_bytes, "application/pdf")}
        data = {"purpose": "ocr"}
        r = await client.post(
            f"{MISTRAL_API_BASE}/files",
            headers=headers,
            files=files,
            data=data,
        )
        r.raise_for_status()
        up = r.json()
        file_id = up.get("id")
        if not file_id:
            raise RuntimeError(f"Mistral file upload: missing id in response: {up}")

        try:
            body = {
                "model": MISTRAL_OCR_MODEL,
                "document": {"type": "file", "file_id": file_id},
                "include_image_base64": False,
            }
            r2 = await client.post(
                f"{MISTRAL_API_BASE}/ocr",
                headers={**headers, "Content-Type": "application/json"},
                json=body,
            )
            r2.raise_for_status()
            return r2.json()
        finally:
            try:
                rd = await client.delete(
                    f"{MISTRAL_API_BASE}/files/{file_id}",
                    headers=headers,
                )
                rd.raise_for_status()
            except Exception as e:
                logger.warning("Mistral file delete failed file_id=%s: %s", file_id, e)
