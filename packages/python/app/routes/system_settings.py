# system_settings.py

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

import analytiq_data as ad
from app.auth import get_admin_user
from app.models import User

system_settings_router = APIRouter(tags=["account/system_settings"])

_worker_count_field = lambda *, default=...: Field(  # noqa: E731
    default,
    ge=ad.system.worker_counts.WORKER_COUNT_MIN,
    le=ad.system.worker_counts.WORKER_COUNT_MAX,
)


class SystemSettingsResponse(BaseModel):
    textract_max_concurrent: int = Field(
        ...,
        ge=ad.system.settings.TEXTRACT_MAX_CONCURRENT_MIN,
        le=ad.system.settings.TEXTRACT_MAX_CONCURRENT_MAX,
    )
    llm_max_concurrent_by_model: dict[str, int] = Field(default_factory=dict)
    n_ocr_workers: int = _worker_count_field()
    n_llm_workers: int = _worker_count_field()
    n_kb_index_workers: int = _worker_count_field()
    n_webhook_workers: int = _worker_count_field()
    n_flow_run_workers: int = _worker_count_field()
    updated_at: Optional[datetime] = None


class SystemSettingsUpdate(BaseModel):
    textract_max_concurrent: Optional[int] = Field(
        default=None,
        ge=ad.system.settings.TEXTRACT_MAX_CONCURRENT_MIN,
        le=ad.system.settings.TEXTRACT_MAX_CONCURRENT_MAX,
    )
    llm_max_concurrent_by_model: Optional[dict[str, int]] = None
    n_ocr_workers: Optional[int] = _worker_count_field(default=None)
    n_llm_workers: Optional[int] = _worker_count_field(default=None)
    n_kb_index_workers: Optional[int] = _worker_count_field(default=None)
    n_webhook_workers: Optional[int] = _worker_count_field(default=None)
    n_flow_run_workers: Optional[int] = _worker_count_field(default=None)


def _response_from_doc(doc: dict) -> SystemSettingsResponse:
    return SystemSettingsResponse(
        textract_max_concurrent=int(doc["textract_max_concurrent"]),
        llm_max_concurrent_by_model=dict(doc.get("llm_max_concurrent_by_model") or {}),
        n_ocr_workers=int(doc["n_ocr_workers"]),
        n_llm_workers=int(doc["n_llm_workers"]),
        n_kb_index_workers=int(doc["n_kb_index_workers"]),
        n_webhook_workers=int(doc["n_webhook_workers"]),
        n_flow_run_workers=int(doc["n_flow_run_workers"]),
        updated_at=doc.get("updated_at"),
    )


@system_settings_router.get(
    "/v0/account/system_settings",
    response_model=SystemSettingsResponse,
)
async def get_system_settings(current_user: User = Depends(get_admin_user)):
    """Return deployment-wide worker settings (admin only)."""
    doc = await ad.system.settings.get_system_settings_document()
    return _response_from_doc(doc)


@system_settings_router.patch(
    "/v0/account/system_settings",
    response_model=SystemSettingsResponse,
)
async def update_system_settings(
    body: SystemSettingsUpdate,
    current_user: User = Depends(get_admin_user),
):
    """Update deployment-wide worker settings (admin only)."""
    payload = body.model_dump(exclude_unset=True)
    if not payload:
        raise HTTPException(status_code=400, detail="No settings provided")
    doc = await ad.system.settings.update_system_settings(**payload)
    return _response_from_doc(doc)
