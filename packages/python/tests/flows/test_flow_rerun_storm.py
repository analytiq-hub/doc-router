"""Tests for flow rerun storm fixes (enqueue dedupe + heartbeat-aware queue reclaim)."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

import pytest
import pytest_asyncio
from bson import ObjectId

import analytiq_data as ad
from analytiq_data.docrouter_flows.event_dispatch import (
    build_docrouter_event_flow_item,
    build_docrouter_event_payload,
    enqueue_docrouter_event_flow_run,
    ensure_docrouter_flow_trigger_indexes,
)
from analytiq_data.msg_handlers import flow_run as flow_run_mod
from analytiq_data.queue import queue as queue_mod

from tests.conftest_utils import TEST_ORG_ID


@pytest.fixture(autouse=True)
def fast_queue_visibility(monkeypatch):
    monkeypatch.setenv("QUEUE_VISIBILITY_TIMEOUT_SECS", "1")
    import importlib

    importlib.reload(queue_mod)


@pytest_asyncio.fixture
async def indexes_ready(test_db):
    await ensure_docrouter_flow_trigger_indexes(ad.common.get_async_db())


async def _minimal_enqueue_kwargs(
    analytiq_client,
    *,
    flow_id: str,
    flow_revid: str,
    document_id: str,
) -> dict:
    doc = {
        "_id": ObjectId(document_id),
        "organization_id": TEST_ORG_ID,
        "document_id": document_id,
        "user_file_name": "invoice.pdf",
        "tag_ids": [],
        "upload_date": datetime.now(UTC),
        "metadata": {},
    }
    payload = await build_docrouter_event_payload(
        analytiq_client,
        event_type="document.uploaded",
        doc=doc,
    )
    item = build_docrouter_event_flow_item(
        payload,
        doc,
        source_node_id="trigger-1",
    )
    return {
        "organization_id": TEST_ORG_ID,
        "flow_id": flow_id,
        "flow_revid": flow_revid,
        "trigger_node_id": "trigger-1",
        "payload": payload,
        "item": item,
    }


@pytest.mark.asyncio
async def test_enqueue_docrouter_event_dedupes_active_flow_document(test_db, indexes_ready):
    client = ad.common.get_analytiq_client()
    db = ad.common.get_async_db()
    flow_id = str(ObjectId())
    flow_revid = str(ObjectId())
    document_id = str(ObjectId())
    kwargs = await _minimal_enqueue_kwargs(
        client,
        flow_id=flow_id,
        flow_revid=flow_revid,
        document_id=document_id,
    )

    first_id = await enqueue_docrouter_event_flow_run(client, **kwargs)
    second_id = await enqueue_docrouter_event_flow_run(client, **kwargs)

    assert first_id == second_id
    assert await db.flow_executions.count_documents({"flow_id": flow_id}) == 1
    assert await db["queues.flow_run"].count_documents({}) == 1


@pytest.mark.asyncio
async def test_enqueue_docrouter_event_allows_rerun_after_completion(test_db, indexes_ready):
    client = ad.common.get_analytiq_client()
    db = ad.common.get_async_db()
    flow_id = str(ObjectId())
    flow_revid = str(ObjectId())
    document_id = str(ObjectId())
    kwargs = await _minimal_enqueue_kwargs(
        client,
        flow_id=flow_id,
        flow_revid=flow_revid,
        document_id=document_id,
    )

    first_id = await enqueue_docrouter_event_flow_run(client, **kwargs)
    await db.flow_executions.update_one(
        {"_id": ObjectId(first_id)},
        {"$set": {"status": "success", "finished_at": datetime.now(UTC)}},
    )

    second_id = await enqueue_docrouter_event_flow_run(client, **kwargs)
    assert second_id != first_id
    assert await db.flow_executions.count_documents({"flow_id": flow_id}) == 2
    assert await db["queues.flow_run"].count_documents({}) == 2


@pytest.mark.asyncio
async def test_enqueue_docrouter_event_distinct_documents_not_deduped(test_db, indexes_ready):
    client = ad.common.get_analytiq_client()
    db = ad.common.get_async_db()
    flow_id = str(ObjectId())
    flow_revid = str(ObjectId())
    doc_a = str(ObjectId())
    doc_b = str(ObjectId())

    kwargs_a = await _minimal_enqueue_kwargs(
        client, flow_id=flow_id, flow_revid=flow_revid, document_id=doc_a
    )
    kwargs_b = await _minimal_enqueue_kwargs(
        client, flow_id=flow_id, flow_revid=flow_revid, document_id=doc_b
    )

    id_a = await enqueue_docrouter_event_flow_run(client, **kwargs_a)
    id_b = await enqueue_docrouter_event_flow_run(client, **kwargs_b)

    assert id_a != id_b
    assert await db.flow_executions.count_documents({"flow_id": flow_id}) == 2


@pytest.mark.asyncio
async def test_enqueue_docrouter_event_concurrent_dedupe(test_db, indexes_ready):
    client = ad.common.get_analytiq_client()
    db = ad.common.get_async_db()
    flow_id = str(ObjectId())
    flow_revid = str(ObjectId())
    document_id = str(ObjectId())
    kwargs = await _minimal_enqueue_kwargs(
        client,
        flow_id=flow_id,
        flow_revid=flow_revid,
        document_id=document_id,
    )

    results = await asyncio.gather(
        enqueue_docrouter_event_flow_run(client, **kwargs),
        enqueue_docrouter_event_flow_run(client, **kwargs),
        enqueue_docrouter_event_flow_run(client, **kwargs),
    )

    assert len(set(results)) == 1
    assert await db.flow_executions.count_documents({"flow_id": flow_id}) == 1
    assert await db["queues.flow_run"].count_documents({}) == 1


@pytest.mark.asyncio
async def test_concurrent_manual_runs_same_flow_not_blocked(test_db, indexes_ready):
    """Manual runs lack trigger.document_id and must not hit the dedupe index."""
    db = ad.common.get_async_db()
    flow_id = str(ObjectId())
    flow_revid = str(ObjectId())
    now = datetime.now(UTC)

    async def _insert_manual() -> str:
        oid = ObjectId()
        await db.flow_executions.insert_one(
            {
                "_id": oid,
                "flow_id": flow_id,
                "flow_revid": flow_revid,
                "organization_id": TEST_ORG_ID,
                "mode": "manual",
                "status": "queued",
                "started_at": now,
                "finished_at": None,
                "last_heartbeat_at": None,
                "trigger": {"type": "manual"},
                "run_data": {},
            }
        )
        return str(oid)

    id_a, id_b = await asyncio.gather(_insert_manual(), _insert_manual())

    assert id_a != id_b
    assert await db.flow_executions.count_documents({"flow_id": flow_id}) == 2


@pytest.mark.asyncio
async def test_recover_stale_flow_run_skips_alive_execution(test_db, indexes_ready):
    client = ad.common.get_analytiq_client()
    db = ad.common.get_async_db()
    exec_id = str(ObjectId())
    stale_started = datetime.now(UTC) - timedelta(seconds=30)
    fresh_hb = datetime.now(UTC)

    await db.flow_executions.insert_one(
        {
            "_id": ObjectId(exec_id),
            "flow_id": str(ObjectId()),
            "flow_revid": str(ObjectId()),
            "organization_id": TEST_ORG_ID,
            "mode": "event",
            "status": "running",
            "started_at": stale_started,
            "last_heartbeat_at": fresh_hb,
            "trigger": {"document_id": str(ObjectId())},
        }
    )
    await db["queues.flow_run"].insert_one(
        {
            "status": "processing",
            "attempts": 1,
            "created_at": stale_started,
            "processing_started_at": stale_started,
            "msg": {"execution_id": exec_id},
        }
    )

    recovered = await flow_run_mod.recover_stale_flow_run_messages(client)
    assert recovered == 0

    row = await db["queues.flow_run"].find_one({})
    assert row is not None
    assert row["status"] == "processing"


@pytest.mark.asyncio
async def test_recover_stale_flow_run_reclaims_dead_execution(test_db, indexes_ready):
    client = ad.common.get_analytiq_client()
    db = ad.common.get_async_db()
    exec_id = str(ObjectId())
    stale = datetime.now(UTC) - timedelta(seconds=30)

    await db.flow_executions.insert_one(
        {
            "_id": ObjectId(exec_id),
            "flow_id": str(ObjectId()),
            "flow_revid": str(ObjectId()),
            "organization_id": TEST_ORG_ID,
            "mode": "event",
            "status": "running",
            "started_at": stale,
            "last_heartbeat_at": stale,
            "trigger": {"document_id": str(ObjectId())},
        }
    )
    await db["queues.flow_run"].insert_one(
        {
            "status": "processing",
            "attempts": 1,
            "created_at": stale,
            "processing_started_at": stale,
            "msg": {"execution_id": exec_id},
        }
    )

    recovered = await flow_run_mod.recover_stale_flow_run_messages(client)
    assert recovered == 1

    row = await db["queues.flow_run"].find_one({})
    assert row is not None
    assert row["status"] == "pending"
    assert row["attempts"] == 0


@pytest.mark.asyncio
async def test_recover_stale_flow_run_skips_queued_pre_running(test_db, indexes_ready):
    client = ad.common.get_analytiq_client()
    db = ad.common.get_async_db()
    exec_id = str(ObjectId())
    now = datetime.now(UTC)
    stale_message_at = now - timedelta(seconds=2)
    recent_started_at = now - timedelta(milliseconds=200)

    await db.flow_executions.insert_one(
        {
            "_id": ObjectId(exec_id),
            "flow_id": str(ObjectId()),
            "flow_revid": str(ObjectId()),
            "organization_id": TEST_ORG_ID,
            "mode": "event",
            "status": "queued",
            "started_at": recent_started_at,
            "last_heartbeat_at": None,
            "trigger": {"document_id": str(ObjectId())},
        }
    )
    await db["queues.flow_run"].insert_one(
        {
            "status": "processing",
            "attempts": 1,
            "created_at": stale_message_at,
            "processing_started_at": stale_message_at,
            "msg": {"execution_id": exec_id},
        }
    )

    recovered = await flow_run_mod.recover_stale_flow_run_messages(client)
    assert recovered == 0


@pytest.mark.asyncio
async def test_recv_flow_run_skips_alive_stale_processing(test_db, indexes_ready):
    client = ad.common.get_analytiq_client()
    db = ad.common.get_async_db()
    exec_id = str(ObjectId())
    stale = datetime.now(UTC) - timedelta(seconds=30)
    fresh_hb = datetime.now(UTC)

    await db.flow_executions.insert_one(
        {
            "_id": ObjectId(exec_id),
            "flow_id": str(ObjectId()),
            "flow_revid": str(ObjectId()),
            "organization_id": TEST_ORG_ID,
            "mode": "event",
            "status": "running",
            "started_at": stale,
            "last_heartbeat_at": fresh_hb,
            "trigger": {"document_id": str(ObjectId())},
        }
    )
    await db["queues.flow_run"].insert_one(
        {
            "status": "processing",
            "attempts": 1,
            "created_at": stale,
            "processing_started_at": stale,
            "msg": {"execution_id": exec_id},
        }
    )

    claimed = await flow_run_mod.recv_flow_run_msg(client)
    assert claimed is None


@pytest.mark.asyncio
async def test_recv_flow_run_reclaims_dead_stale_processing(test_db, indexes_ready):
    client = ad.common.get_analytiq_client()
    db = ad.common.get_async_db()
    exec_id = str(ObjectId())
    stale = datetime.now(UTC) - timedelta(seconds=30)

    await db.flow_executions.insert_one(
        {
            "_id": ObjectId(exec_id),
            "flow_id": str(ObjectId()),
            "flow_revid": str(ObjectId()),
            "organization_id": TEST_ORG_ID,
            "mode": "event",
            "status": "running",
            "started_at": stale,
            "last_heartbeat_at": stale,
            "trigger": {"document_id": str(ObjectId())},
        }
    )
    msg_id = (
        await db["queues.flow_run"].insert_one(
            {
                "status": "processing",
                "attempts": 1,
                "created_at": stale,
                "processing_started_at": stale,
                "msg": {"execution_id": exec_id},
            }
        )
    ).inserted_id

    claimed = await flow_run_mod.recv_flow_run_msg(client)
    assert claimed is not None
    assert claimed["_id"] == msg_id
    assert claimed["status"] == "processing"
    assert claimed["attempts"] == 2
