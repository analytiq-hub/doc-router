import json

import pytest

from .conftest_utils import TEST_ORG_ID, client, get_auth_headers


def _minimal_schema_body(name: str) -> dict:
    return {
        "name": name,
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": "grid_test",
                "strict": True,
                "schema": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {"a": {"type": "string"}},
                    "required": ["a"],
                },
            },
        },
    }


def _list_schemas(params: dict) -> dict:
    resp = client.get(
        f"/v0/orgs/{TEST_ORG_ID}/schemas",
        params=params,
        headers=get_auth_headers(),
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


@pytest.mark.asyncio
async def test_schemas_grid_sort_filters_focused(test_db, mock_auth):
    for name in ("Gamma Schema", "Alpha Schema", "Beta Schema"):
        r = client.post(
            f"/v0/orgs/{TEST_ORG_ID}/schemas",
            json=_minimal_schema_body(name),
            headers=get_auth_headers(),
        )
        assert r.status_code == 200, r.text

    sort = json.dumps([{"field": "name", "sort": "asc"}])
    r = _list_schemas({"sort": sort, "limit": 50})
    assert r["total_count"] == 3
    ordered = [s["name"] for s in r["schemas"]]
    assert ordered == ["Alpha Schema", "Beta Schema", "Gamma Schema"]

    filters = json.dumps(
        {
            "items": [{"field": "name", "operator": "contains", "value": "Beta"}],
            "logicOperator": "and",
        }
    )
    r = _list_schemas({"filters": filters, "limit": 50})
    assert r["total_count"] == 1
    assert r["schemas"][0]["name"] == "Beta Schema"

    sort = json.dumps([{"field": "name", "sort": "asc"}])
    r = _list_schemas({"sort": sort, "skip": 0, "limit": 1})
    assert r["total_count"] == 3
    assert len(r["schemas"]) == 1
    assert r["schemas"][0]["name"] == "Alpha Schema"

    r = _list_schemas({"sort": sort, "skip": 1, "limit": 1})
    assert len(r["schemas"]) == 1
    assert r["schemas"][0]["name"] == "Beta Schema"

    bad = client.get(
        f"/v0/orgs/{TEST_ORG_ID}/schemas",
        params={"sort": "not-json"},
        headers=get_auth_headers(),
    )
    assert bad.status_code == 400

    bad_f = client.get(
        f"/v0/orgs/{TEST_ORG_ID}/schemas",
        params={"filters": "not-json"},
        headers=get_auth_headers(),
    )
    assert bad_f.status_code == 400
