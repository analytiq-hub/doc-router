"""Tests for bulk OCR analyze and upload OCR policy."""

import pytest
from bson import ObjectId
from datetime import datetime, UTC

import analytiq_data as ad
from analytiq_data.ocr.bulk_analyze import _needs_ocr_run, bulk_analyze_ocr_executions
from analytiq_data.ocr.ocr_config import OrgOcrConfig, current_ocr_config_fingerprint, ocr_blob_metadata
from analytiq_data.ocr.upload_policy import resolve_upload_pipeline_policy
from tests.conftest_utils import TEST_ORG_ID, client, get_auth_headers


async def _insert_pdf_doc(test_db, *, name: str, tag_ids: list[str] | None = None, state: str = "uploaded"):
    doc_id = ObjectId()
    await test_db.docs.insert_one({
        "_id": doc_id,
        "organization_id": TEST_ORG_ID,
        "user_file_name": name,
        "mongo_file_name": f"{doc_id}.pdf",
        "pdf_file_name": f"{doc_id}.pdf",
        "document_id": str(doc_id),
        "upload_date": datetime.now(UTC),
        "uploaded_by": "test",
        "state": state,
        "tag_ids": tag_ids or [],
        "metadata": {},
    })
    return str(doc_id)


async def _insert_ocr_text_blob(test_db, document_id: str, metadata: dict):
    await test_db["ocr.files"].insert_one({
        "filename": f"{document_id}_text",
        "metadata": metadata,
        "uploadDate": datetime.now(UTC),
        "length": 10,
        "chunkSize": 261120,
    })


@pytest.mark.asyncio
async def test_current_ocr_config_fingerprint_stable():
    cfg = OrgOcrConfig(mode="textract", textract={"feature_types": ["TABLES"]})
    assert current_ocr_config_fingerprint(cfg) == current_ocr_config_fingerprint(cfg)


@pytest.mark.asyncio
async def test_bulk_analyze_ocr_missing(test_db, mock_auth, setup_test_models):
    analytiq_client = ad.common.get_analytiq_client()
    tag_id = str(ObjectId())
    doc_with = await _insert_pdf_doc(test_db, name="has.pdf", tag_ids=[tag_id])
    doc_without = await _insert_pdf_doc(test_db, name="missing.pdf", tag_ids=[tag_id])
    cfg = OrgOcrConfig()
    await _insert_ocr_text_blob(test_db, doc_with, ocr_blob_metadata(cfg))

    result = await bulk_analyze_ocr_executions(
        analytiq_client,
        TEST_ORG_ID,
        "missing",
        tag_ids=[tag_id],
    )
    ids = {row["document_id"] for row in result["executions"]}
    assert doc_without in ids
    assert doc_with not in ids


@pytest.mark.asyncio
async def test_bulk_analyze_ocr_outdated(test_db, mock_auth, setup_test_models):
    analytiq_client = ad.common.get_analytiq_client()
    tag_id = str(ObjectId())
    doc_old = await _insert_pdf_doc(test_db, name="old.pdf", tag_ids=[tag_id])
    doc_current = await _insert_pdf_doc(test_db, name="current.pdf", tag_ids=[tag_id])

    old_cfg = OrgOcrConfig(mode="textract", textract={"feature_types": ["TABLES"]})
    current_cfg = OrgOcrConfig(mode="textract", textract={"feature_types": ["TABLES", "FORMS"]})
    await _insert_ocr_text_blob(test_db, doc_old, ocr_blob_metadata(old_cfg))
    await _insert_ocr_text_blob(test_db, doc_current, ocr_blob_metadata(current_cfg))

    await test_db.organizations.update_one(
        {"_id": ObjectId(TEST_ORG_ID)},
        {"$set": {"ocr_config": current_cfg.model_dump()}},
    )

    result = await bulk_analyze_ocr_executions(
        analytiq_client,
        TEST_ORG_ID,
        "outdated",
        tag_ids=[tag_id],
    )
    ids = {row["document_id"] for row in result["executions"]}
    assert doc_old in ids
    assert doc_current not in ids


@pytest.mark.asyncio
async def test_bulk_analyze_ocr_all(test_db, mock_auth, setup_test_models):
    analytiq_client = ad.common.get_analytiq_client()
    tag_id = str(ObjectId())
    doc_a = await _insert_pdf_doc(test_db, name="a.pdf", tag_ids=[tag_id])
    doc_b = await _insert_pdf_doc(test_db, name="b.pdf", tag_ids=[tag_id])
    cfg = OrgOcrConfig()
    await _insert_ocr_text_blob(test_db, doc_a, ocr_blob_metadata(cfg))

    result = await bulk_analyze_ocr_executions(
        analytiq_client,
        TEST_ORG_ID,
        "all",
        tag_ids=[tag_id],
    )
    ids = {row["document_id"] for row in result["executions"]}
    assert ids == {doc_a, doc_b}


@pytest.mark.asyncio
async def test_bulk_analyze_ocr_excludes_non_ocr_types(test_db, mock_auth, setup_test_models):
    analytiq_client = ad.common.get_analytiq_client()
    tag_id = str(ObjectId())
    await _insert_pdf_doc(test_db, name="note.txt", tag_ids=[tag_id])

    result = await bulk_analyze_ocr_executions(
        analytiq_client,
        TEST_ORG_ID,
        "all",
        tag_ids=[tag_id],
    )
    assert result["total_executions"] == 0


@pytest.mark.asyncio
async def test_bulk_analyze_ocr_api(test_db, mock_auth, setup_test_models):
    tag_id = str(ObjectId())
    await _insert_pdf_doc(test_db, name="api.pdf", tag_ids=[tag_id])

    response = client.post(
        f"/v0/orgs/{TEST_ORG_ID}/ocr/bulk-analyze",
        headers=get_auth_headers(),
        json={"mode": "missing", "document_filters": {"tag_ids": [tag_id]}},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["total_executions"] == 1


@pytest.mark.asyncio
async def test_upload_policy_skips_ocr_for_flow_only(test_db, mock_auth, setup_test_models):
    analytiq_client = ad.common.get_analytiq_client()
    await test_db.organizations.update_one(
        {"_id": ObjectId(TEST_ORG_ID)},
        {"$set": {"default_prompt_enabled": False}},
    )
    policy = await resolve_upload_pipeline_policy(
        analytiq_client,
        TEST_ORG_ID,
        [],
        "large.pdf",
        cache={},
    )
    assert policy.needs_ocr is False
    assert policy.needs_llm is False
    assert policy.needs_kb is False


@pytest.mark.asyncio
async def test_upload_policy_needs_ocr_for_default_prompt(test_db, mock_auth, setup_test_models):
    analytiq_client = ad.common.get_analytiq_client()
    await test_db.organizations.update_one(
        {"_id": ObjectId(TEST_ORG_ID)},
        {"$set": {"default_prompt_enabled": True}},
    )
    policy = await resolve_upload_pipeline_policy(
        analytiq_client,
        TEST_ORG_ID,
        [],
        "doc.pdf",
        cache={},
    )
    assert policy.needs_ocr is True


@pytest.mark.asyncio
async def test_upload_policy_needs_ocr_for_kb_tags(test_db, mock_auth, setup_test_models):
    analytiq_client = ad.common.get_analytiq_client()
    tag_id = str(ObjectId())
    await test_db.organizations.update_one(
        {"_id": ObjectId(TEST_ORG_ID)},
        {"$set": {"default_prompt_enabled": False}},
    )
    await test_db.knowledge_bases.insert_one({
        "_id": ObjectId(),
        "organization_id": TEST_ORG_ID,
        "name": "KB",
        "status": "active",
        "tag_ids": [tag_id],
        "chunker_type": "recursive",
        "chunk_size": 100,
        "chunk_overlap": 10,
    })
    policy = await resolve_upload_pipeline_policy(
        analytiq_client,
        TEST_ORG_ID,
        [tag_id],
        "doc.pdf",
        cache={},
    )
    assert policy.needs_ocr is True
    assert policy.needs_kb is True


def test_needs_ocr_run_modes():
    cfg = OrgOcrConfig()
    assert _needs_ocr_run("all", has_ocr=True, ocr_failed=False, stored_metadata={}, current_cfg=cfg)[0]
    assert _needs_ocr_run("missing", has_ocr=False, ocr_failed=False, stored_metadata=None, current_cfg=cfg)[0]
    assert not _needs_ocr_run(
        "missing", has_ocr=True, ocr_failed=False, stored_metadata={}, current_cfg=cfg
    )[0]
