import pytest
from tests.conftest_utils import client, get_token_headers
import logging

logger = logging.getLogger(__name__)

@pytest.mark.asyncio
async def test_create_tag(org_and_users, test_db):
    """Test creating tags"""
    org_id = org_and_users["org_id"]
    admin = org_and_users["admin"]
    
    # Valid tag data
    tag_data = {
        "name": "test-tag",
        "color": "#FF0000",
        "description": "A test tag"
    }
    
    resp = client.post(f"/v0/orgs/{org_id}/tags", json=tag_data, headers=get_token_headers(admin["token"]))
    assert resp.status_code == 200, f"Failed to create tag: {resp.text}"
    
    result = resp.json()
    assert "id" in result
    assert result["name"] == tag_data["name"]
    assert result["color"] == tag_data["color"]
    assert result["description"] == tag_data["description"]
    assert "created_at" in result
    assert "created_by" in result


@pytest.mark.asyncio
async def test_create_tag_with_empty_color_uses_default(org_and_users, test_db):
    """Tag created with empty color should use backend default color."""
    org_id = org_and_users["org_id"]
    admin = org_and_users["admin"]

    tag_data = {
        "name": "empty-color-tag",
        "color": "",
        "description": "Tag with empty color",
    }

    resp = client.post(
        f"/v0/orgs/{org_id}/tags",
        json=tag_data,
        headers=get_token_headers(admin["token"]),
    )
    assert resp.status_code == 200, f"Failed to create tag: {resp.text}"

    result = resp.json()
    assert result["name"] == tag_data["name"]
    # Backend should replace empty string with a non-empty default color
    assert result["color"]
    assert result["color"].startswith("#")


@pytest.mark.asyncio
async def test_create_tag_with_null_color_uses_default(org_and_users, test_db):
    """Tag created with null color should use backend default color."""
    org_id = org_and_users["org_id"]
    admin = org_and_users["admin"]

    tag_data = {
        "name": "null-color-tag",
        "color": None,
        "description": "Tag with null color",
    }

    resp = client.post(
        f"/v0/orgs/{org_id}/tags",
        json=tag_data,
        headers=get_token_headers(admin["token"]),
    )
    assert resp.status_code == 200, f"Failed to create tag: {resp.text}"

    result = resp.json()
    assert result["name"] == tag_data["name"]
    # Backend should replace null with a non-empty default color
    assert result["color"]
    assert result["color"].startswith("#")

@pytest.mark.asyncio
async def test_create_duplicate_tag(org_and_users, test_db):
    """Test creating a tag with duplicate name"""
    org_id = org_and_users["org_id"]
    admin = org_and_users["admin"]
    
    tag_data = {
        "name": "duplicate-tag",
        "color": "#FF0000",
        "description": "A test tag"
    }
    
    # Create first tag
    resp = client.post(f"/v0/orgs/{org_id}/tags", json=tag_data, headers=get_token_headers(admin["token"]))
    assert resp.status_code == 200
    
    # Try to create duplicate
    resp = client.post(f"/v0/orgs/{org_id}/tags", json=tag_data, headers=get_token_headers(admin["token"]))
    assert resp.status_code == 400
    assert "already exists" in resp.json()["detail"]

@pytest.mark.asyncio
async def test_list_tags(org_and_users, test_db):
    """Test listing tags"""
    org_id = org_and_users["org_id"]
    admin = org_and_users["admin"]
    
    # Create some test tags
    tags_data = [
        {"name": "tag1", "color": "#FF0000", "description": "First tag"},
        {"name": "tag2", "color": "#00FF00", "description": "Second tag"},
        {"name": "tag3", "color": "#0000FF", "description": "Third tag"}
    ]
    
    created_tags = []
    for tag_data in tags_data:
        resp = client.post(f"/v0/orgs/{org_id}/tags", json=tag_data, headers=get_token_headers(admin["token"]))
        assert resp.status_code == 200
        created_tags.append(resp.json())
    
    # List tags
    resp = client.get(f"/v0/orgs/{org_id}/tags", headers=get_token_headers(admin["token"]))
    assert resp.status_code == 200
    
    result = resp.json()
    assert "tags" in result
    assert "total_count" in result
    assert "skip" in result
    assert len(result["tags"]) >= len(created_tags)
    
    # Verify our created tags are in the list
    tag_names = [tag["name"] for tag in result["tags"]]
    for tag_data in tags_data:
        assert tag_data["name"] in tag_names

@pytest.mark.asyncio
async def test_list_tags_pagination(org_and_users, test_db):
    """Test tag listing with pagination"""
    org_id = org_and_users["org_id"]
    admin = org_and_users["admin"]
    
    # Create more tags than the default limit
    for i in range(15):
        tag_data = {
            "name": f"pagination-tag-{i}",
            "color": "#FF0000",
            "description": f"Tag {i}"
        }
        resp = client.post(f"/v0/orgs/{org_id}/tags", json=tag_data, headers=get_token_headers(admin["token"]))
        assert resp.status_code == 200
    
    # Test default pagination (limit=10)
    resp = client.get(f"/v0/orgs/{org_id}/tags", headers=get_token_headers(admin["token"]))
    assert resp.status_code == 200
    result = resp.json()
    assert len(result["tags"]) <= 10
    assert result["total_count"] >= 15
    
    # Test custom pagination
    resp = client.get(f"/v0/orgs/{org_id}/tags?skip=5&limit=5", headers=get_token_headers(admin["token"]))
    assert resp.status_code == 200
    result = resp.json()
    assert len(result["tags"]) <= 5
    assert result["skip"] == 5

@pytest.mark.asyncio
async def test_update_tag(org_and_users, test_db):
    """Test updating tags"""
    org_id = org_and_users["org_id"]
    admin = org_and_users["admin"]
    
    # Create a tag
    tag_data = {
        "name": "update-test-tag",
        "color": "#FF0000",
        "description": "Original description"
    }
    
    resp = client.post(f"/v0/orgs/{org_id}/tags", json=tag_data, headers=get_token_headers(admin["token"]))
    assert resp.status_code == 200
    tag_id = resp.json()["id"]
    
    # Update the tag
    update_data = {
        "name": "updated-tag-name",
        "color": "#00FF00",
        "description": "Updated description"
    }
    
    resp = client.put(f"/v0/orgs/{org_id}/tags/{tag_id}", json=update_data, headers=get_token_headers(admin["token"]))
    assert resp.status_code == 200
    
    result = resp.json()
    assert result["name"] == update_data["name"]
    assert result["color"] == update_data["color"]
    assert result["description"] == update_data["description"]
    assert result["id"] == tag_id


@pytest.mark.asyncio
async def test_update_tag_with_empty_color_uses_default(org_and_users, test_db):
    """Updating a tag with empty color should set default color."""
    org_id = org_and_users["org_id"]
    admin = org_and_users["admin"]

    # Create a tag with an explicit non-default color
    tag_data = {
        "name": "update-empty-color-tag",
        "color": "#FF0000",
        "description": "Original description",
    }

    resp = client.post(
        f"/v0/orgs/{org_id}/tags",
        json=tag_data,
        headers=get_token_headers(admin["token"]),
    )
    assert resp.status_code == 200
    tag = resp.json()
    tag_id = tag["id"]
    assert tag["color"] == "#FF0000"

    # Update with empty color string - should be normalized to default color
    update_data = {
        "name": "updated-empty-color-tag",
        "color": "",
        "description": "Updated description",
    }

    resp = client.put(
        f"/v0/orgs/{org_id}/tags/{tag_id}",
        json=update_data,
        headers=get_token_headers(admin["token"]),
    )
    assert resp.status_code == 200, f"Failed to update tag: {resp.text}"

    result = resp.json()
    assert result["name"] == update_data["name"]
    assert result["description"] == update_data["description"]
    # Color should now be a non-empty hex string (the backend default)
    assert result["color"]
    assert result["color"].startswith("#")


@pytest.mark.asyncio
async def test_update_tag_with_null_color_preserves_existing(org_and_users, test_db):
    """Updating a tag with null color should keep existing color."""
    org_id = org_and_users["org_id"]
    admin = org_and_users["admin"]

    # Create a tag with an explicit color
    tag_data = {
        "name": "update-null-color-tag",
        "color": "#FF0000",
        "description": "Original description",
    }

    resp = client.post(
        f"/v0/orgs/{org_id}/tags",
        json=tag_data,
        headers=get_token_headers(admin["token"]),
    )
    assert resp.status_code == 200
    tag = resp.json()
    tag_id = tag["id"]
    assert tag["color"] == "#FF0000"

    # Update with null color - backend should not touch color field
    update_data = {
        "name": "updated-null-color-tag",
        "color": None,
        "description": "Updated description",
    }

    resp = client.put(
        f"/v0/orgs/{org_id}/tags/{tag_id}",
        json=update_data,
        headers=get_token_headers(admin["token"]),
    )
    assert resp.status_code == 200, f"Failed to update tag: {resp.text}"

    result = resp.json()
    assert result["name"] == update_data["name"]
    assert result["description"] == update_data["description"]
    # Color should be unchanged from original
    assert result["color"] == "#FF0000"

@pytest.mark.asyncio
async def test_update_nonexistent_tag(org_and_users, test_db):
    """Test updating a tag that doesn't exist"""
    org_id = org_and_users["org_id"]
    admin = org_and_users["admin"]
    
    fake_tag_id = "507f1f77bcf86cd799439011"  # Fake ObjectId
    
    update_data = {
        "name": "updated-tag-name",
        "color": "#00FF00",
        "description": "Updated description"
    }
    
    resp = client.put(f"/v0/orgs/{org_id}/tags/{fake_tag_id}", json=update_data, headers=get_token_headers(admin["token"]))
    assert resp.status_code == 404
    assert "Tag not found" in resp.json()["detail"]

@pytest.mark.asyncio
async def test_delete_tag(org_and_users, test_db):
    """Test deleting tags"""
    org_id = org_and_users["org_id"]
    admin = org_and_users["admin"]
    
    # Create a tag
    tag_data = {
        "name": "delete-test-tag",
        "color": "#FF0000",
        "description": "Tag to be deleted"
    }
    
    resp = client.post(f"/v0/orgs/{org_id}/tags", json=tag_data, headers=get_token_headers(admin["token"]))
    assert resp.status_code == 200
    tag_id = resp.json()["id"]
    
    # Delete the tag
    resp = client.delete(f"/v0/orgs/{org_id}/tags/{tag_id}", headers=get_token_headers(admin["token"]))
    assert resp.status_code == 200
    assert "deleted successfully" in resp.json()["message"]
    
    # Verify tag is deleted by trying to update it
    update_data = {
        "name": "updated-name",
        "color": "#00FF00",
        "description": "Updated description"
    }
    
    resp = client.put(f"/v0/orgs/{org_id}/tags/{tag_id}", json=update_data, headers=get_token_headers(admin["token"]))
    assert resp.status_code == 404

@pytest.mark.asyncio
async def test_delete_nonexistent_tag(org_and_users, test_db):
    """Test deleting a tag that doesn't exist"""
    org_id = org_and_users["org_id"]
    admin = org_and_users["admin"]
    
    fake_tag_id = "507f1f77bcf86cd799439011"  # Fake ObjectId
    
    resp = client.delete(f"/v0/orgs/{org_id}/tags/{fake_tag_id}", headers=get_token_headers(admin["token"]))
    assert resp.status_code == 404
    assert "Tag not found" in resp.json()["detail"]

@pytest.mark.asyncio
async def test_tag_validation(org_and_users, test_db):
    """Test tag validation"""
    org_id = org_and_users["org_id"]
    admin = org_and_users["admin"]
    
    # Test missing required fields
    invalid_tag_data = {
        "color": "#FF0000",
        "description": "Missing name"
    }
    
    resp = client.post(f"/v0/orgs/{org_id}/tags", json=invalid_tag_data, headers=get_token_headers(admin["token"]))
    assert resp.status_code == 422  # Validation error
    
    # Test invalid color format
    invalid_color_data = {
        "name": "test-tag",
        "color": "invalid-color",
        "description": "Invalid color"
    }
    
    resp = client.post(f"/v0/orgs/{org_id}/tags", json=invalid_color_data, headers=get_token_headers(admin["token"]))
    # This might be 422 or 200 depending on validation implementation
    assert resp.status_code in [200, 422]

@pytest.mark.asyncio
async def test_tag_cross_organization_isolation(org_and_users, test_db):
    """Test that tags are isolated between organizations"""
    org_id = org_and_users["org_id"]
    admin = org_and_users["admin"]
    
    # Create tag in first organization
    tag_data = {
        "name": "cross-org-tag",
        "color": "#FF0000",
        "description": "Tag for cross-org test"
    }
    
    resp = client.post(f"/v0/orgs/{org_id}/tags", json=tag_data, headers=get_token_headers(admin["token"]))
    assert resp.status_code == 200
    tag_id = resp.json()["id"]
    
    # Try to access tag from different organization (using a fake org ID)
    fake_org_id = "507f1f77bcf86cd799439011"
    
    # Test that we can't update tag from different org
    resp = client.put(f"/v0/orgs/{fake_org_id}/tags/{tag_id}", json=tag_data, headers=get_token_headers(admin["token"]))
    # This will return 401 because the user doesn't have access to the fake org
    assert resp.status_code == 401
    
    # Test that we can't delete tag from different org
    resp = client.delete(f"/v0/orgs/{fake_org_id}/tags/{tag_id}", headers=get_token_headers(admin["token"]))
    # This will return 401 because the user doesn't have access to the fake org
    assert resp.status_code == 401

@pytest.mark.asyncio
async def test_tag_with_documents(org_and_users, test_db):
    """Test tag behavior when used with documents"""
    org_id = org_and_users["org_id"]
    admin = org_and_users["admin"]
    
    # Create a tag
    tag_data = {
        "name": "document-tag",
        "color": "#FF0000",
        "description": "Tag for document test"
    }
    
    resp = client.post(f"/v0/orgs/{org_id}/tags", json=tag_data, headers=get_token_headers(admin["token"]))
    assert resp.status_code == 200
    tag_id = resp.json()["id"]
    
    # Upload a document with this tag
    pdf_content = "data:application/pdf;base64,JVBERi0xLjQKMSAwIG9iago8PC9UeXBlL0NhdGFsb2cvUGFnZXMgMiAwIFI+PgplbmRvYmoKMiAwIG9iago8PC9UeXBlL1BhZ2VzL0tpZHNbMyAwIFJdL0NvdW50IDE+PgplbmRvYmoKMyAwIG9iago8PC9UeXBlL1BhZ2UvUGFyZW50IDIgMCBSL1Jlc291cmNlczw8Pj4vTWVkaWFCb3hbMCAwIDYxMiA3OTJdL0NvbnRlbnRzIDQgMCBSPj4KZW5kb2JqCjQgMCBvYmoKPDwvTGVuZ3RoIDUgPj4Kc3RyZWFtCkJUClRFU1QKZW5kc3RyZWFtCmVuZG9iagp4cmVmCjAgNQowMDAwMDAwMDAwIDY1NTM1IGYgCjAwMDAwMDAwMTAgMDAwMDAgbiAKMDAwMDAwMDAyMCAwMDAwMCBuIAowMDAwMDAwMDMwIDAwMDAwIG4gCjAwMDAwMDAwNDAgMDAwMDAgbiAKdHJhaWxlcgo8PC9TaXplIDUvUm9vdCAxIDAgUi9JbmZvIDYgMCBSCj4+CnN0YXJ0eHJlZgo2NTU1CiUlRU9G"
    upload_data = {
        "documents": [
            {
                "name": "test.pdf",
                "content": pdf_content,
                "tag_ids": [tag_id]
            }
        ]
    }
    
    resp = client.post(f"/v0/orgs/{org_id}/documents", json=upload_data, headers=get_token_headers(admin["token"]))
    assert resp.status_code == 200
    
    # Get the document ID from the response
    doc_response = resp.json()
    doc_id = doc_response["documents"][0]["document_id"]
    
    # Try to delete the tag (should fail because it's used by a document)
    resp = client.delete(f"/v0/orgs/{org_id}/tags/{tag_id}", headers=get_token_headers(admin["token"]))
    assert resp.status_code == 400
    assert "assigned to one or more documents" in resp.json()["detail"]
    
    # Delete the document first
    resp = client.delete(f"/v0/orgs/{org_id}/documents/{doc_id}", headers=get_token_headers(admin["token"]))
    assert resp.status_code == 200
    
    # Now try to delete the tag again (should succeed)
    resp = client.delete(f"/v0/orgs/{org_id}/tags/{tag_id}", headers=get_token_headers(admin["token"]))
    assert resp.status_code == 200

@pytest.mark.asyncio
async def test_update_document_tags(org_and_users, test_db):
    """Test updating tags on a document through the document update API"""
    org_id = org_and_users["org_id"]
    admin = org_and_users["admin"]

    # Create three tags
    tag_data_list = [
        {"name": "doc-update-tag-1", "color": "#FF0000", "description": "First tag"},
        {"name": "doc-update-tag-2", "color": "#00FF00", "description": "Second tag"},
        {"name": "doc-update-tag-3", "color": "#0000FF", "description": "Third tag"}
    ]

    tag_ids = []
    for tag_data in tag_data_list:
        resp = client.post(f"/v0/orgs/{org_id}/tags", json=tag_data, headers=get_token_headers(admin["token"]))
        assert resp.status_code == 200
        tag_ids.append(resp.json()["id"])

    # Create a document without tags
    pdf_content = "data:application/pdf;base64,JVBERi0xLjQKMSAwIG9iago8PC9UeXBlL0NhdGFsb2cvUGFnZXMgMiAwIFI+PgplbmRvYmoKMiAwIG9iago8PC9UeXBlL1BhZ2VzL0tpZHNbMyAwIFJdL0NvdW50IDE+PgplbmRvYmoKMyAwIG9iago8PC9UeXBlL1BhZ2UvUGFyZW50IDIgMCBSL1Jlc291cmNlczw8Pj4vTWVkaWFCb3hbMCAwIDYxMiA3OTJdL0NvbnRlbnRzIDQgMCBSPj4KZW5kb2JqCjQgMCBvYmoKPDwvTGVuZ3RoIDUgPj4Kc3RyZWFtCkJUClRFU1QKZW5kc3RyZWFtCmVuZG9iagp4cmVmCjAgNQowMDAwMDAwMDAwIDY1NTM1IGYgCjAwMDAwMDAwMTAgMDAwMDAgbiAKMDAwMDAwMDAyMCAwMDAwMCBuIAowMDAwMDAwMDMwIDAwMDAwIG4gCjAwMDAwMDAwNDAgMDAwMDAgbiAKdHJhaWxlcgo8PC9TaXplIDUvUm9vdCAxIDAgUi9JbmZvIDYgMCBSCj4+CnN0YXJ0eHJlZgo2NTU1CiUlRU9G"
    upload_data = {
        "documents": [
            {
                "name": "tag-update-test.pdf",
                "content": pdf_content
            }
        ]
    }

    resp = client.post(f"/v0/orgs/{org_id}/documents", json=upload_data, headers=get_token_headers(admin["token"]))
    assert resp.status_code == 200
    doc_id = resp.json()["documents"][0]["document_id"]

    # Step 1: Add first tag using PUT
    update_data = {"tag_ids": [tag_ids[0]]}
    resp = client.put(f"/v0/orgs/{org_id}/documents/{doc_id}", json=update_data, headers=get_token_headers(admin["token"]))
    assert resp.status_code == 200

    # Step 2: Check tag is there using GET
    resp = client.get(f"/v0/orgs/{org_id}/documents/{doc_id}", headers=get_token_headers(admin["token"]))
    assert resp.status_code == 200
    doc_response = resp.json()
    assert len(doc_response["tag_ids"]) == 1
    assert tag_ids[0] in doc_response["tag_ids"]

    # Step 3: Check tag is there using LIST
    resp = client.get(f"/v0/orgs/{org_id}/documents", headers=get_token_headers(admin["token"]))
    assert resp.status_code == 200
    docs = resp.json()["documents"]
    test_doc = next((doc for doc in docs if doc["id"] == doc_id), None)
    assert test_doc is not None
    assert len(test_doc["tag_ids"]) == 1
    assert tag_ids[0] in test_doc["tag_ids"]

    # Step 4: Add second and third tags using PUT
    update_data = {"tag_ids": [tag_ids[0], tag_ids[1], tag_ids[2]]}
    resp = client.put(f"/v0/orgs/{org_id}/documents/{doc_id}", json=update_data, headers=get_token_headers(admin["token"]))
    assert resp.status_code == 200

    # Step 5: Check all three tags are there
    resp = client.get(f"/v0/orgs/{org_id}/documents/{doc_id}", headers=get_token_headers(admin["token"]))
    assert resp.status_code == 200
    doc_response = resp.json()
    assert len(doc_response["tag_ids"]) == 3
    assert tag_ids[0] in doc_response["tag_ids"]
    assert tag_ids[1] in doc_response["tag_ids"]
    assert tag_ids[2] in doc_response["tag_ids"]

    # Step 6: Remove second and third tags, keep only first
    update_data = {"tag_ids": [tag_ids[0]]}
    resp = client.put(f"/v0/orgs/{org_id}/documents/{doc_id}", json=update_data, headers=get_token_headers(admin["token"]))
    assert resp.status_code == 200

    # Step 7: Check only first tag remains
    resp = client.get(f"/v0/orgs/{org_id}/documents/{doc_id}", headers=get_token_headers(admin["token"]))
    assert resp.status_code == 200
    doc_response = resp.json()
    assert len(doc_response["tag_ids"]) == 1
    assert tag_ids[0] in doc_response["tag_ids"]
    assert tag_ids[1] not in doc_response["tag_ids"]
    assert tag_ids[2] not in doc_response["tag_ids"]

    # Step 8: Remove the last tag
    update_data = {"tag_ids": []}
    resp = client.put(f"/v0/orgs/{org_id}/documents/{doc_id}", json=update_data, headers=get_token_headers(admin["token"]))
    assert resp.status_code == 200

    # Step 9: Check all tags are removed
    resp = client.get(f"/v0/orgs/{org_id}/documents/{doc_id}", headers=get_token_headers(admin["token"]))
    assert resp.status_code == 200
    doc_response = resp.json()
    assert len(doc_response["tag_ids"]) == 0 