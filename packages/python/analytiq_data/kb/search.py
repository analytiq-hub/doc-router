"""
Knowledge Base vector search functionality.
"""

import logging
import re
from datetime import datetime, UTC
from typing import List, Dict, Any, Optional, Tuple
from bson import ObjectId
from bson.decimal128 import Decimal128

import litellm
import stamina

import analytiq_data as ad
from .embedding_cache import get_embedding_from_cache, store_embedding_in_cache, compute_chunk_hash
from .errors import is_retryable_embedding_error, is_retryable_vector_index_error

logger = logging.getLogger(__name__)


def _normalize_relevance_score(val: Any) -> Optional[float]:
    """Coerce MongoDB aggregation scores (float, Decimal128, etc.) to float for JSON."""
    if val is None:
        return None
    if isinstance(val, Decimal128):
        return float(val.to_decimal())
    try:
        return float(val)
    except (TypeError, ValueError):
        return None


def get_embedding_cost(response, embedding_model: str) -> float:
    """
    Extract actual cost from a litellm embedding response.
    
    Args:
        response: The litellm embedding response object
        embedding_model: The embedding model name
        
    Returns:
        Actual cost in USD (float)
    """
    try:
        # Try to get cost from hidden params (litellm's automatic cost tracking)
        if hasattr(response, '_hidden_params') and response._hidden_params:
            response_cost = response._hidden_params.get("response_cost")
            if response_cost is not None:
                return float(response_cost)
        
        # Fallback: calculate cost from usage if available
        if hasattr(response, 'usage') and response.usage:
            # Get token count from usage
            total_tokens = 0
            if hasattr(response.usage, 'total_tokens'):
                total_tokens = response.usage.total_tokens
            elif hasattr(response.usage, 'prompt_tokens'):
                total_tokens = response.usage.prompt_tokens
            
            # Get cost per token from litellm model_cost
            if embedding_model in litellm.model_cost:
                cost_info = litellm.model_cost[embedding_model]
                # For embeddings, check if we're using batched pricing
                input_cost_per_token = cost_info.get("input_cost_per_token", 0.0)
                input_cost_per_token_batches = cost_info.get("input_cost_per_token_batches", 0.0)
                
                # Use batched pricing if available and we have multiple inputs
                if input_cost_per_token_batches > 0 and hasattr(response, 'data') and len(response.data) > 1:
                    cost = total_tokens * input_cost_per_token_batches
                else:
                    cost = total_tokens * input_cost_per_token
                
                return float(cost)
        
        # If we can't determine cost, return 0.0
        logger.debug(f"Could not determine cost for embedding model {embedding_model}, returning 0.0")
        return 0.0
        
    except Exception as e:
        logger.warning(f"Error extracting embedding cost: {e}, returning 0.0")
        return 0.0


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
        # Only allow tag_ids filtering
        if key != "tag_ids":
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
    metadata_filter: Optional[Dict[str, Any]] = None,
    upload_date_from: Optional[datetime] = None,
    upload_date_to: Optional[datetime] = None
) -> tuple[Dict[str, Any], Dict[str, Any]]:
    """
    Build filter for MongoDB $vectorSearch.
    
    Args:
        organization_id: Organization ID (required)
        metadata_filter: Optional metadata filters (sanitized)
        upload_date_from: Optional upload date start
        upload_date_to: Optional upload date end
        
    Returns:
        tuple: (vector_search_filter, post_filter)
        - vector_search_filter: Filter to use in $vectorSearch stage (no regex)
        - post_filter: Filter to apply after vector search (supports regex)
    """
    filter_dict = {"organization_id": organization_id}
    post_filter = {}
    
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
    
    # Apply date range filters
    if upload_date_from or upload_date_to:
        date_filter = {}
        if upload_date_from:
            date_filter["$gte"] = upload_date_from
        if upload_date_to:
            date_filter["$lte"] = upload_date_to
        if date_filter:
            filter_dict["metadata_snapshot.upload_date"] = date_filter
    
    return filter_dict, post_filter


def _coerce_object_id_list(values: Any) -> List[Any]:
    """Normalize tag id values for Atlas Search ``in`` operator."""
    if not isinstance(values, list):
        values = [values]
    out: List[Any] = []
    for v in values:
        if isinstance(v, ObjectId):
            out.append(v)
        elif isinstance(v, str):
            try:
                out.append(ObjectId(v))
            except Exception:
                out.append(v)
        else:
            out.append(v)
    return out


def build_atlas_search_filter_clauses(filter_dict: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Map ``build_vector_search_filter`` output to Atlas Search ``compound.filter`` clauses."""
    clauses: List[Dict[str, Any]] = []
    if not filter_dict:
        return clauses
    oid = filter_dict.get("organization_id")
    if oid is not None:
        clauses.append({"equals": {"path": "organization_id", "value": oid}})
    if "metadata_snapshot.tag_ids" in filter_dict:
        v = filter_dict["metadata_snapshot.tag_ids"]
        if isinstance(v, dict) and "$in" in v:
            vals = _coerce_object_id_list(v["$in"])
        elif isinstance(v, list):
            vals = _coerce_object_id_list(v)
        else:
            vals = _coerce_object_id_list([v])
        clauses.append({"in": {"path": "metadata_snapshot.tag_ids", "value": vals}})
    if "metadata_snapshot.upload_date" in filter_dict:
        df = filter_dict["metadata_snapshot.upload_date"]
        rng: Dict[str, Any] = {"path": "metadata_snapshot.upload_date"}
        if isinstance(df, dict):
            if "$gte" in df:
                rng["gte"] = df["$gte"]
            if "$lte" in df:
                rng["lte"] = df["$lte"]
        clauses.append({"range": rng})
    return clauses


def _lexical_search_stage(query_text: str, search_filter: Dict[str, Any]) -> Dict[str, Any]:
    must = [{"text": {"query": query_text, "path": "chunk_text"}}]
    clauses = build_atlas_search_filter_clauses(search_filter)
    compound: Dict[str, Any] = {"must": must}
    if clauses:
        compound["filter"] = clauses
    return {"$search": {"index": "kb_lexical_index", "compound": compound}}


def _fusion_heuristic_weights(query: str) -> Tuple[float, float]:
    """Default RRF weights from query shape (lexical vs semantic)."""
    q = query.strip()
    if not q:
        return 0.5, 0.5
    tokens = q.split()
    n = len(tokens)
    if n >= 8:
        return 0.2, 0.8
    if n <= 3:
        return 0.6, 0.4
    if re.search(r"[A-Z]{2,}[0-9A-Z]|\b[A-Z]{1,4}[0-9]{2,}\b|\b[A-Z0-9_-]{4,}\b", q):
        return 0.7, 0.3
    return 0.4, 0.6


def _branch_candidate_limit(top_k: int) -> int:
    """Per-branch cap before fusion (plan: ~5×k, bounded)."""
    return min(max(5 * top_k, 25), 200)


def _num_candidates_for_vector(branch_limit: int) -> int:
    return max(branch_limit * 20, 200)


def _hybrid_rank_fusion_pipeline(
    query_text: str,
    query_embedding: List[float],
    search_filter: Dict[str, Any],
    post_filter: Dict[str, Any],
    branch_limit: int,
    num_candidates: int,
    skip: int,
    top_k: int,
    w_lex: float,
    w_sem: float,
) -> List[Dict[str, Any]]:
    lexical = [
        _lexical_search_stage(query_text, search_filter),
        {"$limit": branch_limit},
    ]
    vector_stage: Dict[str, Any] = {
        "index": "kb_vector_index",
        "path": "embedding",
        "queryVector": query_embedding,
        "numCandidates": num_candidates,
        "limit": branch_limit,
    }
    if search_filter:
        vector_stage["filter"] = search_filter
    semantic = [
        {"$vectorSearch": vector_stage},
        {"$limit": branch_limit},
    ]
    rank_fusion: Dict[str, Any] = {
        "$rankFusion": {
            "input": {
                "pipelines": {
                    "lexical": lexical,
                    "semantic": semantic,
                }
            },
            "combination": {
                "weights": {
                    "lexical": w_lex,
                    "semantic": w_sem,
                }
            },
        }
    }
    pipeline: List[Dict[str, Any]] = [
        rank_fusion,
        {"$addFields": {"score": {"$meta": "score"}}},
    ]
    if post_filter:
        pipeline.append({"$match": post_filter})
    if skip > 0:
        pipeline.append({"$skip": skip})
    pipeline.append({"$limit": top_k})
    return pipeline


def _vector_only_pipeline(
    query_embedding: List[float],
    search_filter: Dict[str, Any],
    post_filter: Dict[str, Any],
    branch_limit: int,
    num_candidates: int,
    skip: int,
    top_k: int,
    min_vector_score: Optional[float],
) -> List[Dict[str, Any]]:
    inner_limit = branch_limit * 3 if post_filter else skip + top_k
    vector_search_stage: Dict[str, Any] = {
        "index": "kb_vector_index",
        "path": "embedding",
        "queryVector": query_embedding,
        "numCandidates": num_candidates,
        "limit": inner_limit,
    }
    if search_filter:
        vector_search_stage["filter"] = search_filter
    pipeline: List[Dict[str, Any]] = [
        {"$vectorSearch": vector_search_stage},
        {"$addFields": {"score": {"$meta": "vectorSearchScore"}}},
    ]
    if min_vector_score is not None:
        pipeline.append({"$match": {"score": {"$gte": min_vector_score}}})
    if post_filter:
        pipeline.append({"$match": post_filter})
    if skip > 0:
        pipeline.append({"$skip": skip})
    pipeline.append({"$limit": top_k})
    return pipeline


def _rank_fusion_likely_unsupported(err: Exception) -> bool:
    msg = str(err).lower()
    if "rankfusion" in msg or "$rankfusion" in msg:
        return True
    if "unrecognized" in msg and "stage" in msg:
        return True
    if "unknown" in msg and "stage" in msg:
        return True
    if "not supported" in msg and "search" in msg:
        return True
    return False


async def _apply_coalesce_neighbors_deduped(
    vectors_collection,
    search_results: List[Dict[str, Any]],
    organization_id: str,
    coalesce: int,
    kb_id: str,
) -> List[Dict[str, Any]]:
    if coalesce <= 0:
        for r in search_results:
            r["is_matched"] = True
            r["relevance"] = r.get("score")
        return search_results

    doc_chunks_cache: Dict[str, List[Dict[str, Any]]] = {}
    output: List[Dict[str, Any]] = []
    seen: set = set()

    async def _chunks_for_doc(document_id: str) -> List[Dict[str, Any]]:
        if document_id not in doc_chunks_cache:
            doc_chunks_cache[document_id] = await _execute_find_query_with_retry(
                vectors_collection,
                {"document_id": document_id, "organization_id": organization_id},
                kb_id,
            )
        return doc_chunks_cache[document_id]

    for result in search_results:
        document_id = result["document_id"]
        chunk_index = result["chunk_index"]
        score = result.get("score")
        doc_chunks = await _chunks_for_doc(document_id)
        matched_idx = next(
            (i for i, chunk in enumerate(doc_chunks) if chunk["chunk_index"] == chunk_index),
            None,
        )
        if matched_idx is None:
            key = (document_id, chunk_index)
            if key in seen:
                continue
            seen.add(key)
            output.append({**result, "is_matched": True, "relevance": score})
            continue
        for i in range(
            max(0, matched_idx - coalesce),
            min(len(doc_chunks), matched_idx + coalesce + 1),
        ):
            key = (document_id, doc_chunks[i]["chunk_index"])
            if key in seen:
                continue
            seen.add(key)
            output.append({
                **doc_chunks[i],
                "is_matched": i == matched_idx,
                "relevance": score if i == matched_idx else None,
            })
    return output


async def search_knowledge_base(
    analytiq_client,
    kb_id: str,
    query: str,
    organization_id: str,
    top_k: int = 5,
    skip: int = 0,
    metadata_filter: Optional[Dict[str, Any]] = None,
    upload_date_from: Optional[datetime] = None,
    upload_date_to: Optional[datetime] = None,
    coalesce_neighbors: Optional[int] = None
) -> Dict[str, Any]:
    """
    Search a knowledge base: hybrid retrieval ($rankFusion over lexical + vector) when the query
    is non-empty. Falls back to vector-only if the query is empty or $rankFusion is unavailable.

    ``min_vector_score`` on the KB applies only on that vector-only path (empty query or fusion failure).
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
            query_embedding, embedding_cost = await _generate_query_embedding_with_retry(
                analytiq_client,
                query,
                embedding_model
            )
            
            # Cache the query embedding
            await store_embedding_in_cache(analytiq_client, query_hash, embedding_model, query_embedding)
            
            # Record SPU usage: 1 SPU per query embedding generated (cache miss)
            try:
                # Get provider using the standard method
                provider = ad.llm.get_llm_model_provider(embedding_model)
                if provider:
                    await ad.payments.record_spu_usage(
                        org_id=organization_id,
                        spus=1,  # 1 SPU per query embedding
                        llm_provider=provider,
                        llm_model=embedding_model,
                        actual_cost=embedding_cost
                    )
                    logger.info(f"Recorded 1 SPU usage for query embedding generated, actual cost: ${embedding_cost:.6f}")
            except Exception as e:
                logger.error(f"Error recording SPU usage for query embedding: {e}")
                # Don't fail search if SPU recording fails
            
        except Exception as e:
            logger.error(f"Error generating query embedding: {e}")
            raise ValueError(f"Failed to generate query embedding: {str(e)}")
    
    # Build filters (vector search filter and post-filter for regex)
    search_filter, post_filter = build_vector_search_filter(
        organization_id=organization_id,
        metadata_filter=metadata_filter,
        upload_date_from=upload_date_from,
        upload_date_to=upload_date_to
    )
    
    collection_name = f"kb_vectors_{kb_id}"
    vectors_collection = db[collection_name]

    branch_limit = _branch_candidate_limit(top_k)
    num_candidates = _num_candidates_for_vector(branch_limit)

    use_hybrid = bool(query.strip())
    w_lex, w_sem = _fusion_heuristic_weights(query)

    search_results: List[Dict[str, Any]] = []
    if use_hybrid:
        try:
            pipeline = _hybrid_rank_fusion_pipeline(
                query_text=query,
                query_embedding=query_embedding,
                search_filter=search_filter,
                post_filter=post_filter,
                branch_limit=branch_limit,
                num_candidates=num_candidates,
                skip=skip,
                top_k=top_k,
                w_lex=w_lex,
                w_sem=w_sem,
            )
            search_results = await _execute_vector_search_with_retry(
                vectors_collection,
                pipeline,
                top_k,
                kb_id,
            )
        except Exception as e:
            if _rank_fusion_likely_unsupported(e):
                logger.warning(
                    "Hybrid rank fusion failed; falling back to vector search: %s",
                    e,
                )
                use_hybrid = False
            else:
                raise

    if not use_hybrid:
        min_vs = kb.get("min_vector_score")
        pipeline = _vector_only_pipeline(
            query_embedding=query_embedding,
            search_filter=search_filter,
            post_filter=post_filter,
            branch_limit=branch_limit,
            num_candidates=num_candidates,
            skip=skip,
            top_k=top_k,
            min_vector_score=min_vs,
        )
        search_results = await _execute_vector_search_with_retry(
            vectors_collection,
            pipeline,
            top_k,
            kb_id,
        )

    total_count = len(search_results) + skip if len(search_results) == top_k else len(search_results) + skip

    if coalesce > 0 and search_results:
        search_results = await _apply_coalesce_neighbors_deduped(
            vectors_collection,
            search_results,
            organization_id,
            coalesce,
            kb_id,
        )
    else:
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
            "relevance": _normalize_relevance_score(result.get("relevance")),
            "chunk_index": result.get("chunk_index", 0),
            "is_matched": result.get("is_matched", True),
            "indexed_text_start": result.get("indexed_text_start"),
            "indexed_text_end": result.get("indexed_text_end"),
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
) -> Tuple[List[float], float]:
    """
    Generate a query embedding with retry logic for transient errors.
    
    Uses stamina retry mechanism for transient errors (rate limits, timeouts, 503 errors).
    
    Args:
        analytiq_client: The analytiq client
        query: Query text to embed
        embedding_model: LiteLLM embedding model string
        
    Returns:
        Tuple of (embedding vector as a list of floats, actual cost in USD)
        
    Raises:
        Exception: If embedding generation fails after retries
    """
    # Get provider using the standard method
    provider = ad.llm.get_llm_model_provider(embedding_model)
    if provider is None:
        raise ValueError(f"Could not determine provider for model {embedding_model}")
    
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
    
    # Extract actual cost from response
    actual_cost = get_embedding_cost(response, embedding_model)
    
    return response.data[0]["embedding"], actual_cost
