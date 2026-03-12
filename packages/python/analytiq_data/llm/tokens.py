import json
import os
import analytiq_data as ad

async def get_llm_key(analytiq_client, llm_provider: str) -> str:
    """
    Get the LLM key
    """
    db = analytiq_client.mongodb_async[analytiq_client.env]
    provider_config = await db.llm_providers.find_one({"litellm_provider": llm_provider})
    if provider_config is None:
        raise ValueError(f"LLM provider {llm_provider} not found")
    if provider_config["token"] in [None, ""]:
        return ""

    # Decrypt the token before returning
    return ad.crypto.decrypt_token(provider_config["token"])


async def get_vertex_ai_config(analytiq_client) -> tuple[str, str]:
    """
    Get the Vertex AI project and location.

    Extracts ``project_id`` from the stored service account JSON credentials.
    Location falls back to env var VERTEX_AI_LOCATION (default: ``global``).

    Returns:
        (vertex_project, vertex_location) — either may be empty string if not configured.
    """
    db = analytiq_client.mongodb_async[analytiq_client.env]
    provider_config = await db.llm_providers.find_one({"litellm_provider": "vertex_ai"})
    vertex_location = os.getenv("VERTEX_AI_LOCATION", "global")
    if provider_config is None or not provider_config.get("token"):
        return "", vertex_location
    try:
        credentials = json.loads(ad.crypto.decrypt_token(provider_config["token"]))
        vertex_project = credentials.get("project_id", "")
    except Exception:
        vertex_project = ""
    return vertex_project, vertex_location