import pytest
import pytest_asyncio
import os
import sys
import pathlib
import base64
from fastapi.testclient import TestClient
from bson import ObjectId
from unittest.mock import patch
import json
from typing import Dict, Any, List
import logging
from datetime import datetime, UTC

# Import shared test utilities
from tests.conftest_utils import (
    client, TEST_ORG_ID, 
    get_auth_headers
)
import analytiq_data as ad

logger = logging.getLogger(__name__)

# Import the DocRouterClient
from docrouter_sdk import DocRouterClient
from docrouter_sdk.models.document import ListDocumentsResponse

# Check that ENV is set to pytest
assert os.environ["ENV"] == "pytest"

def mock_request(self, method: str, path: str, **kwargs) -> Any:
    """
    Override the request method to use FastAPI test client
    instead of making real HTTP requests
    
    Args:
        method: The HTTP method to use (GET, POST, PUT, DELETE)
        path: The path to request
        **kwargs: Additional arguments to pass to the client
        
    Returns:
        The response data
    """
    url = f"{path}"
    
    # Add Authorization header
    headers = kwargs.pop("headers", {})
    headers.update(get_auth_headers())
    
    # Extract parameters for different request types
    params = kwargs.pop("params", None)
    json_data = kwargs.pop("json", None)
    
    # Make the request using the FastAPI test client
    if method.upper() == "GET":
        response = client.get(url, headers=headers, params=params)
    elif method.upper() == "POST":
        response = client.post(url, headers=headers, json=json_data)
    elif method.upper() == "PUT":
        response = client.put(url, headers=headers, json=json_data)
    elif method.upper() == "DELETE":
        response = client.delete(url, headers=headers)
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


@pytest.fixture
def mock_docrouter_client():
    """
    Fixture that provides a DocRouterClient with mocked request method
    that uses FastAPI test client instead of making real HTTP requests
    """
    # Create a client with a dummy URL and token
    client = DocRouterClient(
        base_url="",  # Doesn't matter, not used for requests
        api_token="test_token"   # Doesn't matter, we use get_auth_headers
    )
    
    # Override the request method with our mock implementation
    with patch.object(DocRouterClient, 'request', mock_request):
        yield client

@pytest.fixture
def small_pdf():
    """Create a minimal test PDF file"""
    pdf_content = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF\n"
    return {
        "name": "small_test.pdf",
        "content": f"data:application/pdf;base64,{base64.b64encode(pdf_content).decode()}"
    }

@pytest.mark.asyncio
async def test_documents_api(test_db, mock_auth, mock_docrouter_client, small_pdf):
    """Test the documents API using the mock DocRouterClient"""
    logger.info(f"test_documents_api() start")

    # Test 0: Create test tags for use during upload
    tag_data_1 = {
        "name": "Test Tag 1",
        "color": "#FF0000"
    }
    tag_data_2 = {
        "name": "Test Tag 2",
        "color": "#00FF00"
    }

    tag_1 = mock_docrouter_client.tags.create(TEST_ORG_ID, tag_data_1)
    tag_2 = mock_docrouter_client.tags.create(TEST_ORG_ID, tag_data_2)

    # Test 1: Create a document with metadata and tags
    small_pdf["metadata"] = {"test_client": "sdk", "suite": "integration", "upload_test": "true"}
    small_pdf["tag_ids"] = [tag_1.id, tag_2.id]

    upload_result = mock_docrouter_client.documents.upload(TEST_ORG_ID, [small_pdf])
    assert "documents" in upload_result
    assert len(upload_result["documents"]) == 1
    assert upload_result["documents"][0]["document_name"] == "small_test.pdf"
    assert upload_result["documents"][0]["metadata"] == {"test_client": "sdk", "suite": "integration", "upload_test": "true"}
    assert upload_result["documents"][0]["tag_ids"] == [tag_1.id, tag_2.id]

    document_id = upload_result["documents"][0]["document_id"]
    
    # Test 2: List documents
    documents = mock_docrouter_client.documents.list(TEST_ORG_ID)
    assert isinstance(documents, ListDocumentsResponse)
    assert documents.total_count >= 1
    
    # Find our document in the list
    created_doc = next((doc for doc in documents.documents
                       if doc.id == document_id), None)
    assert created_doc is not None
    assert created_doc.document_name == "small_test.pdf"
    assert created_doc.metadata == {"test_client": "sdk", "suite": "integration", "upload_test": "true"}
    assert created_doc.tag_ids == [tag_1.id, tag_2.id]
    
    # Test 3: Get a document
    doc = mock_docrouter_client.documents.get(TEST_ORG_ID, document_id)
    assert doc.id == document_id
    assert doc.document_name == "small_test.pdf"
    assert doc.metadata == {"test_client": "sdk", "suite": "integration", "upload_test": "true"}
    assert doc.tag_ids == [tag_1.id, tag_2.id]
    
    # Test 4: Update a document with metadata and tags
    update_result = mock_docrouter_client.documents.update(
        TEST_ORG_ID,
        document_id,
        document_name="small_test_updated.pdf",
        tag_ids=[tag_1.id],  # Remove one tag
        metadata={"test_client": "sdk", "suite": "integration", "updated": "true"}
    )
    assert "message" in update_result
    assert update_result["message"] == "Document updated successfully"

    # Get the document again to verify the update
    updated_doc = mock_docrouter_client.documents.get(TEST_ORG_ID, document_id)
    assert updated_doc.document_name == "small_test_updated.pdf"
    assert updated_doc.metadata == {"test_client": "sdk", "suite": "integration", "updated": "true"}
    assert updated_doc.tag_ids == [tag_1.id]
    
    # Test 5: Delete a document
    delete_result = mock_docrouter_client.documents.delete(TEST_ORG_ID, document_id)
    assert "message" in delete_result
    assert delete_result["message"] == "Document deleted successfully"
    
    # List documents again to verify it was deleted
    documents_after_delete = mock_docrouter_client.documents.list(TEST_ORG_ID)
    deleted_doc = next((doc for doc in documents_after_delete.documents
                       if doc.id == document_id), None)
    assert deleted_doc is None, "Document should have been deleted"

    # Clean up created tags
    mock_docrouter_client.tags.delete(TEST_ORG_ID, tag_1.id)
    mock_docrouter_client.tags.delete(TEST_ORG_ID, tag_2.id)
    
    logger.info(f"test_documents_api() end")


@pytest.mark.asyncio
async def test_tags_api(test_db, mock_auth, mock_docrouter_client):
    """Test the tags API using the mock DocRouterClient"""
    logger.info(f"test_tags_api() start")
    
    # Test: List tags
    tags = mock_docrouter_client.tags.list(TEST_ORG_ID)
    assert hasattr(tags, "total_count")
    initial_tag_count = tags.total_count
    
    # Create a tag
    tag_data = {
        "name": "Test Tag",
        "color": "#FF0000"
    }
    create_response = client.post(
        f"/v0/orgs/{TEST_ORG_ID}/tags",
        json=tag_data,
        headers=get_auth_headers()
    )
    assert create_response.status_code == 200
    created_tag = create_response.json()
    
    # List tags again to verify it was created
    tags_after_create = mock_docrouter_client.tags.list(TEST_ORG_ID)
    assert tags_after_create.total_count == initial_tag_count + 1
    
    # Clean up
    client.delete(
        f"/v0/orgs/{TEST_ORG_ID}/tags/{created_tag['id']}",
        headers=get_auth_headers()
    )
    
    logger.info(f"test_tags_api() end")


@pytest.mark.asyncio
async def test_llm_api(test_db, mock_auth, mock_docrouter_client):
    """Test the LLM API using the mock DocRouterClient"""
    logger.info(f"test_llm_api() start")
    
    # Mock the LLM API responses
    with patch.object(mock_docrouter_client.llm, 'run', return_value={"status": "success", "result_id": "mock_result_id"}) as mock_run, \
         patch.object(mock_docrouter_client.llm, 'get_result', return_value={"status": "completed", "output": "Sample output"}) as mock_get_result, \
         patch.object(mock_docrouter_client.llm, 'update_result', return_value={"message": "Result updated successfully"}) as mock_update_result, \
         patch.object(mock_docrouter_client.llm, 'delete_result', return_value={"message": "Result deleted successfully"}) as mock_delete_result:
        
        # Generate a valid ObjectId for testing
        document_id = str(ObjectId())  # This generates a valid ObjectId
        prompt_id = "default_prompt"
        
        # Test: Run LLM analysis
        run_response = mock_docrouter_client.llm.run(TEST_ORG_ID, document_id, prompt_id)
        assert run_response["status"] == "success"
        assert "result_id" in run_response
        
        # Test: Get LLM result
        result_id = run_response["result_id"]
        get_response = mock_docrouter_client.llm.get_result(organization_id=TEST_ORG_ID, document_id=document_id, prompt_revid=result_id)
        assert get_response["status"] == "completed"
        assert "output" in get_response
        
        # Test: Update LLM result
        update_response = mock_docrouter_client.llm.update_result(TEST_ORG_ID, document_id, result_id, {"new_data": "value"})
        assert update_response["message"] == "Result updated successfully"
        
        # Test: Delete LLM result
        delete_response = mock_docrouter_client.llm.delete_result(TEST_ORG_ID, document_id, result_id)
        assert delete_response["message"] == "Result deleted successfully"
    
    logger.info(f"test_llm_api() end")

@pytest.mark.asyncio
async def test_ocr_api(test_db, mock_auth, mock_docrouter_client, small_pdf):
    """Test the OCR API using the mock DocRouterClient"""
    logger.info(f"test_ocr_api() start")
    
    # Mock the OCR API responses
    with patch.object(mock_docrouter_client.ocr, 'get_text', return_value="Sample OCR text") as mock_get_text, \
         patch.object(mock_docrouter_client.ocr, 'get_metadata', return_value={"n_pages": 1, "ocr_date": "2023-10-01"}) as mock_get_metadata, \
         patch.object(mock_docrouter_client.ocr, 'get_blocks', return_value={"blocks": [{"text": "Sample block text", "position": {"x": 0, "y": 0}}]}) as mock_get_blocks:
        
        # Generate a valid ObjectId for testing
        document_id = str(ObjectId())  # This generates a valid ObjectId
        
        # Test: Get OCR text
        ocr_text = mock_docrouter_client.ocr.get_text(TEST_ORG_ID, document_id)
        assert isinstance(ocr_text, str)
        assert len(ocr_text) > 0  # Ensure some text is returned
        
        # Test: Get OCR metadata
        ocr_metadata = mock_docrouter_client.ocr.get_metadata(TEST_ORG_ID, document_id)
        assert isinstance(ocr_metadata, dict)
        assert "n_pages" in ocr_metadata
        assert "ocr_date" in ocr_metadata
        
        # Test: Get OCR blocks
        ocr_blocks = mock_docrouter_client.ocr.get_blocks(TEST_ORG_ID, document_id)
        assert isinstance(ocr_blocks, dict)
        assert "blocks" in ocr_blocks
        assert len(ocr_blocks["blocks"]) > 0
        assert "text" in ocr_blocks["blocks"][0]
        assert "position" in ocr_blocks["blocks"][0]
    
    logger.info(f"test_ocr_api() end")

@pytest.mark.asyncio
async def test_schemas_api(test_db, mock_auth, mock_docrouter_client):
    """Test the Schemas API using the DocRouterClient"""
    logger.info(f"test_schemas_api() start")
    
    # Step 1: Create a JSON schema
    schema_data = {
        "name": "Test Invoice Schema",
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
                                },
                                "address": {
                                    "type": "string",
                                    "description": "Vendor address"
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
    
    create_response = mock_docrouter_client.schemas.create(TEST_ORG_ID, schema_data)
    assert hasattr(create_response, "schema_revid")
    assert create_response.name == "Test Invoice Schema"
    
    schema_id = create_response.schema_id
    schema_revid = create_response.schema_revid
    
    # Step 2: List schemas to verify it was created
    list_response = mock_docrouter_client.schemas.list(TEST_ORG_ID)
    assert list_response.total_count > 0
    
    # Find our schema in the list
    created_schema = next((schema for schema in list_response.schemas if schema.schema_revid == schema_revid), None)
    assert created_schema is not None
    assert created_schema.name == "Test Invoice Schema"
    
    # Step 3: Get the specific schema to verify its content
    get_response = mock_docrouter_client.schemas.get(TEST_ORG_ID, schema_revid)
    assert get_response.schema_revid == schema_revid
    assert get_response.name == "Test Invoice Schema"
    
    # Step 4: Update the schema
    update_data = {
        "name": "Updated Invoice Schema",
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": "invoice_extraction_updated",
                "schema": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "invoice_number": {
                            "type": "string",
                            "description": "The invoice identifier"
                        },
                        "date": {
                            "type": "string",
                            "description": "Invoice date"
                        },
                        "total_amount": {
                            "type": "number",
                            "description": "Total invoice amount"
                        },
                        "tax_amount": {
                            "type": "number",
                            "description": "Tax amount"
                        }
                    },
                    "required": ["invoice_number", "date", "total_amount"]
                },
                "strict": True
            }
        }
    }
    
    update_response = mock_docrouter_client.schemas.update(TEST_ORG_ID, schema_id, update_data)
    assert update_response.name == "Updated Invoice Schema"
    
    # Step 5: Delete the schema
    delete_response = mock_docrouter_client.schemas.delete(TEST_ORG_ID, schema_id)
    assert delete_response["message"] == "Schema deleted successfully"
    
    logger.info(f"test_schemas_api() end")

@pytest.mark.asyncio
async def test_prompts_api(test_db, mock_auth, mock_docrouter_client, setup_test_models):
    """Test the Prompts API using the DocRouterClient"""
    logger.info(f"test_prompts_api() start")


    # Step 1: Create a JSON schema
    schema_data = {
        "name": "Test Prompt Schema",
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": "prompt_extraction",
                "schema": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "field1": {
                            "type": "string",
                            "description": "Field 1 description"
                        },
                        "field2": {
                            "type": "number",
                            "description": "Field 2 description"
                        }
                    },
                    "required": ["field1", "field2"]
                },
                "strict": True
            }
        }
    }
    
    logger.info(f"Creating schema: {schema_data['name']}")
    schema_response = mock_docrouter_client.schemas.create(TEST_ORG_ID, schema_data)
    assert hasattr(schema_response, "schema_revid")
    assert schema_response.name == "Test Prompt Schema"

    logger.info(f"Schema created: {schema_response}")
    
    schema_id = schema_response.schema_id
    schema_revid = schema_response.schema_revid
    schema_version = schema_response.schema_version
    
    # Step 2: Create a prompt
    prompt_data = {
        "name": "Test Prompt",
        "description": "A test prompt for demonstration",
        "schema_id": schema_id,
        "schema_version": schema_version,
        "content": "Extract information from the document."
    }
    
    logger.info(f"Creating prompt: {prompt_data['name']}")
    create_response = mock_docrouter_client.prompts.create(TEST_ORG_ID, prompt_data)
    assert hasattr(create_response, "prompt_revid")
    assert create_response.name == "Test Prompt"
    
    prompt_id = create_response.prompt_id
    prompt_revid = create_response.prompt_revid
    prompt_version = create_response.prompt_version
    logger.info(f"Prompt created: {create_response}")

    assert prompt_version == 1

    # Step 3: List prompts to verify it was created
    logger.info(f"Listing prompts")
    list_response = mock_docrouter_client.prompts.list(TEST_ORG_ID)
    logger.info(f"List prompts response: {list_response}")
    assert list_response.total_count > 0
    
    # Find our prompt in the list
    created_prompt = next((prompt for prompt in list_response.prompts if prompt.prompt_revid == prompt_revid), None)
    assert created_prompt is not None
    assert created_prompt.name == "Test Prompt"
    
    # Step 4: Get the specific prompt to verify its content
    logger.info(f"Getting prompt: {prompt_revid}")
    get_response = mock_docrouter_client.prompts.get(TEST_ORG_ID, prompt_revid)
    logger.info(f"Get prompt response: {get_response}")
    assert get_response.prompt_revid == prompt_revid
    assert get_response.name == "Test Prompt"
    
    # Step 5: Update the prompt
    update_data = {
        "name": "Updated Test Prompt",
        "description": "An updated test prompt",
        "content": "Extract detailed information from the document."
    }
    
    logger.info(f"Updating prompt: {prompt_id}")
    update_response = mock_docrouter_client.prompts.update(TEST_ORG_ID, prompt_id, update_data)
    logger.info(f"Update prompt response: {update_response}")
    assert update_response.name == "Updated Test Prompt"
    
    # Step 6: Delete the prompt
    logger.info(f"Deleting prompt: {prompt_id}")
    delete_response = mock_docrouter_client.prompts.delete(TEST_ORG_ID, prompt_id)
    logger.info(f"Delete prompt response: {delete_response}")
    assert delete_response["message"] == "Prompt deleted successfully"
    
    # Step 7: Delete the schema
    logger.info(f"Deleting schema: {schema_id}")
    delete_schema_response = mock_docrouter_client.schemas.delete(TEST_ORG_ID, schema_id)
    logger.info(f"Delete schema response: {delete_schema_response}")
    assert delete_schema_response["message"] == "Schema deleted successfully"
    
    logger.info(f"test_prompts_api() end")
