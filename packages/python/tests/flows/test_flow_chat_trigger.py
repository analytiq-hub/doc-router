"""HTTP tests for Chat Trigger routes (/chat, /chat/test)."""

from __future__ import annotations

import asyncio
import json
from unittest.mock import AsyncMock, patch

import pytest
from bson import ObjectId

import analytiq_data as ad
from tests.conftest_utils import TEST_ORG_ID, client, get_auth_headers

_ECHO_CODE = (
    "def run(items, context):\n"
    "    out = []\n"
    "    for it in items:\n"
    "        d = dict(it.get('json') or {})\n"
    "        d['agent_output'] = d.get('chatInput', '')\n"
    "        out.append({'json': d})\n"
    "    return out\n"
)


def _std_node(id_: str, ntype: str, x: int = 0, parameters: dict | None = None) -> dict:
    return {
        "id": id_,
        "name": id_,
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


def _chat_snapshot(*, response_mode: str = "last_node") -> dict:
    nodes = [
        _std_node(
            "chat-1",
            "flows.trigger.chat",
            0,
            {"response_mode": response_mode},
        ),
        _std_node(
            "code-1",
            "flows.code",
            200,
            {"python_code": _ECHO_CODE, "timeout_seconds": 5},
        ),
    ]
    connections = {
        "chat-1": {"main": [[{"dest_node_id": "code-1", "connection_type": "main", "index": 0}]]},
    }
    return {
        "nodes": nodes,
        "connections": connections,
        "settings": {},
        "pin_data": None,
    }


@pytest.fixture(autouse=True)
def _register_nodes() -> None:
    ad.flows.register_builtin_nodes()
    ad.flows.register_docrouter_nodes()


@pytest.mark.asyncio
async def test_chat_test_buffered_returns_text(test_db, mock_auth) -> None:
    r_flow = client.post(
        f"/v0/orgs/{TEST_ORG_ID}/flows",
        json={"name": "Chat test flow"},
        headers=get_auth_headers(),
    )
    assert r_flow.status_code == 200, r_flow.text
    flow_id = r_flow.json()["flow"]["flow_id"]

    r = client.post(
        f"/v0/orgs/{TEST_ORG_ID}/flows/{flow_id}/chat/test",
        json={
            "chatInput": "Hello from test panel",
            "revision_snapshot": _chat_snapshot(response_mode="last_node"),
        },
        headers=get_auth_headers(),
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["text"] == "Hello from test panel"
    assert body["execution_id"]
    assert body["session_id"]

    db = ad.common.get_async_db()
    exec_doc = await db.flow_executions.find_one({"_id": ObjectId(body["execution_id"])})
    assert exec_doc is not None
    assert exec_doc["status"] == "success"
    assert exec_doc["mode"] == "chat"


@pytest.mark.asyncio
async def test_buffered_chat_timeout_finalizes_execution(test_db, mock_auth) -> None:
    r_flow = client.post(
        f"/v0/orgs/{TEST_ORG_ID}/flows",
        json={"name": "Chat timeout flow"},
        headers=get_auth_headers(),
    )
    flow_id = r_flow.json()["flow"]["flow_id"]

    with patch("app.routes.flow_chat.asyncio.wait_for", new_callable=AsyncMock, side_effect=asyncio.TimeoutError):
        r = client.post(
            f"/v0/orgs/{TEST_ORG_ID}/flows/{flow_id}/chat/test",
            json={
                "chatInput": "Slow reply",
                "revision_snapshot": _chat_snapshot(response_mode="last_node"),
            },
            headers=get_auth_headers(),
        )

    assert r.status_code == 504, r.text
    body = r.json()
    assert "timed out" in body["detail"].lower()

    db = ad.common.get_async_db()
    exec_docs = await db.flow_executions.find({"flow_id": flow_id}).to_list(None)
    assert len(exec_docs) == 1
    assert exec_docs[0]["status"] == "error"
    assert exec_docs[0]["finished_at"] is not None
    assert exec_docs[0]["error"]["message"] == "Chat flow execution timed out"


@pytest.mark.asyncio
async def test_chat_test_streaming_returns_ndjson_meta(test_db, mock_auth) -> None:
    r_flow = client.post(
        f"/v0/orgs/{TEST_ORG_ID}/flows",
        json={"name": "Chat stream flow"},
        headers=get_auth_headers(),
    )
    flow_id = r_flow.json()["flow"]["flow_id"]

    r = client.post(
        f"/v0/orgs/{TEST_ORG_ID}/flows/{flow_id}/chat/test",
        json={
            "chatInput": "Stream please",
            "revision_snapshot": _chat_snapshot(response_mode="streaming"),
        },
        headers=get_auth_headers(),
    )
    assert r.status_code == 200, r.text
    assert "application/x-ndjson" in (r.headers.get("content-type") or "")

    lines = [ln for ln in r.text.strip().split("\n") if ln.strip()]
    assert lines
    meta = json.loads(lines[0])
    assert meta["type"] == "meta"
    assert meta["execution_id"]
    assert meta["session_id"]

    db = ad.common.get_async_db()
    exec_doc = await db.flow_executions.find_one({"_id": ObjectId(meta["execution_id"])})
    assert exec_doc is not None
    assert exec_doc["status"] == "success"


@pytest.mark.asyncio
async def test_chat_active_flow_required(test_db, mock_auth) -> None:
    r_flow = client.post(
        f"/v0/orgs/{TEST_ORG_ID}/flows",
        json={"name": "Inactive chat"},
        headers=get_auth_headers(),
    )
    flow_id = r_flow.json()["flow"]["flow_id"]

    r = client.post(
        f"/v0/orgs/{TEST_ORG_ID}/flows/{flow_id}/chat",
        json={"chatInput": "Should fail"},
        headers=get_auth_headers(),
    )
    assert r.status_code == 409, r.text
    assert "not active" in r.json()["detail"].lower()


@pytest.mark.asyncio
async def test_chat_active_flow_buffered(test_db, mock_auth) -> None:
    r_flow = client.post(
        f"/v0/orgs/{TEST_ORG_ID}/flows",
        json={"name": "Active chat"},
        headers=get_auth_headers(),
    )
    flow_id = r_flow.json()["flow"]["flow_id"]

    r_rev = client.put(
        f"/v0/orgs/{TEST_ORG_ID}/flows/{flow_id}",
        json={
            "base_flow_revid": "",
            "name": "Active chat",
            **_chat_snapshot(response_mode="last_node"),
        },
        headers=get_auth_headers(),
    )
    assert r_rev.status_code == 200, r_rev.text

    r_act = client.post(
        f"/v0/orgs/{TEST_ORG_ID}/flows/{flow_id}/activate",
        json={},
        headers=get_auth_headers(),
    )
    assert r_act.status_code == 200, r_act.text

    r = client.post(
        f"/v0/orgs/{TEST_ORG_ID}/flows/{flow_id}/chat",
        json={"chatInput": "Live chat message"},
        headers=get_auth_headers(),
    )
    assert r.status_code == 200, r.text
    assert r.json()["text"] == "Live chat message"


@pytest.mark.asyncio
async def test_chat_test_rejects_missing_chat_trigger(test_db, mock_auth) -> None:
    r_flow = client.post(
        f"/v0/orgs/{TEST_ORG_ID}/flows",
        json={"name": "No chat trigger"},
        headers=get_auth_headers(),
    )
    flow_id = r_flow.json()["flow"]["flow_id"]

    r = client.post(
        f"/v0/orgs/{TEST_ORG_ID}/flows/{flow_id}/chat/test",
        json={
            "chatInput": "Hi",
            "revision_snapshot": {
                "nodes": [_std_node("t1", "flows.trigger.manual")],
                "connections": {},
                "settings": {},
                "pin_data": None,
            },
        },
        headers=get_auth_headers(),
    )
    assert r.status_code == 400, r.text
    assert "no chat trigger" in r.json()["detail"].lower()
