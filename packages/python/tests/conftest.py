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
# Ensure SDK src is importable without editable install
sdk_src_path = os.path.normpath(os.path.join(cwd, "../sdk/src"))
if os.path.isdir(sdk_src_path) and sdk_src_path not in sys.path:
    sys.path.append(sdk_src_path)

# Now import the FastAPI app and dependencies
from app.main import app, security
from app.auth import get_current_user, get_admin_user
from app.models import User
from app.routes.payments import init_payments, sync_payments_customer
from worker.worker import main as worker_main
import analytiq_data as ad

from tests.conftest_utils import (
    TEST_USER_ID,
    TEST_ORG_ID,
    TEST_USER
)

# Define pytest configuration
pytest_plugins = ["pytest_asyncio"]

# Set default asyncio fixture scope
def pytest_addoption(parser):
    parser.addini(
        "asyncio_default_fixture_loop_scope",
        help="default scope for asyncio fixtures",
        default="function",
    )

@pytest_asyncio.fixture(scope="function")
def unique_db_name():
    # Use xdist worker id if available, else use a UUID
    worker_id = os.environ.get("PYTEST_XDIST_WORKER")
    if worker_id:
        db_name = f"pytest_{worker_id}"
    else:
        db_name = f"pytest_{uuid.uuid4()}"

    os.environ["ENV"] = db_name

    # Disable Stripe during all unit tests by clearing the secret key
    os.environ["STRIPE_SECRET_KEY"] = ""
    os.environ["STRIPE_WEBHOOK_SECRET"] = ""

    return db_name

@pytest_asyncio.fixture
async def test_db(unique_db_name):
    """Set up and tear down a unique test database per worker/session"""
    client = motor.motor_asyncio.AsyncIOMotorClient(os.environ["MONGODB_URI"])
    db = client[unique_db_name]
    
    # Verify we're using the test database
    if not os.environ["ENV"].startswith("pytest"):
        raise ValueError(f"Test is not using the test database! ENV={os.environ['ENV']}")
    
    # Clear the database before each test
    collections = await db.list_collection_names()
    for collection in collections:
        await db.drop_collection(collection)
    
    # Initialize payments system for all tests
    await init_payments(db)
    
    # Create a test user in the database
    await db.users.insert_one({
        "_id": ObjectId(TEST_USER_ID),
        "email": "test@example.com",
        "name": "Test User",
        "role": "admin",
        "email_verified": True,
        "has_password": True,
        "created_at": datetime.now(UTC)
    })
    
    # Create a test organization in the database
    await db.organizations.insert_one({
        "_id": ObjectId(TEST_ORG_ID),
        "name": "Test Organization",
        "members": [{
            "user_id": TEST_USER_ID,
            "role": "admin"
        }],
        "type": "team",
        "created_at": datetime.now(UTC),
        "updated_at": datetime.now(UTC)
    })
    
    # Create payment customer for the organization (required for document processing)
    await sync_payments_customer(db, TEST_ORG_ID)

    try:
        yield db
    finally:
        # Ensure DB cleanup and client close to avoid hanging on Ctrl-C
        if os.environ["ENV"].startswith("pytest"):
            collections = await db.list_collection_names()
            for collection in collections:
                await db.drop_collection(collection)
        else:
            # This should never happen, but just in case
            raise ValueError(f"Attempted to clean up non-test database! ENV={os.environ['ENV']}")
        client.close()

@pytest_asyncio.fixture
async def org_and_users(test_db):
    """
    Create an organization, an admin, a member, and a non-member user, and generate tokens for each.
    Returns a dict with user/org info and tokens.
    """
    from app.main import app
    import secrets

    # Create users
    admin_id = str(ObjectId())
    member_id = str(ObjectId())
    outsider_id = str(ObjectId())

    await test_db.users.insert_many([
        {
            "_id": ObjectId(admin_id),
            "email": "org-admin@example.com",
            "name": "Org Admin",
            "role": "admin",
            "email_verified": True,
            "has_password": True,
            "created_at": datetime.now(UTC)
        },
        {
            "_id": ObjectId(member_id),
            "email": "org-member@example.com",
            "name": "Org Member",
            "role": "user",
            "email_verified": True,
            "has_password": True,
            "created_at": datetime.now(UTC)
        },
        {
            "_id": ObjectId(outsider_id),
            "email": "org-outsider@example.com",
            "name": "Not In Org",
            "role": "user",
            "email_verified": True,
            "has_password": True,
            "created_at": datetime.now(UTC)
        }
    ])

    # Create org with admin and member
    org_id = str(ObjectId())
    await test_db.organizations.insert_one({
        "_id": ObjectId(org_id),
        "name": "Test Org For Auth",
        "members": [
            {"user_id": admin_id, "role": "admin"},
            {"user_id": member_id, "role": "user"}
        ],
        "type": "team",
        "created_at": datetime.now(UTC),
        "updated_at": datetime.now(UTC)
    })

    await sync_payments_customer(test_db, org_id)

    # Helper to create a token for a user
    async def create_token(user_id, org_id, name):
        if org_id is None:
            # Account-level token
            token = f"acc_{secrets.token_urlsafe(32)}"
        else:
            # Organization-level token
            token = f"org_{secrets.token_urlsafe(32)}"
        encrypted = ad.crypto.encrypt_token(token)
        token_doc = {
            "user_id": user_id,
            "organization_id": org_id,
            "name": name,
            "token": encrypted,
            "created_at": datetime.now(UTC),
            "lifetime": 30
        }
        await test_db.access_tokens.insert_one(token_doc)
        return token

    # Create org-level tokens (backward compatibility - existing tests use these)
    admin_token = await create_token(admin_id, org_id, "admin-token")
    member_token = await create_token(member_id, org_id, "member-token")
    outsider_token = await create_token(outsider_id, org_id, "outsider-token")
    
    # Create account-level tokens (for /v0/account/* endpoints)
    admin_account_token = await create_token(admin_id, None, "admin-account-token")
    member_account_token = await create_token(member_id, None, "member-account-token")
    outsider_account_token = await create_token(outsider_id, None, "outsider-account-token")

    return {
        "org_id": org_id,
        "admin": {"id": admin_id, "token": admin_token, "account_token": admin_account_token},
        "member": {"id": member_id, "token": member_token, "account_token": member_account_token},
        "outsider": {"id": outsider_id, "token": outsider_token, "account_token": outsider_account_token}
    }

@pytest.fixture
def mock_auth():
    """Set up and tear down authentication mocking"""
    # Create proper credentials object
    mock_credentials = HTTPAuthorizationCredentials(
        scheme="Bearer",
        credentials="test_token"
    )

    # Override authentication dependencies
    app.dependency_overrides = {
        security: lambda: mock_credentials,
        get_current_user: lambda: TEST_USER,
        get_admin_user: lambda: TEST_USER  # Also mock the admin user dependency
    }
    
    yield
    
    # Clean up
    app.dependency_overrides.clear() 

@pytest_asyncio.fixture
async def setup_test_models(test_db):
    """Set up test LLM models in the database"""
    # Check if the providers already exist
    providers = await test_db.llm_providers.find({}).to_list(None)
    if providers:
        return  # Providers already set up
        
    import analytiq_data as ad
    
    # Add test provider
    test_provider = {
        "name": "OpenAI",
        "display_name": "OpenAI",
        "litellm_provider": "openai",
        "litellm_models_available": ["gpt-4o-mini", "gpt-4o"],
        "litellm_models_enabled": ["gpt-4o-mini", "gpt-4o"],
        "enabled": True,
        "token": ad.crypto.encrypt_token("test-token"),
        "token_created_at": datetime.now(UTC)
    }
    
    await test_db.llm_providers.insert_one(test_provider)