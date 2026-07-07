import pytest
import pytest_asyncio
from bson import ObjectId
from datetime import datetime, UTC

from app import limits
from .conftest_utils import client, get_auth_headers


def _list_orgs(params: dict | None = None):
    return client.get(
        "/v0/account/organizations",
        params=params or {},
        headers=get_auth_headers(),
    )


def _list_users(params: dict | None = None):
    return client.get(
        "/v0/account/users",
        params=params or {},
        headers=get_auth_headers(),
    )


async def _seed_search_fixtures(test_db) -> dict[str, str]:
    now = datetime.now(UTC)
    alice_id = str(ObjectId())
    bob_id = str(ObjectId())
    regex_user_id = str(ObjectId())

    await test_db.users.insert_many([
        {
            "_id": ObjectId(alice_id),
            "email": "alice.search@example.com",
            "name": "Alice Searchable",
            "role": "user",
            "email_verified": True,
            "has_password": True,
            "created_at": now,
        },
        {
            "_id": ObjectId(bob_id),
            "email": "bob.member@example.com",
            "name": "Bob Member",
            "role": "user",
            "email_verified": True,
            "has_password": True,
            "created_at": now,
        },
        {
            "_id": ObjectId(regex_user_id),
            "email": "literal.(a+)+@example.com",
            "name": "Literal Regex User",
            "role": "user",
            "email_verified": True,
            "has_password": True,
            "created_at": now,
        },
    ])

    acme_org_id = str(ObjectId())
    beta_org_id = str(ObjectId())
    literal_org_id = str(ObjectId())

    await test_db.organizations.insert_many([
        {
            "_id": ObjectId(acme_org_id),
            "name": "Acme Invoice Team",
            "members": [{"user_id": alice_id, "role": "admin"}],
            "type": "team",
            "created_at": now,
            "updated_at": now,
        },
        {
            "_id": ObjectId(beta_org_id),
            "name": "Beta Corporation",
            "members": [{"user_id": bob_id, "role": "user"}],
            "type": "team",
            "created_at": now,
            "updated_at": now,
        },
        {
            "_id": ObjectId(literal_org_id),
            "name": "Literal (.*) Org",
            "members": [{"user_id": regex_user_id, "role": "user"}],
            "type": "team",
            "created_at": now,
            "updated_at": now,
        },
    ])

    return {
        "alice_id": alice_id,
        "bob_id": bob_id,
        "regex_user_id": regex_user_id,
        "acme_org_id": acme_org_id,
        "beta_org_id": beta_org_id,
        "literal_org_id": literal_org_id,
    }


@pytest_asyncio.fixture
async def search_fixtures(test_db):
    return await _seed_search_fixtures(test_db)


@pytest.mark.asyncio
async def test_org_name_search_substring_case_insensitive(search_fixtures, mock_auth):
    resp = _list_orgs({"name_search": "invoice"})
    assert resp.status_code == 200, resp.text
    data = resp.json()
    names = {org["name"] for org in data["organizations"]}
    assert names == {"Acme Invoice Team"}

    resp = _list_orgs({"name_search": "INVOICE"})
    assert resp.status_code == 200, resp.text
    assert resp.json()["total_count"] == 1


@pytest.mark.asyncio
async def test_org_name_search_treats_regex_metacharacters_literally(search_fixtures, mock_auth):
    resp = _list_orgs({"name_search": ".*"})
    assert resp.status_code == 200, resp.text
    data = resp.json()
    names = {org["name"] for org in data["organizations"]}
    assert names == {"Literal (.*) Org"}


@pytest.mark.asyncio
async def test_org_name_search_rejects_overlong_term(search_fixtures, mock_auth):
    overlong = "a" * (limits.MAX_SEARCH_TERM_LENGTH + 1)
    resp = _list_orgs({"name_search": overlong})
    assert resp.status_code == 400
    assert f"maximum length of {limits.MAX_SEARCH_TERM_LENGTH}" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_org_member_search_by_name_and_email(search_fixtures, mock_auth):
    resp = _list_orgs({"member_search": "alice.search"})
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["total_count"] == 1
    assert data["organizations"][0]["name"] == "Acme Invoice Team"

    resp = _list_orgs({"member_search": "bob.member@"})
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["total_count"] == 1
    assert data["organizations"][0]["name"] == "Beta Corporation"


@pytest.mark.asyncio
async def test_org_member_search_treats_regex_metacharacters_literally(search_fixtures, mock_auth):
    resp = _list_orgs({"member_search": "(a+)+"})
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["total_count"] == 1
    assert data["organizations"][0]["name"] == "Literal (.*) Org"


@pytest.mark.asyncio
async def test_org_member_search_no_match_returns_empty(search_fixtures, mock_auth):
    resp = _list_orgs({"member_search": "definitely-not-a-member"})
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["organizations"] == []
    assert data["total_count"] == 0


@pytest.mark.asyncio
async def test_org_member_search_rejects_overlong_term(search_fixtures, mock_auth):
    overlong = "a" * (limits.MAX_SEARCH_TERM_LENGTH + 1)
    resp = _list_orgs({"member_search": overlong})
    assert resp.status_code == 400
    assert f"maximum length of {limits.MAX_SEARCH_TERM_LENGTH}" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_user_search_name_substring_case_insensitive(search_fixtures, mock_auth):
    resp = _list_users({"search_name": "searchable"})
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["total_count"] == 1
    assert data["users"][0]["name"] == "Alice Searchable"

    resp = _list_users({"search_name": "ALICE.SEARCH@"})
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["total_count"] == 1
    assert data["users"][0]["email"] == "alice.search@example.com"


@pytest.mark.asyncio
async def test_user_search_name_treats_regex_metacharacters_literally(search_fixtures, mock_auth):
    resp = _list_users({"search_name": "(a+)+"})
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["total_count"] == 1
    assert data["users"][0]["email"] == "literal.(a+)+@example.com"


@pytest.mark.asyncio
async def test_user_search_name_rejects_overlong_term(search_fixtures, mock_auth):
    overlong = "a" * (limits.MAX_SEARCH_TERM_LENGTH + 1)
    resp = _list_users({"search_name": overlong})
    assert resp.status_code == 400
    assert f"maximum length of {limits.MAX_SEARCH_TERM_LENGTH}" in resp.json()["detail"]
