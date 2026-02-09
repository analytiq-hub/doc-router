"""Tests for agent loop with mocked LLM (no real API or DB)."""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from analytiq_data.agent.agent_loop import (
    run_agent_turn,
    run_agent_approve,
    _sanitize_messages_for_llm,
)
from analytiq_data.agent.session import set_turn_state, get_turn_state, clear_turn_state, generate_turn_id


@pytest.fixture
def mock_analytiq_client():
    client = MagicMock()
    client.env = "test"
    return client


@pytest.fixture
def mock_payments():
    with patch("analytiq_data.agent.agent_loop.ad.payments") as m:
        m.get_spu_cost = AsyncMock(return_value=1)
        m.check_spu_limits = AsyncMock()
        yield m


@pytest.fixture
def mock_llm_key():
    with patch("analytiq_data.agent.agent_loop.ad.llm.get_llm_key", new_callable=AsyncMock) as m:
        m.return_value = "test-api-key"
        yield m


@pytest.fixture
def mock_llm_provider():
    with patch("analytiq_data.agent.agent_loop.ad.llm.get_llm_model_provider") as m:
        m.return_value = "openai"
        yield m


@pytest.fixture
def mock_litellm():
    with patch("analytiq_data.llm.agent_completion", new_callable=AsyncMock) as m:
        yield m


@pytest.fixture
def mock_build_system():
    with patch("analytiq_data.agent.agent_loop.build_system_message", new_callable=AsyncMock) as m:
        m.return_value = "You are a document assistant."
        yield m


@pytest.mark.asyncio
async def test_run_agent_turn_returns_text_when_no_tool_calls(
    mock_analytiq_client,
    mock_payments,
    mock_llm_key,
    mock_llm_provider,
    mock_litellm,
    mock_build_system,
):
    msg = MagicMock()
    msg.content = "Here is the summary."
    msg.tool_calls = None
    mock_litellm.return_value = MagicMock(
        choices=[MagicMock(message=msg)],
        usage=MagicMock(prompt_tokens=10, completion_tokens=5),
    )
    result = await run_agent_turn(
        analytiq_client=mock_analytiq_client,
        organization_id="org1",
        document_id="doc1",
        user_id="user1",
        messages=[{"role": "user", "content": "Summarize the document."}],
        model="gpt-4o-mini",
        auto_approve=False,
    )
    assert "error" not in result
    assert result.get("text") == "Here is the summary."


@pytest.mark.asyncio
async def test_run_agent_turn_returns_turn_id_when_tool_calls_and_not_auto_approve(
    mock_analytiq_client,
    mock_payments,
    mock_llm_key,
    mock_llm_provider,
    mock_litellm,
    mock_build_system,
):
    msg = MagicMock()
    msg.content = "I will create a schema."
    tc = MagicMock()
    tc.id = "call_1"
    tc.function.name = "help_schemas"
    tc.function.arguments = "{}"
    msg.tool_calls = [tc]
    mock_litellm.return_value = MagicMock(
        choices=[MagicMock(message=msg)],
        usage=MagicMock(prompt_tokens=10, completion_tokens=5),
    )
    result = await run_agent_turn(
        analytiq_client=mock_analytiq_client,
        organization_id="org1",
        document_id="doc1",
        user_id="user1",
        messages=[{"role": "user", "content": "Create a schema for invoices."}],
        model="gpt-4o-mini",
        auto_approve=False,
    )
    assert "error" not in result
    assert "turn_id" in result
    assert result.get("text") == "I will create a schema."
    assert len(result.get("tool_calls", [])) == 1
    assert result["tool_calls"][0]["name"] == "help_schemas"


def test_sanitize_messages_strips_tool_calls_without_results():
    """After navigating away and back, thread can have assistant+tool_calls with no tool results."""
    messages = [
        {"role": "user", "content": "Create a tag"},
        {"role": "assistant", "content": "I'll create it.", "tool_calls": [{"id": "toolu_abc", "function": {"name": "create_tag", "arguments": "{}"}}]},
        {"role": "user", "content": "ok"},
    ]
    out = _sanitize_messages_for_llm(messages)
    assert len(out) == 3
    assert out[0] == {"role": "user", "content": "Create a tag"}
    assert out[1]["role"] == "assistant"
    assert "tool_calls" not in out[1]
    assert out[1]["content"] == "I'll create it."
    assert out[2] == {"role": "user", "content": "ok"}


def test_sanitize_messages_keeps_tool_calls_when_results_present():
    """When tool results exist immediately after assistant+tool_calls, keep the block."""
    messages = [
        {"role": "user", "content": "Create a tag"},
        {"role": "assistant", "content": "I'll create it.", "tool_calls": [{"id": "toolu_abc", "function": {"name": "create_tag", "arguments": "{}"}}]},
        {"role": "tool", "tool_call_id": "toolu_abc", "content": "Created."},
        {"role": "user", "content": "thanks"},
    ]
    out = _sanitize_messages_for_llm(messages)
    assert len(out) == 4
    assert out[1]["role"] == "assistant"
    assert out[1].get("tool_calls") is not None
    assert out[2] == {"role": "tool", "tool_call_id": "toolu_abc", "content": "Created."}
    assert out[3] == {"role": "user", "content": "thanks"}


@pytest.mark.asyncio
async def test_run_agent_approve_expired_turn():
    result = await run_agent_approve("nonexistent-turn-id", [])
    assert result.get("error") == "Turn expired or not found"


@pytest.mark.asyncio
async def test_session_set_get_clear():
    turn_id = generate_turn_id()
    set_turn_state(turn_id, {"foo": "bar"})
    state = get_turn_state(turn_id)
    assert state is not None
    assert state.get("foo") == "bar"
    clear_turn_state(turn_id)
    assert get_turn_state(turn_id) is None
