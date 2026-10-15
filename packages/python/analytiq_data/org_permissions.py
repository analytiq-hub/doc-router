"""Org permission groups and capability resolver (phase 3)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Optional

from bson import ObjectId

BUILTIN_VIEWER = "viewer"
BUILTIN_OPERATOR = "operator"
BUILTIN_BUILDER = "builder"
BUILTIN_ADMIN = "admin"

BUILTIN_GROUP_IDS: frozenset[str] = frozenset(
    {BUILTIN_VIEWER, BUILTIN_OPERATOR, BUILTIN_BUILDER, BUILTIN_ADMIN}
)

CAPABILITY_DOCUMENTS_READ = "documents.read"
CAPABILITY_DOCUMENTS_WRITE = "documents.write"
CAPABILITY_RUNS_EXECUTE = "runs.execute"
CAPABILITY_CONFIG_READ = "config.read"
CAPABILITY_CONFIG_WRITE = "config.write"
CAPABILITY_ORG_ADMIN = "org.admin"

ALL_CAPABILITIES: frozenset[str] = frozenset(
    {
        CAPABILITY_DOCUMENTS_READ,
        CAPABILITY_DOCUMENTS_WRITE,
        CAPABILITY_RUNS_EXECUTE,
        CAPABILITY_CONFIG_READ,
        CAPABILITY_CONFIG_WRITE,
        CAPABILITY_ORG_ADMIN,
    }
)

_BUILTIN_GROUP_CAPABILITIES: dict[str, frozenset[str]] = {
    BUILTIN_VIEWER: frozenset({CAPABILITY_DOCUMENTS_READ, CAPABILITY_CONFIG_READ}),
    BUILTIN_OPERATOR: frozenset(
        {
            CAPABILITY_DOCUMENTS_READ,
            CAPABILITY_CONFIG_READ,
            CAPABILITY_DOCUMENTS_WRITE,
            CAPABILITY_RUNS_EXECUTE,
        }
    ),
    BUILTIN_BUILDER: frozenset(
        {
            CAPABILITY_DOCUMENTS_READ,
            CAPABILITY_CONFIG_READ,
            CAPABILITY_DOCUMENTS_WRITE,
            CAPABILITY_RUNS_EXECUTE,
            CAPABILITY_CONFIG_WRITE,
        }
    ),
    BUILTIN_ADMIN: frozenset(ALL_CAPABILITIES),
}


@dataclass(frozen=True)
class OrgMemberContext:
    org_id: str
    user_id: str
    permission_groups: list[dict[str, Any]]
    member: dict[str, Any]
    capabilities: frozenset[str]


def builtin_permission_groups_document() -> list[dict[str, Any]]:
    labels = {
        BUILTIN_VIEWER: "Viewer",
        BUILTIN_OPERATOR: "Operator",
        BUILTIN_BUILDER: "Builder",
        BUILTIN_ADMIN: "Admin",
    }
    return [
        {
            "id": group_id,
            "name": labels[group_id],
            "builtin": True,
            "capabilities": sorted(_BUILTIN_GROUP_CAPABILITIES[group_id]),
        }
        for group_id in sorted(BUILTIN_GROUP_IDS)
    ]


def resolve_member_group_ids(member: dict[str, Any]) -> list[str]:
    """Built-in group ids stored on the member."""
    ids = member.get("permission_group_ids")
    if not isinstance(ids, list) or not ids:
        return []
    return [str(g) for g in ids if str(g) in BUILTIN_GROUP_IDS]


def prepare_member_for_storage(member: dict[str, Any]) -> dict[str, Any]:
    user_id = member.get("user_id")
    if not user_id:
        raise ValueError("member.user_id is required")

    raw_ids = member.get("permission_group_ids")
    if not isinstance(raw_ids, list) or not raw_ids:
        raise ValueError("permission_group_ids is required")

    group_ids: list[str] = []
    for gid in raw_ids:
        s = str(gid)
        if s not in BUILTIN_GROUP_IDS:
            raise ValueError(f"Unknown permission group id: {s}")
        if s not in group_ids:
            group_ids.append(s)
    if not group_ids:
        raise ValueError("permission_group_ids must include at least one built-in group")

    return {
        "user_id": str(user_id),
        "permission_group_ids": group_ids,
    }


def prepare_members_for_storage(members: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    return [prepare_member_for_storage(m) for m in members]


def member_for_api(member: dict[str, Any]) -> dict[str, Any]:
    return {
        "user_id": str(member["user_id"]),
        "permission_group_ids": resolve_member_group_ids(member),
    }


def members_for_api(members: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    return [member_for_api(m) for m in members]


def group_catalog_from_org(org: dict[str, Any]) -> dict[str, frozenset[str]]:
    raw_groups = org.get("permission_groups")
    if not raw_groups:
        return dict(_BUILTIN_GROUP_CAPABILITIES)

    catalog: dict[str, frozenset[str]] = {}
    for group in raw_groups:
        gid = group.get("id")
        if not isinstance(gid, str):
            continue
        caps = group.get("capabilities") or []
        if isinstance(caps, list):
            catalog[gid] = frozenset(str(c) for c in caps if c in ALL_CAPABILITIES)
    return catalog or dict(_BUILTIN_GROUP_CAPABILITIES)


def effective_capabilities_for_member(
    org: dict[str, Any],
    member: dict[str, Any],
) -> frozenset[str]:
    catalog = group_catalog_from_org(org)
    group_ids = resolve_member_group_ids(member)
    caps: set[str] = set()
    for gid in group_ids:
        caps |= set(catalog.get(gid, frozenset()))
    return frozenset(caps)


def member_has_capability(
    org: dict[str, Any],
    member: dict[str, Any],
    capability: str,
) -> bool:
    return capability in effective_capabilities_for_member(org, member)


def member_has_admin_group(member: dict[str, Any]) -> bool:
    return BUILTIN_ADMIN in resolve_member_group_ids(member)


def members_include_org_admin(
    members: Iterable[dict[str, Any]],
    org: Optional[dict[str, Any]] = None,
) -> bool:
    org_doc = org if org is not None else {"permission_groups": builtin_permission_groups_document()}
    for member in members:
        if member_has_capability(org_doc, member, CAPABILITY_ORG_ADMIN):
            return True
    return False


def build_member_entry(
    user_id: str,
    *,
    permission_group_ids: Optional[list[str]] = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "user_id": user_id,
        "permission_group_ids": list(permission_group_ids or [BUILTIN_OPERATOR]),
    }
    return prepare_member_for_storage(payload)


def display_persona_from_group_ids(group_ids: Iterable[str]) -> Optional[str]:
    ids = set(group_ids)
    for persona in (BUILTIN_ADMIN, BUILTIN_BUILDER, BUILTIN_OPERATOR, BUILTIN_VIEWER):
        if persona in ids:
            return persona
    return None


def mongo_elem_match_org_admin(user_id: str) -> dict[str, Any]:
    """Query fragment: user is org admin via built-in Admin group."""
    return {
        "members": {
            "$elemMatch": {
                "user_id": user_id,
                "permission_group_ids": BUILTIN_ADMIN,
            }
        }
    }


async def load_org_member_context(
    db,
    org_id: str,
    user_id: str,
) -> Optional[OrgMemberContext]:
    org = await db.organizations.find_one(
        {"_id": ObjectId(org_id), "members.user_id": user_id},
        projection={"members.$": 1, "permission_groups": 1},
    )
    if not org or not org.get("members"):
        return None
    member = org["members"][0]
    groups = org.get("permission_groups") or builtin_permission_groups_document()
    caps = effective_capabilities_for_member(org, member)
    return OrgMemberContext(
        org_id=org_id,
        user_id=user_id,
        permission_groups=groups,
        member=member,
        capabilities=caps,
    )


async def user_has_org_capability(db, org_id: str, user_id: str, capability: str) -> bool:
    ctx = await load_org_member_context(db, org_id, user_id)
    return ctx is not None and capability in ctx.capabilities


async def ensure_org_permission_groups(db, org_id: str) -> None:
    org = await db.organizations.find_one(
        {"_id": ObjectId(org_id)},
        projection={"permission_groups": 1, "members": 1},
    )
    if not org:
        return
    sets: dict[str, Any] = {}
    if not org.get("permission_groups"):
        sets["permission_groups"] = builtin_permission_groups_document()
    if org.get("members"):
        prepared = prepare_members_for_storage(org["members"])
        if prepared != org["members"]:
            sets["members"] = prepared
    if sets:
        await db.organizations.update_one({"_id": ObjectId(org_id)}, {"$set": sets})
