import asyncio
from datetime import datetime, UTC, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from bson import ObjectId

import analytiq_data as ad
from analytiq_data.queue import queue as queue_mod
from analytiq_data.llm import llm as llm_mod
from analytiq_data.aws import textract as textract_mod


def create_mock_message(
    status: str = "pending",
    attempts: int = 0,
    created_minutes_ago: int = 0,
    processing_minutes_ago: int | None = None,
):
    msg = {
        "_id": ObjectId(),
        "status": status,
        "attempts": attempts,
        "created_at": datetime.now(UTC) - timedelta(minutes=created_minutes_ago),
        "msg": {"document_id": str(ObjectId())},
    }
    if processing_minutes_ago is not None:
        msg["processing_started_at"] = datetime.now(UTC) - timedelta(minutes=processing_minutes_ago)
    return msg


@pytest.fixture(autouse=True)
def fast_timeouts(monkeypatch):
    """Override timeout-related env vars so code picks small values (logic is still mocked)."""
    monkeypatch.setenv("LLM_REQUEST_TIMEOUT_SECS", "1")
    monkeypatch.setenv("OCR_TIMEOUT_SECS", "1")
    monkeypatch.setenv("QUEUE_VISIBILITY_TIMEOUT_SECS", "1")
    # Reload modules that read env at import time
    import importlib

    importlib.reload(queue_mod)
    importlib.reload(llm_mod)
    importlib.reload(textract_mod)
    yield


@pytest.fixture
def mock_analytiq_client():
    client = MagicMock()
    client.env = "test"
    client.mongodb_async = MagicMock()
    return client


@pytest.mark.asyncio
async def test_recv_msg_claims_pending_message(mock_analytiq_client):
    """Normal case - pending message is claimed and marked processing with attempts incremented."""
    coll = MagicMock()
    mock_analytiq_client.mongodb_async.__getitem__.return_value = {"queues.llm": coll}
    msg = create_mock_message(status="pending", attempts=0)
    coll.find_one_and_update = AsyncMock(return_value=msg)

    result = await queue_mod.recv_msg(mock_analytiq_client, "llm")

    assert result is msg
    coll.find_one_and_update.assert_awaited()
    args, kwargs = coll.find_one_and_update.call_args
    query = args[0]
    assert query["$or"][0]["status"] == "pending"


@pytest.mark.asyncio
async def test_recv_msg_reclaims_stale_processing_message(mock_analytiq_client):
    """Worker crashed, message stuck in processing past visibility timeout."""
    coll = MagicMock()
    mock_analytiq_client.mongodb_async.__getitem__.return_value = {"queues.ocr": coll}
    msg = create_mock_message(status="processing", attempts=1, processing_minutes_ago=20)
    coll.find_one_and_update = AsyncMock(return_value=msg)

    result = await queue_mod.recv_msg(mock_analytiq_client, "ocr")

    assert result is msg
    coll.find_one_and_update.assert_awaited()


@pytest.mark.asyncio
async def test_recv_msg_skips_max_attempts(mock_analytiq_client):
    """Messages at or above MAX_QUEUE_ATTEMPTS are not claimed (left for DLQ)."""
    coll = MagicMock()
    mock_analytiq_client.mongodb_async.__getitem__.return_value = {"queues.llm": coll}
    coll.find_one_and_update = AsyncMock(return_value=None)

    result = await queue_mod.recv_msg(mock_analytiq_client, "llm")

    assert result is None
    coll.find_one_and_update.assert_awaited()
    args, kwargs = coll.find_one_and_update.call_args
    query = args[0]
    # Ensure attempts filter is present in both branches
    for branch in query["$or"]:
        assert branch["attempts"]["$lt"] == queue_mod.MAX_QUEUE_ATTEMPTS


@pytest.mark.asyncio
async def test_recover_stale_messages_bulk_reset(mock_analytiq_client):
    """recover_stale_messages bulk-resets only stale processing messages."""
    coll = MagicMock()
    mock_analytiq_client.mongodb_async.__getitem__.return_value = {"queues.ocr": coll}
    coll.update_many = AsyncMock()
    coll.update_many.return_value.modified_count = 2

    recovered = await queue_mod.recover_stale_messages(mock_analytiq_client, "ocr")

    assert recovered == 2
    coll.update_many.assert_awaited()


@pytest.mark.asyncio
async def test_move_to_dlq_sets_dead_letter(mock_analytiq_client):
    """move_to_dlq marks message as dead_letter with error metadata."""
    coll = MagicMock()
    mock_analytiq_client.mongodb_async.__getitem__.return_value = {"queues.llm": coll}
    coll.update_one = AsyncMock()
    msg_id = str(ObjectId())

    await queue_mod.move_to_dlq(mock_analytiq_client, "llm", msg_id, "boom")

    coll.update_one.assert_awaited()
    args, kwargs = coll.update_one.call_args
    update = args[1]
    assert update["$set"]["status"] == "dead_letter"
    assert "failed_at" in update["$set"]
    assert update["$set"]["last_error"] == "boom"


@pytest.fixture
def mock_litellm():
    with patch("analytiq_data.llm.llm.litellm.acompletion") as mock:
        yield mock


@pytest.mark.asyncio
async def test_llm_completion_with_timeout_success(mock_litellm):
    """LLM responds within timeout and timeout param is passed to litellm."""
    class Resp:
        def __init__(self):
            self.choices = [type("C", (), {"message": type("M", (), {"content": "{}"})()})()]
            self.usage = type("U", (), {"prompt_tokens": 1, "completion_tokens": 1})()

    mock_litellm.return_value = Resp()

    resp = await llm_mod._litellm_acompletion_with_retry(
        analytiq_client=None,
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": "hi"}],
        api_key="test",
    )

    assert resp is not None
    kwargs = mock_litellm.call_args.kwargs
    assert kwargs["timeout"] == llm_mod.LLM_REQUEST_TIMEOUT_SECS


@pytest.mark.asyncio
async def test_is_retryable_error_handles_timeout():
    """TimeoutError is treated as retryable by is_retryable_error."""
    exc = asyncio.TimeoutError("timeout")
    assert llm_mod.is_retryable_error(exc) is True


@pytest.mark.asyncio
async def test_run_llm_for_prompts_partial_failures(monkeypatch):
    """run_llm_for_prompt_revids returns list with results and exceptions."""
    async def ok(*args, **kwargs):
        return {"ok": True}

    async def fail(*args, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(llm_mod, "run_llm", ok)
    # For second prompt override to fail
    call_count = {"n": 0}

    async def run_llm_side_effect(*args, **kwargs):
        call_count["n"] += 1
        if call_count["n"] == 2:
            return await fail()
        return await ok()

    monkeypatch.setattr(llm_mod, "run_llm", run_llm_side_effect)

    results = await llm_mod.run_llm_for_prompt_revids(
        analytiq_client=MagicMock(),
        document_id="doc1",
        prompt_revids=["p1", "p2", "p3"],
    )

    assert len(results) == 3
    assert sum(1 for r in results if isinstance(r, Exception)) == 1


@pytest.mark.asyncio
async def test_textract_timeout_raises_timeout_error(monkeypatch):
    """run_textract raises asyncio.TimeoutError when elapsed time exceeds OCR_TIMEOUT_SECS."""
    aws_client = MagicMock()

    class FakeCtx:
        def __init__(self, inner):
            self._inner = inner

        async def __aenter__(self):
            return self._inner

        async def __aexit__(self, exc_type, exc, tb):
            return False

    textract_client = MagicMock()
    textract_client.start_document_text_detection = AsyncMock(
        return_value={"JobId": "job-1"}
    )

    # Always report IN_PROGRESS so timeout logic is exercised
    textract_client.get_document_text_detection = AsyncMock(
        return_value={"JobStatus": "IN_PROGRESS"}
    )

    # s3 client also needs async methods
    s3_client = MagicMock()
    s3_client.put_object = AsyncMock(return_value=None)
    s3_client.delete_object = AsyncMock(return_value=None)

    aws_client.client.side_effect = lambda name: FakeCtx(
        s3_client if name == "s3" else textract_client
    )

    monkeypatch.setattr(ad.aws, "get_aws_client_async", AsyncMock(return_value=aws_client))

    # Mock loop.time() to jump past timeout immediately
    class FakeLoop:
        def __init__(self):
            self._first = True

        def time(self):
            if self._first:
                self._first = False
                return 0.0
            return textract_mod.OCR_TIMEOUT_SECS + 1.0

    monkeypatch.setattr(asyncio, "get_event_loop", lambda: FakeLoop())

    with pytest.raises(asyncio.TimeoutError):
        await textract_mod.run_textract(MagicMock(), b"blob")


@pytest.mark.asyncio
async def test_send_msg_initializes_attempts(mock_analytiq_client):
    """send_msg creates a message with attempts=0 and status=pending."""
    coll = MagicMock()
    mock_analytiq_client.mongodb_async.__getitem__.return_value = {"queues.llm": coll}

    class InsertResult:
        inserted_id = ObjectId()

    coll.insert_one = AsyncMock(return_value=InsertResult())

    await queue_mod.send_msg(mock_analytiq_client, "llm", msg={"document_id": "doc1"})

    coll.insert_one.assert_awaited()
    args, kwargs = coll.insert_one.call_args
    msg_data = args[0]
    assert msg_data["status"] == "pending"
    assert msg_data["attempts"] == 0
    assert "created_at" in msg_data
    assert msg_data["msg"]["document_id"] == "doc1"


@pytest.mark.asyncio
async def test_concurrent_recv_msg_no_duplicate_claims(mock_analytiq_client):
    """Two concurrent recv_msg calls should not claim the same message (atomic operation)."""
    coll = MagicMock()
    mock_analytiq_client.mongodb_async.__getitem__.return_value = {"queues.llm": coll}

    msg = create_mock_message(status="pending", attempts=0)
    call_count = {"n": 0}

    async def atomic_find_one_and_update(*args, **kwargs):
        """Simulate MongoDB atomic behavior - only first caller gets the message."""
        call_count["n"] += 1
        if call_count["n"] == 1:
            return msg
        return None  # Second caller finds nothing (message already claimed)

    coll.find_one_and_update = AsyncMock(side_effect=atomic_find_one_and_update)

    results = await asyncio.gather(
        queue_mod.recv_msg(mock_analytiq_client, "llm"),
        queue_mod.recv_msg(mock_analytiq_client, "llm"),
    )

    # Exactly one should get the message, the other should get None
    non_none = [r for r in results if r is not None]
    assert len(non_none) == 1
    assert non_none[0] is msg


@pytest.mark.asyncio
async def test_recover_stale_messages_skips_max_attempts(mock_analytiq_client):
    """recover_stale_messages does NOT reset messages that exceeded max attempts."""
    coll = MagicMock()
    mock_analytiq_client.mongodb_async.__getitem__.return_value = {"queues.llm": coll}
    coll.update_many = AsyncMock()
    coll.update_many.return_value.modified_count = 0

    recovered = await queue_mod.recover_stale_messages(mock_analytiq_client, "llm")

    assert recovered == 0
    coll.update_many.assert_awaited()
    args, kwargs = coll.update_many.call_args
    query = args[0]
    # Verify the query includes attempts < MAX_QUEUE_ATTEMPTS filter
    assert query["attempts"]["$lt"] == queue_mod.MAX_QUEUE_ATTEMPTS


@pytest.mark.asyncio
async def test_recovery_is_idempotent(mock_analytiq_client):
    """Calling recover_stale_messages multiple times is safe and idempotent."""
    coll = MagicMock()
    mock_analytiq_client.mongodb_async.__getitem__.return_value = {"queues.ocr": coll}

    # First call resets 2 messages
    result1 = MagicMock()
    result1.modified_count = 2
    # Second call resets 0 (messages already reset)
    result2 = MagicMock()
    result2.modified_count = 0
    coll.update_many = AsyncMock(side_effect=[result1, result2])

    # First recovery
    recovered1 = await queue_mod.recover_stale_messages(mock_analytiq_client, "ocr")
    assert recovered1 == 2

    # Second recovery - should be safe and return 0
    recovered2 = await queue_mod.recover_stale_messages(mock_analytiq_client, "ocr")
    assert recovered2 == 0


def test_get_int_env_returns_default_for_invalid_value(monkeypatch):
    """_get_int_env returns default when env var is invalid (non-integer)."""
    monkeypatch.setenv("TEST_INT_VAR", "not_a_number")
    result = queue_mod._get_int_env("TEST_INT_VAR", 42)
    assert result == 42


def test_get_int_env_returns_env_value_when_valid(monkeypatch):
    """_get_int_env returns parsed int when env var is valid."""
    monkeypatch.setenv("TEST_INT_VAR", "100")
    result = queue_mod._get_int_env("TEST_INT_VAR", 42)
    assert result == 100


def test_get_int_env_returns_default_when_missing():
    """_get_int_env returns default when env var is not set."""
    import os
    # Ensure variable is not set
    os.environ.pop("NONEXISTENT_VAR", None)
    result = queue_mod._get_int_env("NONEXISTENT_VAR", 99)
    assert result == 99


@pytest.mark.asyncio
async def test_delete_msg_deletes_message(mock_analytiq_client):
    """delete_msg removes the message from the queue."""
    coll = MagicMock()
    mock_analytiq_client.mongodb_async.__getitem__.return_value = {"queues.llm": coll}
    coll.delete_one = AsyncMock()
    msg_id = str(ObjectId())

    await queue_mod.delete_msg(mock_analytiq_client, "llm", msg_id)

    coll.delete_one.assert_awaited()
    args, kwargs = coll.delete_one.call_args
    query = args[0]
    assert query["_id"] == ObjectId(msg_id)


@pytest.mark.asyncio
async def test_run_llm_for_prompts_all_succeed(monkeypatch):
    """run_llm_for_prompt_revids returns all successful results when no failures."""
    async def ok(*args, **kwargs):
        return {"success": True, "prompt_revid": kwargs.get("prompt_revid", "unknown")}

    monkeypatch.setattr(llm_mod, "run_llm", ok)

    results = await llm_mod.run_llm_for_prompt_revids(
        analytiq_client=MagicMock(),
        document_id="doc1",
        prompt_revids=["p1", "p2", "p3"],
    )

    assert len(results) == 3
    assert all(isinstance(r, dict) for r in results)
    assert all(r["success"] for r in results)


@pytest.mark.asyncio
async def test_run_llm_for_prompts_all_fail(monkeypatch):
    """run_llm_for_prompt_revids returns all exceptions when all fail."""
    async def fail(*args, **kwargs):
        raise RuntimeError("LLM error")

    monkeypatch.setattr(llm_mod, "run_llm", fail)

    results = await llm_mod.run_llm_for_prompt_revids(
        analytiq_client=MagicMock(),
        document_id="doc1",
        prompt_revids=["p1", "p2", "p3"],
    )

    assert len(results) == 3
    assert all(isinstance(r, Exception) for r in results)

