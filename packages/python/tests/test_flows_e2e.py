"""
End-to-end / integration tests for flow HTTP + `flow_run` queue (Phase 2 in `docs/flows.md`).

Uses TestClient, real test Mongo, and a direct `process_flow_run_msg` call (the same as
`worker_flow_run` uses). The in-app `flow_run` worker is prevented from taking messages in this
module (see fixture) because it would otherwise read a different `ENV`/database than
per-test `test_db` fixtures.
"""

from __future__ import annotations

import pytest
from bson import ObjectId

import analytiq_data as ad
import analytiq_data.queue.queue as queue_mod
from analytiq_data.msg_handlers import process_flow_run_msg
from tests.conftest_utils import TEST_ORG_ID, client, get_auth_headers


def _std_node(
    id_: str,
    name: str,
    ntype: str,
    x: int,
    parameters: dict | None = None,
) -> dict:
    return {
        "id": id_,
        "name": name,
        "type": ntype,
        "position": [x, 0],
        "parameters": parameters or {},
        "webhook_id": None,
        "disabled": False,
        "on_error": "stop",
        "retry_on_fail": False,
        "max_tries": 1,
        "wait_between_tries_ms": 1000,
        "notes": None,
    }


@pytest.fixture(autouse=True)
def _stop_flow_run_worker_consuming_stale_env_db():
    """
    `worker_flow_run` uses `analytiq_client` for whatever `ENV` was at app startup, while
    `test_db` switches `os.environ['ENV']` per test. Block the background worker from taking
    `flow_run` messages so this file can run `process_flow_run_msg` with a client for the
    current test database.
    """

    _orig = queue_mod.recv_msg

    async def _recv_shim(aclient, qname: str):
        if qname == "flow_run":
            return None
        return await _orig(aclient, qname)

    queue_mod.recv_msg = _recv_shim
    yield
    queue_mod.recv_msg = _orig


_CODE_SNIPPET = (
    "def run(items, context):\n"
    "    out = []\n"
    "    for it in items:\n"
    "        d = dict(it)\n"
    "        d['e2e'] = context.get('trigger', {}).get('type')\n"
    "        out.append(d)\n"
    "    return out\n"
)


@pytest.mark.asyncio
async def test_post_run_enqueues_queued_flow_run_message(test_db, mock_auth):
    """POST /run creates a queued execution and a `queues.flow_run` message."""

    r0 = client.post(
        f"/v0/orgs/{TEST_ORG_ID}/flows",
        json={"name": "E2E flow"},
        headers=get_auth_headers(),
    )
    assert r0.status_code == 200, r0.text
    flow_id = r0.json()["flow"]["flow_id"]

    nodes = [
        _std_node("t1", "Start", "flows.trigger.manual", 0),
        _std_node(
            "c1",
            "Code",
            "flows.code",
            200,
            {"python_code": _CODE_SNIPPET, "timeout_seconds": 5},
        ),
    ]
    conns = {
        "t1": {
            "main": [
                [{"dest_node_id": "c1", "connection_type": "main", "index": 0}],
            ],
        }
    }
    r1 = client.put(
        f"/v0/orgs/{TEST_ORG_ID}/flows/{flow_id}",
        json={
            "base_flow_revid": "",
            "name": "E2E flow",
            "nodes": nodes,
            "connections": conns,
            "settings": {},
            "pin_data": None,
        },
        headers=get_auth_headers(),
    )
    assert r1.status_code == 200, r1.text

    r2 = client.post(
        f"/v0/orgs/{TEST_ORG_ID}/flows/{flow_id}/run",
        json={},
        headers=get_auth_headers(),
    )
    assert r2.status_code == 200, r2.text
    exec_id = r2.json()["execution_id"]

    db = ad.common.get_async_db()
    exec_doc = await db.flow_executions.find_one({"_id": ObjectId(exec_id)})
    assert exec_doc is not None
    assert exec_doc["status"] == "queued"

    qdocs = await db["queues.flow_run"].find({}).to_list(100)
    assert len(qdocs) == 1
    assert qdocs[0]["msg"]["execution_id"] == exec_id
    assert qdocs[0]["msg"]["flow_id"] == flow_id


@pytest.mark.asyncio
async def test_process_flow_run_msg_completes_http_triggered_run(test_db, mock_auth):
    """
    `POST /run` + queue message + `process_flow_run_msg` (same as `worker_flow_run`).

    The background consumer is disabled for `flow_run` in this file (see
    `_stop_flow_run_worker_consuming_stale_env_db`) so the handler uses a client that matches
    the per-test `ENV` and Mongo database.
    """
    r0 = client.post(
        f"/v0/orgs/{TEST_ORG_ID}/flows",
        json={"name": "E2E flow run"},
        headers=get_auth_headers(),
    )
    assert r0.status_code == 200
    flow_id = r0.json()["flow"]["flow_id"]

    nodes = [
        _std_node("t1", "Start", "flows.trigger.manual", 0),
        _std_node(
            "c1",
            "Code",
            "flows.code",
            200,
            {"python_code": _CODE_SNIPPET, "timeout_seconds": 5},
        ),
    ]
    conns = {
        "t1": {
            "main": [
                [{"dest_node_id": "c1", "connection_type": "main", "index": 0}],
            ],
        }
    }
    r1 = client.put(
        f"/v0/orgs/{TEST_ORG_ID}/flows/{flow_id}",
        json={
            "base_flow_revid": "",
            "name": "E2E flow run",
            "nodes": nodes,
            "connections": conns,
            "settings": {},
            "pin_data": None,
        },
        headers=get_auth_headers(),
    )
    assert r1.status_code == 200, r1.text
    flow_revid = r1.json()["revision"]["flow_revid"]

    r2 = client.post(
        f"/v0/orgs/{TEST_ORG_ID}/flows/{flow_id}/run",
        json={},
        headers=get_auth_headers(),
    )
    assert r2.status_code == 200
    exec_id = r2.json()["execution_id"]

    db = ad.common.get_async_db()
    q0 = await db["queues.flow_run"].find_one({})
    assert q0 is not None
    assert q0["msg"]["flow_revid"] == flow_revid

    aclient = ad.common.get_analytiq_client()
    await process_flow_run_msg(aclient, q0)

    assert await db["queues.flow_run"].count_documents({}) == 0

    last = await db.flow_executions.find_one({"_id": ObjectId(exec_id)})
    assert last is not None, "execution not found"
    assert last.get("status") == "success", f"status={last.get('status')!r} err={last.get('error')!r}"
    run_data = last.get("run_data") or {}
    c1 = run_data.get("c1")
    assert c1 and c1.get("status") == "success"
    first_item = c1["data"]["main"][0][0]
    assert first_item["json"].get("e2e") == "manual"
    assert "json" in first_item

    r3 = client.get(
        f"/v0/orgs/{TEST_ORG_ID}/flows/{flow_id}/executions/{exec_id}",
        headers=get_auth_headers(),
    )
    assert r3.status_code == 200
    ex = r3.json()
    assert ex["status"] == "success"
    assert ex["run_data"]["c1"]["data"]["main"][0][0]["json"]["e2e"] == "manual"
