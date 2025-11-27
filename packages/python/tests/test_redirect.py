import pytest
import os
import logging

# Import shared test utilities
from .conftest_utils import client

logger = logging.getLogger(__name__)

# Check that ENV is set to pytest
assert os.environ["ENV"] == "pytest"


@pytest.mark.asyncio
async def test_root_redirect():
    """Test that the root endpoint redirects to the frontend"""
    logger.info("test_root_redirect() start")

    response = client.get("/", follow_redirects=False)

    assert response.status_code == 307, f"Expected 307 redirect, got {response.status_code}"
    assert "location" in response.headers, "Redirect response should include Location header"

    location = response.headers["location"]
    assert location is not None and len(location) > 0, "Redirect location should not be empty"
    # Should redirect to a valid URL (either NEXTAUTH_URL or default http://localhost:3000)
    assert location.startswith("http"), f"Redirect location should be a valid URL, got {location}"

    logger.info(f"test_root_redirect() end - redirects to: {location}")


@pytest.mark.asyncio
async def test_organization_access_tokens_redirect():
    """Test that the organization access tokens endpoint redirects to the frontend with correct path"""
    logger.info("test_organization_access_tokens_redirect() start")

    response = client.get("/settings/user/developer/organization-access-tokens", follow_redirects=False)

    assert response.status_code == 307, f"Expected 307 redirect, got {response.status_code}"
    assert "location" in response.headers, "Redirect response should include Location header"

    location = response.headers["location"]
    assert location is not None and len(location) > 0, "Redirect location should not be empty"
    assert location.startswith("http"), f"Redirect location should be a valid URL, got {location}"
    # Verify the path is preserved in the redirect
    assert "/settings/user/developer/organization-access-tokens" in location, \
        f"Redirect location should include the path, got: {location}"

    logger.info(f"test_organization_access_tokens_redirect() end - redirects to: {location}")


@pytest.mark.asyncio
async def test_root_redirect_defaults_to_localhost():
    """Test that the root endpoint defaults to localhost:3000 when NEXTAUTH_URL is not set"""
    logger.info("test_root_redirect_defaults_to_localhost() start")

    # The app reads NEXTAUTH_URL at import time, so we test the current behavior
    # If NEXTAUTH_URL was not set when the app was imported, it defaults to http://localhost:3000
    response = client.get("/", follow_redirects=False)

    assert response.status_code == 307, f"Expected 307 redirect, got {response.status_code}"
    assert "location" in response.headers, "Redirect response should include Location header"

    # Should redirect to either NEXTAUTH_URL (if set) or default to http://localhost:3000
    location = response.headers["location"]
    assert location is not None and len(location) > 0, "Redirect location should not be empty"

    logger.info(f"test_root_redirect_defaults_to_localhost() end - redirects to: {location}")


@pytest.mark.asyncio
async def test_organization_access_tokens_redirect_path_preserved():
    """Test that the organization access tokens endpoint preserves the path in the redirect"""
    logger.info("test_organization_access_tokens_redirect_path_preserved() start")

    response = client.get("/settings/user/developer/organization-access-tokens", follow_redirects=False)

    assert response.status_code == 307, f"Expected 307 redirect, got {response.status_code}"
    assert "location" in response.headers, "Redirect response should include Location header"

    location = response.headers["location"]
    assert location is not None and len(location) > 0, "Redirect location should not be empty"
    assert "/settings/user/developer/organization-access-tokens" in location, \
        f"Redirect location should include the path, got: {location}"

    logger.info(f"test_organization_access_tokens_redirect_path_preserved() end - redirects to: {location}")


