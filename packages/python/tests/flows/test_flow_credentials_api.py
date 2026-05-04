"""Org credential REST API: uniqueness of credential name per organization."""

from __future__ import annotations

import pytest

from tests.conftest_utils import client, get_token_headers


@pytest.mark.asyncio
async def test_credential_name_unique_on_create(org_and_users, test_db):
    org_id = org_and_users["org_id"]
    member = org_and_users["member"]
    headers = get_token_headers(member["token"])
    body = {
        "kind_key": "httpHeaderAuth",
        "name": "My API Token",
        "fields": {"name": "Authorization", "value": "Bearer x"},
    }
    r1 = client.post(f"/v0/orgs/{org_id}/credentials", json=body, headers=headers)
    assert r1.status_code == 200, r1.text

    r2 = client.post(f"/v0/orgs/{org_id}/credentials", json=body, headers=headers)
    assert r2.status_code == 409
    assert "already exists" in (r2.json().get("detail") or "").lower()


@pytest.mark.asyncio
async def test_credential_name_trim_matches_existing(org_and_users, test_db):
    org_id = org_and_users["org_id"]
    member = org_and_users["member"]
    headers = get_token_headers(member["token"])
    client.post(
        f"/v0/orgs/{org_id}/credentials",
        json={
            "kind_key": "httpHeaderAuth",
            "name": "Trimmed",
            "fields": {"name": "Authorization", "value": "Bearer a"},
        },
        headers=headers,
    )
    r = client.post(
        f"/v0/orgs/{org_id}/credentials",
        json={
            "kind_key": "httpHeaderAuth",
            "name": "  Trimmed  ",
            "fields": {"name": "Authorization", "value": "Bearer b"},
        },
        headers=headers,
    )
    assert r.status_code == 409


@pytest.mark.asyncio
async def test_credential_rename_conflict(org_and_users, test_db):
    org_id = org_and_users["org_id"]
    member = org_and_users["member"]
    headers = get_token_headers(member["token"])

    a = client.post(
        f"/v0/orgs/{org_id}/credentials",
        json={
            "kind_key": "httpHeaderAuth",
            "name": "Credential A",
            "fields": {"name": "Authorization", "value": "Bearer a"},
        },
        headers=headers,
    )
    assert a.status_code == 200
    b = client.post(
        f"/v0/orgs/{org_id}/credentials",
        json={
            "kind_key": "httpHeaderAuth",
            "name": "Credential B",
            "fields": {"name": "Authorization", "value": "Bearer b"},
        },
        headers=headers,
    )
    assert b.status_code == 200
    cred_b_id = b.json()["credential_id"]

    conflict = client.put(
        f"/v0/orgs/{org_id}/credentials/{cred_b_id}",
        json={
            "name": "Credential A",
            "fields": {"name": "Authorization", "value": "Bearer b"},
        },
        headers=headers,
    )
    assert conflict.status_code == 409


@pytest.mark.asyncio
async def test_same_name_allowed_in_different_orgs(org_and_users, test_db):
    """Uniqueness is scoped to organization_id."""

    import secrets

    from bson import ObjectId
    from datetime import datetime, UTC

    import analytiq_data as ad
    from app.routes.payments import sync_payments_customer

    other_org = str(ObjectId())
    admin = org_and_users["admin"]
    await test_db.organizations.insert_one(
        {
            "_id": ObjectId(other_org),
            "name": "Other Org",
            "members": [{"user_id": admin["id"], "role": "admin"}],
            "type": "team",
            "created_at": datetime.now(UTC),
            "updated_at": datetime.now(UTC),
        }
    )
    await sync_payments_customer(test_db, other_org)

    token_plain = f"org_{secrets.token_urlsafe(32)}"
    await test_db.access_tokens.insert_one(
        {
            "user_id": admin["id"],
            "organization_id": other_org,
            "name": "other-org-token",
            "token": ad.crypto.encrypt_token(token_plain),
            "created_at": datetime.now(UTC),
            "lifetime": 30,
        }
    )
    body = {
        "kind_key": "httpHeaderAuth",
        "name": "Shared Label",
        "fields": {"name": "Authorization", "value": "Bearer z"},
    }
    org_a = org_and_users["org_id"]
    r1 = client.post(
        f"/v0/orgs/{org_a}/credentials",
        json=body,
        headers=get_token_headers(org_and_users["member"]["token"]),
    )
    assert r1.status_code == 200
    r2 = client.post(
        f"/v0/orgs/{other_org}/credentials",
        json=body,
        headers=get_token_headers(token_plain),
    )
    assert r2.status_code == 200
