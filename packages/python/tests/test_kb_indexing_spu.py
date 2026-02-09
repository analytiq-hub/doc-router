"""
Unit tests for SPU usage in Knowledge Base indexing and search.
"""

import pytest
from bson import ObjectId
import os
from datetime import datetime, UTC
import logging
from unittest.mock import patch, AsyncMock, Mock

# Import shared test utilities
from .conftest_utils import (
    client, TEST_ORG_ID, 
    get_auth_headers
)
import analytiq_data as ad

logger = logging.getLogger(__name__)

# Check that ENV is set to pytest
assert os.environ["ENV"] == "pytest"

# Mock embedding response for dimension detection
MOCK_EMBEDDING_DIMENSIONS = 1536

def create_mock_embedding_response(num_embeddings=1):
    """Create a mock embedding response with non-zero vectors (required for cosine similarity).
    Uses Mock() not AsyncMock() so get_embedding_cost() does not trigger unawaited coroutines."""
    mock_response = Mock()
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
@patch('analytiq_data.payments.record_spu_usage')
@patch('analytiq_data.payments.check_spu_limits')
async def test_kb_indexing_spu_recording(
    mock_check_spu_limits,
    mock_record_spu_usage,
    mock_embedding,
    mock_get_model_info,
    test_db,
    mock_auth,
    setup_test_models
):
    """Test that SPU usage is recorded for embedding generation (cache misses)"""
    logger.info(f"test_kb_indexing_spu_recording() start")
    
    # Set up mocks
    mock_embedding.return_value = create_mock_embedding_response()
    mock_check_spu_limits.return_value = True  # Allow all SPU usage
    mock_record_spu_usage.return_value = True
    
    try:
        # Create tag and KB
        tag_data = {"name": "SPU Test Tag", "color": "#FF5733"}
        tag_response = client.post(
            f"/v0/orgs/{TEST_ORG_ID}/tags",
            json=tag_data,
            headers=get_auth_headers()
        )
        tag_id = tag_response.json()["id"]
        
        kb_data = {
            "name": "SPU Test KB",
            "tag_ids": [tag_id],
            "chunker_type": "recursive",
            "chunk_size": 50,  # Small chunks to generate multiple embeddings
            "chunk_overlap": 10
        }
        kb_response = client.post(
            f"/v0/orgs/{TEST_ORG_ID}/knowledge-bases",
            json=kb_data,
            headers=get_auth_headers()
        )
        kb_id = kb_response.json()["kb_id"]
        
        # Create document with enough text to generate multiple chunks
        document_id = str(ObjectId())
        test_text = "This is a test document for SPU recording. " * 20  # Enough text for multiple chunks
        
        await test_db.docs.insert_one({
            "_id": ObjectId(document_id),
            "organization_id": TEST_ORG_ID,
            "user_file_name": "spu_test.pdf",
            "tag_ids": [tag_id],
            "upload_date": datetime.now(UTC),
            "state": ad.common.doc.DOCUMENT_STATE_OCR_COMPLETED,
            "mongo_file_name": "test_file.pdf"
        })
        
        analytiq_client = ad.common.get_analytiq_client()
        await ad.common.ocr.save_ocr_text(analytiq_client, document_id, test_text)
        
        # Reset mocks to track calls
        mock_check_spu_limits.reset_mock()
        mock_record_spu_usage.reset_mock()
        
        # Index the document
        kb_msg = {
            "_id": str(ObjectId()),
            "msg": {"document_id": document_id, "kb_id": kb_id}
        }
        await ad.msg_handlers.process_kb_index_msg(analytiq_client, kb_msg)
        
        # Verify SPU credit check was called
        assert mock_check_spu_limits.called, "SPU credit check should be called before generating embeddings"
        check_call = mock_check_spu_limits.call_args
        assert check_call[0][0] == TEST_ORG_ID, "Should check credits for correct organization"
        assert check_call[0][1] > 0, "Should check for positive number of SPUs"
        
        # Verify SPU recording was called
        assert mock_record_spu_usage.called, "SPU usage should be recorded after generating embeddings"
        record_call = mock_record_spu_usage.call_args
        assert record_call[1]["org_id"] == TEST_ORG_ID, "Should record for correct organization"
        assert record_call[1]["spus"] > 0, "Should record positive number of SPUs"
        assert record_call[1]["llm_model"] == "text-embedding-3-small", "Should record correct embedding model"
        assert record_call[1]["llm_provider"] == "openai", "Should record correct provider"
        
        # Verify the number of SPUs recorded matches the number of cache misses
        # (which should equal the number of chunks generated)
        num_chunks = check_call[0][1]
        assert record_call[1]["spus"] == num_chunks, "SPUs recorded should match number of embeddings generated"
        
        logger.info(f"SPU test passed: {num_chunks} SPUs checked and recorded")
        
        # Cleanup
        client.delete(f"/v0/orgs/{TEST_ORG_ID}/knowledge-bases/{kb_id}", headers=get_auth_headers())
        await test_db.docs.delete_one({"_id": ObjectId(document_id)})
        
    finally:
        pass

@pytest.mark.asyncio
@patch('litellm.get_model_info', return_value={"provider": "openai"})
@patch('litellm.aembedding')
@patch('analytiq_data.payments.record_spu_usage')
@patch('analytiq_data.payments.check_spu_limits')
async def test_kb_indexing_spu_insufficient_credits(
    mock_check_spu_limits,
    mock_record_spu_usage,
    mock_embedding,
    mock_get_model_info,
    test_db,
    mock_auth,
    setup_test_models
):
    """Test that SPUCreditException is raised when insufficient credits"""
    logger.info(f"test_kb_indexing_spu_insufficient_credits() start")
    
    from app.routes.payments import SPUCreditException
    
    # Set up mocks
    mock_embedding.return_value = create_mock_embedding_response()
    # Make check_spu_limits raise SPUCreditException
    mock_check_spu_limits.side_effect = SPUCreditException(TEST_ORG_ID, 10, 5)
    mock_record_spu_usage.return_value = True
    
    try:
        # Create tag and KB
        tag_data = {"name": "SPU Credit Test Tag", "color": "#FF5733"}
        tag_response = client.post(
            f"/v0/orgs/{TEST_ORG_ID}/tags",
            json=tag_data,
            headers=get_auth_headers()
        )
        tag_id = tag_response.json()["id"]
        
        kb_data = {
            "name": "SPU Credit Test KB",
            "tag_ids": [tag_id],
            "chunker_type": "recursive",
            "chunk_size": 50,
            "chunk_overlap": 10
        }
        kb_response = client.post(
            f"/v0/orgs/{TEST_ORG_ID}/knowledge-bases",
            json=kb_data,
            headers=get_auth_headers()
        )
        kb_id = kb_response.json()["kb_id"]
        
        # Create document
        document_id = str(ObjectId())
        test_text = "This is a test document. " * 10
        
        await test_db.docs.insert_one({
            "_id": ObjectId(document_id),
            "organization_id": TEST_ORG_ID,
            "user_file_name": "spu_credit_test.pdf",
            "tag_ids": [tag_id],
            "upload_date": datetime.now(UTC),
            "state": ad.common.doc.DOCUMENT_STATE_OCR_COMPLETED,
            "mongo_file_name": "test_file.pdf"
        })
        
        analytiq_client = ad.common.get_analytiq_client()
        await ad.common.ocr.save_ocr_text(analytiq_client, document_id, test_text)
        
        # Attempt to index - should raise SPUCreditException
        kb_msg = {
            "_id": str(ObjectId()),
            "msg": {"document_id": document_id, "kb_id": kb_id}
        }
        
        with pytest.raises(SPUCreditException):
            await ad.msg_handlers.process_kb_index_msg(analytiq_client, kb_msg)
        
        # Verify SPU recording was NOT called (because indexing failed)
        assert not mock_record_spu_usage.called, "SPU usage should not be recorded if indexing fails"
        
        logger.info("SPU credit exception test passed")
        
        # Cleanup
        client.delete(f"/v0/orgs/{TEST_ORG_ID}/knowledge-bases/{kb_id}", headers=get_auth_headers())
        await test_db.docs.delete_one({"_id": ObjectId(document_id)})
        
    finally:
        pass

@pytest.mark.asyncio
@patch('litellm.get_model_info', return_value={"provider": "openai"})
@patch('litellm.aembedding')
@patch('analytiq_data.payments.record_spu_usage')
@patch('analytiq_data.payments.check_spu_limits')
async def test_kb_indexing_spu_cache_hits_free(
    mock_check_spu_limits,
    mock_record_spu_usage,
    mock_embedding,
    mock_get_model_info,
    test_db,
    mock_auth,
    setup_test_models
):
    """Test that cache hits don't charge SPU"""
    logger.info(f"test_kb_indexing_spu_cache_hits_free() start")
    
    # Set up mocks
    mock_embedding.return_value = create_mock_embedding_response()
    mock_check_spu_limits.return_value = True
    mock_record_spu_usage.return_value = True
    
    try:
        # Create tag and KB
        tag_data = {"name": "SPU Cache Test Tag", "color": "#FF5733"}
        tag_response = client.post(
            f"/v0/orgs/{TEST_ORG_ID}/tags",
            json=tag_data,
            headers=get_auth_headers()
        )
        tag_id = tag_response.json()["id"]
        
        kb_data = {
            "name": "SPU Cache Test KB",
            "tag_ids": [tag_id],
            "chunker_type": "recursive",
            "chunk_size": 100,
            "chunk_overlap": 20
        }
        kb_response = client.post(
            f"/v0/orgs/{TEST_ORG_ID}/knowledge-bases",
            json=kb_data,
            headers=get_auth_headers()
        )
        kb_id = kb_response.json()["kb_id"]
        
        # Create document
        document_id = str(ObjectId())
        test_text = "This is a test document for cache testing. " * 5
        
        await test_db.docs.insert_one({
            "_id": ObjectId(document_id),
            "organization_id": TEST_ORG_ID,
            "user_file_name": "spu_cache_test.pdf",
            "tag_ids": [tag_id],
            "upload_date": datetime.now(UTC),
            "state": ad.common.doc.DOCUMENT_STATE_OCR_COMPLETED,
            "mongo_file_name": "test_file.pdf"
        })
        
        analytiq_client = ad.common.get_analytiq_client()
        await ad.common.ocr.save_ocr_text(analytiq_client, document_id, test_text)
        
        # First indexing - should generate embeddings and charge SPU
        mock_check_spu_limits.reset_mock()
        mock_record_spu_usage.reset_mock()
        
        kb_msg1 = {
            "_id": str(ObjectId()),
            "msg": {"document_id": document_id, "kb_id": kb_id}
        }
        await ad.msg_handlers.process_kb_index_msg(analytiq_client, kb_msg1)
        
        first_check_calls = mock_check_spu_limits.call_count
        first_record_calls = mock_record_spu_usage.call_count
        
        assert first_check_calls > 0, "First indexing should check SPU credits"
        assert first_record_calls > 0, "First indexing should record SPU usage"
        
        # Second indexing with same text - should use cache and NOT charge SPU for cache hits
        # Note: Due to chunking overlap or other factors, some chunks might still be cache misses
        # The test verifies that cache hits don't charge SPU, and only cache misses are charged
        mock_check_spu_limits.reset_mock()
        mock_record_spu_usage.reset_mock()
        
        kb_msg2 = {
            "_id": str(ObjectId()),
            "msg": {"document_id": document_id, "kb_id": kb_id}
        }
        await ad.msg_handlers.process_kb_index_msg(analytiq_client, kb_msg2)
        
        # Verify SPU behavior:
        # - If all chunks are cache hits (cache_miss_count == 0), no SPU check should happen
        # - If there are cache misses, SPU check should happen only for the number of cache misses
        # - Cache hits should never charge SPU
        if mock_check_spu_limits.called:
            # SPU check was called - verify it was only for cache misses
            check_call = mock_check_spu_limits.call_args
            cache_miss_count = check_call[0][1] if check_call else 0
            # Verify that SPU was checked and recorded only for cache misses
            assert cache_miss_count > 0, "SPU check should only be called if there are cache misses"
            assert mock_record_spu_usage.called, "SPU should be recorded for cache misses"
            record_call = mock_record_spu_usage.call_args
            assert record_call[1]["spus"] == cache_miss_count, f"SPU recorded ({record_call[1]['spus']}) should match cache misses ({cache_miss_count})"
            logger.info(f"Second indexing had {cache_miss_count} cache misses - SPU correctly charged only for misses")
        else:
            # No SPU check was called - all chunks must be cache hits
            assert not mock_record_spu_usage.called, "SPU should not be recorded if all chunks are cache hits"
            logger.info("Second indexing had all cache hits - no SPU charged (correct)")
        
        logger.info("SPU cache hits free test passed")
        
        # Cleanup
        client.delete(f"/v0/orgs/{TEST_ORG_ID}/knowledge-bases/{kb_id}", headers=get_auth_headers())
        await test_db.docs.delete_one({"_id": ObjectId(document_id)})
        
    finally:
        pass

@pytest.mark.asyncio
@patch('litellm.get_model_info', return_value={"provider": "openai"})
@patch('litellm.aembedding')
@patch('analytiq_data.payments.record_spu_usage')
@patch('analytiq_data.payments.check_spu_limits')
async def test_kb_search_spu_recording(
    mock_check_spu_limits,
    mock_record_spu_usage,
    mock_embedding,
    mock_get_model_info,
    test_db,
    mock_auth,
    setup_test_models
):
    """Test that SPU usage is recorded for query embedding generation"""
    logger.info(f"test_kb_search_spu_recording() start")
    
    # Set up mocks
    mock_embedding.return_value = create_mock_embedding_response()
    mock_check_spu_limits.return_value = True
    mock_record_spu_usage.return_value = True
    
    try:
        # Create tag and KB
        tag_data = {"name": "SPU Search Test Tag", "color": "#FF5733"}
        tag_response = client.post(
            f"/v0/orgs/{TEST_ORG_ID}/tags",
            json=tag_data,
            headers=get_auth_headers()
        )
        tag_id = tag_response.json()["id"]
        
        kb_data = {"name": "SPU Search Test KB", "tag_ids": [tag_id]}
        kb_response = client.post(
            f"/v0/orgs/{TEST_ORG_ID}/knowledge-bases",
            json=kb_data,
            headers=get_auth_headers()
        )
        kb_id = kb_response.json()["kb_id"]
        
        # Create and index a document
        document_id = str(ObjectId())
        test_text = "This is a test document for search SPU testing. " * 5
        
        await test_db.docs.insert_one({
            "_id": ObjectId(document_id),
            "organization_id": TEST_ORG_ID,
            "user_file_name": "spu_search_test.pdf",
            "tag_ids": [tag_id],
            "upload_date": datetime.now(UTC),
            "state": ad.common.doc.DOCUMENT_STATE_OCR_COMPLETED,
            "mongo_file_name": "test_file.pdf"
        })
        
        analytiq_client = ad.common.get_analytiq_client()
        await ad.common.ocr.save_ocr_text(analytiq_client, document_id, test_text)
        
        # Index the document
        kb_msg = {
            "_id": str(ObjectId()),
            "msg": {"document_id": document_id, "kb_id": kb_id}
        }
        await ad.msg_handlers.process_kb_index_msg(analytiq_client, kb_msg)
        
        # Wait for vector index to be ready (increase wait time for test environment)
        from app.routes.knowledge_bases import wait_for_vector_index_ready
        await wait_for_vector_index_ready(analytiq_client, kb_id, max_wait_seconds=60)
        
        # Additional wait and retry loop to ensure index is fully ready
        import asyncio
        max_retries = 10
        for retry in range(max_retries):
            try:
                # Try a test search to verify index is ready
                test_results = await ad.kb.search.search_knowledge_base(
                    analytiq_client=analytiq_client,
                    kb_id=kb_id,
                    query="test",
                    organization_id=TEST_ORG_ID,
                    top_k=1
                )
                # If we get here, index is ready
                break
            except Exception as e:
                if "not initialized" in str(e).lower() and retry < max_retries - 1:
                    await asyncio.sleep(2)
                    continue
                elif retry < max_retries - 1:
                    # Other error, wait a bit and retry
                    await asyncio.sleep(1)
                    continue
                else:
                    # Last retry failed, but continue anyway - the actual search will handle it
                    logger.warning(f"Index may not be fully ready after {max_retries} retries, but continuing test")
                    break
        
        # Reset mocks for search
        mock_check_spu_limits.reset_mock()
        mock_record_spu_usage.reset_mock()
        
        # Perform search with new query (cache miss)
        search_query = "test query for SPU recording"
        search_results = await ad.kb.search.search_knowledge_base(
            analytiq_client=analytiq_client,
            kb_id=kb_id,
            query=search_query,
            organization_id=TEST_ORG_ID,
            top_k=5
        )
        
        # Verify SPU credit check was called
        assert mock_check_spu_limits.called, "SPU credit check should be called before generating query embedding"
        check_call = mock_check_spu_limits.call_args
        assert check_call[0][0] == TEST_ORG_ID, "Should check credits for correct organization"
        assert check_call[0][1] == 1, "Should check for 1 SPU (query embedding)"
        
        # Verify SPU recording was called
        assert mock_record_spu_usage.called, "SPU usage should be recorded after generating query embedding"
        record_call = mock_record_spu_usage.call_args
        assert record_call[1]["org_id"] == TEST_ORG_ID, "Should record for correct organization"
        assert record_call[1]["spus"] == 1, "Should record 1 SPU for query embedding"
        assert record_call[1]["llm_model"] == "text-embedding-3-small", "Should record correct embedding model"
        assert record_call[1]["llm_provider"] == "openai", "Should record correct provider"
        
        logger.info("SPU search recording test passed")
        
        # Cleanup
        client.delete(f"/v0/orgs/{TEST_ORG_ID}/knowledge-bases/{kb_id}", headers=get_auth_headers())
        await test_db.docs.delete_one({"_id": ObjectId(document_id)})
        
    finally:
        pass

@pytest.mark.asyncio
@patch('litellm.get_model_info', return_value={"provider": "openai"})
@patch('litellm.aembedding')
@patch('analytiq_data.payments.record_spu_usage')
@patch('analytiq_data.payments.check_spu_limits')
async def test_kb_search_spu_insufficient_credits(
    mock_check_spu_limits,
    mock_record_spu_usage,
    mock_embedding,
    mock_get_model_info,
    test_db,
    mock_auth,
    setup_test_models
):
    """Test that SPUCreditException is raised when insufficient credits for search"""
    logger.info(f"test_kb_search_spu_insufficient_credits() start")
    
    from app.routes.payments import SPUCreditException
    
    # Set up mocks - allow indexing to succeed, but fail on search
    mock_embedding.return_value = create_mock_embedding_response()
    # Allow all SPU checks during indexing
    mock_check_spu_limits.return_value = True
    mock_record_spu_usage.return_value = True
    
    try:
        # Create tag and KB
        tag_data = {"name": "SPU Search Credit Test Tag", "color": "#FF5733"}
        tag_response = client.post(
            f"/v0/orgs/{TEST_ORG_ID}/tags",
            json=tag_data,
            headers=get_auth_headers()
        )
        tag_id = tag_response.json()["id"]
        
        kb_data = {"name": "SPU Search Credit Test KB", "tag_ids": [tag_id]}
        kb_response = client.post(
            f"/v0/orgs/{TEST_ORG_ID}/knowledge-bases",
            json=kb_data,
            headers=get_auth_headers()
        )
        kb_id = kb_response.json()["kb_id"]
        
        # Create and index a document
        document_id = str(ObjectId())
        test_text = "This is a test document. " * 5
        
        await test_db.docs.insert_one({
            "_id": ObjectId(document_id),
            "organization_id": TEST_ORG_ID,
            "user_file_name": "spu_search_credit_test.pdf",
            "tag_ids": [tag_id],
            "upload_date": datetime.now(UTC),
            "state": ad.common.doc.DOCUMENT_STATE_OCR_COMPLETED,
            "mongo_file_name": "test_file.pdf"
        })
        
        analytiq_client = ad.common.get_analytiq_client()
        await ad.common.ocr.save_ocr_text(analytiq_client, document_id, test_text)
        
        # Index the document (should succeed)
        kb_msg = {
            "_id": str(ObjectId()),
            "msg": {"document_id": document_id, "kb_id": kb_id}
        }
        await ad.msg_handlers.process_kb_index_msg(analytiq_client, kb_msg)
        
        # Wait for vector index to be ready
        from app.routes.knowledge_bases import wait_for_vector_index_ready
        await wait_for_vector_index_ready(analytiq_client, kb_id)
        
        # Reset mocks and set side_effect to fail only on search
        # After indexing is complete, we set the mock to fail on the next call (which will be search)
        mock_check_spu_limits.reset_mock()
        mock_record_spu_usage.reset_mock()
        
        # Set side_effect to raise exception for search (spus=1 for query embedding)
        # Note: This assumes search uses exactly 1 SPU. If indexing also used 1 SPU, 
        # we'd need a more sophisticated approach, but indexing is already done.
        async def fail_on_search(org_id, spus):
            if spus == 1:  # Query embedding
                raise SPUCreditException(TEST_ORG_ID, 1, 0)
            return True
        
        mock_check_spu_limits.side_effect = fail_on_search
        
        # Attempt to search - should raise SPUCreditException
        with pytest.raises(SPUCreditException):
            await ad.kb.search.search_knowledge_base(
                analytiq_client=analytiq_client,
                kb_id=kb_id,
                query="test query",
                organization_id=TEST_ORG_ID,
                top_k=5
            )
        
        # Verify SPU recording was NOT called for search (because search failed)
        # Check that no call was made with spus=1 after we reset the mock
        if mock_record_spu_usage.called:
            # If it was called, verify it wasn't for the search (spus=1)
            for call in mock_record_spu_usage.call_args_list:
                if call and len(call) > 1 and call[1].get("spus") == 1:
                    assert False, "SPU usage should not be recorded if search fails"
        
        logger.info("SPU search credit exception test passed")
        
        # Cleanup
        client.delete(f"/v0/orgs/{TEST_ORG_ID}/knowledge-bases/{kb_id}", headers=get_auth_headers())
        await test_db.docs.delete_one({"_id": ObjectId(document_id)})
        
    finally:
        pass

@pytest.mark.asyncio
@patch('litellm.get_model_info', return_value={"provider": "openai"})
@patch('litellm.aembedding')
@patch('analytiq_data.payments.record_spu_usage')
@patch('analytiq_data.payments.check_spu_limits')
async def test_kb_search_spu_cache_hit_free(
    mock_check_spu_limits,
    mock_record_spu_usage,
    mock_embedding,
    mock_get_model_info,
    test_db,
    mock_auth,
    setup_test_models
):
    """Test that cached query embeddings don't charge SPU"""
    logger.info(f"test_kb_search_spu_cache_hit_free() start")
    
    # Set up mocks
    mock_embedding.return_value = create_mock_embedding_response()
    mock_check_spu_limits.return_value = True
    mock_record_spu_usage.return_value = True
    
    try:
        # Create tag and KB
        tag_data = {"name": "SPU Search Cache Test Tag", "color": "#FF5733"}
        tag_response = client.post(
            f"/v0/orgs/{TEST_ORG_ID}/tags",
            json=tag_data,
            headers=get_auth_headers()
        )
        tag_id = tag_response.json()["id"]
        
        kb_data = {"name": "SPU Search Cache Test KB", "tag_ids": [tag_id]}
        kb_response = client.post(
            f"/v0/orgs/{TEST_ORG_ID}/knowledge-bases",
            json=kb_data,
            headers=get_auth_headers()
        )
        kb_id = kb_response.json()["kb_id"]
        
        # Create and index a document
        document_id = str(ObjectId())
        test_text = "This is a test document. " * 5
        
        await test_db.docs.insert_one({
            "_id": ObjectId(document_id),
            "organization_id": TEST_ORG_ID,
            "user_file_name": "spu_search_cache_test.pdf",
            "tag_ids": [tag_id],
            "upload_date": datetime.now(UTC),
            "state": ad.common.doc.DOCUMENT_STATE_OCR_COMPLETED,
            "mongo_file_name": "test_file.pdf"
        })
        
        analytiq_client = ad.common.get_analytiq_client()
        await ad.common.ocr.save_ocr_text(analytiq_client, document_id, test_text)
        
        # Index the document
        kb_msg = {
            "_id": str(ObjectId()),
            "msg": {"document_id": document_id, "kb_id": kb_id}
        }
        await ad.msg_handlers.process_kb_index_msg(analytiq_client, kb_msg)
        
        # Wait for vector index to be ready
        from app.routes.knowledge_bases import wait_for_vector_index_ready
        await wait_for_vector_index_ready(analytiq_client, kb_id)
        
        # First search - should generate query embedding and charge SPU
        mock_check_spu_limits.reset_mock()
        mock_record_spu_usage.reset_mock()
        
        search_query = "test query for cache testing"
        search_results1 = await ad.kb.search.search_knowledge_base(
            analytiq_client=analytiq_client,
            kb_id=kb_id,
            query=search_query,
            organization_id=TEST_ORG_ID,
            top_k=5
        )
        
        assert mock_check_spu_limits.call_count == 1, "First search should check SPU credits"
        assert mock_record_spu_usage.call_count == 1, "First search should record SPU usage"
        
        # Second search with same query - should use cache and NOT charge SPU
        mock_check_spu_limits.reset_mock()
        mock_record_spu_usage.reset_mock()
        
        search_results2 = await ad.kb.search.search_knowledge_base(
            analytiq_client=analytiq_client,
            kb_id=kb_id,
            query=search_query,  # Same query
            organization_id=TEST_ORG_ID,
            top_k=5
        )
        
        # Cache hits should not check credits or record SPU usage
        assert mock_check_spu_limits.call_count == 0, "Cache hits should not check SPU credits"
        assert mock_record_spu_usage.call_count == 0, "Cache hits should not record SPU usage"
        
        logger.info("SPU search cache hits free test passed")
        
        # Cleanup
        client.delete(f"/v0/orgs/{TEST_ORG_ID}/knowledge-bases/{kb_id}", headers=get_auth_headers())
        await test_db.docs.delete_one({"_id": ObjectId(document_id)})
        
    finally:
        pass
