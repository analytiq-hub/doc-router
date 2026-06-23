"""Tests for stale flow execution recovery after worker death."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from bson import ObjectId

import analytiq_data as ad
from analytiq_data.flows import recovery as recovery_mod

from tests.conftest_utils import TEST_ORG_ID


@pytest.fixture(autouse=True)
def fast_stale_threshold(monkeypatch):
    monkeypatch.setenv("FLOW_EXECUTION_STALE_SECS", "30")
    monkeypatch.setattr(recovery_mod, "FLOW_EXECUTION_STALE_SECS", 30)


@pytest.mark.asyncio
async def test_recover_stale_flow_execution_stop_requested(test_db):
    client = ad.common.get_analytiq_client()
    db = ad.common.get_async_db()
    exec_oid = ObjectId()
    stale_hb = datetime.now(UTC) - timedelta(minutes=5)

    await db.flow_executions.insert_one(
        {
            "_id": exec_oid,
            "flow_id": str(ObjectId()),
            "flow_revid": str(ObjectId()),
            "organization_id": TEST_ORG_ID,
            "mode": "event",
            "status": "running",
            "started_at": stale_hb,
            "finished_at": None,
            "last_heartbeat_at": stale_hb,
            "stop_requested": True,
            "run_data": {},
            "trigger": {},
        }
    )

    recovered = await ad.flows.recover_stale_flow_executions(client)
    assert recovered == 1

    doc = await db.flow_executions.find_one({"_id": exec_oid})
    assert doc is not None
    assert doc["status"] == "stopped"
    assert doc["finished_at"] is not None


@pytest.mark.asyncio
async def test_recover_stale_flow_execution_without_stop_is_interrupted(test_db):
    client = ad.common.get_analytiq_client()
    db = ad.common.get_async_db()
    exec_oid = ObjectId()
    stale_hb = datetime.now(UTC) - timedelta(minutes=5)

    await db.flow_executions.insert_one(
        {
            "_id": exec_oid,
            "flow_id": str(ObjectId()),
            "flow_revid": str(ObjectId()),
            "organization_id": TEST_ORG_ID,
            "mode": "manual",
            "status": "running",
            "started_at": stale_hb,
            "finished_at": None,
            "last_heartbeat_at": stale_hb,
            "stop_requested": False,
            "run_data": {},
            "trigger": {},
        }
    )

    recovered = await ad.flows.recover_stale_flow_executions(client)
    assert recovered == 1

    doc = await db.flow_executions.find_one({"_id": exec_oid})
    assert doc is not None
    assert doc["status"] == "interrupted"
    assert doc["error"]["message"]


@pytest.mark.asyncio
async def test_recover_skips_fresh_running_execution(test_db):
    client = ad.common.get_analytiq_client()
    db = ad.common.get_async_db()
    exec_oid = ObjectId()
    fresh_hb = datetime.now(UTC)

    await db.flow_executions.insert_one(
        {
            "_id": exec_oid,
            "flow_id": str(ObjectId()),
            "flow_revid": str(ObjectId()),
            "organization_id": TEST_ORG_ID,
            "mode": "manual",
            "status": "running",
            "started_at": fresh_hb,
            "finished_at": None,
            "last_heartbeat_at": fresh_hb,
            "stop_requested": False,
            "run_data": {},
            "trigger": {},
        }
    )

    recovered = await ad.flows.recover_stale_flow_executions(client)
    assert recovered == 0

    doc = await db.flow_executions.find_one({"_id": exec_oid})
    assert doc is not None
    assert doc["status"] == "running"
    assert doc["finished_at"] is None


@pytest.mark.asyncio
async def test_startup_orphan_scratch_retry_when_resume_enabled(test_db) -> None:
    client = ad.common.get_analytiq_client()
    db = ad.common.get_async_db()
    exec_oid = ObjectId()
    fresh_hb = datetime.now(UTC)

    await db.flow_executions.insert_one(
        {
            "_id": exec_oid,
            "flow_id": str(ObjectId()),
            "flow_revid": str(ObjectId()),
            "organization_id": TEST_ORG_ID,
            "mode": "event",
            "status": "running",
            "started_at": fresh_hb,
            "finished_at": None,
            "last_heartbeat_at": fresh_hb,
            "stop_requested": False,
            "run_data": {},
            "completed_nodes": [],
            "revision_snapshot": {
                "nodes": [],
                "connections": {},
                "settings": {"resume_on_restart": True},
                "pin_data": None,
            },
            "trigger": {"type": "manual"},
        }
    )

    recovered = await ad.flows.recover_orphaned_running_flow_executions_at_startup(client)
    assert recovered == 1

    doc = await db.flow_executions.find_one({"_id": exec_oid})
    assert doc is not None
    assert doc["status"] == "queued"
    assert doc.get("finished_at") is None
    assert doc["run_data"] == {}
    assert doc.get("resumed_by") is None


@pytest.mark.asyncio
async def test_startup_orphan_finalizes_when_resume_disabled(test_db) -> None:
    client = ad.common.get_analytiq_client()
    db = ad.common.get_async_db()
    exec_oid = ObjectId()
    fresh_hb = datetime.now(UTC)

    await db.flow_executions.insert_one(
        {
            "_id": exec_oid,
            "flow_id": str(ObjectId()),
            "flow_revid": str(ObjectId()),
            "organization_id": TEST_ORG_ID,
            "mode": "manual",
            "status": "running",
            "started_at": fresh_hb,
            "finished_at": None,
            "last_heartbeat_at": fresh_hb,
            "stop_requested": False,
            "run_data": {"t1": {"status": "success", "data": {"main": [[]]}}},
            "completed_nodes": ["t1"],
            "revision_snapshot": {"nodes": [], "connections": {}, "settings": {}, "pin_data": None},
            "trigger": {},
        }
    )

    recovered = await ad.flows.recover_orphaned_running_flow_executions_at_startup(client)
    assert recovered == 1

    doc = await db.flow_executions.find_one({"_id": exec_oid})
    assert doc is not None
    assert doc["status"] == "interrupted"
    assert doc.get("resumed_by") is None


@pytest.mark.asyncio
async def test_startup_orphan_checkpoint_auto_resume_when_resume_enabled(test_db, monkeypatch) -> None:
    client = ad.common.get_analytiq_client()
    db = ad.common.get_async_db()
    exec_oid = ObjectId()
    fresh_hb = datetime.now(UTC)

    await db.flow_executions.insert_one(
        {
            "_id": exec_oid,
            "flow_id": str(ObjectId()),
            "flow_revid": str(ObjectId()),
            "organization_id": TEST_ORG_ID,
            "mode": "manual",
            "status": "running",
            "started_at": fresh_hb,
            "finished_at": None,
            "last_heartbeat_at": fresh_hb,
            "stop_requested": False,
            "run_data": {"t1": {"status": "success", "data": {"main": [[]]}}},
            "completed_nodes": ["t1"],
            "revision_snapshot": {
                "nodes": [],
                "connections": {},
                "settings": {"resume_on_restart": True},
                "pin_data": None,
            },
            "trigger": {},
        }
    )

    sent: list[dict] = []

    async def _capture_send(_client, queue_name, msg=None, **_kwargs):
        sent.append({"queue": queue_name, "msg": msg})

    monkeypatch.setattr(ad.queue, "send_msg", _capture_send)

    recovered = await ad.flows.recover_orphaned_running_flow_executions_at_startup(client)
    assert recovered == 1

    source = await db.flow_executions.find_one({"_id": exec_oid})
    assert source is not None
    assert source["status"] == "interrupted"
    assert source.get("resumed_by")

    child = await db.flow_executions.find_one({"_id": ObjectId(source["resumed_by"])})
    assert child is not None
    assert child["status"] == "queued"
    assert child["resumed_from"] == str(exec_oid)
    assert child["completed_nodes"] == ["t1"]
    assert len(sent) == 1
    assert sent[0]["queue"] == "flow_run"
    assert sent[0]["msg"]["execution_id"] == source["resumed_by"]
