import pytest
import os
import json
import secrets
import base64
import asyncio
from datetime import datetime, UTC
from bson import ObjectId
from tests.conftest_utils import client, get_token_headers, TEST_ORG_ID, get_auth_headers
from tests.conftest_llm import WorkerAppliance, MockLLMResponse
import analytiq_data as ad
import logging

logger = logging.getLogger(__name__)

@pytest.mark.asyncio
async def test_full_document_llm_processing_pipeline(org_and_users, setup_test_models, test_db, n_docrouter_workers: int = 25, n_uploads: int = 100):
    """Test the complete document processing pipeline with schema, tag, prompt, upload, and LLM processing"""
    org_id = org_and_users["org_id"]
    admin = org_and_users["admin"]

    # Grant sufficient credits via FastAPI admin endpoint to avoid running out mid-test
    grant_resp = client.post(
        f"/v0/orgs/{org_id}/payments/credits/add",
        json={"amount": 10000},
        headers=get_token_headers(admin["token"]),
    )
    assert grant_resp.status_code == 200, f"Failed to add credits: {grant_resp.text}"

    # Create the mock LLM response for the schema
    mock_llm_response = MockLLMResponse()
    mock_llm_response.choices[0].message.content = json.dumps({
        "invoice_number": "12345",
        "total_amount": 1234.56,
        "vendor": {
            "name": "Acme Corp"
        }
    })

    # Start the worker appliance with mocked functions
    with WorkerAppliance(n_docrouter_workers=n_docrouter_workers, mock_llm_response=mock_llm_response) as worker_appliance:

        # Step 1: Create a JSON schema
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
                            "invoice_number": {
                                "type": "string",
                                "description": "The invoice identifier"
                            },
                            "total_amount": {
                                "type": "number",
                                "description": "Total invoice amount"
                            },
                            "vendor": {
                                "type": "object",
                                "properties": {
                                    "name": {
                                        "type": "string",
                                        "description": "Vendor name"
                                    }
                                },
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
        schema_result = schema_resp.json()
        schema_revid = schema_result["schema_revid"]

        # Step 2: Create a tag
        tag_data = {
            "name": "invoice-tag",
            "color": "#FF5722",
            "description": "Invoice documents"
        }

        tag_resp = client.post(f"/v0/orgs/{org_id}/tags", json=tag_data, headers=get_token_headers(admin["token"]))
        assert tag_resp.status_code == 200, f"Failed to create tag: {tag_resp.text}"
        tag_result = tag_resp.json()
        tag_id = tag_result["id"]

        # Step 3: Create a prompt that uses the tag and schema
        prompt_data = {
            "name": "Invoice Processing Prompt",
            "content": "Extract invoice information from this document. Focus on invoice number, total amount, and vendor details.",
            "model": "gpt-4o-mini",
            "tag_ids": [tag_id],
            "schema_revid": schema_revid
        }

        prompt_resp = client.post(f"/v0/orgs/{org_id}/prompts", json=prompt_data, headers=get_token_headers(admin["token"]))
        assert prompt_resp.status_code == 200, f"Failed to create prompt: {prompt_resp.text}"
        prompt_result = prompt_resp.json()
        prompt_revid = prompt_result["prompt_revid"]

        # Step 4: Create a test PDF document
        pdf_content = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF\n"
        test_pdf = {
            "name": "test_invoice.pdf",
            "content": f"data:application/pdf;base64,{base64.b64encode(pdf_content).decode()}"
        }

        # Step 5: Upload n_uploads documents sequentially, collect their IDs
        document_ids = []
        for i in range(n_uploads):
            upload_data = {
                "documents": [
                    {
                        "name": test_pdf["name"],
                        "content": test_pdf["content"],
                        "metadata": {
                            "test_source": "llm_pipeline_test", 
                            "document_idx": str(i)
                        },
                        "tag_ids": [tag_id],
                    }
                ]
            }

            upload_resp = client.post(
                f"/v0/orgs/{org_id}/documents",
                json=upload_data,
                headers=get_token_headers(admin["token"]),
            )
            assert upload_resp.status_code == 200, f"Failed to upload document {i}: {upload_resp.text}"
            upload_result = upload_resp.json()
            document_id = upload_result["documents"][0]["document_id"]
            document_ids.append(document_id)

        # Phase 1: Wait for OCR completion for each document in order
        for idx, document_id in enumerate(document_ids):
            max_retries = 600
            retry_count = 0
            while retry_count < max_retries:
                doc_resp = client.get(
                    f"/v0/orgs/{org_id}/documents/{document_id}",
                    headers=get_token_headers(admin["token"]),
                )
                assert doc_resp.status_code == 200, f"Failed to get document {idx}: {doc_resp.text}"
                doc_data = doc_resp.json()
                logger.info(f"Document {idx} state: {doc_data.get('state', 'unknown')}")
                if doc_data.get("state") in [
                    ad.common.doc.DOCUMENT_STATE_OCR_COMPLETED,
                    ad.common.doc.DOCUMENT_STATE_LLM_PROCESSING,
                    ad.common.doc.DOCUMENT_STATE_LLM_COMPLETED,
                ]:
                    break
                await asyncio.sleep(0.5)
                retry_count += 1
            assert retry_count < max_retries, f"OCR did not complete for document {idx} in time"

        # Phase 2: Wait for LLM results and verify extracted data in order
        for idx, document_id in enumerate(document_ids):
            max_retries = 600
            retry_count = 0
            llm_result = None
            while retry_count < max_retries:
                try:
                    result_resp = client.get(
                        f"/v0/orgs/{org_id}/llm/result/{document_id}",
                        params={"prompt_revid": prompt_revid},
                        headers=get_token_headers(admin["token"]),
                    )
                    if result_resp.status_code == 200:
                        llm_result = result_resp.json()
                        break
                    elif result_resp.status_code == 404:
                        await asyncio.sleep(0.5)
                        retry_count += 1
                    else:
                        pytest.fail(
                            f"Unexpected response getting LLM result for document {idx}: {result_resp.status_code}: {result_resp.text}"
                        )
                except Exception as e:
                    logger.warning(f"Error checking LLM result for document {idx}: {e}")
                    await asyncio.sleep(0.5)
                    retry_count += 1
            assert llm_result is not None, f"LLM processing did not complete for document {idx} in time"
            assert "llm_result" in llm_result, f"Missing llm_result in response for document {idx}: {llm_result}"

            extracted_data = llm_result["llm_result"]
            if isinstance(extracted_data, str):
                extracted_data = json.loads(extracted_data)

            assert "invoice_number" in extracted_data, f"Missing invoice_number for document {idx}: {extracted_data}"
            assert "total_amount" in extracted_data, f"Missing total_amount for document {idx}: {extracted_data}"
            assert "vendor" in extracted_data, f"Missing vendor for document {idx}: {extracted_data}"
            assert extracted_data["invoice_number"] == "12345"
            assert extracted_data["total_amount"] == 1234.56
            assert extracted_data["vendor"]["name"] == "Acme Corp"

        # Phase 3: Final document state and metadata checks in order
        for idx, document_id in enumerate(document_ids):
            final_doc_resp = client.get(
                f"/v0/orgs/{org_id}/documents/{document_id}",
                headers=get_token_headers(admin["token"]),
            )
            assert final_doc_resp.status_code == 200
            final_doc_data = final_doc_resp.json()

            if "tag_ids" in final_doc_data:
                assert tag_id in final_doc_data["tag_ids"], "Document should still have the invoice tag"

            if "metadata" in final_doc_data and final_doc_data["metadata"]:
                assert final_doc_data["metadata"]["test_source"] == "llm_pipeline_test"
                assert final_doc_data["metadata"].get("document_idx") == str(idx)

            assert final_doc_data.get("state") in [
                ad.common.doc.DOCUMENT_STATE_LLM_COMPLETED
            ], f"Document should be in LLM completed state, got: {final_doc_data.get('state')}"
