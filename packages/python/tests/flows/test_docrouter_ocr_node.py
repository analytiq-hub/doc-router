"""Tests for ``docrouter.ocr`` flow node."""

from __future__ import annotations

import asyncio
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
    assert node.validate_parameters({"ocr_provider": "llm"}) == ["parameters.ocr_provider is required"]
    assert node.validate_parameters({"ocr_provider": "pymupdf"}) == []


def test_validate_parameters_rejects_invalid_textract_features() -> None:
    node = DocRouterOcrNode()
    assert node.validate_parameters(
        {"ocr_provider": "textract", "textract_feature_types": ["NOT_A_FEATURE"]}
    ) == ["parameters.textract_feature_types contains invalid feature types"]
    assert node.validate_parameters(
        {"ocr_provider": "textract", "textract_feature_types": ["TABLES", "FORMS"]}
    ) == []


@pytest.mark.asyncio
async def test_execute_passes_textract_feature_types() -> None:
    item = ad.flows.FlowItem(
        json={},
        binary={"pdf": ad.flows.BinaryRef(mime_type="application/pdf", data=b"%PDF-1.4")},
        meta={},
        paired_item=None,
    )

    with patch(
        "analytiq_data.docrouter_flows.nodes.ocr_node.flow_services.run_flow_ocr_on_pdf",
        new=AsyncMock(return_value=({"pages": []}, [])),
    ) as mock_ocr:
        node = DocRouterOcrNode()
        out = await node.execute(
            _ctx(),
            {
                "id": "ocr1",
                "parameters": {
                    "ocr_provider": "textract",
                    "textract_feature_types": ["TABLES", "LAYOUT"],
                },
            },
            [[item]],
        )

    assert mock_ocr.await_args.kwargs["textract_feature_types"] == ["TABLES", "LAYOUT"]
    assert out[0][0].json["textract_feature_types"] == ["TABLES", "LAYOUT"]


@pytest.mark.asyncio
async def test_run_flow_ocr_on_pdf_textract_records_spus(monkeypatch) -> None:
    from analytiq_data.docrouter_flows import services as flow_services
    from analytiq_data.ocr.ocr_config import USD_TEXTRACT_TABLES_PER_PAGE, merge_org_ocr_config

    async def fake_fetch_org_ocr_config(_client, _org_id):
        return merge_org_ocr_config({"mode": "pymupdf"})

    async def fake_textract(*_a, feature_types=None, **_k):
        assert feature_types == ["TABLES"]
        return {"DocumentMetadata": {"Pages": 1}, "Blocks": []}

    import analytiq_data.payments.spu as spu_module

    monkeypatch.setattr(
        ad.ocr.ocr_config,
        "fetch_org_ocr_config",
        fake_fetch_org_ocr_config,
    )
    monkeypatch.setattr(ad.ocr, "ocr_pages_plain_text_list", lambda _payload: [])
    with (
        patch("analytiq_data.ocr.ocr_runners.textract_mod.run_textract", side_effect=fake_textract),
        patch("analytiq_data.ocr.ocr_runners.ad.payments.check_spu_limits"),
        patch("analytiq_data.ocr.ocr_runners.ad.payments.record_spu_usage") as rec,
        patch.object(spu_module, "get_price_per_credit", return_value=0.05),
    ):
        await flow_services.run_flow_ocr_on_pdf(
            None,
            "org1",
            b"%PDF-1.4",
            ocr_provider="textract",
            execution_id="exec1",
            textract_feature_types=["TABLES"],
        )

    rec.assert_called_once()
    assert rec.call_args.kwargs["operation"] == "ocr"
    assert rec.call_args.kwargs["actual_cost"] == pytest.approx(USD_TEXTRACT_TABLES_PER_PAGE)


@pytest.mark.asyncio
async def test_execute_skips_item_without_pdf() -> None:
    node = DocRouterOcrNode()
    item = ad.flows.FlowItem(json={"document_id": "doc1"}, binary={}, meta={}, paired_item=None)
    out = await node.execute(_ctx(), {"id": "ocr1", "parameters": {"ocr_provider": "pymupdf"}}, [[item]])
    assert out == [[]]


@pytest.mark.asyncio
async def test_execute_skips_empty_items_in_batch() -> None:
    items = [
        ad.flows.FlowItem(
            json={},
            binary={"pdf": ad.flows.BinaryRef(mime_type="application/pdf", data=b"%PDF-1.4")},
            meta={"item_index": 0},
            paired_item=0,
        ),
        ad.flows.FlowItem(json={}, binary={}, meta={"item_index": 1}, paired_item=1),
        ad.flows.FlowItem(json={}, binary={}, meta={"item_index": 2}, paired_item=2),
    ]

    with patch(
        "analytiq_data.docrouter_flows.nodes.ocr_node.flow_services.run_flow_ocr_on_pdf",
        new=AsyncMock(return_value=({"pages": []}, ["page"])),
    ) as mock_ocr:
        node = DocRouterOcrNode()
        out = await node.execute(
            _ctx(),
            {"id": "ocr1", "parameters": {"ocr_provider": "pymupdf"}},
            [items],
        )

    mock_ocr.assert_awaited_once()
    assert len(out[0]) == 1
    assert out[0][0].json["ocr_pages"] == ["page"]
    assert out[0][0].paired_item == 0


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
    ) as mock_ocr:
        node = DocRouterOcrNode()
        out = await node.execute(
            _ctx(),
            {"id": "ocr1", "parameters": {"ocr_provider": "pymupdf"}},
            [[item]],
        )

    mock_ocr.assert_awaited_once()
    assert mock_ocr.await_args.kwargs["execution_id"] == "exec1"

    assert out[0][0].binary["pdf"].data == pdf_bytes
    assert set(out[0][0].binary.keys()) == {"pdf", "ocr_json"}
    assert out[0][0].binary["ocr_json"].mime_type == "application/json"


@pytest.mark.asyncio
async def test_execute_passes_execution_id_to_flow_ocr() -> None:
    item = ad.flows.FlowItem(
        json={},
        binary={
            "pdf": ad.flows.BinaryRef(mime_type="application/pdf", data=b"%PDF-1.4"),
        },
        meta={},
        paired_item=None,
    )

    with patch(
        "analytiq_data.docrouter_flows.nodes.ocr_node.flow_services.run_flow_ocr_on_pdf",
        new=AsyncMock(return_value=({"pages": []}, [])),
    ) as mock_ocr:
        node = DocRouterOcrNode()
        await node.execute(
            _ctx(),
            {"id": "ocr1", "parameters": {"ocr_provider": "pymupdf"}},
            [[item]],
        )

    assert mock_ocr.await_args.kwargs["execution_id"] == "exec1"


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
async def test_execute_uses_first_binary_when_pdf_property_missing() -> None:
    item = ad.flows.FlowItem(
        json={"document_id": "doc1"},
        binary={
            "foo": ad.flows.BinaryRef(
                mime_type="application/pdf",
                file_name="a.pdf",
                data=b"%PDF-1.4 a",
            ),
            "foo_2": ad.flows.BinaryRef(
                mime_type="application/pdf",
                file_name="b.pdf",
                data=b"%PDF-1.4 b",
            ),
        },
        meta={"item_index": 2},
        paired_item=2,
    )

    with patch(
        "analytiq_data.docrouter_flows.nodes.ocr_node.flow_services.run_flow_ocr_on_pdf",
        new=AsyncMock(return_value=({"pages": []}, ["first only"])),
    ) as mock_ocr:
        node = DocRouterOcrNode()
        out = await node.execute(
            _ctx(),
            {"id": "ocr1", "parameters": {"ocr_provider": "pymupdf"}},
            [[item]],
        )

    mock_ocr.assert_awaited_once()
    assert mock_ocr.await_args.args[2] == b"%PDF-1.4 a"
    assert len(out[0]) == 1
    assert out[0][0].json["ocr_pages"] == ["first only"]
    assert out[0][0].binary["pdf"].data == b"%PDF-1.4 a"


@pytest.mark.asyncio
async def test_execute_prefers_pdf_property_over_other_binaries() -> None:
    item = ad.flows.FlowItem(
        json={},
        binary={
            "foo": ad.flows.BinaryRef(mime_type="application/pdf", data=b"%PDF-1.4 foo"),
            "pdf": ad.flows.BinaryRef(mime_type="application/pdf", data=b"%PDF-1.4 chosen"),
        },
        meta={},
        paired_item=None,
    )

    with patch(
        "analytiq_data.docrouter_flows.nodes.ocr_node.flow_services.run_flow_ocr_on_pdf",
        new=AsyncMock(return_value=({"pages": []}, [])),
    ) as mock_ocr:
        node = DocRouterOcrNode()
        await node.execute(_ctx(), {"id": "ocr1", "parameters": {"ocr_provider": "pymupdf"}}, [[item]])

    assert mock_ocr.await_args.args[2] == b"%PDF-1.4 chosen"


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

    async def _fake_ocr(_client, _org, pdf_bytes, *, ocr_provider, execution_id, textract_feature_types=None):
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


@pytest.mark.asyncio
async def test_execute_runs_items_in_parallel_up_to_eight() -> None:
    active = 0
    max_active = 0
    lock = asyncio.Lock()
    items = [
        ad.flows.FlowItem(
            json={"document_id": f"doc{i}"},
            binary={"pdf": ad.flows.BinaryRef(mime_type="application/pdf", data=f"pdf-{i}".encode())},
            meta={},
            paired_item=None,
        )
        for i in range(10)
    ]

    async def _slow_ocr(*_args, **_kwargs):
        nonlocal active, max_active
        async with lock:
            active += 1
            max_active = max(max_active, active)
        await asyncio.sleep(0.02)
        async with lock:
            active -= 1
        return ({"pages": []}, ["page"])

    with patch(
        "analytiq_data.docrouter_flows.nodes.ocr_node.flow_services.run_flow_ocr_on_pdf",
        new=AsyncMock(side_effect=_slow_ocr),
    ) as mock_ocr:
        node = DocRouterOcrNode()
        out = await node.execute(
            _ctx(),
            {"id": "ocr1", "parameters": {"ocr_provider": "pymupdf"}},
            [items],
        )

    assert mock_ocr.await_count == 10
    assert len(out[0]) == 10
    assert max_active <= 8
    assert max_active >= 2
