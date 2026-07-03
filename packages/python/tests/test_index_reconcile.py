"""Tests for MongoDB index registry and deploy-time reconcile."""

from __future__ import annotations

import asyncio

import pytest

import analytiq_data as ad
from analytiq_data.docrouter_flows.event_dispatch import ensure_docrouter_flow_trigger_indexes
from analytiq_data.mongodb.index_registry import (
    EXPECTED_INDEXES,
    FLOW_EXECUTIONS_ACTIVE_FLOW_DOCUMENT_INDEX,
)
from analytiq_data.mongodb.index_reconcile import index_spec_matches, reconcile_indexes


@pytest.mark.asyncio
async def test_reconcile_creates_missing_indexes(test_db):
    summary = await reconcile_indexes(test_db)
    assert summary["created"] + summary["unchanged"] == len(EXPECTED_INDEXES)
    assert summary["updated"] == 0

    for spec in EXPECTED_INDEXES:
        indexes = await test_db[spec.collection].list_indexes().to_list(length=None)
        assert spec.name in {idx["name"] for idx in indexes}


@pytest.mark.asyncio
async def test_reconcile_idempotent_when_aligned(test_db):
    await reconcile_indexes(test_db)
    summary = await reconcile_indexes(test_db)
    assert summary["created"] == 0
    assert summary["updated"] == 0
    assert summary["unchanged"] == len(EXPECTED_INDEXES)


@pytest.mark.asyncio
async def test_index_spec_matches_partial_filter(test_db):
    await test_db.flow_executions.create_index(
        [("flow_id", 1), ("trigger.document_id", 1)],
        unique=True,
        partialFilterExpression={"status": {"$in": ["queued"]}},
        name=FLOW_EXECUTIONS_ACTIVE_FLOW_DOCUMENT_INDEX,
    )
    spec = next(
        s for s in EXPECTED_INDEXES if s.name == FLOW_EXECUTIONS_ACTIVE_FLOW_DOCUMENT_INDEX
    )
    live = (await test_db.flow_executions.list_indexes().to_list(length=None))[-1]
    assert not index_spec_matches(live, spec)

    summary = await reconcile_indexes(test_db)
    assert summary["updated"] >= 1

    live_after = next(
        idx
        for idx in await test_db.flow_executions.list_indexes().to_list(length=None)
        if idx["name"] == FLOW_EXECUTIONS_ACTIVE_FLOW_DOCUMENT_INDEX
    )
    assert index_spec_matches(live_after, spec)


@pytest.mark.asyncio
async def test_parallel_ensure_docrouter_flow_trigger_indexes(test_db):
    await asyncio.gather(
        *[ensure_docrouter_flow_trigger_indexes(test_db) for _ in range(16)]
    )
    indexes = await test_db.flow_executions.list_indexes().to_list(length=None)
    matching = [
        idx for idx in indexes if idx["name"] == FLOW_EXECUTIONS_ACTIVE_FLOW_DOCUMENT_INDEX
    ]
    assert len(matching) == 1


@pytest.mark.asyncio
async def test_reconcile_renames_legacy_auto_named_index(test_db):
    await test_db.flow_static_data.create_index(
        [("flow_id", 1), ("node_id", 1)],
        unique=True,
        name="flow_id_1_node_id_1",
    )

    summary = await reconcile_indexes(test_db)
    assert summary["updated"] >= 1

    indexes = await test_db.flow_static_data.list_indexes().to_list(length=None)
    names = {idx["name"] for idx in indexes}
    assert "flow_static_data_flow_node_unique" in names
    assert "flow_id_1_node_id_1" not in names


@pytest.mark.asyncio
async def test_run_migrations_reconciles_when_schema_current(test_db):
    client = ad.common.get_analytiq_client()
    target_version = len(ad.migrations.MIGRATIONS)
    await test_db.migrations.insert_one(
        {
            "_id": "schema_version",
            "version": target_version,
        }
    )

    await ad.migrations.run_migrations(client, target_version=target_version)

    indexes = await test_db.flow_triggers.list_indexes().to_list(length=None)
    assert "flow_triggers_flow_node_unique" in {idx["name"] for idx in indexes}
