"""FastAPI license status and admin update routes."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

import analytiq_data as ad
from app.auth import get_admin_user, get_current_user
from app.models import User

license_router = APIRouter(tags=["account/license"])


class LicenseStatusResponse(BaseModel):
    valid: bool
    mode: str
    license_id: Optional[str] = None
    customer_name: Optional[str] = None
    issued_at: Optional[datetime] = None
    not_before: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    grace_days: Optional[int] = None
    days_remaining: Optional[int] = None
    in_grace: bool = False
    features: list[str] = Field(default_factory=list)
    limits: dict[str, Any] = Field(default_factory=dict)
    installation_id: Optional[str] = None
    state: str = "ok"
    checked_at: Optional[datetime] = None
    code: Optional[str] = None
    message: Optional[str] = None


class LicenseAdminResponse(LicenseStatusResponse):
    masked_key: Optional[str] = None


class LicenseUpdateRequest(BaseModel):
    license_key: str = Field(..., min_length=1)


def _to_status(status: ad.licensing.LicenseStatus, *, admin: bool) -> dict:
    data = status.model_dump()
    if not admin:
        data.pop("masked_key", None)
    return data


@license_router.get(
    "/v0/account/license/status",
    response_model=LicenseStatusResponse,
)
async def get_license_status(current_user: User = Depends(get_current_user)):
    """Safe license status for any authenticated user (banners)."""
    status = await ad.licensing.get_cached_status(include_masked_key=False)
    return LicenseStatusResponse(**_to_status(status, admin=False))


@license_router.get(
    "/v0/account/license",
    response_model=LicenseAdminResponse,
)
async def get_license(current_user: User = Depends(get_admin_user)):
    """Admin license status including masked key preview."""
    status = await ad.licensing.get_cached_status(include_masked_key=True)
    return LicenseAdminResponse(**_to_status(status, admin=True))


@license_router.put(
    "/v0/account/license",
    response_model=LicenseAdminResponse,
)
async def update_license(
    body: LicenseUpdateRequest,
    current_user: User = Depends(get_admin_user),
):
    """Replace the deployment license key (verify-before-write)."""
    try:
        status = await ad.licensing.put_license_key(
            body.license_key,
            updated_by_user_id=current_user.user_id,
        )
    except ad.licensing.LicenseVerifyError as e:
        raise HTTPException(
            status_code=400,
            detail={"code": e.code, "message": e.message},
        ) from e

    import logging

    logging.getLogger(__name__).info(
        f"License updated by user_id={current_user.user_id} "
        f"license_id={status.license_id} features={status.features}"
    )
    return LicenseAdminResponse(**_to_status(status, admin=True))
