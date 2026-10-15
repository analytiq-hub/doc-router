"""FastAPI dependencies for org capabilities."""

from __future__ import annotations

from typing import Callable

from fastapi import Depends, HTTPException

import analytiq_data as ad
from analytiq_data.org_permissions import (
    CAPABILITY_CONFIG_READ,
    CAPABILITY_CONFIG_WRITE,
    CAPABILITY_DOCUMENTS_READ,
    CAPABILITY_DOCUMENTS_WRITE,
    CAPABILITY_ORG_ADMIN,
    CAPABILITY_RUNS_EXECUTE,
    load_org_member_context,
)
from app.auth import get_current_user, is_system_admin
from app.models import User


async def require_org_capability(
    organization_id: str,
    capability: str,
    current_user: User,
) -> User:
    if await is_system_admin(current_user.user_id):
        return current_user
    db = ad.common.get_async_db()
    ctx = await load_org_member_context(db, organization_id, current_user.user_id)
    if ctx is None:
        raise HTTPException(status_code=403, detail="You are not a member of this organization")
    if capability not in ctx.capabilities:
        raise HTTPException(
            status_code=403,
            detail=f"Missing required permission: {capability}",
        )
    return current_user


def org_capability_dependency(capability: str) -> Callable:
    async def _dependency(
        organization_id: str,
        current_user: User = Depends(get_current_user),
    ) -> User:
        return await require_org_capability(organization_id, capability, current_user)

    return _dependency


require_org_documents_read = org_capability_dependency(CAPABILITY_DOCUMENTS_READ)
require_org_documents_write = org_capability_dependency(CAPABILITY_DOCUMENTS_WRITE)
require_org_runs_execute = org_capability_dependency(CAPABILITY_RUNS_EXECUTE)
require_org_config_read = org_capability_dependency(CAPABILITY_CONFIG_READ)
require_org_config_write = org_capability_dependency(CAPABILITY_CONFIG_WRITE)
require_org_admin_capability = org_capability_dependency(CAPABILITY_ORG_ADMIN)


async def require_org_admin_or_sysadmin(
    organization_id: str,
    current_user: User,
) -> User:
    """Org admin capability, or platform sysadmin (support read access to billing/usage)."""
    if await is_system_admin(current_user.user_id):
        return current_user
    return await require_org_capability(organization_id, CAPABILITY_ORG_ADMIN, current_user)


def org_admin_or_sysadmin_dependency() -> Callable:
    async def _dependency(
        organization_id: str,
        current_user: User = Depends(get_current_user),
    ) -> User:
        return await require_org_admin_or_sysadmin(organization_id, current_user)

    return _dependency


require_org_billing_read = org_admin_or_sysadmin_dependency()


async def get_org_user(
    organization_id: str,
    current_user: User = Depends(get_current_user),
) -> User:
    """Org membership, or platform sysadmin (support access without membership)."""
    if await is_system_admin(current_user.user_id):
        return current_user
    db = ad.common.get_async_db()
    ctx = await load_org_member_context(db, organization_id, current_user.user_id)
    if ctx is None:
        raise HTTPException(status_code=403, detail="You are not a member of this organization")
    return current_user
