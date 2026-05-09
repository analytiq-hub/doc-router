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


@pytest.mark.asyncio
async def test_form_name_search_match_rank_exact_prefix_substring(test_db, mock_auth):
    """
    Rank 0 (exact) beats rank 1 (prefix) beats rank 2 (substring).
    Forms are created in ascending-_id order so without ranking the default
    _id-DESC sort would return them in reverse; ranking must override that.

    Search "invoice":
      "invoice"            → exact (rank 0)
      "invoice processor"  → starts with "invoice" (rank 1)
      "my invoice"         → contains "invoice" (rank 2)
    """
    _create_form("invoice")
    _create_form("invoice processor")
    _create_form("my invoice")

    r = _list_forms({"name_search": "invoice", "limit": 50})
    names = [f["name"] for f in r["forms"]]

    assert "invoice" in names and "invoice processor" in names and "my invoice" in names
    assert names.index("invoice") < names.index("invoice processor"), "exact must precede prefix"
    assert names.index("invoice processor") < names.index("my invoice"), "prefix must precede substring"


@pytest.mark.asyncio
async def test_form_name_search_case_insensitive_exact(test_db, mock_auth):
    """
    Searching 'INVOICE' gives rank 0 for 'invoice' and rank 1 for 'invoice run'.
    The older exact match must rank first despite having a smaller _id.
    """
    _create_form("invoice")
    _create_form("invoice run")

    r = _list_forms({"name_search": "INVOICE", "limit": 50})
    names = [f["name"] for f in r["forms"]]

    assert "invoice" in names and "invoice run" in names
    assert names.index("invoice") < names.index("invoice run"), "case-insensitive exact should rank first"
