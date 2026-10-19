"""Browser session JWT (same payload/secret as legacy NextAuth token minting)."""

from __future__ import annotations

import os
from typing import Any

import jwt

ALGORITHM = "HS256"
NEXTAUTH_SECRET = os.getenv("NEXTAUTH_SECRET")


def mint_session_jwt(*, user_id: str, user_name: str | None, email: str) -> str:
    if not NEXTAUTH_SECRET:
        raise RuntimeError("NEXTAUTH_SECRET not configured")
    name = user_name or email
    return jwt.encode(
        {
            "userId": user_id,
            "userName": name,
            "email": email,
        },
        NEXTAUTH_SECRET,
        algorithm=ALGORITHM,
    )


def decode_session_jwt(token: str) -> dict[str, Any]:
    if not NEXTAUTH_SECRET:
        raise RuntimeError("NEXTAUTH_SECRET not configured")
    return jwt.decode(token, NEXTAUTH_SECRET, algorithms=[ALGORITHM])
