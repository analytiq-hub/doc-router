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
    _record_spu_for_llm_call,
    _tool_auto_approved,
    _any_tool_needs_approval,
    _build_effective_approvals,
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
        m.MAX_SPU_PER_LLM_CALL = 50
        m.get_spu_cost = AsyncMock(return_value=1)
        m.check_spu_limits = AsyncMock()
        m.record_spu_usage = AsyncMock()
        m.compute_spu_to_charge = lambda actual_cost: 1  # Min 1 SPU per call
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
def mock_completion_cost():
    with patch("analytiq_data.agent.agent_loop.litellm.completion_cost", return_value=0.001) as m:
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
    mock_completion_cost,
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
    mock_completion_cost,
):
    msg = MagicMock()
    msg.content = "I will create a schema."
    tc = MagicMock()
    tc.id = "call_1"
    tc.function.name = "create_schema"
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
    assert result["tool_calls"][0]["name"] == "create_schema"


@pytest.mark.asyncio
async def test_run_agent_turn_read_only_tools_auto_approved(
    mock_analytiq_client,
    mock_payments,
    mock_llm_key,
    mock_llm_provider,
    mock_litellm,
    mock_build_system,
    mock_completion_cost,
):
    """Read-only tools (e.g. help_schemas) are auto-approved even when auto_approve=False."""
    msg = MagicMock()
    msg.content = "Here is schema help."
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
        messages=[{"role": "user", "content": "How do I create schemas?"}],
        model="gpt-4o-mini",
        auto_approve=False,
    )
    assert "error" not in result
    assert "turn_id" not in result
    assert result.get("text") == "(Max tool rounds reached.)"


@pytest.mark.asyncio
async def test_run_agent_turn_auto_approved_tools_whitelist_auto_approves(
    mock_analytiq_client,
    mock_payments,
    mock_llm_key,
    mock_llm_provider,
    mock_litellm,
    mock_build_system,
    mock_completion_cost,
):
    """Read-write tool in auto_approved_tools is auto-approved; no turn_id (executes without pause)."""
    msg = MagicMock()
    msg.content = "Creating schema."
    tc = MagicMock()
    tc.id = "call_1"
    tc.function.name = "create_schema"
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
        messages=[{"role": "user", "content": "Create a schema."}],
        model="gpt-4o-mini",
        auto_approve=False,
        auto_approved_tools={"create_schema"},
    )
    assert "error" not in result
    assert "turn_id" not in result
    assert result.get("text") == "(Max tool rounds reached.)"


@pytest.mark.asyncio
async def test_run_agent_turn_auto_approved_tools_partial_whitelist_pauses(
    mock_analytiq_client,
    mock_payments,
    mock_llm_key,
    mock_llm_provider,
    mock_litellm,
    mock_build_system,
    mock_completion_cost,
):
    """Read-write tool NOT in auto_approved_tools still pauses (create_tag whitelisted, create_schema not)."""
    msg = MagicMock()
    msg.content = "Creating schema."
    tc = MagicMock()
    tc.id = "call_1"
    tc.function.name = "create_schema"
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
        messages=[{"role": "user", "content": "Create a schema."}],
        model="gpt-4o-mini",
        auto_approve=False,
        auto_approved_tools={"create_tag"},
    )
    assert "error" not in result
    assert "turn_id" in result
    assert len(result.get("tool_calls", [])) == 1
    assert result["tool_calls"][0]["name"] == "create_schema"


@pytest.mark.asyncio
async def test_run_agent_turn_auto_approve_true_overrides_all(
    mock_analytiq_client,
    mock_payments,
    mock_llm_key,
    mock_llm_provider,
    mock_litellm,
    mock_build_system,
    mock_completion_cost,
):
    """When auto_approve=True, all read-write tools execute without pause regardless of auto_approved_tools."""
    msg = MagicMock()
    msg.content = "Creating schema."
    tc = MagicMock()
    tc.id = "call_1"
    tc.function.name = "create_schema"
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
        messages=[{"role": "user", "content": "Create a schema."}],
        model="gpt-4o-mini",
        auto_approve=True,
        auto_approved_tools=None,
    )
    assert "error" not in result
    assert "turn_id" not in result
    assert result.get("text") == "(Max tool rounds reached.)"


@pytest.mark.asyncio
async def test_run_agent_turn_auto_approved_tools_empty_set_pauses(
    mock_analytiq_client,
    mock_payments,
    mock_llm_key,
    mock_llm_provider,
    mock_litellm,
    mock_build_system,
    mock_completion_cost,
):
    """Empty auto_approved_tools set: no extra whitelist; read-write tools still require approval."""
    msg = MagicMock()
    msg.content = "Creating schema."
    tc = MagicMock()
    tc.id = "call_1"
    tc.function.name = "create_schema"
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
        messages=[{"role": "user", "content": "Create a schema."}],
        model="gpt-4o-mini",
        auto_approve=False,
        auto_approved_tools=set(),
    )
    assert "error" not in result
    assert "turn_id" in result
    assert result["tool_calls"][0]["name"] == "create_schema"


# --- Unit tests for tool permission helpers ---


def test_tool_auto_approved_read_only_always_true():
    """Read-only tools are always auto-approved regardless of auto_approve or auto_approved_tools."""
    for auto_approve in (True, False):
        for auto_approved in (None, set(), {"create_schema"}):
            assert _tool_auto_approved("help_schemas", auto_approve, auto_approved) is True
            assert _tool_auto_approved("get_ocr_text", auto_approve, auto_approved) is True
            assert _tool_auto_approved("list_tags", auto_approve, auto_approved) is True


def test_tool_auto_approved_read_write_when_auto_approve_true():
    """Read-write tools are auto-approved when auto_approve=True regardless of auto_approved_tools."""
    assert _tool_auto_approved("create_schema", True, None) is True
    assert _tool_auto_approved("create_schema", True, set()) is True
    assert _tool_auto_approved("create_tag", True, {"create_schema"}) is True
    assert _tool_auto_approved("delete_document", True, None) is True


def test_tool_auto_approved_read_write_when_auto_approve_false_no_whitelist():
    """Read-write tools require approval when auto_approve=False and auto_approved_tools is None or empty."""
    assert _tool_auto_approved("create_schema", False, None) is False
    assert _tool_auto_approved("create_tag", False, None) is False
    assert _tool_auto_approved("create_schema", False, set()) is False
    assert _tool_auto_approved("update_document", False, set()) is False


def test_tool_auto_approved_read_write_when_in_whitelist():
    """Read-write tools in auto_approved_tools are auto-approved when auto_approve=False."""
    whitelist = {"create_schema", "create_tag"}
    assert _tool_auto_approved("create_schema", False, whitelist) is True
    assert _tool_auto_approved("create_tag", False, whitelist) is True
    assert _tool_auto_approved("create_schema", False, {"create_schema"}) is True
    assert _tool_auto_approved("create_tag", False, {"create_tag"}) is True


def test_tool_auto_approved_read_write_when_not_in_whitelist():
    """Read-write tools not in auto_approved_tools still require approval when auto_approve=False."""
    assert _tool_auto_approved("create_prompt", False, {"create_schema"}) is False
    assert _tool_auto_approved("delete_document", False, {"create_tag"}) is False
    assert _tool_auto_approved("update_schema", False, {"create_schema"}) is False


def test_any_tool_needs_approval_all_read_only():
    """When all tools are read-only, none need approval."""
    pending = [
        {"id": "c1", "name": "help_schemas"},
        {"id": "c2", "name": "get_ocr_text"},
    ]
    assert _any_tool_needs_approval(pending, False, None) is False
    assert _any_tool_needs_approval(pending, False, set()) is False


def test_any_tool_needs_approval_read_write_no_approval():
    """When any read-write tool is not auto-approved, approval is needed."""
    pending = [{"id": "c1", "name": "create_schema"}]
    assert _any_tool_needs_approval(pending, False, None) is True
    assert _any_tool_needs_approval(pending, False, set()) is True
    assert _any_tool_needs_approval(pending, False, {"create_tag"}) is True


def test_any_tool_needs_approval_all_auto_approved():
    """When auto_approve=True or all tools in whitelist, no approval needed."""
    pending = [{"id": "c1", "name": "create_schema"}]
    assert _any_tool_needs_approval(pending, True, None) is False
    assert _any_tool_needs_approval(pending, False, {"create_schema"}) is False


def test_any_tool_needs_approval_mixed():
    """Mixed read-only + read-write: approval needed if any read-write not approved."""
    pending = [
        {"id": "c1", "name": "help_schemas"},
        {"id": "c2", "name": "create_schema"},
    ]
    assert _any_tool_needs_approval(pending, False, None) is True
    assert _any_tool_needs_approval(pending, False, {"create_schema"}) is False
    assert _any_tool_needs_approval(pending, False, {"create_tag"}) is True


def test_any_tool_needs_approval_multiple_read_write():
    """Multiple read-write tools: approval needed if any one is not approved."""
    pending = [
        {"id": "c1", "name": "create_schema"},
        {"id": "c2", "name": "create_tag"},
    ]
    assert _any_tool_needs_approval(pending, False, None) is True
    assert _any_tool_needs_approval(pending, False, {"create_schema"}) is True  # create_tag not in
    assert _any_tool_needs_approval(pending, False, {"create_schema", "create_tag"}) is False


def test_build_effective_approvals():
    """_build_effective_approvals returns correct approved flag per call_id."""
    pending = [
        {"id": "call_1", "name": "help_schemas"},
        {"id": "call_2", "name": "create_schema"},
    ]
    out = _build_effective_approvals(pending, False, None)
    assert out == {"call_1": True, "call_2": False}

    out = _build_effective_approvals(pending, False, {"create_schema"})
    assert out == {"call_1": True, "call_2": True}

    out = _build_effective_approvals(pending, True, None)
    assert out == {"call_1": True, "call_2": True}


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


# --- Tests for _record_spu_for_llm_call ---


@pytest.mark.asyncio
async def test_record_spu_extracts_tokens_and_records():
    """_record_spu_for_llm_call extracts usage and calls record_spu_usage with correct args."""
    response = MagicMock()
    response.usage = MagicMock(prompt_tokens=100, completion_tokens=50, total_tokens=150)

    with patch("analytiq_data.agent.agent_loop.litellm.completion_cost", return_value=0.01):
        with patch("analytiq_data.agent.agent_loop.ad.payments") as m:
            m.compute_spu_to_charge = lambda cost: 2
            m.record_spu_usage = AsyncMock()

            await _record_spu_for_llm_call(response, "org1", "anthropic", "claude-3")

            m.record_spu_usage.assert_called_once()
            call = m.record_spu_usage.call_args
            assert call[0][0] == "org1"
            assert call[0][1] == 2
            assert call[1]["prompt_tokens"] == 100
            assert call[1]["completion_tokens"] == 50
            assert call[1]["total_tokens"] == 150
            assert call[1]["actual_cost"] == 0.01


@pytest.mark.asyncio
async def test_record_spu_uses_total_tokens_when_available():
    """When usage.total_tokens is present, use it instead of prompt+completion."""
    response = MagicMock()
    response.usage = MagicMock(prompt_tokens=100, completion_tokens=50, total_tokens=200)

    with patch("analytiq_data.agent.agent_loop.litellm.completion_cost", return_value=0.01):
        with patch("analytiq_data.agent.agent_loop.ad.payments") as m:
            m.compute_spu_to_charge = lambda cost: 1
            m.record_spu_usage = AsyncMock()

            await _record_spu_for_llm_call(response, "org1", "openai", "gpt-4")

            call = m.record_spu_usage.call_args
            assert call[1]["total_tokens"] == 200


@pytest.mark.asyncio
async def test_record_spu_handles_missing_usage():
    """When response has no usage, does not raise; charges min SPU, tokens=0."""
    response = MagicMock()
    response.usage = None  # No usage attr or None

    with patch("analytiq_data.agent.agent_loop.litellm.completion_cost", return_value=0.0):
        with patch("analytiq_data.agent.agent_loop.ad.payments") as m:
            m.compute_spu_to_charge = lambda cost: 1
            m.record_spu_usage = AsyncMock()

            await _record_spu_for_llm_call(response, "org1", "openai", "gpt-4")

            m.record_spu_usage.assert_called_once()
            assert m.record_spu_usage.call_args[1]["prompt_tokens"] == 0
            assert m.record_spu_usage.call_args[1]["completion_tokens"] == 0


@pytest.mark.asyncio
async def test_record_spu_survives_record_spu_usage_failure():
    """When record_spu_usage raises, _record_spu_for_llm_call does not propagate."""
    response = MagicMock()
    response.usage = MagicMock(prompt_tokens=10, completion_tokens=5, total_tokens=15)

    with patch("analytiq_data.agent.agent_loop.litellm.completion_cost", return_value=0.01):
        with patch("analytiq_data.agent.agent_loop.ad.payments") as m:
            m.compute_spu_to_charge = lambda cost: 1
            m.record_spu_usage = AsyncMock(side_effect=Exception("DB error"))

            await _record_spu_for_llm_call(response, "org1", "openai", "gpt-4")
            # No exception raised


@pytest.mark.asyncio
async def test_record_spu_survives_completion_cost_failure():
    """When litellm.completion_cost raises, _record_spu_for_llm_call does not propagate."""
    response = MagicMock()
    response.usage = MagicMock(prompt_tokens=10, completion_tokens=5)

    with patch("analytiq_data.agent.agent_loop.litellm.completion_cost", side_effect=ValueError("Unknown model")):
        with patch("analytiq_data.agent.agent_loop.ad.payments") as m:
            m.compute_spu_to_charge = lambda cost: 1
            m.record_spu_usage = AsyncMock()

            await _record_spu_for_llm_call(response, "org1", "openai", "gpt-4")
            # No exception raised
