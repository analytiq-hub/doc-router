# Knowledge Base (KB) Design Document

## Overview

This document outlines the design for implementing Knowledge Base (KB) support in DocRouter. Knowledge Bases enable organizations to store, search, and retrieve document content using vector embeddings for RAG (Retrieval-Augmented Generation) during LLM document processing.

## Table of Contents

1. [Requirements Summary](#requirements-summary)
2. [Architecture Overview](#architecture-overview)
3. [Data Models](#data-models)
4. [Text Chunking with Chonkie](#text-chunking-with-chonkie)
5. [Embedding Generation](#embedding-generation)
6. [MongoDB Vector Search](#mongodb-vector-search)
7. [Indexing Workflow](#indexing-workflow)
8. [Agentic LLM Integration](#agentic-llm-integration)
9. [API Design](#api-design)
10. [Implementation Plan](#implementation-plan)

---

## Requirements Summary

1. **Multi-KB Support**: Each organization can create one or more knowledge bases
2. **Per-KB Embeddings**: Each KB uses its own embedding model and vector collection
3. **Tag-Based Association Only**: Documents are associated to KBs by tags (no manual add/remove)
4. **OCR-Gated Indexing**: KB indexing runs only after OCR completes successfully
5. **Auto-Reindexing**: Tag changes on documents trigger reindexing
6. **Vector Storage**: MongoDB vector search (Atlas or self-hosted 8.2+)
7. **Embedding Provider**: LiteLLM for embedding generation
8. **Agentic LLM**: Prompts can reference KBs; LLM calls KB lookup tool until satisfied
9. **Schema Compliance**: Final agent response conforms to the prompt's schema
10. **Atomic Operations**: KB index state changes are transactional and idempotent

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         Document Upload Flow                            │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
                        ┌───────────────────────┐
                        │   Upload Document     │
                        │   (with tags)         │
                        └───────────────────────┘
                                    │
                                    ▼
                        ┌───────────────────────┐
                        │   OCR Queue           │
                        │   (existing)          │
                        └───────────────────────┘
                                    │
                                    ▼
                        ┌───────────────────────┐
                        │   OCR Worker          │
                        │   (extracts text)     │
                        └───────────────────────┘
                                    │
                                    ▼ (OCR completes)
                        ┌───────────────────────┐
                        │   KB Index Queue      │
                        │   (new)               │
                        └───────────────────────┘
                                    │
                                    ▼
                        ┌───────────────────────┐
                        │   KB Index Worker     │
                        └───────────────────────┘
                                    │
                    ┌───────────────┴───────────────┐
                    ▼                               ▼
         ┌──────────────┐                 ┌──────────────┐
         │   Chonkie    │                 │   LiteLLM    │
         │   Chunking   │                 │   Embedding  │
         └──────────────┘                 └──────────────┘
                    │                               │
                    └───────────────┬───────────────┘
                                    ▼
                        ┌──────────────┐
                        │   MongoDB    │
                        │   Vector DB  │
                        └──────────────┘


┌─────────────────────────────────────────────────────────────────────────┐
│                         LLM Processing Flow                             │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
                        ┌───────────────────────┐
                        │   Run Prompt          │
                        │   (with KB IDs)       │
                        └───────────────────────┘
                                    │
                                    ▼
                        ┌───────────────────────┐
                        │   LLM with Tools      │◀──────────┐
                        │   (agentic loop)      │           │
                        └───────────────────────┘           │
                                    │                       │
                          tool call?                        │
                        ┌───────┴───────┐                   │
                        ▼               ▼                   │
                       No              Yes                  │
                        │               │                   │
                        ▼               ▼                   │
              ┌─────────────┐  ┌─────────────────┐          │
              │   Return    │  │  Vector Search  │──────────┘
              │   Response  │  │  in KB          │
              └─────────────┘  └─────────────────┘
```

---

## Data Models

### Design Decision: Per-KB Collections

**Decision: Use one vector collection per KB.**

Rationale:
- Each KB can use a different embedding model and dimension
- Vector indexes require a fixed `numDimensions`
- Operationally simple to drop or rebuild a KB

### Collection: `knowledge_bases`

```python
{
    "_id": ObjectId,                    # KB ID
    "organization_id": str,             # Owner organization
    "name": str,                        # Human-readable name
    "description": str,                 # Optional description (default: "")
    "tag_ids": List[str],               # Tags for auto-indexing (empty = manual only)
    
    # Chunking configuration
    "chunker_type": str,                # "recursive" | "sentence" | "token" (default: "recursive")
    "chunk_size": int,                  # Target tokens per chunk (default: 512)
    "chunk_overlap": int,               # Overlap tokens (default: 128)
    
    # Embedding configuration  
    "embedding_model": str,             # LiteLLM model (default: "text-embedding-3-small")
    "embedding_dimensions": int,        # Vector dimensions (auto-detected, stored for index)
    
    # Search configuration
    "coalesce_neighbors": int,          # Number of neighboring chunks to include (default: 0, 0 = disabled)
    
    # Metadata
    "status": str,                      # "active" | "indexing" | "error" | "pending_reindex"
    "document_count": int,              # Number of indexed documents
    "chunk_count": int,                 # Total chunks in KB
    "last_searched_at": datetime,       # Last time KB was searched (for analytics)
    "created_at": datetime,
    "updated_at": datetime,
    "created_by": str,
    "updated_by": str
}
```

### Collection: `kb_vectors_{kb_id}`

Each KB has its own vector collection. The collection name includes the KB ID.

```python
{
    "_id": ObjectId,
    "organization_id": str,             # For access control
    "kb_id": str,                       # Knowledge base reference
    "document_id": str,                 # Source document
    "chunk_index": int,                 # Position within document (0-indexed)
    "chunk_text": str,                  # Text content
    "embedding": List[float],           # Vector embedding
    "token_count": int,                 # Tokens in this chunk
    
    # Metadata for filtering (copied from document at index time)
    "document_name": str,               # Source filename
    "upload_date": datetime,            # Document upload date
    "tag_ids": List[str],               # Document tags at index time
    "metadata": dict,                   # Custom document metadata (key-value pairs)
    "indexed_at": datetime
}
```

### Collection: `document_index`

Tracks which documents are indexed in which KBs. Separates KB functionality from core document management.

```python
{
    "_id": ObjectId,
    "organization_id": str,
    "kb_id": str,
    "document_id": str,
    "indexed_at": datetime,             # When indexing completed
    "chunk_count": int                  # Number of chunks created
}
```

**Indexes:**
```python
# Find all KBs for a document
await db.document_index.create_index([
    ("organization_id", 1),
    ("document_id", 1)
], name="org_doc_idx")

# Find all documents in a KB
await db.document_index.create_index([
    ("organization_id", 1),
    ("kb_id", 1)
], name="org_kb_idx")

# Unique constraint: one entry per (kb_id, document_id)
await db.document_index.create_index([
    ("kb_id", 1),
    ("document_id", 1)
], name="kb_doc_unique", unique=True)
```

**Benefits:**
- Separates KB functionality from core `docs` collection
- Clean separation of concerns
- Easy queries: "Which KBs contain this document?" or "Which documents are in this KB?"
- Simple status: Document indexed if entry exists in `document_index`

---

## Text Chunking with Chonkie

### Why Chonkie?

[Chonkie](https://docs.chonkie.ai) is a lightweight Python library designed for RAG chunking:
- **Semantic-aware**: Splits at sentence/paragraph boundaries, not mid-word
- **Multiple strategies**: Token, sentence, recursive (hierarchical)
- **Fast**: Optimized for production use
- **Simple API**: Easy to integrate

### Installation

```bash
pip install chonkie
```

### Chunker Types

| Type | Best For | Description |
|------|----------|-------------|
| `recursive` | **General documents** (default) | Hierarchical splitting by paragraphs, then sentences. Best semantic coherence. |
| `sentence` | Structured text | Splits by sentences, preserves sentence boundaries |
| `token` | Fixed-size needs | Exact token counts, may split mid-sentence |

### Implementation

```python
from chonkie import RecursiveChunker, SentenceChunker, TokenChunker

def get_chunker(chunker_type: str, chunk_size: int, chunk_overlap: int):
    """Get configured chunker based on KB settings."""
    
    if chunker_type == "recursive":
        return RecursiveChunker(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap
        )
    elif chunker_type == "sentence":
        return SentenceChunker(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap
        )
    elif chunker_type == "token":
        return TokenChunker(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap
        )
    else:
        raise ValueError(f"Unknown chunker type: {chunker_type}")

def chunk_document(text: str, kb_config: dict) -> List[dict]:
    """Chunk document text according to KB configuration."""
    chunker = get_chunker(
        kb_config["chunker_type"],
        kb_config["chunk_size"],
        kb_config["chunk_overlap"]
    )
    
    chunks = chunker(text)
    
    return [
        {
            "chunk_index": i,
            "chunk_text": chunk.text,
            "token_count": chunk.token_count
        }
        for i, chunk in enumerate(chunks)
    ]
```

### Default Configuration

| Setting | Default | Rationale |
|---------|---------|-----------|
| `chunker_type` | `"recursive"` | Best semantic coherence for varied document types |
| `chunk_size` | `512` | Balances context (enough for RAG) with embedding quality |
| `chunk_overlap` | `128` | ~25% overlap prevents information loss at boundaries |

---

## Embedding Generation

### LiteLLM Integration

LiteLLM provides a unified interface for embedding models across providers.

```python
import litellm

async def generate_embeddings(
    texts: List[str],
    model: str,
    api_key: str
) -> List[List[float]]:
    """Generate embeddings for a batch of texts."""
    
    response = await litellm.aembedding(
        model=model,
        input=texts,
        api_key=api_key
    )
    
    return [item["embedding"] for item in response.data]
```

### Supported Embedding Models

| Model | Dimensions | Provider | Cost | Notes |
|-------|------------|----------|------|-------|
| `text-embedding-3-small` | 1536 | OpenAI | Low | **Recommended default** |
| `text-embedding-3-large` | 3072 | OpenAI | Medium | Higher quality |
| `text-embedding-ada-002` | 1536 | OpenAI | Low | Legacy, still good |
| `embed-english-v3.0` | 1024 | Cohere | Low | Fast |
| `embed-multilingual-v3.0` | 1024 | Cohere | Low | Multi-language |

### Batch Processing

For efficiency, process embeddings in batches:

```python
EMBEDDING_BATCH_SIZE = 100  # Most APIs support up to 2048

async def embed_chunks(chunks: List[dict], kb_config: dict) -> List[dict]:
    """Add embeddings to chunks in batches."""
    
    model = kb_config["embedding_model"]
    api_key = await get_embedding_api_key(kb_config["organization_id"], model)
    
    texts = [c["chunk_text"] for c in chunks]
    
    # Process in batches
    all_embeddings = []
    for i in range(0, len(texts), EMBEDDING_BATCH_SIZE):
        batch = texts[i:i + EMBEDDING_BATCH_SIZE]
        embeddings = await generate_embeddings(batch, model, api_key)
        all_embeddings.extend(embeddings)
    
    # Add embeddings to chunks
    for chunk, embedding in zip(chunks, all_embeddings):
        chunk["embedding"] = embedding
    
    return chunks
```

---

## MongoDB Vector Search

### Prerequisites

MongoDB vector search is available in:
- **MongoDB Atlas**: All tiers (free tier included)
- **MongoDB Community/Enterprise 8.2+**: Self-hosted with `mongot` process

### Vector Search Index

Create a vector search index on each `kb_vectors_{kb_id}` collection:

```javascript
// Atlas Search Index (via Atlas UI or API)
{
  "name": "kb_vector_index",
  "type": "vectorSearch",
  "definition": {
    "fields": [
      {
        "type": "vector",
        "path": "embedding",
        "numDimensions": 1536,  // per-KB embedding dimensions
        "similarity": "cosine"
      },
      {
        "type": "filter",
        "path": "organization_id"
      },
    ]
  }
}
```

For self-hosted MongoDB 8.2+, use `createSearchIndex` on each KB collection:

```javascript
db.kb_vectors_<kb_id>.createSearchIndex({
    name: "kb_vector_index",
    type: "vectorSearch",
    definition: {
        fields: [
            {
                type: "vector",
                path: "embedding",
                numDimensions: 1536,  // per-KB embedding dimensions
                similarity: "cosine"
            }
        ]
    }
})
```

### Standard Indexes

Add compound indexes for efficient filtering:

```python
# In migration or startup
await db.kb_vectors_<kb_id>.create_index([
    ("organization_id", 1),
    ("document_id", 1)
], name="org_doc_idx")

# Indexes for document_index collection (see document_index schema above)
```

### Vector Search Query (Similarity + Metadata)

```python
async def vector_search(
    db,
    query_embedding: List[float],
    organization_id: str,
    kb_id: str,
    top_k: int = 5,
    document_ids: List[str] | None = None,  # Optional: filter by specific documents
    metadata_filter: dict | None = None,     # Optional: filter by document metadata
    upload_date_from: datetime | None = None,  # Optional: filter by upload date range
    upload_date_to: datetime | None = None,
    coalesce_neighbors: int = 0  # Override KB default, 0 = disabled
) -> List[dict]:
    """Search for similar chunks within a KB, with optional metadata and date filtering."""
    
    # Build vector search filter
    vector_filter = {"organization_id": organization_id}
    if document_ids:
        vector_filter["document_id"] = {"$in": document_ids}
    
    # Apply metadata filters (document_name, tag_ids, custom metadata)
    if metadata_filter:
        # metadata_filter can contain: document_name, tag_ids, or custom metadata keys
        for key, value in metadata_filter.items():
            if key == "document_name":
                # Support regex search on document name
                if isinstance(value, dict) and "$regex" in value:
                    vector_filter["document_name"] = value
                else:
                    vector_filter["document_name"] = value
            elif key == "tag_ids":
                # Filter by tag IDs (array contains)
                vector_filter["tag_ids"] = {"$in": value} if isinstance(value, list) else {"$in": [value]}
            else:
                # Custom metadata field
                vector_filter[f"metadata.{key}"] = value
    
    # Apply upload date range filter
    if upload_date_from or upload_date_to:
        date_filter = {}
        if upload_date_from:
            date_filter["$gte"] = upload_date_from
        if upload_date_to:
            date_filter["$lte"] = upload_date_to
        vector_filter["upload_date"] = date_filter
    
    # Get KB config for coalesce_neighbors if not overridden
    if coalesce_neighbors is None:
        kb = await db.knowledge_bases.find_one({"_id": ObjectId(kb_id)})
        coalesce_neighbors = kb.get("coalesce_neighbors", 0) if kb else 0
    
    pipeline = [
        {
            "$vectorSearch": {
                "index": "kb_vector_index",
                "path": "embedding",
                "queryVector": query_embedding,
                "numCandidates": top_k * 20,  # Search wider when filters applied
                "limit": top_k * 2,  # Get more results, filter down
                "filter": vector_filter
            }
        },
        {
            "$project": {
                "chunk_text": 1,
                "document_id": 1,
                "document_name": 1,
                "kb_id": 1,
                "chunk_index": 1,
                "upload_date": 1,
                "tag_ids": 1,
                "score": {"$meta": "vectorSearchScore"}
            }
        },
        {
            "$limit": top_k  # Final limit after filtering
        }
    ]
    
    # Get initial vector search results
    matched_chunks = await db[f"kb_vectors_{kb_id}"].aggregate(pipeline).to_list(length=top_k)
    
    # If coalescing is enabled, fetch neighboring chunks
    if coalesce_neighbors > 0:
        results = await coalesce_neighboring_chunks(
            db, kb_id, matched_chunks, coalesce_neighbors
        )
    else:
        results = matched_chunks
    
    return results

async def coalesce_neighboring_chunks(
    db,
    kb_id: str,
    matched_chunks: List[dict],
    neighbor_count: int
) -> List[dict]:
    """Fetch neighboring chunks for each matched chunk and merge them."""
    
    coalesced_results = []
    seen_chunks = set()  # Track (document_id, chunk_index) to avoid duplicates
    
    for match in matched_chunks:
        doc_id = match["document_id"]
        chunk_idx = match["chunk_index"]
        
        # Build range of chunk indices to fetch
        start_idx = max(0, chunk_idx - neighbor_count)
        end_idx = chunk_idx + neighbor_count + 1
        
        # Fetch all chunks in range for this document
        neighbors = await db[f"kb_vectors_{kb_id}"].find({
            "document_id": doc_id,
            "chunk_index": {"$gte": start_idx, "$lt": end_idx}
        }).sort("chunk_index", 1).to_list(None)
        
        # Merge chunks, preserving the matched chunk's score
        for neighbor in neighbors:
            key = (neighbor["document_id"], neighbor["chunk_index"])
            if key not in seen_chunks:
                seen_chunks.add(key)
                # Use original score if this is the matched chunk, else None
                neighbor["score"] = match["score"] if neighbor["chunk_index"] == chunk_idx else None
                neighbor["is_matched"] = (neighbor["chunk_index"] == chunk_idx)
                coalesced_results.append(neighbor)
    
    # Sort by document_id, then chunk_index to maintain document order
    coalesced_results.sort(key=lambda x: (x["document_id"], x["chunk_index"]))
    
    return coalesced_results
```

### Metadata Filtering

Metadata filtering is done **within the vector search** using MongoDB's filter capability in `$vectorSearch`. This ensures:
- Efficient: Filtering happens during vector search, not after
- Accurate: Results are ranked by similarity within the filtered set
- Fast: MongoDB optimizes the combined vector + metadata query

**Supported Filters:**

1. **Document Metadata**:
   - `document_name`: Exact match or regex (e.g., `{"$regex": "invoice", "$options": "i"}`)
   - `tag_ids`: Array contains (e.g., `{"$in": ["tag1", "tag2"]}`)
   - Custom metadata: Any key-value from document metadata (e.g., `metadata.customer_id: "123"`)

2. **Upload Date Range**:
   - `upload_date_from`: Start date (inclusive)
   - `upload_date_to`: End date (inclusive)

**Example:**
```python
results = await vector_search(
    query_embedding=embedding,
    organization_id=org_id,
    kb_id=kb_id,
    top_k=5,
    metadata_filter={
        "document_name": {"$regex": "invoice", "$options": "i"},
        "tag_ids": {"$in": ["invoice", "2024"]}
    },
    upload_date_from=datetime(2024, 1, 1),
    upload_date_to=datetime(2024, 12, 31)
)
```

**Note:** Metadata is stored in vectors at index time, so filters work on the metadata snapshot from when the document was indexed.

### Chunk Coalescing (Neighboring Context)

When a relevant chunk is found via vector search, you can optionally include neighboring chunks from the same document to provide additional context. This is useful because:

- **Broader Context**: A single chunk might not contain complete information
- **Continuity**: Neighboring chunks often contain related details (e.g., a table header followed by rows)
- **Better LLM Understanding**: More context helps the LLM generate more accurate responses

**Configuration:**
- Set `coalesce_neighbors` in KB config (default: 0 = disabled)
- Override per search query via `coalesce_neighbors` parameter
- Value represents number of chunks before and after the matched chunk (e.g., `2` = 2 before + matched + 2 after = 5 total chunks)

**Example:**
If `coalesce_neighbors = 2` and chunk 5 is matched:
- Returns chunks: 3, 4, **5** (matched), 6, 7
- The matched chunk retains its similarity score
- Neighboring chunks are marked with `is_matched: false` and `score: None`

**Use Cases:**
- **Technical Documentation**: Include surrounding paragraphs for complete context
- **Financial Reports**: Include table headers with data rows
- **Legal Documents**: Include preceding/succeeding clauses for full context

### Performance Tuning

| Parameter | Description | Recommendation |
|-----------|-------------|----------------|
| `numCandidates` | Vectors to consider before filtering | 10-20x `limit` for accuracy |
| `limit` | Max results returned | Start with 5-10 for RAG |
| Filters | Pre-filter by org/kb | Always filter by `organization_id` |

---

## Indexing Workflow

### Transactional Semantics (Simplified)

Each indexing job uses a single MongoDB transaction:
1. Delete any existing vectors for `(kb_id, document_id)` (idempotency)
2. Insert new vectors
3. Add `kb_id` to document's `kb_indexed_in` list

**Benefits:**
- Single transaction = simpler code
- No separate status collection to manage
- If transaction fails, document remains unchanged (no cleanup needed)
- Status is implicit: document is indexed if `kb_id in doc.kb_indexed_in` AND vectors exist

### Message Queue Integration

Following the existing worker pattern, add a `kb_index` queue:

```python
# In worker.py, add new worker function:

async def worker_kb_index(worker_id: str) -> None:
    """Worker for KB indexing jobs."""
    ENV = os.getenv("ENV", "dev")
    analytiq_client = ad.common.get_analytiq_client(env=ENV, name=worker_id)
    logger.info(f"Starting KB index worker {worker_id}")

    while True:
        try:
            msg = await ad.queue.recv_msg(analytiq_client, "kb_index")
            if msg:
                await ad.msg_handlers.process_kb_index_msg(analytiq_client, msg)
            else:
                await asyncio.sleep(0.2)
        except Exception as e:
            logger.error(f"KB index worker error: {e}")
            await asyncio.sleep(1)
```

### Index Message Handler (Atomic / Transactional)

```python
# In msg_handlers/kb_index.py

async def process_kb_index_msg(analytiq_client, msg: dict):
    """Process a KB indexing message."""
    
    document_id = msg["msg"]["document_id"]
    kb_id = msg["msg"]["kb_id"]
    action = msg["msg"].get("action", "index")  # "index" | "remove"
    
    db = ad.common.get_async_db(analytiq_client)
    
    if action == "remove":
        # Simple remove: delete vectors and remove from document_index
        async with await db.client.start_session() as session:
            async with session.start_transaction():
                await db[f"kb_vectors_{kb_id}"].delete_many(
                    {"document_id": document_id},
                    session=session
                )
                await db.document_index.delete_one(
                    {
                        "kb_id": kb_id,
                        "document_id": document_id
                    },
                    session=session
                )
        return
    
    # Get KB configuration
    kb = await db.knowledge_bases.find_one({"_id": ObjectId(kb_id)})
    if not kb:
        logger.error(f"KB not found: {kb_id}")
        return
    
    try:
        # 1. Get document text
        text = await get_document_text(analytiq_client, document_id)
        
        # 2. Chunk the text
        chunks = chunk_document(text, kb)
        
        # 3. Generate embeddings
        chunks = await embed_chunks(chunks, kb)
        
        # 4. Get document for metadata
        doc = await ad.common.doc.get_doc(analytiq_client, document_id)
        
        # 5. Store vectors and update document in a transaction
        async with await db.client.start_session() as session:
            async with session.start_transaction():
                # Delete old vectors (idempotency)
                await db[f"kb_vectors_{kb_id}"].delete_many(
                    {"document_id": document_id},
                    session=session
                )
                
                # Insert new vectors with metadata
                vector_docs = [
                    {
                        "organization_id": doc["organization_id"],
                        "kb_id": kb_id,
                        "document_id": document_id,
                        "chunk_index": chunk["chunk_index"],
                        "chunk_text": chunk["chunk_text"],
                        "embedding": chunk["embedding"],
                        "token_count": chunk["token_count"],
                        "document_name": doc["user_file_name"],
                        "upload_date": doc["upload_date"],
                        "tag_ids": doc.get("tag_ids", []),
                        "metadata": doc.get("metadata", {}),
                        "indexed_at": datetime.now(UTC)
                    }
                    for chunk in chunks
                ]
                await db[f"kb_vectors_{kb_id}"].insert_many(vector_docs, session=session)
                
                # Create/update document_index entry
                await db.document_index.update_one(
                    {
                        "kb_id": kb_id,
                        "document_id": document_id
                    },
                    {
                        "$set": {
                            "organization_id": doc["organization_id"],
                            "kb_id": kb_id,
                            "document_id": document_id,
                            "indexed_at": datetime.now(UTC),
                            "chunk_count": len(chunks)
                        }
                    },
                    upsert=True,
                    session=session
                )
        
        logger.info(f"Successfully indexed {document_id} in {kb_id}: {len(chunks)} chunks")
        
    except Exception as e:
        logger.error(f"Indexing failed for {document_id} in {kb_id}: {e}")
        # On failure, document remains not in kb_indexed_in (no cleanup needed)
        raise  # Re-raise to mark message as failed
```

### Triggering Indexing (OCR-Gated)

#### On OCR Completion

When OCR completes successfully, check if the document has tags that match any KBs. Queue KB indexing jobs.

**Integration Point:**
In `msg_handlers/ocr.py`, after OCR completes successfully:

```python
# After OCR text is saved
if ocr_successful:
    # Get document tags
    doc = await ad.common.doc.get_doc(analytiq_client, document_id)
    tag_ids = doc.get("tag_ids", [])
    org_id = doc.get("organization_id")
    
    # Trigger KB indexing for matching KBs
    if tag_ids:
        await trigger_kb_indexing_after_ocr(analytiq_client, document_id, tag_ids, org_id)
```

```python
# In documents.py upload handler, after saving document:

async def trigger_kb_indexing_after_ocr(analytiq_client, document_id: str, tag_ids: List[str], org_id: str):
    """Queue indexing jobs for matching KBs after OCR completes."""
    
    if not tag_ids:
        return
    
    db = ad.common.get_async_db(analytiq_client)
    
    # Find KBs with matching tags
    matching_kbs = await db.knowledge_bases.find({
        "organization_id": org_id,
        "tag_ids": {"$in": tag_ids},
        "status": "active"
    }).to_list(None)
    
    # Queue indexing for each
    for kb in matching_kbs:
        await ad.queue.send_msg(analytiq_client, "kb_index", {
            "document_id": document_id,
            "kb_id": str(kb["_id"]),
            "action": "index"
        })
```

#### On Tag Update

When document tags change, reindex affected KBs:

```python
async def handle_tag_update(analytiq_client, document_id: str, old_tags: List[str], new_tags: List[str], org_id: str):
    """Handle tag changes by updating KB associations."""
    
    db = ad.common.get_async_db(analytiq_client)
    
    added_tags = set(new_tags) - set(old_tags)
    removed_tags = set(old_tags) - set(new_tags)
    
    # Find KBs to add document to
    if added_tags:
        kbs_to_add = await db.knowledge_bases.find({
            "organization_id": org_id,
            "tag_ids": {"$in": list(added_tags)},
            "status": "active"
        }).to_list(None)
        
        for kb in kbs_to_add:
            await ad.queue.send_msg(analytiq_client, "kb_index", {
                "document_id": document_id,
                "kb_id": str(kb["_id"]),
                "action": "index"
            })
    
    # Find KBs to remove document from
    if removed_tags:
        kbs_to_remove = await db.knowledge_bases.find({
            "organization_id": org_id,
            "tag_ids": {"$in": list(removed_tags)},
            "tag_ids": {"$nin": list(new_tags)}  # Only if no remaining matching tags
        }).to_list(None)
        
        for kb in kbs_to_remove:
            await ad.queue.send_msg(analytiq_client, "kb_index", {
                "document_id": document_id,
                "kb_id": str(kb["_id"]),
                "action": "remove"
            })
```

---

## Agentic LLM Integration

### Prompt Extension

Add `kb_ids` to prompt configuration:

```python
class PromptConfig(BaseModel):
    name: str
    content: str
    schema_id: Optional[str] = None
    schema_version: Optional[int] = None
    tag_ids: List[str] = []
    model: str = "gpt-4o-mini"
    kb_ids: List[str] = []  # NEW: Knowledge bases for RAG
```

### KB Search Tool Definition

```python
KB_SEARCH_TOOL = {
    "type": "function",
    "function": {
        "name": "search_knowledge_base",
        "description": "Search the knowledge base for relevant information. Use this to find context that helps answer questions about the document or related topics.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query describing what information you need"
                },
                "top_k": {
                    "type": "integer",
                    "description": "Number of results to return (1-10)",
                    "default": 5
                },
                "coalesce_neighbors": {
                    "type": "integer",
                    "description": "Number of neighboring chunks to include for context (0 = disabled, default uses KB setting)",
                    "default": None
                },
                "metadata_filter": {
                    "type": "object",
                    "description": "Optional metadata filters: document_name (string or regex), tag_ids (array), or custom metadata fields",
                    "properties": {
                        "document_name": {"type": "string"},
                        "tag_ids": {"type": "array", "items": {"type": "string"}}
                    }
                },
                "upload_date_from": {
                    "type": "string",
                    "description": "Optional: Filter by upload date from (ISO 8601 format)"
                },
                "upload_date_to": {
                    "type": "string",
                    "description": "Optional: Filter by upload date to (ISO 8601 format)"
                }
            },
            "required": ["query"]
        }
    }
}
```

### Agentic LLM Loop

Modify `run_llm()` to support tool calling:

```python
async def run_llm_with_kb(
    analytiq_client,
    document_id: str,
    prompt_revid: str,
    kb_ids: List[str],
    max_iterations: int = 5
) -> dict:
    """Run LLM with KB tool calling support."""
    
    # Get prompt, schema, document, etc. (existing logic)
    prompt = await get_prompt(analytiq_client, prompt_revid)
    schema = await get_schema(analytiq_client, prompt.schema_id) if prompt.schema_id else None
    document_text = await get_document_text(analytiq_client, document_id)
    
    # Build initial messages
    messages = build_messages(prompt, document_text, schema)
    
    # Add tool if KBs specified
    tools = [KB_SEARCH_TOOL] if kb_ids else None
    
    iteration = 0
    while iteration < max_iterations:
        iteration += 1
        
        # Call LLM
        response = await litellm.acompletion(
            model=prompt.model,
            messages=messages,
            tools=tools,
            tool_choice="auto" if tools else None,
            response_format=schema.response_format if schema else None
        )
        
        assistant_message = response.choices[0].message
        messages.append(assistant_message)
        
        # Check for tool calls
        if not assistant_message.tool_calls:
            # No tool calls, we have the final response
            break
        
        # Execute tool calls
        for tool_call in assistant_message.tool_calls:
            if tool_call.function.name == "search_knowledge_base":
                args = json.loads(tool_call.function.arguments)
                
                # Parse date strings if provided
                upload_date_from = None
                upload_date_to = None
                if args.get("upload_date_from"):
                    upload_date_from = datetime.fromisoformat(args["upload_date_from"].replace("Z", "+00:00"))
                if args.get("upload_date_to"):
                    upload_date_to = datetime.fromisoformat(args["upload_date_to"].replace("Z", "+00:00"))
                
                # Execute KB search
                results = await execute_kb_search(
                    analytiq_client,
                    query=args["query"],
                    kb_ids=kb_ids,
                    top_k=args.get("top_k", 5),
                    metadata_filter=args.get("metadata_filter"),
                    upload_date_from=upload_date_from,
                    upload_date_to=upload_date_to,
                    coalesce_neighbors=args.get("coalesce_neighbors")
                )
                
                # Add tool response to messages
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": json.dumps(results)
                })
    
    # Extract and validate final response
    final_content = response.choices[0].message.content
    result = json.loads(final_content)
    
    # Schema validation (existing logic)
    if schema:
        validate_against_schema(result, schema)
    
    return result
```

### KB Search Execution

```python
async def execute_kb_search(
    analytiq_client,
    query: str,
    kb_ids: List[str],
    top_k: int = 5,
    document_ids: List[str] | None = None,
    metadata_filter: dict | None = None,
    upload_date_from: datetime | None = None,
    upload_date_to: datetime | None = None,
    coalesce_neighbors: int | None = None  # None = use KB default
) -> dict:
    """Execute vector search and format results for LLM."""
    
    db = ad.common.get_async_db(analytiq_client)
    
    # Execute per-KB search (each KB may use a different embedding model)
    all_results = []
    for kb_id in kb_ids:
        kb = await db.knowledge_bases.find_one({"_id": ObjectId(kb_id)})
        if not kb:
            continue
        
        org_id = kb["organization_id"]
        embedding_model = kb["embedding_model"]
        api_key = await get_embedding_api_key(org_id, embedding_model)
        
        query_embedding = await generate_embeddings([query], embedding_model, api_key)
        query_embedding = query_embedding[0]
        
        results = await vector_search(
            db=db,
            query_embedding=query_embedding,
            organization_id=org_id,
            kb_id=kb_id,
            top_k=top_k,
            document_ids=document_ids,
            metadata_filter=metadata_filter,
            upload_date_from=upload_date_from,
            upload_date_to=upload_date_to,
            coalesce_neighbors=coalesce_neighbors
        )
        all_results.extend(results)
    
    # Sort across KBs by score
    all_results.sort(key=lambda x: x.get("score", 0), reverse=True)
    results = all_results[:top_k]
    
    # Format for LLM consumption
    return {
        "results": [
            {
                "content": r["chunk_text"],
                "source": r["document_name"],
                "relevance": round(r["score"], 3) if r.get("score") else None,
                "is_matched": r.get("is_matched", True),  # True if this was the matched chunk
                "chunk_index": r.get("chunk_index")  # Position in document
            }
            for r in results
        ],
        "query": query,
        "sources_searched": len(kb_ids),
        "coalesced": any(not r.get("is_matched", True) for r in results)  # True if neighbors included
    }
```

---

## API Design

### Knowledge Base CRUD

#### Create KB

```
POST /v0/orgs/{organization_id}/knowledge-bases

Request:
{
    "name": "Invoice KB",
    "description": "Knowledge base for invoice processing",
    "tag_ids": ["invoice"],
    "chunker_type": "recursive",        // optional, default: "recursive"
    "chunk_size": 512,                  // optional, default: 512
    "chunk_overlap": 128,               // optional, default: 128
    "embedding_model": "text-embedding-3-small",  // optional
    "coalesce_neighbors": 2             // optional, default: 0 (disabled)
}

Response:
{
    "kb_id": "...",
    "name": "Invoice KB",
    "status": "active",
    ...
}
```

#### List KBs

```
GET /v0/orgs/{organization_id}/knowledge-bases?skip=0&limit=10&name_search=invoice
```

#### Get KB

```
GET /v0/orgs/{organization_id}/knowledge-bases/{kb_id}
```

#### Update KB

```
PUT /v0/orgs/{organization_id}/knowledge-bases/{kb_id}

Note: Changing chunking/embedding config requires reindexing.
If these change, set status to "pending_reindex" and queue reindex jobs.
```

#### Delete KB

```
DELETE /v0/orgs/{organization_id}/knowledge-bases/{kb_id}

Deletes KB config and all associated vectors.
```

### KB Documents

#### List Documents in KB

KBs are tag-only. There are no manual add/remove document endpoints.

```
GET /v0/orgs/{organization_id}/knowledge-bases/{kb_id}/documents?skip=0&limit=10
```

**Implementation:**
Query `document_index` collection where `kb_id = {kb_id}`, join with `docs` for document details, aggregate chunk counts from `kb_vectors_{kb_id}`.

Response:
{
    "documents": [
        {
            "document_id": "...",
            "document_name": "invoice.pdf",
            "chunk_count": 15,  # Count from kb_vectors_{kb_id} collection
            "indexed_at": "2026-01-22T..."  # From document or first vector indexed_at
        }
    ],
    "total_count": 42
}
```

### KB Management Operations

#### Reindex All Documents

```
POST /v0/orgs/{organization_id}/knowledge-bases/{kb_id}/reindex

Queues reindexing jobs for all documents currently in the KB.
Useful when chunking/embedding configuration changes.

Response:
{
    "status": "queued",
    "document_count": 42,
    "message": "Reindexing queued for 42 documents"
}
```

#### Get KB Statistics

```
GET /v0/orgs/{organization_id}/knowledge-bases/{kb_id}/stats

Response:
{
    "document_count": 35,      # Count from document_index where kb_id = {kb_id}
    "chunk_count": 1250,       # Sum of chunk_count from document_index for this KB
    "total_documents_with_tags": 40  # Documents with matching tags (may not all be indexed yet)
}
```

#### Retry Failed Indexing

```
POST /v0/orgs/{organization_id}/knowledge-bases/{kb_id}/retry-failed

Retries all failed indexing jobs for this KB.

Response:
{
    "status": "queued",
    "retry_count": 3,
    "message": "3 failed jobs queued for retry"
}
```

### KB Search (for testing/debugging)

```
POST /v0/orgs/{organization_id}/knowledge-bases/search

Request:
{
    "query": "What is the payment terms?",
    "kb_ids": ["kb1", "kb2"],  // optional, searches all org KBs if omitted
    "top_k": 5,
    "document_ids": ["doc1", "doc2"],  // optional, filter by specific documents
    "metadata_filter": {        // optional, filter by document metadata
        "document_name": {"$regex": "invoice", "$options": "i"},
        "tag_ids": {"$in": ["invoice", "2024"]}
    },
    "upload_date_from": "2024-01-01T00:00:00Z",  // optional, ISO date string
    "upload_date_to": "2024-12-31T23:59:59Z",    // optional, ISO date string
    "coalesce_neighbors": 2     // optional, override KB default (0 = disabled)
}

Response:
{
    "results": [
        {
            "content": "Payment is due within 30 days...",
            "source": "invoice-2024-001.pdf",
            "relevance": 0.92,
            "kb_id": "kb1"
        }
    ]
}
```

---

## Implementation Plan

### Phase 1: Core Infrastructure (Week 1)

1. **Data Models**
   - Add `knowledge_bases` collection schema
   - Add `document_index` collection schema (tracks which docs are in which KBs)
   - Add `kb_vectors_{kb_id}` collection schema (per-KB, created dynamically)
   - Create indexes:
     - Vector search index on each `kb_vectors_{kb_id}` collection
     - Indexes on `document_index`: `(org_id, doc_id)`, `(org_id, kb_id)`, unique `(kb_id, doc_id)`

2. **KB CRUD API**
   - Create, list, get, update, delete endpoints
   - Validation logic

3. **Dependencies**
   - Add `chonkie` to requirements.txt

### Phase 2: Indexing Pipeline (Week 2)

1. **Chunking Module**
   - Integrate Chonkie
   - Support recursive, sentence, token chunkers

2. **Embedding Module**
   - LiteLLM embedding wrapper
   - Batch processing
   - API key management

3. **Worker Integration**
   - Add `kb_index` queue
   - Add `worker_kb_index` function
   - Add `process_kb_index_msg` handler

4. **Auto-Indexing Triggers**
   - Hook OCR completion (trigger KB indexing after OCR succeeds)
   - Hook tag updates (reindex when document tags change)

### Phase 3: Vector Search (Week 3)

1. **MongoDB Vector Index**
   - Index creation script/migration
   - Atlas vs self-hosted handling

2. **Search Implementation**
   - Vector search function
   - Result formatting

3. **Search API**
   - Debug/test endpoint

### Phase 4: Agentic LLM (Week 4)

1. **Prompt Extension**
   - Add `kb_ids` to prompt model
   - Update prompt CRUD

2. **Tool Integration**
   - KB search tool definition
   - Tool execution handler

3. **Agentic Loop**
   - Modify `run_llm()` for tool calling
   - Iteration limit and error handling

### Phase 5: Frontend & SDK (Week 5)

1. **Frontend**
   - KB management UI
   - KB selection in prompt editor

2. **TypeScript SDK**
   - KB methods

3. **Python SDK**
   - KB methods

4. **MCP Tools**
   - KB management tools

---

## UI Design

### Navigation Structure

Following the existing pattern (`/orgs/{organizationId}/prompts`, `/orgs/{organizationId}/schemas`, etc.):

```
/orgs/{organizationId}/knowledge-bases          # KB List page
/orgs/{organizationId}/knowledge-bases/{kbId}   # KB Detail/Edit page
```

### KB List Page (`KnowledgeBaseList.tsx`)

Similar to `PromptList.tsx` and `SchemaList.tsx`:

**Features:**
- Table/grid view of all KBs in organization
- Search by name
- Filter by status (active, indexing, error)
- Sort by: name, document count, chunk count, created date
- Actions per KB:
  - View details
  - Edit
  - Delete (with confirmation)
  - View documents
  - Test search

**Table Columns:**
| Column | Description |
|--------|-------------|
| Name | KB name (clickable to detail page) |
| Description | Truncated description |
| Tags | Tag badges (matching document tags) |
| Status | Badge: Active (green), Indexing (yellow), Error (red) |
| Documents | Count of indexed documents |
| Chunks | Total chunk count |
| Embedding Model | Model name (e.g., "text-embedding-3-small") |
| Created | Date created |
| Actions | Menu (⋮) with view/edit/delete |

**UI Components:**
- Header with "Create Knowledge Base" button
- Search bar
- Status filter chips
- Responsive table (Material-UI or Tailwind)
- Pagination
- Empty state when no KBs exist

### KB Create/Edit Page (`KnowledgeBaseCreate.tsx`)

Similar to `PromptCreate.tsx` and `TagCreate.tsx`:

**Form Sections:**

1. **Basic Information**
   - Name (required)
   - Description (optional, textarea)

2. **Tag Association**
   - Multi-select tag picker (similar to prompt tag selection)
   - Info: "Documents with matching tags will be automatically indexed"
   - Empty selection = manual indexing only (not supported yet, but UI ready)

3. **Chunking Configuration**
   - Chunker Type: Dropdown
     - Recursive (default, recommended)
     - Sentence
     - Token
   - Chunk Size: Number input (tokens, default: 512)
     - Help text: "Target tokens per chunk. Larger = more context, fewer chunks"
   - Chunk Overlap: Number input (tokens, default: 128)
     - Help text: "Overlap between chunks to prevent information loss"
   - Advanced toggle (collapsible):
     - Max chunks per document (default: 500, 0 = unlimited)
     - Min chunk size (default: 50)

4. **Embedding Configuration**
   - Embedding Model: Dropdown
     - Populated from available LiteLLM embedding models
     - Show provider (OpenAI, Cohere, etc.)
     - Show dimensions (1536, 1024, etc.)
     - Default: "text-embedding-3-small"
   - Info: "Changing embedding model requires reindexing all documents"

5. **Search Configuration**
   - Coalesce Neighbors: Number input (default: 0)
     - Help text: "Include N chunks before/after matched chunks for context"
     - Range: 0-5
     - Info tooltip explaining use cases

**Validation:**
- Name required
- Chunk size > chunk overlap
- Chunk size within limits (50-2000)
- Coalesce neighbors within limits (0-5)

**Actions:**
- Save button (creates or updates)
- Cancel button (navigates back)
- Delete button (if editing, with confirmation)
- Warning banner if changing chunking/embedding config (requires reindex)

### KB Detail Page (`KnowledgeBaseDetail.tsx`)

**Tabs:**

1. **Overview Tab**
   - KB configuration summary
   - Statistics:
     - Total documents indexed
     - Total chunks
     - Average chunks per document
     - Last indexed document date
   - Status indicator
   - Quick actions (Edit, Delete, Reindex All)

2. **Documents Tab**
   - List of indexed documents (query `document_index` where `kb_id = {kb_id}`, join with `docs`)
   - Columns: Document name, Chunk count, Indexed date
   - Search by document name
   - Click document to view in document viewer
   - Show chunk count from `document_index.chunk_count`
   - Pagination
   - Note: Document is indexed if entry exists in `document_index`

3. **Search Test Tab**
   - Search interface for testing KB
   - Query input
   - Results display:
     - Chunk text (highlighted match)
     - Source document
     - Relevance score
     - Chunk index
     - "View in document" link
   - Options:
     - Top K selector (1-20)
     - Coalesce neighbors override
     - Document filter (multi-select from indexed documents)
     - Metadata filters:
       - Document name (text search)
       - Tags (multi-select)
       - Custom metadata fields (key-value)
     - Date range picker (upload date from/to)

4. **Settings Tab** (if editing)
   - Same form as Create/Edit page
   - Warning if changing config that requires reindex

### KB Selection in Prompt Editor

**Integration in `PromptCreate.tsx`:**

Add new section after "Tag Association":

```tsx
{/* Knowledge Bases Section */}
<div className="space-y-2">
  <label className="block text-sm font-medium text-gray-700">
    Knowledge Bases (Optional)
  </label>
  <KBSelector
    organizationId={organizationId}
    selectedKbIds={selectedKbIds}
    onSelectionChange={setSelectedKbIds}
    multiple={true}
  />
  <InfoTooltip
    title="Knowledge Base RAG"
    content="Select knowledge bases to enable RAG. The LLM will search these KBs for relevant context when processing documents."
  />
</div>
```

**KBSelector Component:**
- Multi-select dropdown/checkboxes
- Shows KB name, document count, status
- Disabled if KB status is "error" or "indexing"
- Empty state: "No knowledge bases available"

### Status Indicators

**KB Status Badges:**
- 🟢 **Active**: Ready for use
- 🟡 **Indexing**: Currently indexing documents
- 🔴 **Error**: Configuration error or indexing failure
- ⚪ **Pending Reindex**: Config changed, needs reindex

**Document Status in KB:**
- ✅ **Indexed**: Entry exists in `document_index` collection for `(kb_id, document_id)` AND vectors exist
- ⚪ **Not Indexed**: No entry in `document_index` for `(kb_id, document_id)`
- Note: No separate "indexing" or "failed" status - check queue if needed for UI

### Error Handling UI (Simplified)

**Failed Indexing:**
- Document simply won't appear in KB's document list (not in `kb_indexed_in`)
- Retry by re-queuing indexing job (tags still match, so will retry automatically)
- No need to track error messages separately - worker logs contain details

**KB Configuration Errors:**
- Validation errors inline in form
- API errors via toast notifications
- Status change to "error" with details

### Monitoring & Analytics (Future Enhancement)

**KB Dashboard Widget:**
- Indexing queue depth
- Average indexing time
- Search query count
- Most searched KBs
- Cost tracking (embedding API usage)

---

## Missing Functionality & Considerations

### Identified Gaps

1. **Reindexing UI**
   - When KB config changes (chunking/embedding), need UI to:
     - Show warning that reindex is required
     - Queue reindex job for all documents
     - Show progress (X of Y documents reindexed)
     - Allow canceling reindex

2. **Indexing Queue Status (Simplified)**
   - No separate queue status needed
   - To check if document is being indexed: check if message exists in queue (optional)
   - UI can show "Indexing..." if document has matching tags but not yet in `kb_indexed_in`

4. **Cost Tracking**
   - Track embedding API costs per KB
   - Display in KB detail page
   - Monthly/quarterly cost reports

5. **Bulk Operations**
   - Bulk delete documents from KB (when tags removed)
   - Bulk reindex
   - Export KB metadata

6. **Search Analytics**
   - Track search queries and results
   - Most common queries per KB
   - Search performance metrics

7. **Migration/Backup**
   - Export KB configuration
   - Import KB configuration
   - Backup vectors (for disaster recovery)

8. **Vector Index Management**
   - UI to trigger index creation/rebuild
   - Index health check
   - Index size/storage metrics

9. **OCR Integration Point**
   - Need to document where OCR worker triggers KB indexing
   - Add hook in OCR completion handler
   - Show in document status that KB indexing is queued

10. **Rate Limiting & Quotas**
    - Per-org limits on KBs
    - Per-KB limits on documents/chunks
    - Embedding API rate limit handling

### Recommended Additions

**To Data Model:**
- Add `document_index` collection (tracks doc-KB associations)
- Store document metadata in vectors: `document_name`, `upload_date`, `tag_ids`, `metadata`
- Add `last_searched_at` to `knowledge_bases` for analytics (optional)

**To API:**
- `POST /v0/orgs/{org_id}/knowledge-bases/{kb_id}/reindex` - Queue reindex for all documents in KB
- `GET /v0/orgs/{org_id}/knowledge-bases/{kb_id}/stats` - Get KB statistics (document count, chunk count)

**To Implementation:**
- Add OCR completion hook to trigger KB indexing (in `msg_handlers/ocr.py`)
- Add retry logic with exponential backoff for embedding API failures
- Add cost tracking middleware for embedding API calls (optional)
- Simple status: document indexed if entry exists in `document_index` for `(kb_id, document_id)`

---

## Appendix: Configuration Reference

### KB Configuration Defaults

```python
KB_DEFAULTS = {
    "chunker_type": "recursive",
    "chunk_size": 512,           # tokens
    "chunk_overlap": 128,        # tokens  
    "embedding_model": "text-embedding-3-small",
    "coalesce_neighbors": 0,     # 0 = disabled, or number of neighbors to include
    "status": "active"
}
```

### Embedding Model Dimensions

```python
EMBEDDING_DIMENSIONS = {
    "text-embedding-3-small": 1536,
    "text-embedding-3-large": 3072,
    "text-embedding-ada-002": 1536,
    "embed-english-v3.0": 1024,
    "embed-multilingual-v3.0": 1024,
}
```

### Limits

```python
KB_LIMITS = {
    "max_kbs_per_org": 20,
    "max_chunks_per_document": 500,
    "max_chunk_size": 2000,      # tokens
    "min_chunk_size": 50,        # tokens
    "max_top_k": 20,
    "max_tool_iterations": 10,
    "max_coalesce_neighbors": 5  # Maximum neighboring chunks to include
}
```

---

## Design Review Summary

### 🎯 Simplifications Made

1. **Index Tracking**: Separate `document_index` collection (not in `docs`)
   - Clean separation: KB functionality doesn't modify core `docs` collection
   - Simple schema: `(kb_id, document_id, indexed_at, chunk_count)`
   - Status: Document indexed if entry exists in `document_index`

2. **Metadata Search**: Integrated into vector search
   - Supports: Document metadata (name, tags, custom fields), upload date range
   - Efficient: Filtering happens during vector search for optimal performance
   - Flexible: Can combine multiple metadata filters with date ranges

3. **Status Management**: Removed complex state machine
   - Removed: "pending", "indexing", "failed" states
   - Now: Binary - indexed or not indexed
   - Simpler: No state transitions to manage

4. **Queue Monitoring**: Removed separate queue status
   - Removed: Complex queue status tracking
   - Now: Simple stats endpoint (document count, chunk count)
   - Simpler: Check if document is indexed, not queue position

### ✅ Core Features Covered

1. **Per-KB Architecture**: Each KB has its own collection and embedding model
2. **Tag-Based Association**: Documents automatically indexed based on tag matching
3. **OCR-Gated Indexing**: Indexing happens **after** OCR completes (sequential, not parallel)
4. **Chunk Coalescing**: Configurable neighbor chunk inclusion for better context
5. **Metadata Search**: Document metadata and upload date range filtering in vector search
6. **Atomic Operations**: Transactional indexing with idempotency
7. **Agentic LLM**: KB search tool for RAG during prompt execution
8. **Complete UI Design**: List, create, edit, detail, and search interfaces
9. **Clean Separation**: `document_index` collection separates KB functionality from core docs

### ⚠️ Implementation Considerations

1. **OCR Integration**: Must hook into OCR completion handler (`msg_handlers/ocr.py`)
2. **Vector Index Creation**: Need migration script to create indexes on KB creation
3. **Error Recovery**: Implement retry logic with exponential backoff for embedding API
4. **Document Index Collection**: Create new `document_index` collection (no migration needed)
5. **Reindexing**: UI and API for triggering full reindex when config changes
6. **Cost Tracking**: Optional middleware to track embedding API usage per KB

### 🔮 Future Enhancements (Post-MVP)

1. **Analytics Dashboard**: Search query analytics, cost tracking, performance metrics
2. **Hybrid Search**: Combine vector search with keyword search (MongoDB full-text)
3. **Reranking**: Cross-encoder models to improve result quality
4. **KB Sharing**: Enterprise feature to share KBs across organizations
5. **Export/Import**: Backup and migration capabilities
6. **Versioning**: Track KB configuration changes over time
7. **A/B Testing**: Compare different chunking/embedding strategies

### 📋 Pre-Implementation Checklist

- [ ] Verify MongoDB version supports vector search (Atlas or 8.2+)
- [ ] Test Chonkie integration with sample documents
- [ ] Verify LiteLLM embedding API access and rate limits
- [ ] Design vector index creation migration
- [ ] Plan OCR worker integration point
- [ ] Design error handling and retry strategy
- [ ] Plan cost tracking implementation
- [ ] Design queue monitoring approach

---

**Document Version**: 2.2  
**Last Updated**: 2026-01-22  
**Author**: DocRouter Development Team