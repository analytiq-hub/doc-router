"""Browser session JWT (HS256, keyed with APP_SECRET like at-rest encryption)."""

from __future__ import annotations

import os
from typing import Any

import jwt

ALGORITHM = "HS256"


def require_app_secret() -> str:
    secret = os.getenv("APP_SECRET")
    if not secret:
        raise RuntimeError("APP_SECRET is not configured")
    return secret


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
