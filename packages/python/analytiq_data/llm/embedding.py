"""
Shared embedding helper that injects provider-specific credentials before
calling litellm.aembedding.

Handles:
  - Standard API-key providers  (OpenAI, Anthropic, etc.)
  - AWS Bedrock                  (AWS IAM – no API key token)
  - Google Vertex AI             (service-account JSON stored in cloud_config)
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

    if not api_key and provider not in ("bedrock", "vertex_ai"):
        raise ValueError(f"No API key found for provider {provider}")

    params: dict = {
        "model": model,
        "input": texts,
    }
    if api_key:
        params["api_key"] = api_key

    if provider == "bedrock":
        aws_client = await ad.aws.get_aws_client_async(analytiq_client, region_name="us-east-1")
        params["aws_access_key_id"] = aws_client.aws_access_key_id
        params["aws_secret_access_key"] = aws_client.aws_secret_access_key
        params["aws_region_name"] = aws_client.region_name
        logger.debug(f"aembedding: Bedrock region={aws_client.region_name}")

    if provider == "vertex_ai":
        params.pop("api_key", None)
        if api_key:
            params["vertex_credentials"] = api_key
            try:
                creds = json.loads(api_key)
                if creds.get("project_id"):
                    params["vertex_project"] = creds["project_id"]
            except Exception:
                pass
        vertex_project, vertex_location = await ad.llm.get_vertex_ai_config(analytiq_client)
        if vertex_project:
            params["vertex_project"] = vertex_project
        # Gemini embedding models are only available in us-central1
        params["vertex_location"] = vertex_location or os.getenv("VERTEX_AI_LOCATION", "us-central1")
        logger.debug(f"aembedding: Vertex AI project={params.get('vertex_project')}, location={params['vertex_location']}")

    return await litellm.aembedding(**params)
