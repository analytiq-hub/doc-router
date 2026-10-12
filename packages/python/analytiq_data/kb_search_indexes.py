"""
Atlas Search / MongoDB Search index definitions for knowledge-base vector collections.

Each KB uses collection ``kb_vectors_<kb_id>`` with:
- ``kb_vector_index`` — vector search on ``embedding`` (and filter fields)
- ``kb_lexical_index`` — full-text search on ``chunk_text`` (and filter fields for ``$search`` compound filters)

Index names used in $vectorSearch / $search and createSearchIndexes: ``kb_vector_index``, ``kb_lexical_index``.

This module lives at ``analytiq_data.kb_search_indexes`` (not under ``kb/``) so migrations can import it
without loading the heavy ``analytiq_data.kb`` package.
"""

KB_VECTOR_INDEX_NAME = "kb_vector_index"
KB_LEXICAL_INDEX_NAME = "kb_lexical_index"


def kb_vector_search_index_definition(embedding_dimensions: int) -> dict:
    """Vector Search index definition (same shape as createSearchIndexes ``indexes[]`` item)."""
    return {
        "name": KB_VECTOR_INDEX_NAME,
        "type": "vectorSearch",
        "definition": {
            "fields": [
                {
                    "type": "vector",
                    "path": "embedding",
                    "numDimensions": embedding_dimensions,
                    "similarity": "cosine",
                },
                {"type": "filter", "path": "organization_id"},
                {"type": "filter", "path": "metadata_snapshot.tag_ids"},
                {"type": "filter", "path": "metadata_snapshot.upload_date"},
            ]
        },
    }


def kb_lexical_search_index_definition() -> dict:
    """
    Atlas Search (Lucene) index for lexical retrieval on ``chunk_text``.

    Includes ``heading_path`` for future structured chunking; documents without the field are fine.
    Filter paths align with ``build_vector_search_filter`` / ``$search`` compound filters.
    """
    return {
        "name": KB_LEXICAL_INDEX_NAME,
        "type": "search",
        "definition": {
            "mappings": {
                "dynamic": False,
                "fields": {
                    "chunk_text": {"type": "string"},
                    "heading_path": {"type": "string"},
                    # token (not string) so Atlas Search ``equals`` / ``in`` match exactly
                    "organization_id": {"type": "token"},
                    "metadata_snapshot": {
                        "type": "document",
                        "fields": {
                            "tag_ids": {"type": "token"},
                            "upload_date": {"type": "date"},
                        },
                    },
                }
            }
        },
    }
