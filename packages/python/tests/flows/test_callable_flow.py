"""Callable flow validation and list filter tests."""

from __future__ import annotations

import pytest

from analytiq_data.flows.callable_flow import validate_callable_flow_revision
from analytiq_data.flows.engine import FlowValidationError
from tests.conftest_utils import TEST_ORG_ID, client, get_auth_headers


def _tool_trigger() -> dict:
    return {
        "id": "tt1",
        "name": "Tool entry",
        "type": "flows.trigger.tool",
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


def test_validate_callable_flow_revision_ok() -> None:
    validate_callable_flow_revision([_tool_trigger()], {})


def test_validate_callable_flow_revision_two_triggers() -> None:
    nodes = [_tool_trigger(), {**_tool_trigger(), "id": "tt2", "name": "Tool entry 2"}]
    with pytest.raises(FlowValidationError, match="exactly one"):
        validate_callable_flow_revision(nodes, {})


@pytest.mark.asyncio
async def test_list_flows_callable_as_tool_filter(test_db, mock_auth) -> None:
    r_callable = client.post(
        f"/v0/orgs/{TEST_ORG_ID}/flows",
        json={"name": "Callable list filter"},
        headers=get_auth_headers(),
    )
    callable_id = r_callable.json()["flow"]["flow_id"]
    client.patch(
        f"/v0/orgs/{TEST_ORG_ID}/flows/{callable_id}",
        json={"callable_as_tool": True},
        headers=get_auth_headers(),
    )

    r_other = client.post(
        f"/v0/orgs/{TEST_ORG_ID}/flows",
        json={"name": "Not callable list filter"},
        headers=get_auth_headers(),
    )
    other_id = r_other.json()["flow"]["flow_id"]

    r_list = client.get(
        f"/v0/orgs/{TEST_ORG_ID}/flows",
        params={"callable_as_tool": "true", "include_unsaved": "true", "limit": 200},
        headers=get_auth_headers(),
    )
    assert r_list.status_code == 200, r_list.text
    ids = {x["flow"]["flow_id"] for x in r_list.json()["items"]}
    assert callable_id in ids
    assert other_id not in ids


@pytest.mark.asyncio
async def test_activate_callable_flow_requires_tool_graph(test_db, mock_auth) -> None:
    r_flow = client.post(
        f"/v0/orgs/{TEST_ORG_ID}/flows",
        json={"name": "Bad callable activate"},
        headers=get_auth_headers(),
    )
    flow_id = r_flow.json()["flow"]["flow_id"]
    client.patch(
        f"/v0/orgs/{TEST_ORG_ID}/flows/{flow_id}",
        json={"callable_as_tool": True},
        headers=get_auth_headers(),
    )
    client.put(
        f"/v0/orgs/{TEST_ORG_ID}/flows/{flow_id}",
        json={
            "base_flow_revid": "",
            "name": "Bad callable activate",
            "nodes": [
                {
                    "id": "m1",
                    "name": "Manual",
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
            ],
            "connections": {},
            "settings": {},
            "pin_data": None,
        },
        headers=get_auth_headers(),
    )

    r_act = client.post(
        f"/v0/orgs/{TEST_ORG_ID}/flows/{flow_id}/activate",
        json={},
        headers=get_auth_headers(),
    )
    assert r_act.status_code == 400, r_act.text
    assert "sub-flow entry" in r_act.json()["detail"].lower()


@pytest.mark.asyncio
async def test_patch_callable_as_tool_validates_revision(test_db, mock_auth) -> None:
    r_flow = client.post(
        f"/v0/orgs/{TEST_ORG_ID}/flows",
        json={"name": "Patch callable validate"},
        headers=get_auth_headers(),
    )
    flow_id = r_flow.json()["flow"]["flow_id"]
    client.put(
        f"/v0/orgs/{TEST_ORG_ID}/flows/{flow_id}",
        json={
            "base_flow_revid": "",
            "name": "Patch callable validate",
            "nodes": [
                {
                    "id": "m1",
                    "name": "Manual",
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
            ],
            "connections": {},
            "settings": {},
            "pin_data": None,
        },
        headers=get_auth_headers(),
    )

    r_patch = client.patch(
        f"/v0/orgs/{TEST_ORG_ID}/flows/{flow_id}",
        json={"callable_as_tool": True},
        headers=get_auth_headers(),
    )
    assert r_patch.status_code == 400, r_patch.text
    assert "sub-flow entry" in r_patch.json()["detail"].lower()
