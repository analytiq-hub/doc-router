"""
Native Mistral Document OCR: upload PDF to Mistral Files, then POST /v1/ocr.

Uses the API key passed in (from account ``llm_providers`` Mistral provider).
"""
from __future__ import annotations

import logging
from typing import Any

import httpx
import stamina

logger = logging.getLogger(__name__)

MISTRAL_OCR_MODEL = "mistral-ocr-latest"
MISTRAL_API_BASE = "https://api.mistral.ai/v1"


def _mistral_transient_error(exc: BaseException) -> bool:
    """Retry on rate limits, server errors, and network/timeouts (not client 4xx except 408/429)."""
    if isinstance(exc, httpx.HTTPStatusError):
        code = exc.response.status_code
        return code in (408, 429) or code >= 500
    if isinstance(exc, httpx.RequestError):
        return True
    return False


@stamina.retry(
    on=_mistral_transient_error,
    attempts=3,
    wait_initial=2.0,
    wait_max=45.0,
    timeout=600.0,
)
async def _post_mistral_file_upload(
    client: httpx.AsyncClient,
    headers: dict[str, str],
    files: dict[str, Any],
    data: dict[str, str],
) -> httpx.Response:
    r = await client.post(
        f"{MISTRAL_API_BASE}/files",
        headers=headers,
        files=files,
        data=data,
    )
    r.raise_for_status()
    return r


@stamina.retry(
    on=_mistral_transient_error,
    attempts=3,
    wait_initial=2.0,
    wait_max=45.0,
    timeout=600.0,
)
async def _post_mistral_ocr(
    client: httpx.AsyncClient,
    headers: dict[str, str],
    body: dict[str, Any],
) -> dict[str, Any]:
    r2 = await client.post(
        f"{MISTRAL_API_BASE}/ocr",
        headers={**headers, "Content-Type": "application/json"},
        json=body,
    )
    r2.raise_for_status()
    return r2.json()


async def mistral_ocr_pdf(
    pdf_bytes: bytes,
    *,
    api_key: str,
    filename: str = "document.pdf",
    timeout_s: float = 600.0,
) -> dict[str, Any]:
    """
    Run Mistral OCR on PDF bytes.

    Returns the JSON body of ``OCRResponse`` (``pages``, ``model``, ``usage_info``, ...).
    ``include_image_base64`` is false (no image payloads).
    """
    if not (api_key or "").strip():
        raise RuntimeError("Mistral OCR requires a non-empty API key from llm_providers")

    headers = {"Authorization": f"Bearer {api_key.strip()}"}

    async with httpx.AsyncClient(timeout=timeout_s) as client:
        files = {"file": (filename, pdf_bytes, "application/pdf")}
        data = {"purpose": "ocr"}
        r = await _post_mistral_file_upload(client, headers, files, data)
        up = r.json()
        file_id = up.get("id")
        if not file_id:
            raise RuntimeError(f"Mistral file upload: missing id in response: {up}")

        try:
            ocr_body = {
                "model": MISTRAL_OCR_MODEL,
                "document": {"type": "file", "file_id": file_id},
                "include_image_base64": False,
            }
            return await _post_mistral_ocr(client, headers, ocr_body)
        finally:
            try:
                rd = await client.delete(
                    f"{MISTRAL_API_BASE}/files/{file_id}",
                    headers=headers,
                )
                rd.raise_for_status()
            except Exception as e:
                logger.warning(f"Mistral file delete failed file_id={file_id}: {e}")
