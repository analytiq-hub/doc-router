"""Tests for ``docrouter.document_split`` flow node."""

from __future__ import annotations

from io import BytesIO
from typing import Any

import fitz  # PyMuPDF
import pytest

import analytiq_data as ad
from analytiq_data.docrouter_flows.nodes.document_split_node import DocRouterDocumentSplitNode


def _ctx(*, analytiq_client: object | None = None) -> ad.flows.ExecutionContext:
    return ad.flows.ExecutionContext(
        organization_id="org1",
        execution_id="exec1",
        flow_id="flow1",
        flow_revid="rev1",
        mode="manual",
        trigger_data={},
        run_data={},
        analytiq_client=analytiq_client,
        stop_requested=False,
        logger=None,
    )


def _make_pdf(num_pages: int) -> bytes:
    doc = fitz.open()
    try:
        for i in range(num_pages):
            page = doc.new_page()
            page.insert_text((72, 72), f"Page {i}")
        buf = BytesIO()
        doc.save(buf)
        return buf.getvalue()
    finally:
        doc.close()


def test_validate_parameters_rejects_invalid_indices() -> None:
    node = DocRouterDocumentSplitNode()
    assert node.validate_parameters({"start": -1}) == ["parameters.start must be a non-negative integer"]
    assert node.validate_parameters({"stop": -2}) == ["parameters.stop must be a non-negative integer"]
    assert node.validate_parameters({"step": 0}) == ["parameters.step must be a positive integer"]


@pytest.mark.asyncio
async def test_execute_emits_one_item_per_page(monkeypatch) -> None:
    pdf_bytes = _make_pdf(3)
    item = ad.flows.FlowItem(
        json={"foo": "bar"},
        binary={
            "pdf_main": ad.flows.BinaryRef(
                mime_type="application/pdf",
                file_name="doc.pdf",
                data=pdf_bytes,
            ),
            "other": ad.flows.BinaryRef(
                mime_type="application/octet-stream",
                file_name="raw.bin",
                data=b"raw-bytes",
            ),
        },
        meta={"item_index": 0},
        paired_item=None,
    )

    saved_blobs: list[dict[str, Any]] = []

    async def fake_save_blob(_client, *, execution_id, node_id, item_index, property_name, blob, mime_type, file_name):
        saved_blobs.append(
            {
                "execution_id": execution_id,
                "node_id": node_id,
                "item_index": item_index,
                "property_name": property_name,
                "blob": blob,
                "mime_type": mime_type,
                "file_name": file_name,
            }
        )
        return ad.flows.BinaryRef(mime_type=mime_type, file_name=file_name, data=blob)

    monkeypatch.setattr(ad.flows, "save_execution_binary_blob", fake_save_blob)

    node = DocRouterDocumentSplitNode()
    out_batches = await node.execute(
        _ctx(),
        {"id": "split1", "parameters": {"start": 0, "step": 1}},
        [[item]],
    )

    out_items = out_batches[0]
    assert len(out_items) == 3

    for idx, out_item in enumerate(out_items):
        assert out_item.json == {"foo": "bar"}
        assert out_item.binary["other"].file_name == "raw.bin"
        assert "pdf_main" in out_item.binary
        assert out_item.binary["pdf_main"].file_name == f"doc_idx_{idx}.pdf"
        assert len(out_item.binary) == 2

    assert [b["item_index"] for b in saved_blobs] == [0, 1, 2]
    assert {b["mime_type"] for b in saved_blobs} == {"application/pdf"}


@pytest.mark.asyncio
async def test_execute_respects_start_stop_step(monkeypatch) -> None:
    pdf_bytes = _make_pdf(5)
    item = ad.flows.FlowItem(
        json={},
        binary={
            "pdf": ad.flows.BinaryRef(
                mime_type="application/pdf",
                file_name="invoice.pdf",
                data=pdf_bytes,
            ),
        },
        meta={},
        paired_item=None,
    )

    async def fake_save_blob(_client, *, execution_id, node_id, item_index, property_name, blob, mime_type, file_name):
        return ad.flows.BinaryRef(mime_type=mime_type, file_name=file_name, data=blob)

    monkeypatch.setattr(ad.flows, "save_execution_binary_blob", fake_save_blob)

    node = DocRouterDocumentSplitNode()
    out_batches = await node.execute(
        _ctx(),
        {"id": "split2", "parameters": {"start": 1, "stop": 5, "step": 2}},
        [[item]],
    )

    out_items = out_batches[0]
    assert len(out_items) == 2
    assert out_items[0].binary["pdf"].file_name == "invoice_idx_1.pdf"
    assert out_items[1].binary["pdf"].file_name == "invoice_idx_3.pdf"


@pytest.mark.asyncio
async def test_execute_stop_zero_splits_all_pages(monkeypatch) -> None:
    pdf_bytes = _make_pdf(2)
    item = ad.flows.FlowItem(
        json={},
        binary={
            "pdf": ad.flows.BinaryRef(
                mime_type="application/pdf",
                file_name="Sarah_Chen_Resume.pdf",
                data=pdf_bytes,
            ),
        },
        meta={},
        paired_item=None,
    )

    async def fake_save_blob(_client, *, execution_id, node_id, item_index, property_name, blob, mime_type, file_name):
        return ad.flows.BinaryRef(mime_type=mime_type, file_name=file_name, data=blob)

    monkeypatch.setattr(ad.flows, "save_execution_binary_blob", fake_save_blob)

    node = DocRouterDocumentSplitNode()
    out_batches = await node.execute(
        _ctx(),
        {"id": "split3", "parameters": {"start": 0, "stop": 0, "step": 1}},
        [[item]],
    )

    out_items = out_batches[0]
    assert len(out_items) == 2
    assert out_items[0].binary["pdf"].file_name == "Sarah_Chen_Resume_idx_0.pdf"
    assert out_items[1].binary["pdf"].file_name == "Sarah_Chen_Resume_idx_1.pdf"


def test_resolve_pdf_binary_ref_on_split_output_item() -> None:
    from analytiq_data.docrouter_flows.document_binary import resolve_pdf_binary_ref

    binary = {
        "pdf": ad.flows.BinaryRef(mime_type="application/pdf", file_name="a_idx_0.pdf"),
        "other": ad.flows.BinaryRef(mime_type="application/octet-stream", file_name="raw.bin"),
    }
    assert resolve_pdf_binary_ref(binary) is binary["pdf"]
