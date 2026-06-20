"""Tests for ``docrouter.llm_run`` flow node."""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

import analytiq_data as ad
from analytiq_data.docrouter_flows.nodes.llm_node import DocRouterLlmRunNode


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


def test_validate_parameters_requires_prompt_id() -> None:
    node = DocRouterLlmRunNode()
    assert node.validate_parameters({}) == ["parameters.prompt_id is required"]
    assert node.validate_parameters({"prompt_id": ""}) == ["parameters.prompt_id is required"]
    assert node.validate_parameters({"prompt_id": "p1"}) == []


@pytest.mark.asyncio
async def test_execute_without_ocr_port() -> None:
    main_item = ad.flows.FlowItem(
        json={"document_id": "doc1", "foo": "bar"},
        binary={"pdf": ad.flows.BinaryRef(mime_type="application/pdf", data=b"%PDF")},
        meta={"item_index": 0},
        paired_item=None,
    )
    llm_result = {"field": "value"}

    with patch(
        "analytiq_data.docrouter_flows.nodes.llm_node.flow_services.run_flow_llm_run",
        new=AsyncMock(return_value=llm_result),
    ) as mock_run:
        node = DocRouterLlmRunNode()
        out = await node.execute(
            _ctx(),
            {"id": "llm1", "parameters": {"prompt_id": "prompt1"}},
            [[main_item], []],
        )

    mock_run.assert_awaited_once_with(
        None,
        "org1",
        prompt_id="prompt1",
        item_json={"document_id": "doc1", "foo": "bar"},
        ocr_pages=None,
    )
    assert len(out[0]) == 1
    item = out[0][0]
    assert item.json == {"prompt_id": "prompt1", "llm_result": llm_result}
    assert item.binary["pdf"].mime_type == "application/pdf"


@pytest.mark.asyncio
async def test_execute_pairs_ocr_pages_by_index() -> None:
    main_item = ad.flows.FlowItem(json={"x": 1}, binary={}, meta={}, paired_item=None)
    ocr_item = ad.flows.FlowItem(
        json={"ocr_pages": ["page one", "page two"]},
        binary={},
        meta={},
        paired_item=None,
    )

    with patch(
        "analytiq_data.docrouter_flows.nodes.llm_node.flow_services.run_flow_llm_run",
        new=AsyncMock(return_value={"ok": True}),
    ) as mock_run:
        node = DocRouterLlmRunNode()
        await node.execute(
            _ctx(),
            {"id": "llm1", "parameters": {"prompt_id": "prompt1"}},
            [[main_item], [ocr_item]],
        )

    assert mock_run.await_args.kwargs["ocr_pages"] == ["page one", "page two"]


@pytest.mark.asyncio
async def test_run_flow_llm_run_builds_messages_and_records_spu(monkeypatch) -> None:
    from analytiq_data.docrouter_flows import services as flow_services

    class _FakeUsage:
        prompt_tokens = 10
        completion_tokens = 5

    class _FakeMessage:
        content = '{"answer": "yes"}'

    class _FakeChoice:
        message = _FakeMessage()

    class _FakeResponse:
        usage = _FakeUsage()
        choices = [_FakeChoice()]

    mock_client = object()
    prompt_revid = "665544332211aabbccddeeff"

    async def fake_resolve(_client, prompt_id: str) -> dict[str, Any]:
        assert prompt_id == "logical-prompt"
        return {"_id": prompt_revid, "prompt_id": prompt_id}

    async def fake_prompt_content(_client, revid: str) -> str:
        assert revid == prompt_revid
        return "Extract the answer."

    async def fake_get_model(_client, revid: str) -> str:
        return "gpt-4o-mini"

    async def fake_get_key(_client, provider: str) -> str:
        return "test-key"

    async def fake_check_spu(_org_id: str, _spus: int) -> None:
        return None

    async def fake_record_spu(*_args, **_kwargs) -> None:
        return None

    monkeypatch.setattr(flow_services, "_resolve_latest_prompt_revision", fake_resolve)
    monkeypatch.setattr(ad.common, "get_prompt_content", fake_prompt_content)
    monkeypatch.setattr(ad.llm, "get_llm_model", fake_get_model)
    monkeypatch.setattr(ad.llm, "get_llm_key", fake_get_key)
    monkeypatch.setattr(ad.payments, "check_spu_limits", fake_check_spu)
    monkeypatch.setattr(ad.payments, "record_spu_usage", fake_record_spu)
    monkeypatch.setattr(ad.payments, "compute_spu_to_charge", lambda cost, min_spu: min_spu)
    monkeypatch.setattr(
        "analytiq_data.docrouter_flows.services.litellm.supports_response_schema",
        lambda **kwargs: False,
    )
    monkeypatch.setattr(
        "analytiq_data.docrouter_flows.services.litellm.completion_cost",
        lambda **kwargs: 0.0,
    )

    with patch(
        "analytiq_data.docrouter_flows.services.ad.llm.agent_completion",
        new=AsyncMock(return_value=_FakeResponse()),
    ) as mock_llm:
        result = await flow_services.run_flow_llm_run(
            mock_client,
            "org1",
            prompt_id="logical-prompt",
            item_json={"foo": "bar"},
            ocr_pages=["line 1", "line 2"],
        )

    assert result == {"answer": "yes"}
    messages = mock_llm.await_args.kwargs["messages"]
    user_content = messages[1]["content"]
    assert "Extract the answer." in user_content
    assert '"foo": "bar"' in user_content
    assert "ocr_text:" in user_content
    assert "line 1\nline 2" in user_content


@pytest.mark.asyncio
async def test_execute_runs_items_in_parallel_up_to_eight() -> None:
    active = 0
    max_active = 0
    lock = asyncio.Lock()
    main_items = [
        ad.flows.FlowItem(json={"i": i}, binary={}, meta={}, paired_item=None) for i in range(10)
    ]

    async def _slow_run(*_args, **_kwargs):
        nonlocal active, max_active
        async with lock:
            active += 1
            max_active = max(max_active, active)
        await asyncio.sleep(0.02)
        async with lock:
            active -= 1
        return {"ok": True}

    with patch(
        "analytiq_data.docrouter_flows.nodes.llm_node.flow_services.run_flow_llm_run",
        new=AsyncMock(side_effect=_slow_run),
    ) as mock_run:
        node = DocRouterLlmRunNode()
        out = await node.execute(
            _ctx(),
            {"id": "llm1", "parameters": {"prompt_id": "prompt1"}},
            [main_items, []],
        )

    assert mock_run.await_count == 10
    assert len(out[0]) == 10
    assert max_active <= 8
    assert max_active >= 2
