"""Tests for document-scoped flow rerun (sidebar + bulk Run Flows)."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from bson import ObjectId

import analytiq_data as ad
from analytiq_data.docrouter_flows import document_flow_sidebar as mod
from analytiq_data.docrouter_flows.document_flow_sidebar import rerun_flow_for_document

from tests.conftest_utils import TEST_ORG_ID


@pytest.mark.asyncio
async def test_incomplete_only_without_partial_starts_force_rerun(monkeypatch: pytest.MonkeyPatch) -> None:
    """incomplete_only must not 409 when no checkpoint exists — fall back to force enqueue."""

    client = ad.common.get_analytiq_client()
    org_id = TEST_ORG_ID
    flow_id = str(ObjectId())
    document_id = str(ObjectId())
    flow_revid = str(ObjectId())

    tag_id = str(ObjectId())
    revision = {
        "_id": ObjectId(flow_revid),
        "flow_id": flow_id,
        "nodes": [
            {
                "id": "t1",
                "type": "docrouter.trigger",
                "disabled": False,
                "parameters": {
                    "tag_ids": [tag_id],
                    "event_type": "document.uploaded",
                    "report_result": True,
                },
            }
        ],
    }

    class _FakeCollection:
        async def find_one(self, query, *_args, **_kwargs):
            if query.get("_id") == ObjectId(flow_revid):
                return revision
            return None

    class _FakeDb:
        flow_revisions = _FakeCollection()

        def __getitem__(self, _name):
            return _FakeCollection()

    class _FakeClient:
        env = client.env
        mongodb_async = {client.env: _FakeDb()}

    monkeypatch.setattr(ad.common.doc, "get_doc", AsyncMock(return_value={"organization_id": org_id}))
    monkeypatch.setattr(
        mod,
        "_load_flow_header",
        AsyncMock(return_value={"_id": ObjectId(flow_id), "active": True, "active_flow_revid": flow_revid}),
    )
    monkeypatch.setattr(mod, "_load_document_tag_ids", AsyncMock(return_value={tag_id}))
    monkeypatch.setattr(
        "analytiq_data.flows.resume.find_resumable_batch_execution",
        AsyncMock(return_value=None),
    )
    enqueue_mock = AsyncMock(return_value="force-exec-id")
    monkeypatch.setattr(mod, "enqueue_docrouter_event_flow_run", enqueue_mock)
    monkeypatch.setattr(mod, "_latest_llm_context_for_flow_rerun", AsyncMock(return_value=(None, None, None, None)))

    exec_id = await rerun_flow_for_document(
        _FakeClient(),
        org_id=org_id,
        document_id=document_id,
        flow_id=flow_id,
        mode="incomplete_only",
    )

    assert exec_id == "force-exec-id"
    enqueue_mock.assert_awaited_once()


@pytest.mark.asyncio
async def test_incomplete_only_revision_mismatch_starts_force_rerun(monkeypatch: pytest.MonkeyPatch) -> None:
    """incomplete_only must fall back to force when partial run is on an older revision."""

    client = ad.common.get_analytiq_client()
    org_id = TEST_ORG_ID
    flow_id = str(ObjectId())
    document_id = str(ObjectId())
    flow_revid = str(ObjectId())
    old_revid = str(ObjectId())
    tag_id = str(ObjectId())

    revision = {
        "_id": ObjectId(flow_revid),
        "flow_id": flow_id,
        "nodes": [
            {
                "id": "t1",
                "type": "docrouter.trigger",
                "disabled": False,
                "parameters": {
                    "tag_ids": [tag_id],
                    "event_type": "document.uploaded",
                    "report_result": True,
                },
            }
        ],
    }

    class _FakeCollection:
        async def find_one(self, query, *_args, **_kwargs):
            if query.get("_id") == ObjectId(flow_revid):
                return revision
            return None

    class _FakeDb:
        flow_revisions = _FakeCollection()

        def __getitem__(self, _name):
            return _FakeCollection()

    class _FakeClient:
        env = client.env
        mongodb_async = {client.env: _FakeDb()}

    monkeypatch.setattr(ad.common.doc, "get_doc", AsyncMock(return_value={"organization_id": org_id}))
    monkeypatch.setattr(
        mod,
        "_load_flow_header",
        AsyncMock(return_value={"_id": ObjectId(flow_id), "active": True, "active_flow_revid": flow_revid}),
    )
    monkeypatch.setattr(mod, "_load_document_tag_ids", AsyncMock(return_value={tag_id}))
    monkeypatch.setattr(
        "analytiq_data.flows.resume.find_resumable_batch_execution",
        AsyncMock(return_value={"flow_revid": old_revid, "_id": ObjectId()}),
    )
    enqueue_mock = AsyncMock(return_value="force-exec-id")
    monkeypatch.setattr(mod, "enqueue_docrouter_event_flow_run", enqueue_mock)
    monkeypatch.setattr(mod, "_latest_llm_context_for_flow_rerun", AsyncMock(return_value=(None, None, None, None)))

    exec_id = await rerun_flow_for_document(
        _FakeClient(),
        org_id=org_id,
        document_id=document_id,
        flow_id=flow_id,
        mode="incomplete_only",
    )

    assert exec_id == "force-exec-id"
    enqueue_mock.assert_awaited_once()
