"""Tests for poll trigger framework (T3)."""

from __future__ import annotations

import asyncio
from unittest.mock import patch

import pytest
from bson import ObjectId

import analytiq_data as ad
from tests.conftest_utils import TEST_ORG_ID, client, get_auth_headers
from tests.flows.poll_trigger_node import TestsPollTriggerNode


@pytest.fixture
def register_poll_node():
    ad.flows.register(TestsPollTriggerNode())
    yield


@pytest.fixture
def flow_nodes_poll_trigger():
    return [
        {
            "id": "poll1",
            "name": "Poll",
            "type": "tests.poll_trigger",
            "parameters": {"items_per_poll": 2},
            "disabled": False,
        },
        {
            "id": "code1",
            "name": "Code",
            "type": "flows.code",
            "parameters": {
                "python_code": "def run(items, context):\n    return items",
                "timeout_seconds": 5,
            },
            "disabled": False,
        },
    ]


@pytest.fixture
def flow_revision(flow_nodes_poll_trigger):
    return {
        "_id": ObjectId(),
        "flow_id": "flow1",
        "nodes": flow_nodes_poll_trigger,
        "connections": {
            "poll1": {"main": [[{"dest_node_id": "code1", "connection_type": "main", "index": 0}]]},
        },
        "settings": {"timezone": "UTC"},
        "pin_data": None,
    }


@pytest.fixture
def aclient():
    return ad.common.get_analytiq_client()


async def _wait_for_flow_executions(db, flow_id: str, *, timeout: float = 2.0) -> list[dict]:
    deadline = asyncio.get_running_loop().time() + timeout
    while asyncio.get_running_loop().time() < deadline:
        execs = await db.flow_executions.find({"flow_id": flow_id}).to_list(10)
        if execs:
            return execs
        await asyncio.sleep(0.02)
    return []


@pytest.mark.asyncio
async def test_poll_empty_tick_does_not_enqueue(test_db, register_poll_node, flow_revision, aclient):
    flow_revision["nodes"][0]["parameters"] = {"items_per_poll": 0}
    scheduler = ad.flows.FlowScheduler()
    registry = ad.flows.ActiveFlowRegistry(
        aclient,
        scheduler,
        leader_check=lambda: True,
        lease_ttl_secs=60,
    )
    db = ad.common.get_async_db(aclient)
    try:
        await registry.register_flow("org1", "flow1", str(flow_revision["_id"]), flow_revision)
        await registry._run_tick(
            registry._triggers["flow1"][0],
            rule_index=0,
            tick_key="2026-05-21T12:00",
            trigger_kind="poll",
        )
        assert await db.flow_executions.count_documents({"flow_id": "flow1"}) == 0
    finally:
        await registry.deregister_flow("flow1")
        await scheduler.shutdown()


@pytest.mark.asyncio
async def test_poll_tick_enqueues_and_persists_static_data(
    test_db, register_poll_node, flow_revision, aclient
):
    scheduler = ad.flows.FlowScheduler()
    registry = ad.flows.ActiveFlowRegistry(
        aclient,
        scheduler,
        leader_check=lambda: True,
        lease_ttl_secs=60,
    )
    db = ad.common.get_async_db(aclient)
    try:
        await registry.register_flow("org1", "flow1", str(flow_revision["_id"]), flow_revision)
        reg = registry._triggers["flow1"][0]
        await registry._run_tick(reg, rule_index=0, tick_key="2026-05-21T12:00", trigger_kind="poll")

        execs = await db.flow_executions.find({"flow_id": "flow1"}).to_list(10)
        assert len(execs) == 1
        assert execs[0]["mode"] == "schedule"
        assert execs[0]["trigger"]["type"] == "poll"
        assert execs[0]["trigger"]["items"][0][0]["json"]["seq"] == 1

        static_doc = await db.flow_static_data.find_one({"flow_id": "flow1", "node_id": "poll1"})
        assert static_doc is not None
        assert static_doc["data"]["cursor"] == 1

        await registry._run_tick(reg, rule_index=0, tick_key="2026-05-21T12:01", trigger_kind="poll")
        execs = await db.flow_executions.find({"flow_id": "flow1"}).to_list(10)
        assert len(execs) == 2
        assert execs[1]["trigger"]["items"][0][0]["json"]["seq"] == 2

        await registry._run_tick(reg, rule_index=0, tick_key="2026-05-21T12:02", trigger_kind="poll")
        assert await db.flow_executions.count_documents({"flow_id": "flow1"}) == 2
    finally:
        await registry.deregister_flow("flow1")
        await scheduler.shutdown()


@pytest.mark.asyncio
async def test_poll_registry_run_immediately_enqueues(test_db, register_poll_node, flow_revision, aclient):
    scheduler = ad.flows.FlowScheduler()
    registry = ad.flows.ActiveFlowRegistry(
        aclient,
        scheduler,
        leader_check=lambda: True,
        lease_ttl_secs=60,
    )
    db = ad.common.get_async_db(aclient)
    try:
        await registry.register_flow(
            "org1",
            "flow1",
            str(flow_revision["_id"]),
            flow_revision,
            run_immediately=True,
        )
        await scheduler.drain_immediate()
        execs = await _wait_for_flow_executions(db, "flow1")
        assert len(execs) == 1
        assert execs[0]["trigger"]["type"] == "poll"
    finally:
        await registry.deregister_flow("flow1")
        await scheduler.shutdown()


@pytest.mark.asyncio
async def test_poll_trigger_execute_replays_trigger_items(register_poll_node):
    nt = ad.flows.get("tests.poll_trigger")
    ctx = ad.flows.ExecutionContext(
        organization_id="org1",
        execution_id="e1",
        flow_id="f1",
        flow_revid="r1",
        mode="schedule",
        trigger_data={
            "type": "poll",
            "items": [[{"json": {"seq": 3}, "binary": {}, "meta": {}, "paired_item": None}]],
        },
        run_data={},
        analytiq_client=None,
    )
    node = {"id": "poll1", "name": "Poll", "type": "tests.poll_trigger", "parameters": {}}
    out = await nt.execute(ctx, node, [[]])
    assert len(out[0]) == 1
    assert out[0][0].json["seq"] == 3


@pytest.mark.asyncio
async def test_run_poll_activation_tests_allows_empty_output(
    test_db, register_poll_node, flow_revision, aclient
):
    flow_revision["nodes"][0]["parameters"] = {"items_per_poll": 0}
    await ad.flows.run_poll_activation_tests(
        aclient,
        organization_id="org1",
        flow_id="flow1",
        flow_revid=str(flow_revision["_id"]),
        revision=flow_revision,
    )


@pytest.mark.asyncio
async def test_run_poll_activation_tests_raises_on_poll_failure(
    test_db, register_poll_node, flow_revision, aclient
):
    flow_revision["nodes"][0]["parameters"] = {"fail_activation": True}
    with pytest.raises(ad.flows.FlowValidationError, match="activation test failed"):
        await ad.flows.run_poll_activation_tests(
            aclient,
            organization_id="org1",
            flow_id="flow1",
            flow_revid=str(flow_revision["_id"]),
            revision=flow_revision,
        )


@pytest.mark.asyncio
async def test_activate_blocks_on_poll_activation_failure(test_db, mock_auth, register_poll_node):
    r0 = client.post(
        f"/v0/orgs/{TEST_ORG_ID}/flows",
        json={"name": "Poll activate block"},
        headers=get_auth_headers(),
    )
    assert r0.status_code == 200, r0.text
    flow_id = r0.json()["flow"]["flow_id"]

    nodes = [
        {
            "id": "poll1",
            "name": "Poll",
            "type": "tests.poll_trigger",
            "position": [0, 0],
            "parameters": {"fail_activation": True, "items_per_poll": 1},
            "webhook_id": None,
            "disabled": False,
            "on_error": "stop",
            "retry_on_fail": False,
            "max_tries": 1,
            "wait_between_tries_ms": 1000,
            "notes": None,
        },
        {
            "id": "c1",
            "name": "Code",
            "type": "flows.code",
            "position": [200, 0],
            "parameters": {"python_code": "def run(items, context):\n    return items", "timeout_seconds": 5},
            "webhook_id": None,
            "disabled": False,
            "on_error": "stop",
            "retry_on_fail": False,
            "max_tries": 1,
            "wait_between_tries_ms": 1000,
            "notes": None,
        },
    ]
    conns = {"poll1": {"main": [[{"dest_node_id": "c1", "connection_type": "main", "index": 0}]]}}
    r1 = client.put(
        f"/v0/orgs/{TEST_ORG_ID}/flows/{flow_id}",
        json={
            "base_flow_revid": "",
            "name": "Poll activate block",
            "nodes": nodes,
            "connections": conns,
            "settings": {},
            "pin_data": None,
        },
        headers=get_auth_headers(),
    )
    assert r1.status_code == 200, r1.text

    monkeypatch_trigger = patch.object(ad.flows, "get_flow_trigger_service", return_value=None)
    with monkeypatch_trigger:
        r_act = client.post(
            f"/v0/orgs/{TEST_ORG_ID}/flows/{flow_id}/activate",
            json={},
            headers=get_auth_headers(),
        )
    assert r_act.status_code == 400, r_act.text
    assert "activation test failed" in r_act.json()["detail"].lower()

    db = ad.common.get_async_db()
    header = await db.flows.find_one({"_id": ObjectId(flow_id)})
    assert header is not None
    assert header.get("active") is not True


@pytest.mark.asyncio
async def test_post_trigger_test_poll_enqueues_run(test_db, mock_auth, register_poll_node):
    r0 = client.post(
        f"/v0/orgs/{TEST_ORG_ID}/flows",
        json={"name": "Poll test trigger"},
        headers=get_auth_headers(),
    )
    assert r0.status_code == 200, r0.text
    flow_id = r0.json()["flow"]["flow_id"]

    nodes = [
        {
            "id": "poll1",
            "name": "Poll",
            "type": "tests.poll_trigger",
            "position": [0, 0],
            "parameters": {"items_per_poll": 1},
            "webhook_id": None,
            "disabled": False,
            "on_error": "stop",
            "retry_on_fail": False,
            "max_tries": 1,
            "wait_between_tries_ms": 1000,
            "notes": None,
        },
        {
            "id": "c1",
            "name": "Code",
            "type": "flows.code",
            "position": [200, 0],
            "parameters": {"python_code": "def run(items, context):\n    return items", "timeout_seconds": 5},
            "webhook_id": None,
            "disabled": False,
            "on_error": "stop",
            "retry_on_fail": False,
            "max_tries": 1,
            "wait_between_tries_ms": 1000,
            "notes": None,
        },
    ]
    conns = {"poll1": {"main": [[{"dest_node_id": "c1", "connection_type": "main", "index": 0}]]}}
    snapshot = {"nodes": nodes, "connections": conns, "settings": {}, "pin_data": None}

    r = client.post(
        f"/v0/orgs/{TEST_ORG_ID}/flows/{flow_id}/trigger-test/poll",
        json={"revision_snapshot": snapshot, "trigger_node_id": "poll1"},
        headers=get_auth_headers(),
    )
    assert r.status_code == 200, r.text
    exec_id = r.json()["execution_id"]

    db = ad.common.get_async_db()
    exec_doc = await db.flow_executions.find_one({"_id": ObjectId(exec_id)})
    assert exec_doc is not None
    assert exec_doc["trigger"]["type"] == "poll"
    assert exec_doc["trigger"].get("test") is True

    qdocs = await db["queues.flow_run"].find({}).to_list(10)
    assert len(qdocs) == 1
    assert qdocs[0]["msg"]["execution_id"] == exec_id


@pytest.mark.asyncio
async def test_registry_persists_poll_trigger_registrations(
    test_db, register_poll_node, flow_revision, aclient
):
    scheduler = ad.flows.FlowScheduler()
    registry = ad.flows.ActiveFlowRegistry(
        aclient,
        scheduler,
        leader_check=lambda: True,
    )
    db = ad.common.get_async_db(aclient)
    try:
        await registry.register_flow("org1", "flow1", str(flow_revision["_id"]), flow_revision)
        regs = await db.flow_trigger_registrations.find({"flow_id": "flow1"}).to_list(10)
        assert len(regs) == 1
        assert regs[0]["node_id"] == "poll1"
        assert regs[0]["trigger_kind"] == "poll"
    finally:
        await registry.deregister_flow("flow1")
        await scheduler.shutdown()
