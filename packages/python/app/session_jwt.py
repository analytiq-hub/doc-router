"""Browser session JWT (HS256, keyed with APP_SECRET like at-rest encryption)."""

from __future__ import annotations

import os
from typing import Any

import jwt
from fastapi import Request, Response

ALGORITHM = "HS256"

# Same name as the Next.js route used (`packages/typescript/frontend/src/constants/sessionCookie.ts`).
SESSION_COOKIE_NAME = "dr.api-token"


def require_app_secret() -> str:
    secret = os.getenv("APP_SECRET")
    if not secret:
        raise RuntimeError("APP_SECRET is not configured")
    return secret


def _request_is_https(request: Request) -> bool:
    forwarded = request.headers.get("x-forwarded-proto", "").split(",")[0].strip().lower()
    if forwarded:
        return forwarded == "https"
    return request.url.scheme == "https"


def set_session_cookie(response: Response, request: Request, token: str) -> None:
    """httpOnly session cookie for browser clients (SPA-friendly)."""
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=token,
        max_age=30 * 24 * 60 * 60,
        httponly=True,
        secure=_request_is_https(request),
        samesite="lax",
        path="/",
    )


def clear_session_cookie(response: Response, request: Request) -> None:
    response.delete_cookie(
        key=SESSION_COOKIE_NAME,
        httponly=True,
        secure=_request_is_https(request),
        samesite="lax",
        path="/",
    )


def mint_session_jwt(*, user_id: str, user_name: str | None, email: str) -> str:
    name = user_name or email
    return jwt.encode(
        {
            "userId": user_id,
            "userName": name,
            "email": email,
        },
        require_app_secret(),
        algorithm=ALGORITHM,
    )


def decode_session_jwt(token: str) -> dict[str, Any]:
    return jwt.decode(token, require_app_secret(), algorithms=[ALGORITHM])
