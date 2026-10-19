import os
from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import bcrypt
import pytest
from fastapi.testclient import TestClient

import analytiq_data as ad
from app.main import app
from app.session_jwt import decode_session_jwt


@pytest.fixture
def client():
    return TestClient(app)


def _hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(12)).decode("utf-8")


@pytest.mark.asyncio
async def test_login_success(client, worker_db_name):
    db = ad.common.get_async_db()
    password = "test-login-password"
    result = await db.users.insert_one({
        "email": "login-test@example.com",
        "password": _hash_password(password),
        "name": "Login Test",
        "email_verified": True,
        "created_at": datetime.now(UTC),
    })
    user_id = str(result.inserted_id)

    response = client.post(
        "/v0/account/auth/login",
        json={"email": "login-test@example.com", "password": password},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["user"]["id"] == user_id
    assert body["user"]["email"] == "login-test@example.com"
    assert body["token"]

    payload = decode_session_jwt(body["token"])
    assert payload["userId"] == user_id
    assert payload["email"] == "login-test@example.com"


@pytest.mark.asyncio
async def test_login_rejects_unverified_email(client, worker_db_name):
    db = ad.common.get_async_db()
    password = "unverified-pass"
    await db.users.insert_one({
        "email": "unverified@example.com",
        "password": _hash_password(password),
        "name": "Unverified",
        "email_verified": False,
        "created_at": datetime.now(UTC),
    })

    response = client.post(
        "/v0/account/auth/login",
        json={"email": "unverified@example.com", "password": password},
    )
    assert response.status_code == 401
    assert "verify" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_register_creates_user_and_sends_verification(client, worker_db_name):
    db = ad.common.get_async_db()
    with patch(
        "app.routes.account_auth.send_registration_verification_email_for_user",
        new_callable=AsyncMock,
    ) as send_verification:
        response = client.post(
            "/v0/account/auth/register",
            json={
                "email": "new-user@example.com",
                "password": "register-password",
                "name": "New User",
            },
        )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["success"] is True
    assert "verify" in body["message"].lower()
    send_verification.assert_awaited_once()

    user = await db.users.find_one({"email": "new-user@example.com"})
    assert user is not None
    assert user["email_verified"] is False
    assert user["name"] == "New User"
    assert bcrypt.checkpw(
        b"register-password",
        user["password"].encode("utf-8"),
    )


@pytest.mark.asyncio
async def test_register_rejects_verified_duplicate_email(client, worker_db_name):
    db = ad.common.get_async_db()
    await db.users.insert_one({
        "email": "taken@example.com",
        "password": _hash_password("x"),
        "name": "Taken",
        "email_verified": True,
        "created_at": datetime.now(UTC),
    })

    response = client.post(
        "/v0/account/auth/register",
        json={"email": "taken@example.com", "password": "pw", "name": "Other"},
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "User already exists"


@pytest.mark.asyncio
async def test_register_resends_verification_for_unverified_email(client, worker_db_name):
    db = ad.common.get_async_db()
    result = await db.users.insert_one({
        "email": "pending@example.com",
        "password": _hash_password("old-password"),
        "name": "Old Name",
        "email_verified": False,
        "created_at": datetime.now(UTC),
    })
    user_id = str(result.inserted_id)

    with patch(
        "app.routes.account_auth.send_registration_verification_email_for_user",
        new_callable=AsyncMock,
    ) as send_verification:
        response = client.post(
            "/v0/account/auth/register",
            json={
                "email": "pending@example.com",
                "password": "new-password",
                "name": "New Name",
            },
        )

    assert response.status_code == 200, response.text
    send_verification.assert_awaited_once_with(user_id)

    user = await db.users.find_one({"_id": result.inserted_id})
    assert user["name"] == "New Name"
    assert bcrypt.checkpw(b"new-password", user["password"].encode("utf-8"))


def test_login_invalid_password(client):
    response = client.post(
        "/v0/account/auth/login",
        json={"email": "nobody@example.com", "password": "wrong"},
    )
    assert response.status_code == 401


def test_google_start_redirects_when_configured(client, monkeypatch):
    monkeypatch.setenv("AUTH_GOOGLE_ID", "google-client-id")
    monkeypatch.setenv("AUTH_GOOGLE_SECRET", "google-secret")
    monkeypatch.setenv("NEXTAUTH_URL", "http://localhost:3000")
    monkeypatch.setenv("NEXTAUTH_SECRET", os.environ.get("NEXTAUTH_SECRET", "test_secret_key_for_tests_32bytes_min!!"))

    response = client.get("/v0/account/auth/google/start", follow_redirects=False)
    assert response.status_code == 302
    location = response.headers["location"]
    assert location.startswith("https://accounts.google.com/o/oauth2/v2/auth")
    assert "client_id=google-client-id" in location
    assert "redirect_uri=" in location
    assert "localhost%3A3000%2Ffastapi%2Fv0%2Faccount%2Fauth%2Fgoogle%2Fcallback" in location
