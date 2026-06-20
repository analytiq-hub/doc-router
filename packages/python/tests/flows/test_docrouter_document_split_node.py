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
async def test_execute_splits_pdf_into_pages(monkeypatch) -> None:
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

    assert len(out_batches) == 1
    out_items = out_batches[0]
    assert len(out_items) == 1
    out_item = out_items[0]

    # Non-PDF binary is preserved.
    assert "other" in out_item.binary
    assert out_item.binary["other"].file_name == "raw.bin"

    # Three page PDFs inserted, with expected names and property keys.
    page_keys = sorted(k for k in out_item.binary.keys() if k.startswith("pdf_main_idx_"))
    assert page_keys == ["pdf_main_idx_0", "pdf_main_idx_1", "pdf_main_idx_2"]
    page_names = [out_item.binary[k].file_name for k in page_keys]
    assert page_names == ["doc_idx_0.pdf", "doc_idx_1.pdf", "doc_idx_2.pdf"]

    # Blobs were saved with application/pdf mime type.
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

    out_item = out_batches[0][0]
    page_keys = sorted(k for k in out_item.binary.keys() if k.startswith("pdf_idx_"))
    # Indices 1 and 3 should be selected.
    assert page_keys == ["pdf_idx_1", "pdf_idx_3"]
    page_names = [out_item.binary[k].file_name for k in page_keys]
    assert page_names == ["invoice_idx_1.pdf", "invoice_idx_3.pdf"]


@pytest.mark.asyncio
async def test_execute_stop_zero_splits_all_pages(monkeypatch) -> None:
    """stop=0 means no stop limit — split through the last page."""
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

    out_item = out_batches[0][0]
    assert "pdf" not in out_item.binary
    page_keys = sorted(k for k in out_item.binary.keys() if k.startswith("pdf_idx_"))
    assert page_keys == ["pdf_idx_0", "pdf_idx_1"]
    assert [out_item.binary[k].file_name for k in page_keys] == [
        "Sarah_Chen_Resume_idx_0.pdf",
        "Sarah_Chen_Resume_idx_1.pdf",
    ]


def test_resolve_pdf_binary_ref_on_split_output() -> None:
    from analytiq_data.docrouter_flows.document_binary import list_pdf_binary_refs, resolve_pdf_binary_ref

    binary = {
        "pdf_idx_0": ad.flows.BinaryRef(mime_type="application/pdf", file_name="a_idx_0.pdf"),
        "pdf_idx_1": ad.flows.BinaryRef(mime_type="application/pdf", file_name="a_idx_1.pdf"),
        "other": ad.flows.BinaryRef(mime_type="application/octet-stream", file_name="raw.bin"),
    }
    assert resolve_pdf_binary_ref(binary) is binary["pdf_idx_0"]
    assert list_pdf_binary_refs(binary) == [binary["pdf_idx_0"], binary["pdf_idx_1"]]

