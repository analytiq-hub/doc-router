"""Tests for dual auth header support: Authorization: Bearer and X-Api-Key."""
import pytest
import logging

from .conftest_utils import (
    client, TEST_ORG_ID,
    get_auth_headers,
)

logger = logging.getLogger(__name__)

assert __import__("os").environ["ENV"] == "pytest"

PROTECTED_URL = f"/v0/orgs/{TEST_ORG_ID}/documents"


def _bearer_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


def _api_key_headers(token: str) -> dict:
    return {"X-Api-Key": token, "Content-Type": "application/json"}


@pytest.mark.asyncio
async def test_bearer_token_accepted(test_db, mock_auth):
    """Authorization: Bearer {token} is accepted for org-scoped endpoints."""
    # Create an org-scoped token via mocked auth
    resp = client.post(
        f"/v0/orgs/{TEST_ORG_ID}/access_tokens",
        json={"name": "bearer-test", "lifetime": 30},
        headers=get_auth_headers(),
    )
    assert resp.status_code == 200
    api_token = resp.json()["token"]

    from app.main import app
    original_overrides = app.dependency_overrides.copy()
    app.dependency_overrides.clear()
    try:
        resp = client.get(PROTECTED_URL, headers=_bearer_headers(api_token))
        assert resp.status_code == 200, resp.text
        assert "documents" in resp.json()
    finally:
        app.dependency_overrides = original_overrides


@pytest.mark.asyncio
async def test_x_api_key_header_accepted(test_db, mock_auth):
    """X-Api-Key: {token} is accepted for org-scoped endpoints."""
    resp = client.post(
        f"/v0/orgs/{TEST_ORG_ID}/access_tokens",
        json={"name": "xapikey-test", "lifetime": 30},
        headers=get_auth_headers(),
    )
    assert resp.status_code == 200
    api_token = resp.json()["token"]

    from app.main import app
    original_overrides = app.dependency_overrides.copy()
    app.dependency_overrides.clear()
    try:
        resp = client.get(PROTECTED_URL, headers=_api_key_headers(api_token))
        assert resp.status_code == 200, resp.text
        assert "documents" in resp.json()
    finally:
        app.dependency_overrides = original_overrides


@pytest.mark.asyncio
async def test_no_credentials_returns_401(test_db, mock_auth):
    """Requests with no auth header return 401."""
    from app.main import app
    original_overrides = app.dependency_overrides.copy()
    app.dependency_overrides.clear()
    try:
        resp = client.get(PROTECTED_URL, headers={"Content-Type": "application/json"})
        assert resp.status_code == 401, resp.text
    finally:
        app.dependency_overrides = original_overrides


@pytest.mark.asyncio
async def test_invalid_bearer_token_returns_401(test_db, mock_auth):
    """An invalid Bearer token returns 401."""
    from app.main import app
    original_overrides = app.dependency_overrides.copy()
    app.dependency_overrides.clear()
    try:
        resp = client.get(PROTECTED_URL, headers=_bearer_headers("invalid_token_xyz"))
        assert resp.status_code == 401, resp.text
    finally:
        app.dependency_overrides = original_overrides


@pytest.mark.asyncio
async def test_invalid_x_api_key_returns_401(test_db, mock_auth):
    """An invalid X-Api-Key value returns 401."""
    from app.main import app
    original_overrides = app.dependency_overrides.copy()
    app.dependency_overrides.clear()
    try:
        resp = client.get(PROTECTED_URL, headers=_api_key_headers("invalid_token_xyz"))
        assert resp.status_code == 401, resp.text
    finally:
        app.dependency_overrides = original_overrides


@pytest.mark.asyncio
async def test_bearer_and_x_api_key_for_account_endpoint(test_db, mock_auth):
    """Both auth methods work for account-level endpoints."""
    resp = client.post(
        "/v0/account/access_tokens",
        json={"name": "account-dual-auth-test", "lifetime": 30},
        headers=get_auth_headers(),
    )
    assert resp.status_code == 200
    api_token = resp.json()["token"]

    from app.main import app
    original_overrides = app.dependency_overrides.copy()
    app.dependency_overrides.clear()
    try:
        bearer_resp = client.get(
            "/v0/account/organizations", headers=_bearer_headers(api_token)
        )
        assert bearer_resp.status_code == 200, bearer_resp.text

        xkey_resp = client.get(
            "/v0/account/organizations", headers=_api_key_headers(api_token)
        )
        assert xkey_resp.status_code == 200, xkey_resp.text
    finally:
        app.dependency_overrides = original_overrides


@pytest.mark.asyncio
async def test_bearer_and_x_api_key_for_org_endpoint(test_db, mock_auth):
    """Both auth methods work for org-level endpoints."""
    resp = client.post(
        f"/v0/orgs/{TEST_ORG_ID}/access_tokens",
        json={"name": "org-dual-auth-test", "lifetime": 30},
        headers=get_auth_headers(),
    )
    assert resp.status_code == 200
    api_token = resp.json()["token"]

    from app.main import app
    original_overrides = app.dependency_overrides.copy()
    app.dependency_overrides.clear()
    try:
        bearer_resp = client.get(PROTECTED_URL, headers=_bearer_headers(api_token))
        assert bearer_resp.status_code == 200, bearer_resp.text
        assert "documents" in bearer_resp.json()

        xkey_resp = client.get(PROTECTED_URL, headers=_api_key_headers(api_token))
        assert xkey_resp.status_code == 200, xkey_resp.text
        assert "documents" in xkey_resp.json()
    finally:
        app.dependency_overrides = original_overrides
