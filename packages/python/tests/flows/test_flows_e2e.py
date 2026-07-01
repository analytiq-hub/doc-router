"""
End-to-end / integration tests for flow HTTP + `flow_run` queue (Phase 2 in `docs/flows.md`).

Uses TestClient, real test Mongo, and a direct `process_flow_run_msg` call (the same as
`worker_flow_run` uses). The completion test chains a test seed node (JSON array + binaries) →
**`flows.code`** → **`flows.http_request`** (POST JSON via `json_keypair` + expressions); outbound HTTP is
**mocked** (`httpx.AsyncClient` in the HTTP Request node) so the run stays offline while we
assert the POST JSON matches echo fields. The in-app `flow_run` worker is
prevented from taking messages in this module (see fixture) because it would otherwise read a
different `ENV`/database than per-test `test_db` fixtures.
"""

from __future__ import annotations

import json
from unittest.mock import patch

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
    "        d = dict(it.get('json') or {})\n"
    "        d['e2e'] = context.get('trigger', {}).get('type')\n"
    "        d['org_id_echo'] = context.get('organization_id')\n"
    "        d['execution_id_echo'] = context.get('execution_id')\n"
    "        d['flow_id_echo'] = context.get('flow_id')\n"
    "        d['flow_revid_echo'] = context.get('flow_revid')\n"
    "        d['mode_echo'] = context.get('mode')\n"
    "        row = {'json': d}\n"
    "        if it.get('binary'):\n"
    "            row['binary'] = dict(it['binary'])\n"
    "        out.append(row)\n"
    "    return out\n"
)


class _E2eContextSeedNode:
    """Test-only node: JSON array field + two named binaries for webhook `json_with_binary`."""

    key = "tests.e2e_context_seed"
    label = "E2E context seed"
    description = "Adds context_ids array and binary attachments for e2e."
    category = "Test"
    is_trigger = False
    is_merge = False
    min_inputs = 1
    max_inputs = 1
    outputs = 1
    output_labels = ["output"]
    icon_key = None
    parameter_schema: dict = {"type": "object", "properties": {}, "additionalProperties": False}

    def validate_parameters(self, params: dict) -> list[str]:
        return []

    async def execute(self, context, node, inputs):
        out: list[ad.flows.FlowItem] = []
        for it in inputs[0]:
            j = {**it.json, "context_ids": ["a", "b", "c"]}
            binary = {
                "alpha": ad.flows.BinaryRef(
                    mime_type="application/octet-stream",
                    file_name="alpha.bin",
                    data=b"hello-alpha",
                ),
                "beta": ad.flows.BinaryRef(
                    mime_type="text/plain",
                    file_name="beta.txt",
                    data=b"beta-bytes",
                ),
            }
            out.append(
                ad.flows.FlowItem(
                    json=j,
                    binary=binary,
                    meta={**it.meta, "source_node_id": node["id"]},
                    paired_item=it.paired_item,
                )
            )
        return [out]


@pytest.fixture(autouse=True)
def _register_e2e_context_seed_node():
    ad.flows.register(_E2eContextSeedNode())
    yield


@pytest.mark.asyncio
async def test_put_flow_unchanged_graph_and_name_does_not_create_revision(test_db, mock_auth):
    """Same graph + same name + latest base_revid → revision None; no extra row in flow_revisions."""

    r0 = client.post(
        f"/v0/orgs/{TEST_ORG_ID}/flows",
        json={"name": "Idempotent save"},
        headers=get_auth_headers(),
    )
    assert r0.status_code == 200, r0.text
    flow_id = r0.json()["flow"]["flow_id"]

    nodes = [_std_node("t1", "Start", "flows.trigger.manual", 0)]
    conns: dict = {}
    r1 = client.put(
        f"/v0/orgs/{TEST_ORG_ID}/flows/{flow_id}",
        json={
            "base_flow_revid": "",
            "name": "Idempotent save",
            "nodes": nodes,
            "connections": conns,
            "settings": {},
            "pin_data": None,
        },
        headers=get_auth_headers(),
    )
    assert r1.status_code == 200, r1.text
    assert r1.json()["revision"] is not None
    rev_id = r1.json()["revision"]["flow_revid"]

    db = ad.common.get_async_db()
    count_before = await db.flow_revisions.count_documents({"flow_id": flow_id})

    r2 = client.put(
        f"/v0/orgs/{TEST_ORG_ID}/flows/{flow_id}",
        json={
            "base_flow_revid": rev_id,
            "name": "Idempotent save",
            "nodes": nodes,
            "connections": conns,
            "settings": {},
            "pin_data": None,
        },
        headers=get_auth_headers(),
    )
    assert r2.status_code == 200, r2.text
    assert r2.json()["revision"] is None
    count_after = await db.flow_revisions.count_documents({"flow_id": flow_id})
    assert count_after == count_before


@pytest.mark.asyncio
async def test_put_flow_position_only_change_does_not_create_revision(test_db, mock_auth):
    """Moving nodes on the canvas must not bump flow_version; layout is patched on the latest revision."""

    r0 = client.post(
        f"/v0/orgs/{TEST_ORG_ID}/flows",
        json={"name": "Layout only"},
        headers=get_auth_headers(),
    )
    assert r0.status_code == 200, r0.text
    flow_id = r0.json()["flow"]["flow_id"]

    nodes = [_std_node("t1", "Start", "flows.trigger.manual", 0)]
    conns: dict = {}
    r1 = client.put(
        f"/v0/orgs/{TEST_ORG_ID}/flows/{flow_id}",
        json={
            "base_flow_revid": "",
            "name": "Layout only",
            "nodes": nodes,
            "connections": conns,
            "settings": {},
            "pin_data": None,
        },
        headers=get_auth_headers(),
    )
    assert r1.status_code == 200, r1.text
    rev_id = r1.json()["revision"]["flow_revid"]
    version_before = r1.json()["revision"]["flow_version"]

    moved_nodes = [_std_node("t1", "Start", "flows.trigger.manual", 320)]
    db = ad.common.get_async_db()
    count_before = await db.flow_revisions.count_documents({"flow_id": flow_id})

    r2 = client.put(
        f"/v0/orgs/{TEST_ORG_ID}/flows/{flow_id}",
        json={
            "base_flow_revid": rev_id,
            "name": "Layout only",
            "nodes": moved_nodes,
            "connections": conns,
            "settings": {},
            "pin_data": None,
        },
        headers=get_auth_headers(),
    )
    assert r2.status_code == 200, r2.text
    assert r2.json()["revision"] is None
    count_after = await db.flow_revisions.count_documents({"flow_id": flow_id})
    assert count_after == count_before

    stored = await db.flow_revisions.find_one({"_id": ObjectId(rev_id)})
    assert stored is not None
    assert stored["flow_version"] == version_before
    assert stored["nodes"][0]["position"] == [320, 0]


@pytest.mark.asyncio
async def test_preview_expression_rejects_oversized_run_data_entry(test_db, mock_auth):
    """Per-entry size cap on preview-expression protects the evaluator from huge blobs."""

    huge = "x" * 600_000
    r = client.post(
        f"/v0/orgs/{TEST_ORG_ID}/flows/preview-expression",
        json={
            "expression": "=_json",
            "run_data": {
                "n1": {
                    "status": "success",
                    "data": {"main": [[{"json": {"h": huge}, "binary": {}}]]},
                }
            },
            "input_items": [{}],
            "preview_item_index": 0,
            "nodes": [],
        },
        headers=get_auth_headers(),
    )
    assert r.status_code == 400
    assert "exceeds maximum size" in r.json()["detail"]


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
async def test_post_run_revision_snapshot_without_saved_revision(test_db, mock_auth):
    """POST /run with `revision_snapshot` works when the flow has no saved revisions yet."""

    r0 = client.post(
        f"/v0/orgs/{TEST_ORG_ID}/flows",
        json={"name": "Snapshot-only run"},
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

    db = ad.common.get_async_db()
    rv_count = await db.flow_revisions.count_documents({"flow_id": flow_id})
    assert rv_count == 0

    r2 = client.post(
        f"/v0/orgs/{TEST_ORG_ID}/flows/{flow_id}/run",
        json={
            "revision_snapshot": {
                "nodes": nodes,
                "connections": conns,
                "settings": {},
                "pin_data": None,
            }
        },
        headers=get_auth_headers(),
    )
    assert r2.status_code == 200, r2.text
    exec_id = r2.json()["execution_id"]

    exec_doc = await db.flow_executions.find_one({"_id": ObjectId(exec_id)})
    assert exec_doc is not None
    assert exec_doc["status"] == "queued"
    assert exec_doc.get("flow_revid") == ""
    snap = exec_doc.get("revision_snapshot")
    assert isinstance(snap, dict)
    assert len(snap.get("nodes") or []) == 2


@pytest.mark.asyncio
async def test_delete_flow_header_removes_flow(test_db, mock_auth):
    """DELETE /flows/{flow_id} deletes the flow header; subsequent GET returns 404."""

    r0 = client.post(
        f"/v0/orgs/{TEST_ORG_ID}/flows",
        json={"name": "E2E flow delete"},
        headers=get_auth_headers(),
    )
    assert r0.status_code == 200, r0.text
    flow_id = r0.json()["flow"]["flow_id"]

    r1 = client.get(
        f"/v0/orgs/{TEST_ORG_ID}/flows/{flow_id}",
        headers=get_auth_headers(),
    )
    assert r1.status_code == 200, r1.text

    r2 = client.delete(
        f"/v0/orgs/{TEST_ORG_ID}/flows/{flow_id}",
        headers=get_auth_headers(),
    )
    assert r2.status_code == 200, r2.text
    assert r2.json().get("ok") is True

    r3 = client.get(
        f"/v0/orgs/{TEST_ORG_ID}/flows/{flow_id}",
        headers=get_auth_headers(),
    )
    assert r3.status_code == 404


class _MockAsyncHttpClient:
    """Patches `httpx.AsyncClient` for `flows.http_request` in the e2e test."""

    last_request: dict | None = None

    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def request(self, method: str, url: str, **kwargs):
        content = kwargs.get("content")
        parsed = None
        if content:
            try:
                parsed = json.loads(content.decode())
            except Exception:
                parsed = None
        _MockAsyncHttpClient.last_request = {
            "method": method,
            "url": url,
            "json": parsed,
            "headers": kwargs.get("headers") or {},
        }
        import httpx

        return httpx.Response(
            201,
            json={"echo": True, "from_server": "e2e-webhook-mock"},
            request=httpx.Request(method, url),
        )


@pytest.mark.asyncio
async def test_process_flow_run_msg_completes_http_triggered_run(test_db, mock_auth):
    """
    `POST /run` + queue message + `process_flow_run_msg` (same as `worker_flow_run`).

    Graph: manual trigger → **`tests.e2e_context_seed`** (JSON array + binary map) →
    `flows.code` (echoes execution context into item JSON; binaries pass through) →
    **`flows.http_request`** so the POST body is JSON from key/value pairs (echo fields from code).

    Outbound HTTP is mocked via `httpx.AsyncClient`; we assert the mock received the expected JSON.

    The background consumer is disabled for `flow_run` in this file (see
    `_stop_flow_run_worker_consuming_stale_env_db`) so the handler uses a client that matches
    the per-test `ENV` and Mongo database.
    """
    _MockAsyncHttpClient.last_request = None

    r0 = client.post(
        f"/v0/orgs/{TEST_ORG_ID}/flows",
        json={"name": "E2E flow run"},
        headers=get_auth_headers(),
    )
    assert r0.status_code == 200
    flow_id = r0.json()["flow"]["flow_id"]

    nodes = [
        _std_node("t1", "Start", "flows.trigger.manual", 0),
        _std_node("s1", "Seed ctx", "tests.e2e_context_seed", 100, {}),
        _std_node(
            "c1",
            "Code",
            "flows.code",
            200,
            {"python_code": _CODE_SNIPPET, "timeout_seconds": 5},
        ),
        _std_node(
            "w1",
            "HTTP Request",
            "flows.http_request",
            400,
            {
                "method": "POST",
                "url": "https://example.invalid/flow-e2e-webhook",
                "headers": [],
                "query_params": [],
                "body_mode": "json_keypair",
                "body_json": "",
                "body_params": [
                    {"name": "e2e", "value": "=_json['e2e']"},
                    {"name": "context_ids", "value": "=_json['context_ids']"},
                    {"name": "org_id_echo", "value": "=_json['org_id_echo']"},
                    {"name": "execution_id_echo", "value": "=_json['execution_id_echo']"},
                    {"name": "flow_id_echo", "value": "=_json['flow_id_echo']"},
                    {"name": "flow_revid_echo", "value": "=_json['flow_revid_echo']"},
                    {"name": "mode_echo", "value": "=_json['mode_echo']"},
                ],
                "body_raw": "",
                "body_content_type": "text/plain",
                "full_response": False,
                "never_error": False,
                "follow_redirects": True,
                "timeout_seconds": 30,
            },
        ),
    ]
    conns = {
        "t1": {
            "main": [
                [{"dest_node_id": "s1", "connection_type": "main", "index": 0}],
            ],
        },
        "s1": {
            "main": [
                [{"dest_node_id": "c1", "connection_type": "main", "index": 0}],
            ],
        },
        "c1": {
            "main": [
                [{"dest_node_id": "w1", "connection_type": "main", "index": 0}],
            ],
        },
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
    with patch(
        "analytiq_data.flows.nodes.http_request.httpx.AsyncClient",
        _MockAsyncHttpClient,
    ):
        await process_flow_run_msg(aclient, q0)

    assert await db["queues.flow_run"].count_documents({}) == 0

    assert _MockAsyncHttpClient.last_request is not None
    assert _MockAsyncHttpClient.last_request["url"] == "https://example.invalid/flow-e2e-webhook"
    assert _MockAsyncHttpClient.last_request["method"] == "POST"
    posted = _MockAsyncHttpClient.last_request["json"]
    assert isinstance(posted, dict)
    assert posted.get("e2e") == "manual"
    assert posted.get("context_ids") == ["a", "b", "c"]
    assert posted.get("org_id_echo") == TEST_ORG_ID
    assert posted.get("execution_id_echo") == exec_id
    assert posted.get("flow_id_echo") == flow_id
    assert posted.get("flow_revid_echo") == flow_revid
    assert posted.get("mode_echo") == "manual"

    last = await db.flow_executions.find_one({"_id": ObjectId(exec_id)})
    assert last is not None, "execution not found"
    assert last.get("status") == "success", f"status={last.get('status')!r} err={last.get('error')!r}"
    run_data = last.get("run_data") or {}
    s1 = run_data.get("s1")
    assert s1 and s1.get("status") == "success"
    seed_item = s1["data"]["main"][0][0]
    assert seed_item["json"].get("context_ids") == ["a", "b", "c"]
    assert set(seed_item.get("binary") or {}) == {"alpha", "beta"}

    c1 = run_data.get("c1")
    assert c1 and c1.get("status") == "success"
    first_item = c1["data"]["main"][0][0]
    assert first_item["json"].get("e2e") == "manual"
    assert first_item["json"].get("context_ids") == ["a", "b", "c"]
    assert set(first_item.get("binary") or {}) == {"alpha", "beta"}
    assert "json" in first_item

    w1 = run_data.get("w1")
    assert w1 and w1.get("status") == "success"
    hook_out = w1["data"]["main"][0][0]
    assert hook_out["json"]["body"]["echo"] is True
    assert hook_out["json"]["body"]["from_server"] == "e2e-webhook-mock"

    r3 = client.get(
        f"/v0/orgs/{TEST_ORG_ID}/flows/{flow_id}/executions/{exec_id}",
        headers=get_auth_headers(),
    )
    assert r3.status_code == 200
    ex = r3.json()
    assert ex["status"] == "success"
    assert ex["run_data"]["c1"]["data"]["main"][0][0]["json"]["e2e"] == "manual"
    assert ex["run_data"]["c1"]["data"]["main"][0][0]["json"]["context_ids"] == ["a", "b", "c"]
    w1_api = ex["run_data"]["w1"]["data"]["main"][0][0]
    assert w1_api["json"]["body"]["from_server"] == "e2e-webhook-mock"


@pytest.mark.asyncio
async def test_schedule_immediate_run_completes(test_db, mock_auth, monkeypatch):
    """
    Saved flow with schedule trigger → register + immediate tick → ``process_flow_run_msg`` → ``success``.

    Flow is created via HTTP; trigger registration uses the in-test registry (TestClient runs on a
    different event loop than ``FlowTriggerService``, so activate is header-only here).
    """
    ad.flows.register_builtin_nodes()
    monkeypatch.setattr(ad.flows, "get_flow_trigger_service", lambda: None)

    r0 = client.post(
        f"/v0/orgs/{TEST_ORG_ID}/flows",
        json={"name": "Schedule E2E"},
        headers=get_auth_headers(),
    )
    assert r0.status_code == 200, r0.text
    flow_id = r0.json()["flow"]["flow_id"]

    nodes = [
        _std_node(
            "trig1",
            "Schedule",
            "flows.trigger.schedule",
            0,
            {"rule": {"interval": [{"field": "minutes", "minutesInterval": 5}]}},
        ),
        _std_node(
            "c1",
            "Code",
            "flows.code",
            200,
            {"python_code": _CODE_SNIPPET, "timeout_seconds": 5},
        ),
    ]
    conns = {
        "trig1": {
            "main": [[{"dest_node_id": "c1", "connection_type": "main", "index": 0}]],
        },
    }
    r1 = client.put(
        f"/v0/orgs/{TEST_ORG_ID}/flows/{flow_id}",
        json={
            "base_flow_revid": "",
            "name": "Schedule E2E",
            "nodes": nodes,
            "connections": conns,
            "settings": {"timezone": "UTC"},
            "pin_data": None,
        },
        headers=get_auth_headers(),
    )
    assert r1.status_code == 200, r1.text
    flow_revid = r1.json()["revision"]["flow_revid"]

    r_act = client.post(
        f"/v0/orgs/{TEST_ORG_ID}/flows/{flow_id}/activate",
        json={},
        headers=get_auth_headers(),
    )
    assert r_act.status_code == 200, r_act.text
    assert r_act.json()["flow"]["active"] is True

    db = ad.common.get_async_db()
    rev = await db.flow_revisions.find_one({"_id": ObjectId(flow_revid), "flow_id": flow_id})
    assert rev is not None

    aclient = ad.common.get_analytiq_client()
    scheduler = ad.flows.FlowScheduler()
    registry = ad.flows.ActiveFlowRegistry(
        aclient,
        scheduler,
        leader_check=lambda: True,
        lease_ttl_secs=60,
    )
    try:
        await registry.register_flow(
            TEST_ORG_ID,
            flow_id,
            flow_revid,
            rev,
            run_immediately=True,
        )
        await scheduler.drain_immediate()

        execs = await db.flow_executions.find({"flow_id": flow_id}).to_list(10)
        assert len(execs) == 1
        exec_id = str(execs[0]["_id"])
        assert execs[0]["mode"] == "schedule"
        assert execs[0]["status"] == "queued"

        regs = await db.flow_trigger_registrations.find({"flow_id": flow_id}).to_list(10)
        assert len(regs) == 1
        assert regs[0]["node_id"] == "trig1"

        q0 = await db["queues.flow_run"].find_one({"msg.execution_id": exec_id})
        assert q0 is not None

        await process_flow_run_msg(aclient, q0)

        last = await db.flow_executions.find_one({"_id": ObjectId(exec_id)})
        assert last is not None
        assert last.get("status") == "success", f"status={last.get('status')!r} err={last.get('error')!r}"
        c1 = (last.get("run_data") or {}).get("c1")
        assert c1 and c1.get("status") == "success"
        assert c1["data"]["main"][0][0]["json"].get("e2e") == "schedule"
        assert c1["data"]["main"][0][0]["json"].get("flow_revid_echo") == flow_revid
    finally:
        await registry.deregister_flow(flow_id)
        await scheduler.shutdown()


@pytest.mark.asyncio
async def test_post_trigger_test_schedule_enqueues_run(test_db, mock_auth):
    """POST trigger-test/schedule enqueues a schedule-mode run from the editor snapshot."""
    r0 = client.post(
        f"/v0/orgs/{TEST_ORG_ID}/flows",
        json={"name": "Schedule test trigger"},
        headers=get_auth_headers(),
    )
    assert r0.status_code == 200, r0.text
    flow_id = r0.json()["flow"]["flow_id"]

    nodes = [
        _std_node(
            "trig1",
            "Schedule",
            "flows.trigger.schedule",
            0,
            {"rule": {"interval": [{"field": "minutes", "minutesInterval": 5}]}},
        ),
        _std_node(
            "c1",
            "Code",
            "flows.code",
            200,
            {"python_code": _CODE_SNIPPET, "timeout_seconds": 5},
        ),
    ]
    conns = {
        "trig1": {
            "main": [[{"dest_node_id": "c1", "connection_type": "main", "index": 0}]],
        },
    }
    snapshot = {
        "nodes": nodes,
        "connections": conns,
        "settings": {"timezone": "UTC"},
        "pin_data": None,
    }

    r = client.post(
        f"/v0/orgs/{TEST_ORG_ID}/flows/{flow_id}/trigger-test/schedule",
        json={"revision_snapshot": snapshot, "trigger_node_id": "trig1"},
        headers=get_auth_headers(),
    )
    assert r.status_code == 200, r.text
    exec_id = r.json()["execution_id"]
    assert exec_id

    db = ad.common.get_async_db()
    exec_doc = await db.flow_executions.find_one({"_id": ObjectId(exec_id)})
    assert exec_doc is not None
    assert exec_doc["mode"] == "schedule"
    assert exec_doc["status"] == "queued"
    assert exec_doc.get("revision_snapshot") is not None
    assert exec_doc["trigger"].get("test") is True

    qdocs = await db["queues.flow_run"].find({}).to_list(10)
    assert len(qdocs) == 1
    assert qdocs[0]["msg"]["execution_id"] == exec_id
