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
            {"manual_chat_input": "What is the temperature in Boston?"},
            "manual",
            "What is the temperature in Boston?",
        ),
        (
            {"chatInput": ""},
            {"manual_chat_input": "fallback question"},
            "manual",
            "fallback question",
        ),
        (
            {"chatInput": ""},
            {
                "initial_messages": "Welcome!\nHow can I help?",
                "manual_chat_input": "ignored when greeting only",
            },
            "chat",
            "",
        ),
        (
            {"chatInput": "from api"},
            {"manual_chat_input": "ignored"},
            "manual",
            "from api",
        ),
        (
            {"type": "manual"},
            {"manual_chat_input": "  \n  "},
            "manual",
            "",
        ),
        (
            {"type": "manual"},
            {
                "initial_messages": "Line one\nLine two",
                "manual_chat_input": "",
            },
            "manual",
            "",
        ),
        (
            {"type": "manual"},
            {
                "initial_messages": "Greeting only",
                "manual_chat_input": "Run this on execute",
            },
            "manual",
            "Run this on execute",
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
async def test_execute_manual_run_uses_manual_chat_input() -> None:
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
            "initial_messages": "Hello!\nAsk me anything.",
            "manual_chat_input": "What is the temperature in Boston and in Seattle?",
        },
    }

    out = await node.execute(ctx, chat_node, [])

    assert len(out) == 1
    assert len(out[0]) == 1
    assert out[0][0].json["chatInput"] == "What is the temperature in Boston and in Seattle?"
    assert out[0][0].json["action"] == "sendMessage"
