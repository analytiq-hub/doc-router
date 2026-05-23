"""Tests for flow trigger scheduler (leader, registry, enqueue)."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, UTC
from unittest.mock import AsyncMock, patch

import pytest
from bson import ObjectId

import analytiq_data as ad


@pytest.fixture
def flow_nodes_schedule_trigger():
    return [
        {
            "id": "trig1",
            "name": "Schedule",
            "type": "flows.trigger.schedule",
            "parameters": {
                "rule": {"interval": [{"field": "minutes", "minutesInterval": 5}]},
            },
            "disabled": False,
        },
        {
            "id": "code1",
            "name": "Code",
            "type": "flows.code",
            "parameters": {"language": "python", "code": "def run(items, context):\n    return items"},
            "disabled": False,
        },
    ]


@pytest.fixture
def flow_revision(flow_nodes_schedule_trigger):
    return {
        "_id": ObjectId(),
        "flow_id": "flow1",
        "nodes": flow_nodes_schedule_trigger,
        "connections": {
            "trig1": {"main": [[{"dest_node_id": "code1", "connection_type": "main", "index": 0}]]},
        },
        "settings": {"timezone": "UTC"},
        "pin_data": None,
    }


@pytest.fixture
def register_nodes():
    ad.flows.register_builtin_nodes()


@pytest.fixture
def aclient():
    return ad.common.get_analytiq_client()


@pytest.mark.asyncio
async def test_leader_election_single_holder(test_db, register_nodes, aclient):
    db = ad.common.get_async_db(aclient)
    leader = ad.flows.FlowSchedulerLeader(db, holder_id="host-a", ttl_secs=10)
    assert await leader.renew() is True
    assert leader.is_leader is True

    follower = ad.flows.FlowSchedulerLeader(db, holder_id="host-b", ttl_secs=10)
    assert await follower.renew() is False
    assert follower.is_leader is False


@pytest.mark.asyncio
async def test_leader_takeover_after_expiry(test_db, register_nodes, aclient):
    db = ad.common.get_async_db(aclient)
    leader_a = ad.flows.FlowSchedulerLeader(db, holder_id="host-a", ttl_secs=1)
    assert await leader_a.renew() is True

    await db.flow_scheduler_leader.update_one(
        {"_id": "leader"},
        {"$set": {"expires_at": datetime.now(UTC) - timedelta(seconds=1)}},
    )

    leader_b = ad.flows.FlowSchedulerLeader(db, holder_id="host-b", ttl_secs=10)
    assert await leader_b.renew() is True
    assert leader_b.is_leader is True


@pytest.mark.asyncio
async def test_register_interval_run_immediately(test_db, register_nodes):
    scheduler = ad.flows.FlowScheduler()
    calls: list[str] = []
    anchor = datetime.now(UTC)

    async def on_tick() -> None:
        calls.append("tick")

    await scheduler.register_interval("job1", 60.0, on_tick, anchor=anchor, run_immediately=True)
    await asyncio.sleep(0.05)
    assert calls == ["tick"]
    await scheduler.shutdown()


@pytest.mark.asyncio
async def test_register_cron_run_immediately(test_db, register_nodes):
    scheduler = ad.flows.FlowScheduler()
    calls: list[str] = []

    async def on_tick() -> None:
        calls.append("tick")

    await scheduler.register_cron("job1", "* * * * *", on_tick, run_immediately=True)
    await asyncio.sleep(0.05)
    assert calls == ["tick"]
    await scheduler.shutdown()


@pytest.mark.asyncio
async def test_registry_run_immediately_enqueues(test_db, register_nodes, flow_revision, aclient):
    scheduler = ad.flows.FlowScheduler()
    registry = ad.flows.ActiveFlowRegistry(
        aclient,
        scheduler,
        leader_check=lambda: True,
        lease_ttl_secs=60,
    )
    flow_revid = str(flow_revision["_id"])
    await registry.register_flow(
        "org1",
        "flow1",
        flow_revid,
        flow_revision,
        run_immediately=True,
    )
    await asyncio.sleep(0.05)

    db = ad.common.get_async_db(aclient)
    execs = await db.flow_executions.find({"flow_id": "flow1"}).to_list(10)
    assert len(execs) == 1
    assert execs[0]["mode"] == "schedule"

    await registry.deregister_flow("flow1")


@pytest.mark.asyncio
async def test_registry_registers_cron_jobs(test_db, register_nodes, flow_revision, aclient):
    scheduler = ad.flows.FlowScheduler()
    registry = ad.flows.ActiveFlowRegistry(
        aclient,
        scheduler,
        leader_check=lambda: True,
    )
    await registry.register_flow("org1", "flow1", str(flow_revision["_id"]), flow_revision)
    assert scheduler.job_count() == 1
    assert "flow1:trig1:0" in scheduler._interval_jobs
    await registry.deregister_flow("flow1")
    assert scheduler.job_count() == 0


@pytest.mark.asyncio
async def test_registry_tick_enqueues_flow_run(test_db, register_nodes, flow_revision, aclient):
    scheduler = ad.flows.FlowScheduler()
    registry = ad.flows.ActiveFlowRegistry(
        aclient,
        scheduler,
        leader_check=lambda: True,
        lease_ttl_secs=60,
    )
    flow_revid = str(flow_revision["_id"])
    await registry.register_flow("org1", "flow1", flow_revid, flow_revision)

    with patch.object(registry, "_run_tick", new_callable=AsyncMock) as mock_tick:
        job_id = "flow1:trig1:0"
        job = scheduler._interval_jobs[job_id]
        await job.callback()
        mock_tick.assert_awaited_once()

    await registry._run_tick(
        registry._triggers["flow1"][0],
        rule_index=0,
        tick_key="2026-05-21T12:00",
        trigger_kind="schedule",
    )

    db = ad.common.get_async_db(aclient)
    execs = await db.flow_executions.find({"flow_id": "flow1"}).to_list(10)
    assert len(execs) == 1
    assert execs[0]["mode"] == "schedule"
    assert execs[0]["status"] == "queued"
    assert execs[0]["start_trigger_node_id"] == "trig1"
    assert execs[0]["trigger"]["type"] == "schedule"

    qdocs = await db["queues.flow_run"].find({}).to_list(10)
    assert len(qdocs) == 1
    assert qdocs[0]["msg"]["execution_id"] == str(execs[0]["_id"])

    await registry.deregister_flow("flow1")


@pytest.mark.asyncio
async def test_schedule_trigger_execute_replays_trigger_items(register_nodes):
    nt = ad.flows.get("flows.trigger.schedule")
    ctx = ad.flows.ExecutionContext(
        organization_id="org1",
        execution_id="e1",
        flow_id="f1",
        flow_revid="r1",
        mode="schedule",
        trigger_data={
            "type": "schedule",
            "items": [[{"json": {"timestamp": "t0", "rule_index": 2}, "binary": {}, "meta": {}, "paired_item": None}]],
        },
        run_data={},
        analytiq_client=None,
    )
    node = {"id": "trig1", "name": "Schedule", "type": "flows.trigger.schedule", "parameters": {}}
    out = await nt.execute(ctx, node, [[]])
    assert len(out[0]) == 1
    assert out[0][0].json["rule_index"] == 2


@pytest.mark.asyncio
async def test_trigger_service_start_stop(test_db, register_nodes, flow_revision, monkeypatch, aclient):
    monkeypatch.setenv("FLOW_SCHEDULER_LEADER_TTL_SECS", "30")
    db = ad.common.get_async_db(aclient)
    flow_id = str(ObjectId())
    rev_id = str(flow_revision["_id"])
    flow_revision["flow_id"] = flow_id
    await db.flows.insert_one(
        {
            "_id": ObjectId(flow_id),
            "organization_id": "org1",
            "name": "Scheduled flow",
            "active": True,
            "active_flow_revid": rev_id,
        }
    )
    await db.flow_revisions.insert_one({**flow_revision, "_id": ObjectId(rev_id), "flow_id": flow_id})

    svc = ad.flows.FlowTriggerService(aclient, holder_id="test-host")
    await svc.start()
    assert svc.leader.is_leader is True
    assert svc.registry._triggers.get(flow_id)
    await svc.stop()
