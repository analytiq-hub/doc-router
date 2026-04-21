"""
Mistral native OCR: API key from account ``llm_providers`` (name ``mistral``).

OCR availability in the catalog matches other future OCR+LLM modes: the provider must be
enabled and at least one LiteLLM model must be enabled on that provider. We do **not**
inspect the API key to decide whether OCR is offered in the UI.
"""
from __future__ import annotations

import logging

import analytiq_data as ad

logger = logging.getLogger(__name__)

MISTRAL_LLM_PROVIDER_NAME = "mistral"


def provider_and_llm_enabled(doc: dict | None) -> bool:
    """
    True when the ``llm_providers`` document has the provider on and at least one model enabled.

    Used for OCR catalog / org validation so options appear without requiring a stored API key.
    """
    if doc is None:
        return False
    if not doc.get("enabled", False):
        return False
    models = doc.get("litellm_models_enabled") or []
    return len(models) > 0


async def _mistral_provider_doc() -> dict | None:
    db = ad.common.get_async_db()
    return await db.llm_providers.find_one({"name": MISTRAL_LLM_PROVIDER_NAME})


async def mistral_ocr_enabled_from_llm_providers() -> bool:
    """Whether Mistral OCR may be selected (provider + models enabled; key not checked)."""
    doc = await _mistral_provider_doc()
    return provider_and_llm_enabled(doc)


def _decrypt_token_field(doc: dict | None) -> str | None:
    if doc is None:
        return None
    token = doc.get("token")
    if not token:
        return None
    try:
        decrypted = ad.crypto.decrypt_token(token)
    except Exception as e:
        logger.warning(f"Failed to decrypt Mistral llm_providers token: {e}")
        return None
    key = (decrypted or "").strip()
    return key if key else None


async def mistral_api_key_from_llm_providers() -> str | None:
    """Decrypted Mistral API key for HTTP calls, or None if missing/invalid (enablement not checked)."""
    doc = await _mistral_provider_doc()
    return _decrypt_token_field(doc)


async def get_mistral_api_key_for_ocr() -> str:
    """
    API key for Mistral OCR HTTP calls.

    Requires the same provider+model enablement as the catalog, plus a non-empty stored key.
    """
    doc = await _mistral_provider_doc()
    if not provider_and_llm_enabled(doc):
        raise RuntimeError(
            "Mistral OCR requires the Mistral LLM provider to be enabled with at least one model "
            "enabled in account LLM settings (llm_providers)."
        )
    key = _decrypt_token_field(doc)
    if not key:
        raise RuntimeError(
            "Mistral OCR requires an API key on the Mistral LLM provider in account LLM settings."
        )
    return key
