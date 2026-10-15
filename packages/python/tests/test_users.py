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
async def test_list_users(test_db, mock_auth):
    """Test listing users endpoint"""
    logger.info(f"test_list_users() start")
    
    try:
        # List users
        list_response = client.get(
            "/v0/account/users",
            headers=get_auth_headers()
        )
        
        assert list_response.status_code == 200
        list_data = list_response.json()
        assert "users" in list_data
        assert "total_count" in list_data
        assert "skip" in list_data
        
        # Test with organization_id filter
        list_with_org_response = client.get(
            f"/v0/account/users?organization_id={TEST_ORG_ID}",
            headers=get_auth_headers()
        )
        
        assert list_with_org_response.status_code == 200
        
        # Test with pagination
        list_with_pagination_response = client.get(
            "/v0/account/users?skip=0&limit=5",
            headers=get_auth_headers()
        )
        
        assert list_with_pagination_response.status_code == 200
        pagination_data = list_with_pagination_response.json()
        assert len(pagination_data["users"]) <= 5
        
    finally:
        pass  # mock_auth fixture handles cleanup
    
    logger.info(f"test_list_users() end")


@pytest.mark.asyncio
async def test_list_users_tolerates_null_email(test_db, mock_auth):
    """Users without email (e.g. legacy OAuth adapter rows) must not break list_users."""
    null_email_user_id = str(ObjectId())
    await test_db.users.insert_one({
        "_id": ObjectId(null_email_user_id),
        "email": None,
        "name": "Incomplete Account",
        "created_at": datetime.now(UTC),
    })
    await test_db.organizations.update_one(
        {"_id": ObjectId(TEST_ORG_ID)},
        {"$push": {"members": {"user_id": null_email_user_id, "permission_group_ids": ["builder"]}}},
    )

    list_response = client.get(
        f"/v0/account/users?organization_id={TEST_ORG_ID}",
        headers=get_auth_headers(),
    )
    assert list_response.status_code == 200
    users = list_response.json()["users"]
    incomplete = next(u for u in users if u["id"] == null_email_user_id)
    assert incomplete["email"] == ""

    all_users_response = client.get(
        "/v0/account/users?limit=100",
        headers=get_auth_headers(),
    )
    assert all_users_response.status_code == 200


@pytest.mark.asyncio
async def test_user_lifecycle(test_db, mock_auth):
    """Test the complete user lifecycle (create, get, update, delete)"""
    logger.info(f"test_user_lifecycle() start")
    
    try:
        # Step 1: Create a user
        user_data = {
            "email": "testuser@example.com",
            "name": "Test User",
            "password": "securePassword123"
        }
        
        create_response = client.post(
            "/v0/account/users",
            json=user_data,
            headers=get_auth_headers()
        )
        
        assert create_response.status_code == 200
        user_result = create_response.json()
        assert "id" in user_result
        assert user_result["email"] == "testuser@example.com"
        assert user_result["name"] == "Test User"
        assert user_result["is_sysadmin"] is False
        assert "email_verified" in user_result
        assert "has_password" in user_result
        assert user_result["has_password"] is True
        
        user_id = user_result["id"]
        
        # Step 2: Get the specific user
        get_response = client.get(
            f"/v0/account/users?user_id={user_id}",
            headers=get_auth_headers()
        )
        
        assert get_response.status_code == 200
        get_data = get_response.json()
        assert "users" in get_data
        assert len(get_data["users"]) == 1
        assert get_data["users"][0]["id"] == user_id
        assert get_data["users"][0]["email"] == "testuser@example.com"
        
        # Step 3: Update the user
        update_data = {
            "name": "Updated Test User",
            "is_sysadmin": True,
        }
        
        update_response = client.put(
            f"/v0/account/users/{user_id}",
            json=update_data,
            headers=get_auth_headers()
        )
        
        assert update_response.status_code == 200
        update_result = update_response.json()
        assert update_result["name"] == "Updated Test User"
        assert update_result["is_sysadmin"] is True
        
        # Step 4: Update user password
        password_update_data = {
            "password": "newSecurePassword456"
        }
        
        password_update_response = client.put(
            f"/v0/account/users/{user_id}",
            json=password_update_data,
            headers=get_auth_headers()
        )
        
        assert password_update_response.status_code == 200
        password_update_result = password_update_response.json()
        assert password_update_result["has_password"] is True
        
        # Step 5: Update email verification status
        verification_update_data = {
            "email_verified": True
        }

        verification_update_response = client.put(
            f"/v0/account/users/{user_id}",
            json=verification_update_data,
            headers=get_auth_headers()
        )

        assert verification_update_response.status_code == 200
        verification_update_result = verification_update_response.json()
        assert verification_update_result["email_verified"] is True
        
        # Step 6: Delete the user
        delete_response = client.delete(
            f"/v0/account/users/{user_id}",
            headers=get_auth_headers()
        )
        
        assert delete_response.status_code == 200
        
        # Step 7: Verify user is deleted by trying to get it
        # The API returns 404 when trying to get a deleted user by ID
        get_deleted_response = client.get(
            f"/v0/account/users?user_id={user_id}",
            headers=get_auth_headers()
        )
        
        # Update assertion to expect 404 Not Found
        assert get_deleted_response.status_code == 404
        
    finally:
        pass  # mock_auth fixture handles cleanup
    
    logger.info(f"test_user_lifecycle() end")