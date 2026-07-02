"""Unit tests for composable queue primitives in analytiq_data.queue.queue."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from bson import ObjectId

import analytiq_data as ad
from analytiq_data.queue import queue as queue_mod


QUEUE = "llm"


@pytest.fixture(autouse=True)
def fast_queue_visibility(monkeypatch):
    monkeypatch.setenv("QUEUE_VISIBILITY_TIMEOUT_SECS", "1")
    import importlib

    importlib.reload(queue_mod)


def test_lease_cutoff_subtracts_visibility_timeout():
    now = datetime(2026, 7, 2, 12, 0, 0, tzinfo=UTC)
    cutoff = queue_mod.lease_cutoff(now)
    assert cutoff == now - timedelta(seconds=queue_mod.QUEUE_VISIBILITY_TIMEOUT_SECS)


async def _insert_queue_row(
    db,
    *,
    status: str = "pending",
    attempts: int = 0,
    created_at: datetime | None = None,
    processing_started_at: datetime | None = None,
    msg: dict | None = None,
) -> ObjectId:
    doc: dict = {
        "status": status,
        "attempts": attempts,
        "created_at": created_at or datetime.now(UTC),
        "msg": msg or {"document_id": str(ObjectId())},
    }
    if processing_started_at is not None:
        doc["processing_started_at"] = processing_started_at
    return (await db[f"queues.{QUEUE}"].insert_one(doc)).inserted_id


@pytest.mark.asyncio
async def test_recv_pending_msg_claims_pending_only(test_db):
    client = ad.common.get_analytiq_client()
    db = ad.common.get_async_db()
    now = datetime.now(UTC)

    older_id = await _insert_queue_row(
        db,
        created_at=now - timedelta(seconds=10),
    )
    await _insert_queue_row(
        db,
        created_at=now - timedelta(seconds=5),
    )
    await _insert_queue_row(
        db,
        status="processing",
        attempts=1,
        processing_started_at=now,
    )

    claimed = await queue_mod.recv_pending_msg(client, QUEUE)

    assert claimed is not None
    assert claimed["_id"] == older_id
    assert claimed["status"] == "processing"
    assert claimed["attempts"] == 1
    assert claimed["processing_started_at"] is not None

    row = await db[f"queues.{QUEUE}"].find_one({"_id": older_id})
    assert row is not None
    assert row["status"] == "processing"


@pytest.mark.asyncio
async def test_recv_pending_msg_returns_none_when_only_processing(test_db):
    client = ad.common.get_analytiq_client()
    db = ad.common.get_async_db()
    now = datetime.now(UTC)

    await _insert_queue_row(
        db,
        status="processing",
        attempts=1,
        processing_started_at=now - timedelta(seconds=30),
    )

    assert await queue_mod.recv_pending_msg(client, QUEUE) is None


@pytest.mark.asyncio
async def test_recv_pending_msg_skips_max_attempts(test_db):
    client = ad.common.get_analytiq_client()
    db = ad.common.get_async_db()

    await _insert_queue_row(db, attempts=queue_mod.MAX_QUEUE_ATTEMPTS)

    assert await queue_mod.recv_pending_msg(client, QUEUE) is None


@pytest.mark.asyncio
async def test_list_stale_processing_messages_filters_by_age(test_db):
    client = ad.common.get_analytiq_client()
    db = ad.common.get_async_db()
    now = datetime.now(UTC)

    stale_id = await _insert_queue_row(
        db,
        status="processing",
        attempts=1,
        processing_started_at=now - timedelta(seconds=30),
    )
    await _insert_queue_row(
        db,
        status="processing",
        attempts=1,
        processing_started_at=now - timedelta(milliseconds=200),
    )
    await _insert_queue_row(db, status="pending", attempts=0)

    stale = await queue_mod.list_stale_processing_messages(client, QUEUE)

    assert len(stale) == 1
    assert stale[0]["_id"] == stale_id


@pytest.mark.asyncio
async def test_list_stale_processing_messages_respects_limit(test_db):
    client = ad.common.get_analytiq_client()
    db = ad.common.get_async_db()
    now = datetime.now(UTC)
    stale_at = now - timedelta(seconds=30)

    for offset in (10, 8, 6):
        await _insert_queue_row(
            db,
            status="processing",
            attempts=1,
            created_at=now - timedelta(seconds=offset),
            processing_started_at=stale_at,
        )

    stale = await queue_mod.list_stale_processing_messages(client, QUEUE, limit=2)

    assert len(stale) == 2
    created_times = [row["created_at"] for row in stale]
    assert created_times == sorted(created_times)


@pytest.mark.asyncio
async def test_try_reclaim_stale_processing_msg_reclaims_and_increments_attempts(test_db):
    client = ad.common.get_analytiq_client()
    db = ad.common.get_async_db()
    now = datetime.now(UTC)
    stale_at = now - timedelta(seconds=30)

    msg_id = await _insert_queue_row(
        db,
        status="processing",
        attempts=1,
        processing_started_at=stale_at,
    )

    reclaimed = await queue_mod.try_reclaim_stale_processing_msg(client, QUEUE, msg_id)

    assert reclaimed is not None
    assert reclaimed["_id"] == msg_id
    assert reclaimed["status"] == "processing"
    assert reclaimed["attempts"] == 2
    assert reclaimed["processing_started_at"] is not None


@pytest.mark.asyncio
async def test_try_reclaim_stale_processing_msg_no_match_when_still_fresh(test_db):
    client = ad.common.get_analytiq_client()
    db = ad.common.get_async_db()
    now = datetime.now(UTC)

    msg_id = await _insert_queue_row(
        db,
        status="processing",
        attempts=1,
        processing_started_at=now - timedelta(milliseconds=200),
    )

    reclaimed = await queue_mod.try_reclaim_stale_processing_msg(client, QUEUE, msg_id)

    assert reclaimed is None
    row = await db[f"queues.{QUEUE}"].find_one({"_id": msg_id})
    assert row is not None
    assert row["attempts"] == 1


@pytest.mark.asyncio
async def test_release_stale_processing_msg_resets_to_pending(test_db):
    client = ad.common.get_analytiq_client()
    db = ad.common.get_async_db()
    now = datetime.now(UTC)
    stale_at = now - timedelta(seconds=30)

    msg_id = await _insert_queue_row(
        db,
        status="processing",
        attempts=2,
        processing_started_at=stale_at,
    )

    released = await queue_mod.release_stale_processing_msg(client, QUEUE, msg_id)

    assert released is True
    row = await db[f"queues.{QUEUE}"].find_one({"_id": msg_id})
    assert row is not None
    assert row["status"] == "pending"
    assert row["attempts"] == 1
    assert "processing_started_at" not in row


@pytest.mark.asyncio
async def test_release_stale_processing_msg_no_op_when_still_fresh(test_db):
    client = ad.common.get_analytiq_client()
    db = ad.common.get_async_db()
    now = datetime.now(UTC)

    msg_id = await _insert_queue_row(
        db,
        status="processing",
        attempts=2,
        processing_started_at=now - timedelta(milliseconds=200),
    )

    released = await queue_mod.release_stale_processing_msg(client, QUEUE, msg_id)

    assert released is False
    row = await db[f"queues.{QUEUE}"].find_one({"_id": msg_id})
    assert row is not None
    assert row["status"] == "processing"
    assert row["attempts"] == 2
