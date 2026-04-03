import asyncio
from datetime import datetime, UTC
from unittest.mock import patch

import pytest
from bson import ObjectId

import analytiq_data as ad

from .conftest_utils import TEST_ORG_ID, client, get_auth_headers
from .kb_test_helpers import create_kb_api, create_mock_embedding_response, create_tag_api, delete_kb_api


@pytest.mark.kb_slow
@pytest.mark.mongot
@pytest.mark.asyncio
@patch("litellm.get_model_info", return_value={"provider": "openai"})
@patch("litellm.aembedding")
async def test_kb_search_http_endpoint_returns_results_with_mongot(
    mock_embedding,
    _mock_get_model_info,
    test_db,
    mock_auth,
    setup_test_models,
):
    """
    End-to-end KB search via HTTP, using real $vectorSearch (mongot).
    External dependencies (embeddings) are mocked; KB logic + DB search are real.
    """
    mock_embedding.return_value = create_mock_embedding_response()

    tag_id = create_tag_api("Mongot Search Tag")
    kb_id = create_kb_api("Mongot Search KB", [tag_id])

    analytiq_client = ad.common.get_analytiq_client()
    doc_id = str(ObjectId())
    await test_db.docs.insert_one(
        {
            "_id": ObjectId(doc_id),
            "organization_id": TEST_ORG_ID,
            "user_file_name": "doc_search.pdf",
            "tag_ids": [tag_id],
            "upload_date": datetime.now(UTC),
            "state": ad.common.doc.DOCUMENT_STATE_OCR_COMPLETED,
            "mongo_file_name": "doc_search.pdf",
        }
    )
    await ad.common.ocr.save_ocr_text(
        analytiq_client,
        doc_id,
        "This is a mongot-backed search integration test about invoices and totals.",
    )
    await ad.msg_handlers.process_kb_index_msg(
        analytiq_client,
        {"_id": str(ObjectId()), "msg": {"document_id": doc_id, "kb_id": kb_id}},
    )

    try:
        # Search indexes can take a moment to build; retry until we get results.
        last = None
        for _ in range(30):
            last = client.post(
                f"/v0/orgs/{TEST_ORG_ID}/knowledge-bases/{kb_id}/search",
                json={"query": "invoice totals", "top_k": 5},
                headers=get_auth_headers(),
            )
            if last.status_code == 200:
                body = last.json()
                if body.get("results"):
                    return
            await asyncio.sleep(1)

        assert last is not None
        assert last.status_code == 200
        assert last.json().get("results"), "Expected non-empty results from mongot vector search"
    finally:
        delete_kb_api(kb_id)
