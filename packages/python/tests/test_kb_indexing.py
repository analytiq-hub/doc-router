"""
KB tests: one integration test that exercises real indexing against a single API-created KB,
plus mocked API tests that do not run KB worker logic or mongot search.
"""

import logging
import os
from datetime import datetime, UTC
from unittest.mock import AsyncMock, patch

import pytest
from bson import ObjectId

from .conftest_utils import TEST_ORG_ID, client, get_auth_headers
from .kb_test_helpers import (
    create_kb_api,
    create_mock_embedding_response,
    create_tag_api,
    delete_kb_api,
)
import analytiq_data as ad

logger = logging.getLogger(__name__)

assert os.environ["ENV"] == "pytest"


async def _process_pending_kb_index_messages(test_db, document_id: str | None = None):
    analytiq_client = ad.common.get_analytiq_client()
    queue_collection = test_db["queues.kb_index"]
    query: dict = {"status": "pending"}
    if document_id:
        query["msg.document_id"] = document_id
    queue_messages = await queue_collection.find(query).to_list(length=50)
    for msg in queue_messages:
        kb_msg = {"_id": str(msg["_id"]), "msg": msg.get("msg", {})}
        await ad.msg_handlers.process_kb_index_msg(analytiq_client, kb_msg)


@pytest.mark.kb_slow
@pytest.mark.asyncio
@patch("litellm.get_model_info", return_value={"provider": "openai"})
@patch("litellm.aembedding")
async def test_kb_integration_single_kb_lifecycle(
    mock_embedding, mock_get_model_info, test_db, mock_auth, setup_test_models
):
    """
    One real KB (POST /knowledge-bases): index, reconciliation, tag change, delete cleanup, KB delete.
    Avoids listSearchIndexes / vector search (mongot); relies on collections and document_index.
    """
    mock_embedding.return_value = create_mock_embedding_response()

    tag_kb = create_tag_api("Integration KB Tag")
    tag_other = create_tag_api("Integration Other Tag", color="#33AA33")
    kb_id = create_kb_api(
        "Integration Lifecycle KB",
        [tag_kb],
        chunk_size=100,
        chunk_overlap=20,
    )
    analytiq_client = ad.common.get_analytiq_client()
    doc1 = None
    doc2 = None

    try:
        # --- 1) Basic index + vectors + KB stats
        doc1 = str(ObjectId())
        text1 = "Integration test document one for knowledge base indexing. " * 10
        await test_db.docs.insert_one(
            {
                "_id": ObjectId(doc1),
                "organization_id": TEST_ORG_ID,
                "user_file_name": "doc1.pdf",
                "tag_ids": [tag_kb],
                "upload_date": datetime.now(UTC),
                "state": ad.common.doc.DOCUMENT_STATE_OCR_COMPLETED,
                "mongo_file_name": "f1.pdf",
            }
        )
        await ad.ocr.save_ocr_text(analytiq_client, doc1, text1)
        await ad.msg_handlers.process_kb_index_msg(
            analytiq_client,
            {"_id": str(ObjectId()), "msg": {"document_id": doc1, "kb_id": kb_id}},
        )
        index_entry = await test_db.document_index.find_one(
            {"kb_id": kb_id, "document_id": doc1}
        )
        assert index_entry is not None
        assert index_entry["chunk_count"] > 0
        vectors = test_db[f"kb_vectors_{kb_id}"]
        assert await vectors.count_documents({"document_id": doc1}) > 0
        kb = await test_db.knowledge_bases.find_one({"_id": ObjectId(kb_id)})
        assert kb["document_count"] >= 1
        assert kb["chunk_count"] >= index_entry["chunk_count"]

        # --- 2) Embedding cache: second pass same doc+kb should not explode embedding calls
        mock_embedding.reset_mock()
        await ad.msg_handlers.process_kb_index_msg(
            analytiq_client,
            {"_id": str(ObjectId()), "msg": {"document_id": doc1, "kb_id": kb_id}},
        )
        assert mock_embedding.call_count <= 1

        # --- 3) Reconciliation: doc2 tagged but not indexed → missing → index after reconcile
        doc2 = str(ObjectId())
        text2 = "Document two for reconciliation. " * 10
        await test_db.docs.insert_one(
            {
                "_id": ObjectId(doc2),
                "organization_id": TEST_ORG_ID,
                "user_file_name": "doc2.pdf",
                "tag_ids": [tag_kb],
                "upload_date": datetime.now(UTC),
                "state": ad.common.doc.DOCUMENT_STATE_OCR_COMPLETED,
                "mongo_file_name": "f2.pdf",
            }
        )
        await ad.ocr.save_ocr_text(analytiq_client, doc2, text2)

        dry = await ad.kb.reconciliation.reconcile_knowledge_base(
            analytiq_client, TEST_ORG_ID, kb_id=kb_id, dry_run=True
        )
        assert doc2 in dry["missing_documents"]

        await ad.kb.reconciliation.reconcile_knowledge_base(
            analytiq_client, TEST_ORG_ID, kb_id=kb_id, dry_run=False
        )
        await _process_pending_kb_index_messages(test_db, document_id=doc2)
        assert (
            await test_db.document_index.find_one({"kb_id": kb_id, "document_id": doc2})
            is not None
        )

        # --- 4) Tag update removes doc1 from KB
        upd = client.put(
            f"/v0/orgs/{TEST_ORG_ID}/documents/{doc1}",
            json={"tag_ids": [tag_other]},
            headers=get_auth_headers(),
        )
        assert upd.status_code == 200
        await _process_pending_kb_index_messages(test_db, document_id=doc1)
        await ad.kb.indexing.remove_document_from_kb(
            analytiq_client, kb_id, doc1, TEST_ORG_ID
        )
        assert (
            await test_db.document_index.find_one({"kb_id": kb_id, "document_id": doc1})
            is None
        )

        # --- 5) Document deletion removes vectors for doc2
        await ad.common.delete_doc(analytiq_client, doc2, TEST_ORG_ID)
        assert await vectors.count_documents({"document_id": doc2}) == 0
        assert (
            await test_db.document_index.find_one({"kb_id": kb_id, "document_id": doc2})
            is None
        )

        # --- 6) DELETE KB via API: KB row, document_index, and vector collection gone
        coll_name = f"kb_vectors_{kb_id}"
        del_r = client.delete(
            f"/v0/orgs/{TEST_ORG_ID}/knowledge-bases/{kb_id}",
            headers=get_auth_headers(),
        )
        assert del_r.status_code == 200
        assert await test_db.knowledge_bases.find_one({"_id": ObjectId(kb_id)}) is None
        assert await test_db.document_index.count_documents({"kb_id": kb_id}) == 0
        assert coll_name not in await test_db.list_collection_names()

    finally:
        if await test_db.knowledge_bases.find_one({"_id": ObjectId(kb_id)}):
            delete_kb_api(kb_id)
        doc_ids = []
        if doc1:
            doc_ids.append(ObjectId(doc1))
        if doc2:
            doc_ids.append(ObjectId(doc2))
        if doc_ids:
            await test_db.docs.delete_many({"_id": {"$in": doc_ids}})


@pytest.mark.kb_slow
@pytest.mark.asyncio
@patch("litellm.get_model_info", return_value={"provider": "openai"})
@patch("litellm.aembedding")
async def test_kb_api_crud_smoke(
    mock_embedding,
    mock_get_model_info,
    test_db,
    mock_auth,
    setup_test_models,
):
    """HTTP CRUD surface for KBs (no mocking of KB core functions)."""
    mock_embedding.return_value = create_mock_embedding_response()
    tag_id = create_tag_api("Mocked API Tag")
    kb_id = create_kb_api("Mocked API KB", [tag_id])
    try:
        lr = client.get(
            f"/v0/orgs/{TEST_ORG_ID}/knowledge-bases",
            headers=get_auth_headers(),
        )
        assert lr.status_code == 200
        assert any(x["kb_id"] == kb_id for x in lr.json()["knowledge_bases"])

        gr = client.get(
            f"/v0/orgs/{TEST_ORG_ID}/knowledge-bases/{kb_id}",
            headers=get_auth_headers(),
        )
        assert gr.status_code == 200
        assert gr.json()["kb_id"] == kb_id

        pr = client.put(
            f"/v0/orgs/{TEST_ORG_ID}/knowledge-bases/{kb_id}",
            json={"name": "Mocked API KB Renamed"},
            headers=get_auth_headers(),
        )
        assert pr.status_code == 200
    finally:
        delete_kb_api(kb_id)