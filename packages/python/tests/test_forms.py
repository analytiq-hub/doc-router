import pytest
from bson import ObjectId
import os
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
async def test_form_lifecycle(test_db, mock_auth):
    """Test the complete form lifecycle"""
    logger.info(f"test_form_lifecycle() start")
    
    try:
        # Step 1: Create a form
        form_data = {
            "name": "Test Insurance Form",
            "response_format": {
                "json_formio": [
                    {
                        "type": "textfield",
                        "key": "applicant_name",
                        "label": "Applicant Name",
                        "input": True,
                        "validate": {
                            "required": True
                        }
                    },
                    {
                        "type": "email",
                        "key": "applicant_email", 
                        "label": "Email Address",
                        "input": True,
                        "validate": {
                            "required": True
                        }
                    },
                    {
                        "type": "number",
                        "key": "coverage_amount",
                        "label": "Coverage Amount",
                        "input": True,
                        "validate": {
                            "required": True,
                            "min": 1000
                        }
                    },
                    {
                        "type": "select",
                        "key": "policy_type",
                        "label": "Policy Type",
                        "input": True,
                        "data": {
                            "values": [
                                {"label": "Auto", "value": "auto"},
                                {"label": "Home", "value": "home"},
                                {"label": "Life", "value": "life"}
                            ]
                        },
                        "validate": {
                            "required": True
                        }
                    }
                ]
            },
            "tag_ids": []
        }
        
        create_response = client.post(
            f"/v0/orgs/{TEST_ORG_ID}/forms",
            json=form_data,
            headers=get_auth_headers()
        )
        
        assert create_response.status_code == 200
        form_result = create_response.json()
        assert "form_revid" in form_result
        assert form_result["name"] == "Test Insurance Form"
        assert "response_format" in form_result
        assert "json_formio" in form_result["response_format"]
        
        form_id = form_result["form_id"]
        form_revid = form_result["form_revid"]
        
        # Step 2: List forms to verify it was created
        list_response = client.get(
            f"/v0/orgs/{TEST_ORG_ID}/forms",
            headers=get_auth_headers()
        )
        
        assert list_response.status_code == 200
        list_data = list_response.json()
        assert "forms" in list_data
        
        # Find our form in the list
        created_form = next((form for form in list_data["forms"] if form["form_revid"] == form_revid), None)
        assert created_form is not None
        assert created_form["name"] == "Test Insurance Form"
        
        # Step 3: Get the specific form to verify its content
        get_response = client.get(
            f"/v0/orgs/{TEST_ORG_ID}/forms/{form_revid}",
            headers=get_auth_headers()
        )
        
        assert get_response.status_code == 200
        form_data_response = get_response.json()
        assert form_data_response["form_revid"] == form_revid
        assert form_data_response["name"] == "Test Insurance Form"
        assert "response_format" in form_data_response
        assert "json_formio" in form_data_response["response_format"]
        
        # Verify form fields
        form_fields = form_data_response["response_format"]["json_formio"]
        field_keys = [field["key"] for field in form_fields]
        assert "applicant_name" in field_keys
        assert "applicant_email" in field_keys
        assert "coverage_amount" in field_keys
        assert "policy_type" in field_keys
        
        # Step 4: Update the form
        update_data = {
            "name": "Updated Insurance Form",
            "response_format": {
                "json_formio": [
                    {
                        "type": "textfield",
                        "key": "applicant_name",
                        "label": "Full Name",  # Changed label
                        "input": True,
                        "validate": {
                            "required": True
                        }
                    },
                    {
                        "type": "email",
                        "key": "applicant_email", 
                        "label": "Email Address",
                        "input": True,
                        "validate": {
                            "required": True
                        }
                    },
                    {
                        "type": "number",
                        "key": "coverage_amount",
                        "label": "Coverage Amount",
                        "input": True,
                        "validate": {
                            "required": True,
                            "min": 5000  # Changed minimum
                        }
                    },
                    {
                        "type": "select",
                        "key": "policy_type",
                        "label": "Policy Type",
                        "input": True,
                        "data": {
                            "values": [
                                {"label": "Auto", "value": "auto"},
                                {"label": "Home", "value": "home"},
                                {"label": "Life", "value": "life"},
                                {"label": "Business", "value": "business"}  # Added new option
                            ]
                        },
                        "validate": {
                            "required": True
                        }
                    },
                    {
                        "type": "textfield",
                        "key": "phone_number",  # New field
                        "label": "Phone Number",
                        "input": True,
                        "validate": {
                            "required": False
                        }
                    }
                ]
            },
            "tag_ids": []
        }
        
        update_response = client.put(
            f"/v0/orgs/{TEST_ORG_ID}/forms/{form_id}",
            json=update_data,
            headers=get_auth_headers()
        )
        
        assert update_response.status_code == 200
        logger.info(f"update_response: {update_response.json()}")

        updated_form_revid = update_response.json()["form_revid"]
        
        # Step 5: Get the form again to verify the update
        get_updated_response = client.get(
            f"/v0/orgs/{TEST_ORG_ID}/forms/{updated_form_revid}",
            headers=get_auth_headers()
        )
        
        assert get_updated_response.status_code == 200
        updated_form_data = get_updated_response.json()
        assert updated_form_data["form_revid"] == updated_form_revid
        assert updated_form_data["name"] == "Updated Insurance Form"
        assert "response_format" in updated_form_data
        
        # Verify the updated fields
        updated_fields = updated_form_data["response_format"]["json_formio"]
        updated_field_keys = [field["key"] for field in updated_fields]
        assert "phone_number" in updated_field_keys  # New field
        
        # Find the coverage_amount field and verify minimum changed
        coverage_field = next((field for field in updated_fields if field["key"] == "coverage_amount"), None)
        assert coverage_field is not None
        assert coverage_field["validate"]["min"] == 5000
        
        # Find applicant_name field and verify label changed
        name_field = next((field for field in updated_fields if field["key"] == "applicant_name"), None)
        assert name_field is not None
        assert name_field["label"] == "Full Name"
        
        # Step 6: Delete the form
        delete_response = client.delete(
            f"/v0/orgs/{TEST_ORG_ID}/forms/{form_id}",
            headers=get_auth_headers()
        )
        
        assert delete_response.status_code == 200
        
        # Step 7: List forms again to verify it was deleted
        list_after_delete_response = client.get(
            f"/v0/orgs/{TEST_ORG_ID}/forms",
            headers=get_auth_headers()
        )
        
        assert list_after_delete_response.status_code == 200
        list_after_delete_data = list_after_delete_response.json()
        
        # Verify the form is no longer in the list
        deleted_form = next((form for form in list_after_delete_data["forms"] if form["form_revid"] == form_revid), None)
        assert deleted_form is None, "Form should have been deleted"
        
        # Step 8: Verify that getting the deleted form returns 404
        get_deleted_response = client.get(
            f"/v0/orgs/{TEST_ORG_ID}/forms/{form_revid}",
            headers=get_auth_headers()
        )
        
        assert get_deleted_response.status_code == 404
        
    finally:
        pass  # mock_auth fixture handles cleanup
    
    logger.info(f"test_form_lifecycle() end")

@pytest.mark.asyncio
async def test_form_with_tags(test_db, mock_auth):
    """Test form creation and management with tags"""
    logger.info(f"test_form_with_tags() start")
    
    try:
        # Step 1: Create a tag first
        tag_data = {
            "name": "Insurance Documents",
            "color": "#FF5722",
            "description": "Tag for insurance-related forms"
        }
        
        tag_response = client.post(
            f"/v0/orgs/{TEST_ORG_ID}/tags",
            json=tag_data,
            headers=get_auth_headers()
        )
        
        assert tag_response.status_code == 200
        tag_result = tag_response.json()
        tag_id = tag_result["id"]
        
        # Step 2: Create a form with the tag
        form_data = {
            "name": "Tagged Insurance Form",
            "response_format": {
                "json_formio": [
                    {
                        "type": "textfield",
                        "key": "policy_number",
                        "label": "Policy Number",
                        "input": True,
                        "validate": {
                            "required": True
                        }
                    }
                ]
            },
            "tag_ids": [tag_id]
        }
        
        create_response = client.post(
            f"/v0/orgs/{TEST_ORG_ID}/forms",
            json=form_data,
            headers=get_auth_headers()
        )
        
        assert create_response.status_code == 200
        form_result = create_response.json()
        assert form_result["name"] == "Tagged Insurance Form"
        assert tag_id in form_result["tag_ids"]
        
        form_id = form_result["form_id"]
        form_revid = form_result["form_revid"]
        
        # Step 3: Verify the form has the tag when retrieved
        get_response = client.get(
            f"/v0/orgs/{TEST_ORG_ID}/forms/{form_revid}",
            headers=get_auth_headers()
        )
        
        assert get_response.status_code == 200
        form_data_response = get_response.json()
        assert tag_id in form_data_response["tag_ids"]
        
        # Step 4: Update the form to remove the tag
        update_data = {
            "name": "Tagged Insurance Form",
            "response_format": form_result["response_format"],
            "tag_ids": []  # Remove all tags
        }
        
        update_response = client.put(
            f"/v0/orgs/{TEST_ORG_ID}/forms/{form_id}",
            json=update_data,
            headers=get_auth_headers()
        )
        
        assert update_response.status_code == 200
        updated_form = update_response.json()
        assert len(updated_form["tag_ids"]) == 0
        
        # Clean up
        client.delete(
            f"/v0/orgs/{TEST_ORG_ID}/forms/{form_id}",
            headers=get_auth_headers()
        )
        
        client.delete(
            f"/v0/orgs/{TEST_ORG_ID}/tags/{tag_id}",
            headers=get_auth_headers()
        )
        
    finally:
        pass  # mock_auth fixture handles cleanup
    
    logger.info(f"test_form_with_tags() end")

@pytest.mark.asyncio
async def test_form_version_deletion(test_db, mock_auth):
    """Test that when deleting a form, all versions with the same form_id are deleted"""
    logger.info(f"test_form_version_deletion() start")
    
    try:
        # Step 1: Create a form
        original_form_data = {
            "name": "My Versioned Form",
            "response_format": {
                "json_formio": [
                    {
                        "type": "textfield",
                        "key": "field1",
                        "label": "First Field",
                        "input": True,
                        "validate": {
                            "required": True
                        }
                    }
                ]
            },
            "tag_ids": []
        }
        
        create_response = client.post(
            f"/v0/orgs/{TEST_ORG_ID}/forms",
            json=original_form_data,
            headers=get_auth_headers()
        )
        
        assert create_response.status_code == 200
        original_form = create_response.json()
        original_form_revid = original_form["form_revid"]
        original_form_id = original_form["form_id"]
        original_form_version = original_form["form_version"]
        
        # Step 2: Update the form to create a new version
        updated_form_data = {
            "name": "Renamed Versioned Form",
            "response_format": {
                "json_formio": [
                    {
                        "type": "textfield",
                        "key": "field1",
                        "label": "First Field Modified",
                        "input": True,
                        "validate": {
                            "required": True
                        }
                    },
                    {
                        "type": "textfield",
                        "key": "field2",
                        "label": "Second Field",
                        "input": True,
                        "validate": {
                            "required": False
                        }
                    }
                ]
            },
            "tag_ids": []
        }
        
        update_response = client.put(
            f"/v0/orgs/{TEST_ORG_ID}/forms/{original_form_id}",
            json=updated_form_data,
            headers=get_auth_headers()
        )
        
        assert update_response.status_code == 200
        updated_form = update_response.json()
        updated_form_revid = updated_form["form_revid"]
        updated_form_id = updated_form["form_id"]

        # Verify both versions exist and have the same form_id but different names
        assert original_form_revid != updated_form_revid
        assert original_form_id == updated_form_id
        assert original_form_version + 1 == updated_form["form_version"]
        assert original_form["name"] != updated_form["name"]
        
        # Step 3: Check if both versions exist in the database
        db_forms = await test_db.form_revisions.find({
            "form_id": original_form_id
        }).to_list(None)
        
        assert len(db_forms) == 2, "Should have two versions of the form"
        
        # Step 4: Delete the form using the original ID
        delete_response = client.delete(
            f"/v0/orgs/{TEST_ORG_ID}/forms/{original_form_id}",
            headers=get_auth_headers()
        )
        
        assert delete_response.status_code == 200
        
        # Step 5: Verify both versions are deleted from the database
        remaining_forms = await test_db.form_revisions.find({
            "form_id": original_form_id
        }).to_list(None)
        
        assert len(remaining_forms) == 0, "All versions of the form should be deleted"
        
        # Step 6: Verify that trying to get either version returns 404
        for form_revid in [original_form_revid, updated_form_revid]:
            get_response = client.get(
                f"/v0/orgs/{TEST_ORG_ID}/forms/{form_revid}",
                headers=get_auth_headers()
            )
            assert get_response.status_code == 404, f"Form with ID {form_revid} should not exist"
        
    finally:
        pass  # mock_auth fixture handles cleanup
    
    logger.info(f"test_form_version_deletion() end")

@pytest.mark.asyncio
async def test_form_latest_version_listing(test_db, mock_auth):
    """Test that when listing forms, only the latest versions are shown"""
    logger.info(f"test_form_latest_version_listing() start")
    
    try:
        # Step 1: Create a form
        original_form_data = {
            "name": "Version Test Form",
            "response_format": {
                "json_formio": [
                    {
                        "type": "textfield",
                        "key": "field1",
                        "label": "First Field",
                        "input": True,
                        "validate": {
                            "required": True
                        }
                    }
                ]
            },
            "tag_ids": []
        }
        
        create_response = client.post(
            f"/v0/orgs/{TEST_ORG_ID}/forms",
            json=original_form_data,
            headers=get_auth_headers()
        )
        
        assert create_response.status_code == 200
        original_form = create_response.json()
        original_form_revid = original_form["form_revid"]
        original_form_id = original_form["form_id"]
        original_form_version = original_form["form_version"]
        
        # Step 2: Update the form with a new name only (shouldn't create new version)
        renamed_form_data = {
            "name": "Renamed Version Test Form",
            "response_format": original_form["response_format"],
            "tag_ids": []
        }
        
        update_response = client.put(
            f"/v0/orgs/{TEST_ORG_ID}/forms/{original_form_id}",
            json=renamed_form_data,
            headers=get_auth_headers()
        )
        
        assert update_response.status_code == 200
        renamed_form = update_response.json()
        renamed_form_id = renamed_form["form_id"]
        renamed_form_revid = renamed_form["form_revid"]
        assert original_form_id == renamed_form_id, "Form ID should remain the same"
        assert original_form_version == renamed_form["form_version"], "Form version should not increase"
        
        # Step 3: List forms and verify only the renamed version is returned
        list_response = client.get(
            f"/v0/orgs/{TEST_ORG_ID}/forms",
            headers=get_auth_headers()
        )
        
        assert list_response.status_code == 200
        list_data = list_response.json()
        assert "forms" in list_data
        
        # Find forms with our form_id
        matching_forms = [f for f in list_data["forms"] if f["form_id"] == original_form_id]
        
        # Verify we only have one result for our form_id
        assert len(matching_forms) == 1, "Should only return latest version in listing"
        
        # Verify the one returned is the renamed version
        assert matching_forms[0]["name"] == "Renamed Version Test Form"
        assert matching_forms[0]["form_revid"] == renamed_form_revid
        
        # Step 4: Clean up
        client.delete(
            f"/v0/orgs/{TEST_ORG_ID}/forms/{original_form_id}",
            headers=get_auth_headers()
        )
        
    finally:
        pass  # mock_auth fixture handles cleanup
    
    logger.info(f"test_form_latest_version_listing() end")

@pytest.mark.asyncio
async def test_form_name_only_update(test_db, mock_auth):
    """Test that updating only the form name doesn't create a new version"""
    logger.info(f"test_form_name_only_update() start")
    
    try:
        # Step 1: Create a form
        original_form_data = {
            "name": "Original Form Name",
            "response_format": {
                "json_formio": [
                    {
                        "type": "textfield",
                        "key": "field1",
                        "label": "First Field",
                        "input": True,
                        "validate": {
                            "required": True
                        }
                    }
                ]
            },
            "tag_ids": []
        }
        
        create_response = client.post(
            f"/v0/orgs/{TEST_ORG_ID}/forms",
            json=original_form_data,
            headers=get_auth_headers()
        )
        
        assert create_response.status_code == 200
        original_form = create_response.json()
        original_form_revid = original_form["form_revid"]
        original_form_id = original_form["form_id"]
        original_form_version = original_form["form_version"]
        
        # Step 2: Update only the name
        name_update_data = {
            "name": "Updated Form Name",
            "response_format": original_form["response_format"],
            "tag_ids": original_form["tag_ids"]
        }
        
        update_response = client.put(
            f"/v0/orgs/{TEST_ORG_ID}/forms/{original_form_id}",
            json=name_update_data,
            headers=get_auth_headers()
        )
        
        assert update_response.status_code == 200
        updated_form = update_response.json()
        updated_form_revid = updated_form["form_revid"]
        updated_form_version = updated_form["form_version"]
        
        # Verify the ID remains the same (no new version created)
        assert original_form_revid == updated_form_revid, "ID should remain the same for name-only updates"
        assert original_form_id == updated_form["form_id"]
        assert original_form_version == updated_form_version, "Version should remain the same for name-only updates"
        assert updated_form["name"] == "Updated Form Name", "Name should be updated"
        
        # Step 3: Verify only one version exists in the database
        db_forms = await test_db.form_revisions.find({
            "form_id": original_form_id
        }).to_list(None)
        
        assert len(db_forms) == 1, "Should still have only one version of the form"
        
        # Step 4: Update form with a substantive change (new field)
        content_update_data = {
            "name": "Updated Form Name",
            "response_format": {
                "json_formio": [
                    {
                        "type": "textfield",
                        "key": "field1",
                        "label": "First Field",
                        "input": True,
                        "validate": {
                            "required": True
                        }
                    },
                    {
                        "type": "textfield",
                        "key": "field2",
                        "label": "Second Field",
                        "input": True,
                        "validate": {
                            "required": False
                        }
                    }
                ]
            },
            "tag_ids": []
        }
        
        content_update_response = client.put(
            f"/v0/orgs/{TEST_ORG_ID}/forms/{original_form_id}",
            json=content_update_data,
            headers=get_auth_headers()
        )
        
        assert content_update_response.status_code == 200
        content_updated_form = content_update_response.json()
        content_updated_form_revid = content_updated_form["form_revid"]
        content_updated_form_version = content_updated_form["form_version"]
        
        # Verify a new version was created
        assert original_form_revid != content_updated_form_revid, "ID should change for content updates"
        assert original_form_version != content_updated_form_version, "Version should increase for content updates"
        assert content_updated_form_version > original_form_version, "Version should increase for content updates"
        
        # Step 5: Verify two versions exist in the database
        db_forms_after = await test_db.form_revisions.find({
            "form_id": original_form_id
        }).to_list(None)
        
        assert len(db_forms_after) == 2, "Should now have two revisions of the form"
        
        # Clean up
        client.delete(
            f"/v0/orgs/{TEST_ORG_ID}/forms/{original_form_id}",
            headers=get_auth_headers()
        )
        
    finally:
        pass  # mock_auth fixture handles cleanup
    
    logger.info(f"test_form_name_only_update() end")

@pytest.mark.asyncio
async def test_list_form_versions(test_db, mock_auth):
    """Test listing all versions of a form"""
    logger.info(f"test_list_form_versions() start")
    
    try:
        # Step 1: Create a form
        original_form_data = {
            "name": "Version List Test Form",
            "response_format": {
                "json_formio": [
                    {
                        "type": "textfield",
                        "key": "field1",
                        "label": "First Field",
                        "input": True,
                        "validate": {
                            "required": True
                        }
                    }
                ]
            },
            "tag_ids": []
        }
        
        create_response = client.post(
            f"/v0/orgs/{TEST_ORG_ID}/forms",
            json=original_form_data,
            headers=get_auth_headers()
        )
        
        assert create_response.status_code == 200
        original_form = create_response.json()
        original_form_id = original_form["form_id"]
        original_form_version = original_form["form_version"]
        
        # Step 2: Create a second version by updating the form
        updated_form_data = {
            "name": "Version List Test Form",
            "response_format": {
                "json_formio": [
                    {
                        "type": "textfield",
                        "key": "field1",
                        "label": "First Field",
                        "input": True,
                        "validate": {
                            "required": True
                        }
                    },
                    {
                        "type": "textfield",
                        "key": "field2",
                        "label": "Second Field",
                        "input": True,
                        "validate": {
                            "required": False
                        }
                    }
                ]
            },
            "tag_ids": []
        }
        
        update_response = client.put(
            f"/v0/orgs/{TEST_ORG_ID}/forms/{original_form_id}",
            json=updated_form_data,
            headers=get_auth_headers()
        )
        
        assert update_response.status_code == 200
        updated_form = update_response.json()
        updated_form_version = updated_form["form_version"]
        assert updated_form_version > original_form_version
        
        # Step 3: List all versions
        versions_response = client.get(
            f"/v0/orgs/{TEST_ORG_ID}/forms/{original_form_id}/versions",
            headers=get_auth_headers()
        )
        
        assert versions_response.status_code == 200
        versions_data = versions_response.json()
        assert "forms" in versions_data
        assert versions_data["total_count"] == 2
        assert len(versions_data["forms"]) == 2
        
        # Step 4: Verify versions are sorted descending by version
        versions = versions_data["forms"]
        assert versions[0]["form_version"] > versions[1]["form_version"]
        assert versions[0]["form_version"] == updated_form_version
        assert versions[1]["form_version"] == original_form_version
        
        # Step 5: Verify all versions have the same form_id and name
        for version in versions:
            assert version["form_id"] == original_form_id
            assert version["name"] == "Version List Test Form"
            assert "form_revid" in version
        
        # Step 6: Test with non-existent form_id
        fake_id = str(ObjectId())
        not_found_response = client.get(
            f"/v0/orgs/{TEST_ORG_ID}/forms/{fake_id}/versions",
            headers=get_auth_headers()
        )
        assert not_found_response.status_code == 404
        
        # Clean up
        client.delete(
            f"/v0/orgs/{TEST_ORG_ID}/forms/{original_form_id}",
            headers=get_auth_headers()
        )
        
    finally:
        pass  # mock_auth fixture handles cleanup
    
    logger.info(f"test_list_form_versions() end")

@pytest.mark.asyncio
async def test_form_with_mapping(test_db, mock_auth):
    """Test form creation and retrieval with json_formio_mapping field"""
    logger.info(f"test_form_with_mapping() start")
    
    try:
        # Step 1: Create a form with field mappings
        form_data = {
            "name": "Test Mapped Form",
            "response_format": {
                "json_formio": [
                    {
                        "type": "textfield",
                        "key": "full_name",
                        "label": "Full Name",
                        "input": True,
                        "validate": {
                            "required": True
                        }
                    },
                    {
                        "type": "textfield",
                        "key": "address",
                        "label": "Address",
                        "input": True,
                        "validate": {
                            "required": False
                        }
                    }
                ],
                "json_formio_mapping": {
                    "full_name": {
                        "sources": [
                            {
                                "promptId": "prompt123",
                                "promptName": "Test Prompt",
                                "schemaFieldPath": "clearance_search_fields.insured_name.first_name",
                                "schemaFieldName": "first_name",
                                "schemaFieldType": "string"
                            },
                            {
                                "promptId": "prompt123",
                                "promptName": "Test Prompt",
                                "schemaFieldPath": "clearance_search_fields.insured_name.last_name",
                                "schemaFieldName": "last_name",
                                "schemaFieldType": "string"
                            }
                        ],
                        "mappingType": "concatenated",
                        "concatenationSeparator": " "
                    },
                    "address": {
                        "sources": [
                            {
                                "promptId": "prompt123",
                                "promptName": "Test Prompt",
                                "schemaFieldPath": "clearance_search_fields.mailing_address.street_address",
                                "schemaFieldName": "street_address",
                                "schemaFieldType": "string"
                            }
                        ],
                        "mappingType": "direct"
                    }
                }
            },
            "tag_ids": []
        }
        
        create_response = client.post(
            f"/v0/orgs/{TEST_ORG_ID}/forms",
            json=form_data,
            headers=get_auth_headers()
        )
        
        assert create_response.status_code == 200
        form_result = create_response.json()
        assert "form_revid" in form_result
        assert form_result["name"] == "Test Mapped Form"
        assert "response_format" in form_result
        assert "json_formio" in form_result["response_format"]
        assert "json_formio_mapping" in form_result["response_format"]
        
        form_id = form_result["form_id"]
        form_revid = form_result["form_revid"]
        
        # Step 2: Verify the mapping was saved correctly
        mapping = form_result["response_format"]["json_formio_mapping"]
        assert "full_name" in mapping
        assert "address" in mapping
        
        # Verify full_name mapping (concatenated)
        full_name_mapping = mapping["full_name"]
        assert full_name_mapping["mappingType"] == "concatenated"
        assert full_name_mapping["concatenationSeparator"] == " "
        assert len(full_name_mapping["sources"]) == 2
        
        # Verify address mapping (direct)
        address_mapping = mapping["address"]
        assert address_mapping["mappingType"] == "direct"
        assert len(address_mapping["sources"]) == 1
        
        # Step 3: Get the form to verify mappings are persisted
        get_response = client.get(
            f"/v0/orgs/{TEST_ORG_ID}/forms/{form_revid}",
            headers=get_auth_headers()
        )
        
        assert get_response.status_code == 200
        retrieved_form = get_response.json()
        assert "json_formio_mapping" in retrieved_form["response_format"]
        
        retrieved_mapping = retrieved_form["response_format"]["json_formio_mapping"]
        assert retrieved_mapping == mapping  # Should be identical
        
        # Step 4: Update the form to modify mappings
        updated_form_data = {
            "name": "Test Mapped Form",
            "response_format": {
                "json_formio": form_result["response_format"]["json_formio"],
                "json_formio_mapping": {
                    "full_name": {
                        "sources": [
                            {
                                "promptId": "prompt456",
                                "promptName": "Updated Prompt",
                                "schemaFieldPath": "person.full_name",
                                "schemaFieldName": "full_name",
                                "schemaFieldType": "string"
                            }
                        ],
                        "mappingType": "direct"
                    }
                }
            },
            "tag_ids": []
        }
        
        update_response = client.put(
            f"/v0/orgs/{TEST_ORG_ID}/forms/{form_id}",
            json=updated_form_data,
            headers=get_auth_headers()
        )
        
        assert update_response.status_code == 200
        updated_form = update_response.json()
        
        # Verify updated mapping
        updated_mapping = updated_form["response_format"]["json_formio_mapping"]
        assert "full_name" in updated_mapping
        assert "address" not in updated_mapping  # Should be removed
        assert updated_mapping["full_name"]["mappingType"] == "direct"
        assert len(updated_mapping["full_name"]["sources"]) == 1
        
        # Clean up
        client.delete(
            f"/v0/orgs/{TEST_ORG_ID}/forms/{form_id}",
            headers=get_auth_headers()
        )
        
    finally:
        pass  # mock_auth fixture handles cleanup
    
    logger.info(f"test_form_with_mapping() end")