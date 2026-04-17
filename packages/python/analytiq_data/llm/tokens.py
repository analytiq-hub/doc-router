import analytiq_data as ad

async def get_llm_key(analytiq_client, llm_provider: str) -> str:
    """
    Get the LLM key
    """
    if llm_provider == "vertex_ai":
        from analytiq_data.cloud.cloud_config import get_gcp_service_account_json

        return await get_gcp_service_account_json(analytiq_client)

    if llm_provider == "azure_ai":
        # Microsoft Foundry: Entra tokens come from cloud_config via llm_azure
        return ""

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

    Extracts ``project_id`` from GCP credentials in ``cloud_config`` (or legacy ``llm_providers``).
    Location falls back to env var VERTEX_AI_LOCATION (default: ``global``).

    Returns:
        (vertex_project, vertex_location) — either may be empty string if not configured.
    """
    from analytiq_data.cloud.cloud_config import get_vertex_project_and_location

    return await get_vertex_project_and_location(analytiq_client)