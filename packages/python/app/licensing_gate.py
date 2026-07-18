"""HTTP middleware: block API when a stored license is disabled (expired/invalid)."""

from __future__ import annotations

import logging
from typing import Callable, Optional

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

import analytiq_data as ad

logger = logging.getLogger(__name__)

# Paths always allowed when license is disabled (prefix match unless exact).
_ALLOW_EXACT = {
    "/",
    "/docs",
    "/openapi.json",
    "/redoc",
}

_ALLOW_PREFIXES = (
    "/v0/account/license",
    "/v0/account/auth",
    "/v0/account/token",
    "/v0/account/email/verification",
    "/v0/account/email/invitations",
)


def _is_allowlisted(path: str) -> bool:
    if path in _ALLOW_EXACT:
        return True
    # Strip trailing slash for comparison
    normalized = path.rstrip("/") or "/"
    if normalized in _ALLOW_EXACT:
        return True
    for prefix in _ALLOW_PREFIXES:
        if path == prefix or path.startswith(prefix + "/") or path.startswith(prefix + "?"):
            return True
        if normalized == prefix or normalized.startswith(prefix + "/"):
            return True
    return False


class LicenseGateMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        path = request.url.path

        # Never gate CORS preflight
        if request.method == "OPTIONS":
            return await call_next(request)

        if _is_allowlisted(path):
            return await call_next(request)

        try:
            status = await ad.licensing.get_cached_status()
        except Exception:
            logger.exception("License gate failed to read status; allowing request")
            return await call_next(request)

        # No key → ungated
        if status.code == "LICENSE_MISSING" or status.mode == "unlicensed":
            return await call_next(request)

        if status.state == "ok":
            return await call_next(request)

        code = status.code or "LICENSE_INVALID"
        message = status.message or "Product license is not valid."
        return JSONResponse(
            status_code=403,
            content={
                "detail": {
                    "code": code,
                    "message": message,
                }
            },
        )


def is_path_allowlisted(path: str) -> bool:
    """Exposed for tests."""
    return _is_allowlisted(path)
