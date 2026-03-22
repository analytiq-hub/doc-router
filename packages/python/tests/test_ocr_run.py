"""Tests for POST /v0/orgs/{org_id}/ocr/run/{doc_id} — all parameter variants."""
import base64
import os
import pytest
from bson import ObjectId
from datetime import datetime, UTC
from unittest.mock import patch

import analytiq_data as ad
from tests.conftest_utils import client, get_auth_headers, TEST_ORG_ID
from tests.conftest_llm import (
    mock_run_textract,
    mock_litellm_acreate_file_with_retry,
    mock_litellm_acompletion_with_retry,
)

# Minimal valid PDF used across tests
_PDF_BYTES = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF\n"
_PDF_B64 = f"data:application/pdf;base64,{base64.b64encode(_PDF_BYTES).decode()}"


def _upload_pdf(name="test.pdf"):
    resp = client.post(
        f"/v0/orgs/{TEST_ORG_ID}/documents",
        json={"documents": [{"name": name, "content": _PDF_B64, "tag_ids": []}]},
        headers=get_auth_headers(),
    )
    assert resp.status_code == 200, f"Upload failed: {resp.text}"
    return resp.json()["documents"][0]["document_id"]


def _run_url(doc_id):
    return f"/v0/orgs/{TEST_ORG_ID}/ocr/run/{doc_id}"


# ---------------------------------------------------------------------------
# 404 — document does not exist
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_run_ocr_document_not_found(test_db, mock_auth):
    resp = client.post(_run_url(str(ObjectId())), headers=get_auth_headers())
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# 400 — file type does not support OCR (.txt)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_run_ocr_unsupported_file_type(test_db, mock_auth):
    # Insert a .txt document directly — no need to go through the upload pipeline
    db = ad.common.get_async_db()
    doc_id = str(ObjectId())
    await db.docs.insert_one({
        "_id": ObjectId(doc_id),
        "organization_id": TEST_ORG_ID,
        "user_file_name": "data.txt",
        "state": "uploaded",
        "created_at": datetime.now(UTC),
    })

    resp = client.post(_run_url(doc_id), headers=get_auth_headers())
    assert resp.status_code == 400
    assert "OCR" in resp.json()["detail"]


# ---------------------------------------------------------------------------
# 200 — default params (force=True, ocr_only=False)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_run_ocr_default_params_queues_message(test_db, mock_auth):
    doc_id = _upload_pdf()

    resp = client.post(_run_url(doc_id), headers=get_auth_headers())
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "queued"
    assert body["document_id"] == doc_id

    # Document state should be reset to "uploaded"
    db = ad.common.get_async_db()
    doc = await db.docs.find_one({"_id": ObjectId(doc_id)})
    assert doc["state"] == "uploaded"

    # OCR queue should contain a message for this document with force=True, ocr_only=False
    msgs = await db["queues.ocr"].find({"msg.document_id": doc_id}).to_list(None)
    assert len(msgs) >= 1
    msg_payload = msgs[-1]["msg"]
    assert msg_payload.get("force") is True
    assert msg_payload.get("ocr_only") is False


# ---------------------------------------------------------------------------
# force=False — OCR queued without force flag
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_run_ocr_force_false(test_db, mock_auth):
    doc_id = _upload_pdf()

    resp = client.post(_run_url(doc_id), params={"force": "false"}, headers=get_auth_headers())
    assert resp.status_code == 200

    db = ad.common.get_async_db()
    msgs = await db["queues.ocr"].find({"msg.document_id": doc_id}).to_list(None)
    assert len(msgs) >= 1
    assert msgs[-1]["msg"].get("force") is False


# ---------------------------------------------------------------------------
# ocr_only=True — not reset to uploaded (LLM path); set ocr_processing for polling
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_run_ocr_ocr_only_sets_ocr_processing_not_uploaded(test_db, mock_auth):
    doc_id = _upload_pdf()

    db = ad.common.get_async_db()
    await db.docs.update_one(
        {"_id": ObjectId(doc_id)},
        {"$set": {"state": ad.common.doc.DOCUMENT_STATE_OCR_COMPLETED}},
    )

    resp = client.post(_run_url(doc_id), params={"ocr_only": "true"}, headers=get_auth_headers())
    assert resp.status_code == 200

    doc = await db.docs.find_one({"_id": ObjectId(doc_id)})
    assert doc["state"] == ad.common.doc.DOCUMENT_STATE_OCR_PROCESSING

    msgs = await db["queues.ocr"].find({"msg.document_id": doc_id}).to_list(None)
    assert msgs[-1]["msg"].get("ocr_only") is True


@pytest.mark.asyncio
async def test_run_ocr_ocr_only_from_failed_sets_ocr_processing(test_db, mock_auth):
    doc_id = _upload_pdf()

    db = ad.common.get_async_db()
    await db.docs.update_one(
        {"_id": ObjectId(doc_id)},
        {"$set": {"state": ad.common.doc.DOCUMENT_STATE_OCR_FAILED}},
    )

    resp = client.post(_run_url(doc_id), params={"ocr_only": "true"}, headers=get_auth_headers())
    assert resp.status_code == 200

    doc = await db.docs.find_one({"_id": ObjectId(doc_id)})
    assert doc["state"] == ad.common.doc.DOCUMENT_STATE_OCR_PROCESSING


# ---------------------------------------------------------------------------
# End-to-end: ocr_only=False — LLM message is enqueued after OCR completes
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_run_ocr_pipeline_queues_llm_when_not_ocr_only(test_db, mock_auth, setup_test_models):
    doc_id = _upload_pdf()

    with patch("analytiq_data.aws.textract.run_textract", new=mock_run_textract):
        # Initial OCR run to populate state
        analytiq_client = ad.common.get_analytiq_client()
        init_msg = {"_id": str(ObjectId()), "msg": {"document_id": doc_id}, "attempts": 1}
        await ad.msg_handlers.process_ocr_msg(analytiq_client, init_msg)

    # Drain LLM queue from initial run
    db = ad.common.get_async_db()
    await db["queues.llm"].delete_many({})

    # Trigger rerun with default params (ocr_only=False)
    resp = client.post(_run_url(doc_id), headers=get_auth_headers())
    assert resp.status_code == 200

    # Process the new OCR message inline
    with patch("analytiq_data.aws.textract.run_textract", new=mock_run_textract):
        ocr_msgs = await db["queues.ocr"].find({"msg.document_id": doc_id}).sort("_id", -1).limit(1).to_list(None)
        assert ocr_msgs, "Expected an OCR queue message"
        await ad.msg_handlers.process_ocr_msg(analytiq_client, ocr_msgs[0], force=True, ocr_only=False)

    # LLM queue should now have a message for this doc with force=True
    llm_msgs = await db["queues.llm"].find({"msg.document_id": doc_id}).to_list(None)
    assert len(llm_msgs) >= 1, "LLM should be re-queued after OCR rerun with ocr_only=False"
    assert llm_msgs[-1]["msg"].get("force") is True


# ---------------------------------------------------------------------------
# End-to-end: ocr_only=True — LLM is NOT enqueued after OCR completes
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_run_ocr_pipeline_no_llm_when_ocr_only(test_db, mock_auth, setup_test_models):
    doc_id = _upload_pdf()

    with patch("analytiq_data.aws.textract.run_textract", new=mock_run_textract):
        analytiq_client = ad.common.get_analytiq_client()
        init_msg = {"_id": str(ObjectId()), "msg": {"document_id": doc_id}, "attempts": 1}
        await ad.msg_handlers.process_ocr_msg(analytiq_client, init_msg)

    db = ad.common.get_async_db()
    await db["queues.llm"].delete_many({})

    resp = client.post(_run_url(doc_id), params={"ocr_only": "true"}, headers=get_auth_headers())
    assert resp.status_code == 200

    with patch("analytiq_data.aws.textract.run_textract", new=mock_run_textract):
        ocr_msgs = await db["queues.ocr"].find({"msg.document_id": doc_id}).sort("_id", -1).limit(1).to_list(None)
        await ad.msg_handlers.process_ocr_msg(analytiq_client, ocr_msgs[0], force=True, ocr_only=True)

    llm_msgs = await db["queues.llm"].find({"msg.document_id": doc_id}).to_list(None)
    assert len(llm_msgs) == 0, "LLM should NOT be queued when ocr_only=True"


# ---------------------------------------------------------------------------
# End-to-end: force=True propagates to LLM — LLM skips cache
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_run_ocr_force_propagates_to_llm(test_db, mock_auth, setup_test_models):
    doc_id = _upload_pdf()

    analytiq_client = ad.common.get_analytiq_client()
    db = ad.common.get_async_db()

    with (
        patch("analytiq_data.aws.textract.run_textract", new=mock_run_textract),
        patch("analytiq_data.llm.llm._litellm_acompletion_with_retry", new=mock_litellm_acompletion_with_retry),
        patch("analytiq_data.llm.llm._litellm_acreate_file_with_retry", new=mock_litellm_acreate_file_with_retry),
        patch("litellm.completion_cost", return_value=0.001),
        patch("litellm.supports_response_schema", return_value=True),
        patch("litellm.utils.supports_pdf_input", return_value=True),
    ):
        # Run initial OCR + LLM to populate the cache
        init_msg = {"_id": str(ObjectId()), "msg": {"document_id": doc_id}, "attempts": 1}
        await ad.msg_handlers.process_ocr_msg(analytiq_client, init_msg)

        llm_msgs = await db["queues.llm"].find({"msg.document_id": doc_id}).to_list(None)
        for m in llm_msgs:
            await ad.msg_handlers.process_llm_msg(analytiq_client, m)

        # Verify cache is populated
        cached = await ad.llm.get_llm_result(analytiq_client, doc_id, "default")
        assert cached is not None, "LLM cache should be populated after initial run"

        await db["queues.llm"].delete_many({})

        # Rerun OCR with force=True (default), ocr_only=False
        resp = client.post(_run_url(doc_id), headers=get_auth_headers())
        assert resp.status_code == 200

        # Process the new OCR message inline
        ocr_msgs = await db["queues.ocr"].find({"msg.document_id": doc_id}).sort("_id", -1).limit(1).to_list(None)
        await ad.msg_handlers.process_ocr_msg(analytiq_client, ocr_msgs[0], force=True, ocr_only=False)

        # Verify the LLM queue message has force=True
        llm_msgs = await db["queues.llm"].find({"msg.document_id": doc_id}).to_list(None)
        assert len(llm_msgs) >= 1
        assert llm_msgs[-1]["msg"].get("force") is True, "force=True must be propagated to LLM queue message"

        # Process the forced LLM message — should re-run, not use cache
        llm_call_count = 0
        original_mock = mock_litellm_acompletion_with_retry

        async def counting_mock(*args, **kwargs):
            nonlocal llm_call_count
            llm_call_count += 1
            return await original_mock(*args, **kwargs)

        with patch("analytiq_data.llm.llm._litellm_acompletion_with_retry", new=counting_mock):
            await ad.msg_handlers.process_llm_msg(analytiq_client, llm_msgs[-1], force=True)

        assert llm_call_count > 0, "LLM should have been called (not served from cache) when force=True"
