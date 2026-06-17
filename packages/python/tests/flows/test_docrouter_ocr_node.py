"""Tests for ``docrouter.ocr`` flow node."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

import analytiq_data as ad
from analytiq_data.docrouter_flows.nodes.ocr_node import DocRouterOcrNode


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


def test_validate_parameters_requires_ocr_provider() -> None:
    node = DocRouterOcrNode()
    assert node.validate_parameters({}) == ["parameters.ocr_provider is required"]
    assert node.validate_parameters({"ocr_provider": "nope"}) == ["parameters.ocr_provider is required"]
    assert node.validate_parameters({"ocr_provider": "pymupdf"}) == []


@pytest.mark.asyncio
async def test_execute_requires_binary_pdf() -> None:
    node = DocRouterOcrNode()
    item = ad.flows.FlowItem(json={"document_id": "doc1"}, binary={}, meta={}, paired_item=None)
    with pytest.raises(ValueError, match="binary.pdf"):
        await node.execute(_ctx(), {"id": "ocr1", "parameters": {"ocr_provider": "pymupdf"}}, [[item]])


@pytest.mark.asyncio
async def test_execute_accepts_pinned_pdf_under_data_property() -> None:
    pdf_bytes = b"%PDF-1.4 pinned"
    item = ad.flows.FlowItem(
        json={"document_id": "doc1"},
        binary={
            "data": ad.flows.BinaryRef(
                mime_type="application/pdf",
                file_name="DocRouter_Bouyguer.pdf",
                data=pdf_bytes,
            ),
        },
        meta={},
        paired_item=None,
    )
    ocr_payload: dict[str, Any] = {"ocr_engine": "pymupdf", "pages": []}

    with patch(
        "analytiq_data.docrouter_flows.nodes.ocr_node.flow_services.run_flow_ocr_on_pdf",
        new=AsyncMock(return_value=(ocr_payload, [])),
    ):
        node = DocRouterOcrNode()
        out = await node.execute(
            _ctx(),
            {"id": "ocr1", "parameters": {"ocr_provider": "pymupdf"}},
            [[item]],
        )

    assert out[0][0].binary["pdf"].data == pdf_bytes
    assert set(out[0][0].binary.keys()) == {"pdf", "ocr_json"}
    assert out[0][0].binary["ocr_json"].mime_type == "application/json"


@pytest.mark.asyncio
async def test_execute_emits_ocr_pages_and_flow_blob(monkeypatch) -> None:
    pdf_bytes = b"%PDF-1.4 test"
    item = ad.flows.FlowItem(
        json={"document_id": "doc1", "file_name": "invoice.pdf"},
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
    ocr_payload: dict[str, Any] = {
        "ocr_engine": "pymupdf",
        "pages": [{"index": 0, "markdown": "# Page one"}],
    }
    saved: dict[str, Any] = {}

    async def _fake_save_blob_async(_client, *, bucket: str, key: str, blob: bytes, metadata: dict[str, Any], **_kw):
        saved["bucket"] = bucket
        saved["key"] = key
        saved["blob"] = blob
        saved["metadata"] = metadata

    monkeypatch.setattr(ad.mongodb.blob, "save_blob_async", _fake_save_blob_async)

    with patch(
        "analytiq_data.docrouter_flows.nodes.ocr_node.flow_services.run_flow_ocr_on_pdf",
        new=AsyncMock(return_value=(ocr_payload, ["Page one"])),
    ):
        node = DocRouterOcrNode()
        out = await node.execute(
            _ctx(analytiq_client=object()),
            {"id": "ocr1", "parameters": {"ocr_provider": "pymupdf"}},
            [[item]],
        )

    assert len(out) == 1 and len(out[0]) == 1
    result = out[0][0]
    assert result.json["ocr_provider"] == "pymupdf"
    assert result.json["ocr_pages"] == ["Page one"]
    assert result.binary["pdf"].data == pdf_bytes
    ocr_ref = result.binary["ocr_json"]
    assert ocr_ref.mime_type == "application/json"
    assert ocr_ref.data is None
    assert ocr_ref.storage_id == "flow_blobs:exec1/ocr1/0/ocr_json"
    assert saved["bucket"] == "flow_blobs"
    assert saved["key"] == "exec1/ocr1/0/ocr_json"
    assert b"pymupdf" in saved["blob"]


@pytest.mark.asyncio
async def test_execute_preserves_multiple_input_items() -> None:
    items = [
        ad.flows.FlowItem(
            json={"document_id": f"doc{i}"},
            binary={
                "pdf": ad.flows.BinaryRef(
                    mime_type="application/pdf",
                    data=f"pdf-{i}".encode(),
                ),
            },
            meta={},
            paired_item=None,
        )
        for i in range(2)
    ]

    async def _fake_ocr(_client, _org, pdf_bytes, *, ocr_provider, document_id=None):
        return ({"pages": [{"index": 0, "markdown": pdf_bytes.decode()}]}, [pdf_bytes.decode()])

    with patch(
        "analytiq_data.docrouter_flows.nodes.ocr_node.flow_services.run_flow_ocr_on_pdf",
        new=AsyncMock(side_effect=_fake_ocr),
    ):
        node = DocRouterOcrNode()
        out = await node.execute(
            _ctx(),
            {"id": "ocr1", "parameters": {"ocr_provider": "pymupdf"}},
            [items],
        )

    assert len(out[0]) == 2
    assert out[0][0].json["ocr_pages"] == ["pdf-0"]
    assert out[0][1].json["ocr_pages"] == ["pdf-1"]
