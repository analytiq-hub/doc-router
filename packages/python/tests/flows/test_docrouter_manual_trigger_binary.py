"""Binary refs on docrouter.trigger.manual (document GridFS keys → FlowItem.binary)."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

import analytiq_data as ad


@pytest.mark.asyncio
async def test_docrouter_manual_trigger_sets_pdf_and_original_binary_refs() -> None:
    fake_doc: dict[str, Any] = {
        "_id": "64f3a1b2c3d4e5f6a7b8c9d0",
        "organization_id": "org1",
        "user_file_name": "report.docx",
        "pdf_file_name": "grid-pdf.pdf",
        "mongo_file_name": "grid-orig.docx",
    }

    with patch(
        "analytiq_data.docrouter_flows.nodes.manual_trigger_node.flow_services.get_document",
        new=AsyncMock(return_value=fake_doc),
    ):
        n = ad.docrouter_flows.nodes.manual_trigger_node.DocRouterManualTriggerNode()
        ctx = ad.flows.ExecutionContext(
            organization_id="org1",
            execution_id="64f3a1b2c3d4e5f6a7b8c9d1",
            flow_id="flow1",
            flow_revid="rev1",
            mode="manual",
            trigger_data={"document_id": "64f3a1b2c3d4e5f6a7b8c9d0"},
            run_data={},
            analytiq_client=object(),
            stop_requested=False,
            logger=None,
        )
        out = await n.execute(ctx, {"id": "t1"}, [[]])

    assert len(out) == 1 and len(out[0]) == 1
    item = out[0][0]
    assert item.binary["pdf"].mime_type == "application/pdf"
    assert item.binary["pdf"].storage_id == "files:grid-pdf.pdf"
    assert item.binary["pdf"].file_name == "report.docx"

    assert item.binary["original"].mime_type == (
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )
    assert item.binary["original"].storage_id == "files:grid-orig.docx"
    assert item.binary["original"].file_name == "report.docx"


@pytest.mark.asyncio
async def test_docrouter_manual_trigger_dedupes_original_when_same_as_pdf() -> None:
    same_key = "same.pdf"
    fake_doc: dict[str, Any] = {
        "_id": "64f3a1b2c3d4e5f6a7b8c9d0",
        "organization_id": "org1",
        "pdf_file_name": same_key,
        "mongo_file_name": same_key,
    }

    with patch(
        "analytiq_data.docrouter_flows.nodes.manual_trigger_node.flow_services.get_document",
        new=AsyncMock(return_value=fake_doc),
    ):
        n = ad.docrouter_flows.nodes.manual_trigger_node.DocRouterManualTriggerNode()
        ctx = ad.flows.ExecutionContext(
            organization_id="org1",
            execution_id="64f3a1b2c3d4e5f6a7b8c9d1",
            flow_id="flow1",
            flow_revid="rev1",
            mode="manual",
            trigger_data={"document_id": "64f3a1b2c3d4e5f6a7b8c9d0"},
            run_data={},
            analytiq_client=object(),
            stop_requested=False,
            logger=None,
        )
        out = await n.execute(ctx, {"id": "t1"}, [[]])

    assert set(out[0][0].binary.keys()) == {"pdf"}
