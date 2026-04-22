import json

import pytest

from .conftest_utils import TEST_ORG_ID, client, get_auth_headers
from .kb_test_helpers import insert_minimal_kb, insert_org_tag


def _list_kbs(params: dict) -> dict:
    resp = client.get(
        f"/v0/orgs/{TEST_ORG_ID}/knowledge-bases",
        params=params,
        headers=get_auth_headers(),
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


@pytest.mark.asyncio
async def test_knowledge_bases_grid_sort_filters_focused(test_db, mock_auth):
    await insert_minimal_kb(test_db, [], name="Gamma KB", description="third")
    await insert_minimal_kb(test_db, [], name="Alpha KB", description="first")
    await insert_minimal_kb(test_db, [], name="Beta KB", description="second")

    sort = json.dumps([{"field": "name", "sort": "asc"}])
    r = _list_kbs({"sort": sort, "limit": 50})
    assert r["total_count"] == 3
    ordered = [k["name"] for k in r["knowledge_bases"]]
    assert ordered == ["Alpha KB", "Beta KB", "Gamma KB"]

    filters = json.dumps(
        {
            "items": [{"field": "name", "operator": "contains", "value": "Beta"}],
            "logicOperator": "and",
        }
    )
    r = _list_kbs({"filters": filters, "limit": 50})
    assert r["total_count"] == 1
    assert r["knowledge_bases"][0]["name"] == "Beta KB"

    sort = json.dumps([{"field": "name", "sort": "asc"}])
    r = _list_kbs({"sort": sort, "skip": 0, "limit": 1})
    assert r["total_count"] == 3
    assert len(r["knowledge_bases"]) == 1
    assert r["knowledge_bases"][0]["name"] == "Alpha KB"

    r = _list_kbs({"sort": sort, "skip": 1, "limit": 1})
    assert len(r["knowledge_bases"]) == 1
    assert r["knowledge_bases"][0]["name"] == "Beta KB"

    r = _list_kbs({"name_search": "Gamma", "limit": 50})
    assert r["total_count"] == 1
    assert r["knowledge_bases"][0]["name"] == "Gamma KB"

    bad = client.get(
        f"/v0/orgs/{TEST_ORG_ID}/knowledge-bases",
        params={"sort": "not-json"},
        headers=get_auth_headers(),
    )
    assert bad.status_code == 400

    bad_f = client.get(
        f"/v0/orgs/{TEST_ORG_ID}/knowledge-bases",
        params={"filters": "not-json"},
        headers=get_auth_headers(),
    )
    assert bad_f.status_code == 400


@pytest.mark.asyncio
async def test_knowledge_bases_grid_tag_filter_resolves_tag_name(test_db, mock_auth):
    """MUI tag column filters by display name; KB rows store ``tag_ids`` (ids), like prompts."""
    tag_id = await insert_org_tag(test_db, "UniqueGridTagName")
    await insert_minimal_kb(test_db, [tag_id], name="KB With Tag", description="has tag")
    await insert_minimal_kb(test_db, [], name="KB No Tag", description="no tag")

    filters = json.dumps(
        {
            "items": [{"field": "tag_ids", "operator": "contains", "value": "UniqueGrid"}],
            "logicOperator": "and",
        }
    )
    r = _list_kbs({"filters": filters, "limit": 50})
    assert r["total_count"] == 1
    assert r["knowledge_bases"][0]["name"] == "KB With Tag"

    filters_is = json.dumps(
        {
            "items": [{"field": "tag_ids", "operator": "is", "value": "UniqueGridTagName"}],
            "logicOperator": "and",
        }
    )
    r2 = _list_kbs({"filters": filters_is, "limit": 50})
    assert r2["total_count"] == 1
    assert r2["knowledge_bases"][0]["name"] == "KB With Tag"

    filters_any = json.dumps(
        {
            "items": [
                {
                    "field": "tag_ids",
                    "operator": "isAnyOf",
                    "value": ["UniqueGridTagName"],
                }
            ],
            "logicOperator": "and",
        }
    )
    r3 = _list_kbs({"filters": filters_any, "limit": 50})
    assert r3["total_count"] == 1
    assert r3["knowledge_bases"][0]["name"] == "KB With Tag"
