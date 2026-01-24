"""
Embedding cache management for Knowledge Bases.

The embedding cache stores embeddings keyed by (chunk_hash, embedding_model) to enable
reuse across KBs with the same embedding model, avoiding redundant API calls.
"""

import logging
from datetime import datetime, UTC
from typing import Optional, List, Dict, Any
import hashlib

import analytiq_data as ad

logger = logging.getLogger(__name__)


def compute_chunk_hash(chunk_text: str) -> str:
    """
    Compute SHA-256 hash of chunk text for caching.
    
    Args:
        chunk_text: The text content of the chunk
        
    Returns:
        SHA-256 hash as hexadecimal string
    """
    return hashlib.sha256(chunk_text.encode('utf-8')).hexdigest()


async def get_embedding_from_cache(
    analytiq_client,
    chunk_hash: str,
    embedding_model: str
) -> Optional[List[float]]:
    """
    Retrieve embedding from cache if it exists.
    
    Args:
        analytiq_client: The analytiq client
        chunk_hash: SHA-256 hash of the chunk text
        embedding_model: LiteLLM embedding model string
        
    Returns:
        Embedding vector if found, None otherwise
    """
    db = analytiq_client.mongodb_async[analytiq_client.env]
    cache_entry = await db.embedding_cache.find_one({
        "chunk_hash": chunk_hash,
        "embedding_model": embedding_model
    })
    
    if cache_entry:
        logger.debug(f"Cache hit for chunk_hash={chunk_hash[:16]}..., model={embedding_model}")
        return cache_entry.get("embedding")
    
    logger.debug(f"Cache miss for chunk_hash={chunk_hash[:16]}..., model={embedding_model}")
    return None


async def store_embedding_in_cache(
    analytiq_client,
    chunk_hash: str,
    embedding_model: str,
    embedding: List[float]
) -> None:
    """
    Store embedding in cache.
    
    Args:
        analytiq_client: The analytiq client
        chunk_hash: SHA-256 hash of the chunk text
        embedding_model: LiteLLM embedding model string
        embedding: The embedding vector to store
    """
    db = analytiq_client.mongodb_async[analytiq_client.env]
    
    # Upsert cache entry (unique on chunk_hash + embedding_model)
    await db.embedding_cache.update_one(
        {
            "chunk_hash": chunk_hash,
            "embedding_model": embedding_model
        },
        {
            "$set": {
                "embedding": embedding,
                "created_at": datetime.now(UTC)
            },
            "$setOnInsert": {
                "chunk_hash": chunk_hash,
                "embedding_model": embedding_model
            }
        },
        upsert=True
    )
    
    logger.debug(f"Stored embedding in cache: chunk_hash={chunk_hash[:16]}..., model={embedding_model}")


async def ensure_embedding_cache_index(analytiq_client) -> None:
    """
    Ensure the embedding_cache collection has the required unique index.
    This should be called during application startup.
    
    Args:
        analytiq_client: The analytiq client
    """
    db = analytiq_client.mongodb_async[analytiq_client.env]
    
    # Create unique compound index on (chunk_hash, embedding_model)
    try:
        await db.embedding_cache.create_index(
            [("chunk_hash", 1), ("embedding_model", 1)],
            unique=True,
            name="chunk_hash_embedding_model_unique"
        )
        logger.info("Created unique index on embedding_cache (chunk_hash, embedding_model)")
    except Exception as e:
        # Index might already exist, that's okay
        if "already exists" not in str(e).lower() and "IndexOptionsConflict" not in str(e):
            logger.warning(f"Could not create embedding_cache index: {e}")
