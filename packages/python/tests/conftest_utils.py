import pytest
import os
import sys
import uuid
import pytest_asyncio
from datetime import datetime, UTC
import motor.motor_asyncio
from bson import ObjectId
from fastapi.testclient import TestClient
from fastapi.security import HTTPAuthorizationCredentials
from filelock import FileLock

# Set up the path first, before other imports
cwd = os.path.dirname(os.path.abspath(__file__))
sys.path.append(f"{cwd}/..")

# Now import the FastAPI app and dependencies
from app.main import app, security
from app.auth import get_current_user, get_admin_user
from app.models import User
import analytiq_data as ad

# Use a valid ObjectId format for user_id (24-character hex string)
TEST_USER_ID = "6579a94b1f1d8f5a8e9c0124"

# Common test data
TEST_USER = User(
    user_id=TEST_USER_ID,
    user_name="test@example.com",
    token_type="jwt"
)

# Use a valid ObjectId format (24-character hex string)
TEST_ORG_ID = "6579a94b1f1d8f5a8e9c0123"

def setup_env():
    """Set up the environment variables for the tests"""
    os.environ["ENV"] = "pytest"
    os.environ["MONGODB_URI"] = "mongodb://localhost:27017"
    os.environ["NEXTAUTH_SECRET"] = "test_secret_key_for_tests"

# Set test environment variables
setup_env()

# Create a test client
client = TestClient(app)


def get_token_headers(token):
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

def get_auth_headers():
    """Get authentication headers for test requests"""
    return {
        "Authorization": "Bearer test_token",
        "Content-Type": "application/json"
    }