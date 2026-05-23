"""
Phase 0 fulltrace tests: failed-run stack over HTTP and worker `last_node_executed`.

See ``docs/docrouter_fulltrace.md`` Phase 0 checklist.
"""

from __future__ import annotations

import pytest
from bson import ObjectId

import analytiq_data as ad
import analytiq_data.queue.queue as queue_mod
from analytiq_data.msg_handlers import process_flow_run_msg
from tests.conftest_utils import TEST_ORG_ID, client, get_auth_headers

FAIL_NODE_ID = "f1"
TRIGGER_NODE_ID = "t1"


def _std_node(id_: str, name: str, ntype: str, x: int) -> dict:
    return {
        "id": id_,
        "name": name,
        "type": ntype,
        "position": [x, 0],
        "parameters": {},
        "webhook_id": None,
        "disabled": False,
        "on_error": "stop",
        "retry_on_fail": False,
        "max_tries": 1,
        "wait_between_tries_ms": 1000,
        "notes": None,
    }


class _Phase0FailNode:
    key = "tests.fail_phase0"
    label = "Fail"
    description = "Test fail node for phase 0 logging."
    category = "Test"
    is_trigger = False
    is_merge = False
    min_inputs = 1
    max_inputs = 1
    outputs = 1
    output_labels = ["main"]
    icon_key = None
    parameter_schema = {"type": "object", "properties": {}, "additionalProperties": False}

    def validate_parameters(self, params):
        return []

    async def execute(self, context, node, inputs):
        raise RuntimeError("phase0 node boom")


@pytest.fixture(autouse=True)
def _stop_background_flow_run_worker():
    """Prevent the app worker from consuming queue messages on a stale test ENV/db."""

    _orig = queue_mod.recv_msg

    async def _recv_shim(aclient, qname: str):
        if qname == "flow_run":
            return None
        return await _orig(aclient, qname)

    queue_mod.recv_msg = _recv_shim
    yield
    queue_mod.recv_msg = _orig


@pytest.fixture
def fail_phase0_node():
    ad.flows.register_builtin_nodes()
    ad.flows.register(_Phase0FailNode())


def _fail_flow_graph() -> tuple[list[dict], dict]:
    nodes = [
        _std_node(TRIGGER_NODE_ID, "Start", "flows.trigger.manual", 0),
        _std_node(FAIL_NODE_ID, "Fail", "tests.fail_phase0", 200),
    ]
    connections = {
        TRIGGER_NODE_ID: {
            "main": [[{"dest_node_id": FAIL_NODE_ID, "connection_type": "main", "index": 0}]],
        },
    }
    return nodes, connections


async def _queue_and_run_fail_flow(test_db, fail_phase0_node) -> tuple[str, str]:
    """Create flow, enqueue run, process via ``process_flow_run_msg``; return ``(flow_id, exec_id)``."""

    r0 = client.post(
        f"/v0/orgs/{TEST_ORG_ID}/flows",
        json={"name": "Phase0 fail flow"},
        headers=get_auth_headers(),
    )
    assert r0.status_code == 200, r0.text
    flow_id = r0.json()["flow"]["flow_id"]

    nodes, connections = _fail_flow_graph()
    r1 = client.put(
        f"/v0/orgs/{TEST_ORG_ID}/flows/{flow_id}",
        json={
            "base_flow_revid": "",
            "name": "Phase0 fail flow",
            "nodes": nodes,
            "connections": connections,
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
    q0 = await db["queues.flow_run"].find_one({})
    assert q0 is not None

    aclient = ad.common.get_analytiq_client()
    await process_flow_run_msg(aclient, q0)

    return flow_id, exec_id


@pytest.mark.asyncio
async def test_flow_run_worker_sets_last_node_executed_on_failure(test_db, mock_auth, fail_phase0_node):
    """Worker path: Mongo execution doc records failing node id and stack in ``run_data``."""

    _flow_id, exec_id = await _queue_and_run_fail_flow(test_db, fail_phase0_node)

    db = ad.common.get_async_db()
    doc = await db.flow_executions.find_one({"_id": ObjectId(exec_id)})
    assert doc is not None
    assert doc.get("status") == "error"
    assert doc.get("last_node_executed") == FAIL_NODE_ID

    run_data = doc.get("run_data") or {}
    fail_entry = run_data.get(FAIL_NODE_ID)
    assert fail_entry is not None
    assert fail_entry.get("status") == "error"
    err = fail_entry.get("error") or {}
    assert err.get("message") == "phase0 node boom"
    assert isinstance(err.get("stack"), str)
    assert "RuntimeError" in err["stack"]

    top = doc.get("error") or {}
    assert top.get("message") == "phase0 node boom"
    assert top.get("node_id") == FAIL_NODE_ID
    assert isinstance(top.get("stack"), str)


@pytest.mark.asyncio
async def test_get_execution_returns_stack_for_failed_run(test_db, mock_auth, fail_phase0_node):
    """``GET .../executions/{id}`` returns node and top-level error stacks for failed runs."""

    flow_id, exec_id = await _queue_and_run_fail_flow(test_db, fail_phase0_node)

    r = client.get(
        f"/v0/orgs/{TEST_ORG_ID}/flows/{flow_id}/executions/{exec_id}",
        headers=get_auth_headers(),
    )
    assert r.status_code == 200, r.text
    ex = r.json()
    assert ex["status"] == "error"
    assert ex["last_node_executed"] == FAIL_NODE_ID

    fail_entry = ex["run_data"][FAIL_NODE_ID]
    assert fail_entry["status"] == "error"
    node_err = fail_entry["error"]
    assert node_err["message"] == "phase0 node boom"
    assert isinstance(node_err["stack"], str)
    assert "RuntimeError" in node_err["stack"]

    top_err = ex["error"]
    assert top_err["message"] == "phase0 node boom"
    assert top_err["node_id"] == FAIL_NODE_ID
    assert isinstance(top_err["stack"], str)
    assert "RuntimeError" in top_err["stack"]
