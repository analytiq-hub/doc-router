"""Shared helpers for knowledge-base tests (embedding mocks, API setup, cleanup)."""

from __future__ import annotations

from datetime import datetime, UTC
from typing import Any, Tuple
from unittest.mock import Mock

from bson import ObjectId

import analytiq_data as ad
from analytiq_data.kb.chunking_config import chunking_preprocess_for_preset

from .conftest_utils import TEST_ORG_ID, client, get_auth_headers

MOCK_EMBEDDING_DIMENSIONS = 1536


def create_mock_embedding_response(num_embeddings: int = 1):
    """Non-zero vectors for cosine similarity; Mock (not AsyncMock) for get_embedding_cost()."""
    mock_response = Mock()
    embeddings = []
    for _ in range(num_embeddings):
        embedding = [0.001 * (j % 100 + 1) for j in range(MOCK_EMBEDDING_DIMENSIONS)]
        embeddings.append({"embedding": embedding})
    mock_response.data = embeddings
    return mock_response


def create_tag_api(name: str, color: str = "#FF5733") -> str:
    r = client.post(
        f"/v0/orgs/{TEST_ORG_ID}/tags",
        json={"name": name, "color": color},
        headers=get_auth_headers(),
    )
    assert r.status_code == 200
    return r.json()["id"]


def create_kb_api(name: str, tag_ids: list, **kwargs) -> str:
    payload = {
        "name": name,
        "tag_ids": tag_ids,
        "chunker_type": "recursive",
        "chunk_size": 100,
        "chunk_overlap": 20,
        **kwargs,
    }
    r = client.post(
        f"/v0/orgs/{TEST_ORG_ID}/knowledge-bases",
        json=payload,
        headers=get_auth_headers(),
    )
    assert r.status_code == 200
    return r.json()["kb_id"]


def delete_kb_api(kb_id: str) -> None:
    client.delete(
        f"/v0/orgs/{TEST_ORG_ID}/knowledge-bases/{kb_id}",
        headers=get_auth_headers(),
    )


async def create_active_kb_api(
    tag_name: str, kb_name: str, **kb_kwargs: Any
) -> Tuple[str, str, Any]:
    """Create tag + KB via HTTP, set KB status to active (for prompts). Returns (tag_id, kb_id, analytiq_client)."""
    tag_id = create_tag_api(tag_name)
    kb_id = create_kb_api(kb_name, [tag_id], **kb_kwargs)
    analytiq_client = ad.common.get_analytiq_client()
    db = ad.common.get_async_db(analytiq_client)
    await db.knowledge_bases.update_one(
        {"_id": ObjectId(kb_id)},
        {"$set": {"status": "active"}},
    )
    return tag_id, kb_id, analytiq_client


async def cleanup_org_kb_artifacts(test_db) -> None:
    """Remove docs, KBs, and tags for the test org (used in comprehensive KB scenario tests)."""
    await test_db.docs.delete_many({"organization_id": TEST_ORG_ID})
    await test_db.knowledge_bases.delete_many({"organization_id": TEST_ORG_ID})
    await test_db.tags.delete_many({"organization_id": TEST_ORG_ID})


async def insert_org_tag(test_db, name: str, color: str = "#FF5733") -> str:
    """Insert a tag for TEST_ORG_ID (no HTTP). Returns tag id string."""
    oid = ObjectId()
    await test_db.tags.insert_one(
        {
            "_id": oid,
            "organization_id": TEST_ORG_ID,
            "name": name,
            "color": color,
            "created_at": datetime.now(UTC),
        }
    )
    return str(oid)


async def insert_minimal_kb(
    test_db,
    tag_ids: list,
    *,
    name: str = "Direct KB",
    chunk_size: int = 50,
    chunk_overlap: int = 10,
    embedding_model: str = "text-embedding-3-small",
    embedding_dimensions: int = MOCK_EMBEDDING_DIMENSIONS,
) -> str:
    """
    Insert an active knowledge base without POST /knowledge-bases (no createSearchIndexes).
    For tests that need KB rows but should not register search indexes with mongot.
    """
    now = datetime.now(UTC)
    preset = "structured_doc"
    kb_doc = {
        "organization_id": TEST_ORG_ID,
        "name": name,
        "description": "",
        "system_prompt": "",
        "tag_ids": tag_ids,
        "chunker_type": "recursive",
        "chunk_size": chunk_size,
        "chunk_overlap": chunk_overlap,
        "embedding_model": embedding_model,
        "embedding_dimensions": embedding_dimensions,
        "coalesce_neighbors": 0,
        "reconcile_enabled": False,
        "reconcile_interval_seconds": None,
        "min_vector_score": None,
        "chunking_preset": preset,
        "chunking_preprocess": chunking_preprocess_for_preset(preset).model_dump(),
        "last_reconciled_at": None,
        "status": "active",
        "document_count": 0,
        "chunk_count": 0,
        "created_at": now,
        "updated_at": now,
    }
    r = await test_db.knowledge_bases.insert_one(kb_doc)
    return str(r.inserted_id)
