"""
Error handling utilities for Knowledge Base operations.
"""

import logging
from datetime import datetime, UTC
from bson import ObjectId

import analytiq_data as ad

logger = logging.getLogger(__name__)


def is_retryable_embedding_error(exception: Exception) -> bool:
    """
    Check if an embedding API error is retryable.
    
    Args:
        exception: The exception to check
        
    Returns:
        bool: True if the exception is retryable, False otherwise
    """
    if not isinstance(exception, Exception):
        return False
    
    error_message = str(exception).lower()
    
    # Check for specific retryable error patterns
    retryable_patterns = [
        "503",
        "429",  # Rate limit
        "rate limit",
        "rate_limit",
        "too many requests",
        "timeout",
        "connection error",
        "connection timeout",
        "internal server error",
        "service unavailable",
        "temporarily unavailable",
        "model is overloaded",
        "overloaded",
        "unavailable",
        "502",  # Bad Gateway
        "504",  # Gateway Timeout
    ]
    
    for pattern in retryable_patterns:
        if pattern in error_message:
            return True
    
    return False


def is_permanent_embedding_error(exception: Exception) -> bool:
    """
    Check if an embedding API error is permanent (non-retryable).
    
    Args:
        exception: The exception to check
        
    Returns:
        bool: True if the exception is permanent, False otherwise
    """
    if not isinstance(exception, Exception):
        return False
    
    error_message = str(exception).lower()
    
    # Check for permanent error patterns
    permanent_patterns = [
        "401",  # Unauthorized
        "403",  # Forbidden
        "invalid api key",
        "authentication failed",
        "invalid model",
        "model not found",
        "unsupported model",
        "400",  # Bad Request (usually means invalid input, not retryable)
    ]
    
    for pattern in permanent_patterns:
        if pattern in error_message:
            return True
    
    return False


async def set_kb_status_to_error(
    analytiq_client,
    kb_id: str,
    organization_id: str,
    error_message: str
) -> None:
    """
    Set a knowledge base status to "error" with error details.
    
    Args:
        analytiq_client: The analytiq client
        kb_id: Knowledge base ID
        organization_id: Organization ID
        error_message: Error message to store
    """
    db = analytiq_client.mongodb_async[analytiq_client.env]
    
    try:
        await db.knowledge_bases.update_one(
            {"_id": ObjectId(kb_id), "organization_id": organization_id},
            {
                "$set": {
                    "status": "error",
                    "error_message": error_message,
                    "updated_at": datetime.now(UTC)
                }
            }
        )
        logger.warning(f"Set KB {kb_id} status to 'error': {error_message}")
    except Exception as e:
        logger.error(f"Failed to set KB {kb_id} status to error: {e}")
