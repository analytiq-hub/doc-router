# knowledge_bases.py

# Standard library imports
import logging
import hashlib
from datetime import datetime, UTC
from typing import Optional, List, Dict, Literal, Any
from pydantic import BaseModel, Field, field_validator, model_validator

# Third-party imports
from fastapi import APIRouter, Depends, HTTPException, Query, Body
from bson import ObjectId

# Local imports
import analytiq_data as ad
from app.auth import get_org_user
from app.models import User
from app.routes.payments import SPUCreditException

# Configure logger
logger = logging.getLogger(__name__)

# Initialize FastAPI router
knowledge_bases_router = APIRouter(tags=["knowledge-bases"])

# KB Configuration Constants
VALID_CHUNKER_TYPES = ["token", "word", "sentence", "recursive"]
# Note: "semantic", "late", and "sdpm" are disabled as they require sentence_transformers (large dependency)
DEFAULT_CHUNKER_TYPE = "recursive"  # Uses RecursiveChunker from chonkie
DEFAULT_CHUNK_SIZE = 512
DEFAULT_CHUNK_OVERLAP = 128
DEFAULT_EMBEDDING_MODEL = "text-embedding-3-small"
DEFAULT_COALESCE_NEIGHBORS = 0
MIN_CHUNK_SIZE = 50
MAX_CHUNK_SIZE = 2000
MAX_COALESCE_NEIGHBORS = 5

# KB Models
class KnowledgeBaseConfig(BaseModel):
    name: str = Field(..., description="Human-readable name for the KB")
    description: str = Field(default="", description="Optional description")
    tag_ids: List[str] = Field(default_factory=list, description="Tag IDs for auto-indexing")
    chunker_type: str = Field(default=DEFAULT_CHUNKER_TYPE, description="Chonkie chunker type")
    chunk_size: int = Field(default=DEFAULT_CHUNK_SIZE, description="Target tokens per chunk")
    chunk_overlap: int = Field(default=DEFAULT_CHUNK_OVERLAP, description="Overlap tokens between chunks")
    embedding_model: str = Field(default=DEFAULT_EMBEDDING_MODEL, description="LiteLLM embedding model")
    coalesce_neighbors: int = Field(default=DEFAULT_COALESCE_NEIGHBORS, description="Number of neighboring chunks to include (0-5)")
    
    @field_validator('chunker_type')
    @classmethod
    def validate_chunker_type(cls, v):
        # "recursive" is a valid chunker type (uses RecursiveChunker)
        if v not in VALID_CHUNKER_TYPES:
            raise ValueError(f"chunker_type must be one of {VALID_CHUNKER_TYPES}")
        return v
    
    @field_validator('chunk_size')
    @classmethod
    def validate_chunk_size(cls, v):
        if v < MIN_CHUNK_SIZE or v > MAX_CHUNK_SIZE:
            raise ValueError(f"chunk_size must be between {MIN_CHUNK_SIZE} and {MAX_CHUNK_SIZE}")
        return v
    
    @field_validator('chunk_overlap')
    @classmethod
    def validate_chunk_overlap(cls, v):
        if v < 0:
            raise ValueError("chunk_overlap must be non-negative")
        return v
    
    @model_validator(mode='after')
    def validate_chunk_overlap_vs_size(self):
        if self.chunk_overlap >= self.chunk_size:
            raise ValueError("chunk_overlap must be less than chunk_size")
        return self
    
    @field_validator('coalesce_neighbors')
    @classmethod
    def validate_coalesce_neighbors(cls, v):
        if v < 0 or v > MAX_COALESCE_NEIGHBORS:
            raise ValueError(f"coalesce_neighbors must be between 0 and {MAX_COALESCE_NEIGHBORS}")
        return v

class KnowledgeBaseUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    tag_ids: Optional[List[str]] = None
    coalesce_neighbors: Optional[int] = None
    
    @field_validator('coalesce_neighbors')
    @classmethod
    def validate_coalesce_neighbors(cls, v):
        if v is not None and (v < 0 or v > MAX_COALESCE_NEIGHBORS):
            raise ValueError(f"coalesce_neighbors must be between 0 and {MAX_COALESCE_NEIGHBORS}")
        return v

class KnowledgeBase(KnowledgeBaseConfig):
    kb_id: str
    embedding_dimensions: int
    status: Literal["indexing", "active", "error"]
    document_count: int
    chunk_count: int
    created_at: datetime
    updated_at: datetime

class ListKnowledgeBasesResponse(BaseModel):
    knowledge_bases: List[KnowledgeBase]
    total_count: int

class KnowledgeBaseDocument(BaseModel):
    document_id: str
    document_name: str
    chunk_count: int
    indexed_at: datetime

class ListKBDocumentsResponse(BaseModel):
    documents: List[KnowledgeBaseDocument]
    total_count: int

class KBSearchRequest(BaseModel):
    query: str = Field(..., description="Search query text")
    top_k: int = Field(default=5, ge=1, le=20, description="Number of results to return")
    skip: int = Field(default=0, ge=0, description="Pagination offset")
    document_ids: Optional[List[str]] = Field(default=None, description="Filter by specific document IDs")
    metadata_filter: Optional[Dict[str, Any]] = Field(default=None, description="Metadata filters (sanitized server-side)")
    upload_date_from: Optional[datetime] = Field(default=None, description="Filter by upload date from")
    upload_date_to: Optional[datetime] = Field(default=None, description="Filter by upload date to")
    coalesce_neighbors: Optional[int] = Field(default=None, ge=0, le=MAX_COALESCE_NEIGHBORS, description="Override KB default")

class KBSearchResult(BaseModel):
    content: str
    source: str
    document_id: str
    relevance: Optional[float]
    chunk_index: int
    is_matched: bool

class KBSearchResponse(BaseModel):
    results: List[KBSearchResult]
    query: str
    total_count: int
    skip: int
    top_k: int

# Helper Functions
async def detect_embedding_dimensions(embedding_model: str, analytiq_client) -> int:
    """
    Auto-detect embedding dimensions by making a test call to LiteLLM.
    
    Args:
        embedding_model: LiteLLM model string
        analytiq_client: AnalytiqClient instance
        
    Returns:
        Dimension count
        
    Raises:
        HTTPException: If embedding model is invalid or API call fails
    """
    try:
        import litellm
        
        # Get provider and API key
        provider = litellm.get_model_info(embedding_model).get("provider", "openai")
        api_key = await ad.llm.get_llm_key(analytiq_client, provider)
        
        # Make test embedding call
        response = await litellm.aembedding(
            model=embedding_model,
            input=["test"],
            api_key=api_key
        )
        
        if not response.data or len(response.data) == 0:
            raise HTTPException(status_code=400, detail="Invalid embedding model response")
        
        dimensions = len(response.data[0]["embedding"])
        return dimensions
        
    except Exception as e:
        logger.error(f"Failed to detect embedding dimensions for {embedding_model}: {e}")
        raise HTTPException(
            status_code=400,
            detail=f"Failed to detect embedding dimensions: {str(e)}"
        )

async def wait_for_vector_index_ready(
    analytiq_client,
    kb_id: str,
    max_wait_seconds: int = 30,
    poll_interval: float = 0.5
) -> None:
    """
    Wait for the vector search index to be ready (not in INITIAL_SYNC or NOT_STARTED state).
    
    Args:
        analytiq_client: AnalytiqClient instance
        kb_id: Knowledge base ID
        max_wait_seconds: Maximum time to wait in seconds
        poll_interval: Time between polls in seconds
    """
    import asyncio
    db = ad.common.get_async_db(analytiq_client)
    collection_name = f"kb_vectors_{kb_id}"
    
    max_attempts = int(max_wait_seconds / poll_interval)
    for i in range(max_attempts):
        try:
            # Try a minimal vector search query to check if index is ready
            # Use a non-zero vector to avoid "zero vector" errors
            test_vector = [0.001] * 1536  # Small non-zero values
            test_result = await db[collection_name].aggregate([
                {
                    "$vectorSearch": {
                        "index": "kb_vector_index",
                        "path": "embedding",
                        "queryVector": test_vector,
                        "numCandidates": 1,
                        "limit": 1
                    }
                }
            ]).to_list(length=1)
            # If we get here without an error, the index is ready
            logger.debug(f"Vector index for KB {kb_id} is ready after {i * poll_interval:.1f}s")
            return
        except Exception as e:
            error_msg = str(e)
            # Check for index building states
            if ("INITIAL_SYNC" in error_msg or "NOT_STARTED" in error_msg or 
                "not initialized" in error_msg.lower()):
                # Index is still building, wait and retry
                if i < max_attempts - 1:
                    await asyncio.sleep(poll_interval)
                    continue
                else:
                    state = "INITIAL_SYNC" if "INITIAL_SYNC" in error_msg else ("NOT_STARTED" if "NOT_STARTED" in error_msg else "not initialized")
                    logger.warning(f"Vector index for KB {kb_id} still building after {max_wait_seconds}s (state: {state})")
                    # Don't raise - let the actual search handle the error
                    return
            elif "zero vector" in error_msg.lower():
                # This is a different error - the index might be ready but we used a zero vector
                # Try again with a non-zero vector (shouldn't happen with our test_vector, but just in case)
                if i < max_attempts - 1:
                    await asyncio.sleep(poll_interval)
                    continue
            else:
                # Different error - might be that index doesn't exist or other issue
                # For test purposes, if it's not a building state error, log and continue
                if "no such command" not in error_msg.lower() and "not found" not in error_msg.lower():
                    logger.debug(f"Vector index check for KB {kb_id} returned non-building error: {error_msg[:100]}")
                    # Assume it might be ready and let the actual search handle it
                    return
                # If it's a "not found" type error, wait a bit more
                if i < max_attempts - 1:
                    await asyncio.sleep(poll_interval)
                    continue
                raise

async def create_vector_search_index(
    analytiq_client,
    kb_id: str,
    embedding_dimensions: int,
    organization_id: str
) -> None:
    """
    Create a vector search index on the KB's vector collection.
    
    Args:
        analytiq_client: AnalytiqClient instance
        kb_id: Knowledge base ID
        embedding_dimensions: Number of dimensions in the embedding vectors
        organization_id: Organization ID for filtering
        
    Raises:
        HTTPException: If index creation fails
    """
    db = ad.common.get_async_db(analytiq_client)
    collection_name = f"kb_vectors_{kb_id}"
    
    # Ensure the collection exists before creating the search index
    # MongoDB requires the collection to exist before creating a search index
    # We ensure it exists by inserting a temporary document (keep it until index is created)
    collection = db[collection_name]
    temp_doc_inserted = False
    try:
        # Insert a temporary document to ensure collection exists
        # Keep it until after index creation - mongot may need the collection to have content
        await collection.insert_one({"_id": "temp_init", "temp": True})
        temp_doc_inserted = True
        logger.info(f"Ensured collection {collection_name} exists for KB {kb_id}")
    except Exception as e:
        # If insert fails, collection might not exist - try creating it explicitly
        logger.warning(f"Could not ensure collection exists via insert, trying create_collection: {e}")
        try:
            await db.create_collection(collection_name)
            # After creating, insert temp doc to make it visible to mongot
            await collection.insert_one({"_id": "temp_init", "temp": True})
            temp_doc_inserted = True
            logger.info(f"Created collection {collection_name} for KB {kb_id}")
        except Exception as create_error:
            # Collection might already exist, that's okay - try inserting temp doc
            if "already exists" not in str(create_error).lower() and "NamespaceExists" not in str(create_error):
                logger.warning(f"Collection creation issue (may already exist): {create_error}")
            try:
                await collection.insert_one({"_id": "temp_init", "temp": True})
                temp_doc_inserted = True
            except Exception:
                pass  # Collection exists but we can't insert - proceed anyway
    
    # For MongoDB Atlas: Use Atlas Search API
    # For self-hosted MongoDB 8.2+: Use createSearchIndexes command
    index_definition = {
        "name": "kb_vector_index",
        "type": "vectorSearch",
        "definition": {
            "fields": [
                {
                    "type": "vector",
                    "path": "embedding",
                    "numDimensions": embedding_dimensions,
                    "similarity": "cosine"
                },
                {
                    "type": "filter",
                    "path": "organization_id"
                }
            ]
        }
    }
    
    # Create the search index - fail if this doesn't work
    try:
        # Use createSearchIndexes command (works for both Atlas and self-hosted 8.2+)
        await db.command({
            "createSearchIndexes": collection_name,
            "indexes": [index_definition]
        })
        logger.info(f"Created vector search index for KB {kb_id}")
        
        # Clean up temporary document after successful index creation
        if temp_doc_inserted:
            try:
                await collection.delete_one({"_id": "temp_init"})
            except Exception:
                pass  # Ignore cleanup errors
    except Exception as e:
        logger.error(f"Failed to create vector search index for KB {kb_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create vector search index: {str(e)}. Ensure MongoDB supports vector search (Atlas or 8.2+)."
        )

async def validate_tag_ids(tag_ids: List[str], organization_id: str, analytiq_client) -> None:
    """
    Validate that all tag IDs exist and belong to the organization.
    
    Args:
        tag_ids: List of tag IDs to validate
        organization_id: Organization ID
        analytiq_client: AnalytiqClient instance
        
    Raises:
        HTTPException: If any tag ID is invalid
    """
    if not tag_ids:
        return
    
    db = ad.common.get_async_db(analytiq_client)
    
    # Convert to ObjectIds for query
    tag_object_ids = []
    for tag_id in tag_ids:
        try:
            tag_object_ids.append(ObjectId(tag_id))
        except Exception:
            raise HTTPException(status_code=400, detail=f"Invalid tag ID format: {tag_id}")
    
    # Check all tags exist and belong to org
    tags = await db.tags.find({
        "_id": {"$in": tag_object_ids},
        "organization_id": organization_id
    }).to_list(None)
    
    found_tag_ids = {str(tag["_id"]) for tag in tags}
    missing_tags = set(tag_ids) - found_tag_ids
    
    if missing_tags:
        raise HTTPException(
            status_code=400,
            detail=f"Tags not found or not accessible: {list(missing_tags)}"
        )

# API Endpoints
@knowledge_bases_router.post("/v0/orgs/{organization_id}/knowledge-bases", response_model=KnowledgeBase)
async def create_knowledge_base(
    organization_id: str,
    config: KnowledgeBaseConfig = Body(...),
    current_user: User = Depends(get_org_user)
):
    """Create a new knowledge base"""
    logger.info(f"Creating KB for org {organization_id}: {config.name}")
    
    analytiq_client = ad.common.get_analytiq_client()
    db = ad.common.get_async_db(analytiq_client)
    
    # Validate tag IDs
    await validate_tag_ids(config.tag_ids, organization_id, analytiq_client)
    
    # Auto-detect embedding dimensions
    embedding_dimensions = await detect_embedding_dimensions(config.embedding_model, analytiq_client)
    
    # Create KB document
    now = datetime.now(UTC)
    kb_doc = {
        "organization_id": organization_id,
        "name": config.name,
        "description": config.description,
        "tag_ids": config.tag_ids,
        "chunker_type": config.chunker_type,
        "chunk_size": config.chunk_size,
        "chunk_overlap": config.chunk_overlap,
        "embedding_model": config.embedding_model,
        "embedding_dimensions": embedding_dimensions,
        "coalesce_neighbors": config.coalesce_neighbors,
        "status": "indexing",  # Will be set to "active" after index creation
        "document_count": 0,
        "chunk_count": 0,
        "created_at": now,
        "updated_at": now
    }
    
    result = await db.knowledge_bases.insert_one(kb_doc)
    kb_id = str(result.inserted_id)
    
    # Create vector search index (await completion)
    # For a new empty KB, this should be fast
    # If this fails, we'll delete the KB and return an error
    try:
        await create_vector_search_index(
            analytiq_client,
            kb_id,
            embedding_dimensions,
            organization_id
        )
        # Update status to active after successful index creation
        await db.knowledge_bases.update_one(
            {"_id": ObjectId(kb_id)},
            {"$set": {"status": "active", "updated_at": datetime.now(UTC)}}
        )
    except HTTPException:
        # If index creation fails, clean up the KB and re-raise the exception
        await db.knowledge_bases.delete_one({"_id": ObjectId(kb_id)})
        # Also clean up the vector collection if it was created
        try:
            await db[f"kb_vectors_{kb_id}"].drop()
        except Exception:
            pass  # Collection may not exist
        raise  # Re-raise the HTTPException
    
    # Fetch and return created KB
    kb = await db.knowledge_bases.find_one({"_id": ObjectId(kb_id)})
    return KnowledgeBase(
        kb_id=kb_id,
        embedding_dimensions=kb["embedding_dimensions"],
        status=kb["status"],
        document_count=kb["document_count"],
        chunk_count=kb["chunk_count"],
        created_at=kb["created_at"],
        updated_at=kb["updated_at"],
        **config.model_dump()
    )

@knowledge_bases_router.get("/v0/orgs/{organization_id}/knowledge-bases", response_model=ListKnowledgeBasesResponse)
async def list_knowledge_bases(
    organization_id: str,
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100),
    name_search: Optional[str] = Query(None),
    current_user: User = Depends(get_org_user)
):
    """List knowledge bases for an organization"""
    analytiq_client = ad.common.get_analytiq_client()
    db = ad.common.get_async_db(analytiq_client)
    
    # Build query
    query = {"organization_id": organization_id}
    if name_search:
        query["name"] = {"$regex": name_search, "$options": "i"}
    
    # Get total count
    total_count = await db.knowledge_bases.count_documents(query)
    
    # Get KBs with pagination
    cursor = db.knowledge_bases.find(query).skip(skip).limit(limit).sort("created_at", -1)
    kbs = await cursor.to_list(length=limit)
    
    knowledge_bases = [
        KnowledgeBase(
            kb_id=str(kb["_id"]),
            embedding_dimensions=kb["embedding_dimensions"],
            status=kb["status"],
            document_count=kb["document_count"],
            chunk_count=kb["chunk_count"],
            created_at=kb["created_at"],
            updated_at=kb["updated_at"],
            name=kb["name"],
            description=kb.get("description", ""),
            tag_ids=kb.get("tag_ids", []),
            chunker_type=kb["chunker_type"],
            chunk_size=kb["chunk_size"],
            chunk_overlap=kb["chunk_overlap"],
            embedding_model=kb["embedding_model"],
            coalesce_neighbors=kb.get("coalesce_neighbors", 0)
        )
        for kb in kbs
    ]
    
    return ListKnowledgeBasesResponse(
        knowledge_bases=knowledge_bases,
        total_count=total_count
    )

@knowledge_bases_router.get("/v0/orgs/{organization_id}/knowledge-bases/{kb_id}", response_model=KnowledgeBase)
async def get_knowledge_base(
    organization_id: str,
    kb_id: str,
    current_user: User = Depends(get_org_user)
):
    """Get a knowledge base by ID"""
    analytiq_client = ad.common.get_analytiq_client()
    db = ad.common.get_async_db(analytiq_client)
    
    kb = await db.knowledge_bases.find_one({
        "_id": ObjectId(kb_id),
        "organization_id": organization_id
    })
    
    if not kb:
        raise HTTPException(status_code=404, detail="Knowledge base not found")
    
    return KnowledgeBase(
        kb_id=kb_id,
        embedding_dimensions=kb["embedding_dimensions"],
        status=kb["status"],
        document_count=kb["document_count"],
        chunk_count=kb["chunk_count"],
        created_at=kb["created_at"],
        updated_at=kb["updated_at"],
        name=kb["name"],
        description=kb.get("description", ""),
        tag_ids=kb.get("tag_ids", []),
        chunker_type=kb["chunker_type"],
        chunk_size=kb["chunk_size"],
        chunk_overlap=kb["chunk_overlap"],
        embedding_model=kb["embedding_model"],
        coalesce_neighbors=kb.get("coalesce_neighbors", 0)
    )

@knowledge_bases_router.put("/v0/orgs/{organization_id}/knowledge-bases/{kb_id}", response_model=KnowledgeBase)
async def update_knowledge_base(
    organization_id: str,
    kb_id: str,
    update: KnowledgeBaseUpdate = Body(...),
    current_user: User = Depends(get_org_user)
):
    """Update a knowledge base (only mutable fields)"""
    analytiq_client = ad.common.get_analytiq_client()
    db = ad.common.get_async_db(analytiq_client)
    
    # Verify KB exists and belongs to org
    kb = await db.knowledge_bases.find_one({
        "_id": ObjectId(kb_id),
        "organization_id": organization_id
    })
    
    if not kb:
        raise HTTPException(status_code=404, detail="Knowledge base not found")
    
    # Validate tag IDs if provided
    if update.tag_ids is not None:
        await validate_tag_ids(update.tag_ids, organization_id, analytiq_client)
    
    # Build update dict (only include provided fields)
    update_dict = {"updated_at": datetime.now(UTC)}
    if update.name is not None:
        update_dict["name"] = update.name
    if update.description is not None:
        update_dict["description"] = update.description
    if update.tag_ids is not None:
        update_dict["tag_ids"] = update.tag_ids
    if update.coalesce_neighbors is not None:
        update_dict["coalesce_neighbors"] = update.coalesce_neighbors
    
    # Update KB
    await db.knowledge_bases.update_one(
        {"_id": ObjectId(kb_id)},
        {"$set": update_dict}
    )
    
    # Fetch and return updated KB
    updated_kb = await db.knowledge_bases.find_one({"_id": ObjectId(kb_id)})
    return KnowledgeBase(
        kb_id=kb_id,
        embedding_dimensions=updated_kb["embedding_dimensions"],
        status=updated_kb["status"],
        document_count=updated_kb["document_count"],
        chunk_count=updated_kb["chunk_count"],
        created_at=updated_kb["created_at"],
        updated_at=updated_kb["updated_at"],
        name=updated_kb["name"],
        description=updated_kb.get("description", ""),
        tag_ids=updated_kb.get("tag_ids", []),
        chunker_type=updated_kb["chunker_type"],
        chunk_size=updated_kb["chunk_size"],
        chunk_overlap=updated_kb["chunk_overlap"],
        embedding_model=updated_kb["embedding_model"],
        coalesce_neighbors=updated_kb.get("coalesce_neighbors", 0)
    )

@knowledge_bases_router.delete("/v0/orgs/{organization_id}/knowledge-bases/{kb_id}")
async def delete_knowledge_base(
    organization_id: str,
    kb_id: str,
    current_user: User = Depends(get_org_user)
):
    """Delete a knowledge base and all associated data"""
    logger.info(f"Deleting KB {kb_id} for org {organization_id}")
    
    analytiq_client = ad.common.get_analytiq_client()
    db = ad.common.get_async_db(analytiq_client)
    
    # Verify KB exists and belongs to org
    kb = await db.knowledge_bases.find_one({
        "_id": ObjectId(kb_id),
        "organization_id": organization_id
    })
    
    if not kb:
        raise HTTPException(status_code=404, detail="Knowledge base not found")
    
    # Drop vector collection
    collection_name = f"kb_vectors_{kb_id}"
    await db[collection_name].drop()
    
    # Delete document_index entries
    await db.document_index.delete_many({"kb_id": kb_id})
    
    # Delete KB config
    await db.knowledge_bases.delete_one({"_id": ObjectId(kb_id)})
    
    return {"message": "Knowledge base deleted successfully"}

@knowledge_bases_router.get("/v0/orgs/{organization_id}/knowledge-bases/{kb_id}/documents", response_model=ListKBDocumentsResponse)
async def list_kb_documents(
    organization_id: str,
    kb_id: str,
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100),
    current_user: User = Depends(get_org_user)
):
    """List documents in a knowledge base"""
    analytiq_client = ad.common.get_analytiq_client()
    db = ad.common.get_async_db(analytiq_client)
    
    # Verify KB exists and belongs to org
    kb = await db.knowledge_bases.find_one({
        "_id": ObjectId(kb_id),
        "organization_id": organization_id
    })
    
    if not kb:
        raise HTTPException(status_code=404, detail="Knowledge base not found")
    
    # Get total count
    total_count = await db.document_index.count_documents({"kb_id": kb_id})
    
    # Get document_index entries with pagination
    index_entries = await db.document_index.find({"kb_id": kb_id}).skip(skip).limit(limit).sort("indexed_at", -1).to_list(length=limit)
    
    # Fetch document details
    document_ids = [entry["document_id"] for entry in index_entries]
    docs = await db.docs.find({
        "_id": {"$in": [ObjectId(doc_id) for doc_id in document_ids]},
        "organization_id": organization_id
    }).to_list(None)
    
    doc_map = {str(doc["_id"]): doc for doc in docs}
    
    documents = [
        KnowledgeBaseDocument(
            document_id=entry["document_id"],
            document_name=doc_map.get(entry["document_id"], {}).get("user_file_name", "Unknown"),
            chunk_count=entry["chunk_count"],
            indexed_at=entry["indexed_at"]
        )
        for entry in index_entries
        if entry["document_id"] in doc_map
    ]
    
    return ListKBDocumentsResponse(
        documents=documents,
        total_count=total_count
    )

@knowledge_bases_router.post("/v0/orgs/{organization_id}/knowledge-bases/{kb_id}/search", response_model=KBSearchResponse)
async def search_knowledge_base(
    organization_id: str,
    kb_id: str,
    search_request: KBSearchRequest = Body(...),
    current_user: User = Depends(get_org_user)
):
    """Search a knowledge base using vector search"""
    analytiq_client = ad.common.get_analytiq_client()
    
    try:
        search_results = await ad.kb.search.search_knowledge_base(
            analytiq_client=analytiq_client,
            kb_id=kb_id,
            query=search_request.query,
            organization_id=organization_id,
            top_k=search_request.top_k,
            skip=search_request.skip,
            document_ids=search_request.document_ids,
            metadata_filter=search_request.metadata_filter,
            upload_date_from=search_request.upload_date_from,
            upload_date_to=search_request.upload_date_to,
            coalesce_neighbors=search_request.coalesce_neighbors
        )
        
        return KBSearchResponse(
            results=[KBSearchResult(**result) for result in search_results["results"]],
            query=search_request.query,
            total_count=search_results["total_count"],
            skip=search_request.skip,
            top_k=search_request.top_k
        )
    except SPUCreditException as e:
        logger.warning(f"SPU credit exhausted for KB search {kb_id}: {str(e)}")
        raise HTTPException(
            status_code=402,
            detail=f"Insufficient SPU credits: {str(e)}"
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        error_msg = str(e)
        # Check if this is a vector index timing issue
        if "INITIAL_SYNC" in error_msg or "NOT_STARTED" in error_msg or "cannot query vector index" in error_msg.lower():
            logger.warning(f"Vector index for KB {kb_id} not ready yet. Error: {error_msg[:200]}")
            raise HTTPException(
                status_code=503,  # Service Unavailable
                detail=f"Knowledge base search index is still building. Please try again in a few moments. Error: {error_msg[:200]}"
            )
        logger.error(f"Error searching KB {kb_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")

@knowledge_bases_router.post("/v0/orgs/{organization_id}/knowledge-bases/{kb_id}/reconcile")
async def reconcile_knowledge_base_endpoint(
    organization_id: str,
    kb_id: str,
    dry_run: bool = Query(False, description="If true, only report issues without fixing them"),
    current_user: User = Depends(get_org_user)
):
    """Reconcile a knowledge base (fix drift between tags and indexes)"""
    analytiq_client = ad.common.get_analytiq_client()
    
    try:
        results = await ad.kb.reconciliation.reconcile_knowledge_base(
            analytiq_client=analytiq_client,
            kb_id=kb_id,
            organization_id=organization_id,
            dry_run=dry_run
        )
        return results
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error reconciling KB {kb_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Reconciliation failed: {str(e)}")

@knowledge_bases_router.post("/v0/orgs/{organization_id}/knowledge-bases/reconcile-all")
async def reconcile_all_knowledge_bases_endpoint(
    organization_id: str,
    dry_run: bool = Query(False, description="If true, only report issues without fixing them"),
    current_user: User = Depends(get_org_user)
):
    """Reconcile all knowledge bases for an organization"""
    analytiq_client = ad.common.get_analytiq_client()
    
    try:
        results = await ad.kb.reconciliation.reconcile_all_knowledge_bases(
            analytiq_client=analytiq_client,
            organization_id=organization_id,
            dry_run=dry_run
        )
        return results
    except Exception as e:
        logger.error(f"Error reconciling all KBs for org {organization_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Reconciliation failed: {str(e)}")
