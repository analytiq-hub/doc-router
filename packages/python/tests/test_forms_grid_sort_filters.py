import json

import pytest

from .conftest_utils import TEST_ORG_ID, client, get_auth_headers

_MIN_FORMIO = [{"type": "textfield", "key": "k", "label": "L", "input": True}]


def _create_form(name: str) -> dict:
    r = client.post(
        f"/v0/orgs/{TEST_ORG_ID}/forms",
        json={"name": name, "response_format": {"json_formio": _MIN_FORMIO}, "tag_ids": []},
        headers=get_auth_headers(),
    )
    assert r.status_code == 200, r.text
    return r.json()


def _list_forms(params: dict) -> dict:
    resp = client.get(
        f"/v0/orgs/{TEST_ORG_ID}/forms",
        params=params,
        headers=get_auth_headers(),
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


@pytest.mark.asyncio
async def test_forms_grid_sort_filters_focused(test_db, mock_auth):
    for name in ("Gamma Form", "Alpha Form", "Beta Form"):
        _create_form(name)

    sort = json.dumps([{"field": "name", "sort": "asc"}])
    r = _list_forms({"sort": sort, "limit": 50})
    assert r["total_count"] == 3
    ordered = [f["name"] for f in r["forms"]]
    assert ordered == ["Alpha Form", "Beta Form", "Gamma Form"]

    filters = json.dumps(
        {
            "items": [{"field": "name", "operator": "contains", "value": "Beta"}],
            "logicOperator": "and",
        }
    )
    r = _list_forms({"filters": filters, "limit": 50})
    assert r["total_count"] == 1
    assert r["forms"][0]["name"] == "Beta Form"

    r = _list_forms({"name_search": "Gamma", "limit": 50})
    assert r["total_count"] == 1
    assert r["forms"][0]["name"] == "Gamma Form"

    bad = client.get(
        f"/v0/orgs/{TEST_ORG_ID}/forms",
        params={"sort": "not-json"},
        headers=get_auth_headers(),
    )
    assert bad.status_code == 400

    bad_f = client.get(
        f"/v0/orgs/{TEST_ORG_ID}/forms",
        params={"filters": "not-json"},
        headers=get_auth_headers(),
    )
    assert bad_f.status_code == 400
