import json

import pytest

from .conftest_utils import client, TEST_ORG_ID, get_auth_headers


def _list_prompts(params: dict) -> dict:
    resp = client.get(
        f"/v0/orgs/{TEST_ORG_ID}/prompts",
        params=params,
        headers=get_auth_headers(),
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


@pytest.mark.asyncio
async def test_prompts_grid_sort_filters_focused(test_db, mock_auth, setup_test_models):
    """
    Coverage for JSON `sort` and `filters` on GET /prompts (MUI DataGrid server mode).
    """

    cv_tag = client.post(
        f"/v0/orgs/{TEST_ORG_ID}/tags",
        json={"name": "CV", "color": "#FF0000"},
        headers=get_auth_headers(),
    )
    assert cv_tag.status_code == 200, cv_tag.text
    cv_tag_id = cv_tag.json()["id"]

    finance_tag = client.post(
        f"/v0/orgs/{TEST_ORG_ID}/tags",
        json={"name": "Finance", "color": "#00FF00"},
        headers=get_auth_headers(),
    )
    assert finance_tag.status_code == 200, finance_tag.text
    finance_tag_id = finance_tag.json()["id"]

    p1 = client.post(
        f"/v0/orgs/{TEST_ORG_ID}/prompts",
        json={
            "name": "Alpha Prompt",
            "content": "c1",
            "model": "gpt-4o-mini",
            "tag_ids": [cv_tag_id],
        },
        headers=get_auth_headers(),
    )
    assert p1.status_code == 200, p1.text
    rev1 = p1.json()["prompt_revid"]

    p2 = client.post(
        f"/v0/orgs/{TEST_ORG_ID}/prompts",
        json={
            "name": "Beta Prompt",
            "content": "c2",
            "model": "gpt-4o",
            "tag_ids": [finance_tag_id],
        },
        headers=get_auth_headers(),
    )
    assert p2.status_code == 200, p2.text
    rev2 = p2.json()["prompt_revid"]

    p3 = client.post(
        f"/v0/orgs/{TEST_ORG_ID}/prompts",
        json={
            "name": "Gamma Prompt",
            "content": "c3",
            "model": "gpt-4o-mini",
            "tag_ids": [],
        },
        headers=get_auth_headers(),
    )
    assert p3.status_code == 200, p3.text
    rev3 = p3.json()["prompt_revid"]

    from bson import ObjectId
    from datetime import datetime, UTC

    revs = test_db["prompt_revisions"]
    await revs.update_one(
        {"_id": ObjectId(rev1)},
        {"$set": {"created_at": datetime(2026, 1, 1, tzinfo=UTC)}},
    )
    await revs.update_one(
        {"_id": ObjectId(rev2)},
        {"$set": {"created_at": datetime(2026, 2, 1, tzinfo=UTC)}},
    )
    await revs.update_one(
        {"_id": ObjectId(rev3)},
        {"$set": {"created_at": datetime(2026, 3, 1, tzinfo=UTC)}},
    )

    # name_search (existing)
    r = _list_prompts({"name_search": "Beta", "limit": 50})
    names = {p["name"] for p in r["prompts"]}
    assert names == {"Beta Prompt"}

    # Grid filter: name contains
    filters = json.dumps(
        {
            "items": [
                {"field": "name", "operator": "contains", "value": "Gamma"},
            ],
            "logicOperator": "and",
        }
    )
    r = _list_prompts({"filters": filters, "limit": 50})
    names = {p["name"] for p in r["prompts"]}
    assert names == {"Gamma Prompt"}

    # Grid filter: model equals
    filters = json.dumps(
        {
            "items": [
                {"field": "model", "operator": "equals", "value": "gpt-4o"},
            ],
            "logicOperator": "and",
        }
    )
    r = _list_prompts({"filters": filters, "limit": 50})
    names = {p["name"] for p in r["prompts"]}
    assert names == {"Beta Prompt"}

    # Tag filter by tag name (contains "CV" — distinct from Finance)
    filters = json.dumps(
        {
            "items": [
                {"field": "tag_ids", "operator": "contains", "value": "CV"},
            ],
            "logicOperator": "and",
        }
    )
    r = _list_prompts({"filters": filters, "limit": 50})
    names = {p["name"] for p in r["prompts"]}
    assert names == {"Alpha Prompt"}

    # Sort by name ascending
    sort = json.dumps([{"field": "name", "sort": "asc"}])
    r = _list_prompts({"sort": sort, "limit": 50})
    ordered = [p["name"] for p in r["prompts"]]
    assert ordered == ["Alpha Prompt", "Beta Prompt", "Gamma Prompt"]

    # Sort by created_at ascending
    sort = json.dumps([{"field": "created_at", "sort": "asc"}])
    r = _list_prompts({"sort": sort, "limit": 50})
    ordered = [p["name"] for p in r["prompts"]]
    assert ordered == ["Alpha Prompt", "Beta Prompt", "Gamma Prompt"]

    # Pagination: first page size 1
    sort = json.dumps([{"field": "name", "sort": "asc"}])
    r = _list_prompts({"sort": sort, "skip": 0, "limit": 1})
    assert r["total_count"] == 3
    assert len(r["prompts"]) == 1
    assert r["prompts"][0]["name"] == "Alpha Prompt"

    r = _list_prompts({"sort": sort, "skip": 1, "limit": 1})
    assert len(r["prompts"]) == 1
    assert r["prompts"][0]["name"] == "Beta Prompt"

    # Sort by prompt_version is ignored (falls back to default _id tiebreaker)
    sort = json.dumps([{"field": "prompt_version", "sort": "asc"}])
    r = _list_prompts({"sort": sort, "limit": 50})
    assert len(r["prompts"]) == 3

    bad = client.get(
        f"/v0/orgs/{TEST_ORG_ID}/prompts",
        params={"sort": "not-json"},
        headers=get_auth_headers(),
    )
    assert bad.status_code == 400


@pytest.mark.asyncio
async def test_prompts_schema_column_filter_resolves_display_name(mock_auth, setup_test_models):
    """Grid sends field=schema_id but user types schema *name* (contains)."""
    schema_data = {
        "name": "ZebraFilterSchemaX",
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": "zebra_test",
                "schema": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {"a": {"type": "string"}},
                    "required": ["a"],
                },
                "strict": True,
            },
        },
    }
    sch = client.post(
        f"/v0/orgs/{TEST_ORG_ID}/schemas",
        json=schema_data,
        headers=get_auth_headers(),
    )
    assert sch.status_code == 200, sch.text
    schema_id = sch.json()["schema_id"]

    p_schema = client.post(
        f"/v0/orgs/{TEST_ORG_ID}/prompts",
        json={
            "name": "Prompt With Zebra Schema",
            "content": "x",
            "model": "gpt-4o-mini",
            "schema_id": schema_id,
            "schema_version": 1,
            "tag_ids": [],
        },
        headers=get_auth_headers(),
    )
    assert p_schema.status_code == 200, p_schema.text

    p_plain = client.post(
        f"/v0/orgs/{TEST_ORG_ID}/prompts",
        json={
            "name": "Prompt No Schema",
            "content": "y",
            "model": "gpt-4o-mini",
            "tag_ids": [],
        },
        headers=get_auth_headers(),
    )
    assert p_plain.status_code == 200, p_plain.text

    filters = json.dumps(
        {
            "items": [
                {"field": "schema_id", "operator": "contains", "value": "Zebra"},
            ],
            "logicOperator": "and",
        }
    )
    r = _list_prompts({"filters": filters, "limit": 50})
    names = {p["name"] for p in r["prompts"]}
    assert names == {"Prompt With Zebra Schema"}
