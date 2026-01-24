"""
Comprehensive unit tests for KB indexing covering all edge cases and combinations.

Tests cover:
- Document deletion scenarios (with/without KB membership)
- Document tag update scenarios (add/remove/replace)
- KB tag update scenarios (add/remove/replace)
- Multiple KB scenarios with overlapping tags
- Edge cases (no tags, concurrent updates, etc.)
"""

import pytest
from bson import ObjectId
import os
from datetime import datetime, UTC
import logging
from unittest.mock import patch, AsyncMock

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
    """Create a mock embedding response with non-zero vectors (required for cosine similarity)"""
    mock_response = AsyncMock()
    # Generate non-zero embeddings (simple pattern that's not all zeros)
    embeddings = []
    for i in range(num_embeddings):
        # Create a simple non-zero vector: [0.1, 0.2, 0.3, ...] pattern
        embedding = [0.001 * (j % 100 + 1) for j in range(MOCK_EMBEDDING_DIMENSIONS)]
        embeddings.append({"embedding": embedding})
    mock_response.data = embeddings
    return mock_response


# Helper functions for test setup
async def create_tag(name: str, color: str = "#FF5733") -> str:
    """Create a tag and return its ID"""
    tag_data = {"name": name, "color": color}
    tag_response = client.post(
        f"/v0/orgs/{TEST_ORG_ID}/tags",
        json=tag_data,
        headers=get_auth_headers()
    )
    assert tag_response.status_code == 200
    return tag_response.json()["id"]

async def create_kb(name: str, tag_ids: list, **kwargs) -> str:
    """Create a KB and return its ID"""
    kb_data = {
        "name": name,
        "tag_ids": tag_ids,
        "chunker_type": "recursive",
        "chunk_size": 100,
        "chunk_overlap": 20,
        **kwargs
    }
    kb_response = client.post(
        f"/v0/orgs/{TEST_ORG_ID}/knowledge-bases",
        json=kb_data,
        headers=get_auth_headers()
    )
    assert kb_response.status_code == 200
    return kb_response.json()["kb_id"]

async def create_document(test_db, tag_ids: list, test_text: str = None) -> str:
    """Create a document with tags and OCR text, return document ID"""
    if test_text is None:
        test_text = "This is a test document for knowledge base indexing. " * 10
    
    document_id = str(ObjectId())
    await test_db.docs.insert_one({
        "_id": ObjectId(document_id),
        "organization_id": TEST_ORG_ID,
        "user_file_name": "test_doc.pdf",
        "tag_ids": tag_ids,
        "upload_date": datetime.now(UTC),
        "state": ad.common.doc.DOCUMENT_STATE_OCR_COMPLETED,
        "mongo_file_name": "test_file.pdf"
    })
    
    analytiq_client = ad.common.get_analytiq_client()
    await ad.common.ocr.save_ocr_text(analytiq_client, document_id, test_text)
    
    return document_id

async def index_document(document_id: str, kb_id: str = None, test_db=None):
    """Index a document into KB(s)"""
    analytiq_client = ad.common.get_analytiq_client()
    kb_msg = {
        "_id": str(ObjectId()),
        "msg": {"document_id": document_id, "kb_id": kb_id} if kb_id else {"document_id": document_id}
    }
    await ad.msg_handlers.process_kb_index_msg(analytiq_client, kb_msg)

async def verify_document_in_kb(test_db, document_id: str, kb_id: str, should_be_indexed: bool):
    """Verify document indexing state in KB"""
    index_entry = await test_db.document_index.find_one({
        "kb_id": kb_id,
        "document_id": document_id
    })
    
    if should_be_indexed:
        assert index_entry is not None, f"Document {document_id} should be indexed in KB {kb_id}"
        # Verify vectors exist
        vectors_collection = test_db[f"kb_vectors_{kb_id}"]
        vector_count = await vectors_collection.count_documents({"document_id": document_id})
        assert vector_count > 0, f"Document {document_id} should have vectors in KB {kb_id}"
    else:
        assert index_entry is None, f"Document {document_id} should NOT be indexed in KB {kb_id}"
        # Verify vectors don't exist
        vectors_collection = test_db[f"kb_vectors_{kb_id}"]
        vector_count = await vectors_collection.count_documents({"document_id": document_id})
        assert vector_count == 0, f"Document {document_id} should NOT have vectors in KB {kb_id}"

async def process_pending_kb_index_messages(test_db, document_id: str = None):
    """Process pending KB index messages from the queue"""
    analytiq_client = ad.common.get_analytiq_client()
    queue_collection = test_db["queues.kb_index"]
    query = {"status": "pending"}
    if document_id:
        query["msg.document_id"] = document_id
    
    queue_messages = await queue_collection.find(query).to_list(length=10)
    for msg in queue_messages:
        kb_msg = {
            "_id": str(msg["_id"]),
            "msg": msg.get("msg", {})
        }
        await ad.msg_handlers.process_kb_index_msg(analytiq_client, kb_msg)


# ============================================================================
# CATEGORY 1: Document Deletion Scenarios
# ============================================================================

@pytest.mark.asyncio
@patch('litellm.get_model_info', return_value={"provider": "openai"})
@patch('litellm.aembedding')
async def test_1_1_delete_document_not_indexed(mock_embedding, mock_get_model_info, test_db, mock_auth, setup_test_models):
    """Test 1.1: Delete document not indexed by KB tag"""
    mock_embedding.return_value = create_mock_embedding_response()
    
    try:
        # Setup: Document has tagA, KB1 has tagB (no overlap)
        tagA_id = await create_tag("TagA")
        tagB_id = await create_tag("TagB")
        kb1_id = await create_kb("KB1", [tagB_id])
        
        document_id = await create_document(test_db, [tagA_id])
        
        # Verify document is NOT indexed in KB1
        await verify_document_in_kb(test_db, document_id, kb1_id, should_be_indexed=False)
        
        # Delete the document
        await ad.common.delete_doc(ad.common.get_analytiq_client(), document_id, TEST_ORG_ID)
        
        # Verify document is deleted and KB1 is unaffected
        doc = await test_db.docs.find_one({"_id": ObjectId(document_id)})
        assert doc is None, "Document should be deleted"
        
        # Verify KB1 stats are unchanged (0 documents)
        kb1 = await test_db.knowledge_bases.find_one({"_id": ObjectId(kb1_id)})
        assert kb1["document_count"] == 0, "KB1 should have 0 documents"
        
    finally:
        # Cleanup
        await test_db.docs.delete_many({"organization_id": TEST_ORG_ID})
        await test_db.knowledge_bases.delete_many({"organization_id": TEST_ORG_ID})
        await test_db.tags.delete_many({"organization_id": TEST_ORG_ID})

@pytest.mark.asyncio
@patch('litellm.get_model_info', return_value={"provider": "openai"})
@patch('litellm.aembedding')
async def test_1_2_delete_document_indexed_single_kb(mock_embedding, mock_get_model_info, test_db, mock_auth, setup_test_models):
    """Test 1.2: Delete document indexed by KB tag (single KB)"""
    mock_embedding.return_value = create_mock_embedding_response()
    
    try:
        # Setup: Document has tagA, KB1 has tagA
        tagA_id = await create_tag("TagA")
        kb1_id = await create_kb("KB1", [tagA_id])
        document_id = await create_document(test_db, [tagA_id])
        
        # Index the document
        await index_document(document_id, kb1_id)
        
        # Verify document is indexed
        await verify_document_in_kb(test_db, document_id, kb1_id, should_be_indexed=True)
        
        # Delete the document
        await ad.common.delete_doc(ad.common.get_analytiq_client(), document_id, TEST_ORG_ID)
        
        # Verify document is removed from KB1
        await verify_document_in_kb(test_db, document_id, kb1_id, should_be_indexed=False)
        
        # Verify KB1 stats are updated
        kb1 = await test_db.knowledge_bases.find_one({"_id": ObjectId(kb1_id)})
        assert kb1["document_count"] == 0, "KB1 should have 0 documents after deletion"
        
    finally:
        await test_db.docs.delete_many({"organization_id": TEST_ORG_ID})
        await test_db.knowledge_bases.delete_many({"organization_id": TEST_ORG_ID})
        await test_db.tags.delete_many({"organization_id": TEST_ORG_ID})

@pytest.mark.asyncio
@patch('litellm.get_model_info', return_value={"provider": "openai"})
@patch('litellm.aembedding')
async def test_1_3_delete_document_indexed_multiple_kbs(mock_embedding, mock_get_model_info, test_db, mock_auth, setup_test_models):
    """Test 1.3: Delete document indexed by multiple KBs"""
    mock_embedding.return_value = create_mock_embedding_response()
    
    try:
        # Setup: Document has [tagA, tagB], KB1 has [tagA, tagC], KB2 has [tagB, tagD]
        tagA_id = await create_tag("TagA")
        tagB_id = await create_tag("TagB")
        tagC_id = await create_tag("TagC")
        tagD_id = await create_tag("TagD")
        
        kb1_id = await create_kb("KB1", [tagA_id, tagC_id])
        kb2_id = await create_kb("KB2", [tagB_id, tagD_id])
        
        document_id = await create_document(test_db, [tagA_id, tagB_id])
        
        # Index the document (should go into both KBs)
        await index_document(document_id, None, test_db)
        await process_pending_kb_index_messages(test_db, document_id)
        
        # Verify document is indexed in both KBs
        await verify_document_in_kb(test_db, document_id, kb1_id, should_be_indexed=True)
        await verify_document_in_kb(test_db, document_id, kb2_id, should_be_indexed=True)
        
        # Delete the document
        await ad.common.delete_doc(ad.common.get_analytiq_client(), document_id, TEST_ORG_ID)
        
        # Verify document is removed from both KBs
        await verify_document_in_kb(test_db, document_id, kb1_id, should_be_indexed=False)
        await verify_document_in_kb(test_db, document_id, kb2_id, should_be_indexed=False)
        
        # Verify both KBs have 0 documents
        kb1 = await test_db.knowledge_bases.find_one({"_id": ObjectId(kb1_id)})
        kb2 = await test_db.knowledge_bases.find_one({"_id": ObjectId(kb2_id)})
        assert kb1["document_count"] == 0, "KB1 should have 0 documents"
        assert kb2["document_count"] == 0, "KB2 should have 0 documents"
        
    finally:
        await test_db.docs.delete_many({"organization_id": TEST_ORG_ID})
        await test_db.knowledge_bases.delete_many({"organization_id": TEST_ORG_ID})
        await test_db.tags.delete_many({"organization_id": TEST_ORG_ID})


# ============================================================================
# CATEGORY 2: Document Tag Update Scenarios
# ============================================================================

@pytest.mark.asyncio
@patch('litellm.get_model_info', return_value={"provider": "openai"})
@patch('litellm.aembedding')
async def test_2_1_remove_tag_matching_single_kb(mock_embedding, mock_get_model_info, test_db, mock_auth, setup_test_models):
    """Test 2.1: Remove tag that matches KB (single KB)"""
    mock_embedding.return_value = create_mock_embedding_response()
    
    try:
        # Setup: Document has [tagA, tagB], KB1 has [tagA, tagC]
        tagA_id = await create_tag("TagA")
        tagB_id = await create_tag("TagB")
        tagC_id = await create_tag("TagC")
        
        kb1_id = await create_kb("KB1", [tagA_id, tagC_id])
        document_id = await create_document(test_db, [tagA_id, tagB_id])
        
        # Index the document
        await index_document(document_id, None, test_db)
        await process_pending_kb_index_messages(test_db, document_id)
        
        # Verify document is indexed
        await verify_document_in_kb(test_db, document_id, kb1_id, should_be_indexed=True)
        
        # Remove tagA from document
        update_response = client.put(
            f"/v0/orgs/{TEST_ORG_ID}/documents/{document_id}",
            json={"tag_ids": [tagB_id]},
            headers=get_auth_headers()
        )
        assert update_response.status_code == 200
        
        # Process the queued KB indexing message
        await process_pending_kb_index_messages(test_db, document_id)
        
        # Verify document is removed from KB1
        await verify_document_in_kb(test_db, document_id, kb1_id, should_be_indexed=False)
        
        # Verify KB1 stats
        kb1 = await test_db.knowledge_bases.find_one({"_id": ObjectId(kb1_id)})
        assert kb1["document_count"] == 0, "KB1 should have 0 documents"
        
    finally:
        await test_db.docs.delete_many({"organization_id": TEST_ORG_ID})
        await test_db.knowledge_bases.delete_many({"organization_id": TEST_ORG_ID})
        await test_db.tags.delete_many({"organization_id": TEST_ORG_ID})

@pytest.mark.asyncio
@patch('litellm.get_model_info', return_value={"provider": "openai"})
@patch('litellm.aembedding')
async def test_2_2_remove_tag_matching_multiple_kbs(mock_embedding, mock_get_model_info, test_db, mock_auth, setup_test_models):
    """Test 2.2: Remove tag that matches KB (multiple KBs) - USER TEST 5"""
    mock_embedding.return_value = create_mock_embedding_response()
    
    try:
        # Setup: Document has [tagA, tagB], KB1 has [tagA, tagC], KB2 has [tagB, tagD]
        tagA_id = await create_tag("TagA")
        tagB_id = await create_tag("TagB")
        tagC_id = await create_tag("TagC")
        tagD_id = await create_tag("TagD")
        
        kb1_id = await create_kb("KB1", [tagA_id, tagC_id])
        kb2_id = await create_kb("KB2", [tagB_id, tagD_id])
        document_id = await create_document(test_db, [tagA_id, tagB_id])
        
        # Index the document
        await index_document(document_id, None, test_db)
        await process_pending_kb_index_messages(test_db, document_id)
        
        # Verify document is indexed in both KBs
        await verify_document_in_kb(test_db, document_id, kb1_id, should_be_indexed=True)
        await verify_document_in_kb(test_db, document_id, kb2_id, should_be_indexed=True)
        
        # Remove tagA from document
        update_response = client.put(
            f"/v0/orgs/{TEST_ORG_ID}/documents/{document_id}",
            json={"tag_ids": [tagB_id]},
            headers=get_auth_headers()
        )
        assert update_response.status_code == 200
        
        # Process the queued KB indexing message
        await process_pending_kb_index_messages(test_db, document_id)
        
        # Verify document is removed from KB1, remains in KB2
        await verify_document_in_kb(test_db, document_id, kb1_id, should_be_indexed=False)
        await verify_document_in_kb(test_db, document_id, kb2_id, should_be_indexed=True)
        
        # Verify KB stats
        kb1 = await test_db.knowledge_bases.find_one({"_id": ObjectId(kb1_id)})
        kb2 = await test_db.knowledge_bases.find_one({"_id": ObjectId(kb2_id)})
        assert kb1["document_count"] == 0, "KB1 should have 0 documents"
        assert kb2["document_count"] == 1, "KB2 should have 1 document"
        
    finally:
        await test_db.docs.delete_many({"organization_id": TEST_ORG_ID})
        await test_db.knowledge_bases.delete_many({"organization_id": TEST_ORG_ID})
        await test_db.tags.delete_many({"organization_id": TEST_ORG_ID})

@pytest.mark.asyncio
@patch('litellm.get_model_info', return_value={"provider": "openai"})
@patch('litellm.aembedding')
async def test_2_3_add_tag_matching_new_kb(mock_embedding, mock_get_model_info, test_db, mock_auth, setup_test_models):
    """Test 2.3: Add tag that matches new KB - USER TEST 3"""
    mock_embedding.return_value = create_mock_embedding_response()
    
    try:
        # Setup: Document has [tagA], KB1 has [tagA, tagC], KB2 has [tagB, tagD]
        tagA_id = await create_tag("TagA")
        tagB_id = await create_tag("TagB")
        tagC_id = await create_tag("TagC")
        tagD_id = await create_tag("TagD")
        
        kb1_id = await create_kb("KB1", [tagA_id, tagC_id])
        kb2_id = await create_kb("KB2", [tagB_id, tagD_id])
        document_id = await create_document(test_db, [tagA_id])
        
        # Index the document (should go into KB1 only)
        await index_document(document_id, None, test_db)
        await process_pending_kb_index_messages(test_db, document_id)
        
        # Verify document is indexed in KB1 only
        await verify_document_in_kb(test_db, document_id, kb1_id, should_be_indexed=True)
        await verify_document_in_kb(test_db, document_id, kb2_id, should_be_indexed=False)
        
        # Add tagB to document
        update_response = client.put(
            f"/v0/orgs/{TEST_ORG_ID}/documents/{document_id}",
            json={"tag_ids": [tagA_id, tagB_id]},
            headers=get_auth_headers()
        )
        assert update_response.status_code == 200
        
        # Process the queued KB indexing message
        await process_pending_kb_index_messages(test_db, document_id)
        
        # Verify document is in both KBs now
        await verify_document_in_kb(test_db, document_id, kb1_id, should_be_indexed=True)
        await verify_document_in_kb(test_db, document_id, kb2_id, should_be_indexed=True)
        
        # Verify KB stats
        kb1 = await test_db.knowledge_bases.find_one({"_id": ObjectId(kb1_id)})
        kb2 = await test_db.knowledge_bases.find_one({"_id": ObjectId(kb2_id)})
        assert kb1["document_count"] == 1, "KB1 should have 1 document"
        assert kb2["document_count"] == 1, "KB2 should have 1 document"
        
    finally:
        await test_db.docs.delete_many({"organization_id": TEST_ORG_ID})
        await test_db.knowledge_bases.delete_many({"organization_id": TEST_ORG_ID})
        await test_db.tags.delete_many({"organization_id": TEST_ORG_ID})

@pytest.mark.asyncio
@patch('litellm.get_model_info', return_value={"provider": "openai"})
@patch('litellm.aembedding')
async def test_2_4_replace_tags(mock_embedding, mock_get_model_info, test_db, mock_auth, setup_test_models):
    """Test 2.4: Replace tags (remove matching, add non-matching)"""
    mock_embedding.return_value = create_mock_embedding_response()
    
    try:
        # Setup: Document has [tagA], KB1 has [tagA, tagC], KB2 has [tagB, tagD]
        tagA_id = await create_tag("TagA")
        tagB_id = await create_tag("TagB")
        tagC_id = await create_tag("TagC")
        tagD_id = await create_tag("TagD")
        
        kb1_id = await create_kb("KB1", [tagA_id, tagC_id])
        kb2_id = await create_kb("KB2", [tagB_id, tagD_id])
        document_id = await create_document(test_db, [tagA_id])
        
        # Index the document
        await index_document(document_id, None, test_db)
        await process_pending_kb_index_messages(test_db, document_id)
        
        # Verify document is indexed in KB1 only
        await verify_document_in_kb(test_db, document_id, kb1_id, should_be_indexed=True)
        await verify_document_in_kb(test_db, document_id, kb2_id, should_be_indexed=False)
        
        # Replace tags: [tagA] -> [tagB]
        update_response = client.put(
            f"/v0/orgs/{TEST_ORG_ID}/documents/{document_id}",
            json={"tag_ids": [tagB_id]},
            headers=get_auth_headers()
        )
        assert update_response.status_code == 200
        
        # Process the queued KB indexing message
        await process_pending_kb_index_messages(test_db, document_id)
        
        # Verify document is removed from KB1, added to KB2
        await verify_document_in_kb(test_db, document_id, kb1_id, should_be_indexed=False)
        await verify_document_in_kb(test_db, document_id, kb2_id, should_be_indexed=True)
        
        # Verify KB stats
        kb1 = await test_db.knowledge_bases.find_one({"_id": ObjectId(kb1_id)})
        kb2 = await test_db.knowledge_bases.find_one({"_id": ObjectId(kb2_id)})
        assert kb1["document_count"] == 0, "KB1 should have 0 documents"
        assert kb2["document_count"] == 1, "KB2 should have 1 document"
        
    finally:
        await test_db.docs.delete_many({"organization_id": TEST_ORG_ID})
        await test_db.knowledge_bases.delete_many({"organization_id": TEST_ORG_ID})
        await test_db.tags.delete_many({"organization_id": TEST_ORG_ID})

@pytest.mark.asyncio
@patch('litellm.get_model_info', return_value={"provider": "openai"})
@patch('litellm.aembedding')
async def test_2_5_remove_all_tags(mock_embedding, mock_get_model_info, test_db, mock_auth, setup_test_models):
    """Test 2.5: Remove all tags from document"""
    mock_embedding.return_value = create_mock_embedding_response()
    
    try:
        # Setup: Document has [tagA, tagB], KB1 has [tagA, tagC], KB2 has [tagB, tagD]
        tagA_id = await create_tag("TagA")
        tagB_id = await create_tag("TagB")
        tagC_id = await create_tag("TagC")
        tagD_id = await create_tag("TagD")
        
        kb1_id = await create_kb("KB1", [tagA_id, tagC_id])
        kb2_id = await create_kb("KB2", [tagB_id, tagD_id])
        document_id = await create_document(test_db, [tagA_id, tagB_id])
        
        # Index the document
        await index_document(document_id, None, test_db)
        await process_pending_kb_index_messages(test_db, document_id)
        
        # Verify document is indexed in both KBs
        await verify_document_in_kb(test_db, document_id, kb1_id, should_be_indexed=True)
        await verify_document_in_kb(test_db, document_id, kb2_id, should_be_indexed=True)
        
        # Remove all tags
        update_response = client.put(
            f"/v0/orgs/{TEST_ORG_ID}/documents/{document_id}",
            json={"tag_ids": []},
            headers=get_auth_headers()
        )
        assert update_response.status_code == 200
        
        # Process the queued KB indexing message
        await process_pending_kb_index_messages(test_db, document_id)
        
        # Verify document is removed from both KBs
        await verify_document_in_kb(test_db, document_id, kb1_id, should_be_indexed=False)
        await verify_document_in_kb(test_db, document_id, kb2_id, should_be_indexed=False)
        
        # Verify KB stats
        kb1 = await test_db.knowledge_bases.find_one({"_id": ObjectId(kb1_id)})
        kb2 = await test_db.knowledge_bases.find_one({"_id": ObjectId(kb2_id)})
        assert kb1["document_count"] == 0, "KB1 should have 0 documents"
        assert kb2["document_count"] == 0, "KB2 should have 0 documents"
        
    finally:
        await test_db.docs.delete_many({"organization_id": TEST_ORG_ID})
        await test_db.knowledge_bases.delete_many({"organization_id": TEST_ORG_ID})
        await test_db.tags.delete_many({"organization_id": TEST_ORG_ID})


# ============================================================================
# CATEGORY 3: KB Tag Update Scenarios
# ============================================================================

@pytest.mark.asyncio
@patch('litellm.get_model_info', return_value={"provider": "openai"})
@patch('litellm.aembedding')
async def test_3_1_remove_kb_tag_matching_document(mock_embedding, mock_get_model_info, test_db, mock_auth, setup_test_models):
    """Test 3.1: Remove tag from KB that matches document (single document)"""
    mock_embedding.return_value = create_mock_embedding_response()
    
    try:
        # Setup: Document has [tagA, tagB], KB1 has [tagA, tagC]
        tagA_id = await create_tag("TagA")
        tagB_id = await create_tag("TagB")
        tagC_id = await create_tag("TagC")
        
        kb1_id = await create_kb("KB1", [tagA_id, tagC_id])
        document_id = await create_document(test_db, [tagA_id, tagB_id])
        
        # Index the document
        await index_document(document_id, None, test_db)
        await process_pending_kb_index_messages(test_db, document_id)
        
        # Verify document is indexed
        await verify_document_in_kb(test_db, document_id, kb1_id, should_be_indexed=True)
        
        # Remove tagA from KB1
        update_response = client.put(
            f"/v0/orgs/{TEST_ORG_ID}/knowledge-bases/{kb1_id}",
            json={"tag_ids": [tagC_id]},
            headers=get_auth_headers()
        )
        assert update_response.status_code == 200
        
        # Run reconciliation to remove stale documents
        await ad.kb.reconciliation.reconcile_knowledge_base(
            ad.common.get_analytiq_client(), kb1_id, TEST_ORG_ID, dry_run=False
        )
        await process_pending_kb_index_messages(test_db)
        
        # Verify document is removed from KB1
        await verify_document_in_kb(test_db, document_id, kb1_id, should_be_indexed=False)
        
        # Verify KB1 stats
        kb1 = await test_db.knowledge_bases.find_one({"_id": ObjectId(kb1_id)})
        assert kb1["document_count"] == 0, "KB1 should have 0 documents"
        
    finally:
        await test_db.docs.delete_many({"organization_id": TEST_ORG_ID})
        await test_db.knowledge_bases.delete_many({"organization_id": TEST_ORG_ID})
        await test_db.tags.delete_many({"organization_id": TEST_ORG_ID})

@pytest.mark.asyncio
@patch('litellm.get_model_info', return_value={"provider": "openai"})
@patch('litellm.aembedding')
async def test_3_2_remove_kb_tag_multiple_documents(mock_embedding, mock_get_model_info, test_db, mock_auth, setup_test_models):
    """Test 3.2: Remove tag from KB that matches document (multiple documents) - USER TEST 4"""
    mock_embedding.return_value = create_mock_embedding_response()
    
    try:
        # Setup: Document has [tagA, tagB], KB1 has [tagA, tagC], KB2 has [tagB, tagD]
        tagA_id = await create_tag("TagA")
        tagB_id = await create_tag("TagB")
        tagC_id = await create_tag("TagC")
        tagD_id = await create_tag("TagD")
        
        kb1_id = await create_kb("KB1", [tagA_id, tagC_id])
        kb2_id = await create_kb("KB2", [tagB_id, tagD_id])
        document_id = await create_document(test_db, [tagA_id, tagB_id])
        
        # Index the document
        await index_document(document_id, None, test_db)
        await process_pending_kb_index_messages(test_db, document_id)
        
        # Verify document is indexed in both KBs
        await verify_document_in_kb(test_db, document_id, kb1_id, should_be_indexed=True)
        await verify_document_in_kb(test_db, document_id, kb2_id, should_be_indexed=True)
        
        # Remove tagA from KB1
        update_response = client.put(
            f"/v0/orgs/{TEST_ORG_ID}/knowledge-bases/{kb1_id}",
            json={"tag_ids": [tagC_id]},
            headers=get_auth_headers()
        )
        assert update_response.status_code == 200
        
        # Run reconciliation to remove stale documents
        await ad.kb.reconciliation.reconcile_knowledge_base(
            ad.common.get_analytiq_client(), kb1_id, TEST_ORG_ID, dry_run=False
        )
        await process_pending_kb_index_messages(test_db)
        
        # Verify document is removed from KB1, remains in KB2
        await verify_document_in_kb(test_db, document_id, kb1_id, should_be_indexed=False)
        await verify_document_in_kb(test_db, document_id, kb2_id, should_be_indexed=True)
        
        # Verify KB stats
        kb1 = await test_db.knowledge_bases.find_one({"_id": ObjectId(kb1_id)})
        kb2 = await test_db.knowledge_bases.find_one({"_id": ObjectId(kb2_id)})
        assert kb1["document_count"] == 0, "KB1 should have 0 documents"
        assert kb2["document_count"] == 1, "KB2 should have 1 document"
        
    finally:
        await test_db.docs.delete_many({"organization_id": TEST_ORG_ID})
        await test_db.knowledge_bases.delete_many({"organization_id": TEST_ORG_ID})
        await test_db.tags.delete_many({"organization_id": TEST_ORG_ID})

@pytest.mark.asyncio
@patch('litellm.get_model_info', return_value={"provider": "openai"})
@patch('litellm.aembedding')
async def test_3_3_remove_kb_tag_document_has_other_matching_tags(mock_embedding, mock_get_model_info, test_db, mock_auth, setup_test_models):
    """Test 3.3: Remove tag from KB (document has other matching tags)"""
    mock_embedding.return_value = create_mock_embedding_response()
    
    try:
        # Setup: Document has [tagA, tagB], KB1 has [tagA, tagB, tagC]
        tagA_id = await create_tag("TagA")
        tagB_id = await create_tag("TagB")
        tagC_id = await create_tag("TagC")
        
        kb1_id = await create_kb("KB1", [tagA_id, tagB_id, tagC_id])
        document_id = await create_document(test_db, [tagA_id, tagB_id])
        
        # Index the document
        await index_document(document_id, None, test_db)
        await process_pending_kb_index_messages(test_db, document_id)
        
        # Verify document is indexed
        await verify_document_in_kb(test_db, document_id, kb1_id, should_be_indexed=True)
        
        # Remove tagA from KB1 (KB1 now has [tagB, tagC])
        update_response = client.put(
            f"/v0/orgs/{TEST_ORG_ID}/knowledge-bases/{kb1_id}",
            json={"tag_ids": [tagB_id, tagC_id]},
            headers=get_auth_headers()
        )
        assert update_response.status_code == 200
        
        # Run reconciliation
        await ad.kb.reconciliation.reconcile_knowledge_base(
            ad.common.get_analytiq_client(), kb1_id, TEST_ORG_ID, dry_run=False
        )
        await process_pending_kb_index_messages(test_db)
        
        # Verify document remains in KB1 (still matches via tagB)
        await verify_document_in_kb(test_db, document_id, kb1_id, should_be_indexed=True)
        
        # Verify KB1 stats
        kb1 = await test_db.knowledge_bases.find_one({"_id": ObjectId(kb1_id)})
        assert kb1["document_count"] == 1, "KB1 should still have 1 document"
        
    finally:
        await test_db.docs.delete_many({"organization_id": TEST_ORG_ID})
        await test_db.knowledge_bases.delete_many({"organization_id": TEST_ORG_ID})
        await test_db.tags.delete_many({"organization_id": TEST_ORG_ID})


# ============================================================================
# USER-REQUESTED SPECIFIC TEST SCENARIOS
# ============================================================================

@pytest.mark.asyncio
@patch('litellm.get_model_info', return_value={"provider": "openai"})
@patch('litellm.aembedding')
async def test_user_2_document_indexed_with_extra_tag_delete(mock_embedding, mock_get_model_info, test_db, mock_auth, setup_test_models):
    """USER TEST 2: Document indexed by KB tag and another tag, KB has 1st tag and 3rd tag, delete it"""
    mock_embedding.return_value = create_mock_embedding_response()
    
    try:
        # Setup: Document has [tagA, tagB], KB1 has [tagA, tagC]
        tagA_id = await create_tag("TagA")
        tagB_id = await create_tag("TagB")
        tagC_id = await create_tag("TagC")
        
        kb1_id = await create_kb("KB1", [tagA_id, tagC_id])
        document_id = await create_document(test_db, [tagA_id, tagB_id])
        
        # Index the document
        await index_document(document_id, None, test_db)
        await process_pending_kb_index_messages(test_db, document_id)
        
        # Verify document is indexed in KB1 (via tagA)
        await verify_document_in_kb(test_db, document_id, kb1_id, should_be_indexed=True)
        
        # Delete the document
        await ad.common.delete_doc(ad.common.get_analytiq_client(), document_id, TEST_ORG_ID)
        
        # Verify document is removed from KB1
        await verify_document_in_kb(test_db, document_id, kb1_id, should_be_indexed=False)
        
        # Verify KB1 stats
        kb1 = await test_db.knowledge_bases.find_one({"_id": ObjectId(kb1_id)})
        assert kb1["document_count"] == 0, "KB1 should have 0 documents"
        
    finally:
        await test_db.docs.delete_many({"organization_id": TEST_ORG_ID})
        await test_db.knowledge_bases.delete_many({"organization_id": TEST_ORG_ID})
        await test_db.tags.delete_many({"organization_id": TEST_ORG_ID})

# Note: USER TEST 1 is covered by test_1_1_delete_document_not_indexed
# Note: USER TEST 3 is covered by test_2_3_add_tag_matching_new_kb
# Note: USER TEST 4 is covered by test_3_2_remove_kb_tag_multiple_documents
# Note: USER TEST 5 is covered by test_2_2_remove_tag_matching_multiple_kbs


# ============================================================================
# CATEGORY 4: KB Created After Document
# ============================================================================

@pytest.mark.asyncio
@patch('litellm.get_model_info', return_value={"provider": "openai"})
@patch('litellm.aembedding')
async def test_4_1_kb_created_after_document(mock_embedding, mock_get_model_info, test_db, mock_auth, setup_test_models):
    """Test 4.1: KB created with matching tag after document was created"""
    mock_embedding.return_value = create_mock_embedding_response()
    
    try:
        # Setup: Create document first with tagA
        tagA_id = await create_tag("TagA")
        document_id = await create_document(test_db, [tagA_id])
        
        # Verify document exists but is not indexed in any KB yet
        index_entries = await test_db.document_index.find({"document_id": document_id}).to_list(length=None)
        assert len(index_entries) == 0, "Document should not be indexed yet"
        
        # Create KB later with tagA (matching the document)
        kb1_id = await create_kb("KB1", [tagA_id])
        
        # Verify document is still not indexed (KB creation doesn't auto-index)
        await verify_document_in_kb(test_db, document_id, kb1_id, should_be_indexed=False)
        
        # Run reconciliation to find and index matching documents
        results = await ad.kb.reconciliation.reconcile_knowledge_base(
            ad.common.get_analytiq_client(), kb1_id, TEST_ORG_ID, dry_run=False
        )
        
        # Process the queued indexing messages
        await process_pending_kb_index_messages(test_db)
        
        # Verify document is now indexed in KB1
        await verify_document_in_kb(test_db, document_id, kb1_id, should_be_indexed=True)
        
        # Verify KB1 stats
        kb1 = await test_db.knowledge_bases.find_one({"_id": ObjectId(kb1_id)})
        assert kb1["document_count"] == 1, "KB1 should have 1 document"
        assert kb1["chunk_count"] > 0, "KB1 should have chunks"
        
    finally:
        await test_db.docs.delete_many({"organization_id": TEST_ORG_ID})
        await test_db.knowledge_bases.delete_many({"organization_id": TEST_ORG_ID})
        await test_db.tags.delete_many({"organization_id": TEST_ORG_ID})

@pytest.mark.asyncio
@patch('litellm.get_model_info', return_value={"provider": "openai"})
@patch('litellm.aembedding')
async def test_4_2_kb_created_after_document_multiple_kbs(mock_embedding, mock_get_model_info, test_db, mock_auth, setup_test_models):
    """Test 4.2: Multiple KBs created after document with matching tags"""
    mock_embedding.return_value = create_mock_embedding_response()
    
    try:
        # Setup: Create document first with [tagA, tagB]
        tagA_id = await create_tag("TagA")
        tagB_id = await create_tag("TagB")
        tagC_id = await create_tag("TagC")
        tagD_id = await create_tag("TagD")
        
        document_id = await create_document(test_db, [tagA_id, tagB_id])
        
        # Create KB1 later with [tagA, tagC]
        kb1_id = await create_kb("KB1", [tagA_id, tagC_id])
        
        # Create KB2 later with [tagB, tagD]
        kb2_id = await create_kb("KB2", [tagB_id, tagD_id])
        
        # Run reconciliation for both KBs
        await ad.kb.reconciliation.reconcile_knowledge_base(
            ad.common.get_analytiq_client(), kb1_id, TEST_ORG_ID, dry_run=False
        )
        await ad.kb.reconciliation.reconcile_knowledge_base(
            ad.common.get_analytiq_client(), kb2_id, TEST_ORG_ID, dry_run=False
        )
        
        # Process the queued indexing messages
        await process_pending_kb_index_messages(test_db)
        
        # Verify document is indexed in both KBs
        await verify_document_in_kb(test_db, document_id, kb1_id, should_be_indexed=True)
        await verify_document_in_kb(test_db, document_id, kb2_id, should_be_indexed=True)
        
        # Verify KB stats
        kb1 = await test_db.knowledge_bases.find_one({"_id": ObjectId(kb1_id)})
        kb2 = await test_db.knowledge_bases.find_one({"_id": ObjectId(kb2_id)})
        assert kb1["document_count"] == 1, "KB1 should have 1 document"
        assert kb2["document_count"] == 1, "KB2 should have 1 document"
        
    finally:
        await test_db.docs.delete_many({"organization_id": TEST_ORG_ID})
        await test_db.knowledge_bases.delete_many({"organization_id": TEST_ORG_ID})
        await test_db.tags.delete_many({"organization_id": TEST_ORG_ID})

@pytest.mark.asyncio
@patch('litellm.get_model_info', return_value={"provider": "openai"})
@patch('litellm.aembedding')
async def test_4_3_kb_created_after_document_no_match(mock_embedding, mock_get_model_info, test_db, mock_auth, setup_test_models):
    """Test 4.3: KB created after document but tags don't match"""
    mock_embedding.return_value = create_mock_embedding_response()
    
    try:
        # Setup: Create document first with tagA
        tagA_id = await create_tag("TagA")
        tagB_id = await create_tag("TagB")
        
        document_id = await create_document(test_db, [tagA_id])
        
        # Create KB later with tagB (no match)
        kb1_id = await create_kb("KB1", [tagB_id])
        
        # Run reconciliation
        results = await ad.kb.reconciliation.reconcile_knowledge_base(
            ad.common.get_analytiq_client(), kb1_id, TEST_ORG_ID, dry_run=False
        )
        
        # Process any queued indexing messages
        await process_pending_kb_index_messages(test_db)
        
        # Verify document is NOT indexed in KB1 (tags don't match)
        await verify_document_in_kb(test_db, document_id, kb1_id, should_be_indexed=False)
        
        # Verify KB1 stats
        kb1 = await test_db.knowledge_bases.find_one({"_id": ObjectId(kb1_id)})
        assert kb1["document_count"] == 0, "KB1 should have 0 documents"
        
    finally:
        await test_db.docs.delete_many({"organization_id": TEST_ORG_ID})
        await test_db.knowledge_bases.delete_many({"organization_id": TEST_ORG_ID})
        await test_db.tags.delete_many({"organization_id": TEST_ORG_ID})


# ============================================================================
# EDGE CASES
# ============================================================================

@pytest.mark.asyncio
@patch('litellm.get_model_info', return_value={"provider": "openai"})
@patch('litellm.aembedding')
async def test_edge_case_document_no_tags(mock_embedding, mock_get_model_info, test_db, mock_auth, setup_test_models):
    """Edge Case: Document with no tags"""
    mock_embedding.return_value = create_mock_embedding_response()
    
    try:
        # Setup: Document has [], KB1 has [tagA]
        tagA_id = await create_tag("TagA")
        kb1_id = await create_kb("KB1", [tagA_id])
        document_id = await create_document(test_db, [])
        
        # Attempt to index the document
        await index_document(document_id, None, test_db)
        await process_pending_kb_index_messages(test_db, document_id)
        
        # Verify document is NOT indexed
        await verify_document_in_kb(test_db, document_id, kb1_id, should_be_indexed=False)
        
        # Verify KB1 stats
        kb1 = await test_db.knowledge_bases.find_one({"_id": ObjectId(kb1_id)})
        assert kb1["document_count"] == 0, "KB1 should have 0 documents"
        
    finally:
        await test_db.docs.delete_many({"organization_id": TEST_ORG_ID})
        await test_db.knowledge_bases.delete_many({"organization_id": TEST_ORG_ID})
        await test_db.tags.delete_many({"organization_id": TEST_ORG_ID})

@pytest.mark.asyncio
@patch('litellm.get_model_info', return_value={"provider": "openai"})
@patch('litellm.aembedding')
async def test_edge_case_kb_no_tags(mock_embedding, mock_get_model_info, test_db, mock_auth, setup_test_models):
    """Edge Case: KB with no tags"""
    mock_embedding.return_value = create_mock_embedding_response()
    
    try:
        # Setup: Document has [tagA], KB1 has []
        tagA_id = await create_tag("TagA")
        kb1_id = await create_kb("KB1", [])
        document_id = await create_document(test_db, [tagA_id])
        
        # Attempt to index the document
        await index_document(document_id, None, test_db)
        await process_pending_kb_index_messages(test_db, document_id)
        
        # Verify document is NOT indexed (KB has no tags)
        await verify_document_in_kb(test_db, document_id, kb1_id, should_be_indexed=False)
        
        # Verify KB1 stats
        kb1 = await test_db.knowledge_bases.find_one({"_id": ObjectId(kb1_id)})
        assert kb1["document_count"] == 0, "KB1 should have 0 documents"
        
    finally:
        await test_db.docs.delete_many({"organization_id": TEST_ORG_ID})
        await test_db.knowledge_bases.delete_many({"organization_id": TEST_ORG_ID})
        await test_db.tags.delete_many({"organization_id": TEST_ORG_ID})
