import pytest
from bson import ObjectId
import os
from datetime import datetime, UTC
import logging
from unittest.mock import patch, AsyncMock
import asyncio

# Import shared test utilities
from .conftest_utils import (
    client, TEST_ORG_ID, 
    get_auth_headers
)
import analytiq_data as ad

logger = logging.getLogger(__name__)

# Check that ENV is set to pytest
assert os.environ["ENV"] == "pytest"

# Note: Only LiteLLM API calls are mocked (to avoid external API costs and key requirements).
# MongoDB operations, including vector search index creation, use the real MongoDB instance.
# The test MongoDB (localhost:27017) must support vector search (mongodb-atlas-local or MongoDB 8.2+).

# Mock embedding response for dimension detection
MOCK_EMBEDDING_DIMENSIONS = 1536

def create_mock_embedding_response(num_embeddings=1):
    """Create a mock embedding response with non-zero vectors (required for cosine similarity)"""
    mock_response = AsyncMock()
    # Generate non-zero embeddings (simple pattern that's not all zeros)
    # Use a small non-zero value to avoid zero vector issues with MongoDB cosine similarity
    embeddings = []
    for i in range(num_embeddings):
        # Create a simple non-zero vector: [0.1, 0.2, 0.3, ...] pattern
        embedding = [0.001 * (j % 100 + 1) for j in range(MOCK_EMBEDDING_DIMENSIONS)]
        embeddings.append({"embedding": embedding})
    mock_response.data = embeddings
    return mock_response

@pytest.mark.asyncio
@patch('litellm.get_model_info', return_value={"provider": "openai"})
@patch('litellm.aembedding')
async def test_kb_lifecycle(mock_embedding, mock_get_model_info, test_db, mock_auth, setup_test_models):
    """Test the complete knowledge base lifecycle"""
    logger.info(f"test_kb_lifecycle() start")
    
    # Set up mock embedding response
    mock_embedding.return_value = create_mock_embedding_response()
    
    try:
        # Step 1: Create a KB
        kb_data = {
            "name": "Test Invoice KB",
            "description": "Knowledge base for invoice processing",
            "tag_ids": [],
            "chunker_type": "recursive",
            "chunk_size": 512,
            "chunk_overlap": 128,
            "embedding_model": "text-embedding-3-small",
            "coalesce_neighbors": 2
        }
        
        create_response = client.post(
            f"/v0/orgs/{TEST_ORG_ID}/knowledge-bases",
            json=kb_data,
            headers=get_auth_headers()
        )
        
        assert create_response.status_code == 200, f"Create failed: {create_response.text}"
        kb_result = create_response.json()
        assert "kb_id" in kb_result
        assert kb_result["name"] == "Test Invoice KB"
        assert kb_result["description"] == "Knowledge base for invoice processing"
        assert kb_result["embedding_dimensions"] > 0, "Embedding dimensions should be auto-detected"
        assert kb_result["status"] in ["indexing", "active"]
        assert kb_result["document_count"] == 0
        assert kb_result["chunk_count"] == 0
        
        kb_id = kb_result["kb_id"]
        
        # Step 2: List KBs to verify it was created
        list_response = client.get(
            f"/v0/orgs/{TEST_ORG_ID}/knowledge-bases",
            headers=get_auth_headers()
        )
        
        assert list_response.status_code == 200
        list_data = list_response.json()
        assert "knowledge_bases" in list_data
        assert "total_count" in list_data
        
        # Find our KB in the list
        created_kb = next((kb for kb in list_data["knowledge_bases"] if kb["kb_id"] == kb_id), None)
        assert created_kb is not None, "KB should be in the list"
        assert created_kb["name"] == "Test Invoice KB"
        
        # Step 3: Get the specific KB to verify its content
        get_response = client.get(
            f"/v0/orgs/{TEST_ORG_ID}/knowledge-bases/{kb_id}",
            headers=get_auth_headers()
        )
        
        assert get_response.status_code == 200
        kb_data_retrieved = get_response.json()
        assert kb_data_retrieved["kb_id"] == kb_id
        assert kb_data_retrieved["name"] == "Test Invoice KB"
        assert kb_data_retrieved["embedding_model"] == "text-embedding-3-small"
        assert kb_data_retrieved["chunk_size"] == 512
        assert kb_data_retrieved["chunk_overlap"] == 128
        
        # Step 4: Update the KB (mutable fields only)
        update_data = {
            "name": "Updated Invoice KB",
            "description": "Updated description",
            "coalesce_neighbors": 3
        }
        
        update_response = client.put(
            f"/v0/orgs/{TEST_ORG_ID}/knowledge-bases/{kb_id}",
            json=update_data,
            headers=get_auth_headers()
        )
        
        assert update_response.status_code == 200
        updated_kb = update_response.json()
        assert updated_kb["name"] == "Updated Invoice KB"
        assert updated_kb["description"] == "Updated description"
        assert updated_kb["coalesce_neighbors"] == 3
        # Immutable fields should remain unchanged
        assert updated_kb["chunk_size"] == 512
        assert updated_kb["embedding_model"] == "text-embedding-3-small"
        
        # Step 5: Delete the KB
        delete_response = client.delete(
            f"/v0/orgs/{TEST_ORG_ID}/knowledge-bases/{kb_id}",
            headers=get_auth_headers()
        )
        
        assert delete_response.status_code == 200
        assert delete_response.json()["message"] == "Knowledge base deleted successfully"
        
        # Step 6: Verify deletion
        get_after_delete_response = client.get(
            f"/v0/orgs/{TEST_ORG_ID}/knowledge-bases/{kb_id}",
            headers=get_auth_headers()
        )
        
        assert get_after_delete_response.status_code == 404
        
    finally:
        pass  # mock_auth fixture handles cleanup

@pytest.mark.asyncio
async def test_kb_create_validation(test_db, mock_auth, setup_test_models):
    """Test KB creation validation"""
    logger.info(f"test_kb_create_validation() start")
    
    try:
        # Test invalid chunker_type
        invalid_kb = {
            "name": "Invalid KB",
            "chunker_type": "invalid_chunker"
        }
        response = client.post(
            f"/v0/orgs/{TEST_ORG_ID}/knowledge-bases",
            json=invalid_kb,
            headers=get_auth_headers()
        )
        assert response.status_code == 422  # Validation error
        
        # Test chunk_overlap >= chunk_size
        invalid_kb = {
            "name": "Invalid KB",
            "chunk_size": 100,
            "chunk_overlap": 150  # Overlap > size
        }
        response = client.post(
            f"/v0/orgs/{TEST_ORG_ID}/knowledge-bases",
            json=invalid_kb,
            headers=get_auth_headers()
        )
        assert response.status_code == 422
        
        # Test invalid chunk_size (too small)
        invalid_kb = {
            "name": "Invalid KB",
            "chunk_size": 10  # Below minimum
        }
        response = client.post(
            f"/v0/orgs/{TEST_ORG_ID}/knowledge-bases",
            json=invalid_kb,
            headers=get_auth_headers()
        )
        assert response.status_code == 422
        
        # Test invalid chunk_size (too large)
        invalid_kb = {
            "name": "Invalid KB",
            "chunk_size": 5000  # Above maximum
        }
        response = client.post(
            f"/v0/orgs/{TEST_ORG_ID}/knowledge-bases",
            json=invalid_kb,
            headers=get_auth_headers()
        )
        assert response.status_code == 422
        
        # Test invalid coalesce_neighbors
        invalid_kb = {
            "name": "Invalid KB",
            "coalesce_neighbors": 10  # Above maximum
        }
        response = client.post(
            f"/v0/orgs/{TEST_ORG_ID}/knowledge-bases",
            json=invalid_kb,
            headers=get_auth_headers()
        )
        assert response.status_code == 422
        
    finally:
        pass

@pytest.mark.asyncio
@patch('litellm.get_model_info', return_value={"provider": "openai"})
@patch('litellm.aembedding')
async def test_kb_list_pagination(mock_embedding, mock_get_model_info, test_db, mock_auth, setup_test_models):
    """Test KB list pagination and filtering"""
    logger.info(f"test_kb_list_pagination() start")
    
    # Set up mock embedding response
    mock_embedding.return_value = create_mock_embedding_response()
    
    try:
        # Create multiple KBs
        kb_ids = []
        for i in range(5):
            kb_data = {
                "name": f"Test KB {i}",
                "description": f"KB number {i}"
            }
            response = client.post(
                f"/v0/orgs/{TEST_ORG_ID}/knowledge-bases",
                json=kb_data,
                headers=get_auth_headers()
            )
            assert response.status_code == 200
            kb_ids.append(response.json()["kb_id"])
        
        # Test pagination
        list_response = client.get(
            f"/v0/orgs/{TEST_ORG_ID}/knowledge-bases?skip=0&limit=2",
            headers=get_auth_headers()
        )
        assert list_response.status_code == 200
        list_data = list_response.json()
        assert len(list_data["knowledge_bases"]) == 2
        assert list_data["total_count"] >= 5
        
        # Test name search
        search_response = client.get(
            f"/v0/orgs/{TEST_ORG_ID}/knowledge-bases?name_search=KB 1",
            headers=get_auth_headers()
        )
        assert search_response.status_code == 200
        search_data = search_response.json()
        assert any("KB 1" in kb["name"] for kb in search_data["knowledge_bases"])
        
        # Cleanup
        for kb_id in kb_ids:
            client.delete(
                f"/v0/orgs/{TEST_ORG_ID}/knowledge-bases/{kb_id}",
                headers=get_auth_headers()
            )
        
    finally:
        pass

@pytest.mark.asyncio
@patch('litellm.get_model_info', return_value={"provider": "openai"})
@patch('litellm.aembedding')
async def test_kb_documents_list(mock_embedding, mock_get_model_info, test_db, mock_auth, setup_test_models):
    """Test listing documents in a KB"""
    logger.info(f"test_kb_documents_list() start")
    
    # Set up mock embedding response
    mock_embedding.return_value = create_mock_embedding_response()
    
    try:
        # Create a KB
        kb_data = {
            "name": "Test KB for Documents",
            "tag_ids": []
        }
        create_response = client.post(
            f"/v0/orgs/{TEST_ORG_ID}/knowledge-bases",
            json=kb_data,
            headers=get_auth_headers()
        )
        assert create_response.status_code == 200
        kb_id = create_response.json()["kb_id"]
        
        # List documents (should be empty initially)
        list_response = client.get(
            f"/v0/orgs/{TEST_ORG_ID}/knowledge-bases/{kb_id}/documents",
            headers=get_auth_headers()
        )
        assert list_response.status_code == 200
        list_data = list_response.json()
        assert list_data["total_count"] == 0
        assert len(list_data["documents"]) == 0
        
        # Cleanup
        client.delete(
            f"/v0/orgs/{TEST_ORG_ID}/knowledge-bases/{kb_id}",
            headers=get_auth_headers()
        )
        
    finally:
        pass

@pytest.mark.asyncio
@patch('litellm.get_model_info', return_value={"provider": "openai"})
@patch('litellm.aembedding')
async def test_kb_search(mock_embedding, mock_get_model_info, test_db, mock_auth, setup_test_models):
    """Test KB search endpoint"""
    logger.info(f"test_kb_search() start")
    
    # Set up mock embedding response
    mock_embedding.return_value = create_mock_embedding_response()
    
    try:
        # Create a KB
        kb_data = {
            "name": "Test Search KB",
            "tag_ids": []
        }
        create_response = client.post(
            f"/v0/orgs/{TEST_ORG_ID}/knowledge-bases",
            json=kb_data,
            headers=get_auth_headers()
        )
        assert create_response.status_code == 200
        kb_id = create_response.json()["kb_id"]
        
        # Search (should return empty results for now)
        search_data = {
            "query": "test query",
            "top_k": 5
        }
        search_response = client.post(
            f"/v0/orgs/{TEST_ORG_ID}/knowledge-bases/{kb_id}/search",
            json=search_data,
            headers=get_auth_headers()
        )
        assert search_response.status_code == 200
        search_result = search_response.json()
        assert "results" in search_result
        assert "query" in search_result
        assert search_result["query"] == "test query"
        assert search_result["total_count"] == 0
        
        # Cleanup
        client.delete(
            f"/v0/orgs/{TEST_ORG_ID}/knowledge-bases/{kb_id}",
            headers=get_auth_headers()
        )
        
    finally:
        pass

@pytest.mark.asyncio
async def test_kb_not_found_errors(test_db, mock_auth, setup_test_models):
    """Test KB not found error handling"""
    logger.info(f"test_kb_not_found_errors() start")
    
    try:
        fake_kb_id = str(ObjectId())
        
        # Get non-existent KB
        get_response = client.get(
            f"/v0/orgs/{TEST_ORG_ID}/knowledge-bases/{fake_kb_id}",
            headers=get_auth_headers()
        )
        assert get_response.status_code == 404
        
        # Update non-existent KB
        update_response = client.put(
            f"/v0/orgs/{TEST_ORG_ID}/knowledge-bases/{fake_kb_id}",
            json={"name": "Updated"},
            headers=get_auth_headers()
        )
        assert update_response.status_code == 404
        
        # Delete non-existent KB
        delete_response = client.delete(
            f"/v0/orgs/{TEST_ORG_ID}/knowledge-bases/{fake_kb_id}",
            headers=get_auth_headers()
        )
        assert delete_response.status_code == 404
        
    finally:
        pass

@pytest.mark.asyncio
@patch('litellm.get_model_info', return_value={"provider": "openai"})
@patch('litellm.aembedding')
async def test_kb_immutable_fields(mock_embedding, mock_get_model_info, test_db, mock_auth, setup_test_models):
    """Test that immutable fields cannot be updated"""
    logger.info(f"test_kb_immutable_fields() start")
    
    # Set up mock embedding response
    mock_embedding.return_value = create_mock_embedding_response()
    
    try:
        # Create a KB
        kb_data = {
            "name": "Test Immutable KB",
            "chunker_type": "recursive",  # Use recursive instead of semantic (semantic is disabled)
            "chunk_size": 512,
            "chunk_overlap": 128,
            "embedding_model": "text-embedding-3-small"
        }
        create_response = client.post(
            f"/v0/orgs/{TEST_ORG_ID}/knowledge-bases",
            json=kb_data,
            headers=get_auth_headers()
        )
        assert create_response.status_code == 200
        kb_id = create_response.json()["kb_id"]
        
        # Try to update immutable fields (should be ignored or rejected)
        # Note: The current implementation allows these in the request but doesn't update them
        # This test verifies the behavior
        update_data = {
            "name": "Updated Name",
            "chunker_type": "token",  # Immutable - should be ignored
            "chunk_size": 256,  # Immutable - should be ignored
            "embedding_model": "text-embedding-3-large"  # Immutable - should be ignored
        }
        update_response = client.put(
            f"/v0/orgs/{TEST_ORG_ID}/knowledge-bases/{kb_id}",
            json=update_data,
            headers=get_auth_headers()
        )
        assert update_response.status_code == 200
        updated_kb = update_response.json()
        assert updated_kb["name"] == "Updated Name"  # Mutable field updated
        # Immutable fields should remain unchanged
        assert updated_kb["chunker_type"] == "recursive"  # Not changed
        assert updated_kb["chunk_size"] == 512  # Not changed
        assert updated_kb["embedding_model"] == "text-embedding-3-small"  # Not changed
        
        # Cleanup
        client.delete(
            f"/v0/orgs/{TEST_ORG_ID}/knowledge-bases/{kb_id}",
            headers=get_auth_headers()
        )
        
    finally:
        pass
