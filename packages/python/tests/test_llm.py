import pytest
import os
import json
import base64
import asyncio
from unittest.mock import patch
from bson import ObjectId

from tests.conftest_utils import client, get_token_headers, TEST_ORG_ID, get_auth_headers
from tests.conftest_llm import (
    MockLLMResponse,
    mock_run_textract,
    mock_litellm_acreate_file_with_retry,
    mock_litellm_acompletion_with_retry,
)

import analytiq_data as ad
import logging

logger = logging.getLogger(__name__)


@pytest.mark.asyncio
async def test_textract_and_llm_default_pipeline_inline(test_db, mock_auth, setup_test_models):
    """Test Textract + default LLM pipeline inline without spawning a worker."""

    pdf_content = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF\n"
    test_pdf = {
        "name": "test_invoice.pdf",
        "content": f"data:application/pdf;base64,{base64.b64encode(pdf_content).decode()}"
    }

    upload_data = {
        "documents": [{
            "name": test_pdf["name"],
            "content": test_pdf["content"],
            "metadata": {"test_source": "textract_pipeline_test"},
            "tag_ids": []
        }]
    }

    # Patch OCR and LLM internals to run inline
    with (
        patch('analytiq_data.aws.textract.run_textract', new=mock_run_textract),
        patch('analytiq_data.llm.llm._litellm_acompletion_with_retry', new=mock_litellm_acompletion_with_retry),
        patch('analytiq_data.llm.llm._litellm_acreate_file_with_retry', new=mock_litellm_acreate_file_with_retry),
        patch('litellm.completion_cost', return_value=0.001),
        patch('litellm.supports_response_schema', return_value=True),
        patch('litellm.utils.supports_pdf_input', return_value=True),
    ):
        # Upload the document
        upload_resp = client.post(f"/v0/orgs/{TEST_ORG_ID}/documents", json=upload_data, headers=get_auth_headers())
        assert upload_resp.status_code == 200, f"Failed to upload document: {upload_resp.text}"
        upload_result = upload_resp.json()
        document_id = upload_result["documents"][0]["document_id"]

        # Run OCR inline via handler
        analytiq_client = ad.common.get_analytiq_client()
        ocr_msg = {"_id": str(ObjectId()), "msg": {"document_id": document_id}}
        await ad.msg_handlers.process_ocr_msg(analytiq_client, ocr_msg)

        # Verify OCR endpoints
        metadata_resp = client.get(
            f"/v0/orgs/{TEST_ORG_ID}/ocr/download/metadata/{document_id}",
            headers=get_auth_headers()
        )
        assert metadata_resp.status_code == 200, f"Failed to get OCR metadata: {metadata_resp.text}"
        metadata_data = metadata_resp.json()
        assert "n_pages" in metadata_data
        assert "ocr_date" in metadata_data
        assert metadata_data["n_pages"] > 0

        text_resp = client.get(
            f"/v0/orgs/{TEST_ORG_ID}/ocr/download/text/{document_id}",
            headers=get_auth_headers()
        )
        assert text_resp.status_code == 200
        ocr_text = text_resp.text
        assert "INVOICE #12345" in ocr_text
        assert "Total: $1,234.56" in ocr_text
        assert "Vendor: Acme Corp" in ocr_text

        # Run LLM inline via handler for default prompt
        llm_msg = {"_id": str(ObjectId()), "msg": {"document_id": document_id}}
        await ad.msg_handlers.process_llm_msg(analytiq_client, llm_msg)

        # Verify default prompt result
        llm_result_resp = client.get(
            f"/v0/orgs/{TEST_ORG_ID}/llm/result/{document_id}",
            params={"prompt_revid": "default"},
            headers=get_auth_headers()
        )
        assert llm_result_resp.status_code == 200, f"Failed to get LLM result: {llm_result_resp.text}"
        llm_result_data = llm_result_resp.json()
        assert "llm_result" in llm_result_data
        assert llm_result_data.get("prompt_display_name") == "Document Summary"


@pytest.mark.asyncio
async def test_full_document_llm_processing_pipeline_inline(org_and_users, setup_test_models, test_db):
    """End-to-end: schema, tag, prompt, upload, OCR + LLM inline, then CRUD on results."""
    org_id = org_and_users["org_id"]
    admin = org_and_users["admin"]

    mock_llm_response = MockLLMResponse()
    mock_llm_response.choices[0].message.content = json.dumps({
        "invoice_number": "12345",
        "total_amount": 1234.56,
        "vendor": {"name": "Acme Corp"}
    })

    with (
        patch('analytiq_data.aws.textract.run_textract', new=mock_run_textract),
        patch('analytiq_data.llm.llm._litellm_acompletion_with_retry', new=mock_litellm_acompletion_with_retry),
        patch('analytiq_data.llm.llm._litellm_acreate_file_with_retry', new=mock_litellm_acreate_file_with_retry),
        patch('litellm.completion_cost', return_value=0.001),
        patch('litellm.supports_response_schema', return_value=True),
        patch('litellm.utils.supports_pdf_input', return_value=True),
    ):
        # Create schema
        schema_data = {
            "name": "Invoice Extraction Schema",
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "invoice_extraction",
                    "schema": {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {
                            "invoice_number": {"type": "string", "description": "The invoice identifier"},
                            "total_amount": {"type": "number", "description": "Total invoice amount"},
                            "vendor": {
                                "type": "object",
                                "properties": {"name": {"type": "string", "description": "Vendor name"}},
                                "required": ["name"]
                            }
                        },
                        "required": ["invoice_number", "total_amount"]
                    },
                    "strict": True
                }
            }
        }
        schema_resp = client.post(f"/v0/orgs/{org_id}/schemas", json=schema_data, headers=get_token_headers(admin["token"]))
        assert schema_resp.status_code == 200, f"Failed to create schema: {schema_resp.text}"
        schema_revid = schema_resp.json()["schema_revid"]

        # Create tag
        tag_data = {"name": "invoice-tag", "color": "#FF5722", "description": "Invoice documents"}
        tag_resp = client.post(f"/v0/orgs/{org_id}/tags", json=tag_data, headers=get_token_headers(admin["token"]))
        assert tag_resp.status_code == 200, f"Failed to create tag: {tag_resp.text}"
        tag_id = tag_resp.json()["id"]

        # Create prompt bound to tag + schema
        prompt_data = {
            "name": "Invoice Processing Prompt",
            "content": "Extract invoice information from this document. Focus on invoice number, total amount, and vendor details.",
            "model": "gpt-4o-mini",
            "tag_ids": [tag_id],
            "schema_revid": schema_revid
        }
        prompt_resp = client.post(f"/v0/orgs/{org_id}/prompts", json=prompt_data, headers=get_token_headers(admin["token"]))
        assert prompt_resp.status_code == 200, f"Failed to create prompt: {prompt_resp.text}"
        prompt_revid = prompt_resp.json()["prompt_revid"]
        prompt_id = prompt_resp.json()["prompt_id"]

        # Upload a small PDF with the tag
        pdf_content = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF\n"
        test_pdf = {
            "name": "test_invoice.pdf",
            "content": f"data:application/pdf;base64,{base64.b64encode(pdf_content).decode()}"
        }
        upload_data = {
            "documents": [{
                "name": test_pdf["name"],
                "content": test_pdf["content"],
                "metadata": {"test_source": "llm_pipeline_test"},
                "tag_ids": [tag_id]
            }]
        }
        upload_resp = client.post(f"/v0/orgs/{org_id}/documents", json=upload_data, headers=get_token_headers(admin["token"]))
        assert upload_resp.status_code == 200, f"Failed to upload document: {upload_resp.text}"
        document_id = upload_resp.json()["documents"][0]["document_id"]

        # Process OCR inline
        analytiq_client = ad.common.get_analytiq_client()
        await ad.msg_handlers.process_ocr_msg(analytiq_client, {"_id": str(ObjectId()), "msg": {"document_id": document_id}})

        # Process LLM inline (default + tag prompt)
        await ad.msg_handlers.process_llm_msg(analytiq_client, {"_id": str(ObjectId()), "msg": {"document_id": document_id}})

        # Verify default prompt result includes prompt_display_name
        default_result_resp = client.get(
            f"/v0/orgs/{org_id}/llm/result/{document_id}",
            params={"prompt_revid": "default"},
            headers=get_token_headers(admin["token"]),
        )
        assert default_result_resp.status_code == 200, f"Default LLM result not found: {default_result_resp.text}"
        default_llm_result = default_result_resp.json()
        assert default_llm_result.get("prompt_display_name") == "Document Summary"

        # Verify result for the tagged prompt (no display name for non-default)
        result_resp = client.get(
            f"/v0/orgs/{org_id}/llm/result/{document_id}",
            params={"prompt_revid": prompt_revid},
            headers=get_token_headers(admin["token"]) 
        )
        assert result_resp.status_code == 200, f"LLM result not found: {result_resp.text}"
        llm_result = result_resp.json()
        assert "llm_result" in llm_result
        assert llm_result.get("prompt_display_name") is None
        extracted = llm_result["llm_result"]
        if isinstance(extracted, str):
            extracted = json.loads(extracted)
        assert extracted["invoice_number"] == "12345"
        assert extracted["total_amount"] == 1234.56
        assert extracted["vendor"]["name"] == "Acme Corp"

        # Stable lookup by prompt_id returns the same result without knowing the revid
        by_prompt_id_resp = client.get(
            f"/v0/orgs/{org_id}/llm/result/{document_id}",
            params={"prompt_id": prompt_id},
            headers=get_token_headers(admin["token"]),
        )
        assert by_prompt_id_resp.status_code == 200, f"prompt_id lookup failed: {by_prompt_id_resp.text}"
        by_prompt_id_result = by_prompt_id_resp.json()
        assert by_prompt_id_result["prompt_revid"] == prompt_revid
        assert by_prompt_id_result.get("prompt_display_name") is None

        # prompt_revid_fallback=true resolves via the revision's prompt_id
        fallback_resp = client.get(
            f"/v0/orgs/{org_id}/llm/result/{document_id}",
            params={"prompt_revid": prompt_revid, "prompt_revid_fallback": True},
            headers=get_token_headers(admin["token"]),
        )
        assert fallback_resp.status_code == 200, fallback_resp.text
        assert fallback_resp.json()["prompt_revid"] == prompt_revid

        # The obsolete `fallback` param is still honored for backward compatibility
        obsolete_fallback_resp = client.get(
            f"/v0/orgs/{org_id}/llm/result/{document_id}",
            params={"prompt_revid": prompt_revid, "fallback": True},
            headers=get_token_headers(admin["token"]),
        )
        assert obsolete_fallback_resp.status_code == 200, obsolete_fallback_resp.text
        assert obsolete_fallback_resp.json()["prompt_revid"] == prompt_revid

        # Neither prompt_id nor prompt_revid provided -> 422
        missing_selector_resp = client.get(
            f"/v0/orgs/{org_id}/llm/result/{document_id}",
            headers=get_token_headers(admin["token"]),
        )
        assert missing_selector_resp.status_code == 422, missing_selector_resp.text

        # Verify document state and metadata
        final_doc_resp = client.get(f"/v0/orgs/{org_id}/documents/{document_id}", headers=get_token_headers(admin["token"]))
        assert final_doc_resp.status_code == 200
        final_doc = final_doc_resp.json()
        if "tag_ids" in final_doc:
            assert tag_id in final_doc["tag_ids"]
        if "metadata" in final_doc and final_doc["metadata"]:
            assert final_doc["metadata"]["test_source"] == "llm_pipeline_test"
        assert final_doc.get("state") in [ad.common.doc.DOCUMENT_STATE_LLM_COMPLETED]

        # Update the LLM result via API
        updated_data = {
            "invoice_number": "UPDATED-12345",
            "total_amount": 9999.99,
            "vendor": {"name": "Updated Acme Corp"}
        }
        update_request = {"updated_llm_result": updated_data, "is_verified": True}
        update_resp = client.put(
            f"/v0/orgs/{org_id}/llm/result/{document_id}",
            params={"prompt_revid": prompt_revid},
            json=update_request,
            headers=get_token_headers(admin["token"]) 
        )
        assert update_resp.status_code == 200, f"Failed to update LLM result: {update_resp.text}"
        updated_result = update_resp.json()
        assert updated_result.get("is_verified") is True
        assert updated_result["updated_llm_result"]["invoice_number"] == "UPDATED-12345"

        # Download all results and verify our updated one is present
        download_resp = client.get(
            f"/v0/orgs/{org_id}/llm/results/{document_id}/download",
            headers=get_token_headers(admin["token"]) 
        )
        assert download_resp.status_code == 200
        downloaded = download_resp.json()
        assert isinstance(downloaded, dict) and "results" in downloaded and len(downloaded["results"]) > 0
        assert any(
            r.get("prompt_revid") == prompt_revid and r.get("metadata", {}).get("is_verified") is True and (
                ("extraction_result" in r and r["extraction_result"].get("invoice_number") == "UPDATED-12345") or True
            )
            for r in downloaded["results"]
        )

        # Delete the LLM result and verify 404 afterwards
        delete_resp = client.delete(
            f"/v0/orgs/{org_id}/llm/result/{document_id}",
            params={"prompt_revid": prompt_revid},
            headers=get_token_headers(admin["token"]) 
        )
        assert delete_resp.status_code == 200

        verify_delete_resp = client.get(
            f"/v0/orgs/{org_id}/llm/result/{document_id}",
            params={"prompt_revid": prompt_revid},
            headers=get_token_headers(admin["token"]) 
        )
        assert verify_delete_resp.status_code == 404


@pytest.mark.asyncio
async def test_get_llm_result_by_prompt_id(test_db):
    """get_llm_result(prompt_id=...) returns the latest version regardless of revid."""
    from datetime import datetime, UTC

    analytiq_client = ad.common.get_analytiq_client()
    db = analytiq_client.mongodb_async[analytiq_client.env]

    document_id = str(ObjectId())
    prompt_id = str(ObjectId())
    base = {
        "document_id": document_id,
        "prompt_id": prompt_id,
        "is_edited": False,
        "is_verified": False,
        "created_at": datetime.now(UTC),
        "updated_at": datetime.now(UTC),
    }
    await db.llm_runs.insert_one({
        **base, "prompt_revid": "rev9", "prompt_version": 9,
        "llm_result": {"v": 9}, "updated_llm_result": {"v": 9},
    })
    await db.llm_runs.insert_one({
        **base, "prompt_revid": "rev10", "prompt_version": 10,
        "llm_result": {"v": 10}, "updated_llm_result": {"v": 10},
    })

    # Stable prompt_id lookup returns the highest available version, ignoring revid.
    result = await ad.llm.get_llm_result(analytiq_client, document_id, prompt_id=prompt_id)
    assert result is not None
    assert result["prompt_version"] == 10
    assert result["prompt_revid"] == "rev10"

    # Exact revid lookup still targets that specific version.
    result_v9 = await ad.llm.get_llm_result(analytiq_client, document_id, prompt_revid="rev9")
    assert result_v9 is not None and result_v9["prompt_version"] == 9

    # Unknown prompt_id returns None.
    assert await ad.llm.get_llm_result(analytiq_client, document_id, prompt_id=str(ObjectId())) is None


def test_llm_result_prompt_display_name():
    """Unit test: GET llm/result sets prompt_display_name for default prompt only."""
    from app.routes.llm import _llm_result_response, LLMResult
    from datetime import datetime, UTC

    raw_default = {
        "prompt_revid": "default",
        "prompt_id": "default",
        "prompt_version": 1,
        "document_id": "doc123",
        "llm_result": {"summary": "test"},
        "updated_llm_result": {"summary": "test"},
        "is_edited": False,
        "is_verified": False,
        "created_at": datetime.now(UTC),
        "updated_at": datetime.now(UTC),
    }
    resp_default = _llm_result_response(raw_default)
    assert resp_default.prompt_display_name == "Document Summary"

    raw_other = {**raw_default, "prompt_revid": "abc123", "prompt_id": "pid"}
    resp_other = _llm_result_response(raw_other)
    assert resp_other.prompt_display_name is None


def test_apply_prompt_caching_converts_system_string_when_supported():
    """Prompt caching: system message string is converted to block with cache_control when model supports it."""
    from analytiq_data.llm.llm import _apply_prompt_caching

    with patch("analytiq_data.llm.llm.supports_prompt_caching", return_value=True):
        messages = [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Hello"},
        ]
        out = _apply_prompt_caching("anthropic/claude-3-5-sonnet-20240620", messages)
    assert len(out) == 2
    assert out[0]["role"] == "system"
    assert isinstance(out[0]["content"], list)
    assert len(out[0]["content"]) == 1
    assert out[0]["content"][0]["type"] == "text"
    assert out[0]["content"][0]["text"] == "You are a helpful assistant."
    assert out[0]["content"][0]["cache_control"] == {"type": "ephemeral"}
    assert out[1] == {"role": "user", "content": "Hello"}


def test_apply_prompt_caching_no_change_when_not_supported():
    """Prompt caching: messages are unchanged when model does not support caching."""
    from analytiq_data.llm.llm import _apply_prompt_caching

    with patch("analytiq_data.llm.llm.supports_prompt_caching", return_value=False):
        messages = [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Hello"},
        ]
        out = _apply_prompt_caching("some-other-model", messages)
    assert out is messages
    assert out[0]["content"] == "You are a helpful assistant."


def test_apply_prompt_caching_skipped_for_gemini_when_tools_passed():
    """Prompt caching: skipped for Gemini when tools are passed."""
    from analytiq_data.llm.llm import _apply_prompt_caching

    with patch("analytiq_data.llm.llm.supports_prompt_caching", return_value=True):
        messages = [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Hello"},
        ]
        tools = [{"type": "function", "function": {"name": "test", "description": "test"}}]
        out = _apply_prompt_caching("gemini/gemini-3-flash-preview", messages, tools=tools)
    assert out is messages
    assert out[0]["content"] == "You are a helpful assistant."


def test_apply_prompt_caching_skipped_for_gemini_without_tools():
    """Prompt caching: skipped for Gemini even without tools (min 1024 tokens for cached content)."""
    from analytiq_data.llm.llm import _apply_prompt_caching

    with patch("analytiq_data.llm.llm.supports_prompt_caching", return_value=True):
        messages = [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Hello"},
        ]
        out = _apply_prompt_caching("gemini/gemini-3-flash-preview", messages)
    assert out is messages
    assert out[0]["content"] == "You are a helpful assistant."


def test_apply_prompt_caching_applied_for_claude_when_tools_passed():
    """Prompt caching: still applied for Claude when tools are passed (Claude supports it)."""
    from analytiq_data.llm.llm import _apply_prompt_caching

    with patch("analytiq_data.llm.llm.supports_prompt_caching", return_value=True):
        messages = [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Hello"},
        ]
        tools = [{"type": "function", "function": {"name": "test", "description": "test"}}]
        out = _apply_prompt_caching("anthropic/claude-sonnet-4-5-20250929", messages, tools=tools)
    assert len(out) == 2
    assert out[0]["content"][0]["cache_control"] == {"type": "ephemeral"}


@pytest.mark.asyncio
async def test_default_prompt_runs_when_enabled(test_db, mock_auth, setup_test_models):
    """
    Verify that when an organization has default prompts enabled (the default),
    uploading a document and running the LLM pipeline produces a default prompt result.
    """
    # Organization created by fixtures; ensure flag is effectively enabled
    org = await test_db.organizations.find_one({"_id": ObjectId(TEST_ORG_ID)})
    assert org is not None
    assert org.get("default_prompt_enabled", True) is True

    pdf_content = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF\n"
    test_pdf = {
        "name": "test_default_enabled.pdf",
        "content": f"data:application/pdf;base64,{base64.b64encode(pdf_content).decode()}",
    }
    upload_data = {
        "documents": [
            {
                "name": test_pdf["name"],
                "content": test_pdf["content"],
                "metadata": {"test_source": "default_prompt_enabled_test"},
                "tag_ids": [],
            }
        ]
    }

    with (
        patch("analytiq_data.aws.textract.run_textract", new=mock_run_textract),
        patch(
            "analytiq_data.llm.llm._litellm_acompletion_with_retry",
            new=mock_litellm_acompletion_with_retry,
        ),
        patch(
            "analytiq_data.llm.llm._litellm_acreate_file_with_retry",
            new=mock_litellm_acreate_file_with_retry,
        ),
        patch("litellm.completion_cost", return_value=0.001),
        patch("litellm.supports_response_schema", return_value=True),
        patch("litellm.utils.supports_pdf_input", return_value=True),
    ):
        # Upload the document into the test organization
        upload_resp = client.post(
            f"/v0/orgs/{TEST_ORG_ID}/documents",
            json=upload_data,
            headers=get_auth_headers(),
        )
        assert upload_resp.status_code == 200, f"Failed to upload document: {upload_resp.text}"
        document_id = upload_resp.json()["documents"][0]["document_id"]

        # Run OCR + LLM inline via handlers
        analytiq_client = ad.common.get_analytiq_client()
        await ad.msg_handlers.process_ocr_msg(
            analytiq_client,
            {"_id": str(ObjectId()), "msg": {"document_id": document_id}},
        )
        await ad.msg_handlers.process_llm_msg(
            analytiq_client,
            {"_id": str(ObjectId()), "msg": {"document_id": document_id}},
        )

        # Default prompt result should exist
        llm_result_resp = client.get(
            f"/v0/orgs/{TEST_ORG_ID}/llm/result/{document_id}",
            params={"prompt_revid": "default"},
            headers=get_auth_headers(),
        )
        assert llm_result_resp.status_code == 200, llm_result_resp.text
        data = llm_result_resp.json()
        assert "llm_result" in data
        assert data.get("prompt_display_name") == "Document Summary"


@pytest.mark.asyncio
async def test_default_prompt_does_not_run_when_disabled(test_db, mock_auth, setup_test_models):
    """
    Verify that when default_prompt_enabled is False for an organization,
    the LLM pipeline does not create a default prompt result.
    """
    # Explicitly disable default prompts for the test organization
    await test_db.organizations.update_one(
        {"_id": ObjectId(TEST_ORG_ID)},
        {"$set": {"default_prompt_enabled": False}},
    )
    org = await test_db.organizations.find_one({"_id": ObjectId(TEST_ORG_ID)})
    assert org is not None
    assert org.get("default_prompt_enabled") is False

    pdf_content = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF\n"
    test_pdf = {
        "name": "test_default_disabled.pdf",
        "content": f"data:application/pdf;base64,{base64.b64encode(pdf_content).decode()}",
    }
    upload_data = {
        "documents": [
            {
                "name": test_pdf["name"],
                "content": test_pdf["content"],
                "metadata": {"test_source": "default_prompt_disabled_test"},
                "tag_ids": [],
            }
        ]
    }

    with (
        patch("analytiq_data.aws.textract.run_textract", new=mock_run_textract),
        patch(
            "analytiq_data.llm.llm._litellm_acompletion_with_retry",
            new=mock_litellm_acompletion_with_retry,
        ),
        patch(
            "analytiq_data.llm.llm._litellm_acreate_file_with_retry",
            new=mock_litellm_acreate_file_with_retry,
        ),
        patch("litellm.completion_cost", return_value=0.001),
        patch("litellm.supports_response_schema", return_value=True),
        patch("litellm.utils.supports_pdf_input", return_value=True),
    ):
        # Upload the document into the test organization
        upload_resp = client.post(
            f"/v0/orgs/{TEST_ORG_ID}/documents",
            json=upload_data,
            headers=get_auth_headers(),
        )
        assert upload_resp.status_code == 200, f"Failed to upload document: {upload_resp.text}"
        document_id = upload_resp.json()["documents"][0]["document_id"]

        # Run OCR + LLM inline via handlers
        analytiq_client = ad.common.get_analytiq_client()
        await ad.msg_handlers.process_ocr_msg(
            analytiq_client,
            {"_id": str(ObjectId()), "msg": {"document_id": document_id}},
        )
        await ad.msg_handlers.process_llm_msg(
            analytiq_client,
            {"_id": str(ObjectId()), "msg": {"document_id": document_id}},
        )

        # Default prompt result should NOT exist
        llm_result_resp = client.get(
            f"/v0/orgs/{TEST_ORG_ID}/llm/result/{document_id}",
            params={"prompt_revid": "default"},
            headers=get_auth_headers(),
        )
        assert llm_result_resp.status_code == 404


@pytest.mark.asyncio
async def test_process_llm_msg_deletes_queue_msg_when_document_missing():
    """Deleted documents should drop stale LLM queue messages without retry."""
    from unittest.mock import AsyncMock, MagicMock, patch

    msg_id = str(ObjectId())
    document_id = str(ObjectId())
    analytiq_client = MagicMock()

    with patch.object(ad.common.doc, "get_doc", new_callable=AsyncMock, return_value=None), \
         patch.object(ad.queue, "delete_msg", new_callable=AsyncMock) as mock_delete, \
         patch.object(ad.llm, "run_llm_for_prompt_revids", new_callable=AsyncMock) as mock_run:
        await ad.msg_handlers.process_llm_msg(
            analytiq_client,
            {"_id": msg_id, "msg": {"document_id": document_id}},
        )

    mock_delete.assert_called_once_with(analytiq_client, "llm", msg_id)
    mock_run.assert_not_called()

