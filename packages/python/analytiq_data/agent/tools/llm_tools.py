"""
LLM tools for the agent: list enabled models available for prompts.
Uses get_async_db(analytiq_client) for all DB access.
"""
from __future__ import annotations

import logging
from typing import Any

import analytiq_data as ad

logger = logging.getLogger(__name__)


def _db(context: dict):
    return ad.common.get_async_db(context["analytiq_client"])


async def list_llm_models(context: dict, params: dict) -> dict[str, Any]:
    """List enabled LLM model names available for use in prompts."""
    org_id = context.get("organization_id")
    if not org_id:
        return {"error": "No organization context"}

    db = _db(context)
    providers = await db.llm_providers.find({"enabled": True}).to_list(length=None)

    model_names: list[str] = []
    for provider in providers:
        model_names.extend(provider.get("litellm_models_enabled", []))

    return {"models": model_names}
