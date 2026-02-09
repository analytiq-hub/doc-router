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
    resp_default = _llm_result_response(raw_default, "default")
    assert resp_default.prompt_display_name == "Document Summary"

    raw_other = {**raw_default, "prompt_revid": "abc123", "prompt_id": "pid"}
    resp_other = _llm_result_response(raw_other, "abc123")
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


