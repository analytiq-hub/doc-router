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
async def test_json_schema_lifecycle(test_db, mock_auth):
    """Test the complete JSON schema lifecycle"""
    logger.info(f"test_json_schema_lifecycle() start")
    
    try:
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
                        "required": ["invoice_number", "date", "total_amount"]
                    },
                    "strict": True
                }
            }
        }
        
        create_response = client.post(
            f"/v0/orgs/{TEST_ORG_ID}/schemas",
            json=schema_data,
            headers=get_auth_headers()
        )
        
        assert create_response.status_code == 200
        schema_result = create_response.json()
        assert "schema_revid" in schema_result
        assert schema_result["name"] == "Test Invoice Schema"
        assert "response_format" in schema_result
        
        schema_id = schema_result["schema_id"]
        schema_revid = schema_result["schema_revid"]
        
        # Step 2: List schemas to verify it was created
        list_response = client.get(
            f"/v0/orgs/{TEST_ORG_ID}/schemas",
            headers=get_auth_headers()
        )
        
        assert list_response.status_code == 200
        list_data = list_response.json()
        assert "schemas" in list_data
        
        # Find our schema in the list
        created_schema = next((schema for schema in list_data["schemas"] if schema["schema_revid"] == schema_revid), None)
        assert created_schema is not None
        assert created_schema["name"] == "Test Invoice Schema"
        
        # Step 3: Get the specific schema to verify its content
        get_response = client.get(
            f"/v0/orgs/{TEST_ORG_ID}/schemas/{schema_revid}",
            headers=get_auth_headers()
        )
        
        assert get_response.status_code == 200
        schema_data = get_response.json()
        assert schema_data["schema_revid"] == schema_revid
        assert schema_data["name"] == "Test Invoice Schema"
        assert "response_format" in schema_data
        assert schema_data["response_format"]["type"] == "json_schema"
        assert "json_schema" in schema_data["response_format"]
        assert "invoice_number" in schema_data["response_format"]["json_schema"]["schema"]["properties"]
        assert "total_amount" in schema_data["response_format"]["json_schema"]["schema"]["properties"]
        
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
                                    },
                                    "tax_id": {
                                        "type": "string",
                                        "description": "Vendor tax ID"
                                    }
                                },
                                "required": ["name"]
                            }
                        },
                        "required": ["invoice_number", "date", "total_amount"]
                    },
                    "strict": True
                }
            }
        }
        
        update_response = client.put(
            f"/v0/orgs/{TEST_ORG_ID}/schemas/{schema_id}",
            json=update_data,
            headers=get_auth_headers()
        )
        
        assert update_response.status_code == 200

        logger.info(f"update_response: {update_response.json()}")

        updated_schema_revid = update_response.json()["schema_revid"]
        
        # Step 5: Get the schema again to verify the update
        get_updated_response = client.get(
            f"/v0/orgs/{TEST_ORG_ID}/schemas/{updated_schema_revid}",
            headers=get_auth_headers()
        )
        
        assert get_updated_response.status_code == 200
        updated_schema_data = get_updated_response.json()
        assert updated_schema_data["schema_revid"] == updated_schema_revid
        assert updated_schema_data["name"] == "Updated Invoice Schema"
        assert "response_format" in updated_schema_data
        assert "tax_amount" in updated_schema_data["response_format"]["json_schema"]["schema"]["properties"]
        assert "tax_id" in updated_schema_data["response_format"]["json_schema"]["schema"]["properties"]["vendor"]["properties"]
        
        # Step 6: Delete the schema
        delete_response = client.delete(
            f"/v0/orgs/{TEST_ORG_ID}/schemas/{schema_id}",
            headers=get_auth_headers()
        )
        
        assert delete_response.status_code == 200
        
        # Step 7: List schemas again to verify it was deleted
        list_after_delete_response = client.get(
            f"/v0/orgs/{TEST_ORG_ID}/schemas",
            headers=get_auth_headers()
        )
        
        assert list_after_delete_response.status_code == 200
        list_after_delete_data = list_after_delete_response.json()
        
        # Verify the schema is no longer in the list
        deleted_schema = next((schema for schema in list_after_delete_data["schemas"] if schema["schema_revid"] == schema_revid), None)
        assert deleted_schema is None, "Schema should have been deleted"
        
        # Step 8: Verify that getting the deleted schema returns 404
        get_deleted_response = client.get(
            f"/v0/orgs/{TEST_ORG_ID}/schemas/{schema_id}",
            headers=get_auth_headers()
        )
        
        assert get_deleted_response.status_code == 404
        
    finally:
        pass  # mock_auth fixture handles cleanup
    
    logger.info(f"test_json_schema_lifecycle() end")

@pytest.mark.asyncio
async def test_schema_validation(test_db, mock_auth):
    """Test schema validation functionality"""
    logger.info(f"test_schema_validation() start")
    
    try:
        # Step 1: Create a simple JSON schema for validation testing
        schema_data = {
            "name": "Simple Test Schema",
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "validation_test",
                    "schema": {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {
                            "name": {
                                "type": "string",
                                "minLength": 3
                            },
                            "age": {
                                "type": "integer",
                                "minimum": 18
                            },
                            "email": {
                                "type": "string",
                                "format": "email"
                            }
                        },
                        "required": ["name", "age", "email"]
                    },
                    "strict": True
                }
            }
        }
        
        create_response = client.post(
            f"/v0/orgs/{TEST_ORG_ID}/schemas",
            json=schema_data,
            headers=get_auth_headers()
        )
        
        assert create_response.status_code == 200
        schema_result = create_response.json()
        schema_revid = schema_result["schema_revid"]
        
        # Step 2: Test validation with valid data
        valid_data = {
            "data": {
                "name": "John Doe",
                "age": 25,
                "email": "john.doe@example.com"
            }
        }
        
        valid_validation_response = client.post(
            f"/v0/orgs/{TEST_ORG_ID}/schemas/{schema_revid}/validate",
            json=valid_data,
            headers=get_auth_headers()
        )
        
        assert valid_validation_response.status_code == 200
        valid_result = valid_validation_response.json()
        assert valid_result["valid"] is True
        assert "errors" not in valid_result or len(valid_result["errors"]) == 0
        
        # Step 3: Test validation with invalid data
        invalid_data = {
            "data": {
                "name": "Jo",  # Too short
                "age": 16,     # Below minimum
                "email": "not-an-email"  # Invalid email format
            }
        }
        
        invalid_validation_response = client.post(
            f"/v0/orgs/{TEST_ORG_ID}/schemas/{schema_revid}/validate",
            json=invalid_data,
            headers=get_auth_headers()
        )
        
        assert invalid_validation_response.status_code == 200
        invalid_result = invalid_validation_response.json()
        assert invalid_result["valid"] is False
        assert "errors" in invalid_result
        assert len(invalid_result["errors"]) > 0
        
        # Clean up
        client.delete(
            f"/v0/orgs/{TEST_ORG_ID}/schemas/{schema_revid}",
            headers=get_auth_headers()
        )
        
    finally:
        pass  # mock_auth fixture handles cleanup
    
    logger.info(f"test_schema_validation() end")

@pytest.mark.asyncio
async def test_schema_version_deletion(test_db, mock_auth):
    """Test that when deleting a schema, all versions with the same schema_id are deleted"""
    logger.info(f"test_schema_version_deletion() start")
    
    try:
        # Step 1: Create a schema
        original_schema_data = {
            "name": "My Versioned Schema",
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "test_schema_v1",
                    "schema": {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {
                            "field1": {
                                "type": "string",
                                "description": "First field"
                            },
                            "field2": {
                                "type": "number",
                                "description": "Second field"
                            }
                        },
                        "required": ["field1", "field2"]
                    },
                    "strict": True
                }
            }
        }
        
        create_response = client.post(
            f"/v0/orgs/{TEST_ORG_ID}/schemas",
            json=original_schema_data,
            headers=get_auth_headers()
        )
        
        assert create_response.status_code == 200
        original_schema = create_response.json()
        original_schema_revid = original_schema["schema_revid"]
        original_schema_id = original_schema["schema_id"]  # This is the stable identifier
        original_schema_version = original_schema["schema_version"]
        
        # Step 2: Update the schema with a new name and fields
        updated_schema_data = {
            "name": "Renamed Versioned Schema",  # Changed name
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "test_schema_v2",
                    "schema": {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {
                            "field1": {
                                "type": "string",
                                "description": "First field modified"
                            },
                            "field2": {
                                "type": "number",
                                "description": "Second field modified"
                            },
                            "field3": {
                                "type": "boolean",
                                "description": "New third field"
                            }
                        },
                        "required": ["field1", "field2", "field3"]
                    },
                    "strict": True
                }
            }
        }
        
        update_response = client.put(
            f"/v0/orgs/{TEST_ORG_ID}/schemas/{original_schema_id}",
            json=updated_schema_data,
            headers=get_auth_headers()
        )
        
        assert update_response.status_code == 200
        updated_schema = update_response.json()
        updated_schema_revid = updated_schema["schema_revid"]
        updated_schema_id = updated_schema["schema_id"]

        # Verify both versions exist and have the same schema_id but different names
        assert original_schema_revid != updated_schema_revid  # Different MongoDB _id
        assert original_schema_id == updated_schema_id  # Same stable identifier
        assert original_schema_version + 1 == updated_schema["schema_version"]  # Same stable identifier
        assert original_schema["name"] != updated_schema["name"]  # Different names
        
        # Step 3: Check if both versions exist in the database
        db_schemas = await test_db.schema_revisions.find({
            "schema_id": original_schema_id
        }).to_list(None)
        
        assert len(db_schemas) == 2, "Should have two versions of the schema"
        
        # Step 4: Delete the schema using the original ID
        delete_response = client.delete(
            f"/v0/orgs/{TEST_ORG_ID}/schemas/{original_schema_id}",
            headers=get_auth_headers()
        )
        
        assert delete_response.status_code == 200
        
        # Step 5: Verify both versions are deleted from the database
        remaining_schemas = await test_db.schemas.find({
            "schema_id": original_schema_id
        }).to_list(None)
        
        assert len(remaining_schemas) == 0, "All versions of the schema should be deleted"
        
        # Step 6: Check that the version counter is also deleted
        version_counter = await test_db.schema_versions.find_one({
            "_id": original_schema_id
        })
        
        assert version_counter is None, "Version counter should be deleted"
        
        # Step 7: Verify that trying to get either version returns 404
        for schema_revid in [original_schema_revid, updated_schema_revid]:
            get_response = client.get(
                f"/v0/orgs/{TEST_ORG_ID}/schemas/{schema_revid}",
                headers=get_auth_headers()
            )
            assert get_response.status_code == 404, f"Schema with ID {schema_revid} should not exist"
        
    finally:
        pass  # mock_auth fixture handles cleanup
    
    logger.info(f"test_schema_version_deletion() end")

@pytest.mark.asyncio
async def test_schema_latest_version_listing(test_db, mock_auth):
    """Test that when listing schemas, only the latest versions are shown"""
    logger.info(f"test_schema_latest_version_listing() start")
    
    try:
        # Step 1: Create a schema
        original_schema_data = {
            "name": "Version Test Schema",
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "version_test_schema",
                    "schema": {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {
                            "field1": {
                                "type": "string",
                                "description": "First field"
                            }
                        },
                        "required": ["field1"]
                    },
                    "strict": True
                }
            }
        }
        
        create_response = client.post(
            f"/v0/orgs/{TEST_ORG_ID}/schemas",
            json=original_schema_data,
            headers=get_auth_headers()
        )
        
        assert create_response.status_code == 200
        original_schema = create_response.json()
        original_schema_revid = original_schema["schema_revid"]
        original_schema_id = original_schema["schema_id"]
        original_schema_version = original_schema["schema_version"]
        
        # Step 2: Update the schema with a new name
        renamed_schema_data = {
            "name": "Renamed Version Test Schema",
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "version_test_schema",
                    "schema": {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {
                            "field1": {
                                "type": "string",
                                "description": "First field"
                            }
                        },
                        "required": ["field1"]
                    },
                    "strict": True
                }
            }
        }
        
        update_response = client.put(
            f"/v0/orgs/{TEST_ORG_ID}/schemas/{original_schema_id}",
            json=renamed_schema_data,
            headers=get_auth_headers()
        )
        
        assert update_response.status_code == 200
        renamed_schema = update_response.json()
        renamed_schema_id = renamed_schema["schema_id"]
        renamed_schema_revid = renamed_schema["schema_revid"]
        assert original_schema_id == renamed_schema_id, "Schema ID should remain the same"
        assert original_schema_version == renamed_schema["schema_version"], "Schema version should not increase"
        
        # Step 3: List schemas and verify only the renamed version is returned
        list_response = client.get(
            f"/v0/orgs/{TEST_ORG_ID}/schemas",
            headers=get_auth_headers()
        )
        
        assert list_response.status_code == 200
        list_data = list_response.json()
        assert "schemas" in list_data
        
        # Find schemas with our schema_id
        matching_schemas = [s for s in list_data["schemas"] if s["schema_id"] == original_schema_id]
        
        # Verify we only have one result for our schema_id
        assert len(matching_schemas) == 1, "Should only return latest version in listing"
        
        # Verify the one returned is the renamed version
        assert matching_schemas[0]["name"] == "Renamed Version Test Schema"
        assert matching_schemas[0]["schema_revid"] == renamed_schema_revid  # Should be the newer ID
        
        # Step 4: Clean up
        client.delete(
            f"/v0/orgs/{TEST_ORG_ID}/schemas/{original_schema_id}",
            headers=get_auth_headers()
        )
        
    finally:
        pass  # mock_auth fixture handles cleanup
    
    logger.info(f"test_schema_latest_version_listing() end")

@pytest.mark.asyncio
async def test_schema_name_only_update(test_db, mock_auth):
    """Test that updating only the schema name doesn't create a new version"""
    logger.info(f"test_schema_name_only_update() start")
    
    try:
        # Step 1: Create a schema
        original_schema_data = {
            "name": "Original Schema Name",
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "test_schema",
                    "schema": {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {
                            "field1": {
                                "type": "string",
                                "description": "First field"
                            }
                        },
                        "required": ["field1"]
                    },
                    "strict": True
                }
            }
        }
        
        create_response = client.post(
            f"/v0/orgs/{TEST_ORG_ID}/schemas",
            json=original_schema_data,
            headers=get_auth_headers()
        )
        
        assert create_response.status_code == 200
        original_schema = create_response.json()
        original_schema_revid = original_schema["schema_revid"]
        original_schema_id = original_schema["schema_id"]
        original_schema_version = original_schema["schema_version"]
        
        # Step 2: Update only the name
        name_update_data = {
            "name": "Updated Schema Name",
            "response_format": original_schema["response_format"]
        }
        
        update_response = client.put(
            f"/v0/orgs/{TEST_ORG_ID}/schemas/{original_schema_id}",
            json=name_update_data,
            headers=get_auth_headers()
        )
        
        assert update_response.status_code == 200
        updated_schema = update_response.json()
        updated_schema_revid = updated_schema["schema_revid"]
        updated_schema_version = updated_schema["schema_version"]
        
        # Verify the ID remains the same (no new version created)
        assert original_schema_revid == updated_schema_revid, "ID should remain the same for name-only updates"
        assert original_schema_id == updated_schema["schema_id"]
        assert original_schema_version == updated_schema_version, "Version should remain the same for name-only updates"
        assert updated_schema["name"] == "Updated Schema Name", "Name should be updated"
        
        # Step 3: Verify only one version exists in the database
        db_schemas = await test_db.schema_revisions.find({
            "schema_id": original_schema_id
        }).to_list(None)
        
        assert len(db_schemas) == 1, "Should still have only one version of the schema"
        
        # Step 4: Update schema with a substantive change
        content_update_data = {
            "name": "Updated Schema Name",
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "test_schema",
                    "schema": {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {
                            "field1": {
                                "type": "string",
                                "description": "First field"
                            },
                            "field2": {
                                "type": "string",
                                "description": "Second field"
                            }
                        },
                        "required": ["field1", "field2"]
                    },
                    "strict": True
                }
            }
        }
        
        content_update_response = client.put(
            f"/v0/orgs/{TEST_ORG_ID}/schemas/{original_schema_id}",
            json=content_update_data,
            headers=get_auth_headers()
        )
        
        assert content_update_response.status_code == 200
        content_updated_schema = content_update_response.json()
        content_updated_schema_revid = content_updated_schema["schema_revid"]
        content_updated_schema_version = content_updated_schema["schema_version"]
        
        # Verify a new version was created
        assert original_schema_revid != content_updated_schema_revid, "ID should change for content updates"
        assert original_schema_version != content_updated_schema_version, "Version should increase for content updates"
        assert content_updated_schema_version > original_schema_version, "Version should increase for content updates"
        
        # Step 5: Verify two versions exist in the database
        db_schemas_after = await test_db.schema_revisions.find({
            "schema_id": original_schema_id
        }).to_list(None)
        
        assert len(db_schemas_after) == 2, "Should now have two revisions of the schema"
        
        # Clean up
        client.delete(
            f"/v0/orgs/{TEST_ORG_ID}/schemas/{original_schema_id}",
            headers=get_auth_headers()
        )
        
    finally:
        pass  # mock_auth fixture handles cleanup
    
    logger.info(f"test_schema_name_only_update() end")

@pytest.mark.asyncio
async def test_list_schema_versions(test_db, mock_auth):
    """Test listing all versions of a schema"""
    logger.info(f"test_list_schema_versions() start")
    
    try:
        # Step 1: Create a schema
        original_schema_data = {
            "name": "Version List Test Schema",
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "version_list_test",
                    "schema": {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {
                            "field1": {
                                "type": "string",
                                "description": "First field"
                            }
                        },
                        "required": ["field1"]
                    },
                    "strict": True
                }
            }
        }
        
        create_response = client.post(
            f"/v0/orgs/{TEST_ORG_ID}/schemas",
            json=original_schema_data,
            headers=get_auth_headers()
        )
        
        assert create_response.status_code == 200
        original_schema = create_response.json()
        original_schema_id = original_schema["schema_id"]
        original_schema_version = original_schema["schema_version"]
        
        # Step 2: Create a second version by updating the schema
        updated_schema_data = {
            "name": "Version List Test Schema",
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "version_list_test",
                    "schema": {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {
                            "field1": {
                                "type": "string",
                                "description": "First field"
                            },
                            "field2": {
                                "type": "string",
                                "description": "Second field"
                            }
                        },
                        "required": ["field1", "field2"]
                    },
                    "strict": True
                }
            }
        }
        
        update_response = client.put(
            f"/v0/orgs/{TEST_ORG_ID}/schemas/{original_schema_id}",
            json=updated_schema_data,
            headers=get_auth_headers()
        )
        
        assert update_response.status_code == 200
        updated_schema = update_response.json()
        updated_schema_version = updated_schema["schema_version"]
        assert updated_schema_version > original_schema_version
        
        # Step 3: List all versions
        versions_response = client.get(
            f"/v0/orgs/{TEST_ORG_ID}/schemas/{original_schema_id}/versions",
            headers=get_auth_headers()
        )
        
        assert versions_response.status_code == 200
        versions_data = versions_response.json()
        assert "schemas" in versions_data
        assert versions_data["total_count"] == 2
        assert len(versions_data["schemas"]) == 2
        
        # Step 4: Verify versions are sorted descending by version
        versions = versions_data["schemas"]
        assert versions[0]["schema_version"] > versions[1]["schema_version"]
        assert versions[0]["schema_version"] == updated_schema_version
        assert versions[1]["schema_version"] == original_schema_version
        
        # Step 5: Verify all versions have the same schema_id and name
        for version in versions:
            assert version["schema_id"] == original_schema_id
            assert version["name"] == "Version List Test Schema"
            assert "schema_revid" in version
        
        # Step 6: Test with non-existent schema_id
        fake_id = str(ObjectId())
        not_found_response = client.get(
            f"/v0/orgs/{TEST_ORG_ID}/schemas/{fake_id}/versions",
            headers=get_auth_headers()
        )
        assert not_found_response.status_code == 404
        
        # Clean up
        client.delete(
            f"/v0/orgs/{TEST_ORG_ID}/schemas/{original_schema_id}",
            headers=get_auth_headers()
        )
        
    finally:
        pass  # mock_auth fixture handles cleanup
    
    logger.info(f"test_list_schema_versions() end")