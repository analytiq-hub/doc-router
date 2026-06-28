"""Delete protection when a flow is referenced by Flow Tool / Execute Flow."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from bson import ObjectId

from analytiq_data.flows.flow_references import find_flows_referencing_target
from tests.conftest_utils import TEST_ORG_ID, TEST_USER_ID, client, get_auth_headers


def _std_node(id_: str, ntype: str, *, parameters: dict | None = None) -> dict:
    return {
        "id": id_,
        "name": id_,
        "type": ntype,
        "position": [0, 0],
        "parameters": parameters or {},
        "webhook_id": None,
        "disabled": False,
        "on_error": "stop",
        "retry_on_fail": False,
        "max_tries": 1,
        "wait_between_tries_ms": 1000,
        "notes": None,
    }


async def _insert_latest_revision(db, *, flow_id: str, flow_version: int, nodes: list[dict]) -> None:
    now = datetime.now(UTC)
    await db.flow_revisions.insert_one(
        {
            "_id": ObjectId(),
            "flow_id": flow_id,
            "flow_version": flow_version,
            "nodes": nodes,
            "connections": {},
            "settings": {},
            "pin_data": None,
            "created_at": now,
            "created_by": TEST_USER_ID,
        }
    )
    await db.flows.update_one(
        {"_id": ObjectId(flow_id)},
        {"$set": {"flow_version": flow_version, "updated_at": now, "updated_by": TEST_USER_ID}},
    )


@pytest.mark.asyncio
async def test_find_flows_referencing_target(test_db) -> None:
    db = test_db
    target_oid = (await db.flows.insert_one({"organization_id": TEST_ORG_ID, "name": "Target"})).inserted_id
    parent_oid = (await db.flows.insert_one({"organization_id": TEST_ORG_ID, "name": "Parent"})).inserted_id
    target_id = str(target_oid)
    parent_id = str(parent_oid)

    await _insert_latest_revision(
        db,
        flow_id=parent_id,
        flow_version=1,
        nodes=[
            _std_node(
                "ft1",
                "flows.flow_tool",
                parameters={"target_flow_id": target_id, "tool_name": "t", "tool_description": "d"},
            )
        ],
    )

    refs = await find_flows_referencing_target(db, organization_id=TEST_ORG_ID, target_flow_id=target_id)
    assert len(refs) == 1
    assert refs[0].flow_id == parent_id
    assert refs[0].flow_name == "Parent"
    assert refs[0].node_type == "flows.flow_tool"


@pytest.mark.asyncio
async def test_delete_flow_blocked_when_referenced_by_flow_tool(test_db, mock_auth) -> None:
    db = test_db
    r_target = client.post(
        f"/v0/orgs/{TEST_ORG_ID}/flows",
        json={"name": "Callable target"},
        headers=get_auth_headers(),
    )
    target_id = r_target.json()["flow"]["flow_id"]

    r_parent = client.post(
        f"/v0/orgs/{TEST_ORG_ID}/flows",
        json={"name": "Agent parent"},
        headers=get_auth_headers(),
    )
    parent_id = r_parent.json()["flow"]["flow_id"]
    await _insert_latest_revision(
        db,
        flow_id=parent_id,
        flow_version=1,
        nodes=[
            _std_node(
                "ft",
                "flows.flow_tool",
                parameters={
                    "target_flow_id": target_id,
                    "tool_name": "my_tool",
                    "tool_description": "Runs callable target",
                },
            )
        ],
    )

    r_del = client.delete(
        f"/v0/orgs/{TEST_ORG_ID}/flows/{target_id}",
        headers=get_auth_headers(),
    )
    assert r_del.status_code == 409, r_del.text
    assert "Agent parent" in r_del.json()["detail"]
    assert "Flow Tool" in r_del.json()["detail"]

    assert client.get(f"/v0/orgs/{TEST_ORG_ID}/flows/{target_id}", headers=get_auth_headers()).status_code == 200


@pytest.mark.asyncio
async def test_delete_flow_blocked_when_referenced_by_execute_flow(test_db, mock_auth) -> None:
    db = test_db
    r_target = client.post(
        f"/v0/orgs/{TEST_ORG_ID}/flows",
        json={"name": "Subflow target"},
        headers=get_auth_headers(),
    )
    target_id = r_target.json()["flow"]["flow_id"]

    r_parent = client.post(
        f"/v0/orgs/{TEST_ORG_ID}/flows",
        json={"name": "Orchestrator"},
        headers=get_auth_headers(),
    )
    parent_id = r_parent.json()["flow"]["flow_id"]
    await _insert_latest_revision(
        db,
        flow_id=parent_id,
        flow_version=1,
        nodes=[
            _std_node("ef", "flows.execute_flow", parameters={"target_flow_id": target_id, "mode": "each"}),
        ],
    )

    r_del = client.delete(
        f"/v0/orgs/{TEST_ORG_ID}/flows/{target_id}",
        headers=get_auth_headers(),
    )
    assert r_del.status_code == 409, r_del.text
    assert "Orchestrator" in r_del.json()["detail"]
    assert "Execute Flow" in r_del.json()["detail"]


@pytest.mark.asyncio
async def test_delete_flow_allowed_after_reference_removed(test_db, mock_auth) -> None:
    db = test_db
    r_target = client.post(
        f"/v0/orgs/{TEST_ORG_ID}/flows",
        json={"name": "Removable target"},
        headers=get_auth_headers(),
    )
    target_id = r_target.json()["flow"]["flow_id"]

    r_parent = client.post(
        f"/v0/orgs/{TEST_ORG_ID}/flows",
        json={"name": "Temporary parent"},
        headers=get_auth_headers(),
    )
    parent_id = r_parent.json()["flow"]["flow_id"]
    await _insert_latest_revision(
        db,
        flow_id=parent_id,
        flow_version=1,
        nodes=[
            _std_node(
                "ft",
                "flows.flow_tool",
                parameters={
                    "target_flow_id": target_id,
                    "tool_name": "t",
                    "tool_description": "d",
                },
            )
        ],
    )
    await _insert_latest_revision(
        db,
        flow_id=parent_id,
        flow_version=2,
        nodes=[_std_node("t1", "flows.trigger.manual")],
    )

    r_del = client.delete(
        f"/v0/orgs/{TEST_ORG_ID}/flows/{target_id}",
        headers=get_auth_headers(),
    )
    assert r_del.status_code == 200, r_del.text
