import pytest
from bson import ObjectId
import os
from datetime import datetime, UTC
import logging

# Import shared test utilities
from .conftest_utils import (
    client, TEST_ORG_ID, 
    get_auth_headers
)
import analytiq_data as ad

logger = logging.getLogger(__name__)

# Check that ENV is set to pytest
assert os.environ["ENV"] == "pytest"

@pytest.mark.asyncio
async def test_prompt_lifecycle(test_db, mock_auth, setup_test_models):
    """Test the complete prompt lifecycle"""
    logger.info(f"test_prompt_lifecycle() start")
    
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
    assert "prompt_revid" in prompt_result
    assert prompt_result["name"] == "Test Invoice Prompt"
    assert "content" in prompt_result
    
    prompt_id = prompt_result["prompt_id"]
    prompt_revid = prompt_result["prompt_revid"]
    
    # Step 2: List prompts to verify it was created
    list_response = client.get(
        f"/v0/orgs/{TEST_ORG_ID}/prompts",
        headers=get_auth_headers()
    )
    
    assert list_response.status_code == 200
    list_data = list_response.json()
    assert "prompts" in list_data
    
    # Find our prompt in the list
    created_prompt = next((prompt for prompt in list_data["prompts"] if prompt["prompt_revid"] == prompt_revid), None)
    assert created_prompt is not None
    assert created_prompt["name"] == "Test Invoice Prompt"
    
    # Step 3: Get the specific prompt to verify its content
    get_response = client.get(
        f"/v0/orgs/{TEST_ORG_ID}/prompts/{prompt_revid}",
        headers=get_auth_headers()
    )
    
    assert get_response.status_code == 200
    prompt_data = get_response.json()
    assert prompt_data["prompt_revid"] == prompt_revid
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
    updated_prompt_id = updated_prompt_result["prompt_id"]
    updated_prompt_revid = updated_prompt_result["prompt_revid"]
    
    # Step 5: Get the prompt again to verify the update
    get_updated_response = client.get(
        f"/v0/orgs/{TEST_ORG_ID}/prompts/{updated_prompt_revid}",
        headers=get_auth_headers()
    )
    
    assert get_updated_response.status_code == 200
    updated_prompt_data = get_updated_response.json()
    assert updated_prompt_data["prompt_id"] == updated_prompt_id
    assert updated_prompt_data["prompt_revid"] == updated_prompt_revid
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
    deleted_prompt = next((prompt for prompt in list_after_delete_data["prompts"] if prompt["prompt_revid"] == prompt_revid), None)
    assert deleted_prompt is None, "Prompt should have been deleted"
    
    # Step 8: Verify that getting the deleted prompt returns 404
    get_deleted_response = client.get(
        f"/v0/orgs/{TEST_ORG_ID}/prompts/{prompt_revid}",
        headers=get_auth_headers()
    )
    
    assert get_deleted_response.status_code == 404
    
    logger.info(f"test_prompt_lifecycle() end")

@pytest.mark.asyncio
async def test_prompt_with_schema(test_db, mock_auth, setup_test_models):
    """Test creating and using prompts with associated schemas"""
    logger.info(f"test_prompt_with_schema() start")
    
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
    prompt_revid = prompt_result["prompt_revid"]
    
    # Step 3: Get the prompt to verify it has the schema attached
    get_response = client.get(
        f"/v0/orgs/{TEST_ORG_ID}/prompts/{prompt_revid}",
        headers=get_auth_headers()
    )
    
    assert get_response.status_code == 200
    prompt_data = get_response.json()
    assert prompt_data["schema_id"] == schema_id
    assert prompt_data["schema_version"] == 1
    
    # Step 4: Delete the prompt and schema for cleanup
    client.delete(
        f"/v0/orgs/{TEST_ORG_ID}/prompts/{prompt_revid}",
        headers=get_auth_headers()
    )
    
    client.delete(
        f"/v0/orgs/{TEST_ORG_ID}/schemas/{schema_result['schema_revid']}",
        headers=get_auth_headers()
    )

    logger.info(f"test_prompt_with_schema() end")

@pytest.mark.asyncio
async def test_prompt_with_schema_id_only(test_db, mock_auth, setup_test_models):
    """Test creating a prompt with schema_id but no schema_version (should auto-fetch latest)"""
    logger.info(f"test_prompt_with_schema_id_only() start")
    
    # Step 1: Create a schema first
    schema_data = {
        "name": "Test Schema for Auto Version",
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": "test_auto_version",
                "schema": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "field1": {
                            "type": "string",
                            "description": "Field 1 description"
                        }
                    },
                    "required": ["field1"]
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
    expected_schema_version = schema_result["schema_version"]
    
    # Step 2: Create a prompt with schema_id but NO schema_version
    prompt_data = {
        "name": "Test Prompt Auto Version",
        "content": "Extract information from the document.",
        "model": "gpt-4o-mini",
        "schema_id": schema_id,
        # Note: schema_version is intentionally omitted
        "tag_ids": []
    }
    
    create_response = client.post(
        f"/v0/orgs/{TEST_ORG_ID}/prompts",
        json=prompt_data,
        headers=get_auth_headers()
    )
    
    assert create_response.status_code == 200
    prompt_result = create_response.json()
    prompt_revid = prompt_result["prompt_revid"]
    
    # Step 3: Verify the prompt was created with the correct schema_version
    assert prompt_result["schema_id"] == schema_id
    assert prompt_result["schema_version"] == expected_schema_version, f"Expected schema_version {expected_schema_version}, got {prompt_result['schema_version']}"
    
    # Step 4: Get the prompt to double-check
    get_response = client.get(
        f"/v0/orgs/{TEST_ORG_ID}/prompts/{prompt_revid}",
        headers=get_auth_headers()
    )
    
    assert get_response.status_code == 200
    prompt_data = get_response.json()
    assert prompt_data["schema_id"] == schema_id
    assert prompt_data["schema_version"] == expected_schema_version
    
    # Step 5: Cleanup
    client.delete(
        f"/v0/orgs/{TEST_ORG_ID}/prompts/{prompt_revid}",
        headers=get_auth_headers()
    )
    
    client.delete(
        f"/v0/orgs/{TEST_ORG_ID}/schemas/{schema_result['schema_revid']}",
        headers=get_auth_headers()
    )

    logger.info(f"test_prompt_with_schema_id_only() end")

@pytest.mark.asyncio
async def test_prompt_filtering(test_db, mock_auth, setup_test_models):
    """Test filtering prompts by tags"""
    logger.info(f"test_prompt_filtering() start")

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
    
    prompt1_id = prompt1_response.json()["prompt_revid"]
    prompt2_id = prompt2_response.json()["prompt_revid"]
    prompt3_id = prompt3_response.json()["prompt_revid"]
    
    # Step 3: Filter prompts by tag1
    filter_response = client.get(
        f"/v0/orgs/{TEST_ORG_ID}/prompts?tag_ids={tag1_id}",
        headers=get_auth_headers()
    )
    
    assert filter_response.status_code == 200
    filter_data = filter_response.json()
    
    # Should include prompt1 and prompt3
    prompt_ids = [p["prompt_revid"] for p in filter_data["prompts"]]
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
    prompt_ids = [p["prompt_revid"] for p in filter_data["prompts"]]
    assert prompt2_id in prompt_ids
    assert prompt3_id in prompt_ids
    assert prompt1_id not in prompt_ids
    
    # Step 5: Clean up
    client.delete(f"/v0/orgs/{TEST_ORG_ID}/prompts/{prompt1_id}", headers=get_auth_headers())
    client.delete(f"/v0/orgs/{TEST_ORG_ID}/prompts/{prompt2_id}", headers=get_auth_headers())
    client.delete(f"/v0/orgs/{TEST_ORG_ID}/prompts/{prompt3_id}", headers=get_auth_headers())
    client.delete(f"/v0/orgs/{TEST_ORG_ID}/tags/{tag1_id}", headers=get_auth_headers())
    client.delete(f"/v0/orgs/{TEST_ORG_ID}/tags/{tag2_id}", headers=get_auth_headers())
    
    logger.info(f"test_prompt_filtering() end") 

@pytest.mark.asyncio
async def test_prompt_version_deletion(test_db, mock_auth, setup_test_models):
    """Test that when deleting a prompt, all versions with the same prompt_id are deleted"""
    logger.info(f"test_prompt_version_deletion() start")
    
    # Step 1: Create a prompt
    original_prompt_data = {
        "name": "My Versioned Prompt",
        "content": "Original prompt content for version 1",
        "model": "gpt-4o-mini",
        "tag_ids": []
    }
    
    create_response = client.post(
        f"/v0/orgs/{TEST_ORG_ID}/prompts",
        json=original_prompt_data,
        headers=get_auth_headers()
    )
    
    assert create_response.status_code == 200
    original_prompt = create_response.json()
    original_prompt_id = original_prompt["prompt_id"]  # This is the stable identifier
    original_prompt_revid = original_prompt["prompt_revid"]
    original_prompt_version = original_prompt["prompt_version"]
    
    # Step 2: Update the prompt with a new name and content
    updated_prompt_data = {
        "name": "Renamed Versioned Prompt",  # Changed name
        "content": "Updated prompt content for version 2",
        "model": "gpt-4o-mini",
        "tag_ids": []
    }
    
    update_response = client.put(
        f"/v0/orgs/{TEST_ORG_ID}/prompts/{original_prompt_id}",
        json=updated_prompt_data,
        headers=get_auth_headers()
    )
    
    assert update_response.status_code == 200
    updated_prompt = update_response.json()
    updated_prompt_id = updated_prompt["prompt_id"]
    updated_prompt_revid = updated_prompt["prompt_revid"]
    updated_prompt_version = updated_prompt["prompt_version"]
    
    # Verify both versions exist and have the same prompt_id but different names
    assert original_prompt_id == updated_prompt_id  # Same stable identifier
    assert original_prompt_revid != updated_prompt_revid  # Different MongoDB _id
    assert original_prompt_version+1 == updated_prompt_version  # Same stable identifier
    assert original_prompt["name"] != updated_prompt["name"]  # Different names
    
    # Step 3: Check if both versions exist in the database
    db_prompts = await test_db.prompt_revisions.find({
        "prompt_id": original_prompt_id
    }).to_list(None)
    
    assert len(db_prompts) == 2, "Should have two versions of the prompt"
    
    # Step 4: Delete the prompt using the original ID
    delete_response = client.delete(
        f"/v0/orgs/{TEST_ORG_ID}/prompts/{original_prompt_id}",
        headers=get_auth_headers()
    )
    
    assert delete_response.status_code == 200
    
    # Step 5: Verify both versions are deleted from the database
    prompt_revisions = await test_db.prompt_revisions.find({
        "prompt_id": original_prompt_id
    }).to_list(None)
    
    assert len(prompt_revisions) == 0, "All versions of the prompt should be deleted"
    
    # Step 6: Check that the prompt is also deleted
    db_prompts = await test_db.prompts.find_one({
        "_id": original_prompt_id
    })
    
    assert db_prompts is None, "Prompt should be deleted"
    
    # Step 7: Verify that trying to get either version returns 404
    for prompt_revid in [original_prompt_revid, updated_prompt_revid]:
        get_response = client.get(
            f"/v0/orgs/{TEST_ORG_ID}/prompts/{prompt_revid}",
            headers=get_auth_headers()
        )
        assert get_response.status_code == 404, f"Prompt with ID {prompt_revid} should not exist"
    
    logger.info(f"test_prompt_version_deletion() end") 

@pytest.mark.asyncio
async def test_prompt_latest_version_listing(test_db, mock_auth, setup_test_models):
    """Test that when listing prompts, only the latest versions are shown"""
    logger.info(f"test_prompt_latest_version_listing() start")
    
    # Step 1: Create a prompt
    original_prompt_data = {
        "name": "Version Test Prompt",
        "content": "This is the original content",
        "model": "gpt-4o-mini",
        "tag_ids": []
    }
    
    create_response = client.post(
        f"/v0/orgs/{TEST_ORG_ID}/prompts",
        json=original_prompt_data,
        headers=get_auth_headers()
    )
    
    assert create_response.status_code == 200
    original_prompt = create_response.json()
    original_prompt_id = original_prompt["prompt_id"]
    original_prompt_revid = original_prompt["prompt_revid"]
    original_prompt_version = original_prompt["prompt_version"]
    
    # Step 2: Update the prompt with a new name
    renamed_prompt_data = {
        "name": "Renamed Version Test Prompt",
        "content": "This is the original content",
        "model": "gpt-4o-mini",
        "tag_ids": []
    }
    
    update_response = client.put(
        f"/v0/orgs/{TEST_ORG_ID}/prompts/{original_prompt_id}",
        json=renamed_prompt_data,
        headers=get_auth_headers()
    )
    
    assert update_response.status_code == 200
    renamed_prompt = update_response.json()
    renamed_prompt_id = renamed_prompt["prompt_id"]
    renamed_prompt_revid = renamed_prompt["prompt_revid"]
    assert original_prompt_id == renamed_prompt["prompt_id"], "Prompt ID should remain the same"
    
    # Step 3: List prompts and verify only the renamed version is returned
    list_response = client.get(
        f"/v0/orgs/{TEST_ORG_ID}/prompts",
        headers=get_auth_headers()
    )
    
    assert list_response.status_code == 200
    list_data = list_response.json()
    assert "prompts" in list_data
    
    # Find prompts with our prompt_id
    matching_prompts = [p for p in list_data["prompts"] if p["prompt_id"] == original_prompt_id]
    
    # Verify we only have one result for our prompt_id
    assert len(matching_prompts) == 1, "Should only return latest version in listing"
    
    # Verify the one returned is the renamed version
    assert matching_prompts[0]["name"] == "Renamed Version Test Prompt"
    assert matching_prompts[0]["prompt_revid"] == renamed_prompt_revid  # Should be the newer ID
    
    # Step 4: Clean up
    client.delete(
        f"/v0/orgs/{TEST_ORG_ID}/prompts/{original_prompt_id}",
        headers=get_auth_headers()
    )
    
    
    logger.info(f"test_prompt_latest_version_listing() end") 

@pytest.mark.asyncio
async def test_prompt_name_only_update(test_db, mock_auth, setup_test_models):
    """Test that updating only the prompt name doesn't create a new version"""
    logger.info(f"test_prompt_name_only_update() start")
    
    # Step 1: Create a prompt
    original_prompt_data = {
        "name": "Original Prompt Name",
        "content": "This is a test prompt content",
        "model": "gpt-4o-mini",
        "tag_ids": []
    }
    
    create_response = client.post(
        f"/v0/orgs/{TEST_ORG_ID}/prompts",
        json=original_prompt_data,
        headers=get_auth_headers()
    )
    
    assert create_response.status_code == 200
    original_prompt = create_response.json()
    original_prompt_id = original_prompt["prompt_id"]
    original_prompt_revid = original_prompt["prompt_revid"]
    original_prompt_version = original_prompt["prompt_version"]
    
    # Step 2: Update only the name
    name_update_data = {
        "name": "Updated Prompt Name",
        "content": original_prompt["content"],
        "model": original_prompt["model"],
        "tag_ids": original_prompt["tag_ids"]
    }
    
    update_response = client.put(
        f"/v0/orgs/{TEST_ORG_ID}/prompts/{original_prompt_id}",
        json=name_update_data,
        headers=get_auth_headers()
    )
    
    assert update_response.status_code == 200
    updated_prompt = update_response.json()
    updated_prompt_id = updated_prompt["prompt_id"]
    updated_prompt_revid = updated_prompt["prompt_revid"]
    updated_prompt_version = updated_prompt["prompt_version"]
    
    # Verify the ID remains the same (no new version created)
    assert original_prompt_id == updated_prompt_id, "ID should remain the same for name-only updates"
    assert original_prompt_version == updated_prompt_version, "Version should remain the same for name-only updates"
    assert updated_prompt["name"] == "Updated Prompt Name", "Name should be updated"
    
    # Step 3: Verify only one version exists in the database
    db_prompts = await test_db.prompt_revisions.find({
        "prompt_id": original_prompt_id,
        "prompt_version": original_prompt_version
    }).to_list(None)
    
    assert len(db_prompts) == 1, "Should still have only one revision of the prompt"
    
    # Step 4: Update prompt with a substantive change (content)
    content_update_data = {
        "name": "Updated Prompt Name",
        "content": "This is an updated test prompt content",
        "model": original_prompt["model"],
        "tag_ids": original_prompt["tag_ids"]
    }
    
    content_update_response = client.put(
        f"/v0/orgs/{TEST_ORG_ID}/prompts/{original_prompt_id}",
        json=content_update_data,
        headers=get_auth_headers()
    )
    
    assert content_update_response.status_code == 200
    content_updated_prompt = content_update_response.json()
    content_updated_prompt_id = content_updated_prompt["prompt_id"]
    content_updated_prompt_revid = content_updated_prompt["prompt_revid"]
    content_updated_prompt_version = content_updated_prompt["prompt_version"]
    
    # Verify a new version was created
    assert original_prompt_id == content_updated_prompt["prompt_id"], "ID should remain the same for content updates"
    assert original_prompt_version != content_updated_prompt_version, "Version should increase for content updates"
    assert content_updated_prompt_version > original_prompt_version, "Version should increase for content updates"
    
    # Step 5: Verify two versions exist in the database
    db_prompts_after = await test_db.prompt_revisions.find({
        "prompt_id": original_prompt_id
    }).to_list(None)
    
    assert len(db_prompts_after) == 2, "Should now have two revisions of the prompt"
    
    # Clean up
    client.delete(
        f"/v0/orgs/{TEST_ORG_ID}/prompts/{original_prompt_id}",
        headers=get_auth_headers()
    )

    logger.info(f"test_prompt_name_only_update() end")

@pytest.mark.asyncio
async def test_list_prompt_versions(test_db, mock_auth, setup_test_models):
    """Test listing all versions of a prompt"""
    logger.info(f"test_list_prompt_versions() start")
    
    # Step 1: Create a prompt
    original_prompt_data = {
        "name": "Version List Test Prompt",
        "content": "This is the original content",
        "model": "gpt-4o-mini",
        "tag_ids": []
    }
    
    create_response = client.post(
        f"/v0/orgs/{TEST_ORG_ID}/prompts",
        json=original_prompt_data,
        headers=get_auth_headers()
    )
    
    assert create_response.status_code == 200
    original_prompt = create_response.json()
    original_prompt_id = original_prompt["prompt_id"]
    original_prompt_version = original_prompt["prompt_version"]
    
    # Step 2: Create a second version by updating the prompt
    updated_prompt_data = {
        "name": "Version List Test Prompt",
        "content": "This is the updated content",
        "model": "gpt-4o-mini",
        "tag_ids": []
    }
    
    update_response = client.put(
        f"/v0/orgs/{TEST_ORG_ID}/prompts/{original_prompt_id}",
        json=updated_prompt_data,
        headers=get_auth_headers()
    )
    
    assert update_response.status_code == 200
    updated_prompt = update_response.json()
    updated_prompt_version = updated_prompt["prompt_version"]
    assert updated_prompt_version > original_prompt_version
    
    # Step 3: List all versions
    versions_response = client.get(
        f"/v0/orgs/{TEST_ORG_ID}/prompts/{original_prompt_id}/versions",
        headers=get_auth_headers()
    )
    
    assert versions_response.status_code == 200
    versions_data = versions_response.json()
    assert "prompts" in versions_data
    assert versions_data["total_count"] == 2
    assert len(versions_data["prompts"]) == 2
    
    # Step 4: Verify versions are sorted descending by version
    versions = versions_data["prompts"]
    assert versions[0]["prompt_version"] > versions[1]["prompt_version"]
    assert versions[0]["prompt_version"] == updated_prompt_version
    assert versions[1]["prompt_version"] == original_prompt_version
    
    # Step 5: Verify all versions have the same prompt_id and name
    for version in versions:
        assert version["prompt_id"] == original_prompt_id
        assert version["name"] == "Version List Test Prompt"
        assert "prompt_revid" in version
    
    # Step 6: Test with non-existent prompt_id
    fake_id = str(ObjectId())
    not_found_response = client.get(
        f"/v0/orgs/{TEST_ORG_ID}/prompts/{fake_id}/versions",
        headers=get_auth_headers()
    )
    assert not_found_response.status_code == 404
    
    # Clean up
    client.delete(
        f"/v0/orgs/{TEST_ORG_ID}/prompts/{original_prompt_id}",
        headers=get_auth_headers()
    )
    
    logger.info(f"test_list_prompt_versions() end") 