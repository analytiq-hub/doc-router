"""Org credential REST API: uniqueness of credential name per organization."""

from __future__ import annotations

import httpx
import pytest

import analytiq_data as ad

from tests.conftest_utils import client, get_token_headers


class _RecordingHttpClient:
    """Minimal async client that records outbound URLs."""

    urls: list[str]

    def __init__(self, urls: list[str], **_: object) -> None:
        self._urls = urls

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_):
        pass

    async def request(self, method: str, url: str, **_kw):  # type: ignore[no-untyped-def]
        self._urls.append(url)
        return httpx.Response(204, request=httpx.Request(method, url))


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
async def test_credential_update_preserves_secret_when_omitted(org_and_users, test_db):
    org_id = org_and_users["org_id"]
    member = org_and_users["member"]
    headers = get_token_headers(member["token"])
    created = client.post(
        f"/v0/orgs/{org_id}/credentials",
        json={
            "kind_key": "httpHeaderAuth",
            "name": "Secret keep",
            "fields": {"name": "Authorization", "value": "Bearer original"},
        },
        headers=headers,
    )
    assert created.status_code == 200, created.text
    cred_id = created.json()["credential_id"]

    updated = client.put(
        f"/v0/orgs/{org_id}/credentials/{cred_id}",
        json={
            "name": "Secret keep renamed",
            "fields": {"name": "X-Api-Key", "value": ""},
        },
        headers=headers,
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["name"] == "Secret keep renamed"
    assert "value" in (updated.json().get("secret_fields_set") or [])

    listed = client.get(f"/v0/orgs/{org_id}/credentials/{cred_id}", headers=headers)
    assert listed.status_code == 200
    assert listed.json()["public_fields"]["name"] == "X-Api-Key"


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
            "token": ad.crypto.encrypt_secret(token_plain),
            "fingerprint": ad.crypto.fingerprint_secret(token_plain),
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


@pytest.mark.asyncio
async def test_list_credentials_pagination(org_and_users, test_db):
    org_id = org_and_users["org_id"]
    headers = get_token_headers(org_and_users["member"]["token"])
    for i in range(3):
        r = client.post(
            f"/v0/orgs/{org_id}/credentials",
            json={
                "kind_key": "httpHeaderAuth",
                "name": f"Cred {i}",
                "fields": {"name": "Authorization", "value": f"Bearer {i}"},
            },
            headers=headers,
        )
        assert r.status_code == 200, r.text

    p1 = client.get(
        f"/v0/orgs/{org_id}/credentials",
        params={"limit": 2, "offset": 0},
        headers=headers,
    )
    assert p1.status_code == 200
    j1 = p1.json()
    assert j1["total"] == 3
    assert len(j1["items"]) == 2

    p2 = client.get(
        f"/v0/orgs/{org_id}/credentials",
        params={"limit": 2, "offset": 2},
        headers=headers,
    )
    assert p2.status_code == 200
    j2 = p2.json()
    assert j2["total"] == 3
    assert len(j2["items"]) == 1


@pytest.mark.asyncio
async def test_credential_test_renders_templated_url(org_and_users, monkeypatch):
    """``test_request.url`` supports Jinja2 with ``credentials.<field>`` (Gap 3)."""

    import app.routes.flows_credentials as fc

    _TEMPLATED_TEST_KIND = {
        "key": "httpTemplatedUrlTest",
        "display_name": "Templated test URL",
        "auth_mode": "api_key",
        "secret_schema": {
            "type": "object",
            "additionalProperties": False,
            "required": ["host_path"],
            "properties": {
                "host_path": {"type": "string", "minLength": 1},
            },
        },
        "inject": {},
        "test_request": {
            "method": "GET",
            "url": "https://example.com/{{ credentials.host_path }}",
        },
    }
    _real_get_kind = ad.flows.get_credential_kind

    def get_kind_maybe_synthetic(kind_key: str):
        if kind_key == "httpTemplatedUrlTest":
            return dict(_TEMPLATED_TEST_KIND)
        return _real_get_kind(kind_key)

    monkeypatch.setattr(ad.flows, "get_credential_kind", get_kind_maybe_synthetic)

    org_id = org_and_users["org_id"]
    member = org_and_users["member"]
    hdrs = get_token_headers(member["token"])

    create = client.post(
        f"/v0/orgs/{org_id}/credentials",
        json={
            "kind_key": "httpTemplatedUrlTest",
            "name": "Template URL cred",
            "fields": {"host_path": "v1/hello"},
        },
        headers=hdrs,
    )
    assert create.status_code == 200, create.text
    cred_id = create.json()["credential_id"]

    seen: list[str] = []

    monkeypatch.setattr(fc.httpx, "AsyncClient", lambda **kw: _RecordingHttpClient(seen, **kw))

    probe = client.post(
        f"/v0/orgs/{org_id}/credentials/{cred_id}/test",
        headers=hdrs,
    )

    assert probe.status_code == 200, probe.text
    assert probe.json().get("ok") is True
    assert seen == ["https://example.com/v1/hello"]


@pytest.mark.asyncio
async def test_list_credential_kinds_filters_experimental_without_org_flag(
    org_and_users, test_db, monkeypatch
):
    from bson import ObjectId

    org_id = org_and_users["org_id"]
    member = org_and_users["member"]
    headers = get_token_headers(member["token"])

    real_list = ad.flows.list_credential_kinds

    def patched_list():
        kinds = real_list()
        kinds.append(
            {
                "key": "expKindTestOnly",
                "display_name": "Experimental Test",
                "auth_mode": "custom",
                "secret_schema": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {},
                    "required": [],
                },
                "experimental": True,
            }
        )
        return kinds

    monkeypatch.setattr(ad.flows, "list_credential_kinds", patched_list)
    r = client.get(f"/v0/orgs/{org_id}/credential-kinds", headers=headers)
    assert r.status_code == 200
    keys = [x["key"] for x in r.json()]
    assert "expKindTestOnly" not in keys

    await test_db.organizations.update_one(
        {"_id": ObjectId(org_id)},
        {"$set": {"experimental_features": True}},
    )
    r2 = client.get(f"/v0/orgs/{org_id}/credential-kinds", headers=headers)
    keys2 = [x["key"] for x in r2.json()]
    assert "expKindTestOnly" in keys2


@pytest.mark.asyncio
async def test_oauth_kind_includes_redirect_uri(org_and_users, test_db):
    from bson import ObjectId

    org_id = org_and_users["org_id"]
    member = org_and_users["member"]
    headers = get_token_headers(member["token"])
    await test_db.organizations.update_one(
        {"_id": ObjectId(org_id)},
        {"$set": {"experimental_features": True}},
    )
    r = client.get(f"/v0/orgs/{org_id}/credential-kinds", headers=headers)
    assert r.status_code == 200
    kinds = {k["key"]: k for k in r.json()}
    gmail = kinds.get("gmailOAuth2")
    assert gmail is not None
    assert gmail.get("supports_oauth_browser_flow") is True
    assert gmail.get("oauth_redirect_uri") == ad.flows.flow_oauth_redirect_uri()
    outlook = kinds.get("microsoftOutlookOAuth2Api")
    assert outlook is not None
    assert outlook.get("oauth_redirect_uri") == ad.flows.flow_oauth_redirect_uri(
        prefer_localhost_loopback=True
    )
    gmail_field_names = {f["name"] for f in gmail.get("fields") or []}
    assert "ignoreSSLIssues" not in gmail_field_names
    oauth2 = kinds.get("oAuth2Api")
    assert oauth2 is not None
    oauth2_field_names = {f["name"] for f in oauth2.get("fields") or []}
    assert "ignoreSSLIssues" in oauth2_field_names
    http = kinds.get("httpHeaderAuth")
    assert http is not None
    assert not http.get("supports_oauth_browser_flow")
    assert http.get("oauth_redirect_uri") is None


@pytest.mark.asyncio
async def test_create_experimental_credential_blocked_without_org_flag(org_and_users, monkeypatch):
    org_id = org_and_users["org_id"]
    member = org_and_users["member"]
    headers = get_token_headers(member["token"])

    real_get = ad.flows.get_credential_kind

    def get_kind_exp(key: str):
        k = dict(real_get(key))
        k["experimental"] = True
        return k

    monkeypatch.setattr(ad.flows, "get_credential_kind", get_kind_exp)

    r = client.post(
        f"/v0/orgs/{org_id}/credentials",
        json={
            "kind_key": "httpHeaderAuth",
            "name": "Blocked Exp",
            "fields": {"name": "Authorization", "value": "Bearer x"},
        },
        headers=headers,
    )
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_create_experimental_credential_allowed_with_org_flag(
    org_and_users, test_db, monkeypatch
):
    from bson import ObjectId

    org_id = org_and_users["org_id"]
    member = org_and_users["member"]
    headers = get_token_headers(member["token"])

    await test_db.organizations.update_one(
        {"_id": ObjectId(org_id)},
        {"$set": {"experimental_features": True}},
    )

    real_get = ad.flows.get_credential_kind

    def get_kind_exp(key: str):
        k = dict(real_get(key))
        k["experimental"] = True
        return k

    monkeypatch.setattr(ad.flows, "get_credential_kind", get_kind_exp)

    r = client.post(
        f"/v0/orgs/{org_id}/credentials",
        json={
            "kind_key": "httpHeaderAuth",
            "name": "Allowed Exp",
            "fields": {"name": "Authorization", "value": "Bearer x"},
        },
        headers=headers,
    )
    assert r.status_code == 200, r.text
