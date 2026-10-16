import pytest
from bson import ObjectId
import os
import logging
from datetime import datetime, UTC

# Import shared test utilities
from .conftest_utils import (
    client,
    TEST_ORG_ID,
    TEST_USER_ID,
    get_auth_headers,
)
import analytiq_data as ad

logger = logging.getLogger(__name__)

# Check that ENV is set to pytest
assert os.environ["ENV"] == "pytest"

@pytest.mark.asyncio
async def test_form_submission_lifecycle(test_db, mock_auth):
    """Test the complete form submission lifecycle"""
    logger.info(f"test_form_submission_lifecycle() start")
    
    try:
        # Step 1: Create a form first
        form_data = {
            "name": "Test Submission Form",
            "response_format": {
                "json_formio": [
                    {
                        "type": "textfield",
                        "key": "customer_name",
                        "label": "Customer Name",
                        "input": True,
                        "validate": {
                            "required": True
                        }
                    },
                    {
                        "type": "email",
                        "key": "customer_email", 
                        "label": "Email Address",
                        "input": True,
                        "validate": {
                            "required": True
                        }
                    },
                    {
                        "type": "number",
                        "key": "order_amount",
                        "label": "Order Amount",
                        "input": True,
                        "validate": {
                            "required": True,
                            "min": 1
                        }
                    }
                ]
            },
            "tag_ids": []
        }
        
        create_form_response = client.post(
            f"/v0/orgs/{TEST_ORG_ID}/forms",
            json=form_data,
            headers=get_auth_headers()
        )
        
        assert create_form_response.status_code == 200
        form_result = create_form_response.json()
        form_revid = form_result["form_revid"]
        
        # Step 2: Create a document to submit against
        document_data = {
            "documents": [
                {
                    "name": "test_document.pdf",
                    "content": "data:application/pdf;base64,JVBERi0xLjQKJcOkw7zDtsO8DQoxIDAgb2JqDQo8PA0KL1R5cGUgL0NhdGFsb2cNCi9QYWdlcyAyIDAgUg0KPj4NCmVuZG9iag0KMiAwIG9iag0KPDwNCi9UeXBlIC9QYWdlcw0KL0NvdW50IDENCi9LaWRzIFsgMyAwIFIgXQ0KPj4NCmVuZG9iag0KMyAwIG9iag0KPDwNCi9UeXBlIC9QYWdlDQovUGFyZW50IDIgMCBSDQovUmVzb3VyY2VzIDw8DQovRm9udCA8PA0KL0YxIDQgMCBSDQo+Pg0KPj4NCi9Db250ZW50cyA1IDAgUg0KPj4NCmVuZG9iag0KNCAwIG9iag0KPDwNCi9UeXBlIC9Gb250DQovU3VidHlwZSAvVHlwZTENCi9CYXNlRm9udCAvSGVsdmV0aWNhDQovRW5jb2RpbmcgL1dpbkFuc2lFbmNvZGluZw0KPj4NCmVuZG9iag0KNSAwIG9iag0KPDwNCi9MZW5ndGggMzQNCj4+DQpzdHJlYW0NCkJUCjcwIDUwIFRECi9GMSAxMiBUZgooSGVsbG8gV29ybGQpIFRqCkVUCmVuZG9iag0KeHJlZg0KMCA2DQowMDAwMDAwMDAwIDY1NTM1IGYNCjAwMDAwMDAwMTAgMDAwMDAgbg0KMDAwMDAwMDA3MCAwMDAwMCBuDQowMDAwMDAwMTczIDAwMDAwIG4NCjAwMDAwMDAzMDEgMDAwMDAgbg0KMDAwMDAwMDM4MCAwMDAwMCBuDQp0cmFpbGVyDQo8PA0KL1NpemUgNg0KL1Jvb3QgMSAwIFINCj4+DQpzdGFydHhyZWYNCjQ5Mg0KJSVFT0Y=",
                    "tag_ids": []
                }
            ]
        }
        
        upload_response = client.post(
            f"/v0/orgs/{TEST_ORG_ID}/documents",
            json=document_data,
            headers=get_auth_headers()
        )
        
        assert upload_response.status_code == 200
        document_result = upload_response.json()
        document_id = document_result["documents"][0]["document_id"]
        
        # Step 3: Submit a form
        submission_data = {
            "form_revid": form_revid,
            "submission_data": {
                "customer_name": "John Doe",
                "customer_email": "john.doe@example.com",
                "order_amount": 150.00
            },
            "submitted_by": None  # Will use current user
        }
        
        submit_response = client.post(
            f"/v0/orgs/{TEST_ORG_ID}/forms/submissions/{document_id}",
            json=submission_data,
            headers=get_auth_headers()
        )
        
        assert submit_response.status_code == 200
        submission_result = submit_response.json()
        assert "id" in submission_result
        assert submission_result["form_revid"] == form_revid
        # Note: document_id is not included in the response model
        assert submission_result["submission_data"]["customer_name"] == "John Doe"
        assert submission_result["submission_data"]["customer_email"] == "john.doe@example.com"
        assert submission_result["submission_data"]["order_amount"] == 150.00
        assert "created_at" in submission_result
        assert "updated_at" in submission_result
        
        submission_id = submission_result["id"]
        
        # Step 4: Get the submission using the new endpoint
        get_response = client.get(
            f"/v0/orgs/{TEST_ORG_ID}/forms/submissions/{document_id}?form_revid={form_revid}",
            headers=get_auth_headers()
        )
        
        assert get_response.status_code == 200
        get_result = get_response.json()
        assert get_result["id"] == submission_id
        assert get_result["form_revid"] == form_revid
        # Note: document_id is not included in the response model
        
        # Step 5: Submit the same form again (should update existing)
        updated_submission_data = {
            "form_revid": form_revid,
            "submission_data": {
                "customer_name": "Jane Smith",
                "customer_email": "jane.smith@example.com",
                "order_amount": 200.00
            }
        }
        
        update_response = client.post(
            f"/v0/orgs/{TEST_ORG_ID}/forms/submissions/{document_id}",
            json=updated_submission_data,
            headers=get_auth_headers()
        )
        
        assert update_response.status_code == 200
        update_result = update_response.json()
        assert update_result["submission_data"]["customer_name"] == "Jane Smith"
        assert update_result["submission_data"]["customer_email"] == "jane.smith@example.com"
        assert update_result["submission_data"]["order_amount"] == 200.00
        assert update_result["id"] == submission_id  # Same submission ID
        
        # Step 6: Delete the submission
        delete_response = client.delete(
            f"/v0/orgs/{TEST_ORG_ID}/forms/submissions/{document_id}?form_revid={form_revid}",
            headers=get_auth_headers()
        )
        
        assert delete_response.status_code == 200
        delete_result = delete_response.json()
        assert delete_result["message"] == "Form submission deleted successfully"
        
        # Step 7: Verify deletion - should return None (not 404)
        get_deleted_response = client.get(
            f"/v0/orgs/{TEST_ORG_ID}/forms/submissions/{document_id}?form_revid={form_revid}",
            headers=get_auth_headers()
        )
        
        assert get_deleted_response.status_code == 200
        assert get_deleted_response.json() is None
        
    except Exception as e:
        logger.error(f"test_form_submission_lifecycle() failed: {e}")
        raise

@pytest.mark.asyncio
async def test_form_submission_validation(test_db, mock_auth):
    """Test form submission validation and error cases"""
    logger.info(f"test_form_submission_validation() start")
    
    try:
        # Test submission with non-existent form
        invalid_submission = {
            "form_revid": "507f1f77bcf86cd799439011",  # Non-existent ObjectId
            "submission_data": {"test": "value"}
        }
        
        response = client.post(
            f"/v0/orgs/{TEST_ORG_ID}/forms/submissions/507f1f77bcf86cd799439012",
            json=invalid_submission,
            headers=get_auth_headers()
        )
        
        assert response.status_code == 404
        assert "Form revision not found" in response.json()["detail"]
        
        # Test submission with non-existent document
        form_data = {
            "name": "Validation Test Form",
            "response_format": {
                "json_formio": [
                    {
                        "type": "textfield",
                        "key": "test_field",
                        "label": "Test Field",
                        "input": True
                    }
                ]
            },
            "tag_ids": []
        }
        
        create_form_response = client.post(
            f"/v0/orgs/{TEST_ORG_ID}/forms",
            json=form_data,
            headers=get_auth_headers()
        )
        
        assert create_form_response.status_code == 200
        form_result = create_form_response.json()
        form_revid = form_result["form_revid"]
        
        invalid_doc_submission = {
            "form_revid": form_revid,
            "submission_data": {"test": "value"}
        }
        
        response = client.post(
            f"/v0/orgs/{TEST_ORG_ID}/forms/submissions/507f1f77bcf86cd799439012",
            json=invalid_doc_submission,
            headers=get_auth_headers()
        )
        
        assert response.status_code == 404
        assert "Document not found" in response.json()["detail"]
        
        # Test getting non-existent submission - should return None (not 404)
        response = client.get(
            f"/v0/orgs/{TEST_ORG_ID}/forms/submissions/507f1f77bcf86cd799439011?form_revid=507f1f77bcf86cd799439012",
            headers=get_auth_headers()
        )
        
        assert response.status_code == 200
        assert response.json() is None
        
        # Test deleting non-existent submission
        response = client.delete(
            f"/v0/orgs/{TEST_ORG_ID}/forms/submissions/507f1f77bcf86cd799439011?form_revid=507f1f77bcf86cd799439012",
            headers=get_auth_headers()
        )
        
        assert response.status_code == 404
        assert "Form submission not found" in response.json()["detail"]
        
    except Exception as e:
        logger.error(f"test_form_submission_validation() failed: {e}")
        raise

@pytest.mark.asyncio
async def test_form_submission_cross_organization_isolation(test_db, mock_auth):
    """Test that form submissions are isolated between organizations"""
    logger.info(f"test_form_submission_cross_organization_isolation() start")

    try:
        # Default test user is platform sysadmin (bypasses org membership checks).
        await test_db.users.update_one(
            {"_id": ObjectId(TEST_USER_ID)},
            {"$unset": {"system_role": ""}},
        )

        # Create a form in the test organization
        form_data = {
            "name": "Isolation Test Form",
            "response_format": {
                "json_formio": [
                    {
                        "type": "textfield",
                        "key": "test_field",
                        "label": "Test Field",
                        "input": True
                    }
                ]
            },
            "tag_ids": []
        }
        
        create_form_response = client.post(
            f"/v0/orgs/{TEST_ORG_ID}/forms",
            json=form_data,
            headers=get_auth_headers()
        )
        
        assert create_form_response.status_code == 200
        form_result = create_form_response.json()
        form_revid = form_result["form_revid"]
        
        # Create a document in the test organization
        document_data = {
            "documents": [
                {
                    "name": "isolation_test.pdf",
                    "content": "data:application/pdf;base64,JVBERi0xLjQKJcOkw7zDtsO8DQoxIDAgb2JqDQo8PA0KL1R5cGUgL0NhdGFsb2cNCi9QYWdlcyAyIDAgUg0KPj4NCmVuZG9iag0KMiAwIG9iag0KPDwNCi9UeXBlIC9QYWdlcw0KL0NvdW50IDENCi9LaWRzIFsgMyAwIFIgXQ0KPj4NCmVuZG9iag0KMyAwIG9iag0KPDwNCi9UeXBlIC9QYWdlDQovUGFyZW50IDIgMCBSDQovUmVzb3VyY2VzIDw8DQovRm9udCA8PA0KL0YxIDQgMCBSDQo+Pg0KPj4NCi9Db250ZW50cyA1IDAgUg0KPj4NCmVuZG9iag0KNCAwIG9iag0KPDwNCi9UeXBlIC9Gb250DQovU3VidHlwZSAvVHlwZTENCi9CYXNlRm9udCAvSGVsdmV0aWNhDQovRW5jb2RpbmcgL1dpbkFuc2lFbmNvZGluZw0KPj4NCmVuZG9iag0KNSAwIG9iag0KPDwNCi9MZW5ndGggMzQNCj4+DQpzdHJlYW0NCkJUCjcwIDUwIFRECi9GMSAxMiBUZgooSGVsbG8gV29ybGQpIFRqCkVUCmVuZG9iag0KeHJlZg0KMCA2DQowMDAwMDAwMDAwIDY1NTM1IGYNCjAwMDAwMDAwMTAgMDAwMDAgbg0KMDAwMDAwMDA3MCAwMDAwMCBuDQowMDAwMDAwMTczIDAwMDAwIG4NCjAwMDAwMDAzMDEgMDAwMDAgbg0KMDAwMDAwMDM4MCAwMDAwMCBuDQp0cmFpbGVyDQo8PA0KL1NpemUgNg0KL1Jvb3QgMSAwIFINCj4+DQpzdGFydHhyZWYNCjQ5Mg0KJSVFT0Y=",
                    "tag_ids": []
                }
            ]
        }
        
        upload_response = client.post(
            f"/v0/orgs/{TEST_ORG_ID}/documents",
            json=document_data,
            headers=get_auth_headers()
        )
        
        assert upload_response.status_code == 200
        document_result = upload_response.json()
        document_id = document_result["documents"][0]["document_id"]
        
        # Create a submission
        submission_data = {
            "form_revid": form_revid,
            "submission_data": {"test_field": "isolation_test"}
        }
        
        submit_response = client.post(
            f"/v0/orgs/{TEST_ORG_ID}/forms/submissions/{document_id}",
            json=submission_data,
            headers=get_auth_headers()
        )
        
        assert submit_response.status_code == 200
        submission_result = submit_response.json()
        submission_id = submission_result["id"]
        
        # Try to access the submission from a different organization
        different_org_id = "507f1f77bcf86cd799439013"
        
        # Get submission from different org should fail
        get_response = client.get(
            f"/v0/orgs/{different_org_id}/forms/submissions/{document_id}?form_revid={form_revid}",
            headers=get_auth_headers()
        )
        
        assert get_response.status_code == 403
        
        # Submit to different org should fail
        submit_different_org_response = client.post(
            f"/v0/orgs/{different_org_id}/forms/submissions/{document_id}",
            json=submission_data,
            headers=get_auth_headers()
        )
        
        assert submit_different_org_response.status_code == 403
        
        # Delete submission from different org should fail
        delete_response = client.delete(
            f"/v0/orgs/{different_org_id}/forms/submissions/{document_id}?form_revid={form_revid}",
            headers=get_auth_headers()
        )
        
        assert delete_response.status_code == 403
        
        # Verify the submission still exists in the original organization
        verify_response = client.get(
            f"/v0/orgs/{TEST_ORG_ID}/forms/submissions/{document_id}?form_revid={form_revid}",
            headers=get_auth_headers()
        )
        
        assert verify_response.status_code == 200
        
    except Exception as e:
        logger.error(f"test_form_submission_cross_organization_isolation() failed: {e}")
        raise

@pytest.mark.asyncio
async def test_form_submission_update_behavior(test_db, mock_auth):
    """Test that submitting the same form multiple times updates the existing submission"""
    logger.info(f"test_form_submission_update_behavior() start")
    
    try:
        # Create a form
        form_data = {
            "name": "Update Test Form",
            "response_format": {
                "json_formio": [
                    {
                        "type": "textfield",
                        "key": "test_field",
                        "label": "Test Field",
                        "input": True
                    }
                ]
            },
            "tag_ids": []
        }
        
        create_form_response = client.post(
            f"/v0/orgs/{TEST_ORG_ID}/forms",
            json=form_data,
            headers=get_auth_headers()
        )
        
        assert create_form_response.status_code == 200
        form_result = create_form_response.json()
        form_revid = form_result["form_revid"]
        
        # Create a document
        document_data = {
            "documents": [
                {
                    "name": "update_test.pdf",
                    "content": "data:application/pdf;base64,JVBERi0xLjQKJcOkw7zDtsO8DQoxIDAgb2JqDQo8PA0KL1R5cGUgL0NhdGFsb2cNCi9QYWdlcyAyIDAgUg0KPj4NCmVuZG9iag0KMiAwIG9iag0KPDwNCi9UeXBlIC9QYWdlcw0KL0NvdW50IDENCi9LaWRzIFsgMyAwIFIgXQ0KPj4NCmVuZG9iag0KMyAwIG9iag0KPDwNCi9UeXBlIC9QYWdlDQovUGFyZW50IDIgMCBSDQovUmVzb3VyY2VzIDw8DQovRm9udCA8PA0KL0YxIDQgMCBSDQo+Pg0KPj4NCi9Db250ZW50cyA1IDAgUg0KPj4NCmVuZG9iag0KNCAwIG9iag0KPDwNCi9UeXBlIC9Gb250DQovU3VidHlwZSAvVHlwZTENCi9CYXNlRm9udCAvSGVsdmV0aWNhDQovRW5jb2RpbmcgL1dpbkFuc2lFbmNvZGluZw0KPj4NCmVuZG9iag0KNSAwIG9iag0KPDwNCi9MZW5ndGggMzQNCj4+DQpzdHJlYW0NCkJUCjcwIDUwIFRECi9GMSAxMiBUZgooSGVsbG8gV29ybGQpIFRqCkVUCmVuZG9iag0KeHJlZg0KMCA2DQowMDAwMDAwMDAwIDY1NTM1IGYNCjAwMDAwMDAwMTAgMDAwMDAgbg0KMDAwMDAwMDA3MCAwMDAwMCBuDQowMDAwMDAwMTczIDAwMDAwIG4NCjAwMDAwMDAzMDEgMDAwMDAgbg0KMDAwMDAwMDM4MCAwMDAwMCBuDQp0cmFpbGVyDQo8PA0KL1NpemUgNg0KL1Jvb3QgMSAwIFINCj4+DQpzdGFydHhyZWYNCjQ5Mg0KJSVFT0Y=",
                    "tag_ids": []
                }
            ]
        }
        
        upload_response = client.post(
            f"/v0/orgs/{TEST_ORG_ID}/documents",
            json=document_data,
            headers=get_auth_headers()
        )
        
        assert upload_response.status_code == 200
        document_result = upload_response.json()
        document_id = document_result["documents"][0]["document_id"]
        
        # First submission
        submission1_data = {
            "form_revid": form_revid,
            "submission_data": {"test_field": "initial_value"}
        }
        
        submit1_response = client.post(
            f"/v0/orgs/{TEST_ORG_ID}/forms/submissions/{document_id}",
            json=submission1_data,
            headers=get_auth_headers()
        )
        
        assert submit1_response.status_code == 200
        submission1_result = submit1_response.json()
        submission_id = submission1_result["id"]
        
        # Second submission (should update the first one)
        submission2_data = {
            "form_revid": form_revid,
            "submission_data": {"test_field": "updated_value"}
        }
        
        submit2_response = client.post(
            f"/v0/orgs/{TEST_ORG_ID}/forms/submissions/{document_id}",
            json=submission2_data,
            headers=get_auth_headers()
        )
        
        assert submit2_response.status_code == 200
        submission2_result = submit2_response.json()
        
        # Should have the same submission ID
        assert submission2_result["id"] == submission_id
        
        # Should have updated data
        assert submission2_result["submission_data"]["test_field"] == "updated_value"
        
        # Verify via GET request
        get_response = client.get(
            f"/v0/orgs/{TEST_ORG_ID}/forms/submissions/{document_id}?form_revid={form_revid}",
            headers=get_auth_headers()
        )
        
        assert get_response.status_code == 200
        get_result = get_response.json()
        assert get_result["id"] == submission_id
        assert get_result["submission_data"]["test_field"] == "updated_value"
        
    except Exception as e:
        logger.error(f"test_form_submission_update_behavior() failed: {e}")
        raise 