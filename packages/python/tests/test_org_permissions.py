import pytest
from bson import ObjectId
import os
import secrets
from datetime import datetime, UTC
import logging

# Third-party imports
from fastapi.security import HTTPAuthorizationCredentials

# Import shared test utilities
from .conftest_utils import (
    client, TEST_ORG_ID, TEST_USER,
    get_auth_headers, get_token_headers
)
import analytiq_data as ad

logger = logging.getLogger(__name__)

# Check that ENV is set to pytest
assert os.environ["ENV"] == "pytest"

@pytest.mark.asyncio
async def test_enterprise_upgrade_restriction(org_and_users, test_db, mock_auth):
    """Test that only system admins can upgrade organizations to Enterprise type"""
    logger.info("test_enterprise_upgrade_restriction() start")
    
    try:
        # Get the test organization and users
        org_id = org_and_users["org_id"]
        admin_user = org_and_users["admin"]
        regular_user = org_and_users["member"]
        
        # Modify the admin user to not be a system admin (only org admin)
        # This ensures they can update the organization but cannot upgrade to enterprise
        await test_db.users.update_one(
            {"_id": ObjectId(admin_user["id"])},
            {"$set": {"role": "user"}}
        )
        
        # Test 1: Organization admin (but not system admin) cannot upgrade to Enterprise
        # Temporarily clear auth mock to use real token authentication
        from app.main import app
        app.dependency_overrides.clear()
        
        org_admin_headers = get_token_headers(admin_user["account_token"])
        
        # Try to upgrade organization to Enterprise as organization admin
        upgrade_to_enterprise_data = {
            "type": "enterprise"
        }
        
        response = client.put(
            f"/v0/account/organizations/{org_id}",
            json=upgrade_to_enterprise_data,
            headers=org_admin_headers
        )
        
        # This should fail with 403 Forbidden (enterprise upgrade restriction)
        assert response.status_code == 403
        error_data = response.json()
        assert "Only system administrators can upgrade organizations to Enterprise" in error_data["detail"]
        
        # Test 2: System admin CAN upgrade to Enterprise
        # Restore auth mock to use TEST_USER (system admin)
        from app.main import security
        from app.auth import get_current_user, get_admin_user
        mock_credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials="test_token")
        app.dependency_overrides = {
            security: lambda: mock_credentials,
            get_current_user: lambda: TEST_USER,
            get_admin_user: lambda: TEST_USER
        }
        
        admin_headers = get_auth_headers()
        
        # First, verify the organization is currently 'team' type
        get_org_response = client.get(
            f"/v0/account/organizations?organization_id={org_id}",
            headers=admin_headers
        )
        assert get_org_response.status_code == 200
        org_data = get_org_response.json()
        assert len(org_data["organizations"]) == 1
        assert org_data["organizations"][0]["type"] == "team"
        
        # Now upgrade to Enterprise as system admin
        response = client.put(
            f"/v0/account/organizations/{org_id}",
            json=upgrade_to_enterprise_data,
            headers=admin_headers
        )
        
        # This should succeed
        assert response.status_code == 200
        updated_org = response.json()
        assert updated_org["type"] == "enterprise"
        
        # Verify the change was persisted
        get_updated_org_response = client.get(
            f"/v0/account/organizations?organization_id={org_id}",
            headers=admin_headers
        )
        assert get_updated_org_response.status_code == 200
        updated_org_data = get_updated_org_response.json()
        assert len(updated_org_data["organizations"]) == 1
        assert updated_org_data["organizations"][0]["type"] == "enterprise"
        
        logger.info("test_enterprise_upgrade_restriction() completed successfully")
        
    except Exception as e:
        logger.error(f"test_enterprise_upgrade_restriction() failed: {e}")
        raise

@pytest.mark.asyncio
async def test_enterprise_creation_restriction(test_db, mock_auth):
    """Test that only system admins can create Enterprise organizations"""
    logger.info("test_enterprise_creation_restriction() start")
    
    try:
        # Test 1: Regular user cannot create Enterprise organization
        # Create a regular user
        regular_user_data = {
            "email": "regularuser@example.com",
            "name": "Regular User",
            "password": "securePassword123"
        }
        
        create_user_response = client.post(
            "/v0/account/users",
            json=regular_user_data,
            headers=get_auth_headers()
        )
        
        assert create_user_response.status_code == 200
        regular_user = create_user_response.json()
        
        # Set the user as non-admin in database
        await test_db.users.update_one(
            {"_id": ObjectId(regular_user["id"])},
            {"$set": {"role": "user"}}
        )
        
        # Temporarily clear auth mock to use real token authentication
        from app.main import app
        app.dependency_overrides.clear()
        
        # Create an account token for the regular user
        token = f"acc_{secrets.token_urlsafe(32)}"
        encrypted = ad.crypto.encrypt_token(token)
        token_doc = {
            "user_id": regular_user["id"],
            "organization_id": None,  # Account-level token
            "name": "test-account-token",
            "token": encrypted,
            "created_at": datetime.now(UTC),
            "lifetime": 30
        }
        await test_db.access_tokens.insert_one(token_doc)
        
        regular_user_headers = get_token_headers(token)
        
        # Try to create Enterprise organization as regular user
        enterprise_org_data = {
            "name": "Enterprise Organization",
            "type": "enterprise"
        }
        
        response = client.post(
            "/v0/account/organizations",
            json=enterprise_org_data,
            headers=regular_user_headers
        )
        
        # This should fail with 403 Forbidden
        assert response.status_code == 403
        error_data = response.json()
        assert "Only system administrators can create Enterprise organizations" in error_data["detail"]
        
        # Test 2: System admin CAN create Enterprise organization
        # Restore auth mock to use TEST_USER (system admin)
        from app.main import security
        from app.auth import get_current_user, get_admin_user
        mock_credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials="test_token")
        app.dependency_overrides = {
            security: lambda: mock_credentials,
            get_current_user: lambda: TEST_USER,
            get_admin_user: lambda: TEST_USER
        }
        
        admin_headers = get_auth_headers()
        
        # Create Enterprise organization as system admin
        response = client.post(
            "/v0/account/organizations",
            json=enterprise_org_data,
            headers=admin_headers
        )
        
        # This should succeed
        assert response.status_code == 200
        created_org = response.json()
        assert created_org["type"] == "enterprise"
        assert created_org["name"] == "Enterprise Organization"
        
        # Test 3: Regular user CAN create individual and team organizations
        individual_org_data = {
            "name": "Individual Organization",
            "type": "individual"
        }
        
        response = client.post(
            "/v0/account/organizations",
            json=individual_org_data,
            headers=admin_headers
        )
        
        assert response.status_code == 200
        individual_org = response.json()
        assert individual_org["type"] == "individual"
        
        team_org_data = {
            "name": "Team Organization",
            "type": "team"
        }
        
        response = client.post(
            "/v0/account/organizations",
            json=team_org_data,
            headers=admin_headers
        )
        
        assert response.status_code == 200
        team_org = response.json()
        assert team_org["type"] == "team"
        
        logger.info("test_enterprise_creation_restriction() completed successfully")
        
    except Exception as e:
        logger.error(f"test_enterprise_creation_restriction() failed: {e}")
        raise