import pytest
from bson import ObjectId

from analytiq_data.org_permissions import (
    BUILTIN_ADMIN,
    BUILTIN_BUILDER,
    BUILTIN_OPERATOR,
    BUILTIN_VIEWER,
    CAPABILITY_CONFIG_WRITE,
    CAPABILITY_ORG_ADMIN,
    build_member_entry,
    effective_capabilities_for_member,
    member_has_capability,
    members_include_org_admin,
)
from analytiq_data.org_permissions import builtin_permission_groups_document


def test_viewer_cannot_write_config():
    org = {"permission_groups": builtin_permission_groups_document()}
    member = build_member_entry("u1", permission_group_ids=[BUILTIN_VIEWER])
    assert not member_has_capability(org, member, CAPABILITY_CONFIG_WRITE)
    assert member_has_capability(org, member, "config.read")


def test_builder_has_config_write():
    org = {"permission_groups": builtin_permission_groups_document()}
    member = build_member_entry("u1", permission_group_ids=[BUILTIN_BUILDER])
    assert member_has_capability(org, member, CAPABILITY_CONFIG_WRITE)


def test_admin_org_capability():
    org = {"permission_groups": builtin_permission_groups_document()}
    member = build_member_entry("u1", permission_group_ids=[BUILTIN_ADMIN])
    assert member_has_capability(org, member, CAPABILITY_ORG_ADMIN)


def test_members_include_org_admin_requires_admin_group():
    org = {"permission_groups": builtin_permission_groups_document()}
    assert members_include_org_admin(
        [{"user_id": "a", "permission_group_ids": [BUILTIN_ADMIN]}], org
    )
    assert not members_include_org_admin(
        [{"user_id": "a", "permission_group_ids": [BUILTIN_OPERATOR]}], org
    )


def test_effective_capabilities_union():
    org = {"permission_groups": builtin_permission_groups_document()}
    member = {
        "user_id": "u1",
        "permission_group_ids": [BUILTIN_VIEWER, BUILTIN_OPERATOR],
    }
    caps = effective_capabilities_for_member(org, member)
    assert CAPABILITY_CONFIG_WRITE not in caps
    assert "runs.execute" in caps


@pytest.mark.asyncio
async def test_permissions_me_endpoint(org_and_users):
    from tests.conftest_utils import client, get_token_headers

    org_id = org_and_users["org_id"]
    member = org_and_users["member"]
    resp = client.get(
        f"/v0/orgs/{org_id}/permissions/me",
        headers=get_token_headers(member["token"]),
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert CAPABILITY_CONFIG_WRITE in data["capabilities"]
    assert BUILTIN_BUILDER in data["permission_group_ids"]
    assert data["persona"] == BUILTIN_BUILDER


@pytest.mark.asyncio
async def test_org_member_can_get_co_member_user(org_and_users, test_db):
    from bson import ObjectId
    from tests.conftest_utils import client, get_token_headers

    org_id = org_and_users["org_id"]
    admin_id = org_and_users["admin"]["id"]
    member_id = org_and_users["member"]["id"]

    await test_db.organizations.update_one(
        {"_id": ObjectId(org_id), "members.user_id": member_id},
        {"$set": {"members.$.permission_group_ids": [BUILTIN_VIEWER]}},
    )

    resp = client.get(
        f"/v0/account/users?user_id={admin_id}",
        headers=get_token_headers(org_and_users["member"]["account_token"]),
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["users"][0]["id"] == admin_id

    resp = client.get(
        f"/v0/account/users?user_id={admin_id}",
        headers=get_token_headers(org_and_users["outsider"]["account_token"]),
    )
    assert resp.status_code == 403, resp.text


@pytest.mark.asyncio
async def test_viewer_cannot_create_tag(org_and_users, test_db):
    from tests.conftest_utils import client, get_token_headers

    org_id = org_and_users["org_id"]
    member_id = org_and_users["member"]["id"]
    await test_db.organizations.update_one(
        {"_id": ObjectId(org_id), "members.user_id": member_id},
        {"$set": {"members.$.permission_group_ids": [BUILTIN_VIEWER]}},
    )
    resp = client.post(
        f"/v0/orgs/{org_id}/tags",
        json={"name": "viewer-tag", "color": "#000000"},
        headers=get_token_headers(org_and_users["member"]["token"]),
    )
    assert resp.status_code == 403, resp.text
