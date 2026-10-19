"""Browser login and OAuth (Google/GitHub) — replaces NextAuth credential/OAuth providers."""

from __future__ import annotations

import logging
import os
import secrets
from datetime import UTC, datetime, timedelta
from urllib.parse import urlencode, urlparse

import bcrypt
import httpx
import jwt
from bcrypt import gensalt, hashpw
from bson import ObjectId
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field

import analytiq_data as ad
from app.account.oauth_provision import provision_oauth_signin
from app.account.oauth_models import OAuthAccountData, OAuthSignInRequest
from app.routes.emails import send_registration_verification_email_for_user
from app.session_jwt import ALGORITHM, mint_session_jwt, require_app_secret

logger = logging.getLogger(__name__)

account_auth_router = APIRouter()

SYSTEM_ROLE_SYSADMIN = "sysadmin"
OAUTH_STATE_TTL = timedelta(minutes=10)

def _auth_google_id() -> str:
    return os.getenv("AUTH_GOOGLE_ID", "")


def _auth_google_secret() -> str:
    return os.getenv("AUTH_GOOGLE_SECRET", "")


def _auth_github_id() -> str:
    return os.getenv("AUTH_GITHUB_ID", "")


def _auth_github_secret() -> str:
    return os.getenv("AUTH_GITHUB_SECRET", "")


def _nextauth_url() -> str:
    return (os.getenv("NEXTAUTH_URL") or "http://localhost:3000").rstrip("/")


class LoginRequest(BaseModel):
    email: str = Field(..., min_length=3)
    password: str = Field(..., min_length=1)


class SessionUser(BaseModel):
    id: str
    email: str
    name: str | None = None
    is_sysadmin: bool = False


class LoginResponse(BaseModel):
    token: str
    user: SessionUser


class RegisterRequest(BaseModel):
    email: str = Field(..., min_length=3)
    password: str = Field(..., min_length=1)
    name: str = Field(..., min_length=1)


class RegisterResponse(BaseModel):
    success: bool = True
    message: str


def _oauth_api_base_url() -> str:
    """Public URL prefix that reaches FastAPI (via Next/nginx ``/fastapi`` proxy)."""
    return f"{_nextauth_url()}/fastapi"


def _safe_return_path(return_to: str | None) -> str:
    if not return_to or not return_to.startswith("/") or return_to.startswith("//"):
        return "/dashboard"
    parsed = urlparse(return_to)
    if parsed.scheme or parsed.netloc:
        return "/dashboard"
    return return_to


def _oauth_state(*, provider: str, return_to: str) -> str:
    secret = require_app_secret()
    now = datetime.now(UTC)
    exp = now + OAUTH_STATE_TTL
    payload = {
        "provider": provider,
        "return_to": return_to,
        "nonce": secrets.token_urlsafe(16),
        "exp": int(exp.timestamp()),
        "iat": int(now.timestamp()),
    }
    return jwt.encode(payload, secret, algorithm=ALGORITHM)


def _decode_oauth_state(state: str, *, provider: str) -> str:
    secret = require_app_secret()
    try:
        payload = jwt.decode(state, secret, algorithms=[ALGORITHM])
    except jwt.PyJWTError:
        raise HTTPException(status_code=400, detail="Invalid OAuth state")
    if payload.get("provider") != provider:
        raise HTTPException(status_code=400, detail="OAuth state provider mismatch")
    return _safe_return_path(payload.get("return_to"))


async def _session_user_for_id(user_id: str) -> SessionUser:
    db = ad.common.get_async_db()
    user = await db.users.find_one({"_id": ObjectId(user_id)})
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return SessionUser(
        id=user_id,
        email=user["email"],
        name=user.get("name"),
        is_sysadmin=user.get("system_role") == SYSTEM_ROLE_SYSADMIN,
    )


def _complete_redirect(token: str, return_to: str) -> RedirectResponse:
    query = urlencode({"token": token, "return_to": return_to})
    return RedirectResponse(url=f"{_nextauth_url()}/auth/complete?{query}", status_code=302)


_REGISTER_SUCCESS_MESSAGE = (
    "Registration successful. Please check your email to verify your account."
)


@account_auth_router.post("/v0/account/auth/register", response_model=RegisterResponse, tags=["account/auth"])
async def register_with_password(body: RegisterRequest):
    db = ad.common.get_async_db()
    hashed_password = hashpw(body.password.encode("utf-8"), gensalt(12)).decode("utf-8")

    existing_user = await db.users.find_one({"email": body.email})
    if existing_user:
        if existing_user.get("email_verified"):
            raise HTTPException(status_code=400, detail="User already exists")
        user_id = str(existing_user["_id"])
        await db.users.update_one(
            {"_id": existing_user["_id"]},
            {"$set": {"name": body.name, "password": hashed_password}},
        )
    else:
        result = await db.users.insert_one({
            "email": body.email,
            "password": hashed_password,
            "name": body.name,
            "email_verified": False,
            "created_at": datetime.now(UTC),
        })
        user_id = str(result.inserted_id)

    try:
        await send_registration_verification_email_for_user(user_id)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"register_with_password(): failed to send verification email for {user_id}: {e}")
        raise HTTPException(status_code=500, detail="Registration failed")

    return RegisterResponse(message=_REGISTER_SUCCESS_MESSAGE)


@account_auth_router.post("/v0/account/auth/login", response_model=LoginResponse, tags=["account/auth"])
async def login_with_password(body: LoginRequest):
    db = ad.common.get_async_db()
    user = await db.users.find_one({"email": body.email})
    if not user or not user.get("password"):
        raise HTTPException(status_code=401, detail="No user found with this email")

    if not user.get("email_verified"):
        raise HTTPException(status_code=401, detail="Please verify your email before logging in")

    stored = user["password"]
    if isinstance(stored, str):
        stored = stored.encode("utf-8")
    if not bcrypt.checkpw(body.password.encode("utf-8"), stored):
        raise HTTPException(status_code=401, detail="Invalid password")

    user_id = str(user["_id"])
    session_user = await _session_user_for_id(user_id)
    token = mint_session_jwt(
        user_id=user_id,
        user_name=session_user.name,
        email=session_user.email,
    )
    return LoginResponse(token=token, user=session_user)


@account_auth_router.get("/v0/account/auth/google/start", tags=["account/auth"])
async def google_oauth_start(return_to: str | None = Query(None)):
    if not _auth_google_id() or not _auth_google_secret():
        raise HTTPException(status_code=503, detail="Google sign-in is not configured")
    return_to = _safe_return_path(return_to)
    state = _oauth_state(provider="google", return_to=return_to)
    redirect_uri = f"{_oauth_api_base_url()}/v0/account/auth/google/callback"
    params = urlencode({
        "client_id": _auth_google_id(),
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": "openid email profile",
        "state": state,
        "prompt": "consent",
        "access_type": "offline",
    })
    return RedirectResponse(f"https://accounts.google.com/o/oauth2/v2/auth?{params}", status_code=302)


@account_auth_router.get("/v0/account/auth/google/callback", tags=["account/auth"])
async def google_oauth_callback(
    code: str | None = Query(None),
    state: str | None = Query(None),
    error: str | None = Query(None),
):
    if error:
        raise HTTPException(status_code=400, detail=f"Google OAuth error: {error}")
    if not code or not state:
        raise HTTPException(status_code=400, detail="Missing OAuth code or state")
    return_to = _decode_oauth_state(state, provider="google")
    redirect_uri = f"{_oauth_api_base_url()}/v0/account/auth/google/callback"

    async with httpx.AsyncClient(timeout=30.0) as client:
        token_resp = await client.post(
            "https://oauth2.googleapis.com/token",
            data={
                "code": code,
                "client_id": _auth_google_id(),
                "client_secret": _auth_google_secret(),
                "redirect_uri": redirect_uri,
                "grant_type": "authorization_code",
            },
        )
        if token_resp.status_code >= 400:
            logger.warning(f"Google token exchange failed: {token_resp.text}")
            raise HTTPException(status_code=400, detail="Failed to exchange Google OAuth code")
        token_data = token_resp.json()

        user_resp = await client.get(
            "https://www.googleapis.com/oauth2/v3/userinfo",
            headers={"Authorization": f"Bearer {token_data['access_token']}"},
        )
        if user_resp.status_code >= 400:
            raise HTTPException(status_code=400, detail="Failed to load Google profile")
        profile = user_resp.json()

    email = profile.get("email")
    if not email:
        raise HTTPException(status_code=400, detail="Google account has no email")

    oauth_request = OAuthSignInRequest(
        email=email,
        name=profile.get("name"),
        email_verified=bool(profile.get("email_verified")),
        provider="google",
        provider_account_id=str(profile.get("sub")),
        account=OAuthAccountData(
            access_token=token_data.get("access_token"),
            expires_at=int(datetime.now(UTC).timestamp()) + int(token_data.get("expires_in", 3600))
            if token_data.get("expires_in")
            else None,
            token_type=token_data.get("token_type"),
            scope=token_data.get("scope"),
            id_token=token_data.get("id_token"),
            refresh_token=token_data.get("refresh_token"),
        ),
    )
    user_id, _ = await provision_oauth_signin(oauth_request)
    session_user = await _session_user_for_id(user_id)
    token = mint_session_jwt(user_id=user_id, user_name=session_user.name, email=session_user.email)
    return _complete_redirect(token, return_to)


@account_auth_router.get("/v0/account/auth/github/start", tags=["account/auth"])
async def github_oauth_start(return_to: str | None = Query(None)):
    if not _auth_github_id() or not _auth_github_secret():
        raise HTTPException(status_code=503, detail="GitHub sign-in is not configured")
    return_to = _safe_return_path(return_to)
    state = _oauth_state(provider="github", return_to=return_to)
    redirect_uri = f"{_oauth_api_base_url()}/v0/account/auth/github/callback"
    params = urlencode({
        "client_id": _auth_github_id(),
        "redirect_uri": redirect_uri,
        "scope": "read:user user:email",
        "state": state,
    })
    return RedirectResponse(f"https://github.com/login/oauth/authorize?{params}", status_code=302)


async def _github_primary_email(client: httpx.AsyncClient, access_token: str) -> tuple[str, bool]:
    emails_resp = await client.get(
        "https://api.github.com/user/emails",
        headers={
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/vnd.github+json",
        },
    )
    if emails_resp.status_code >= 400:
        raise HTTPException(status_code=400, detail="Failed to load GitHub emails")
    emails = emails_resp.json()
    primary = next((e for e in emails if e.get("primary")), None)
    if not primary:
        primary = emails[0] if emails else None
    if not primary or not primary.get("email"):
        raise HTTPException(status_code=400, detail="GitHub account has no email")
    return primary["email"], bool(primary.get("verified"))


@account_auth_router.get("/v0/account/auth/github/callback", tags=["account/auth"])
async def github_oauth_callback(
    code: str | None = Query(None),
    state: str | None = Query(None),
    error: str | None = Query(None),
    error_description: str | None = Query(None),
):
    if error:
        detail = error_description or error
        raise HTTPException(status_code=400, detail=f"GitHub OAuth error: {detail}")
    if not code or not state:
        raise HTTPException(status_code=400, detail="Missing OAuth code or state")
    return_to = _decode_oauth_state(state, provider="github")
    redirect_uri = f"{_oauth_api_base_url()}/v0/account/auth/github/callback"

    async with httpx.AsyncClient(timeout=30.0) as client:
        token_resp = await client.post(
            "https://github.com/login/oauth/access_token",
            headers={"Accept": "application/json"},
            data={
                "client_id": _auth_github_id(),
                "client_secret": _auth_github_secret(),
                "code": code,
                "redirect_uri": redirect_uri,
            },
        )
        if token_resp.status_code >= 400:
            logger.warning(f"GitHub token exchange failed: {token_resp.text}")
            raise HTTPException(status_code=400, detail="Failed to exchange GitHub OAuth code")
        token_data = token_resp.json()
        access_token = token_data.get("access_token")
        if not access_token:
            raise HTTPException(status_code=400, detail="GitHub did not return an access token")

        user_resp = await client.get(
            "https://api.github.com/user",
            headers={
                "Authorization": f"Bearer {access_token}",
                "Accept": "application/vnd.github+json",
            },
        )
        if user_resp.status_code >= 400:
            raise HTTPException(status_code=400, detail="Failed to load GitHub profile")
        profile = user_resp.json()

        email = profile.get("email")
        email_verified = False
        if email:
            email_verified = True
        else:
            email, email_verified = await _github_primary_email(client, access_token)

    oauth_request = OAuthSignInRequest(
        email=email,
        name=profile.get("name") or profile.get("login"),
        email_verified=email_verified,
        provider="github",
        provider_account_id=str(profile.get("id")),
        account=OAuthAccountData(
            access_token=access_token,
            token_type=token_data.get("token_type"),
            scope=token_data.get("scope"),
        ),
    )
    user_id, _ = await provision_oauth_signin(oauth_request)
    session_user = await _session_user_for_id(user_id)
    token = mint_session_jwt(user_id=user_id, user_name=session_user.name, email=session_user.email)
    return _complete_redirect(token, return_to)
