"""Org-scoped permission introspection for the current member."""

from typing import List

from fastapi import APIRouter, Depends
from pydantic import BaseModel

import analytiq_data as ad
from analytiq_data.org_permissions import (
    ALL_CAPABILITIES,
    display_persona_from_group_ids,
    resolve_member_group_ids,
)
from app.auth import is_system_admin
from app.org_auth import get_org_user
from app.models import User

org_permissions_router = APIRouter(tags=["permissions"])


class MemberPermissionsResponse(BaseModel):
    capabilities: List[str]
    permission_group_ids: List[str]
    persona: str | None = None


@org_permissions_router.get(
    "/v0/orgs/{organization_id}/permissions/me",
    response_model=MemberPermissionsResponse,
)
async def get_my_org_permissions(
    organization_id: str,
    current_user: User = Depends(get_org_user),
):
    db = ad.common.get_async_db()
    ctx = await ad.org_permissions.load_org_member_context(
        db, organization_id, current_user.user_id
    )
    if ctx is None:
        if await is_system_admin(current_user.user_id):
            return MemberPermissionsResponse(
                capabilities=sorted(ALL_CAPABILITIES),
                permission_group_ids=[],
                persona=None,
            )
        return MemberPermissionsResponse(capabilities=[], permission_group_ids=[], persona=None)
    group_ids = resolve_member_group_ids(ctx.member)
    return MemberPermissionsResponse(
        capabilities=sorted(ctx.capabilities),
        permission_group_ids=group_ids,
        persona=display_persona_from_group_ids(group_ids),
    )
