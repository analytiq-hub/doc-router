"""Phase 2/3 tests for batch partial results."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from bson import ObjectId

import analytiq_data as ad
from analytiq_data.docrouter_flows.nodes.ocr_node import DocRouterOcrNode
from analytiq_data.flows.batch_progress import (
    batch_run_entry_is_resumable,
    load_batch_resume_items,
    run_data_has_resumable_batch,
)
from analytiq_data.flows.item_batch import FlowBatchItemErrors, map_flow_items_batch
from analytiq_data.flows.resume import (
    _resume_candidate_scan_pipeline,
    find_resumable_batch_execution,
)

from tests.conftest_utils import TEST_ORG_ID


@pytest.mark.asyncio
async def test_map_flow_items_batch_continue_on_item_error_collects_failures() -> None:
    async def fn(i: int) -> int:
        if i == 2:
            raise ValueError("boom")
        return i

    with pytest.raises(FlowBatchItemErrors) as exc_info:
        await map_flow_items_batch(5, fn, batch_size=2, continue_on_item_error=True)

    err = exc_info.value
    assert len(err.errors) == 1
    assert err.errors[0][0] == 2
    assert [x for x in err.results if x is not None] == [0, 1, 3, 4]


@pytest.mark.asyncio
async def test_map_flow_items_batch_fatal_error_invokes_callback() -> None:
    calls: list[int] = []

    async def fn(i: int) -> int:
        if i == 1:
            raise RuntimeError("fail")
        return i

    async def on_fatal(completed: int, _total: int, _results: list, _exc: BaseException) -> None:
        calls.append(completed)

    with pytest.raises(RuntimeError, match="fail"):
        await map_flow_items_batch(
            4,
            fn,
            batch_size=4,
            continue_on_item_error=False,
            on_fatal_item_error=on_fatal,
        )

    assert calls


def test_load_batch_resume_items_by_item_index() -> None:
    entry = {
        "status": "partial",
        "items_total": 5,
        "items_completed": 2,
        "data": {
            "main": [
                [
                    ad.flows.FlowItem(json={"i": 0}, binary={}, meta={"item_index": 0}),
                    ad.flows.FlowItem(json={"i": 2}, binary={}, meta={"item_index": 2}),
                ]
            ]
        },
    }
    assert batch_run_entry_is_resumable(entry)
    items = load_batch_resume_items(entry)
    assert set(items.keys()) == {0, 2}
    assert run_data_has_resumable_batch({"n1": entry})


@pytest.mark.asyncio
async def test_ocr_resume_skips_completed_items() -> None:
    items = [
        ad.flows.FlowItem(
            json={"i": i},
            binary={"pdf": ad.flows.BinaryRef(mime_type="application/pdf", data=f"p{i}".encode())},
            meta={"item_index": i},
            paired_item=None,
        )
        for i in range(4)
    ]
    partial_entry = {
        "status": "partial",
        "items_total": 4,
        "items_completed": 2,
        "data": {"main": [[items[0], items[1]]]},
    }
    ctx = ad.flows.ExecutionContext(
        organization_id="org1",
        execution_id="exec1",
        flow_id="flow1",
        flow_revid="rev1",
        mode="manual",
        trigger_data={},
        run_data={"ocr1": partial_entry},
        analytiq_client=None,
    )
    ocr_calls: list[int] = []

    async def _ocr_side(*_args, **_kwargs):
        return ({"pages": []}, ["page"])

    with patch(
        "analytiq_data.docrouter_flows.nodes.ocr_node.flow_services.run_flow_ocr_on_pdf",
        new=AsyncMock(side_effect=_ocr_side),
    ) as mock_ocr:
        node = DocRouterOcrNode()
        out = await node.execute(
            ctx,
            {
                "id": "ocr1",
                "type": "docrouter.ocr",
                "parameters": {"ocr_provider": "pymupdf"},
                "batch_size": 2,
            },
            [items],
        )

    assert len(out[0]) == 4
    assert mock_ocr.await_count == 2


@pytest.mark.asyncio
async def test_find_resumable_batch_execution(test_db) -> None:
    db = ad.common.get_async_db()
    org_id = TEST_ORG_ID
    flow_id = str(ObjectId())
    doc_id = str(ObjectId())
    exec_oid = ObjectId()

    await db.flow_executions.insert_one(
        {
            "_id": exec_oid,
            "organization_id": org_id,
            "flow_id": flow_id,
            "flow_revid": str(ObjectId()),
            "status": "error",
            "started_at": None,
            "trigger": {"document_id": doc_id},
            "completed_nodes": ["t1"],
            "run_data": {
                "ocr1": {
                    "status": "error",
                    "items_total": 10,
                    "items_completed": 4,
                    "data": {"main": [[{"json": {"i": 0}}]]},
                }
            },
        }
    )

    found = await find_resumable_batch_execution(
        db,
        organization_id=org_id,
        flow_id=flow_id,
        document_id=doc_id,
    )
    assert found is not None
    assert str(found["_id"]) == str(exec_oid)


@pytest.mark.asyncio
async def test_find_resumable_batch_execution_scans_lightweight_then_fetches_full() -> None:
    """Candidate scan should not load full run_data until a match is found."""

    org_id = TEST_ORG_ID
    flow_id = str(ObjectId())
    doc_id = str(ObjectId())
    match_oid = ObjectId()
    full_doc = {
        "_id": match_oid,
        "organization_id": org_id,
        "flow_id": flow_id,
        "flow_revid": str(ObjectId()),
        "status": "error",
        "completed_nodes": ["ocr1"],
        "run_data": {
            "ocr1": {
                "status": "error",
                "items_total": 10,
                "items_completed": 4,
                "data": {"main": [[{"json": {"i": 0}}]]},
            }
        },
    }

    class _FakeCursor:
        def __init__(self, docs):
            self._docs = list(docs)

        def __aiter__(self):
            self._iter = iter(self._docs)
            return self

        async def __anext__(self):
            try:
                return next(self._iter)
            except StopIteration:
                raise StopAsyncIteration from None

    class _FakeFlowExecutions:
        def __init__(self):
            self.aggregate_calls: list[list[dict[str, Any]]] = []
            self.find_one_calls: list[dict[str, Any]] = []

        def aggregate(self, pipeline):
            self.aggregate_calls.append(pipeline)
            return _FakeCursor(
                [
                    {
                        "_id": ObjectId(),
                        "completed_nodes": ["t1"],
                        "run_data": {
                            "ocr1": {
                                "status": "success",
                                "items_total": 10,
                                "items_completed": 10,
                            }
                        },
                    },
                    {
                        "_id": match_oid,
                        "completed_nodes": ["ocr1"],
                        "run_data": {
                            "ocr1": {
                                "status": "error",
                                "items_total": 10,
                                "items_completed": 4,
                            }
                        },
                    },
                ]
            )

        async def find_one(self, query, *_args, **_kwargs):
            self.find_one_calls.append(query)
            if query.get("_id") == match_oid:
                return dict(full_doc)
            return None

    class _FakeDb:
        def __init__(self):
            self.flow_executions = _FakeFlowExecutions()

    db = _FakeDb()
    found = await find_resumable_batch_execution(
        db,
        organization_id=org_id,
        flow_id=flow_id,
        document_id=doc_id,
    )

    assert found == full_doc
    assert len(db.flow_executions.aggregate_calls) == 1
    pipeline = db.flow_executions.aggregate_calls[0]
    assert pipeline[0]["$match"]["completed_nodes"] == {"$exists": True, "$ne": []}
    project = pipeline[-1]["$project"]
    projected_fields = project["run_data"]["$arrayToObject"]["$map"]["in"]["v"]
    assert set(projected_fields) == {"status", "items_total", "items_completed"}
    assert db.flow_executions.find_one_calls == [{"_id": match_oid}]


def test_resume_candidate_scan_pipeline_projects_batch_counters_only() -> None:
    pipeline = _resume_candidate_scan_pipeline({"flow_id": "f1"}, limit=5)
    assert pipeline[1] == {"$sort": {"started_at": -1}}
    assert pipeline[2] == {"$limit": 5}
    project = pipeline[3]["$project"]
    assert set(project) == {"_id", "completed_nodes", "run_data"}
