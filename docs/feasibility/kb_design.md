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

## Vector Search & RAG

### Search Logic
*   **Metadata Filtering**: Filters (by name, tags, or custom metadata) are applied **inside** the `$vectorSearch` stage for performance.
*   **Dimension Isolation**: Searches across multiple KBs are performed in parallel if dimensions differ.
*   **Chunk Coalescing**: If `coalesce_neighbors > 0`, the search returns the matched chunk plus N preceding and succeeding chunks for broader context.

### Agentic Integration
Prompts include a `kb_ids` list. When executed, the LLM is provided with a `search_knowledge_base` tool. The LLM can call this tool multiple times to gather context before producing a final schema-compliant response.

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

| Endpoint | Description |
| :--- | :--- |
| `POST /knowledge-bases` | Create KB (auto-detects dimensions) |
| `GET /knowledge-bases` | List KBs with stats |
| `POST /knowledge-bases/{id}/reindex` | Trigger full reindex |
| `POST /knowledge-bases/search` | Test search (debug tool) |
| `GET /knowledge-bases/{id}/documents` | List documents currently in KB |

---

## Implementation Phases

1.  **Phase 1: Infrastructure**: Data models, dynamic collection management, and dimension auto-detection.
2.  **Phase 2: Pipeline**: Integration with Chonkie (chunking) and LiteLLM (embeddings).
3.  **Phase 3: Workers**: `kb_index` queue, Blue-Green worker logic, and OCR hooks.
4.  **Phase 4: Search & RAG**: Vector search implementation and Agentic LLM tool integration.
5.  **Phase 5: Maintenance**: Reconciliation service and cleanup hooks.
6.  **Phase 6: UI**: KB management dashboard and search testing interface.