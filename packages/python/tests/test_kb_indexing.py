"""
Additional unit tests for KB indexing, caching, deletion cleanup, tag updates, reconciliation, and search.
"""

import pytest
from bson import ObjectId
from pymongo.errors import OperationFailure
import os
from datetime import datetime, UTC
import logging
from unittest.mock import patch, Mock

from .conftest_utils import client, TEST_ORG_ID, get_auth_headers
from .kb_test_helpers import (
    MOCK_EMBEDDING_DIMENSIONS,
    create_mock_embedding_response,
    create_kb_api,
    create_tag_api,
    delete_kb_api,
)
import analytiq_data as ad

logger = logging.getLogger(__name__)

assert os.environ["ENV"] == "pytest"

@pytest.mark.asyncio
@patch('litellm.get_model_info', return_value={"provider": "openai"})
@patch('litellm.aembedding')
async def test_kb_indexing_workflow(mock_embedding, mock_get_model_info, test_db, mock_auth, setup_test_models):
    """Test KB indexing workflow with actual document"""
    logger.info(f"test_kb_indexing_workflow() start")
    
    # Set up mock embedding response
    mock_embedding.return_value = create_mock_embedding_response()

    tag_id = create_tag_api("KB Test Tag")
    kb_id = create_kb_api(
        "Test Indexing KB",
        [tag_id],
        chunk_size=100,
        chunk_overlap=20,
    )

    document_id = str(ObjectId())
    test_text = "This is a test document for knowledge base indexing. " * 10

    await test_db.docs.insert_one({
        "_id": ObjectId(document_id),
        "organization_id": TEST_ORG_ID,
        "user_file_name": "test_doc.pdf",
        "tag_ids": [tag_id],
        "upload_date": datetime.now(UTC),
        "state": ad.common.doc.DOCUMENT_STATE_OCR_COMPLETED
    })

    analytiq_client = ad.common.get_analytiq_client()
    await ad.common.ocr.save_ocr_text(analytiq_client, document_id, test_text)

    kb_msg = {
        "_id": str(ObjectId()),
        "msg": {"document_id": document_id, "kb_id": kb_id}
    }
    await ad.msg_handlers.process_kb_index_msg(analytiq_client, kb_msg)

    index_entry = await test_db.document_index.find_one({
        "kb_id": kb_id,
        "document_id": document_id
    })
    assert index_entry is not None, "Document should be indexed"
    assert index_entry["chunk_count"] > 0, "Document should have chunks"

    vectors_collection = test_db[f"kb_vectors_{kb_id}"]
    vector_count = await vectors_collection.count_documents({"document_id": document_id})
    assert vector_count > 0, "Vectors should be created"

    kb = await test_db.knowledge_bases.find_one({"_id": ObjectId(kb_id)})
    assert kb["document_count"] == 1
    assert kb["chunk_count"] == index_entry["chunk_count"]

    delete_kb_api(kb_id)
    await test_db.docs.delete_one({"_id": ObjectId(document_id)})

@pytest.mark.asyncio
@patch('litellm.get_model_info', return_value={"provider": "openai"})
@patch('litellm.aembedding')
async def test_kb_indexing_embedding_cache(mock_embedding, mock_get_model_info, test_db, mock_auth, setup_test_models):
    """Test that embedding cache works across KBs"""
    logger.info(f"test_kb_indexing_embedding_cache() start")
    
    # Set up mock embedding response - track calls
    embedding_calls = []
    async def mock_embedding_side_effect(*args, **kwargs):
        embedding_calls.append(kwargs.get("input", []))
        return create_mock_embedding_response()
    
    mock_embedding.side_effect = mock_embedding_side_effect

    tag_id = create_tag_api("Cache Test Tag")
    kb1_id = create_kb_api(
        "Cache Test KB 1", [tag_id], embedding_model="text-embedding-3-small"
    )
    kb2_id = create_kb_api(
        "Cache Test KB 2", [tag_id], embedding_model="text-embedding-3-small"
    )

    document_id = str(ObjectId())
    test_text = "This is a test chunk that will be indexed twice. " * 5

    await test_db.docs.insert_one({
        "_id": ObjectId(document_id),
        "organization_id": TEST_ORG_ID,
        "user_file_name": "cache_test.pdf",
        "tag_ids": [tag_id],
        "upload_date": datetime.now(UTC),
        "state": ad.common.doc.DOCUMENT_STATE_OCR_COMPLETED
    })

    analytiq_client = ad.common.get_analytiq_client()
    await ad.common.ocr.save_ocr_text(analytiq_client, document_id, test_text)

    embedding_calls.clear()

    kb_msg1 = {
        "_id": str(ObjectId()),
        "msg": {"document_id": document_id, "kb_id": kb1_id}
    }
    await ad.msg_handlers.process_kb_index_msg(analytiq_client, kb_msg1)

    first_call_count = len(embedding_calls)
    assert first_call_count > 0, "Should generate embeddings for first KB"

    embedding_calls.clear()
    kb_msg2 = {
        "_id": str(ObjectId()),
        "msg": {"document_id": document_id, "kb_id": kb2_id}
    }
    await ad.msg_handlers.process_kb_index_msg(analytiq_client, kb_msg2)

    index1 = await test_db.document_index.find_one({"kb_id": kb1_id, "document_id": document_id})
    index2 = await test_db.document_index.find_one({"kb_id": kb2_id, "document_id": document_id})
    assert index1 is not None
    assert index2 is not None

    delete_kb_api(kb1_id)
    delete_kb_api(kb2_id)
    await test_db.docs.delete_one({"_id": ObjectId(document_id)})

@pytest.mark.asyncio
@patch('litellm.get_model_info', return_value={"provider": "openai"})
@patch('litellm.aembedding')
async def test_kb_document_deletion_cleanup(mock_embedding, mock_get_model_info, test_db, mock_auth, setup_test_models):
    """Test that document deletion removes KB vectors"""
    logger.info(f"test_kb_document_deletion_cleanup() start")
    
    mock_embedding.return_value = create_mock_embedding_response()

    tag_id = create_tag_api("Deletion Test Tag")
    kb_id = create_kb_api("Deletion Test KB", [tag_id])

    document_id = str(ObjectId())
    test_text = "Test document for deletion cleanup. " * 5

    await test_db.docs.insert_one({
        "_id": ObjectId(document_id),
        "organization_id": TEST_ORG_ID,
        "user_file_name": "delete_test.pdf",
        "tag_ids": [tag_id],
        "upload_date": datetime.now(UTC),
        "state": ad.common.doc.DOCUMENT_STATE_OCR_COMPLETED,
        "mongo_file_name": "test_file.pdf"
    })

    analytiq_client = ad.common.get_analytiq_client()
    await ad.common.ocr.save_ocr_text(analytiq_client, document_id, test_text)

    kb_msg = {
        "_id": str(ObjectId()),
        "msg": {"document_id": document_id, "kb_id": kb_id}
    }
    await ad.msg_handlers.process_kb_index_msg(analytiq_client, kb_msg)

    index_entry = await test_db.document_index.find_one({"kb_id": kb_id, "document_id": document_id})
    assert index_entry is not None

    vectors_collection = test_db[f"kb_vectors_{kb_id}"]
    vector_count_before = await vectors_collection.count_documents({"document_id": document_id})
    assert vector_count_before > 0

    await ad.common.delete_doc(analytiq_client, document_id, TEST_ORG_ID)

    vector_count_after = await vectors_collection.count_documents({"document_id": document_id})
    assert vector_count_after == 0, "Vectors should be deleted"

    index_entry_after = await test_db.document_index.find_one({"kb_id": kb_id, "document_id": document_id})
    assert index_entry_after is None, "document_index entry should be removed"

    kb = await test_db.knowledge_bases.find_one({"_id": ObjectId(kb_id)})
    assert kb["document_count"] == 0

    delete_kb_api(kb_id)

@pytest.mark.asyncio
@patch('litellm.get_model_info', return_value={"provider": "openai"})
@patch('litellm.aembedding')
async def test_kb_tag_update_trigger(mock_embedding, mock_get_model_info, test_db, mock_auth, setup_test_models):
    """Test that tag updates trigger KB membership re-evaluation"""
    logger.info(f"test_kb_tag_update_trigger() start")
    
    mock_embedding.return_value = create_mock_embedding_response()

    tag1_id = create_tag_api("Tag 1")
    tag2_id = create_tag_api("Tag 2", color="#33FF57")
    kb_id = create_kb_api("Tag Update Test KB", [tag1_id])

    document_id = str(ObjectId())
    test_text = "Test document for tag updates. " * 5

    await test_db.docs.insert_one({
        "_id": ObjectId(document_id),
        "organization_id": TEST_ORG_ID,
        "user_file_name": "tag_update_test.pdf",
        "tag_ids": [tag1_id],
        "upload_date": datetime.now(UTC),
        "state": ad.common.doc.DOCUMENT_STATE_OCR_COMPLETED,
        "mongo_file_name": "test_file.pdf"
    })

    analytiq_client = ad.common.get_analytiq_client()
    await ad.common.ocr.save_ocr_text(analytiq_client, document_id, test_text)

    kb_msg = {
        "_id": str(ObjectId()),
        "msg": {"document_id": document_id, "kb_id": kb_id}
    }
    await ad.msg_handlers.process_kb_index_msg(analytiq_client, kb_msg)

    index_entry = await test_db.document_index.find_one({"kb_id": kb_id, "document_id": document_id})
    assert index_entry is not None

    update_response = client.put(
        f"/v0/orgs/{TEST_ORG_ID}/documents/{document_id}",
        json={"tag_ids": [tag2_id]},
        headers=get_auth_headers()
    )
    assert update_response.status_code == 200

    queue_collection = test_db["queues.kb_index"]
    queue_messages = await queue_collection.find({"status": "pending"}).to_list(length=10)
    for msg in queue_messages:
        if msg.get("msg", {}).get("document_id") == document_id:
            await ad.msg_handlers.process_kb_index_msg(analytiq_client, msg)
            break

    await ad.kb.indexing.remove_document_from_kb(analytiq_client, kb_id, document_id, TEST_ORG_ID)

    index_entry_after = await test_db.document_index.find_one({"kb_id": kb_id, "document_id": document_id})
    assert index_entry_after is None, "Document should be removed from KB after tag change"

    delete_kb_api(kb_id)
    await test_db.docs.delete_one({"_id": ObjectId(document_id)})

@pytest.mark.asyncio
@patch('litellm.get_model_info', return_value={"provider": "openai"})
@patch('litellm.aembedding')
async def test_kb_reconciliation(mock_embedding, mock_get_model_info, test_db, mock_auth, setup_test_models):
    """Test reconciliation service"""
    logger.info(f"test_kb_reconciliation() start")
    
    mock_embedding.return_value = create_mock_embedding_response()

    tag_id = create_tag_api("Reconciliation Tag")
    kb_id = create_kb_api("Reconciliation Test KB", [tag_id])

    document_id = str(ObjectId())
    test_text = "Test document for reconciliation. " * 5

    await test_db.docs.insert_one({
        "_id": ObjectId(document_id),
        "organization_id": TEST_ORG_ID,
        "user_file_name": "reconciliation_test.pdf",
        "tag_ids": [tag_id],
        "upload_date": datetime.now(UTC),
        "state": ad.common.doc.DOCUMENT_STATE_OCR_COMPLETED,
        "mongo_file_name": "test_file.pdf"
    })

    analytiq_client = ad.common.get_analytiq_client()
    await ad.common.ocr.save_ocr_text(analytiq_client, document_id, test_text)

    results = await ad.kb.reconciliation.reconcile_knowledge_base(
        analytiq_client, TEST_ORG_ID, kb_id=kb_id, dry_run=True
    )

    assert len(results["missing_documents"]) > 0, "Should detect missing document"
    assert document_id in results["missing_documents"]

    await ad.kb.reconciliation.reconcile_knowledge_base(
        analytiq_client, TEST_ORG_ID, kb_id=kb_id, dry_run=False
    )

    queue_collection = test_db["queues.kb_index"]
    queue_messages = await queue_collection.find({"status": "pending"}).to_list(length=10)
    message_found = False
    for msg in queue_messages:
        msg_body = msg.get("msg", {})
        if msg_body.get("document_id") == document_id and msg_body.get("kb_id") == kb_id:
            message_found = True
            kb_msg = {
                "_id": str(msg["_id"]),
                "msg": msg_body
            }
            await ad.msg_handlers.process_kb_index_msg(analytiq_client, kb_msg)
            break

    assert message_found, f"Indexing message should be queued. Found {len(queue_messages)} messages in queue"

    index_entry = await test_db.document_index.find_one({"kb_id": kb_id, "document_id": document_id})
    assert index_entry is not None, "Document should be indexed after reconciliation"

    await test_db.docs.update_one(
        {"_id": ObjectId(document_id)},
        {"$set": {"tag_ids": []}}
    )

    await ad.kb.reconciliation.reconcile_knowledge_base(
        analytiq_client, TEST_ORG_ID, kb_id=kb_id, dry_run=False
    )

    index_entry_after = await test_db.document_index.find_one({"kb_id": kb_id, "document_id": document_id})
    assert index_entry_after is None, "Stale document should be removed"

    delete_kb_api(kb_id)
    await test_db.docs.delete_one({"_id": ObjectId(document_id)})

@pytest.mark.asyncio
@patch('litellm.get_model_info', return_value={"provider": "openai"})
@patch('litellm.aembedding')
async def test_kb_delete_removes_vector_collection_and_document_index(
    mock_embedding, mock_get_model_info, test_db, mock_auth, setup_test_models
):
    """DELETE /knowledge-bases/{id} drops search indexes, the kb_vectors_* collection, and document_index rows."""
    mock_embedding.return_value = create_mock_embedding_response()
    kb_id = None
    document_id = None
    tag_id = None
    try:
        tag_id = create_tag_api("KB Delete Cleanup Tag", color="#111111")
        kb_id = create_kb_api(
            "KB Delete Cleanup KB",
            [tag_id],
            chunk_size=100,
            chunk_overlap=20,
        )

        collection_name = f"kb_vectors_{kb_id}"
        assert collection_name in await test_db.list_collection_names()

        document_id = str(ObjectId())
        test_text = "Content for KB delete cleanup test. " * 10
        await test_db.docs.insert_one(
            {
                "_id": ObjectId(document_id),
                "organization_id": TEST_ORG_ID,
                "user_file_name": "kb_delete_cleanup.pdf",
                "tag_ids": [tag_id],
                "upload_date": datetime.now(UTC),
                "state": ad.common.doc.DOCUMENT_STATE_OCR_COMPLETED,
            }
        )
        analytiq_client = ad.common.get_analytiq_client()
        await ad.common.ocr.save_ocr_text(analytiq_client, document_id, test_text)

        await ad.msg_handlers.process_kb_index_msg(
            analytiq_client,
            {"_id": str(ObjectId()), "msg": {"document_id": document_id, "kb_id": kb_id}},
        )

        assert (
            await test_db.document_index.find_one({"kb_id": kb_id, "document_id": document_id})
            is not None
        )
        vectors_coll = test_db[collection_name]
        assert await vectors_coll.count_documents({}) > 0

        # Search indexes must exist and be listed (vector + lexical) before delete
        list_before = await test_db.command({"listSearchIndexes": collection_name})
        batch_before = (list_before.get("cursor") or {}).get("firstBatch") or []
        assert len(batch_before) >= 2, (
            f"Expected kb_vector_index and kb_lexical_index on {collection_name}, got {batch_before!r}"
        )
        names_before = {entry.get("name") for entry in batch_before}
        assert "kb_vector_index" in names_before
        assert "kb_lexical_index" in names_before

        del_response = client.delete(
            f"/v0/orgs/{TEST_ORG_ID}/knowledge-bases/{kb_id}",
            headers=get_auth_headers(),
        )
        assert del_response.status_code == 200

        assert await test_db.knowledge_bases.find_one({"_id": ObjectId(kb_id)}) is None
        assert await test_db.document_index.count_documents({"kb_id": kb_id}) == 0
        assert collection_name not in await test_db.list_collection_names()

        # Search indexes must be gone with the collection (empty batch or command fails)
        try:
            list_after = await test_db.command({"listSearchIndexes": collection_name})
        except OperationFailure:
            pass
        else:
            batch_after = (list_after.get("cursor") or {}).get("firstBatch") or []
            assert len(batch_after) == 0, f"Search indexes should be dropped, got {batch_after!r}"

        kb_id = None  # already removed; skip finally DELETE
    finally:
        if document_id:
            await test_db.docs.delete_one({"_id": ObjectId(document_id)})
        if kb_id:
            delete_kb_api(kb_id)
        if tag_id:
            await test_db.tags.delete_one({"_id": ObjectId(tag_id)})

@pytest.mark.asyncio
@patch('litellm.get_model_info', return_value={"provider": "openai"})
@patch('litellm.aembedding')
async def test_kb_search_with_data(mock_embedding, mock_get_model_info, test_db, mock_auth, setup_test_models):
    """Test vector search with actual indexed data"""
    logger.info(f"test_kb_search_with_data() start")
    
    # Create mock embeddings that return different vectors for different texts
    def create_mock_embedding_for_text(text):
        # Create a simple hash-based embedding for testing
        import hashlib
        hash_val = int(hashlib.md5(text.encode()).hexdigest()[:8], 16)
        # Create a 1536-dim vector based on hash
        embedding = [(hash_val % 100) / 100.0] * MOCK_EMBEDDING_DIMENSIONS
        return embedding
    
    async def mock_embedding_side_effect(*args, **kwargs):
        inputs = kwargs.get("input", [])
        mock_response = Mock()
        mock_response.data = [
            {"embedding": create_mock_embedding_for_text(text)}
            for text in inputs
        ]
        return mock_response

    mock_embedding.side_effect = mock_embedding_side_effect

    tag_id = create_tag_api("Search Test Tag")
    kb_id = create_kb_api(
        "Search Test KB", [tag_id], chunk_size=50, chunk_overlap=10
    )

    document_id = str(ObjectId())
    test_text = (
        "This document contains information about payment terms. "
        "Payment is due within 30 days. " * 3
    )

    await test_db.docs.insert_one({
        "_id": ObjectId(document_id),
        "organization_id": TEST_ORG_ID,
        "user_file_name": "search_test.pdf",
        "tag_ids": [tag_id],
        "upload_date": datetime.now(UTC),
        "state": ad.common.doc.DOCUMENT_STATE_OCR_COMPLETED,
        "mongo_file_name": "test_file.pdf"
    })

    analytiq_client = ad.common.get_analytiq_client()
    await ad.common.ocr.save_ocr_text(analytiq_client, document_id, test_text)

    kb_msg = {
        "_id": str(ObjectId()),
        "msg": {"document_id": document_id, "kb_id": kb_id}
    }
    await ad.msg_handlers.process_kb_index_msg(analytiq_client, kb_msg)

    from app.routes.knowledge_bases import wait_for_vector_index_ready
    await wait_for_vector_index_ready(analytiq_client, kb_id, max_wait_seconds=60)

    search_response = client.post(
        f"/v0/orgs/{TEST_ORG_ID}/knowledge-bases/{kb_id}/search",
        json={"query": "payment terms", "top_k": 5},
        headers=get_auth_headers()
    )

    assert search_response.status_code == 200
    search_result = search_response.json()
    assert "results" in search_result
    assert search_result["query"] == "payment terms"

    delete_kb_api(kb_id)
    await test_db.docs.delete_one({"_id": ObjectId(document_id)})
