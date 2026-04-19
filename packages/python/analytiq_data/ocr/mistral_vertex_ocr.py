"""
Mistral OCR via Google Cloud Vertex AI rawPredict endpoint.

Endpoint (region hardcoded to us-central1):
  https://us-central1-aiplatform.googleapis.com/v1/projects/{project_id}/
      locations/us-central1/publishers/mistralai/models/mistral-ocr-2505:rawPredict

Auth: Bearer token obtained from the GCP service account JSON stored in cloud_config.
"""
from __future__ import annotations

import asyncio
import base64
import json
import logging
from typing import Any

import httpx
import stamina

logger = logging.getLogger(__name__)

MISTRAL_VERTEX_REGION = "us-central1"
MISTRAL_VERTEX_MODEL = "mistral-ocr-2505"
VERTEX_SCOPES = ["https://www.googleapis.com/auth/cloud-platform"]


def _get_access_token(service_account_json: str) -> str:
    """Synchronous: exchange service account JSON for a short-lived access token.
    Must be called via asyncio.to_thread to avoid blocking the event loop."""
    import google.oauth2.service_account
    import google.auth.transport.requests

    info = json.loads(service_account_json)
    credentials = google.oauth2.service_account.Credentials.from_service_account_info(
        info, scopes=VERTEX_SCOPES
    )
    request = google.auth.transport.requests.Request()
    credentials.refresh(request)
    return credentials.token


def _mistral_vertex_transient_error(exc: BaseException) -> bool:
    if isinstance(exc, httpx.HTTPStatusError):
        code = exc.response.status_code
        return code in (408, 429) or code >= 500
    if isinstance(exc, httpx.RequestError):
        return True
    return False


@stamina.retry(
    on=_mistral_vertex_transient_error,
    attempts=3,
    wait_initial=2.0,
    wait_max=45.0,
    timeout=600.0,
)
async def _post_vertex_ocr(
    client: httpx.AsyncClient,
    url: str,
    token: str,
    body: dict[str, Any],
) -> dict[str, Any]:
    r = await client.post(
        url,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        json=body,
        timeout=600.0,
    )
    r.raise_for_status()
    return r.json()


async def mistral_vertex_ocr_pdf(
    pdf_bytes: bytes,
    *,
    service_account_json: str,
) -> dict[str, Any]:
    """
    Run Mistral OCR on PDF bytes via Vertex AI rawPredict.

    Returns the Mistral OCRResponse JSON (``pages``, ``model``, ``usage_info``, ...).
    ``include_image_base64`` is false.
    """
    if not (service_account_json or "").strip():
        raise RuntimeError("Vertex AI Mistral OCR requires GCP service account JSON in cloud_config")

    sa = json.loads(service_account_json)
    project_id = sa.get("project_id", "").strip()
    if not project_id:
        raise RuntimeError("GCP service account JSON is missing project_id")

    # _get_access_token is synchronous (google-auth); run it off the event loop
    token = await asyncio.to_thread(_get_access_token, service_account_json)

    region = MISTRAL_VERTEX_REGION
    url = (
        f"https://{region}-aiplatform.googleapis.com/v1"
        f"/projects/{project_id}/locations/{region}"
        f"/publishers/mistralai/models/{MISTRAL_VERTEX_MODEL}:rawPredict"
    )

    b64 = base64.b64encode(pdf_bytes).decode("ascii")
    body = {
        "model": MISTRAL_VERTEX_MODEL,
        "document": {
            "type": "document_url",
            "document_url": f"data:application/pdf;base64,{b64}",
        },
        "include_image_base64": False,
    }

    async with httpx.AsyncClient(timeout=600.0) as client:
        result = await _post_vertex_ocr(client, url, token, body)

    logger.info(
        "mistral_vertex_ocr_pdf: project=%s region=%s model=%s pages=%s",
        project_id,
        region,
        MISTRAL_VERTEX_MODEL,
        len((result.get("pages") or [])),
    )
    return result
