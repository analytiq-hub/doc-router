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
async def test_textract_and_llm_default_pipeline(test_db, mock_auth, setup_test_models):
    """Test the document Textract pipeline using WorkerAppliance"""

    # Create a test PDF document
    pdf_content = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF\n"
    test_pdf = {
        "name": "test_invoice.pdf",
        "content": f"data:application/pdf;base64,{base64.b64encode(pdf_content).decode()}"
    }

    # Upload document without tags, schema, or prompts
    upload_data = {
        "documents": [{
            "name": test_pdf["name"],
            "content": test_pdf["content"],
            "metadata": {"test_source": "textract_pipeline_test"},
            "tag_ids": []  # No tags
        }]
    }

    # Start the worker appliance with mocked functions
    with WorkerAppliance(n_workers=1) as worker_appliance:
        # Upload the document
        upload_resp = client.post(f"/v0/orgs/{TEST_ORG_ID}/documents", json=upload_data, headers=get_auth_headers())
        assert upload_resp.status_code == 200, f"Failed to upload document: {upload_resp.text}"
        upload_result = upload_resp.json()
        document_id = upload_result["documents"][0]["document_id"]

        # Wait for OCR processing to complete by checking document state
        max_retries = 20
        retry_count = 0
        ocr_completed = False

        while retry_count < max_retries:
            # Check document status
            doc_resp = client.get(f"/v0/orgs/{TEST_ORG_ID}/documents/{document_id}", headers=get_auth_headers())
            assert doc_resp.status_code == 200, f"Failed to get document: {doc_resp.text}"
            doc_data = doc_resp.json()

            logger.info(f"Document state: {doc_data.get('state', 'unknown')}")

            # Check if OCR has completed (state should be "ocr_completed" or later)
            if doc_data.get("state") in [ad.common.doc.DOCUMENT_STATE_OCR_COMPLETED, ad.common.doc.DOCUMENT_STATE_LLM_COMPLETED]:
                ocr_completed = True
                break

            await asyncio.sleep(0.5)
            retry_count += 1

        assert ocr_completed, f"OCR processing did not complete within expected time. Final state: {doc_data.get('state', 'unknown')}"

        # Test OCR metadata endpoint
        metadata_resp = client.get(
            f"/v0/orgs/{TEST_ORG_ID}/ocr/download/metadata/{document_id}",
            headers=get_auth_headers()
        )
        assert metadata_resp.status_code == 200, f"Failed to get OCR metadata: {metadata_resp.text}"
        metadata_data = metadata_resp.json()

        assert "n_pages" in metadata_data, "OCR metadata should contain n_pages"
        assert "ocr_date" in metadata_data, "OCR metadata should contain ocr_date"
        assert metadata_data["n_pages"] > 0, "Document should have at least 1 page"

        # Test OCR text endpoint
        text_resp = client.get(
            f"/v0/orgs/{TEST_ORG_ID}/ocr/download/text/{document_id}",
            headers=get_auth_headers()
        )
        assert text_resp.status_code == 200, f"Failed to get OCR text: {text_resp.text}"
        ocr_text = text_resp.text

        # Verify we got some text from our mock
        assert "INVOICE #12345" in ocr_text, "OCR text should contain mocked invoice data"
        assert "Total: $1,234.56" in ocr_text, "OCR text should contain mocked total amount"
        assert "Vendor: Acme Corp" in ocr_text, "OCR text should contain mocked vendor"

        # Test OCR text endpoint with specific page
        text_page_resp = client.get(
            f"/v0/orgs/{TEST_ORG_ID}/ocr/download/text/{document_id}",
            params={"page_num": 1},
            headers=get_auth_headers()
        )
        assert text_page_resp.status_code == 200, f"Failed to get OCR text for page 1: {text_page_resp.text}"
        page_text = text_page_resp.text
        assert "INVOICE #12345" in page_text, "Page 1 OCR text should contain mocked invoice data"

        # Test OCR blocks/JSON endpoint
        blocks_resp = client.get(
            f"/v0/orgs/{TEST_ORG_ID}/ocr/download/blocks/{document_id}",
            headers=get_auth_headers()
        )
        assert blocks_resp.status_code == 200, f"Failed to get OCR blocks: {blocks_resp.text}"
        blocks_data = blocks_resp.json()

        # Verify we got the mocked Textract blocks
        assert isinstance(blocks_data, list), "OCR blocks should be a list"
        assert len(blocks_data) > 0, "Should have at least one OCR block"

        # Check for expected block structure from our mock
        invoice_block = next((b for b in blocks_data if b.get("Text") == "INVOICE #12345"), None)
        assert invoice_block is not None, "Should find the invoice block in OCR data"
        assert invoice_block["BlockType"] == "LINE", "Invoice block should be a LINE type"
        assert invoice_block["Page"] == 1, "Invoice block should be on page 1"
        assert invoice_block["Confidence"] >= 98, "Invoice block should have high confidence"

        # Verify the document status shows OCR processing completed
        final_doc_resp = client.get(f"/v0/orgs/{TEST_ORG_ID}/documents/{document_id}", headers=get_auth_headers())
        assert final_doc_resp.status_code == 200
        final_doc_data = final_doc_resp.json()

        logger.info(f"Final document data: {final_doc_data}")

        # Verify metadata if present
        if "metadata" in final_doc_data and final_doc_data["metadata"]:
            assert final_doc_data["metadata"]["test_source"] == "textract_pipeline_test"

        # Wait for LLM processing to complete (up to 30 seconds)
        max_retries = 60  # 30 seconds with 0.5 second intervals
        retry_count = 0
        llm_completed = False

        while retry_count < max_retries:
            doc_resp = client.get(f"/v0/orgs/{TEST_ORG_ID}/documents/{document_id}", headers=get_auth_headers())
            assert doc_resp.status_code == 200, f"Failed to get document: {doc_resp.text}"
            doc_data = doc_resp.json()

            logger.info(f"Document state: {doc_data.get('state', 'unknown')}")

            if doc_data.get("state") == ad.common.doc.DOCUMENT_STATE_LLM_COMPLETED:
                llm_completed = True
                final_doc_data = doc_data
                break

            await asyncio.sleep(0.5)
            retry_count += 1

        assert llm_completed, f"LLM processing did not complete within 30 seconds. Final state: {final_doc_data.get('state', 'unknown')}"

        # Check if LLM default prompt has run and retrieve the result
        try:
            llm_result_resp = client.get(
                f"/v0/orgs/{TEST_ORG_ID}/llm/result/{document_id}",
                params={"prompt_revid": "default"},
                headers=get_auth_headers()
            )

            if llm_result_resp.status_code == 200:
                logger.info("LLM default prompt has completed")
                llm_result_data = llm_result_resp.json()
                logger.info(f"LLM result: {llm_result_data}")

                # Verify the LLM result structure
                assert "llm_result" in llm_result_data, "LLM result should contain 'llm_result' field"

                # Log the extracted data for verification
                extracted_data = llm_result_data["llm_result"]
                if isinstance(extracted_data, str):
                    try:
                        extracted_data = json.loads(extracted_data)
                        logger.info(f"Parsed LLM extracted data: {extracted_data}")
                    except json.JSONDecodeError:
                        logger.info(f"LLM result is text: {extracted_data}")
                else:
                    logger.info(f"LLM extracted data: {extracted_data}")

            elif llm_result_resp.status_code == 404:
                logger.info("LLM default prompt has not run yet or no result available")
            else:
                logger.warning(f"Unexpected response getting LLM result: {llm_result_resp.status_code}: {llm_result_resp.text}")

        except Exception as e:
            logger.warning(f"Error checking LLM result: {e}")

@pytest.mark.asyncio
async def test_full_document_llm_processing_pipeline(org_and_users, setup_test_models, test_db):
    """Test the complete document processing pipeline with schema, tag, prompt, upload, and LLM processing"""
    org_id = org_and_users["org_id"]
    admin = org_and_users["admin"]

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
    with WorkerAppliance(n_workers=1, mock_llm_response=mock_llm_response) as worker_appliance:

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

        # Step 5: Upload document with the tag
        upload_data = {
            "documents": [{
                "name": test_pdf["name"],
                "content": test_pdf["content"],
                "metadata": {"test_source": "llm_pipeline_test"},
                "tag_ids": [tag_id]
            }]
        }

        # Upload the document
        upload_resp = client.post(f"/v0/orgs/{org_id}/documents", json=upload_data, headers=get_token_headers(admin["token"]))
        assert upload_resp.status_code == 200, f"Failed to upload document: {upload_resp.text}"
        upload_result = upload_resp.json()
        document_id = upload_result["documents"][0]["document_id"]

        # Wait for OCR processing to complete
        max_retries = 20
        retry_count = 0
        ocr_completed = False

        while retry_count < max_retries:
            doc_resp = client.get(f"/v0/orgs/{org_id}/documents/{document_id}", headers=get_token_headers(admin["token"]))
            assert doc_resp.status_code == 200, f"Failed to get document: {doc_resp.text}"
            doc_data = doc_resp.json()

            logger.info(f"Document state: {doc_data.get('state', 'unknown')}")

            if doc_data.get("state") in [ad.common.doc.DOCUMENT_STATE_OCR_COMPLETED, ad.common.doc.DOCUMENT_STATE_LLM_COMPLETED]:
                ocr_completed = True
                break

            await asyncio.sleep(0.5)
            retry_count += 1

        assert ocr_completed, f"OCR processing did not complete within expected time. Final state: {doc_data.get('state', 'unknown')}"

        # Wait for LLM processing with the tagged prompt to complete
        max_retries = 20
        retry_count = 0
        llm_result = None

        while retry_count < max_retries:
            try:
                result_resp = client.get(
                    f"/v0/orgs/{org_id}/llm/result/{document_id}",
                    params={"prompt_revid": prompt_revid},
                    headers=get_token_headers(admin["token"])
                )

                if result_resp.status_code == 200:
                    llm_result = result_resp.json()
                    logger.info(f"LLM result found: {llm_result}")
                    break
                elif result_resp.status_code == 404:
                    logger.info(f"LLM result not ready yet, retry {retry_count + 1}/{max_retries}")
                    await asyncio.sleep(0.5)
                    retry_count += 1
                else:
                    pytest.fail(f"Unexpected response getting LLM result: {result_resp.status_code}: {result_resp.text}")

            except Exception as e:
                logger.warning(f"Error checking LLM result: {e}")
                await asyncio.sleep(0.5)
                retry_count += 1

        # Verify the LLM processing results
        assert llm_result is not None, "LLM processing did not complete within expected time"
        assert "llm_result" in llm_result, f"Missing llm_result in response: {llm_result}"

        # Verify the extracted structured data
        extracted_data = llm_result["llm_result"]
        if isinstance(extracted_data, str):
            extracted_data = json.loads(extracted_data)

        assert "invoice_number" in extracted_data, f"Missing invoice_number in extracted data: {extracted_data}"
        assert "total_amount" in extracted_data, f"Missing total_amount in extracted data: {extracted_data}"
        assert "vendor" in extracted_data, f"Missing vendor in extracted data: {extracted_data}"
        assert extracted_data["invoice_number"] == "12345"
        assert extracted_data["total_amount"] == 1234.56
        assert extracted_data["vendor"]["name"] == "Acme Corp"

        # Verify document status and metadata
        final_doc_resp = client.get(f"/v0/orgs/{org_id}/documents/{document_id}", headers=get_token_headers(admin["token"]))
        assert final_doc_resp.status_code == 200
        final_doc_data = final_doc_resp.json()

        logger.info(f"Final document data: {final_doc_data}")

        # Check if document has tag_ids field and contains our tag
        if "tag_ids" in final_doc_data:
            assert tag_id in final_doc_data["tag_ids"], "Document should still have the invoice tag"

        # Verify metadata if present
        if "metadata" in final_doc_data and final_doc_data["metadata"]:
            assert final_doc_data["metadata"]["test_source"] == "llm_pipeline_test"

        # Verify the document state indicates LLM completion
        assert final_doc_data.get("state") in [
            ad.common.doc.DOCUMENT_STATE_LLM_COMPLETED
        ], f"Document should be in LLM completed state, got: {final_doc_data.get('state')}"

        # Additional test steps: Update, verify, download, and delete LLM result
        
        # Step 1: Update the LLM result using the REST API
        updated_data = {
            "invoice_number": "UPDATED-12345",
            "total_amount": 9999.99,
            "vendor": {
                "name": "Updated Acme Corp"
            }
        }
        
        update_request = {
            "updated_llm_result": updated_data,
            "is_verified": True
        }
        
        update_resp = client.put(
            f"/v0/orgs/{org_id}/llm/result/{document_id}",
            params={"prompt_revid": prompt_revid},
            json=update_request,
            headers=get_token_headers(admin["token"])
        )
        assert update_resp.status_code == 200, f"Failed to update LLM result: {update_resp.text}"
        updated_result = update_resp.json()
        
        # Step 2: Verify the LLM result was updated correctly
        assert "llm_result" in updated_result, f"Missing llm_result in updated response: {updated_result}"
        assert "updated_llm_result" in updated_result, f"Missing updated_llm_result in response: {updated_result}"
        assert updated_result.get("is_verified") == True, "Result should be marked as verified"
        
        # Verify the updated data matches what we sent
        updated_llm_data = updated_result["updated_llm_result"]
        assert updated_llm_data["invoice_number"] == "UPDATED-12345"
        assert updated_llm_data["total_amount"] == 9999.99
        assert updated_llm_data["vendor"]["name"] == "Updated Acme Corp"
        
        # Step 3: Download all LLM results and verify them
        download_resp = client.get(
            f"/v0/orgs/{org_id}/llm/results/{document_id}/download",
            headers=get_token_headers(admin["token"])
        )
        assert download_resp.status_code == 200, f"Failed to download LLM results: {download_resp.text}"
        
        # The download should return a JSON file with all results
        downloaded_results = download_resp.json()
        assert isinstance(downloaded_results, dict), "Downloaded results should be a dictionary"
        assert "results" in downloaded_results, "Downloaded results should contain 'results' key"
        assert len(downloaded_results["results"]) > 0, "Should have at least one LLM result"
        
        # Verify our updated result is in the downloaded data
        found_updated_result = False
        for result in downloaded_results["results"]:
            if result.get("prompt_revid") == prompt_revid:
                # Check verification status in metadata
                metadata = result.get("metadata", {})
                assert metadata.get("is_verified") == True, "Downloaded result should be verified"
                if "extraction_result" in result:
                    updated_data_in_download = result["extraction_result"]
                    if updated_data_in_download.get("invoice_number") == "UPDATED-12345":
                        found_updated_result = True
                        break
        
        assert found_updated_result, "Updated result should be found in downloaded data"
        
        # Step 4: Delete the LLM result
        delete_resp = client.delete(
            f"/v0/orgs/{org_id}/llm/result/{document_id}",
            params={"prompt_revid": prompt_revid},
            headers=get_token_headers(admin["token"])
        )
        assert delete_resp.status_code == 200, f"Failed to delete LLM result: {delete_resp.text}"
        delete_result = delete_resp.json()
        assert delete_result.get("status") == "success", f"Delete should return success status: {delete_result}"
        
        # Verify the LLM result was actually deleted
        verify_delete_resp = client.get(
            f"/v0/orgs/{org_id}/llm/result/{document_id}",
            params={"prompt_revid": prompt_revid},
            headers=get_token_headers(admin["token"])
        )
        assert verify_delete_resp.status_code == 404, "LLM result should no longer exist after deletion"
