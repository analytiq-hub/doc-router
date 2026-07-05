"""HTTP tests for org-wide execution list (summary payloads)."""

from __future__ import annotations

from datetime import datetime, UTC

import pytest
import pytest_asyncio
from bson import ObjectId

import analytiq_data as ad

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


@pytest_asyncio.fixture
async def flow_with_heavy_execution(mock_auth, test_db):
    r0 = client.post(
        f"/v0/orgs/{TEST_ORG_ID}/flows",
        json={"name": "execution list summary test"},
        headers=get_auth_headers(),
    )
    assert r0.status_code == 200, r0.text
    flow_id = r0.json()["flow"]["flow_id"]
    r1 = client.put(
        f"/v0/orgs/{TEST_ORG_ID}/flows/{flow_id}",
        json={
            "base_flow_revid": "",
            "name": "execution list summary test",
            "nodes": [_std_manual_node()],
            "connections": {},
            "settings": {},
            "pin_data": None,
        },
        headers=get_auth_headers(),
    )
    assert r1.status_code == 200, r1.text
    rev_id = r1.json()["revision"]["flow_revid"]

    exec_oid = ObjectId()
    exec_id = str(exec_oid)
    db = ad.common.get_async_db()
    await db.flow_executions.insert_one(
        {
            "_id": exec_oid,
            "flow_id": flow_id,
            "flow_revid": rev_id,
            "organization_id": TEST_ORG_ID,
            "mode": "manual",
            "status": "success",
            "started_at": datetime.now(UTC),
            "finished_at": datetime.now(UTC),
            "run_data": {
                "n1": {
                    "status": "success",
                    "data": {"main": [[{"json": {"blob": "x" * 4096}}]]},
                }
            },
            "initial_run_data": {"seed": "y" * 2048},
            "error": {"message": "should not appear in list"},
            "trigger": {"type": "manual"},
            "start_trigger_node_id": "t1",
        }
    )
    return flow_id, exec_id


@pytest.mark.asyncio
async def test_list_executions_returns_summary_without_run_data(flow_with_heavy_execution, mock_auth, test_db):
    flow_id, exec_id = flow_with_heavy_execution

    r = client.get(
        f"/v0/orgs/{TEST_ORG_ID}/executions",
        params={"flow_id": flow_id, "limit": 20, "offset": 0},
        headers=get_auth_headers(),
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["total"] == 1
    assert len(body["items"]) == 1
    item = body["items"][0]
    assert item["execution_id"] == exec_id
    assert item["flow_id"] == flow_id
    assert item["status"] == "success"
    assert item["trigger"] == {"type": "manual"}
    assert "run_data" not in item
    assert "initial_run_data" not in item
    assert "error" not in item
    assert "flow_revid" not in item


@pytest.mark.asyncio
async def test_list_executions_includes_flow_name_when_joined(flow_with_heavy_execution, mock_auth, test_db):
    flow_id, _exec_id = flow_with_heavy_execution

    r = client.get(
        f"/v0/orgs/{TEST_ORG_ID}/executions",
        params={"limit": 50, "offset": 0},
        headers=get_auth_headers(),
    )
    assert r.status_code == 200, r.text
    row = next((x for x in r.json()["items"] if x["flow_id"] == flow_id), None)
    assert row is not None
    assert row["flow_name"] == "execution list summary test"
