import pytest
import os
import json
import secrets
import base64
import asyncio
from datetime import datetime, UTC
from bson import ObjectId
from typing import Any
from tests.conftest_utils import client, get_token_headers, TEST_ORG_ID, get_auth_headers
from tests.conftest_llm import WorkerAppliance, MockLLMResponse
from tests.docrouter_sdk.test_sdk_client import mock_docrouter_client
import analytiq_data as ad
import logging

logger = logging.getLogger(__name__)


@pytest.mark.asyncio
async def test_textract_and_llm_default_pipeline_sdk(test_db, mock_auth, setup_test_models, mock_docrouter_client):
    """Test the document Textract pipeline using WorkerAppliance and SDK"""

    # Create a test PDF document
    pdf_content = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF\n"
    test_pdf = {
        "name": "test_invoice.pdf",
        "content": f"data:application/pdf;base64,{base64.b64encode(pdf_content).decode()}"
    }

    # Upload document without tags, schema, or prompts
    upload_data = [{
        "name": test_pdf["name"],
        "content": test_pdf["content"],
        "metadata": {"test_source": "textract_pipeline_test"},
        "tag_ids": []  # No tags
    }]

    # Start the worker appliance with mocked functions
    with WorkerAppliance(n_workers=1) as worker_appliance:
        # Upload the document using SDK
        upload_result = mock_docrouter_client.documents.upload(TEST_ORG_ID, upload_data)
        assert "documents" in upload_result, f"Failed to upload document: {upload_result}"
        document_id = upload_result["documents"][0]["document_id"]

        # Wait for OCR processing to complete by checking document state
        max_retries = 20
        retry_count = 0
        ocr_completed = False

        while retry_count < max_retries:
            # Check document status using SDK
            doc_data = mock_docrouter_client.documents.get(TEST_ORG_ID, document_id)

            logger.info(f"Document state: {doc_data.state}")

            # Check if OCR has completed (state should be "ocr_completed" or later)
            if doc_data.state in [ad.common.doc.DOCUMENT_STATE_OCR_COMPLETED, ad.common.doc.DOCUMENT_STATE_LLM_COMPLETED]:
                ocr_completed = True
                break

            await asyncio.sleep(0.5)
            retry_count += 1

        assert ocr_completed, f"OCR processing did not complete within expected time. Final state: {doc_data.state}"

        # Test OCR metadata endpoint using SDK
        metadata_data = mock_docrouter_client.ocr.get_metadata(TEST_ORG_ID, document_id)

        assert "n_pages" in metadata_data, "OCR metadata should contain n_pages"
        assert "ocr_date" in metadata_data, "OCR metadata should contain ocr_date"
        assert metadata_data["n_pages"] > 0, "Document should have at least 1 page"

        # Test OCR text endpoint using SDK
        ocr_text = mock_docrouter_client.ocr.get_text(TEST_ORG_ID, document_id)
        
        # Handle both string and bytes responses
        if isinstance(ocr_text, bytes):
            ocr_text = ocr_text.decode('utf-8')

        # Verify we got some text from our mock
        assert "INVOICE #12345" in ocr_text, "OCR text should contain mocked invoice data"
        assert "Total: $1,234.56" in ocr_text, "OCR text should contain mocked total amount"
        assert "Vendor: Acme Corp" in ocr_text, "OCR text should contain mocked vendor"

        # Test OCR text endpoint with specific page using SDK
        page_text = mock_docrouter_client.ocr.get_text(TEST_ORG_ID, document_id, page_num=1)
        if isinstance(page_text, bytes):
            page_text = page_text.decode('utf-8')
        assert "INVOICE #12345" in page_text, "Page 1 OCR text should contain mocked invoice data"

        # Test OCR blocks/JSON endpoint using SDK
        blocks_data = mock_docrouter_client.ocr.get_blocks(TEST_ORG_ID, document_id)

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
        final_doc_data = mock_docrouter_client.documents.get(TEST_ORG_ID, document_id)

        logger.info(f"Final document data: {final_doc_data}")

        # Verify metadata if present
        if hasattr(final_doc_data, 'metadata') and final_doc_data.metadata:
            assert final_doc_data.metadata["test_source"] == "textract_pipeline_test"

        # Wait for LLM processing to complete (up to 30 seconds)
        max_retries = 60  # 30 seconds with 0.5 second intervals
        retry_count = 0
        llm_completed = False

        while retry_count < max_retries:
            doc_data = mock_docrouter_client.documents.get(TEST_ORG_ID, document_id)

            logger.info(f"Document state: {doc_data.state}")

            if doc_data.state == ad.common.doc.DOCUMENT_STATE_LLM_COMPLETED:
                llm_completed = True
                final_doc_data = doc_data
                break

            await asyncio.sleep(0.5)
            retry_count += 1

        assert llm_completed, f"LLM processing did not complete within 30 seconds. Final state: {final_doc_data.state}"

        # Check if LLM default prompt has run and retrieve the result using SDK
        try:
            llm_result_data = mock_docrouter_client.llm.get_result(TEST_ORG_ID, document_id, prompt_revid="default")

            if llm_result_data:
                logger.info("LLM default prompt has completed")
                logger.info(f"LLM result: {llm_result_data}")

                # Verify the LLM result structure
                assert hasattr(llm_result_data, "llm_result"), "LLM result should contain 'llm_result' field"

                # Log the extracted data for verification
                extracted_data = llm_result_data.llm_result
                if isinstance(extracted_data, str):
                    try:
                        extracted_data = json.loads(extracted_data)
                        logger.info(f"Parsed LLM extracted data: {extracted_data}")
                    except json.JSONDecodeError:
                        logger.info(f"LLM result is text: {extracted_data}")
                else:
                    logger.info(f"LLM extracted data: {extracted_data}")

        except Exception as e:
            logger.warning(f"Error checking LLM result: {e}")


@pytest.mark.asyncio
async def test_full_document_llm_processing_pipeline_sdk(org_and_users, setup_test_models, test_db):
    """Test the complete document processing pipeline with schema, tag, prompt, upload, and LLM processing using SDK"""
    org_id = org_and_users["org_id"]
    admin = org_and_users["admin"]
    
    # Create a custom mock client that uses the proper authentication headers
    from docrouter_sdk import DocRouterClient
    from unittest.mock import patch
    
    def mock_request_with_auth(self, method: str, path: str, **kwargs) -> Any:
        """Custom mock request that uses proper auth headers for org_and_users"""
        url = f"{path}"
        
        # Use the admin token from org_and_users fixture
        headers = kwargs.pop("headers", {})
        headers.update(get_token_headers(admin["token"]))
        
        # Extract parameters for different request types
        params = kwargs.pop("params", None)
        json_data = kwargs.pop("json", None)
        
        # Make the request using the FastAPI test client
        if method.upper() == "GET":
            response = client.get(url, headers=headers, params=params)
        elif method.upper() == "POST":
            response = client.post(url, headers=headers, json=json_data, params=params)
        elif method.upper() == "PUT":
            response = client.put(url, headers=headers, json=json_data, params=params)
        elif method.upper() == "DELETE":
            response = client.delete(url, headers=headers, params=params)
        else:
            raise ValueError(f"Unsupported HTTP method: {method}")

        # Check for errors
        try:
            response.raise_for_status()
        except Exception as err:
            try:
                error_detail = response.json().get("detail", str(err))
                raise Exception(f"API Error ({response.status_code}): {error_detail}")
            except (ValueError, KeyError):
                raise err
                
        # Parse the response
        if response.content and response.headers.get("content-type") == "application/json":
            return response.json()
        
        # For text content type, return the text
        if response.content and response.headers.get("content-type") == "text/plain":
            return response.text
            
        # Return raw response for binary data
        return response.content
    
    # Create a client with proper authentication
    mock_docrouter_client = DocRouterClient(
        base_url="",  # Doesn't matter, not used for requests
        api_token="test_token"   # Doesn't matter, we use get_token_headers
    )

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
    with WorkerAppliance(n_workers=1, mock_llm_response=mock_llm_response) as worker_appliance, \
         patch.object(DocRouterClient, 'request', mock_request_with_auth):

        # Step 1: Create a JSON schema using SDK
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

        schema_result = mock_docrouter_client.schemas.create(org_id, schema_data)
        assert hasattr(schema_result, "schema_revid"), f"Failed to create schema: {schema_result}"
        schema_revid = schema_result.schema_revid

        # Step 2: Create a tag using SDK
        tag_data = {
            "name": "invoice-tag",
            "color": "#FF5722",
            "description": "Invoice documents"
        }

        tag_result = mock_docrouter_client.tags.create(org_id, tag_data)
        assert hasattr(tag_result, "id"), f"Failed to create tag: {tag_result}"
        tag_id = tag_result.id

        # Step 3: Create a prompt that uses the tag and schema using SDK
        prompt_data = {
            "name": "Invoice Processing Prompt",
            "content": "Extract invoice information from this document. Focus on invoice number, total amount, and vendor details.",
            "model": "gpt-4o-mini",
            "tag_ids": [tag_id],
            "schema_revid": schema_revid
        }

        prompt_result = mock_docrouter_client.prompts.create(org_id, prompt_data)
        assert hasattr(prompt_result, "prompt_revid"), f"Failed to create prompt: {prompt_result}"
        prompt_revid = prompt_result.prompt_revid

        # Step 4: Create a test PDF document
        pdf_content = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF\n"
        test_pdf = {
            "name": "test_invoice.pdf",
            "content": f"data:application/pdf;base64,{base64.b64encode(pdf_content).decode()}"
        }

        # Step 5: Upload document with the tag using SDK
        upload_data = [{
            "name": test_pdf["name"],
            "content": test_pdf["content"],
            "metadata": {"test_source": "llm_pipeline_test"},
            "tag_ids": [tag_id]
        }]

        # Upload the document
        upload_result = mock_docrouter_client.documents.upload(org_id, upload_data)
        assert "documents" in upload_result, f"Failed to upload document: {upload_result}"
        document_id = upload_result["documents"][0]["document_id"]

        # Wait for OCR processing to complete
        max_retries = 20
        retry_count = 0
        ocr_completed = False

        while retry_count < max_retries:
            doc_data = mock_docrouter_client.documents.get(org_id, document_id)

            logger.info(f"Document state: {doc_data.state}")

            if doc_data.state in [ad.common.doc.DOCUMENT_STATE_OCR_COMPLETED, ad.common.doc.DOCUMENT_STATE_LLM_COMPLETED]:
                ocr_completed = True
                break

            await asyncio.sleep(0.5)
            retry_count += 1

        assert ocr_completed, f"OCR processing did not complete within expected time. Final state: {doc_data.state}"

        # Wait for LLM processing with the tagged prompt to complete
        max_retries = 20
        retry_count = 0
        llm_result = None

        while retry_count < max_retries:
            try:
                llm_result = mock_docrouter_client.llm.get_result(org_id, document_id, prompt_revid=prompt_revid)

                if llm_result:
                    logger.info(f"LLM result found: {llm_result}")
                    break
                else:
                    logger.info(f"LLM result not ready yet, retry {retry_count + 1}/{max_retries}")
                    await asyncio.sleep(0.5)
                    retry_count += 1

            except Exception as e:
                logger.warning(f"Error checking LLM result: {e}")
                await asyncio.sleep(0.5)
                retry_count += 1

        # Verify the LLM processing results
        assert llm_result is not None, "LLM processing did not complete within expected time"
        assert hasattr(llm_result, "llm_result"), f"Missing llm_result in response: {llm_result}"

        # Verify the extracted structured data
        extracted_data = llm_result.llm_result
        if isinstance(extracted_data, str):
            extracted_data = json.loads(extracted_data)

        assert "invoice_number" in extracted_data, f"Missing invoice_number in extracted data: {extracted_data}"
        assert "total_amount" in extracted_data, f"Missing total_amount in extracted data: {extracted_data}"
        assert "vendor" in extracted_data, f"Missing vendor in extracted data: {extracted_data}"
        assert extracted_data["invoice_number"] == "12345"
        assert extracted_data["total_amount"] == 1234.56
        assert extracted_data["vendor"]["name"] == "Acme Corp"

        # Verify document status and metadata
        final_doc_data = mock_docrouter_client.documents.get(org_id, document_id)

        logger.info(f"Final document data: {final_doc_data}")

        # Check if document has tag_ids field and contains our tag
        if hasattr(final_doc_data, 'tag_ids') and final_doc_data.tag_ids:
            assert tag_id in final_doc_data.tag_ids, "Document should still have the invoice tag"

        # Verify metadata if present
        if hasattr(final_doc_data, 'metadata') and final_doc_data.metadata:
            assert final_doc_data.metadata["test_source"] == "llm_pipeline_test"

        # Verify the document state indicates LLM completion
        assert final_doc_data.state in [
            ad.common.doc.DOCUMENT_STATE_LLM_COMPLETED
        ], f"Document should be in LLM completed state, got: {final_doc_data.state}"

        # Additional test steps: Update, verify, download, and delete LLM result
        
        # Step 1: Update the LLM result using the SDK
        updated_data = {
            "invoice_number": "UPDATED-12345",
            "total_amount": 9999.99,
            "vendor": {
                "name": "Updated Acme Corp"
            }
        }
        
        update_result = mock_docrouter_client.llm.update_result(
            org_id, 
            document_id, 
            updated_llm_result=updated_data,
            prompt_revid=prompt_revid,
            is_verified=True
        )
        
        # Step 2: Verify the LLM result was updated correctly
        assert hasattr(update_result, "llm_result"), f"Missing llm_result in updated response: {update_result}"
        assert hasattr(update_result, "updated_llm_result"), f"Missing updated_llm_result in response: {update_result}"
        assert update_result.is_verified == True, "Result should be marked as verified"
        
        # Verify the updated data matches what we sent
        updated_llm_data = update_result.updated_llm_result
        assert updated_llm_data["invoice_number"] == "UPDATED-12345"
        assert updated_llm_data["total_amount"] == 9999.99
        assert updated_llm_data["vendor"]["name"] == "Updated Acme Corp"
        
        # Step 3: Download all LLM results and verify them using SDK
        # Note: download_results method may not be available in SDK, using direct API call for now
        download_resp = client.get(
            f"/v0/orgs/{org_id}/llm/results/{document_id}/download",
            headers=get_token_headers(admin["token"])
        )
        assert download_resp.status_code == 200, f"Failed to download LLM results: {download_resp.text}"
        download_result = download_resp.json()
        
        # The download should return a JSON file with all results
        assert isinstance(download_result, dict), "Downloaded results should be a dictionary"
        assert "results" in download_result, "Downloaded results should contain 'results' key"
        assert len(download_result["results"]) > 0, "Should have at least one LLM result"
        
        # Verify our updated result is in the downloaded data
        found_updated_result = False
        for result in download_result["results"]:
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
        
        # Step 4: Delete the LLM result using SDK
        delete_result = mock_docrouter_client.llm.delete_result(org_id, document_id, prompt_revid=prompt_revid)
        assert delete_result.get("status") == "success", f"Delete should return success status: {delete_result}"
        
        # Verify the LLM result was actually deleted
        try:
            verify_delete_result = mock_docrouter_client.llm.get_result(org_id, document_id, prompt_revid=prompt_revid)
            assert verify_delete_result is None, "LLM result should no longer exist after deletion"
        except Exception:
            # Expected behavior - result should not exist
            pass
