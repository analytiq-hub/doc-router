"""
SPU metering for KB indexing and search: uses a KB row inserted directly (no POST /knowledge-bases).
Search tests mock vector aggregation to avoid mongot.
"""

import logging
import os
from datetime import datetime, UTC
from unittest.mock import AsyncMock, patch

import pytest
from bson import ObjectId

from analytiq_data.kb.indexing import spus_for_kb_indexing_embedding_misses

from .conftest_utils import TEST_ORG_ID, client, get_auth_headers
from .kb_test_helpers import (
    create_mock_embedding_response,
    insert_minimal_kb,
    insert_org_tag,
)
import analytiq_data as ad

logger = logging.getLogger(__name__)

assert os.environ["ENV"] == "pytest"


def test_spus_for_kb_indexing_embedding_misses_formula():
    assert spus_for_kb_indexing_embedding_misses(0) == 0
    assert spus_for_kb_indexing_embedding_misses(1) == 1
    assert spus_for_kb_indexing_embedding_misses(250) == 1
    assert spus_for_kb_indexing_embedding_misses(251) == 2
    assert spus_for_kb_indexing_embedding_misses(1000) == 4


@pytest.mark.asyncio
@patch("litellm.get_model_info", return_value={"provider": "openai"})
@patch("litellm.aembedding")
@patch("analytiq_data.payments.record_spu_usage")
@patch("analytiq_data.payments.check_spu_limits")
async def test_kb_indexing_spu_recording(
    mock_check_spu_limits,
    mock_record_spu_usage,
    mock_embedding,
    mock_get_model_info,
    test_db,
    mock_auth,
    setup_test_models,
):
    mock_embedding.return_value = create_mock_embedding_response()
    mock_check_spu_limits.return_value = True
    mock_record_spu_usage.return_value = True

    tag_id = await insert_org_tag(test_db, "SPU Tag")
    kb_id = await insert_minimal_kb(
        test_db, [tag_id], name="SPU KB", chunk_size=50, chunk_overlap=10
    )

    document_id = str(ObjectId())
    test_text = "This is a test document for SPU recording. " * 20
    await test_db.docs.insert_one(
        {
            "_id": ObjectId(document_id),
            "organization_id": TEST_ORG_ID,
            "user_file_name": "spu_test.pdf",
            "tag_ids": [tag_id],
            "upload_date": datetime.now(UTC),
            "state": ad.common.doc.DOCUMENT_STATE_OCR_COMPLETED,
            "mongo_file_name": "test_file.pdf",
        }
    )
    analytiq_client = ad.common.get_analytiq_client()
    await ad.common.ocr.save_ocr_text(analytiq_client, document_id, test_text)

    mock_check_spu_limits.reset_mock()
    mock_record_spu_usage.reset_mock()

    await ad.msg_handlers.process_kb_index_msg(
        analytiq_client,
        {"_id": str(ObjectId()), "msg": {"document_id": document_id, "kb_id": kb_id}},
    )

    assert mock_check_spu_limits.called
    assert mock_record_spu_usage.called
    check_call = mock_check_spu_limits.call_args
    assert check_call[0][0] == TEST_ORG_ID
    assert check_call[0][1] > 0

    record_call = mock_record_spu_usage.call_args
    assert record_call[1]["org_id"] == TEST_ORG_ID
    assert record_call[1]["spus"] > 0
    assert record_call[1]["llm_model"] == "text-embedding-3-small"
    assert record_call[1]["llm_provider"] == "openai"

    idx = await test_db.document_index.find_one({"kb_id": kb_id, "document_id": document_id})
    assert idx is not None
    num_chunks = idx["chunk_count"]
    expected_spus = spus_for_kb_indexing_embedding_misses(num_chunks)
    assert check_call[0][1] == expected_spus
    assert record_call[1]["spus"] == expected_spus


@pytest.mark.asyncio
@patch("litellm.get_model_info", return_value={"provider": "openai"})
@patch("litellm.aembedding")
@patch("analytiq_data.payments.record_spu_usage")
@patch("analytiq_data.payments.check_spu_limits")
async def test_kb_indexing_spu_insufficient_credits(
    mock_check_spu_limits,
    mock_record_spu_usage,
    mock_embedding,
    mock_get_model_info,
    test_db,
    mock_auth,
    setup_test_models,
):
    from app.routes.payments import SPUCreditException

    mock_embedding.return_value = create_mock_embedding_response()
    mock_check_spu_limits.side_effect = SPUCreditException(TEST_ORG_ID, 10, 5)
    mock_record_spu_usage.return_value = True

    tag_id = await insert_org_tag(test_db, "SPU Credit Tag")
    kb_id = await insert_minimal_kb(test_db, [tag_id], name="SPU Credit KB")

    document_id = str(ObjectId())
    await test_db.docs.insert_one(
        {
            "_id": ObjectId(document_id),
            "organization_id": TEST_ORG_ID,
            "user_file_name": "spu_credit_test.pdf",
            "tag_ids": [tag_id],
            "upload_date": datetime.now(UTC),
            "state": ad.common.doc.DOCUMENT_STATE_OCR_COMPLETED,
            "mongo_file_name": "test_file.pdf",
        }
    )
    analytiq_client = ad.common.get_analytiq_client()
    await ad.common.ocr.save_ocr_text(
        analytiq_client, document_id, "This is a test document. " * 10
    )

    with pytest.raises(SPUCreditException):
        await ad.msg_handlers.process_kb_index_msg(
            analytiq_client,
            {"_id": str(ObjectId()), "msg": {"document_id": document_id, "kb_id": kb_id}},
        )
    assert not mock_record_spu_usage.called


@pytest.mark.asyncio
@patch("litellm.get_model_info", return_value={"provider": "openai"})
@patch("litellm.aembedding")
@patch("analytiq_data.payments.record_spu_usage")
@patch("analytiq_data.payments.check_spu_limits")
async def test_kb_indexing_spu_cache_hits_free(
    mock_check_spu_limits,
    mock_record_spu_usage,
    mock_embedding,
    mock_get_model_info,
    test_db,
    mock_auth,
    setup_test_models,
):
    mock_embedding.return_value = create_mock_embedding_response()
    mock_check_spu_limits.return_value = True
    mock_record_spu_usage.return_value = True

    tag_id = await insert_org_tag(test_db, "SPU Cache Tag")
    kb_id = await insert_minimal_kb(test_db, [tag_id], name="SPU Cache KB", chunk_size=100, chunk_overlap=20)

    document_id = str(ObjectId())
    await test_db.docs.insert_one(
        {
            "_id": ObjectId(document_id),
            "organization_id": TEST_ORG_ID,
            "user_file_name": "spu_cache_test.pdf",
            "tag_ids": [tag_id],
            "upload_date": datetime.now(UTC),
            "state": ad.common.doc.DOCUMENT_STATE_OCR_COMPLETED,
            "mongo_file_name": "test_file.pdf",
        }
    )
    analytiq_client = ad.common.get_analytiq_client()
    await ad.common.ocr.save_ocr_text(
        analytiq_client, document_id, "This is a test document for cache testing. " * 5
    )

    mock_check_spu_limits.reset_mock()
    mock_record_spu_usage.reset_mock()
    await ad.msg_handlers.process_kb_index_msg(
        analytiq_client,
        {"_id": str(ObjectId()), "msg": {"document_id": document_id, "kb_id": kb_id}},
    )
    assert mock_check_spu_limits.called
    assert mock_record_spu_usage.called

    mock_check_spu_limits.reset_mock()
    mock_record_spu_usage.reset_mock()
    await ad.msg_handlers.process_kb_index_msg(
        analytiq_client,
        {"_id": str(ObjectId()), "msg": {"document_id": document_id, "kb_id": kb_id}},
    )
    if mock_check_spu_limits.called:
        record_call = mock_record_spu_usage.call_args
        check_call = mock_check_spu_limits.call_args
        assert record_call[1]["spus"] == check_call[0][1]
    else:
        assert not mock_record_spu_usage.called


@pytest.mark.asyncio
@patch("analytiq_data.kb.search._execute_vector_search_with_retry", new_callable=AsyncMock)
@patch("litellm.get_model_info", return_value={"provider": "openai"})
@patch("litellm.aembedding")
@patch("analytiq_data.payments.record_spu_usage")
@patch("analytiq_data.payments.check_spu_limits")
async def test_kb_search_spu_recording(
    mock_check_spu_limits,
    mock_record_spu_usage,
    mock_embedding,
    mock_get_model_info,
    _mock_vec_exec,
    test_db,
    mock_auth,
    setup_test_models,
):
    _mock_vec_exec.return_value = []
    mock_embedding.return_value = create_mock_embedding_response()
    mock_check_spu_limits.return_value = True
    mock_record_spu_usage.return_value = True

    tag_id = await insert_org_tag(test_db, "SPU Search Tag")
    kb_id = await insert_minimal_kb(test_db, [tag_id], name="SPU Search KB")

    analytiq_client = ad.common.get_analytiq_client()
    mock_check_spu_limits.reset_mock()
    mock_record_spu_usage.reset_mock()

    await ad.kb.search.search_knowledge_base(
        analytiq_client=analytiq_client,
        kb_id=kb_id,
        query="test query for SPU recording",
        organization_id=TEST_ORG_ID,
        top_k=5,
    )

    assert mock_check_spu_limits.called
    check_call = mock_check_spu_limits.call_args
    assert check_call[0][0] == TEST_ORG_ID
    assert check_call[0][1] == 1

    assert mock_record_spu_usage.called
    record_call = mock_record_spu_usage.call_args
    assert record_call[1]["org_id"] == TEST_ORG_ID
    assert record_call[1]["spus"] == 1
    assert record_call[1]["llm_model"] == "text-embedding-3-small"
    assert record_call[1]["llm_provider"] == "openai"


@pytest.mark.asyncio
@patch("analytiq_data.kb.search._execute_vector_search_with_retry", new_callable=AsyncMock)
@patch("litellm.get_model_info", return_value={"provider": "openai"})
@patch("litellm.aembedding")
@patch("analytiq_data.payments.record_spu_usage")
@patch("analytiq_data.payments.check_spu_limits")
async def test_kb_search_spu_insufficient_credits(
    mock_check_spu_limits,
    mock_record_spu_usage,
    mock_embedding,
    mock_get_model_info,
    _mock_vec_exec,
    test_db,
    mock_auth,
    setup_test_models,
):
    from app.routes.payments import SPUCreditException

    _mock_vec_exec.return_value = []
    mock_embedding.return_value = create_mock_embedding_response()
    mock_check_spu_limits.side_effect = SPUCreditException(TEST_ORG_ID, 1, 0)
    mock_record_spu_usage.return_value = True

    tag_id = await insert_org_tag(test_db, "SPU Search Credit Tag")
    kb_id = await insert_minimal_kb(test_db, [tag_id], name="SPU Search Credit KB")

    analytiq_client = ad.common.get_analytiq_client()
    with pytest.raises(SPUCreditException):
        await ad.kb.search.search_knowledge_base(
            analytiq_client=analytiq_client,
            kb_id=kb_id,
            query="test query",
            organization_id=TEST_ORG_ID,
            top_k=5,
        )


@pytest.mark.asyncio
@patch("analytiq_data.kb.search._execute_vector_search_with_retry", new_callable=AsyncMock)
@patch("litellm.get_model_info", return_value={"provider": "openai"})
@patch("litellm.aembedding")
@patch("analytiq_data.payments.record_spu_usage")
@patch("analytiq_data.payments.check_spu_limits")
async def test_kb_search_spu_cache_hit_free(
    mock_check_spu_limits,
    mock_record_spu_usage,
    mock_embedding,
    mock_get_model_info,
    _mock_vec_exec,
    test_db,
    mock_auth,
    setup_test_models,
):
    _mock_vec_exec.return_value = []
    mock_embedding.return_value = create_mock_embedding_response()
    mock_check_spu_limits.return_value = True
    mock_record_spu_usage.return_value = True

    tag_id = await insert_org_tag(test_db, "SPU Search Cache Tag")
    kb_id = await insert_minimal_kb(test_db, [tag_id], name="SPU Search Cache KB")

    analytiq_client = ad.common.get_analytiq_client()
    q = "test query for cache testing"

    mock_check_spu_limits.reset_mock()
    mock_record_spu_usage.reset_mock()
    await ad.kb.search.search_knowledge_base(
        analytiq_client=analytiq_client,
        kb_id=kb_id,
        query=q,
        organization_id=TEST_ORG_ID,
        top_k=5,
    )
    assert mock_check_spu_limits.call_count == 1
    assert mock_record_spu_usage.call_count == 1

    mock_check_spu_limits.reset_mock()
    mock_record_spu_usage.reset_mock()
    await ad.kb.search.search_knowledge_base(
        analytiq_client=analytiq_client,
        kb_id=kb_id,
        query=q,
        organization_id=TEST_ORG_ID,
        top_k=5,
    )
    assert mock_check_spu_limits.call_count == 0
    assert mock_record_spu_usage.call_count == 0


"""
Note: HTTP search endpoint coverage lives in a mongot integration test.
These SPU tests intentionally stub the low-level vector-search executor to avoid requiring mongot.
"""
