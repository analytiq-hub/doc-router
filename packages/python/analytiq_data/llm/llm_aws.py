"""
AWS Bedrock parameter injection for litellm acompletion / aembedding calls.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


async def add_aws_params(analytiq_client, params: dict) -> None:
    """
    For ``bedrock`` models: fetch AWS credentials and inject
    ``aws_access_key_id``, ``aws_secret_access_key``, and ``aws_region_name``.

    Args:
        analytiq_client: Used to retrieve the AWS client with credentials.
        params: litellm params dict to mutate in-place.
    """
    import analytiq_data as ad

    aws_client = await ad.aws.get_aws_client_async(analytiq_client, region_name="us-east-1")
    params["aws_access_key_id"] = aws_client.aws_access_key_id
    params["aws_secret_access_key"] = aws_client.aws_secret_access_key
    params["aws_region_name"] = aws_client.region_name
    logger.debug("add_aws_params: region=%s", aws_client.region_name)
