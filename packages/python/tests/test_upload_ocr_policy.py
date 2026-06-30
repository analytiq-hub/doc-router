"""Tests for upload skipping OCR enqueue."""

import base64
from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import pytest
from bson import ObjectId

import analytiq_data as ad
from tests.conftest_utils import TEST_ORG_ID, client, get_auth_headers

_MINIMAL_PDF = (
    b"%PDF-1.4\n"
    b"1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
    b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
    b"3 0 obj<</Type/Page/MediaBox[0 0 3 3]>>endobj\n"
    b"trailer<</Root 1 0 R>>\n%%EOF\n"
)


@pytest.mark.asyncio
async def test_upload_skips_ocr_when_not_needed(test_db, mock_auth, setup_test_models):
    await test_db.organizations.update_one(
        {"_id": ObjectId(TEST_ORG_ID)},
        {"$set": {"default_prompt_enabled": False}},
    )
    content = base64.b64encode(_MINIMAL_PDF).decode("ascii")
    with patch.object(ad.queue, "send_msg", new_callable=AsyncMock) as mock_send:
        response = client.post(
            f"/v0/orgs/{TEST_ORG_ID}/documents",
            headers=get_auth_headers(),
            json={
                "documents": [
                    {"name": "flow-only.pdf", "content": content, "tag_ids": [], "metadata": {}},
                ]
            },
        )
    assert response.status_code == 200
    mock_send.assert_not_called()

    doc_id = response.json()["documents"][0]["document_id"]
    doc = await test_db.docs.find_one({"_id": ObjectId(doc_id)})
    assert doc["state"] == ad.common.doc.DOCUMENT_STATE_UPLOADED


@pytest.mark.asyncio
async def test_upload_enqueues_ocr_when_default_prompt(test_db, mock_auth, setup_test_models):
    await test_db.organizations.update_one(
        {"_id": ObjectId(TEST_ORG_ID)},
        {"$set": {"default_prompt_enabled": True}},
    )
    content = base64.b64encode(_MINIMAL_PDF).decode("ascii")
    with patch.object(ad.queue, "send_msg", new_callable=AsyncMock) as mock_send:
        response = client.post(
            f"/v0/orgs/{TEST_ORG_ID}/documents",
            headers=get_auth_headers(),
            json={
                "documents": [
                    {"name": "classic.pdf", "content": content, "tag_ids": [], "metadata": {}},
                ]
            },
        )
    assert response.status_code == 200
    mock_send.assert_called()
    assert mock_send.call_args[0][1] == "ocr"


@pytest.mark.asyncio
async def test_process_llm_msg_fails_when_ocr_required(test_db, mock_auth, setup_test_models):
    await test_db.organizations.update_one(
        {"_id": ObjectId(TEST_ORG_ID)},
        {"$set": {"default_prompt_enabled": True}},
    )
    document_id = str(ObjectId())
    file_key = f"{document_id}.pdf"
    analytiq_client = ad.common.get_analytiq_client()
    await ad.common.save_file_async(
        analytiq_client,
        file_key,
        _MINIMAL_PDF,
        metadata={"type": "application/pdf"},
    )
    await test_db.docs.insert_one(
        {
            "_id": ObjectId(document_id),
            "organization_id": TEST_ORG_ID,
            "document_id": document_id,
            "user_file_name": "needs-ocr.pdf",
            "mongo_file_name": file_key,
            "pdf_file_name": file_key,
            "upload_date": datetime.now(UTC),
            "uploaded_by": "test@example.com",
            "state": ad.common.doc.DOCUMENT_STATE_UPLOADED,
            "tag_ids": [],
            "metadata": {},
        }
    )

    msg_id = str(ObjectId())
    with patch.object(ad.queue, "delete_msg", new_callable=AsyncMock) as mock_delete:
        await ad.msg_handlers.process_llm_msg(
            analytiq_client,
            {"_id": msg_id, "msg": {"document_id": document_id}},
        )
        mock_delete.assert_called_once_with(analytiq_client, "llm", msg_id)

    doc = await test_db.docs.find_one({"_id": ObjectId(document_id)})
    assert doc["state"] == ad.common.doc.DOCUMENT_STATE_LLM_FAILED
