from __future__ import annotations

"""Checkpoint resume: engine skip, enqueue, API, and auto-resume on recovery."""

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from bson import ObjectId

import analytiq_data as ad
from analytiq_data.flows import recovery as recovery_mod

from tests.conftest_utils import TEST_ORG_ID, client, get_auth_headers


_EXECUTE_COUNTS: dict[str, int] = {}


class _CountingPassThroughNode:
    key = "tests.counting_passthrough"
    label = "Counting passthrough"
    description = "Test-only passthrough that counts executions."
    category = "Test"
    is_trigger = False
    is_merge = False
    min_inputs = 1
    max_inputs = 1
    outputs = 1
    output_labels = ["output"]
    icon_key = None
    parameter_schema: dict[str, Any] = {
        "type": "object",
        "properties": {},
        "additionalProperties": False,
    }

    def validate_parameters(self, params: dict[str, Any]) -> list[str]:
        return []

    async def execute(
        self,
        context: "ad.flows.ExecutionContext",
        node: dict[str, Any],
        inputs: list[list["ad.flows.FlowItem"]],
    ) -> list[list["ad.flows.FlowItem"]]:
        nid = str(node["id"])
        _EXECUTE_COUNTS[nid] = _EXECUTE_COUNTS.get(nid, 0) + 1
        return [inputs[0]]


@pytest.fixture(autouse=True)
def _register_flow_nodes() -> None:
    ad.flows.register_builtin_nodes()
    from tests.flows.test_flows_engine import _PassThroughNode  # noqa: PLC0415

    ad.flows.register(_PassThroughNode())
    ad.flows.register(_CountingPassThroughNode())
    _EXECUTE_COUNTS.clear()


def _conn(dest: str, index: int = 0) -> ad.flows.NodeConnection:
    return ad.flows.NodeConnection(dest_node_id=dest, connection_type="main", index=index)


def _trigger(nid: str = "t1") -> dict[str, Any]:
    return {
        "id": nid,
        "name": "T",
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


def _counting(nid: str, name: str) -> dict[str, Any]:
    return {
        "id": nid,
        "name": name,
        "type": "tests.counting_passthrough",
        "position": [100, 0],
        "parameters": {},
        "webhook_id": None,
        "disabled": False,
        "on_error": "stop",
        "retry_on_fail": False,
        "max_tries": 1,
        "wait_between_tries_ms": 1000,
        "notes": None,
    }


def _ctx(**kwargs: Any) -> ad.flows.ExecutionContext:
    base = dict(
        organization_id="org",
        execution_id="exec",
        flow_id="flow",
        flow_revid="rev",
        mode="manual",
        trigger_data={"x": 1},
        run_data={},
        analytiq_client=None,
        stop_requested=False,
        logger=None,
    )
    base.update(kwargs)
    return ad.flows.ExecutionContext(**base)


async def _insert_stale_running_execution(
    db,
    *,
    exec_oid: ObjectId | None = None,
    stop_requested: bool = False,
    revision_settings: dict[str, Any] | None = None,
    completed_nodes: list[str] | None = None,
) -> ObjectId:
    exec_oid = exec_oid or ObjectId()
    stale_hb = datetime.now(UTC) - timedelta(minutes=5)
    revision_snapshot = {
        "nodes": [_trigger()],
        "connections": {},
        "settings": revision_settings if revision_settings is not None else {"resume_on_restart": True},
        "pin_data": None,
    }
    nodes = completed_nodes if completed_nodes is not None else ["t1"]
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
            "stop_requested": stop_requested,
            "run_data": {"t1": {"status": "success", "data": {"main": [[]]}}} if nodes else {},
            "completed_nodes": nodes,
            "revision_snapshot": revision_snapshot,
            "trigger": {},
        }
    )
    return exec_oid


async def _child_execution_count(db) -> int:
    return await db.flow_executions.count_documents({"resumed_from": {"$exists": True, "$ne": None}})


@pytest.mark.asyncio
async def test_full_resume_skips_completed_nodes() -> None:
    nodes = [_trigger(), _counting("b1", "B"), _counting("c1", "C")]
    connections = {"t1": {"main": [[_conn("b1")]]}, "b1": {"main": [[_conn("c1")]]}}
    rev = {"nodes": nodes, "connections": connections, "settings": {}, "pin_data": None}

    first = _ctx()
    await ad.flows.run_flow(context=first, revision=rev)
    assert _EXECUTE_COUNTS == {"b1": 1, "c1": 1}

    seed_run_data = dict(first.run_data)
    completed = frozenset(["t1", "b1"])
    _EXECUTE_COUNTS.clear()

    resumed = _ctx(
        execution_id="exec-resume",
        run_data=dict(seed_run_data),
        completed_nodes=completed,
        resumed_from="exec",
    )
    await ad.flows.run_flow(context=resumed, revision=rev)

    assert "c1" in resumed.run_data
    assert resumed.run_data["c1"]["status"] == "success"
    assert _EXECUTE_COUNTS.get("b1", 0) == 0
    assert _EXECUTE_COUNTS.get("c1", 0) == 1


@pytest.mark.asyncio
async def test_in_flight_node_without_checkpoint_is_re_executed() -> None:
    """run_data for a node without a matching completed_nodes entry must re-run that node."""
    nodes = [_trigger(), _counting("b1", "B"), _counting("c1", "C")]
    connections = {"t1": {"main": [[_conn("b1")]]}, "b1": {"main": [[_conn("c1")]]}}
    rev = {"nodes": nodes, "connections": connections, "settings": {}, "pin_data": None}

    first = _ctx()
    await ad.flows.run_flow(context=first, revision=rev)
    assert _EXECUTE_COUNTS == {"b1": 1, "c1": 1}

    # Simulate worker death after persisting run_data but before completed_nodes checkpoint.
    seed_run_data = dict(first.run_data)
    completed = frozenset(["t1"])
    _EXECUTE_COUNTS.clear()

    resumed = _ctx(
        execution_id="exec-resume",
        run_data=dict(seed_run_data),
        completed_nodes=completed,
        resumed_from="exec",
    )
    await ad.flows.run_flow(context=resumed, revision=rev)

    assert resumed.run_data["c1"]["status"] == "success"
    assert _EXECUTE_COUNTS.get("b1", 0) == 1
    assert _EXECUTE_COUNTS.get("c1", 0) == 1


@pytest.mark.asyncio
async def test_enqueue_resume_execution(test_db) -> None:
    client_obj = ad.common.get_analytiq_client()
    db = ad.common.get_async_db()
    source_oid = ObjectId()
    source_id = str(source_oid)

    await db.flow_executions.insert_one(
        {
            "_id": source_oid,
            "flow_id": str(ObjectId()),
            "flow_revid": str(ObjectId()),
            "organization_id": TEST_ORG_ID,
            "mode": "manual",
            "status": "interrupted",
            "started_at": datetime.now(UTC),
            "finished_at": datetime.now(UTC),
            "run_data": {"t1": {"status": "success", "data": {"main": [[]]}}},
            "completed_nodes": ["t1"],
            "trigger": {},
        }
    )

    new_id = await ad.flows.enqueue_resume_execution(client_obj, db, await db.flow_executions.find_one({"_id": source_oid}))
    assert new_id is not None

    source = await db.flow_executions.find_one({"_id": source_oid})
    assert source is not None
    assert source["resumed_by"] == new_id

    child = await db.flow_executions.find_one({"_id": ObjectId(new_id)})
    assert child is not None
    assert child["status"] == "queued"
    assert child.get("started_at") is None
    assert child["resumed_from"] == source_id
    assert child["completed_nodes"] == ["t1"]


@pytest.mark.asyncio
async def test_enqueue_resume_rejects_already_resumed(test_db) -> None:
    client_obj = ad.common.get_analytiq_client()
    db = ad.common.get_async_db()
    source_oid = ObjectId()

    await db.flow_executions.insert_one(
        {
            "_id": source_oid,
            "flow_id": str(ObjectId()),
            "flow_revid": str(ObjectId()),
            "organization_id": TEST_ORG_ID,
            "mode": "manual",
            "status": "interrupted",
            "started_at": datetime.now(UTC),
            "finished_at": datetime.now(UTC),
            "run_data": {"t1": {"status": "success", "data": {"main": [[]]}}},
            "completed_nodes": ["t1"],
            "resumed_by": str(ObjectId()),
            "trigger": {},
        }
    )

    doc = await db.flow_executions.find_one({"_id": source_oid})
    assert await ad.flows.enqueue_resume_execution(client_obj, db, doc) is None


@pytest.fixture(autouse=True)
def fast_stale_threshold(monkeypatch):
    monkeypatch.setenv("FLOW_EXECUTION_STALE_SECS", "30")
    monkeypatch.setattr(recovery_mod, "FLOW_EXECUTION_STALE_SECS", 30)


@pytest.mark.asyncio
async def test_auto_resume_on_stale_recovery_when_enabled(test_db, monkeypatch) -> None:
    client_obj = ad.common.get_analytiq_client()
    db = ad.common.get_async_db()
    exec_oid = ObjectId()

    await _insert_stale_running_execution(db, exec_oid=exec_oid, revision_settings={"resume_on_restart": True})

    sent: list[dict] = []

    async def _capture_send(_client, queue_name, msg=None, **_kwargs):
        sent.append({"queue": queue_name, "msg": msg})

    monkeypatch.setattr(ad.queue, "send_msg", _capture_send)

    recovered = await ad.flows.recover_stale_flow_executions(client_obj)
    assert recovered == 1

    source = await db.flow_executions.find_one({"_id": exec_oid})
    assert source is not None
    assert source["status"] == "interrupted"
    assert source.get("resumed_by")

    child = await db.flow_executions.find_one({"_id": ObjectId(source["resumed_by"])})
    assert child is not None
    assert child["status"] == "queued"
    assert len(sent) == 1
    assert sent[0]["queue"] == "flow_run"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "revision_settings",
    [
        {},
        {"resume_on_restart": False},
    ],
)
async def test_auto_resume_skipped_when_resume_on_restart_disabled(
    test_db, monkeypatch, revision_settings: dict[str, Any]
) -> None:
    client_obj = ad.common.get_analytiq_client()
    db = ad.common.get_async_db()
    exec_oid = ObjectId()

    await _insert_stale_running_execution(db, exec_oid=exec_oid, revision_settings=revision_settings)

    sent: list[dict] = []

    async def _capture_send(_client, queue_name, msg=None, **_kwargs):
        sent.append({"queue": queue_name, "msg": msg})

    monkeypatch.setattr(ad.queue, "send_msg", _capture_send)

    recovered = await ad.flows.recover_stale_flow_executions(client_obj)
    assert recovered == 1

    source = await db.flow_executions.find_one({"_id": exec_oid})
    assert source is not None
    assert source["status"] == "interrupted"
    assert source.get("resumed_by") is None
    assert await _child_execution_count(db) == 0
    assert sent == []


@pytest.mark.asyncio
async def test_stopped_execution_does_not_auto_resume(test_db, monkeypatch) -> None:
    client_obj = ad.common.get_analytiq_client()
    db = ad.common.get_async_db()
    exec_oid = ObjectId()

    await _insert_stale_running_execution(
        db,
        exec_oid=exec_oid,
        stop_requested=True,
        revision_settings={"resume_on_restart": True},
    )

    sent: list[dict] = []

    async def _capture_send(_client, queue_name, msg=None, **_kwargs):
        sent.append({"queue": queue_name, "msg": msg})

    monkeypatch.setattr(ad.queue, "send_msg", _capture_send)

    recovered = await ad.flows.recover_stale_flow_executions(client_obj)
    assert recovered == 1

    source = await db.flow_executions.find_one({"_id": exec_oid})
    assert source is not None
    assert source["status"] == "stopped"
    assert source.get("resumed_by") is None
    assert await _child_execution_count(db) == 0
    assert sent == []


@pytest.mark.asyncio
async def test_stale_scratch_retry_when_resume_enabled_and_no_checkpoints(test_db, monkeypatch) -> None:
    client_obj = ad.common.get_analytiq_client()
    db = ad.common.get_async_db()
    exec_oid = ObjectId()

    await _insert_stale_running_execution(
        db,
        exec_oid=exec_oid,
        revision_settings={"resume_on_restart": True},
        completed_nodes=[],
    )

    sent: list[dict] = []

    async def _capture_send(_client, queue_name, msg=None, **_kwargs):
        sent.append({"queue": queue_name, "msg": msg})

    monkeypatch.setattr(ad.queue, "send_msg", _capture_send)

    recovered = await ad.flows.recover_stale_flow_executions(client_obj)
    assert recovered == 1

    source = await db.flow_executions.find_one({"_id": exec_oid})
    assert source is not None
    assert source["status"] == "queued"
    assert source.get("finished_at") is None
    assert source["run_data"] == {}
    assert source.get("resumed_by") is None
    assert len(sent) == 1
    assert sent[0]["queue"] == "flow_run"
    assert sent[0]["msg"]["execution_id"] == str(exec_oid)


def _std_manual_node() -> dict:
    return _trigger()


@pytest.mark.asyncio
async def test_resume_execution_http(mock_auth, test_db) -> None:
    flow_id, rev_id = await _create_flow_for_resume_http()

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
            "status": "interrupted",
            "started_at": datetime.now(UTC),
            "finished_at": datetime.now(UTC),
            "run_data": {"t1": {"status": "success", "data": {"main": [[]]}}},
            "completed_nodes": ["t1"],
            "trigger": {},
            "start_trigger_node_id": "t1",
        }
    )

    r = client.post(
        f"/v0/orgs/{TEST_ORG_ID}/flows/{flow_id}/executions/{exec_id}/resume",
        headers=get_auth_headers(),
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["resumed_from"] == exec_id
    assert body["execution_id"]

    source = await db.flow_executions.find_one({"_id": exec_oid})
    assert source is not None
    assert source["resumed_by"] == body["execution_id"]


@pytest.mark.asyncio
async def test_resume_execution_http_rejects_running_source(mock_auth, test_db) -> None:
    flow_id, rev_id = await _create_flow_for_resume_http()
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
            "status": "running",
            "started_at": datetime.now(UTC),
            "finished_at": None,
            "run_data": {"t1": {"status": "success", "data": {"main": [[]]}}},
            "completed_nodes": ["t1"],
            "trigger": {},
            "start_trigger_node_id": "t1",
        }
    )

    r = client.post(
        f"/v0/orgs/{TEST_ORG_ID}/flows/{flow_id}/executions/{exec_id}/resume",
        headers=get_auth_headers(),
    )
    assert r.status_code == 409, r.text
    assert "resumable" in r.json()["detail"].lower()


@pytest.mark.asyncio
async def test_resume_execution_http_rejects_empty_checkpoints(mock_auth, test_db) -> None:
    flow_id, rev_id = await _create_flow_for_resume_http()
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
            "status": "interrupted",
            "started_at": datetime.now(UTC),
            "finished_at": datetime.now(UTC),
            "run_data": {},
            "completed_nodes": [],
            "trigger": {},
            "start_trigger_node_id": "t1",
        }
    )

    r = client.post(
        f"/v0/orgs/{TEST_ORG_ID}/flows/{flow_id}/executions/{exec_id}/resume",
        headers=get_auth_headers(),
    )
    assert r.status_code == 409, r.text
    assert "checkpoint" in r.json()["detail"].lower()


@pytest.mark.asyncio
async def test_resume_execution_http_rejects_already_resumed(mock_auth, test_db) -> None:
    flow_id, rev_id = await _create_flow_for_resume_http()
    exec_oid = ObjectId()
    exec_id = str(exec_oid)
    existing_child = str(ObjectId())
    db = ad.common.get_async_db()
    await db.flow_executions.insert_one(
        {
            "_id": exec_oid,
            "flow_id": flow_id,
            "flow_revid": rev_id,
            "organization_id": TEST_ORG_ID,
            "mode": "manual",
            "status": "interrupted",
            "started_at": datetime.now(UTC),
            "finished_at": datetime.now(UTC),
            "run_data": {"t1": {"status": "success", "data": {"main": [[]]}}},
            "completed_nodes": ["t1"],
            "resumed_by": existing_child,
            "trigger": {},
            "start_trigger_node_id": "t1",
        }
    )

    r = client.post(
        f"/v0/orgs/{TEST_ORG_ID}/flows/{flow_id}/executions/{exec_id}/resume",
        headers=get_auth_headers(),
    )
    assert r.status_code == 409, r.text
    assert "already resumed" in r.json()["detail"].lower()


async def _create_flow_for_resume_http() -> tuple[str, str]:
    r0 = client.post(
        f"/v0/orgs/{TEST_ORG_ID}/flows",
        json={"name": "resume http test"},
        headers=get_auth_headers(),
    )
    assert r0.status_code == 200, r0.text
    flow_id = r0.json()["flow"]["flow_id"]
    r1 = client.put(
        f"/v0/orgs/{TEST_ORG_ID}/flows/{flow_id}",
        json={
            "base_flow_revid": "",
            "name": "resume http test",
            "nodes": [_std_manual_node()],
            "connections": {},
            "settings": {},
            "pin_data": None,
        },
        headers=get_auth_headers(),
    )
    assert r1.status_code == 200, r1.text
    return flow_id, r1.json()["revision"]["flow_revid"]
