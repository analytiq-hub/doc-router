"""Tests for Chat Trigger node (`flows.trigger.chat`)."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

import analytiq_data as ad
from analytiq_data.flows.nodes.trigger_chat import FlowsChatTriggerNode, resolve_chat_input


@pytest.mark.parametrize(
    ("trigger_data", "node_params", "execution_mode", "expected"),
    [
        (
            {"chatInput": "  hello  "},
            {},
            "manual",
            "hello",
        ),
        (
            {"type": "manual"},
            {"initial_messages": "What is the temperature in Boston?"},
            "manual",
            "What is the temperature in Boston?",
        ),
        (
            {"chatInput": ""},
            {"initial_messages": "fallback question"},
            "manual",
            "fallback question",
        ),
        (
            {"chatInput": ""},
            {"initial_messages": "ignored greeting"},
            "chat",
            "",
        ),
        (
            {"chatInput": "from api"},
            {"initial_messages": "ignored"},
            "manual",
            "from api",
        ),
        (
            {"type": "manual"},
            {"initial_messages": "  \n  "},
            "manual",
            "",
        ),
    ],
)
def test_resolve_chat_input(
    trigger_data: dict,
    node_params: dict,
    execution_mode: str,
    expected: str,
) -> None:
    assert resolve_chat_input(trigger_data, node_params, execution_mode=execution_mode) == expected


@pytest.mark.asyncio
async def test_execute_manual_run_uses_initial_messages() -> None:
    node = FlowsChatTriggerNode()
    ctx = ad.flows.ExecutionContext(
        organization_id="org1",
        execution_id="exec1",
        flow_id="flow1",
        flow_revid="rev1",
        mode="manual",
        trigger_data={"type": "manual"},
        run_data={},
        analytiq_client=MagicMock(),
    )
    chat_node = {
        "id": "chat-1",
        "parameters": {
            "initial_messages": "What is the temperature in Boston and in Seattle?",
        },
    }

    out = await node.execute(ctx, chat_node, [])

    assert len(out) == 1
    assert len(out[0]) == 1
    assert out[0][0].json["chatInput"] == "What is the temperature in Boston and in Seattle?"
    assert out[0][0].json["action"] == "sendMessage"
