"""Unit tests for prompt content and KB system_prompt helpers."""

import os

import pytest
from bson import ObjectId

import analytiq_data as ad

assert os.environ["ENV"] == "pytest"


@pytest.mark.asyncio
async def test_get_prompt_content_default_prompt_unchanged(test_db, mock_auth):
    analytiq_client = ad.common.get_analytiq_client()
    content = await ad.common.get_prompt_content(analytiq_client, "default")
    assert "document_type" in content
    assert "invoice" in content.lower() or "document" in content.lower()


@pytest.mark.asyncio
async def test_get_prompt_content_no_kb_id_returns_raw_content(test_db, mock_auth):
    analytiq_client = ad.common.get_analytiq_client()
    db = analytiq_client.mongodb_async[analytiq_client.env]
    rev_id = ObjectId()
    await db.prompt_revisions.insert_one(
        {
            "_id": rev_id,
            "content": "Hello extraction",
            "prompt_id": str(ObjectId()),
            "prompt_version": 1,
            "organization_id": "x",
        }
    )
    out = await ad.common.get_prompt_content(analytiq_client, str(rev_id))
    assert out == "Hello extraction"


@pytest.mark.asyncio
async def test_get_prompt_content_with_kb_id_returns_raw_content_only(test_db, mock_auth):
    analytiq_client = ad.common.get_analytiq_client()
    db = analytiq_client.mongodb_async[analytiq_client.env]
    kb_oid = ObjectId()
    await db.knowledge_bases.insert_one(
        {
            "_id": kb_oid,
            "organization_id": "org1",
            "name": "KB",
            "system_prompt": "You are an invoice expert.",
        }
    )
    rev_id = ObjectId()
    await db.prompt_revisions.insert_one(
        {
            "_id": rev_id,
            "content": "Extract line items.",
            "prompt_id": str(ObjectId()),
            "prompt_version": 1,
            "organization_id": "org1",
            "kb_id": str(kb_oid),
        }
    )
    out = await ad.common.get_prompt_content(analytiq_client, str(rev_id))
    assert out == "Extract line items."


@pytest.mark.asyncio
async def test_get_prompt_kb_system_prompt_returns_kb_text(test_db, mock_auth):
    analytiq_client = ad.common.get_analytiq_client()
    db = analytiq_client.mongodb_async[analytiq_client.env]
    kb_oid = ObjectId()
    await db.knowledge_bases.insert_one(
        {
            "_id": kb_oid,
            "organization_id": "org1",
            "name": "KB",
            "system_prompt": "You are an invoice expert.",
        }
    )
    rev_id = ObjectId()
    await db.prompt_revisions.insert_one(
        {
            "_id": rev_id,
            "content": "Extract line items.",
            "prompt_id": str(ObjectId()),
            "prompt_version": 1,
            "organization_id": "org1",
            "kb_id": str(kb_oid),
        }
    )
    out = await ad.common.get_prompt_kb_system_prompt(analytiq_client, str(rev_id))
    assert out == "You are an invoice expert."


@pytest.mark.asyncio
async def test_get_prompt_kb_system_prompt_no_kb_id_returns_empty(test_db, mock_auth):
    analytiq_client = ad.common.get_analytiq_client()
    db = analytiq_client.mongodb_async[analytiq_client.env]
    rev_id = ObjectId()
    await db.prompt_revisions.insert_one(
        {
            "_id": rev_id,
            "content": "Hello extraction",
            "prompt_id": str(ObjectId()),
            "prompt_version": 1,
            "organization_id": "x",
        }
    )
    out = await ad.common.get_prompt_kb_system_prompt(analytiq_client, str(rev_id))
    assert out == ""


@pytest.mark.asyncio
async def test_get_prompt_kb_system_prompt_default_prompt_returns_empty(test_db, mock_auth):
    analytiq_client = ad.common.get_analytiq_client()
    out = await ad.common.get_prompt_kb_system_prompt(analytiq_client, "default")
    assert out == ""


@pytest.mark.asyncio
async def test_get_kb_system_prompt_missing_kb_returns_empty(test_db, mock_auth):
    analytiq_client = ad.common.get_analytiq_client()
    out = await ad.common.get_kb_system_prompt(analytiq_client, str(ObjectId()))
    assert out == ""


@pytest.mark.asyncio
async def test_get_prompt_kb_system_prompt_kb_not_found_returns_empty(test_db, mock_auth):
    analytiq_client = ad.common.get_analytiq_client()
    db = analytiq_client.mongodb_async[analytiq_client.env]
    missing_kb_id = str(ObjectId())
    rev_id = ObjectId()
    await db.prompt_revisions.insert_one(
        {
            "_id": rev_id,
            "content": "Only this",
            "prompt_id": str(ObjectId()),
            "prompt_version": 1,
            "organization_id": "org1",
            "kb_id": missing_kb_id,
        }
    )
    out = await ad.common.get_prompt_kb_system_prompt(analytiq_client, str(rev_id))
    assert out == ""


@pytest.mark.asyncio
async def test_get_prompt_kb_system_prompt_empty_system_prompt_returns_empty(test_db, mock_auth):
    analytiq_client = ad.common.get_analytiq_client()
    db = analytiq_client.mongodb_async[analytiq_client.env]
    kb_oid = ObjectId()
    await db.knowledge_bases.insert_one(
        {
            "_id": kb_oid,
            "organization_id": "org1",
            "name": "KB",
            "system_prompt": "   ",
        }
    )
    rev_id = ObjectId()
    await db.prompt_revisions.insert_one(
        {
            "_id": rev_id,
            "content": "Body only",
            "prompt_id": str(ObjectId()),
            "prompt_version": 1,
            "organization_id": "org1",
            "kb_id": str(kb_oid),
        }
    )
    out = await ad.common.get_prompt_kb_system_prompt(analytiq_client, str(rev_id))
    assert out == ""


@pytest.mark.asyncio
async def test_get_prompt_kb_system_prompt_missing_system_prompt_field_returns_empty(test_db, mock_auth):
    analytiq_client = ad.common.get_analytiq_client()
    db = analytiq_client.mongodb_async[analytiq_client.env]
    kb_oid = ObjectId()
    await db.knowledge_bases.insert_one(
        {
            "_id": kb_oid,
            "organization_id": "org1",
            "name": "KB",
        }
    )
    rev_id = ObjectId()
    await db.prompt_revisions.insert_one(
        {
            "_id": rev_id,
            "content": "Legacy kb doc",
            "prompt_id": str(ObjectId()),
            "prompt_version": 1,
            "organization_id": "org1",
            "kb_id": str(kb_oid),
        }
    )
    out = await ad.common.get_prompt_kb_system_prompt(analytiq_client, str(rev_id))
    assert out == ""
