"""
Fast KB API tests — index creation is mocked so these run in seconds.
For real-index integration tests see test_kb_indexing.py (make tests-kb).
"""

import pytest
from bson import ObjectId
import os
import logging
from unittest.mock import AsyncMock, patch

from .conftest_utils import client, TEST_ORG_ID, get_auth_headers
from .kb_test_helpers import create_mock_embedding_response

logger = logging.getLogger(__name__)

assert os.environ["ENV"] == "pytest"

MOCK_SEARCH_INDEX = patch(
    "app.routes.knowledge_bases.create_vector_search_index",
    new_callable=AsyncMock,
)
MOCK_EMBEDDING = patch("litellm.aembedding")
MOCK_MODEL_INFO = patch(
    "litellm.get_model_info", return_value={"provider": "openai"}
)


def _apply_embedding_mock(mock_embedding):
    mock_embedding.return_value = create_mock_embedding_response()


# ── helpers ──────────────────────────────────────────────────────────

def _create_kb(name="Test KB", **overrides):
    payload = {
        "name": name,
        "tag_ids": [],
        "chunker_type": "recursive",
        "chunk_size": 512,
        "chunk_overlap": 128,
        "embedding_model": "text-embedding-3-small",
        **overrides,
    }
    r = client.post(
        f"/v0/orgs/{TEST_ORG_ID}/knowledge-bases",
        json=payload,
        headers=get_auth_headers(),
    )
    return r


def _delete_kb(kb_id):
    client.delete(
        f"/v0/orgs/{TEST_ORG_ID}/knowledge-bases/{kb_id}",
        headers=get_auth_headers(),
    )


# ── tests ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
@MOCK_SEARCH_INDEX
@MOCK_MODEL_INFO
@MOCK_EMBEDDING
async def test_kb_lifecycle(mock_embedding, _mock_model_info, _mock_idx, test_db, mock_auth, setup_test_models):
    """Full CRUD lifecycle: create → list → get → update → delete → verify gone."""
    _apply_embedding_mock(mock_embedding)

    resp = _create_kb(
        name="Test Invoice KB",
        description="Knowledge base for invoice processing",
        system_prompt="Always prefer vendor names from the header.",
        coalesce_neighbors=2,
    )
    assert resp.status_code == 200, f"Create failed: {resp.text}"
    kb = resp.json()
    assert kb["name"] == "Test Invoice KB"
    assert kb["description"] == "Knowledge base for invoice processing"
    assert kb["embedding_dimensions"] > 0
    assert kb["status"] == "indexing"
    assert kb["document_count"] == 0
    assert kb["chunk_count"] == 0
    assert kb.get("system_prompt") == "Always prefer vendor names from the header."
    kb_id = kb["kb_id"]

    try:
        # List
        lr = client.get(f"/v0/orgs/{TEST_ORG_ID}/knowledge-bases", headers=get_auth_headers())
        assert lr.status_code == 200
        assert any(k["kb_id"] == kb_id for k in lr.json()["knowledge_bases"])

        # Get (BackgroundTasks from create have finished under TestClient, so status is active)
        gr = client.get(f"/v0/orgs/{TEST_ORG_ID}/knowledge-bases/{kb_id}", headers=get_auth_headers())
        assert gr.status_code == 200
        assert gr.json()["status"] == "active"
        assert gr.json()["embedding_model"] == "text-embedding-3-small"
        assert gr.json()["chunk_size"] == 512

        # Update
        ur = client.put(
            f"/v0/orgs/{TEST_ORG_ID}/knowledge-bases/{kb_id}",
            json={
                "name": "Updated Invoice KB",
                "description": "Updated description",
                "system_prompt": "Updated KB instructions.",
                "coalesce_neighbors": 3,
            },
            headers=get_auth_headers(),
        )
        assert ur.status_code == 200
        updated = ur.json()
        assert updated["name"] == "Updated Invoice KB"
        assert updated["system_prompt"] == "Updated KB instructions."
        assert updated["coalesce_neighbors"] == 3
        assert updated["chunk_size"] == 512  # immutable
        assert updated["embedding_model"] == "text-embedding-3-small"  # immutable

        # Delete
        dr = client.delete(f"/v0/orgs/{TEST_ORG_ID}/knowledge-bases/{kb_id}", headers=get_auth_headers())
        assert dr.status_code == 200
        assert dr.json()["message"] == "Knowledge base deleted successfully"

        # Verify gone
        assert client.get(
            f"/v0/orgs/{TEST_ORG_ID}/knowledge-bases/{kb_id}", headers=get_auth_headers()
        ).status_code == 404
    finally:
        _delete_kb(kb_id)


@pytest.mark.asyncio
async def test_kb_create_validation(test_db, mock_auth, setup_test_models):
    """Pydantic validation rejects bad payloads before hitting the DB."""
    cases = [
        {"name": "X", "chunker_type": "invalid_chunker"},
        {"name": "X", "chunk_size": 100, "chunk_overlap": 150},
        {"name": "X", "chunk_size": 10},
        {"name": "X", "chunk_size": 5000},
        {"name": "X", "coalesce_neighbors": 10},
    ]
    for payload in cases:
        r = client.post(
            f"/v0/orgs/{TEST_ORG_ID}/knowledge-bases",
            json=payload,
            headers=get_auth_headers(),
        )
        assert r.status_code == 422, f"Expected 422 for {payload}, got {r.status_code}"


@pytest.mark.asyncio
@MOCK_SEARCH_INDEX
@MOCK_MODEL_INFO
@MOCK_EMBEDDING
async def test_kb_list_pagination(mock_embedding, _mock_model_info, _mock_idx, test_db, mock_auth, setup_test_models):
    """Pagination (skip/limit) and name search."""
    _apply_embedding_mock(mock_embedding)
    kb_ids = []

    try:
        for i in range(5):
            r = _create_kb(name=f"Test KB {i}", description=f"KB number {i}")
            assert r.status_code == 200
            kb_ids.append(r.json()["kb_id"])

        # Paginate
        lr = client.get(
            f"/v0/orgs/{TEST_ORG_ID}/knowledge-bases?skip=0&limit=2",
            headers=get_auth_headers(),
        )
        assert lr.status_code == 200
        assert len(lr.json()["knowledge_bases"]) == 2
        assert lr.json()["total_count"] >= 5

        # Name search
        sr = client.get(
            f"/v0/orgs/{TEST_ORG_ID}/knowledge-bases?name_search=KB 1",
            headers=get_auth_headers(),
        )
        assert sr.status_code == 200
        assert any("KB 1" in kb["name"] for kb in sr.json()["knowledge_bases"])
    finally:
        for kb_id in kb_ids:
            _delete_kb(kb_id)


@pytest.mark.asyncio
@MOCK_SEARCH_INDEX
@MOCK_MODEL_INFO
@MOCK_EMBEDDING
async def test_kb_documents_list(mock_embedding, _mock_model_info, _mock_idx, test_db, mock_auth, setup_test_models):
    """Listing documents on a fresh KB returns empty."""
    _apply_embedding_mock(mock_embedding)

    r = _create_kb(name="Test KB for Documents")
    assert r.status_code == 200
    kb_id = r.json()["kb_id"]

    try:
        lr = client.get(
            f"/v0/orgs/{TEST_ORG_ID}/knowledge-bases/{kb_id}/documents",
            headers=get_auth_headers(),
        )
        assert lr.status_code == 200
        assert lr.json()["total_count"] == 0
        assert len(lr.json()["documents"]) == 0
    finally:
        _delete_kb(kb_id)


@pytest.mark.asyncio
@MOCK_SEARCH_INDEX
@MOCK_MODEL_INFO
@MOCK_EMBEDDING
async def test_kb_search(mock_embedding, _mock_model_info, _mock_idx, test_db, mock_auth, setup_test_models):
    """Search on an empty KB returns zero results."""
    _apply_embedding_mock(mock_embedding)

    r = _create_kb(name="Test Search KB")
    assert r.status_code == 200
    kb_id = r.json()["kb_id"]

    try:
        sr = client.post(
            f"/v0/orgs/{TEST_ORG_ID}/knowledge-bases/{kb_id}/search",
            json={"query": "test query", "top_k": 5},
            headers=get_auth_headers(),
        )
        assert sr.status_code == 200
        body = sr.json()
        assert body["query"] == "test query"
        assert body["total_count"] == 0
    finally:
        _delete_kb(kb_id)


@pytest.mark.asyncio
async def test_kb_not_found_errors(test_db, mock_auth, setup_test_models):
    """GET / PUT / DELETE on a non-existent KB all return 404."""
    fake = str(ObjectId())
    for method, kwargs in [
        ("get", {}),
        ("put", {"json": {"name": "Updated"}}),
        ("delete", {}),
    ]:
        r = getattr(client, method)(
            f"/v0/orgs/{TEST_ORG_ID}/knowledge-bases/{fake}",
            headers=get_auth_headers(),
            **kwargs,
        )
        assert r.status_code == 404, f"{method.upper()} should 404, got {r.status_code}"


@pytest.mark.asyncio
@MOCK_SEARCH_INDEX
@MOCK_MODEL_INFO
@MOCK_EMBEDDING
async def test_kb_immutable_fields(mock_embedding, _mock_model_info, _mock_idx, test_db, mock_auth, setup_test_models):
    """embedding_model is immutable; chunker_type, chunk_size are mutable."""
    _apply_embedding_mock(mock_embedding)

    r = _create_kb(
        name="Test Immutable KB",
        chunker_type="recursive",
        chunk_size=512,
        chunk_overlap=128,
        embedding_model="text-embedding-3-small",
    )
    assert r.status_code == 200
    kb_id = r.json()["kb_id"]

    try:
        ur = client.put(
            f"/v0/orgs/{TEST_ORG_ID}/knowledge-bases/{kb_id}",
            json={
                "name": "Updated Name",
                "chunker_type": "token",
                "chunk_size": 256,
                "embedding_model": "text-embedding-3-large",  # should be ignored
            },
            headers=get_auth_headers(),
        )
        assert ur.status_code == 200
        updated = ur.json()
        assert updated["name"] == "Updated Name"
        assert updated["chunker_type"] == "token"
        assert updated["chunk_size"] == 256
        assert updated["embedding_model"] == "text-embedding-3-small"  # unchanged
    finally:
        _delete_kb(kb_id)
