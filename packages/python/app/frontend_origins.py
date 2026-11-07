"""Browser app origins (Next, Vite dev, production NEXTAUTH_URL)."""

from __future__ import annotations

import os


def frontend_origins() -> list[str]:
    origins = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://host.docker.internal:3000",
    ]
    nextauth = os.getenv("NEXTAUTH_URL")
    if nextauth:
        origins.append(nextauth.rstrip("/"))
    origins.extend(o.strip() for o in os.getenv("CORS_ORIGINS_EXTRA", "").split(",") if o.strip())
    seen: set[str] = set()
    unique: list[str] = []
    for o in origins:
        if o not in seen:
            seen.add(o)
            unique.append(o)
    return unique


def normalize_app_origin(origin: str | None) -> str | None:
    if not origin:
        return None
    normalized = origin.rstrip("/")
    return normalized if normalized in frontend_origins() else None
