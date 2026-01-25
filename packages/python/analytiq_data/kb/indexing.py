"""
Knowledge Base indexing logic.

Handles chunking, embedding generation, caching, and atomic vector storage.
"""

import logging
import warnings
from datetime import datetime, UTC
from typing import List, Dict, Any, Optional, Tuple
from bson import ObjectId
import tiktoken
import litellm
import stamina

import analytiq_data as ad
from .embedding_cache import (
    compute_chunk_hash,
    get_embedding_from_cache,
    store_embedding_in_cache
)
from .errors import (
    is_retryable_embedding_error,
    is_permanent_embedding_error,
    set_kb_status_to_error
)

logger = logging.getLogger(__name__)

try:
    from chonkie import (
        TokenChunker,
        SentenceChunker,
        RecursiveChunker,
        OverlapRefinery
    )
    CHONKIE_AVAILABLE = True
except ImportError:
    CHONKIE_AVAILABLE = False
    logger.warning("Chonkie not available. KB indexing will not work.")

# Disabled chunker types (require sentence_transformers which is too large)
DISABLED_CHUNKER_TYPES = ["semantic", "late", "sdpm"]

# Embedding batch size for LiteLLM API calls
EMBEDDING_BATCH_SIZE = 100


class Chunk:
    """Represents a text chunk with metadata."""
    def __init__(self, text: str, chunk_index: int, token_count: int):
        self.text = text
        self.chunk_index = chunk_index
        self.token_count = token_count
        self.hash = compute_chunk_hash(text)


async def chunk_text(
    text: str,
    chunker_type: str,
    chunk_size: int,
    chunk_overlap: int
) -> List[Chunk]:
    """
    Chunk text using Chonkie.
    
    Args:
        text: The text to chunk
        chunker_type: Chonkie chunker type ("token", "word", "sentence", "recursive")
        chunk_size: Target tokens per chunk
        chunk_overlap: Overlap tokens between chunks
        
    Returns:
        List of Chunk objects
    """
    if not CHONKIE_AVAILABLE:
        raise RuntimeError("Chonkie is not available. Please install chonkie package.")
    
    if not text or not text.strip():
        return []
    
    # Check if chunker type is disabled
    if chunker_type in DISABLED_CHUNKER_TYPES:
        raise ValueError(
            f"Chunker type '{chunker_type}' is disabled as it requires sentence_transformers "
            f"(large dependency). Supported types: token, word, sentence, recursive"
        )
    
    try:
        # Map chunker_type to chonkie chunker class
        # Chunkers that support chunk_overlap directly
        chunkers_with_overlap = {
            "token": TokenChunker,
            "word": TokenChunker,  # Use TokenChunker with word tokenizer
            "sentence": SentenceChunker
        }
        
        # Chunkers that need OverlapRefinery for overlap
        chunkers_without_overlap = {
            "recursive": RecursiveChunker
        }
        
        # Create chunker based on type
        if chunker_type in chunkers_with_overlap:
            ChunkerClass = chunkers_with_overlap[chunker_type]
            # For word tokenizer, use TokenChunker with word tokenizer
            if chunker_type == "word":
                chunker = ChunkerClass(
                    tokenizer="word",
                    chunk_size=chunk_size,
                    chunk_overlap=chunk_overlap
                )
            else:
                chunker = ChunkerClass(
                    chunk_size=chunk_size,
                    chunk_overlap=chunk_overlap
                )
            # Chunk the text
            chonkie_chunks = chunker.chunk(text)
            
        elif chunker_type in chunkers_without_overlap:
            ChunkerClass = chunkers_without_overlap[chunker_type]
            # Create chunker without overlap
            chunker = ChunkerClass(chunk_size=chunk_size)
            # Chunk the text
            chonkie_chunks = chunker.chunk(text)
            
            # Apply overlap using OverlapRefinery if overlap > 0
            if chunk_overlap > 0:
                refinery = OverlapRefinery(
                    context_size=chunk_overlap,
                    mode="token"
                )
                # Suppress warning about context size being greater than chunk size
                # This can happen with recursive chunker when chunks are smaller than expected
                with warnings.catch_warnings():
                    warnings.filterwarnings("ignore", message=".*Context size is greater than the chunk size.*", category=UserWarning, module="chonkie.refinery.overlap")
                    chonkie_chunks = refinery.refine(chonkie_chunks)
        else:
            raise ValueError(f"Unknown chunker_type: {chunker_type}. Supported types: {list(chunkers_with_overlap.keys()) + list(chunkers_without_overlap.keys())}")
        
        # Convert chonkie Chunk objects to our Chunk objects with token counting
        encoding = tiktoken.get_encoding("cl100k_base")  # Used by OpenAI models
        result = []
        for idx, chonkie_chunk in enumerate(chonkie_chunks):
            chunk_text = chonkie_chunk.text
            token_count = len(encoding.encode(chunk_text))
            result.append(Chunk(chunk_text, idx, token_count))
        
        logger.info(f"Chunked text into {len(result)} chunks using {chunker_type} chunker")
        return result
        
    except Exception as e:
        logger.error(f"Error chunking text with {chunker_type}: {e}")
        raise


@stamina.retry(on=is_retryable_embedding_error)
async def generate_embeddings_batch(
    analytiq_client,
    texts: List[str],
    embedding_model: str
) -> List[List[float]]:
    """
    Generate embeddings for a batch of texts using LiteLLM.
    
    Uses stamina retry mechanism for transient errors (rate limits, timeouts, 503 errors).
    
    Args:
        analytiq_client: The analytiq client
        texts: List of text strings to embed
        embedding_model: LiteLLM embedding model string
        
    Returns:
        List of embedding vectors
        
    Raises:
        Exception: If embedding generation fails after retries
    """
    if not texts:
        return []
    
    # Get provider and API key using the standard method
    provider = ad.llm.get_llm_model_provider(embedding_model)
    if provider is None:
        raise ValueError(f"Could not determine provider for model {embedding_model}")
    
    api_key = await ad.llm.get_llm_key(analytiq_client, provider)
    
    if not api_key:
        raise ValueError(f"No API key found for provider {provider}")
    
    # Generate embeddings via LiteLLM
    # This will be retried automatically by stamina if it raises a retryable error
    response = await litellm.aembedding(
        model=embedding_model,
        input=texts,
        api_key=api_key
    )
    
    # Extract embeddings from response
    embeddings = [item["embedding"] for item in response.data]
    
    logger.info(f"Generated {len(embeddings)} embeddings using {embedding_model}")
    return embeddings


async def get_or_generate_embeddings(
    analytiq_client,
    chunks: List[Chunk],
    embedding_model: str,
    organization_id: str
) -> Tuple[List[List[float]], int]:
    """
    Get embeddings from cache or generate new ones.
    
    Args:
        analytiq_client: The analytiq client
        chunks: List of Chunk objects
        embedding_model: LiteLLM embedding model string
        organization_id: Organization ID for SPU metering
        
    Returns:
        Tuple of (embeddings list, cache_miss_count)
    """
    if not chunks:
        return [], 0
    
    embeddings = []
    cache_misses = []
    cache_miss_indices = []
    
    # Check cache for each chunk
    for idx, chunk in enumerate(chunks):
        cached_embedding = await get_embedding_from_cache(
            analytiq_client,
            chunk.hash,
            embedding_model
        )
        
        if cached_embedding:
            embeddings.append(cached_embedding)
        else:
            embeddings.append(None)  # Placeholder
            cache_misses.append(chunk.text)
            cache_miss_indices.append(idx)
    
    # Generate embeddings for cache misses in batches
    if cache_misses:
        cache_miss_count = len(cache_misses)
        logger.info(f"Generating {cache_miss_count} embeddings (cache misses)")
        
        # Check SPU credits before generating embeddings (1 SPU per embedding)
        # This will raise SPUCreditException if insufficient credits
        await ad.payments.check_spu_limits(organization_id, cache_miss_count)
        
        generated_embeddings = []
        
        # Get provider for SPU metering using the standard method
        provider = ad.llm.get_llm_model_provider(embedding_model)
        
        # Process in batches
        for i in range(0, len(cache_misses), EMBEDDING_BATCH_SIZE):
            batch = cache_misses[i:i + EMBEDDING_BATCH_SIZE]
            batch_embeddings = await generate_embeddings_batch(
                analytiq_client,
                batch,
                embedding_model
            )
            generated_embeddings.extend(batch_embeddings)
        
        # Store in cache and fill in embeddings list
        for idx, (cache_miss_idx, embedding) in enumerate(zip(cache_miss_indices, generated_embeddings)):
            chunk = chunks[cache_miss_idx]
            await store_embedding_in_cache(
                analytiq_client,
                chunk.hash,
                embedding_model,
                embedding
            )
            embeddings[cache_miss_idx] = embedding
        
        # Record SPU usage: 1 SPU per embedding generated (cache miss)
        if cache_miss_count > 0:
            try:
                await ad.payments.record_spu_usage(
                    org_id=organization_id,
                    spus=cache_miss_count,  # 1 SPU per embedding
                    llm_provider=provider,
                    llm_model=embedding_model
                )
                logger.info(f"Recorded {cache_miss_count} SPU usage for {cache_miss_count} embedding(s) generated")
            except Exception as e:
                logger.error(f"Error recording SPU usage for embeddings: {e}")
                # Don't fail indexing if SPU recording fails
    
    cache_miss_count = len(cache_misses)
    logger.info(f"Embedding lookup complete: {len(chunks)} total, {cache_miss_count} cache misses, {len(chunks) - cache_miss_count} cache hits")
    
    return embeddings, cache_miss_count


async def index_document_in_kb(
    analytiq_client,
    kb_id: str,
    document_id: str,
    organization_id: str
) -> Dict[str, Any]:
    """
    Index a document into a knowledge base.
    
    This implements the "Blue-Green" atomic swap pattern:
    1. Chunk the document text
    2. Get or generate embeddings (with caching)
    3. Atomically replace old vectors with new ones
    4. Update document_index and KB stats
    
    Args:
        analytiq_client: The analytiq client
        kb_id: Knowledge base ID
        document_id: Document ID to index
        organization_id: Organization ID
        
    Returns:
        Dict with indexing results (chunk_count, cache_misses, etc.)
    """
    db = analytiq_client.mongodb_async[analytiq_client.env]
    
    # Get KB configuration
    kb = await db.knowledge_bases.find_one({"_id": ObjectId(kb_id), "organization_id": organization_id})
    if not kb:
        raise ValueError(f"Knowledge base {kb_id} not found")
    
    if kb.get("status") == "error":
        raise ValueError(f"Knowledge base {kb_id} is in error state")
    
    # Get document
    doc = await ad.common.doc.get_doc(analytiq_client, document_id, organization_id)
    if not doc:
        raise ValueError(f"Document {document_id} not found")
    
    # Get text to chunk (OCR text for OCR-supported files, original content for .txt/.md files)
    text_to_chunk = await ad.llm.get_extracted_text(analytiq_client, document_id)
    if not text_to_chunk or not text_to_chunk.strip():
        logger.warning(f"Document {document_id} has no extractable text. Skipping indexing.")
        return {
            "chunk_count": 0,
            "cache_misses": 0,
            "skipped": True,
            "reason": "no_text"
        }
    
    # Chunk the text
    chunks = await chunk_text(
        text_to_chunk,
        kb["chunker_type"],
        kb["chunk_size"],
        kb["chunk_overlap"]
    )
    
    if not chunks:
        logger.warning(f"Document {document_id} produced no chunks. Skipping indexing.")
        return {
            "chunk_count": 0,
            "cache_misses": 0,
            "skipped": True,
            "reason": "no_chunks"
        }
    
    # Get or generate embeddings
    embeddings, cache_miss_count = await get_or_generate_embeddings(
        analytiq_client,
        chunks,
        kb["embedding_model"],
        organization_id
    )
    
    # Prepare vectors for insertion
    collection_name = f"kb_vectors_{kb_id}"
    vectors_collection = db[collection_name]
    
    # Get document metadata snapshot for filtering
    metadata_snapshot = {
        "document_name": doc.get("user_file_name", ""),
        "tag_ids": doc.get("tag_ids", []),
        "upload_date": doc.get("upload_date"),
        "metadata": doc.get("metadata", {})
    }
    
    now = datetime.now(UTC)
    new_vectors = []
    for chunk, embedding in zip(chunks, embeddings):
        new_vectors.append({
            "organization_id": organization_id,
            "document_id": document_id,
            "chunk_index": chunk.chunk_index,
            "chunk_hash": chunk.hash,
            "chunk_text": chunk.text,
            "embedding": embedding,
            "token_count": chunk.token_count,
            "metadata_snapshot": metadata_snapshot,
            "indexed_at": now
        })
    
    # Atomic swap: Use MongoDB transaction for blue-green pattern
    try:
        client = analytiq_client.mongodb_async
        async with await client.start_session() as session:
            async with session.start_transaction():
                # Delete old vectors for this document
                await vectors_collection.delete_many(
                    {"document_id": document_id},
                    session=session
                )
                
                # Insert new vectors
                if new_vectors:
                    await vectors_collection.insert_many(new_vectors, session=session)
                
                # Update or insert document_index entry
                await db.document_index.update_one(
                    {
                        "kb_id": kb_id,
                        "document_id": document_id
                    },
                    {
                        "$set": {
                            "organization_id": organization_id,
                            "kb_id": kb_id,
                            "document_id": document_id,
                            "chunk_count": len(new_vectors),
                            "indexed_at": now
                        }
                    },
                    upsert=True,
                    session=session
                )
                
                # Update KB stats
                # Count total documents and chunks for this KB
                total_docs = await db.document_index.count_documents({"kb_id": kb_id}, session=session)
                total_chunks_cursor = db.document_index.aggregate([
                    {"$match": {"kb_id": kb_id}},
                    {"$group": {"_id": None, "total": {"$sum": "$chunk_count"}}}
                ], session=session)
                total_chunks = await total_chunks_cursor.to_list(length=1)
                total_chunks_count = total_chunks[0]["total"] if total_chunks else 0
                
                await db.knowledge_bases.update_one(
                    {"_id": ObjectId(kb_id)},
                    {
                        "$set": {
                            "document_count": total_docs,
                            "chunk_count": total_chunks_count,
                            "updated_at": now
                        }
                    },
                    session=session
                )
        
        logger.info(f"Successfully indexed document {document_id} into KB {kb_id}: {len(new_vectors)} chunks")
        
        return {
            "chunk_count": len(new_vectors),
            "cache_misses": cache_miss_count,
            "cache_hits": len(chunks) - cache_miss_count,
            "skipped": False
        }
        
    except Exception as e:
        logger.error(f"Error indexing document {document_id} into KB {kb_id}: {e}")
        
        # Check if this is a permanent error that should set KB status to error
        if is_permanent_embedding_error(e):
            error_msg = f"Permanent error indexing document {document_id}: {str(e)}"
            try:
                await set_kb_status_to_error(analytiq_client, kb_id, organization_id, error_msg)
            except Exception as status_error:
                logger.error(f"Failed to set KB status to error: {status_error}")
        
        # Transaction will rollback automatically
        raise


async def remove_document_from_kb(
    analytiq_client,
    kb_id: str,
    document_id: str,
    organization_id: str
) -> None:
    """
    Remove a document from a knowledge base.
    
    Args:
        analytiq_client: The analytiq client
        kb_id: Knowledge base ID
        document_id: Document ID to remove
        organization_id: Organization ID
    """
    db = analytiq_client.mongodb_async[analytiq_client.env]
    collection_name = f"kb_vectors_{kb_id}"
    vectors_collection = db[collection_name]
    
    try:
        client = analytiq_client.mongodb_async
        async with await client.start_session() as session:
            async with session.start_transaction():
                # Delete vectors
                await vectors_collection.delete_many(
                    {"document_id": document_id},
                    session=session
                )
                
                # Delete document_index entry
                await db.document_index.delete_one(
                    {"kb_id": kb_id, "document_id": document_id},
                    session=session
                )
                
                # Update KB stats
                total_docs = await db.document_index.count_documents({"kb_id": kb_id}, session=session)
                total_chunks_cursor = db.document_index.aggregate([
                    {"$match": {"kb_id": kb_id}},
                    {"$group": {"_id": None, "total": {"$sum": "$chunk_count"}}}
                ], session=session)
                total_chunks = await total_chunks_cursor.to_list(length=1)
                total_chunks_count = total_chunks[0]["total"] if total_chunks else 0
                
                await db.knowledge_bases.update_one(
                    {"_id": ObjectId(kb_id)},
                    {
                        "$set": {
                            "document_count": total_docs,
                            "chunk_count": total_chunks_count,
                            "updated_at": datetime.now(UTC)
                        }
                    },
                    session=session
                )
        
        logger.info(f"Removed document {document_id} from KB {kb_id}")
        
    except Exception as e:
        logger.error(f"Error removing document {document_id} from KB {kb_id}: {e}")
        raise
