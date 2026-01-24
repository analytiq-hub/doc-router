"""
Knowledge Base vector search functionality.
"""

import logging
from datetime import datetime, UTC
from typing import List, Dict, Any, Optional
from bson import ObjectId

import litellm
import stamina

import analytiq_data as ad
from .embedding_cache import get_embedding_from_cache, store_embedding_in_cache, compute_chunk_hash
from .errors import is_retryable_embedding_error, is_retryable_vector_index_error

logger = logging.getLogger(__name__)


def sanitize_metadata_filter(metadata_filter: Dict[str, Any]) -> Dict[str, Any]:
    """
    Sanitize metadata filter to prevent MongoDB injection.
    Only allows safe operators and field names.
    
    Args:
        metadata_filter: Raw metadata filter from request
        
    Returns:
        Sanitized filter dict
    """
    if not metadata_filter:
        return {}
    
    sanitized = {}
    allowed_operators = {"$in", "$eq", "$ne", "$gt", "$gte", "$lt", "$lte"}
    
    for key, value in metadata_filter.items():
        # Only allow specific metadata fields
        if key not in ["document_name", "tag_ids", "metadata"]:
            logger.warning(f"Ignoring disallowed metadata filter key: {key}")
            continue
        
        # If value is a dict, check for allowed operators
        if isinstance(value, dict):
            sanitized_value = {}
            for op, op_value in value.items():
                if op in allowed_operators:
                    sanitized_value[op] = op_value
                else:
                    logger.warning(f"Ignoring disallowed operator: {op}")
            if sanitized_value:
                sanitized[key] = sanitized_value
        else:
            # Direct value match
            sanitized[key] = value
    
    return sanitized


def build_vector_search_filter(
    organization_id: str,
    document_ids: Optional[List[str]] = None,
    metadata_filter: Optional[Dict[str, Any]] = None,
    upload_date_from: Optional[datetime] = None,
    upload_date_to: Optional[datetime] = None
) -> Dict[str, Any]:
    """
    Build MongoDB filter for vector search.
    
    Args:
        organization_id: Organization ID (required)
        document_ids: Optional list of document IDs to filter by
        metadata_filter: Optional metadata filters (sanitized)
        upload_date_from: Optional upload date start
        upload_date_to: Optional upload date end
        
    Returns:
        MongoDB filter dict
    """
    filter_dict = {"organization_id": organization_id}
    
    if document_ids:
        filter_dict["document_id"] = {"$in": document_ids}
    
    # Apply metadata filters from metadata_snapshot
    if metadata_filter:
        sanitized = sanitize_metadata_filter(metadata_filter)
        for key, value in sanitized.items():
            if key == "tag_ids":
                # Filter by tag_ids in metadata_snapshot
                if isinstance(value, list):
                    filter_dict["metadata_snapshot.tag_ids"] = {"$in": value}
                else:
                    filter_dict["metadata_snapshot.tag_ids"] = value
            elif key == "document_name":
                # Filter by document_name in metadata_snapshot
                if isinstance(value, str):
                    filter_dict["metadata_snapshot.document_name"] = {"$regex": value, "$options": "i"}
                else:
                    filter_dict["metadata_snapshot.document_name"] = value
            elif key == "metadata":
                # Filter by custom metadata in metadata_snapshot.metadata
                if isinstance(value, dict):
                    for meta_key, meta_value in value.items():
                        filter_dict[f"metadata_snapshot.metadata.{meta_key}"] = meta_value
                else:
                    filter_dict["metadata_snapshot.metadata"] = value
    
    # Apply date range filters
    if upload_date_from or upload_date_to:
        date_filter = {}
        if upload_date_from:
            date_filter["$gte"] = upload_date_from
        if upload_date_to:
            date_filter["$lte"] = upload_date_to
        if date_filter:
            filter_dict["metadata_snapshot.upload_date"] = date_filter
    
    return filter_dict


async def search_knowledge_base(
    analytiq_client,
    kb_id: str,
    query: str,
    organization_id: str,
    top_k: int = 5,
    skip: int = 0,
    document_ids: Optional[List[str]] = None,
    metadata_filter: Optional[Dict[str, Any]] = None,
    upload_date_from: Optional[datetime] = None,
    upload_date_to: Optional[datetime] = None,
    coalesce_neighbors: Optional[int] = None
) -> Dict[str, Any]:
    """
    Perform vector search on a knowledge base.
    
    Args:
        analytiq_client: The analytiq client
        kb_id: Knowledge base ID
        query: Search query text
        organization_id: Organization ID
        top_k: Number of results to return
        skip: Pagination offset
        document_ids: Optional list of document IDs to filter by
        metadata_filter: Optional metadata filters
        upload_date_from: Optional upload date start
        upload_date_to: Optional upload date end
        coalesce_neighbors: Optional override for KB's coalesce_neighbors setting
        
    Returns:
        Dict with search results and metadata
    """
    db = analytiq_client.mongodb_async[analytiq_client.env]
    
    # Get KB configuration
    kb = await db.knowledge_bases.find_one({"_id": ObjectId(kb_id), "organization_id": organization_id})
    if not kb:
        raise ValueError(f"Knowledge base {kb_id} not found")
    
    if kb.get("status") != "active":
        raise ValueError(f"Knowledge base {kb_id} is not active (status: {kb.get('status')})")
    
    # Determine coalesce_neighbors
    coalesce = coalesce_neighbors if coalesce_neighbors is not None else kb.get("coalesce_neighbors", 0)
    
    # Generate query embedding
    embedding_model = kb["embedding_model"]
    
    # Check cache for query embedding
    query_hash = compute_chunk_hash(query)
    query_embedding = await get_embedding_from_cache(analytiq_client, query_hash, embedding_model)
    
    if not query_embedding:
        # Check SPU credits before generating query embedding (1 SPU per query embedding)
        # This will raise SPUCreditException if insufficient credits
        await ad.payments.check_spu_limits(organization_id, 1)
        
        # Generate embedding with retry logic
        try:
            query_embedding = await _generate_query_embedding_with_retry(
                analytiq_client,
                query,
                embedding_model
            )
            
            # Cache the query embedding
            await store_embedding_in_cache(analytiq_client, query_hash, embedding_model, query_embedding)
            
            # Record SPU usage: 1 SPU per query embedding generated (cache miss)
            try:
                model_info = litellm.get_model_info(embedding_model)
                provider = model_info.get("provider")
                await ad.payments.record_spu_usage(
                    org_id=organization_id,
                    spus=1,  # 1 SPU per query embedding
                    llm_provider=provider,
                    llm_model=embedding_model
                )
                logger.info(f"Recorded 1 SPU usage for query embedding generated")
            except Exception as e:
                logger.error(f"Error recording SPU usage for query embedding: {e}")
                # Don't fail search if SPU recording fails
            
        except Exception as e:
            logger.error(f"Error generating query embedding: {e}")
            raise ValueError(f"Failed to generate query embedding: {str(e)}")
    
    # Build filter
    search_filter = build_vector_search_filter(
        organization_id=organization_id,
        document_ids=document_ids,
        metadata_filter=metadata_filter,
        upload_date_from=upload_date_from,
        upload_date_to=upload_date_to
    )
    
    # Perform vector search
    collection_name = f"kb_vectors_{kb_id}"
    vectors_collection = db[collection_name]
    
    # Build aggregation pipeline with $vectorSearch
    # Note: $vectorSearch must be the first stage
    vector_search_stage = {
        "index": "kb_vector_index",
        "path": "embedding",
        "queryVector": query_embedding,
        "numCandidates": max(top_k * 10, 100),  # Search more candidates for better results
        "limit": top_k + skip  # Get enough for pagination
    }
    
    # Add filter only if it's not empty
    if search_filter:
        vector_search_stage["filter"] = search_filter
    
    pipeline = [
        {
            "$vectorSearch": vector_search_stage
        }
    ]
    
    # Add score field if filter was used (score is always available from $vectorSearch)
    pipeline.append({
        "$addFields": {
            "score": {"$meta": "vectorSearchScore"}
        }
    })
    
    # Apply pagination
    if skip > 0:
        pipeline.append({"$skip": skip})
    pipeline.append({"$limit": top_k})
    
    # Execute search with retry logic for vector index timing issues
    search_results = await _execute_vector_search_with_retry(
        vectors_collection,
        pipeline,
        top_k,
        kb_id
    )
    
    # Get total count (approximate, for pagination)
    # Note: MongoDB vector search doesn't provide exact counts efficiently
    # We'll use the number of results as an approximation
    total_count = len(search_results) + skip if len(search_results) == top_k else len(search_results) + skip
    
    # Handle coalescing if needed
    if coalesce > 0 and search_results:
        coalesced_results = []
        
        for result in search_results:
            document_id = result["document_id"]
            chunk_index = result["chunk_index"]
            
            # Get all chunks for this document, sorted by chunk_index
            # Use retry logic for this query too, in case index is still building
            doc_chunks = await _execute_find_query_with_retry(
                vectors_collection,
                {"document_id": document_id, "organization_id": organization_id},
                kb_id
            )
            
            # Find the index of the matched chunk
            matched_idx = next((i for i, chunk in enumerate(doc_chunks) if chunk["chunk_index"] == chunk_index), None)
            
            if matched_idx is not None:
                # Add the matched chunk first
                matched_chunk = doc_chunks[matched_idx]
                coalesced_results.append({
                    **matched_chunk,
                    "is_matched": True,
                    "relevance": result.get("score")
                })
                
                # Add preceding chunks
                for i in range(max(0, matched_idx - coalesce), matched_idx):
                    coalesced_results.append({
                        **doc_chunks[i],
                        "is_matched": False,
                        "relevance": None
                    })
                
                # Add succeeding chunks
                for i in range(matched_idx + 1, min(len(doc_chunks), matched_idx + 1 + coalesce)):
                    coalesced_results.append({
                        **doc_chunks[i],
                        "is_matched": False,
                        "relevance": None
                    })
            else:
                # Fallback: just add the matched chunk
                coalesced_results.append({
                    **result,
                    "is_matched": True,
                    "relevance": result.get("score")
                })
        
        search_results = coalesced_results
    else:
        # Mark all as matched if no coalescing
        for result in search_results:
            result["is_matched"] = True
            result["relevance"] = result.get("score")
    
    # Format results
    formatted_results = []
    for result in search_results:
        # Safely get metadata_snapshot (handle None case)
        metadata_snapshot = result.get("metadata_snapshot") or {}
        formatted_results.append({
            "content": result.get("chunk_text", ""),
            "source": metadata_snapshot.get("document_name", "Unknown"),
            "document_id": result.get("document_id", ""),
            "relevance": result.get("relevance"),
            "chunk_index": result.get("chunk_index", 0),
            "is_matched": result.get("is_matched", True)
        })
    
    return {
        "results": formatted_results,
        "total_count": total_count
    }


@stamina.retry(on=is_retryable_vector_index_error)
async def _execute_vector_search_with_retry(
    vectors_collection,
    pipeline: List[Dict[str, Any]],
    top_k: int,
    kb_id: str
) -> List[Dict[str, Any]]:
    """
    Execute vector search with retry logic for MongoDB vector index timing issues.
    
    If the index is in INITIAL_SYNC or NOT_STARTED state, this will retry with exponential backoff.
    
    Args:
        vectors_collection: MongoDB collection for vectors
        pipeline: Aggregation pipeline for vector search
        top_k: Number of results to return
        kb_id: Knowledge base ID (for logging)
        
    Returns:
        List of search results
        
    Raises:
        Exception: If search fails after all retries
    """
    try:
        return await vectors_collection.aggregate(pipeline).to_list(length=top_k)
    except Exception as e:
        error_msg = str(e)
        if is_retryable_vector_index_error(e):
            logger.warning(
                f"Vector index for KB {kb_id} not ready yet (INITIAL_SYNC/NOT_STARTED). "
                f"Will retry with exponential backoff. Error: {error_msg[:200]}"
            )
            # Re-raise to trigger stamina retry
            raise
        else:
            # Non-retryable error, re-raise immediately
            logger.error(f"Non-retryable error in vector search for KB {kb_id}: {error_msg[:200]}")
            raise


@stamina.retry(on=is_retryable_vector_index_error)
async def _execute_find_query_with_retry(
    vectors_collection,
    filter_dict: Dict[str, Any],
    kb_id: str
) -> List[Dict[str, Any]]:
    """
    Execute a find query with retry logic for MongoDB vector index timing issues.
    
    Used for coalescing queries that also need to handle index timing.
    
    Args:
        vectors_collection: MongoDB collection for vectors
        filter_dict: Filter dictionary for the find query
        kb_id: Knowledge base ID (for logging)
        
    Returns:
        List of documents
        
    Raises:
        Exception: If query fails after all retries
    """
    try:
        return await vectors_collection.find(filter_dict).sort("chunk_index", 1).to_list(length=None)
    except Exception as e:
        error_msg = str(e)
        if is_retryable_vector_index_error(e):
            logger.warning(
                f"Vector index for KB {kb_id} not ready yet during coalescing query. "
                f"Will retry with exponential backoff. Error: {error_msg[:200]}"
            )
            # Re-raise to trigger stamina retry
            raise
        else:
            # Non-retryable error, re-raise immediately
            logger.error(f"Non-retryable error in coalescing query for KB {kb_id}: {error_msg[:200]}")
            raise


@stamina.retry(on=is_retryable_embedding_error)
async def _generate_query_embedding_with_retry(
    analytiq_client,
    query: str,
    embedding_model: str
) -> List[float]:
    """
    Generate a query embedding with retry logic for transient errors.
    
    Uses stamina retry mechanism for transient errors (rate limits, timeouts, 503 errors).
    
    Args:
        analytiq_client: The analytiq client
        query: Query text to embed
        embedding_model: LiteLLM embedding model string
        
    Returns:
        Embedding vector as a list of floats
        
    Raises:
        Exception: If embedding generation fails after retries
    """
    model_info = litellm.get_model_info(embedding_model)
    provider = model_info.get("provider")
    api_key = await ad.llm.get_llm_key(analytiq_client, provider)
    
    # Generate embedding via LiteLLM
    # This will be retried automatically by stamina if it raises a retryable error
    response = await litellm.aembedding(
        model=embedding_model,
        input=[query],
        api_key=api_key
    )
    
    # Validate response
    if not response or not response.data or len(response.data) == 0:
        raise ValueError(f"Invalid embedding response: no data returned for query")
    
    return response.data[0]["embedding"]
