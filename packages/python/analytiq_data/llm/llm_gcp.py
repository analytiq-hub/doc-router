"""
Google Cloud Vertex AI parameter injection for litellm acompletion / aembedding calls.
"""

from __future__ import annotations

import json
import logging
import os

logger = logging.getLogger(__name__)


async def add_gcp_params(
    analytiq_client,
    params: dict,
    api_key: str,
    *,
    default_location: str = "global",
) -> None:
    """
    For ``vertex_ai`` models: remove ``api_key``, inject ``vertex_credentials``,
    ``vertex_project``, and ``vertex_location``.

    Args:
        analytiq_client: When not None, ``get_vertex_ai_config`` is called to
            override project/location from cloud_config (used by embedding path).
        params: litellm params dict to mutate in-place.
        api_key: GCP service account JSON string (may be empty).
        default_location: Fallback location when not set via env or cloud_config.
    """
    params.pop("api_key", None)

    if api_key:
        try:
            creds = json.loads(api_key)
        except (ValueError, TypeError) as exc:
            raise Exception(f"Vertex AI API key is not valid JSON: {api_key}") from exc
        params["vertex_credentials"] = api_key
        if creds.get("project_id"):
            params["vertex_project"] = creds["project_id"]

    if analytiq_client is not None:
        from analytiq_data.llm.tokens import get_vertex_ai_config

        vertex_project, vertex_location = await get_vertex_ai_config(analytiq_client)
        if vertex_project:
            params["vertex_project"] = vertex_project
        params["vertex_location"] = vertex_location or os.getenv("VERTEX_AI_LOCATION", default_location)
    else:
        params["vertex_location"] = os.getenv("VERTEX_AI_LOCATION", default_location)

    logger.debug(
        f"add_gcp_params: project={params.get('vertex_project')} location={params.get('vertex_location')}"
    )
