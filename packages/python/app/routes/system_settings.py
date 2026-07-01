# system_settings.py

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

import analytiq_data as ad
from app.auth import get_admin_user
from app.models import User

system_settings_router = APIRouter(tags=["account/system_settings"])


class SystemSettingsResponse(BaseModel):
    textract_max_concurrent: int = Field(
        ...,
        ge=ad.system.settings.TEXTRACT_MAX_CONCURRENT_MIN,
        le=ad.system.settings.TEXTRACT_MAX_CONCURRENT_MAX,
    )
    updated_at: Optional[datetime] = None


class SystemSettingsUpdate(BaseModel):
    textract_max_concurrent: int = Field(
        ...,
        ge=ad.system.settings.TEXTRACT_MAX_CONCURRENT_MIN,
        le=ad.system.settings.TEXTRACT_MAX_CONCURRENT_MAX,
    )


@system_settings_router.get(
    "/v0/account/system_settings",
    response_model=SystemSettingsResponse,
)
async def get_system_settings(current_user: User = Depends(get_admin_user)):
    """Return deployment-wide worker settings (admin only)."""
    doc = await ad.system.settings.get_system_settings_document()
    return SystemSettingsResponse(
        textract_max_concurrent=ad.system.settings.clamp_textract_max_concurrent(
            int(doc.get("textract_max_concurrent", ad.system.settings.default_textract_max_concurrent()))
        ),
        updated_at=doc.get("updated_at"),
    )


@system_settings_router.patch(
    "/v0/account/system_settings",
    response_model=SystemSettingsResponse,
)
async def update_system_settings(
    body: SystemSettingsUpdate,
    current_user: User = Depends(get_admin_user),
):
    """Update deployment-wide worker settings (admin only)."""
    doc = await ad.system.settings.update_system_settings(
        textract_max_concurrent=body.textract_max_concurrent,
    )
    return SystemSettingsResponse(
        textract_max_concurrent=int(doc["textract_max_concurrent"]),
        updated_at=doc.get("updated_at"),
    )
