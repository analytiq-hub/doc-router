import json

import pytest
from bson import ObjectId

from .conftest_utils import TEST_ORG_ID, client, get_auth_headers


def _tag_body(name: str, description: str) -> dict:
    return {"name": name, "color": "#336699", "description": description}


def _list_tags(params: dict) -> dict:
    resp = client.get(
        f"/v0/orgs/{TEST_ORG_ID}/tags",
        params=params,
        headers=get_auth_headers(),
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


@pytest.mark.asyncio
async def test_tags_grid_sort_filters_focused(test_db, mock_auth):
    for name, desc in (
        ("Gamma Tag", "third"),
        ("Alpha Tag", "first"),
        ("Beta Tag", "second"),
    ):
        r = client.post(
            f"/v0/orgs/{TEST_ORG_ID}/tags",
            json=_tag_body(name, desc),
            headers=get_auth_headers(),
        )
        assert r.status_code == 200, r.text

    sort = json.dumps([{"field": "name", "sort": "asc"}])
    r = _list_tags({"sort": sort, "limit": 50})
    assert r["total_count"] == 3
    ordered = [t["name"] for t in r["tags"]]
    assert ordered == ["Alpha Tag", "Beta Tag", "Gamma Tag"]

    filters = json.dumps(
        {
            "items": [{"field": "name", "operator": "contains", "value": "Beta"}],
            "logicOperator": "and",
        }
    )
    r = _list_tags({"filters": filters, "limit": 50})
    assert r["total_count"] == 1
    assert r["tags"][0]["name"] == "Beta Tag"

    sort = json.dumps([{"field": "name", "sort": "asc"}])
    r = _list_tags({"sort": sort, "skip": 0, "limit": 1})
    assert r["total_count"] == 3
    assert len(r["tags"]) == 1
    assert r["tags"][0]["name"] == "Alpha Tag"

    r = _list_tags({"sort": sort, "skip": 1, "limit": 1})
    assert len(r["tags"]) == 1
    assert r["tags"][0]["name"] == "Beta Tag"

    r = _list_tags({"name_search": "Gamma", "limit": 50})
    assert r["total_count"] == 1
    assert r["tags"][0]["name"] == "Gamma Tag"

    bad = client.get(
        f"/v0/orgs/{TEST_ORG_ID}/tags",
        params={"sort": "not-json"},
        headers=get_auth_headers(),
    )
    assert bad.status_code == 400

    bad_f = client.get(
        f"/v0/orgs/{TEST_ORG_ID}/tags",
        params={"filters": "not-json"},
        headers=get_auth_headers(),
    )
    assert bad_f.status_code == 400


def _create_tag(name: str) -> str:
    r = client.post(
        f"/v0/orgs/{TEST_ORG_ID}/tags",
        json={"name": name, "color": "#000000"},
        headers=get_auth_headers(),
    )
    assert r.status_code == 200, r.text
    return r.json()["id"]


@pytest.mark.asyncio
async def test_tag_name_search_match_rank_exact_prefix_substring(test_db, mock_auth):
    """
    Rank 0 (exact) beats rank 1 (prefix) beats rank 2 (substring),
    even when lower-ranked tags have a larger _id (inserted later).

    Search "invoice":
      "invoice"            → exact (rank 0)
      "invoice processing" → starts with "invoice" (rank 1)
      "my invoice"         → contains "invoice" (rank 2)
    """
    # Insert in ascending rank order so _id order would give wrong result without ranking
    id_exact = _create_tag("invoice")
    id_prefix = _create_tag("invoice processing")
    id_substr = _create_tag("my invoice")

    r = _list_tags({"name_search": "invoice", "limit": 50})
    ids = [t["id"] for t in r["tags"]]

    assert id_exact in ids and id_prefix in ids and id_substr in ids
    assert ids.index(id_exact) < ids.index(id_prefix), "exact must precede prefix"
    assert ids.index(id_prefix) < ids.index(id_substr), "prefix must precede substring"


@pytest.mark.asyncio
async def test_tag_name_search_exact_beats_substring_older(test_db, mock_auth):
    """
    Tag named "invoice" (smaller _id) ranks above "sub_invoice" (larger _id, substring match).
    """
    id_exact = _create_tag("invoice")
    id_substr = _create_tag("sub_invoice")

    r = _list_tags({"name_search": "invoice", "limit": 50})
    ids = [t["id"] for t in r["tags"]]

    assert id_exact in ids and id_substr in ids
    assert ids.index(id_exact) < ids.index(id_substr), "exact must rank above substring even with smaller _id"


@pytest.mark.asyncio
async def test_tag_name_search_same_rank_id_tiebreaker(test_db, mock_auth):
    """
    Two substring-match tags are ordered by _id DESC (newer insertion first).
    """
    id_old = _create_tag("vendor invoice")
    id_new = _create_tag("past invoice")

    r = _list_tags({"name_search": "invoice", "limit": 50})
    ids = [t["id"] for t in r["tags"]]

    assert id_old in ids and id_new in ids
    assert ids.index(id_new) < ids.index(id_old), "within same rank, larger _id (newer) should come first"


@pytest.mark.asyncio
async def test_tag_name_search_case_insensitive_exact(test_db, mock_auth):
    """
    Searching 'INVOICE' gives rank 0 for 'invoice' and rank 1 for 'invoice run'.
    The older exact match must rank first.
    """
    id_exact = _create_tag("invoice")
    id_prefix = _create_tag("invoice run")

    r = _list_tags({"name_search": "INVOICE", "limit": 50})
    ids = [t["id"] for t in r["tags"]]

    assert id_exact in ids and id_prefix in ids
    assert ids.index(id_exact) < ids.index(id_prefix), "case-insensitive exact should rank first"
