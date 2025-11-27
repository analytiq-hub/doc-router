import pytest
from unittest.mock import patch
from bson import ObjectId
import os
from datetime import datetime, UTC
import re
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

# Create a mock for send_email function
@pytest.fixture
def mock_send_email():
    """Mock the send_email function to prevent actual emails during tests"""
    with patch("app.email_utils.send_email") as mock_send_email:
        mock_send_email.return_value = {
            "success": True, 
            "message": "Email mock: Message would be sent"
        }
        yield mock_send_email

@pytest.mark.asyncio
async def test_email_verification(test_db, mock_auth, mock_send_email):
    """Test email verification endpoints"""
    logger.info(f"test_email_verification() start")
    
    try:
        # Create an invitation for a new user
        invitation_data = {
            "email": "verify@example.com",
            "organization_id": TEST_ORG_ID,
            "role": "user"
        }
        
        create_invitation_response = client.post(
            "/v0/account/email/invitations",
            json=invitation_data,
            headers=get_auth_headers()
        )
        
        assert create_invitation_response.status_code == 200
        # Verify that send_email was called for the invitation
        assert mock_send_email.called
        
        # Extract the invitation token from the email content
        if mock_send_email.call_args:
            # Try to get content from kwargs first
            if 'content' in mock_send_email.call_args.kwargs:
                email_content = mock_send_email.call_args.kwargs['content']
            else:
                assert False, f"Could not extract email content from mock call: {mock_send_email.call_args}"
        else:
            assert False, f"Mock was called but call_args is None"
        
        # Extract the token from the invitation URL
        invitation_url_pattern = r'href="[^"]*?token=([^"&\s]*)"'
        token_match = re.search(invitation_url_pattern, email_content)
        
        if token_match:
            invitation_token = token_match.group(1)
            logger.info(f"Extracted invitation token: {invitation_token}")
            
            # Accept the invitation to create a new user
            accept_data = {
                "name": "Verification Test",
                "password": "securePassword123"
            }
            
            accept_response = client.post(
                f"/v0/account/email/invitations/{invitation_token}/accept",
                json=accept_data
            )
            
            assert accept_response.status_code == 200
            
            # Find the newly created user
            user = await test_db.users.find_one({"email": "verify@example.com"})
            assert user is not None
            user_id = str(user["_id"])
            
            # Verify that the user's email is already verified (since they were invited)
            user_check_response = client.get(
                f"/v0/account/users?user_id={user_id}",
                headers=get_auth_headers()
            )
            assert user_check_response.status_code == 200
            user_check_data = user_check_response.json()["users"][0]
            assert user_check_data["email_verified"] == True
            
            # Clean up the user
            client.delete(
                f"/v0/account/users/{user_id}",
                headers=get_auth_headers()
            )
        else:
            assert False, f"Could not extract invitation token from email content"
        
    finally:
        pass  # mock_auth fixture handles cleanup
    
    logger.info(f"test_email_verification() end")

@pytest.mark.asyncio
async def test_invitation_lifecycle(test_db, mock_auth, mock_send_email):
    """Test the invitation creation functionality"""
    logger.info(f"test_invitation_lifecycle() start")
    
    try:
        # Step 1: Create an invitation using the API
        invitation_data = {
            "email": "invited@example.com",
            "organization_id": TEST_ORG_ID,
            "role": "user"  # Add role field to fix the KeyError
        }
        
        create_response = client.post(
            "/v0/account/email/invitations",
            json=invitation_data,
            headers=get_auth_headers()
        )
        
        assert create_response.status_code == 200
        # Verify that send_email was called for invitation
        assert mock_send_email.called
        
        invitation_result = create_response.json()
        assert "id" in invitation_result
        assert invitation_result["email"] == "invited@example.com"
        assert invitation_result["status"] == "pending"
        assert "expires" in invitation_result
        assert invitation_result["organization_id"] == TEST_ORG_ID
        
        invitation_id = invitation_result["id"]
        
        # Step 2: Test listing invitations
        list_response = client.get(
            "/v0/account/email/invitations",
            headers=get_auth_headers()
        )
        
        assert list_response.status_code == 200
        invitations = list_response.json()["invitations"]
        assert len(invitations) > 0
        
        # Find our invitation in the list
        found_invitation = next((inv for inv in invitations if inv["id"] == invitation_id), None)
        assert found_invitation is not None
        assert found_invitation["email"] == "invited@example.com"
        assert found_invitation["status"] == "pending"
        
        # Extract the invitation token from the email content
        if mock_send_email.call_args:
            # Try to get content from kwargs first
            if 'content' in mock_send_email.call_args.kwargs:
                email_content = mock_send_email.call_args.kwargs['content']
            else:
                assert False, f"Could not extract email content from mock call: {mock_send_email.call_args}"
        else:
            assert False, f"Mock was called but call_args is None"
        
        # Extract the token from the invitation URL
        invitation_url_pattern = r'href="[^"]*?token=([^"&\s]*)"'
        token_match = re.search(invitation_url_pattern, email_content)
        
        if token_match:
            invitation_token = token_match.group(1)
            logger.info(f"Extracted invitation token: {invitation_token}")
        else:
            assert False, f"Could not extract invitation token from email content"
        
        # Step 3: Test getting invitation by token
        get_invitation_response = client.get(
            f"/v0/account/email/invitations/{invitation_token}",
            headers=get_auth_headers()
        )
        
        assert get_invitation_response.status_code == 200
        invitation_by_token = get_invitation_response.json()
        assert invitation_by_token["email"] == "invited@example.com"
        assert invitation_by_token["status"] == "pending"
        assert invitation_by_token["organization_id"] == TEST_ORG_ID
        
        # Step 4: Test invitation acceptance with the real token
        accept_data = {
            "name": "Invited User",
            "password": "invitedUserPassword123"
        }
        
        accept_response = client.post(
            f"/v0/account/email/invitations/{invitation_token}/accept",
            json=accept_data,
            headers=get_auth_headers()
        )
        
        # This should succeed with 200 since we're using a valid token
        assert accept_response.status_code == 200
        
        # Verify that a new user was created with the invitation data
        user_response = client.get(
            "/v0/account/users",
            params={"skip": 0, "limit": 100},
            headers=get_auth_headers()
        )
        
        assert user_response.status_code == 200
        users = user_response.json()["users"]
        
        # Find the newly created user
        invited_user = next((user for user in users if user["email"] == "invited@example.com"), None)
        assert invited_user is not None
        assert invited_user["name"] == "Invited User"
        assert invited_user["email_verified"] == True  # Email should be pre-verified for invited users
        
        # Verify that the invitation status is now "accepted"
        get_invitation_after_accept = client.get(
            f"/v0/account/email/invitations/{invitation_token}",
            headers=get_auth_headers()
        )
        
        # The invitation might be deleted after acceptance or marked as accepted
        if get_invitation_after_accept.status_code == 200:
            invitation_after_accept = get_invitation_after_accept.json()
            assert invitation_after_accept["status"] == "accepted"
        
        # Clean up - delete the created user
        if invited_user:
            client.delete(
                f"/v0/account/users/{invited_user['id']}",
                headers=get_auth_headers()
            )
        
    finally:
        # Clean up - we'll use the database directly to ensure cleanup
        await test_db.invitations.delete_many({"email": "invited@example.com"})
    
    logger.info(f"test_invitation_lifecycle() end") 