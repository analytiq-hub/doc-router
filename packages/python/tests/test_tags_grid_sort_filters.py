import json

import pytest

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
