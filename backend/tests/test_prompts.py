import pytest
from bson import ObjectId
import os
from datetime import datetime, UTC

# Import shared test utilities
from .test_utils import (
    client, TEST_USER, TEST_ORG_ID, 
    test_db, get_auth_headers, mock_auth
)
import analytiq_data as ad

# Check that ENV is set to pytest
assert os.environ["ENV"] == "pytest"

async def setup_test_models(db):
    """Set up test LLM models in the database"""
    # Check if the models already exist
    models = await db.llm_models.find({}).to_list(None)
    if models:
        return  # Models already set up
        
    # Add test models
    test_models = [
        {
            "name": "gpt-4o-mini",
            "provider": "OpenAI",
            "description": "GPT-4o Mini - efficient model for testing",
            "max_tokens": 4096,
            "cost_per_1m_input_tokens": 0.5,
            "cost_per_1m_output_tokens": 1.5
        },
        {
            "name": "gpt-4o",
            "provider": "OpenAI",
            "description": "GPT-4o - powerful model for testing",
            "max_tokens": 8192,
            "cost_per_1m_input_tokens": 5.0,
            "cost_per_1m_output_tokens": 15.0
        }
    ]
    
    await db.llm_models.insert_many(test_models)
    ad.log.info(f"Added {len(test_models)} test LLM models to database")

@pytest.mark.asyncio
async def test_prompt_lifecycle(test_db, mock_auth):
    """Test the complete prompt lifecycle"""
    ad.log.info(f"test_prompt_lifecycle() start")
    
    try:
        # Set up test models first
        await setup_test_models(test_db)
        
        # Step 1: Create a prompt
        prompt_data = {
            "name": "Test Invoice Prompt",
            "content": "Extract the following information from the invoice: invoice number, date, total amount, vendor name.",
            "model": "gpt-4o-mini",
            "tag_ids": []
        }
        
        create_response = client.post(
            f"/v0/orgs/{TEST_ORG_ID}/prompts",
            json=prompt_data,
            headers=get_auth_headers()
        )
        
        assert create_response.status_code == 200
        prompt_result = create_response.json()
        assert "id" in prompt_result
        assert prompt_result["name"] == "Test Invoice Prompt"
        assert "content" in prompt_result
        
        prompt_id = prompt_result["id"]
        
        # Step 2: List prompts to verify it was created
        list_response = client.get(
            f"/v0/orgs/{TEST_ORG_ID}/prompts",
            headers=get_auth_headers()
        )
        
        assert list_response.status_code == 200
        list_data = list_response.json()
        assert "prompts" in list_data
        
        # Find our prompt in the list
        created_prompt = next((prompt for prompt in list_data["prompts"] if prompt["id"] == prompt_id), None)
        assert created_prompt is not None
        assert created_prompt["name"] == "Test Invoice Prompt"
        
        # Step 3: Get the specific prompt to verify its content
        get_response = client.get(
            f"/v0/orgs/{TEST_ORG_ID}/prompts/{prompt_id}",
            headers=get_auth_headers()
        )
        
        assert get_response.status_code == 200
        prompt_data = get_response.json()
        assert prompt_data["id"] == prompt_id
        assert prompt_data["name"] == "Test Invoice Prompt"
        assert "content" in prompt_data
        assert prompt_data["content"] == "Extract the following information from the invoice: invoice number, date, total amount, vendor name."
        
        # Step 4: Update the prompt
        update_data = {
            "name": "Updated Invoice Prompt",
            "content": "Extract the following information from the invoice: invoice number, date, total amount, tax amount, vendor name, vendor address.",
            "model": "gpt-4o",
            "tag_ids": []
        }
        
        update_response = client.put(
            f"/v0/orgs/{TEST_ORG_ID}/prompts/{prompt_id}",
            json=update_data,
            headers=get_auth_headers()
        )
        
        assert update_response.status_code == 200
        updated_prompt_result = update_response.json()

        updated_prompt_id = updated_prompt_result["id"]
        
        # Step 5: Get the prompt again to verify the update
        get_updated_response = client.get(
            f"/v0/orgs/{TEST_ORG_ID}/prompts/{updated_prompt_id}",
            headers=get_auth_headers()
        )
        
        assert get_updated_response.status_code == 200
        updated_prompt_data = get_updated_response.json()
        assert updated_prompt_data["id"] == updated_prompt_id
        assert updated_prompt_data["name"] == "Updated Invoice Prompt"
        assert updated_prompt_data["content"] == "Extract the following information from the invoice: invoice number, date, total amount, tax amount, vendor name, vendor address."
        assert updated_prompt_data["model"] == "gpt-4o"
        
        # Step 6: Delete the prompt
        delete_response = client.delete(
            f"/v0/orgs/{TEST_ORG_ID}/prompts/{prompt_id}",
            headers=get_auth_headers()
        )
        
        assert delete_response.status_code == 200
        
        # Step 7: List prompts again to verify it was deleted
        list_after_delete_response = client.get(
            f"/v0/orgs/{TEST_ORG_ID}/prompts",
            headers=get_auth_headers()
        )
        
        assert list_after_delete_response.status_code == 200
        list_after_delete_data = list_after_delete_response.json()
        
        # Verify the prompt is no longer in the list
        deleted_prompt = next((prompt for prompt in list_after_delete_data["prompts"] if prompt["id"] == prompt_id), None)
        assert deleted_prompt is None, "Prompt should have been deleted"
        
        # Step 8: Verify that getting the deleted prompt returns 404
        get_deleted_response = client.get(
            f"/v0/orgs/{TEST_ORG_ID}/prompts/{prompt_id}",
            headers=get_auth_headers()
        )
        
        assert get_deleted_response.status_code == 404
        
    finally:
        pass  # mock_auth fixture handles cleanup
    
    ad.log.info(f"test_prompt_lifecycle() end")

@pytest.mark.asyncio
async def test_prompt_with_schema(test_db, mock_auth):
    """Test creating and using prompts with associated schemas"""
    ad.log.info(f"test_prompt_with_schema() start")
    
    try:
        # Set up test models first
        await setup_test_models(test_db)
        
        # Step 1: Create a schema first
        schema_data = {
            "name": "Invoice Schema",
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
                            "date": {
                                "type": "string",
                                "description": "Invoice date"
                            },
                            "total_amount": {
                                "type": "number",
                                "description": "Total invoice amount"
                            }
                        },
                        "required": ["invoice_number", "date", "total_amount"]
                    },
                    "strict": True
                }
            }
        }
        
        schema_response = client.post(
            f"/v0/orgs/{TEST_ORG_ID}/schemas",
            json=schema_data,
            headers=get_auth_headers()
        )
        
        assert schema_response.status_code == 200
        schema_result = schema_response.json()
        schema_id = schema_result["schema_id"]
        
        # Step 2: Create a prompt with the schema
        prompt_data = {
            "name": "Invoice Extraction With Schema",
            "content": "Extract the following information from the invoice according to the schema.",
            "model": "gpt-4o-mini",
            "schema_id": schema_id,
            "schema_version": 1,
            "tag_ids": []
        }
        
        create_response = client.post(
            f"/v0/orgs/{TEST_ORG_ID}/prompts",
            json=prompt_data,
            headers=get_auth_headers()
        )
        
        assert create_response.status_code == 200
        prompt_result = create_response.json()
        prompt_id = prompt_result["id"]
        
        # Step 3: Get the prompt to verify it has the schema attached
        get_response = client.get(
            f"/v0/orgs/{TEST_ORG_ID}/prompts/{prompt_id}",
            headers=get_auth_headers()
        )
        
        assert get_response.status_code == 200
        prompt_data = get_response.json()
        assert prompt_data["schema_id"] == schema_id
        assert prompt_data["schema_version"] == 1
        
        # Step 4: Delete the prompt and schema for cleanup
        client.delete(
            f"/v0/orgs/{TEST_ORG_ID}/prompts/{prompt_id}",
            headers=get_auth_headers()
        )
        
        client.delete(
            f"/v0/orgs/{TEST_ORG_ID}/schemas/{schema_result['id']}",
            headers=get_auth_headers()
        )
        
    finally:
        pass  # mock_auth fixture handles cleanup
    
    ad.log.info(f"test_prompt_with_schema() end")

@pytest.mark.asyncio
async def test_prompt_filtering(test_db, mock_auth):
    """Test filtering prompts by tags"""
    ad.log.info(f"test_prompt_filtering() start")
    
    try:
        # Set up test models first
        await setup_test_models(test_db)
        
        # Step 1: Create tags
        tag1_data = {
            "name": "Invoice",
            "color": "#FF0000"
        }
        
        tag2_data = {
            "name": "Receipt",
            "color": "#00FF00"
        }
        
        tag1_response = client.post(
            f"/v0/orgs/{TEST_ORG_ID}/tags",
            json=tag1_data,
            headers=get_auth_headers()
        )
        
        tag2_response = client.post(
            f"/v0/orgs/{TEST_ORG_ID}/tags",
            json=tag2_data,
            headers=get_auth_headers()
        )
        
        assert tag1_response.status_code == 200
        assert tag2_response.status_code == 200
        
        tag1_id = tag1_response.json()["id"]
        tag2_id = tag2_response.json()["id"]
        
        # Step 2: Create prompts with different tags
        prompt1_data = {
            "name": "Invoice Prompt",
            "content": "Extract invoice information.",
            "model": "gpt-4o-mini",
            "tag_ids": [tag1_id]
        }
        
        prompt2_data = {
            "name": "Receipt Prompt",
            "content": "Extract receipt information.",
            "model": "gpt-4o-mini",
            "tag_ids": [tag2_id]
        }
        
        prompt3_data = {
            "name": "Combined Prompt",
            "content": "Extract information from both invoices and receipts.",
            "model": "gpt-4o-mini",
            "tag_ids": [tag1_id, tag2_id]
        }
        
        prompt1_response = client.post(
            f"/v0/orgs/{TEST_ORG_ID}/prompts",
            json=prompt1_data,
            headers=get_auth_headers()
        )
        
        prompt2_response = client.post(
            f"/v0/orgs/{TEST_ORG_ID}/prompts",
            json=prompt2_data,
            headers=get_auth_headers()
        )
        
        prompt3_response = client.post(
            f"/v0/orgs/{TEST_ORG_ID}/prompts",
            json=prompt3_data,
            headers=get_auth_headers()
        )
        
        assert prompt1_response.status_code == 200
        assert prompt2_response.status_code == 200
        assert prompt3_response.status_code == 200
        
        prompt1_id = prompt1_response.json()["id"]
        prompt2_id = prompt2_response.json()["id"]
        prompt3_id = prompt3_response.json()["id"]
        
        # Step 3: Filter prompts by tag1
        filter_response = client.get(
            f"/v0/orgs/{TEST_ORG_ID}/prompts?tag_ids={tag1_id}",
            headers=get_auth_headers()
        )
        
        assert filter_response.status_code == 200
        filter_data = filter_response.json()
        
        # Should include prompt1 and prompt3
        prompt_ids = [p["id"] for p in filter_data["prompts"]]
        assert prompt1_id in prompt_ids
        assert prompt3_id in prompt_ids
        assert prompt2_id not in prompt_ids
        
        # Step 4: Filter prompts by tag2
        filter_response = client.get(
            f"/v0/orgs/{TEST_ORG_ID}/prompts?tag_ids={tag2_id}",
            headers=get_auth_headers()
        )
        
        assert filter_response.status_code == 200
        filter_data = filter_response.json()
        
        # Should include prompt2 and prompt3
        prompt_ids = [p["id"] for p in filter_data["prompts"]]
        assert prompt2_id in prompt_ids
        assert prompt3_id in prompt_ids
        assert prompt1_id not in prompt_ids
        
        # Step 5: Clean up
        client.delete(f"/v0/orgs/{TEST_ORG_ID}/prompts/{prompt1_id}", headers=get_auth_headers())
        client.delete(f"/v0/orgs/{TEST_ORG_ID}/prompts/{prompt2_id}", headers=get_auth_headers())
        client.delete(f"/v0/orgs/{TEST_ORG_ID}/prompts/{prompt3_id}", headers=get_auth_headers())
        client.delete(f"/v0/orgs/{TEST_ORG_ID}/tags/{tag1_id}", headers=get_auth_headers())
        client.delete(f"/v0/orgs/{TEST_ORG_ID}/tags/{tag2_id}", headers=get_auth_headers())
        
    finally:
        pass  # mock_auth fixture handles cleanup
    
    ad.log.info(f"test_prompt_filtering() end") 