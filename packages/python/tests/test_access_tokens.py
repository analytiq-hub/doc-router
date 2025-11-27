import pytest
from bson import ObjectId
import os
import logging

# Import shared test utilities
from .conftest_utils import (
    client, TEST_ORG_ID, 
    get_auth_headers,
    get_token_headers,
)
import analytiq_data as ad

logger = logging.getLogger(__name__)

# Check that ENV is set to pytest
assert os.environ["ENV"] == "pytest"

@pytest.mark.asyncio
async def test_access_tokens(test_db, mock_auth):
    """Test the complete access token lifecycle"""
    logger.info(f"test_access_tokens() start")
    
    try:
        # Step 1: Create an access token
        token_data = {
            "name": "Test API Token",
            "lifetime": 30  # 30 days
        }
        
        create_response = client.post(
            f"/v0/orgs/{TEST_ORG_ID}/access_tokens",
            json=token_data,
            headers=get_auth_headers()
        )
        
        assert create_response.status_code == 200
        token_result = create_response.json()
        assert "id" in token_result
        assert token_result["name"] == "Test API Token"
        assert token_result["lifetime"] == 30
        assert "token" in token_result  # The actual token value
        
        token_id = token_result["id"]
        api_token = token_result["token"]  # Store the actual token value
        
        # Step 2: List access tokens to verify it was created
        list_response = client.get(
            f"/v0/orgs/{TEST_ORG_ID}/access_tokens",
            headers=get_auth_headers()
        )
        
        assert list_response.status_code == 200
        list_data = list_response.json()
        assert "access_tokens" in list_data
        
        # Find our token in the list
        created_token = next((token for token in list_data["access_tokens"] if token["id"] == token_id), None)
        assert created_token is not None
        assert created_token["name"] == "Test API Token"
        assert created_token["lifetime"] == 30
        
        # Step 3: Test the token functionality by calling the list documents API
        # Temporarily clear the mock authentication to test real token authentication
        from app.main import app
        original_overrides = app.dependency_overrides.copy()
        app.dependency_overrides.clear()
        
        try:
            # Create headers using the actual API token
            token_headers = get_token_headers(api_token)
            
            # Call the list documents API using the token
            docs_response = client.get(
                f"/v0/orgs/{TEST_ORG_ID}/documents",
                headers=token_headers
            )
            
            # The API should return 200 even if there are no documents
            assert docs_response.status_code == 200
            docs_data = docs_response.json()
            assert "documents" in docs_data
            assert "total_count" in docs_data
            assert "skip" in docs_data
        finally:
            # Restore the mock authentication
            app.dependency_overrides = original_overrides
        
        # Step 4: Delete the access token
        delete_response = client.delete(
            f"/v0/orgs/{TEST_ORG_ID}/access_tokens/{token_id}",
            headers=get_auth_headers()
        )
        
        assert delete_response.status_code == 200
        
        # Step 5: List access tokens again to verify it was deleted
        list_after_delete_response = client.get(
            f"/v0/orgs/{TEST_ORG_ID}/access_tokens",
            headers=get_auth_headers()
        )
        
        assert list_after_delete_response.status_code == 200
        list_after_delete_data = list_after_delete_response.json()
        
        # Verify the token is no longer in the list
        deleted_token = next((token for token in list_after_delete_data["access_tokens"] if token["id"] == token_id), None)
        assert deleted_token is None, "Token should have been deleted"
        
        # Step 6: Negative test - verify the deleted token no longer works
        # Temporarily clear the mock authentication to test real token authentication
        app.dependency_overrides.clear()
        
        try:
            # Try to use the deleted token to call the list documents API
            deleted_token_headers = get_token_headers(api_token)
            
            # This should fail with 401 Unauthorized since the token was deleted
            docs_response_with_deleted_token = client.get(
                f"/v0/orgs/{TEST_ORG_ID}/documents",
                headers=deleted_token_headers
            )
            
            # Verify that the API call fails with 401 Unauthorized
            assert docs_response_with_deleted_token.status_code == 401, "Deleted token should not be accepted"
            
            # Optionally check the error message
            error_data = docs_response_with_deleted_token.json()
            assert "detail" in error_data
            assert "Invalid authentication credentials" in error_data["detail"]
        finally:
            # Restore the mock authentication
            app.dependency_overrides = original_overrides
        
    finally:
        pass  # mock_auth fixture handles cleanup
    
    logger.info(f"test_access_tokens() end")

@pytest.mark.asyncio
async def test_account_access_tokens(test_db, mock_auth):
    """Test the account-level access token lifecycle"""
    logger.info(f"test_account_access_tokens() start")
    
    try:
        # Step 1: Create an account-level access token
        token_data = {
            "name": "Test Account API Token",
            "lifetime": 60  # 60 days
        }
        
        create_response = client.post(
            f"/v0/account/access_tokens",
            json=token_data,
            headers=get_auth_headers()
        )
        
        assert create_response.status_code == 200
        token_result = create_response.json()
        assert "id" in token_result
        assert token_result["name"] == "Test Account API Token"
        assert token_result["lifetime"] == 60
        assert "token" in token_result  # The actual token value
        assert token_result["organization_id"] is None  # Should be None for account tokens
        
        token_id = token_result["id"]
        api_token = token_result["token"]  # Store the actual token value
        
        # Step 2: List account access tokens to verify it was created
        list_response = client.get(
            f"/v0/account/access_tokens",
            headers=get_auth_headers()
        )
        
        assert list_response.status_code == 200
        list_data = list_response.json()
        assert "access_tokens" in list_data
        
        # Find our token in the list
        created_token = next((token for token in list_data["access_tokens"] if token["id"] == token_id), None)
        assert created_token is not None
        assert created_token["name"] == "Test Account API Token"
        assert created_token["lifetime"] == 60
        assert created_token["organization_id"] is None
        
        # Step 3: Test the token functionality by calling the list organizations API
        # Temporarily clear the mock authentication to test real token authentication
        from app.main import app
        original_overrides = app.dependency_overrides.copy()
        app.dependency_overrides.clear()
        
        try:
            # Create headers using the actual API token
            token_headers = get_token_headers(api_token)
            
            # Call the list organizations API using the token
            orgs_response = client.get(
                f"/v0/account/organizations",
                headers=token_headers
            )
            
            # The API should return 200 and show organizations for the user
            assert orgs_response.status_code == 200
            orgs_data = orgs_response.json()
            assert "organizations" in orgs_data
            
            # Verify that the test organization is in the list
            test_org_found = any(org["id"] == TEST_ORG_ID for org in orgs_data["organizations"])
            assert test_org_found, "Test organization should be visible with account token"
        finally:
            # Restore the mock authentication
            app.dependency_overrides = original_overrides
        
        # Step 4: Delete the access token
        delete_response = client.delete(
            f"/v0/account/access_tokens/{token_id}",
            headers=get_auth_headers()
        )
        
        assert delete_response.status_code == 200
        
        # Step 5: List access tokens again to verify it was deleted
        list_after_delete_response = client.get(
            f"/v0/account/access_tokens",
            headers=get_auth_headers()
        )
        
        assert list_after_delete_response.status_code == 200
        list_after_delete_data = list_after_delete_response.json()
        
        # Verify the token is no longer in the list
        deleted_token = next((token for token in list_after_delete_data["access_tokens"] if token["id"] == token_id), None)
        assert deleted_token is None, "Token should have been deleted"
        
        # Step 6: Negative test - verify the deleted token no longer works
        # Temporarily clear the mock authentication to test real token authentication
        app.dependency_overrides.clear()
        
        try:
            # Try to use the deleted token to call the list organizations API
            deleted_token_headers = get_token_headers(api_token)
            
            # This should fail with 401 Unauthorized since the token was deleted
            orgs_response_with_deleted_token = client.get(
                f"/v0/account/organizations",
                headers=deleted_token_headers
            )
            
            # Verify that the API call fails with 401 Unauthorized
            assert orgs_response_with_deleted_token.status_code == 401, "Deleted token should not be accepted"
            
            # Optionally check the error message
            error_data = orgs_response_with_deleted_token.json()
            assert "detail" in error_data
            assert "Invalid authentication credentials" in error_data["detail"]
        finally:
            # Restore the mock authentication
            app.dependency_overrides = original_overrides
        
    finally:
        pass  # mock_auth fixture handles cleanup
    
    logger.info(f"test_account_access_tokens() end")

@pytest.mark.asyncio
async def test_get_organization_from_token(test_db, mock_auth):
    """Test the get_organization_from_token endpoint"""
    logger.info(f"test_get_organization_from_token() start")
    
    try:
        # Step 1: Create an organization-level access token
        org_token_data = {
            "name": "Test Org API Token",
            "lifetime": 30
        }
        
        create_org_token_response = client.post(
            f"/v0/orgs/{TEST_ORG_ID}/access_tokens",
            json=org_token_data,
            headers=get_auth_headers()
        )
        
        assert create_org_token_response.status_code == 200
        org_token_result = create_org_token_response.json()
        org_api_token = org_token_result["token"]
        
        # Step 2: Create an account-level access token
        account_token_data = {
            "name": "Test Account API Token",
            "lifetime": 60
        }
        
        create_account_token_response = client.post(
            f"/v0/account/access_tokens",
            json=account_token_data,
            headers=get_auth_headers()
        )
        
        assert create_account_token_response.status_code == 200
        account_token_result = create_account_token_response.json()
        account_api_token = account_token_result["token"]
        
        # Step 3: Test resolving organization token to organization ID
        resolve_org_response = client.get(
            f"/v0/account/token/organization?token={org_api_token}"
        )
        
        assert resolve_org_response.status_code == 200
        org_resolve_data = resolve_org_response.json()
        assert "organization_id" in org_resolve_data
        assert org_resolve_data["organization_id"] == TEST_ORG_ID
        
        # Step 4: Test resolving account token to organization ID (should return null)
        resolve_account_response = client.get(
            f"/v0/account/token/organization?token={account_api_token}"
        )
        
        assert resolve_account_response.status_code == 200
        account_resolve_data = resolve_account_response.json()
        assert "organization_id" in account_resolve_data
        assert account_resolve_data["organization_id"] is None
        
        # Step 5: Test with invalid token
        invalid_token_response = client.get(
            f"/v0/account/token/organization?token=invalid_token_12345"
        )
        
        assert invalid_token_response.status_code == 401
        invalid_token_data = invalid_token_response.json()
        assert "detail" in invalid_token_data
        assert invalid_token_data["detail"] == "Invalid token"
        
        # Step 6: Test with empty token
        empty_token_response = client.get(
            f"/v0/account/token/organization?token="
        )
        
        assert empty_token_response.status_code == 401  # Invalid token for empty string
        
        # Step 7: Test with missing token parameter
        missing_token_response = client.get(
            f"/v0/account/token/organization"
        )
        
        assert missing_token_response.status_code == 422  # Validation error for missing required parameter
        
        # Step 8: Clean up - delete the tokens
        org_token_id = org_token_result["id"]
        account_token_id = account_token_result["id"]
        
        # Delete org token
        delete_org_response = client.delete(
            f"/v0/orgs/{TEST_ORG_ID}/access_tokens/{org_token_id}",
            headers=get_auth_headers()
        )
        assert delete_org_response.status_code == 200
        
        # Delete account token
        delete_account_response = client.delete(
            f"/v0/account/access_tokens/{account_token_id}",
            headers=get_auth_headers()
        )
        assert delete_account_response.status_code == 200
        
        # Step 9: Test that deleted tokens no longer resolve
        deleted_org_response = client.get(
            f"/v0/account/token/organization?token={org_api_token}"
        )
        assert deleted_org_response.status_code == 401
        
        deleted_account_response = client.get(
            f"/v0/account/token/organization?token={account_api_token}"
        )
        assert deleted_account_response.status_code == 401
        
    finally:
        pass  # mock_auth fixture handles cleanup
    
    logger.info(f"test_get_organization_from_token() end") 