import pytest
from bson import ObjectId
from unittest.mock import AsyncMock
from datetime import datetime, UTC

import analytiq_data as ad
from analytiq_data.agent.tools.tag_tools import create_tag, get_tag, list_tags, update_tag, delete_tag
from analytiq_data.agent.tools.schema_tools import (
    create_schema,
    get_schema,
    list_schemas,
    update_schema,
    delete_schema,
    validate_schema,
    validate_against_schema,
)
from analytiq_data.agent.tools.prompt_tools import create_prompt, get_prompt, list_prompts, update_prompt, delete_prompt
from analytiq_data.agent.tools.document_tools import list_documents, update_document, delete_document
from analytiq_data.agent.tools.extraction_tools import (
    get_ocr_text,
    run_extraction,
    get_extraction_result,
    update_extraction_field,
)
from analytiq_data.agent.tools.help_tools import help_schemas, help_prompts


def _ctx(*, organization_id: str, analytiq_client, **extra) -> dict:
    return {
        "organization_id": organization_id,
        "analytiq_client": analytiq_client,
        **extra,
    }


@pytest.mark.asyncio
async def test_tag_tools_create_get_list_update_delete_default_color(org_and_users, test_db):
    analytiq_client = ad.common.get_analytiq_client()
    org_id = org_and_users["org_id"]
    context = _ctx(organization_id=org_id, analytiq_client=analytiq_client)

    # Create: omit/None color should default.
    created = await create_tag(context, {"name": "resume_comparison", "color": None, "description": "d"})
    assert "tag_id" in created
    tag_id = created["tag_id"]

    got = await get_tag(context, {"tag_id": tag_id})
    assert got["id"] == tag_id
    assert got["color"] and got["color"].startswith("#")

    listed = await list_tags(context, {"limit": 10, "skip": 0})
    assert any(t["id"] == tag_id for t in listed["tags"])

    # Update: explicitly provide null/empty color -> default.
    await update_tag(context, {"tag_id": tag_id, "color": ""})
    got2 = await get_tag(context, {"tag_id": tag_id})
    assert got2["color"] and got2["color"].startswith("#")

    deleted = await delete_tag(context, {"tag_id": tag_id})
    assert "message" in deleted

    missing = await get_tag(context, {"tag_id": tag_id})
    assert "error" in missing


@pytest.mark.asyncio
async def test_schema_tools_lifecycle_and_validation(org_and_users, test_db):
    analytiq_client = ad.common.get_analytiq_client()
    org_id = org_and_users["org_id"]
    context = _ctx(organization_id=org_id, analytiq_client=analytiq_client)

    response_format = {
        "type": "json_schema",
        "json_schema": {
            "name": "TestSchema",
            "schema": {
                "type": "object",
                "properties": {"foo": {"type": "string", "description": "Foo"}},
                "required": ["foo"],
                "additionalProperties": False,
            },
            "strict": True,
        },
    }

    # validate_schema (no save performed here)
    valid_res = await validate_schema(context, {"schema": response_format})
    assert valid_res.get("valid") is True

    # Create
    created = await create_schema(context, {"name": "S1", "response_format": response_format})
    assert "schema_revid" in created
    assert "schema_id" in created
    schema_id = created["schema_id"]
    schema_revid = created["schema_revid"]

    # List + Get
    listed = await list_schemas(context, {"limit": 10, "skip": 0})
    assert any(s["schema_revid"] == schema_revid for s in listed["schemas"])
    got = await get_schema(context, {"schema_revid": schema_revid})
    assert got["schema_revid"] == schema_revid

    # validate_against_schema
    valid_data = await validate_against_schema(context, {"schema_revid": schema_revid, "data": {"foo": "bar"}})
    assert valid_data.get("valid") is True

    # Update (creates new revision)
    updated = await update_schema(context, {"schema_id": schema_id, "name": "S1-updated"})
    assert "schema_revid" in updated
    updated_revid = updated["schema_revid"]

    got_updated = await get_schema(context, {"schema_revid": updated_revid})
    assert got_updated["name"] == "S1-updated"

    # Delete
    deleted = await delete_schema(context, {"schema_id": schema_id})
    assert "message" in deleted


@pytest.mark.asyncio
async def test_prompt_tools_lifecycle(org_and_users, test_db):
    analytiq_client = ad.common.get_analytiq_client()
    org_id = org_and_users["org_id"]
    context = _ctx(organization_id=org_id, analytiq_client=analytiq_client)

    created = await create_prompt(context, {"name": "P1", "content": "Hello"})
    assert "prompt_revid" in created
    prompt_revid = created["prompt_revid"]
    prompt_id = created["prompt_id"]

    got = await get_prompt(context, {"prompt_revid": prompt_revid})
    assert got["prompt_revid"] == prompt_revid
    assert got["name"] == "P1"

    listed = await list_prompts(context, {"limit": 10, "skip": 0})
    assert any(p["prompt_revid"] == prompt_revid for p in listed["prompts"])

    updated = await update_prompt(context, {"prompt_id": prompt_id, "content": "Hello updated"})
    assert "prompt_revid" in updated
    updated_revid = updated["prompt_revid"]

    got2 = await get_prompt(context, {"prompt_revid": updated_revid})
    assert got2["content"] == "Hello updated"

    deleted = await delete_prompt(context, {"prompt_id": prompt_id})
    assert "message" in deleted


@pytest.mark.asyncio
async def test_document_tools_list_update_delete_with_mocks(org_and_users, test_db, monkeypatch):
    analytiq_client = ad.common.get_analytiq_client()
    org_id = org_and_users["org_id"]
    context = _ctx(organization_id=org_id, analytiq_client=analytiq_client)

    # list_documents: patch ad.common.list_docs to keep the test focused.
    doc_id = ObjectId()
    docs_payload = [
        {
            "_id": doc_id,
            "user_file_name": "doc-a.pdf",
            "upload_date": datetime.now(UTC),
            "uploaded_by": "u1",
            "state": "ready",
            "tag_ids": [],
            "metadata": {"k": "v"},
        }
    ]
    monkeypatch.setattr(ad.common, "list_docs", AsyncMock(return_value=(docs_payload, 1)))

    listed = await list_documents(context, {"limit": 10, "skip": 0})
    assert listed["total_count"] == 1
    assert listed["documents"][0]["id"] == str(doc_id)

    # update_document: use real DB insert, avoid queue re-index by not passing tag_ids.
    update_doc_id = ObjectId()
    await test_db.docs.insert_one(
        {
            "_id": update_doc_id,
            "organization_id": org_id,
            "user_file_name": "old-name",
            "tag_ids": [],
            "metadata": {"m": "1"},
        }
    )
    updated = await update_document(
        context,
        {"document_id": str(update_doc_id), "document_name": "new-name"},
    )
    assert updated["document_name"] == "new-name"

    # delete_document: patch file deletion + doc deletion.
    delete_doc_id = ObjectId()
    await test_db.docs.insert_one(
        {
            "_id": delete_doc_id,
            "organization_id": org_id,
            "user_file_name": "to-delete.pdf",
            "mongo_file_name": "mongo_to_delete.pdf",
            "pdf_file_name": "mongo_to_delete.pdf",
        }
    )
    monkeypatch.setattr(ad.common, "delete_file_async", AsyncMock(return_value=None))
    monkeypatch.setattr(ad.common, "delete_doc", AsyncMock(return_value=None))

    deleted = await delete_document(context, {"document_id": str(delete_doc_id)})
    assert deleted["document_id"] == str(delete_doc_id)


@pytest.mark.asyncio
async def test_extraction_tools_with_mocks(org_and_users, test_db, monkeypatch):
    analytiq_client = ad.common.get_analytiq_client()
    org_id = org_and_users["org_id"]
    document_id = "507f1f77bcf86cd799439011"

    # Mock OCR + LLM calls so we don't depend on external services.
    monkeypatch.setattr(ad.ocr, "get_ocr_text", AsyncMock(return_value="OCR TEXT"))
    monkeypatch.setattr(ad.llm, "run_llm", AsyncMock(return_value={"extracted": True}))
    monkeypatch.setattr(
        ad.llm,
        "get_llm_result",
        AsyncMock(return_value={"updated_llm_result": {"hello": "world"}}),
    )
    monkeypatch.setattr(ad.llm, "update_llm_result", AsyncMock(return_value=None))

    context = _ctx(organization_id=org_id, analytiq_client=analytiq_client, document_id=document_id)

    ocr_res = await get_ocr_text(context, {})
    assert ocr_res["text"] == "OCR TEXT"

    run_res = await run_extraction(context, {})
    assert run_res["extraction"]["extracted"] is True
    assert context["working_state"]["extraction"] == {"extracted": True}

    extraction_res = await get_extraction_result(context, {})
    assert extraction_res["extraction"] == {"extracted": True}

    # update_extraction_field updates nested field and persists via update_llm_result.
    context2 = _ctx(organization_id=org_id, analytiq_client=analytiq_client, document_id=document_id)
    # Ensure working_state.prompt_revid is unset so tool uses "default"
    await update_extraction_field(context2, {"path": "a.b", "value": 2})
    assert context2["working_state"]["extraction"]["a"]["b"] == 2


@pytest.mark.asyncio
async def test_help_tools_returns_content(org_and_users, test_db):
    # No DB needed but we keep fixtures consistent so ENV is set.
    context = {"organization_id": org_and_users["org_id"], "analytiq_client": ad.common.get_analytiq_client()}
    res_schemas = await help_schemas(context, {})
    assert "content" in res_schemas and res_schemas["content"]

    res_prompts = await help_prompts(context, {})
    assert "content" in res_prompts and res_prompts["content"]

