"""
End-to-end / integration tests for flow HTTP + `flow_run` queue (Phase 2 in `docs/flows.md`).

Uses TestClient, real test Mongo, and a direct `process_flow_run_msg` call (the same as
`worker_flow_run` uses). The completion test chains a test seed node (JSON array + binaries) →
**`flows.code`** → **`flows.webhook`** (`body_format: json_with_binary`); outbound HTTP is
**mocked** (`httpx.AsyncClient`) so the run stays offline while we assert POST payload matches
`run_data.request` on the webhook node. The in-app `flow_run` worker is
prevented from taking messages in this module (see fixture) because it would otherwise read a
different `ENV`/database than per-test `test_db` fixtures.
"""

from __future__ import annotations

import base64
from unittest.mock import MagicMock, patch

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
    "        d['org_id_echo'] = context.get('organization_id')\n"
    "        d['execution_id_echo'] = context.get('execution_id')\n"
    "        d['flow_id_echo'] = context.get('flow_id')\n"
    "        d['flow_revid_echo'] = context.get('flow_revid')\n"
    "        d['mode_echo'] = context.get('mode')\n"
    "        out.append(d)\n"
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


class _MockWebhookHttpClient:
    """Async context manager returned as `httpx.AsyncClient` for `flows.webhook` in the e2e test."""

    last_post: dict | None = None

    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def post(self, url: str, json=None, headers=None):
        _MockWebhookHttpClient.last_post = {"url": url, "json": json, "headers": headers or {}}
        resp = MagicMock()
        resp.status_code = 201
        resp.text = '{"echo": true, "from_server": "e2e-webhook-mock"}'
        return resp


@pytest.mark.asyncio
async def test_process_flow_run_msg_completes_http_triggered_run(test_db, mock_auth):
    """
    `POST /run` + queue message + `process_flow_run_msg` (same as `worker_flow_run`).

    Graph: manual trigger → **`tests.e2e_context_seed`** (JSON array + binary map) →
    `flows.code` (echoes execution context into item JSON; binaries pass through) →
    **`flows.webhook`** with `body_format: json_with_binary` so the POST body is
    `{"json": ..., "binary": ...}` matching wire + `run_data.request`.

    Outbound HTTP is mocked via `httpx.AsyncClient`; we assert the mock received the same
    structure as stored on the webhook node.

    The background consumer is disabled for `flow_run` in this file (see
    `_stop_flow_run_worker_consuming_stale_env_db`) so the handler uses a client that matches
    the per-test `ENV` and Mongo database.
    """
    _MockWebhookHttpClient.last_post = None

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
            "Outbound hook",
            "flows.webhook",
            400,
            {
                "url": "https://example.invalid/flow-e2e-webhook",
                "headers": {},
                "body_format": "json_with_binary",
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
    with patch("httpx.AsyncClient", _MockWebhookHttpClient):
        await process_flow_run_msg(aclient, q0)

    assert await db["queues.flow_run"].count_documents({}) == 0

    assert _MockWebhookHttpClient.last_post is not None
    assert _MockWebhookHttpClient.last_post["url"] == "https://example.invalid/flow-e2e-webhook"
    posted = _MockWebhookHttpClient.last_post["json"]
    assert isinstance(posted, dict) and "json" in posted and "binary" in posted
    body_json = posted["json"]
    body_bin = posted["binary"]
    assert body_json.get("e2e") == "manual"
    assert body_json.get("context_ids") == ["a", "b", "c"]
    assert body_json.get("org_id_echo") == TEST_ORG_ID
    assert body_json.get("execution_id_echo") == exec_id
    assert body_json.get("flow_id_echo") == flow_id
    assert body_json.get("flow_revid_echo") == flow_revid
    assert body_json.get("mode_echo") == "manual"
    assert base64.standard_b64decode(body_bin["alpha"]["data_b64"]) == b"hello-alpha"
    assert base64.standard_b64decode(body_bin["beta"]["data_b64"]) == b"beta-bytes"
    assert body_bin["alpha"]["mime_type"] == "application/octet-stream"
    assert body_bin["beta"]["mime_type"] == "text/plain"

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
    assert hook_out["json"]["request"] == posted
    assert hook_out["json"]["response"]["status_code"] == 201
    assert hook_out["json"]["response"]["body"] == '{"echo": true, "from_server": "e2e-webhook-mock"}'

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
    assert w1_api["json"]["request"] == posted
    assert w1_api["json"]["response"]["status_code"] == 201
    assert "e2e-webhook-mock" in w1_api["json"]["response"]["body"]
