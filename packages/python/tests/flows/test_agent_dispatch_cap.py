"""Tests for agent dispatch helpers."""

from __future__ import annotations

from analytiq_data.flows.agent_loop.dispatch import _cap_nodes_snapshot, classify_tool_result
from analytiq_data.flows.agent_loop.messages import build_user_message


def test_cap_nodes_snapshot_trims_incrementally() -> None:
    nodes = {f"n{i}": {"payload": "x" * 4000} for i in range(50)}
    capped = _cap_nodes_snapshot(nodes)
    assert len(capped) < len(nodes)
    assert capped
    for key in capped:
        assert key in nodes


def test_classify_tool_result_dispatch_error() -> None:
    success, err = classify_tool_result('{"error": "Knowledge base not found"}')
    assert success is False
    assert err == "Knowledge base not found"


def test_classify_tool_result_tool_code_payload_with_error_field() -> None:
    success, err = classify_tool_result('{"error": "stale", "value": 1}')
    assert success is True
    assert err is None


def test_classify_tool_result_non_json_success() -> None:
    success, err = classify_tool_result("formatted kb results")
    assert success is True
    assert err is None


def test_build_user_message_falls_back_to_chat_input() -> None:
    msg = build_user_message(
        {"chatInput": "Hello from chat"},
        prompt_source="from_input",
        prompt_field="query",
        prompt_text="",
    )
    assert msg == "Hello from chat"
