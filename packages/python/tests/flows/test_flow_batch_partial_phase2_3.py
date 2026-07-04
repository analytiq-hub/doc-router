"""Phase 2/3 tests for batch partial results."""

from __future__ import annotations

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
from analytiq_data.flows.resume import find_resumable_batch_execution

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
