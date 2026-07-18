"""FastAPI dependencies for license feature gates."""

from __future__ import annotations

from typing import Callable

from fastapi import Depends, HTTPException

import analytiq_data as ad


def require_feature(feature: str) -> Callable:
    """Return a Depends-compatible dependency that requires a license feature.

    No key in DB → allow (ungated). Key present → feature must be in claims.
    """

    async def _dependency() -> None:
        status = await ad.licensing.get_cached_status()
        if status.mode == "unlicensed" or status.code == "LICENSE_MISSING":
            return
        if status.state != "ok":
            # Middleware should usually catch this; defend in depth.
            raise HTTPException(
                status_code=403,
                detail={
                    "code": status.code or "LICENSE_INVALID",
                    "message": status.message or "Product license is not valid.",
                },
            )
        if feature not in status.features:
            raise HTTPException(
                status_code=403,
                detail={
                    "code": "FEATURE_NOT_LICENSED",
                    "message": f"Feature '{feature}' is not included in this license.",
                },
            )

    return _dependency
