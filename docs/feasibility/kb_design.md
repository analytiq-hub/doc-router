# Knowledge Base (KB) Design Document

## Overview

This document outlines the design for implementing Knowledge Base (KB) support in DocRouter. Knowledge Bases enable organizations to store, search, and retrieve document content using vector embeddings for RAG (Retrieval-Augmented Generation) during LLM document processing.

## Requirements Summary

1.  **Multi-KB Support**: Each organization can create one or more knowledge bases.
2.  **Per-KB Embeddings**: Each KB uses its own embedding model and vector collection.
3.  **Tag-Based Association**: Documents are associated with KBs automatically via tags.
4.  **OCR-Gated Indexing**: KB indexing runs only after OCR completes successfully.
5.  **Auto-Reindexing**: Tag changes or document updates trigger reindexing.
6.  **Vector Storage**: MongoDB vector search (Atlas or self-hosted 8.2+).
7.  **Embedding Provider**: LiteLLM for unified embedding generation.
8.  **Agentic LLM**: Prompts can reference KBs; LLM uses a search tool for context.
9.  **Atomic Operations**: Indexing uses a "Blue-Green" swap pattern for zero-downtime.
10. **Self-Healing**: A reconciliation service fixes drift between tags and indexes.

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
```

---

## Data Models

### Collection: `knowledge_bases`
Stores the configuration for each KB.

```python
{
    "_id": ObjectId,
    "organization_id": str,
    "name": str,
    "description": str,
    "tag_ids": List[str],               # Bridge to documents
    
    # Configuration
    "chunker_type": str,                # "recursive" | "sentence" | "token"
    "chunk_size": int,                  # tokens
    "chunk_overlap": int,               # tokens
    "embedding_model": str,             # LiteLLM model string
    "embedding_dimensions": int,        # Auto-detected on creation
    "coalesce_neighbors": int,          # Context window size (0-5)
    
    # Stats & Metadata
    "status": str,                      # "active" | "reconfiguring" | "error"
    "document_count": int,
    "chunk_count": int,
    "created_at": datetime,
    "updated_at": datetime
}
```

### Collection: `document_index`
The source of truth for KB membership. Separates KB logic from the core `docs` collection.

```python
{
    "_id": ObjectId,
    "organization_id": str,
    "kb_id": str,
    "document_id": str,
    "indexed_at": datetime,
    "chunk_count": int
}
```

### Collection: `kb_vectors_{kb_id}`
Dynamically created per KB to allow different embedding dimensions.

```python
{
    "_id": ObjectId,
    "organization_id": str,
    "document_id": str,
    "chunk_index": int,
    "chunk_text": str,
    "embedding": List[float],
    "token_count": int,
    "metadata_snapshot": dict,          # Snapshot of doc metadata for filtering
    "indexed_at": datetime
}
```

---

## Indexing Workflow (Robust & Atomic)

### 1. The "Blue-Green" Atomic Swap
To ensure zero-downtime and prevent partial indexing states, the worker uses a transactional swap:
1.  **Generate**: Chunks and embeddings are prepared in memory.
2.  **Transaction**:
    *   Delete all existing vectors for `(kb_id, document_id)`.
    *   Insert the new batch of vectors.
    *   Update/Upsert the `document_index` entry.
    *   Adjust KB-level statistics.
3.  **Rollback**: If any step fails (API timeout, DB error), the transaction rolls back, and the old vectors remain searchable.

### 2. Triggers
*   **OCR Completion**: Successful OCR automatically evaluates document tags and queues indexing for matching KBs.
*   **Tag Updates**: Adding/removing tags on a document triggers an immediate membership check.
*   **Manual Reindex**: A KB-level "Reindex All" operation queues jobs for every document in the `document_index`.

### 3. Self-Healing (Reconciliation)
A background service runs periodically to fix "drift":
*   **Missing**: Documents with matching tags but no `document_index` entry are queued for indexing.
*   **Stale**: Documents in `document_index` whose tags no longer match the KB are queued for removal.
*   **Orphans**: Vectors in `kb_vectors_*` without a corresponding `document_index` entry are purged.

---

## LiteLLM Integration

LiteLLM provides a unified interface for embedding models across multiple providers (OpenAI, Cohere, Azure OpenAI, etc.). This allows KBs to use different embedding models while maintaining a consistent code path.

### Embedding Model Selection

Each KB specifies an `embedding_model` using LiteLLM's model naming convention:
- `text-embedding-3-small` (OpenAI, 1536 dimensions)
- `text-embedding-3-large` (OpenAI, 3072 dimensions)
- `embed-english-v3.0` (Cohere, 1024 dimensions)
- `embed-multilingual-v3.0` (Cohere, 1024 dimensions)

### API Key Management

LiteLLM requires provider-specific API keys. The system uses the existing `llm_providers` collection pattern:

1. **Provider Lookup**: LiteLLM maps model names to providers (e.g., `text-embedding-3-small` → `openai`)
2. **Key Retrieval**: Uses `ad.llm.get_llm_key(analytiq_client, provider)` which:
   - Queries `llm_providers` collection by `litellm_provider`
   - Decrypts the stored token using `ad.crypto.decrypt_token()`
   - Returns the API key for LiteLLM calls
3. **Key Storage**: API keys are stored encrypted in MongoDB, populated from environment variables during startup

### Embedding Generation

**During Indexing**:
```python
import litellm

# Get provider and API key
provider = litellm.get_model_info(embedding_model)["provider"]
api_key = await ad.llm.get_llm_key(analytiq_client, provider)

# Generate embeddings in batches
response = await litellm.aembedding(
    model=embedding_model,
    input=[chunk.text for chunk in chunks],  # Batch of texts
    api_key=api_key
)

embeddings = [item["embedding"] for item in response.data]
```

**During Search**:
- Query text is embedded using the KB's embedding model and API key pattern

### Dimension Auto-Detection

On KB creation, the system automatically detects embedding dimensions:
1. Makes a test call: `litellm.aembedding(model=embedding_model, input=["test"])`
2. Extracts the dimension count from the response
3. Stores `embedding_dimensions` in the KB config
4. Uses this value when creating the MongoDB vector search index

### Error Handling & Retries

- **Retry Logic**: Uses `stamina` library with exponential backoff for transient errors (rate limits, timeouts, 503 errors)
- **Rate Limiting**: Workers respect provider-specific rate limits to prevent 429 errors
- **Batch Processing**: Embeddings are generated in batches (default: 100 texts per batch) to optimize API usage

---

## Vector Search & RAG

### Search Logic

**Metadata Filtering**: Filters (by document name, tags, or custom metadata) are applied **inside** MongoDB's `$vectorSearch` stage for optimal performance. This ensures:
- Filtering happens during vector search, not after
- Results are ranked by similarity within the filtered set
- MongoDB optimizes the combined vector + metadata query

**Chunk Coalescing**: If `coalesce_neighbors > 0`, the search:
1. Finds the top K matching chunks via vector search
2. For each matched chunk, fetches N preceding and N succeeding chunks from the same document
3. Returns the expanded context set
4. The matched chunk retains its similarity score; neighboring chunks are marked with `is_matched: false`

### Agentic LLM Integration

**Prompt Configuration**: Prompts can include a `kb_id` field (single KB ID to search).

**Tool Definition**: When a prompt with `kb_id` is executed, the LLM is provided with a `search_knowledge_base` tool:
```json
{
  "type": "function",
  "function": {
    "name": "search_knowledge_base",
    "description": "Search the knowledge base for relevant information",
    "parameters": {
      "type": "object",
      "properties": {
        "query": {"type": "string", "description": "Search query"},
        "top_k": {"type": "integer", "default": 5},
        "metadata_filter": {"type": "object"},
        "coalesce_neighbors": {"type": "integer"}
      },
      "required": ["query"]
    }
  }
}
```

**Agentic Loop**:
1. LLM receives the prompt and document text
2. If a KB is specified, the tool is available
3. LLM can call `search_knowledge_base` multiple times (up to `max_iterations`, default: 5)
4. Each tool call performs vector search within the specified KB
5. Results are returned to the LLM as context
6. LLM produces final response conforming to the prompt's schema

---

## Lifecycle & Maintenance

### Deletion Cleanup
*   **Document Delete**: Triggers a hook to remove all associated vectors and `document_index` entries across all KBs.
*   **KB Delete**: Drops the entire `kb_vectors_{kb_id}` collection and removes all related `document_index` entries.

### Error Handling
*   **Retries**: Embedding API calls use exponential backoff (via `stamina`).
*   **Rate Limiting**: Workers respect provider-specific rate limits to prevent 429 errors.
*   **Empty Docs**: Documents with no extractable text are logged as warnings and skipped.

---

## API Design

All endpoints are scoped under `/v0/orgs/{organization_id}/knowledge-bases` and require organization-level authentication.

### Create Knowledge Base

**Endpoint**: `POST /v0/orgs/{organization_id}/knowledge-bases`

**Request Body**:
```json
{
  "name": "Invoice KB",
  "description": "Knowledge base for invoice processing",
  "tag_ids": ["tag_id_1", "tag_id_2"],
  "chunker_type": "recursive",           // optional, default: "recursive"
  "chunk_size": 512,                     // optional, default: 512
  "chunk_overlap": 128,                  // optional, default: 128
  "embedding_model": "text-embedding-3-small",  // optional, default: "text-embedding-3-small"
  "coalesce_neighbors": 2               // optional, default: 0
}
```

**Response**:
```json
{
  "kb_id": "507f1f77bcf86cd799439011",
  "name": "Invoice KB",
  "description": "Knowledge base for invoice processing",
  "tag_ids": ["tag_id_1", "tag_id_2"],
  "embedding_model": "text-embedding-3-small",
  "embedding_dimensions": 1536,          // Auto-detected during creation
  "status": "active",
  "document_count": 0,
  "chunk_count": 0,
  "created_at": "2026-01-23T10:00:00Z"
}
```

**Behavior**: 
- Validates that all `tag_ids` exist and belong to the organization
- Automatically detects `embedding_dimensions` by calling LiteLLM with a test string
- Creates the `kb_vectors_{kb_id}` collection
- Creates the vector search index on the collection
- Sets initial status to `"active"`

### List Knowledge Bases

**Endpoint**: `GET /v0/orgs/{organization_id}/knowledge-bases?skip=0&limit=10&name_search=invoice`

**Query Parameters**:
- `skip`: Pagination offset (default: 0)
- `limit`: Results per page (default: 10, max: 100)
- `name_search`: Filter by KB name (case-insensitive partial match)

**Response**:
```json
{
  "knowledge_bases": [
    {
      "kb_id": "507f1f77bcf86cd799439011",
      "name": "Invoice KB",
      "description": "Knowledge base for invoice processing",
      "tag_ids": ["tag_id_1"],
      "status": "active",
      "document_count": 42,
      "chunk_count": 1250,
      "embedding_model": "text-embedding-3-small",
      "created_at": "2026-01-23T10:00:00Z"
    }
  ],
  "total_count": 1
}
```

### Get Knowledge Base

**Endpoint**: `GET /v0/orgs/{organization_id}/knowledge-bases/{kb_id}`

**Response**: Same structure as Create response, with full configuration details.

### Update Knowledge Base

**Endpoint**: `PUT /v0/orgs/{organization_id}/knowledge-bases/{kb_id}`

**Request Body**: Same as Create, but all fields are optional (only provided fields are updated).

**Important**: 
- Changing `chunker_type`, `chunk_size`, `chunk_overlap`, or `embedding_model` requires reindexing
- If these fields change, the KB status is set to `"reconfiguring"` and a reindex job is automatically queued
- Other fields (name, description, tag_ids, coalesce_neighbors) can be updated without reindexing

### Delete Knowledge Base

**Endpoint**: `DELETE /v0/orgs/{organization_id}/knowledge-bases/{kb_id}`

**Response**: `{"message": "Knowledge base deleted successfully"}`

**Behavior**: 
- Drops the `kb_vectors_{kb_id}` collection (including all vectors and the vector search index)
- Deletes all entries from `document_index` for this KB
- Deletes the KB configuration document

### List Documents in Knowledge Base

**Endpoint**: `GET /v0/orgs/{organization_id}/knowledge-bases/{kb_id}/documents?skip=0&limit=10`

**Response**:
```json
{
  "documents": [
    {
      "document_id": "507f191e810c19729de860ea",
      "document_name": "invoice-2024-001.pdf",
      "chunk_count": 15,
      "indexed_at": "2026-01-22T14:30:00Z"
    }
  ],
  "total_count": 42
}
```

**Implementation**: Queries `document_index` collection where `kb_id = {kb_id}`, joins with `docs` collection for document details.

### Reindex All Documents

**Endpoint**: `POST /v0/orgs/{organization_id}/knowledge-bases/{kb_id}/reindex`

**Response**:
```json
{
  "status": "queued",
  "document_count": 42,
  "message": "Reindexing queued for 42 documents"
}
```

**Behavior**: 
- Finds all documents in `document_index` for this KB
- Queues indexing jobs for each document
- Useful when chunking/embedding configuration changes

### Search Knowledge Base (Testing/Debug)

**Endpoint**: `POST /v0/orgs/{organization_id}/knowledge-bases/{kb_id}/search`

**Request Body**:
```json
{
  "query": "What are the payment terms?",
  "top_k": 5,                            // optional, default: 5
  "document_ids": ["doc_id_1"],          // optional, filter by specific documents
  "metadata_filter": {                   // optional
    "document_name": {"$regex": "invoice", "$options": "i"},
    "tag_ids": {"$in": ["invoice", "2024"]}
  },
  "upload_date_from": "2024-01-01T00:00:00Z",  // optional
  "upload_date_to": "2024-12-31T23:59:59Z",    // optional
  "coalesce_neighbors": 2                // optional, override KB default
}
```

**Response**:
```json
{
  "results": [
    {
      "content": "Payment is due within 30 days of invoice date...",
      "source": "invoice-2024-001.pdf",
      "relevance": 0.92,
      "chunk_index": 5,
      "is_matched": true                 // false if this is a neighboring chunk
    }
  ],
  "query": "What are the payment terms?"
}
```

**Behavior**: 
- Generates embedding for the query using the KB's embedding model
- Performs vector search within the specified KB
- Returns formatted results for LLM consumption

---

## Implementation Phases

1.  **Phase 1: Infrastructure**: Data models, dynamic collection management, and dimension auto-detection.
2.  **Phase 2: Pipeline**: Integration with Chonkie (chunking) and LiteLLM (embeddings).
3.  **Phase 3: Workers**: `kb_index` queue, Blue-Green worker logic, and OCR hooks.
4.  **Phase 4: Search & RAG**: Vector search implementation and Agentic LLM tool integration.
5.  **Phase 5: Maintenance**: Reconciliation service and cleanup hooks.
6.  **Phase 6: UI**: KB management dashboard and search testing interface.