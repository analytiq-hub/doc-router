"""
Shared embedding helper that injects provider-specific credentials before
calling litellm.aembedding.

Handles:
  - Standard API-key providers  (OpenAI, Anthropic, etc.)
  - AWS Bedrock                  (AWS IAM – no API key token)
  - Google Vertex AI             (service-account JSON stored in cloud_config)
  - Microsoft Foundry (azure_ai) (Entra service principal in cloud_config)
"""

import json
import logging
import os

import litellm

import analytiq_data as ad

logger = logging.getLogger(__name__)


async def aembedding(analytiq_client, model: str, texts: list) -> litellm.EmbeddingResponse:
    """
    Call litellm.aembedding with provider-specific credential injection.

    Args:
        analytiq_client: AnalytiqClient instance
        model:           LiteLLM model string (e.g. "text-embedding-3-small",
                         "cohere.embed-v4:0", "vertex_ai/gemini-embedding-001")
        texts:           List of strings to embed

    Returns:
        litellm EmbeddingResponse

    Raises:
        ValueError: If provider cannot be determined or credentials are missing
    """
    provider = ad.llm.get_llm_model_provider(model)
    if provider is None:
        raise ValueError(f"Could not determine provider for embedding model {model}")

    api_key = await ad.llm.get_llm_key(analytiq_client, provider)

    if not api_key and provider not in ("bedrock", "vertex_ai", "azure_ai"):
        raise ValueError(f"No API key found for provider {provider}")

    params: dict = {
        "model": model,
        "input": texts,
    }
    if api_key:
        params["api_key"] = api_key

    if provider == "bedrock":
        from analytiq_data.llm.llm_aws import add_aws_params

        await add_aws_params(analytiq_client, params)

    elif provider == "vertex_ai":
        from analytiq_data.llm.llm_gcp import add_gcp_params

        # Gemini embedding models are only available in us-central1
        await add_gcp_params(analytiq_client, params, api_key, default_location="us-central1")

    elif provider == "azure_ai":
        from analytiq_data.llm.llm_azure import add_azure_params

        await add_azure_params(params)

    return await litellm.aembedding(**params)
