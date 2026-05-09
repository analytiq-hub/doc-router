"""Tests for GET /flows list behavior (saved vs draft-only flows)."""

from __future__ import annotations

import pytest

from tests.conftest_utils import TEST_ORG_ID, client, get_auth_headers


def _std_manual_node() -> dict:
    return {
        "id": "t1",
        "name": "Start",
        "type": "flows.trigger.manual",
        "position": [0, 0],
        "parameters": {},
        "webhook_id": None,
        "disabled": False,
        "on_error": "stop",
        "retry_on_fail": False,
        "max_tries": 1,
        "wait_between_tries_ms": 1000,
        "notes": None,
    }


@pytest.mark.asyncio
async def test_list_flows_aggregate_total_matches_default_filter(test_db, mock_auth):
    """
    Default list total excludes header-only flows; ``include_unsaved`` total counts them — same
    filter pipeline as paginated ``items``.
    """
    r_saved = client.post(
        f"/v0/orgs/{TEST_ORG_ID}/flows",
        json={
            "name": "List total helper saved",
            "nodes": [_std_manual_node()],
            "connections": {},
            "settings": {},
            "pin_data": None,
        },
        headers=get_auth_headers(),
    )
    assert r_saved.status_code == 200, r_saved.text
    saved_id = r_saved.json()["flow"]["flow_id"]

    r_hi = client.post(
        f"/v0/orgs/{TEST_ORG_ID}/flows",
        json={"name": "List total helper header only"},
        headers=get_auth_headers(),
    )
    assert r_hi.status_code == 200, r_hi.text
    orphan_id = r_hi.json()["flow"]["flow_id"]

    limit = 200
    r_def = client.get(
        f"/v0/orgs/{TEST_ORG_ID}/flows",
        params={"limit": limit, "offset": 0},
        headers=get_auth_headers(),
    )
    assert r_def.status_code == 200, r_def.text
    body_def = r_def.json()
    assert body_def["total"] >= len(body_def["items"])
    listed_def = {x["flow"]["flow_id"] for x in body_def["items"]}
    assert saved_id in listed_def and orphan_id not in listed_def

    r_inc = client.get(
        f"/v0/orgs/{TEST_ORG_ID}/flows",
        params={"limit": limit, "offset": 0, "include_unsaved": "true"},
        headers=get_auth_headers(),
    )
    assert r_inc.status_code == 200, r_inc.text
    listed_inc = {x["flow"]["flow_id"] for x in r_inc.json()["items"]}
    assert orphan_id in listed_inc
    assert r_inc.json()["total"] >= r_def.json()["total"]

    client.delete(f"/v0/orgs/{TEST_ORG_ID}/flows/{saved_id}", headers=get_auth_headers())
    client.delete(f"/v0/orgs/{TEST_ORG_ID}/flows/{orphan_id}", headers=get_auth_headers())


@pytest.mark.asyncio
async def test_list_flows_hides_flow_without_revision_unless_include_unsaved(test_db, mock_auth):
    """Draft-only flow (POST create, no PUT save) is omitted from the default list."""

    r0 = client.post(
        f"/v0/orgs/{TEST_ORG_ID}/flows",
        json={"name": "List hide draft only"},
        headers=get_auth_headers(),
    )
    assert r0.status_code == 200, r0.text
    flow_id = r0.json()["flow"]["flow_id"]

    r_list = client.get(
        f"/v0/orgs/{TEST_ORG_ID}/flows",
        params={"limit": 200, "offset": 0},
        headers=get_auth_headers(),
    )
    assert r_list.status_code == 200, r_list.text
    body = r_list.json()
    listed = {x["flow"]["flow_id"] for x in body["items"]}
    assert flow_id not in listed
    assert body["total"] >= 0

    r_unsaved = client.get(
        f"/v0/orgs/{TEST_ORG_ID}/flows",
        params={"limit": 200, "offset": 0, "include_unsaved": "true"},
        headers=get_auth_headers(),
    )
    assert r_unsaved.status_code == 200, r_unsaved.text
    body_u = r_unsaved.json()
    listed_u = {x["flow"]["flow_id"] for x in body_u["items"]}
    assert flow_id in listed_u

    r1 = client.put(
        f"/v0/orgs/{TEST_ORG_ID}/flows/{flow_id}",
        json={
            "base_flow_revid": "",
            "name": "List hide draft only",
            "nodes": [_std_manual_node()],
            "connections": {},
            "settings": {},
            "pin_data": None,
        },
        headers=get_auth_headers(),
    )
    assert r1.status_code == 200, r1.text
    assert r1.json()["revision"] is not None

    r_after = client.get(
        f"/v0/orgs/{TEST_ORG_ID}/flows",
        params={"limit": 200, "offset": 0},
        headers=get_auth_headers(),
    )
    assert r_after.status_code == 200, r_after.text
    listed_after = {x["flow"]["flow_id"] for x in r_after.json()["items"]}
    assert flow_id in listed_after

    r_del = client.delete(
        f"/v0/orgs/{TEST_ORG_ID}/flows/{flow_id}",
        headers=get_auth_headers(),
    )
    assert r_del.status_code == 200, r_del.text
