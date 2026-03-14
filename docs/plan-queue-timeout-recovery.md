# Bugfix Plan: Queue Timeout & Recovery for OCR/LLM Processing

## Problem Summary

When a worker crashes or restarts while processing a document, the queue message remains stuck in "processing" state forever. Additionally, LLM and OCR operations have no timeout, so they can hang indefinitely.

**Root causes identified:**
1. `litellm.acompletion()` has no `timeout` parameter (litellm's kwarg for request timeout)
2. Textract polling loop has no overall timeout
3. Queue `recv_msg()` only looks for `status: "pending"` - stuck "processing" messages are never reclaimed
4. No startup recovery for stuck messages

---

## Implementation Plan

### 1. Add Queue Visibility Timeout (Lease Pattern)

**File:** [queue.py](packages/python/analytiq_data/queue/queue.py)

Modify `recv_msg()` to reclaim stale "processing" messages (similar to webhook pattern in `dispatch.py:249-267`):

```python
# Add at top of file
import os
from datetime import timedelta

def _get_int_env(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except Exception:
        return default

QUEUE_VISIBILITY_TIMEOUT_SECS = _get_int_env("QUEUE_VISIBILITY_TIMEOUT_SECS", 900)  # 15 min
MAX_QUEUE_ATTEMPTS = _get_int_env("MAX_QUEUE_ATTEMPTS", 3)
```

**Changes to `recv_msg()` (lines 68-90):**
- Add `processing_started_at` timestamp when claiming
- Add `$or` query to also match stale "processing" messages
- Track `attempts` counter for max retry limit
- **Only claim messages where `attempts < MAX_QUEUE_ATTEMPTS`**

**Query shape:**
```python
{
    "$or": [
        {"status": "pending", "attempts": {"$lt": MAX_QUEUE_ATTEMPTS}},
        {
            "status": "processing",
            "processing_started_at": {"$lte": lease_cutoff},
            "attempts": {"$lt": MAX_QUEUE_ATTEMPTS}
        }
    ]
}
```

**Required indexes:** Create indexes on `queues.*` collections for efficient queries:
```javascript
db["queues.llm"].createIndex({ "status": 1, "created_at": 1 })
db["queues.llm"].createIndex({ "status": 1, "processing_started_at": 1, "attempts": 1 })
```

**Changes to `send_msg()` (lines 35-66):**
- Initialize `attempts: 0` in message document

**New function `recover_stale_messages()`:**
- Bulk reset stale messages to "pending" at worker startup
- **Idempotent:** Safe to call repeatedly; only touches stale processing items with `attempts < MAX_QUEUE_ATTEMPTS`
- Does NOT touch messages that have exhausted attempts (those need separate DLQ handling)

---

### 2. Add LLM Request Timeout

**File:** [llm.py](packages/python/analytiq_data/llm/llm.py)

Add timeout configuration:
```python
LLM_REQUEST_TIMEOUT_SECS = _get_int_env("LLM_REQUEST_TIMEOUT_SECS", 300)  # 5 min
```

**Modify `_litellm_acompletion_with_retry()` (lines 252-319):**
- Add `timeout` parameter to litellm params dict at line 292-301
- Use litellm's `timeout` kwarg (NOT `request_timeout`)

```python
params = {
    "model": model,
    "messages": messages_to_send,
    "api_key": api_key,
    "temperature": temperature,
    "timeout": LLM_REQUEST_TIMEOUT_SECS,  # litellm's timeout parameter
    # ... other params
}
```

**Modify `is_retryable_error()` (lines 196-229):**
- Explicitly handle `asyncio.TimeoutError` as retryable:
```python
if isinstance(exception, asyncio.TimeoutError):
    return True
```

**Timeout handling flow:**
1. `litellm.acompletion()` raises `asyncio.TimeoutError` on timeout
2. `is_retryable_error()` returns `True` → stamina retries
3. After stamina exhausts retries, exception propagates to message handler
4. Message handler catches exception → sets document to `*_FAILED` state
5. Log entry includes: document_id, prompt_revid, attempt count, timeout value

---

### 3. Add OCR Overall Timeout

**File:** [textract.py](packages/python/analytiq_data/aws/textract.py)

Add timeout configuration:
```python
OCR_TIMEOUT_SECS = _get_int_env("OCR_TIMEOUT_SECS", 600)  # 10 min
```

**Modify `run_textract()` (lines 16-133):**
- Add timeout check inside the polling loop (lines 84-96)
- Track elapsed time since start of polling
- Raise `asyncio.TimeoutError` if elapsed time exceeds limit

```python
start_time = asyncio.get_event_loop().time()

while True:
    elapsed = asyncio.get_event_loop().time() - start_time
    if elapsed > OCR_TIMEOUT_SECS:
        raise asyncio.TimeoutError(
            f"Textract job {job_id} timed out after {OCR_TIMEOUT_SECS}s"
        )
    # ... existing polling code
```

**Timeout handling flow:**
1. `run_textract()` raises `asyncio.TimeoutError`
2. Exception propagates to `process_ocr_msg()` handler
3. Handler catches exception → sets document to `OCR_FAILED`
4. S3 cleanup still executes in `finally` block
5. Log entry includes: document_id, job_id, elapsed time, timeout value

---

### 4. Handle Partial LLM Failures

**File:** [llm.py](packages/python/analytiq_data/llm/llm.py) - `run_llm_for_prompt_revids()`

- Wrap each prompt call with individual timeout
- Use `asyncio.gather(*tasks, return_exceptions=True)` to isolate failures
- Return list of results/exceptions

**File:** [msg_handlers/llm.py](packages/python/analytiq_data/msg_handlers/llm.py)

- Check results for exceptions after `run_llm_for_prompt_revids()`
- If all fail: set `LLM_FAILED`
- If partial fail: set `LLM_COMPLETED` but log warning (successful results are preserved)
- If all succeed: set `LLM_COMPLETED`

---

### 5. Worker Startup Recovery

**File:** [worker.py](packages/python/worker/worker.py)

Add startup recovery before launching worker tasks:
```python
async def recover_all_queues(analytiq_client):
    """
    Recover stale messages at worker startup.

    This function is idempotent and safe to call repeatedly.
    It only touches messages that:
    - Are in "processing" status
    - Have processing_started_at older than visibility timeout
    - Have attempts < MAX_QUEUE_ATTEMPTS

    Messages that have exhausted attempts are left in "processing"
    for separate DLQ handling.
    """
    for queue_name in ["ocr", "llm", "kb_index", "webhook"]:
        await ad.queue.recover_stale_messages(analytiq_client, queue_name)
```

Call in `main()` before `start_workers()`.

---

### 6. Dead Letter Queue: Behavior & Visibility

Messages that exceed `MAX_QUEUE_ATTEMPTS` are handled as follows:

**Behavior:**
1. `recv_msg()` will NOT claim messages with `attempts >= MAX_QUEUE_ATTEMPTS`
2. Message handlers check attempt count after catching errors
3. If `attempts >= MAX_QUEUE_ATTEMPTS`, handler calls `move_to_dlq()`
4. DLQ messages are NOT automatically reprocessed

**Where `move_to_dlq()` is invoked:**
- In message handlers (`process_ocr_msg`, `process_llm_msg`) after catching an exception
- After incrementing attempts and checking `>= MAX_QUEUE_ATTEMPTS`

**Add function to `queue.py`:**
```python
async def move_to_dlq(analytiq_client, queue_name: str, msg_id: str, error: str):
    """
    Move a failed message to dead letter state after max attempts.

    Dead letter messages should be inspected before reprocessing.
    See runbook: docs/operations/dead-letter-handling.md
    """
    db = analytiq_client.mongodb_async[analytiq_client.env]
    collection = db[get_queue_collection_name(queue_name)]

    await collection.update_one(
        {"_id": ObjectId(msg_id)},
        {"$set": {
            "status": "dead_letter",
            "failed_at": datetime.now(UTC),
            "last_error": error,
        }}
    )
    logger.warning(f"Message {msg_id} moved to dead letter: {error}")
```

**Viewing Dead Letter Messages:**

Via MongoDB shell or Compass:
```javascript
// View all dead letter messages in LLM queue
db["queues.llm"].find({ status: "dead_letter" })

// View all dead letter messages across all queues
db["queues.ocr"].find({ status: "dead_letter" })
db["queues.llm"].find({ status: "dead_letter" })
db["queues.kb_index"].find({ status: "dead_letter" })

// Get count of dead letter messages
db["queues.llm"].countDocuments({ status: "dead_letter" })

// Find dead letter messages for a specific document
db["queues.llm"].find({
    status: "dead_letter",
    "msg.document_id": "69b19d774c2066ff34283ee2"
})
```

**Reprocessing Dead Letter Messages:**

⚠️ **Caution:** Inspect messages before reprocessing. Understand why they failed.

```javascript
// Reprocess a dead letter message (resets attempts counter)
db["queues.llm"].updateOne(
    { _id: ObjectId("...") },
    { $set: { status: "pending", attempts: 0 }, $unset: { failed_at: "", last_error: "" } }
)
```

Note: Reprocessing resets `attempts` to 0, giving the message a fresh set of retries.

**Optional: Add API endpoint for dead letter visibility:**

```python
# In packages/python/app/routes/admin.py (new file or existing)
@router.get("/admin/queues/{queue_name}/dead-letter")
async def get_dead_letter_messages(queue_name: str, limit: int = 100):
    db = ad.common.get_async_db()
    collection = db[f"queues.{queue_name}"]
    cursor = collection.find({"status": "dead_letter"}).limit(limit)
    return await cursor.to_list(length=limit)
```

---

## Environment Variables

| Variable | Default | Scope | Description |
|----------|---------|-------|-------------|
| `LLM_REQUEST_TIMEOUT_SECS` | 300 | LLM | LLM API call timeout (5 min) |
| `OCR_TIMEOUT_SECS` | 600 | OCR | Textract overall timeout (10 min) |
| `QUEUE_VISIBILITY_TIMEOUT_SECS` | 900 | Queue | Stale message reclaim threshold (15 min) |
| `MAX_QUEUE_ATTEMPTS` | 3 | Queue | Max retries before dead-letter |

---

## Files to Modify

1. [packages/python/analytiq_data/queue/queue.py](packages/python/analytiq_data/queue/queue.py) - Visibility timeout + DLQ
2. [packages/python/analytiq_data/llm/llm.py](packages/python/analytiq_data/llm/llm.py) - LLM timeout + partial failures
3. [packages/python/analytiq_data/aws/textract.py](packages/python/analytiq_data/aws/textract.py) - OCR timeout
4. [packages/python/analytiq_data/msg_handlers/llm.py](packages/python/analytiq_data/msg_handlers/llm.py) - Handle partial results + DLQ
5. [packages/python/analytiq_data/msg_handlers/ocr.py](packages/python/analytiq_data/msg_handlers/ocr.py) - DLQ on max attempts
6. [packages/python/worker/worker.py](packages/python/worker/worker.py) - Startup recovery

---

## Unit Tests

**New test file:** [packages/python/tests/test_queue_timeout.py](packages/python/tests/test_queue_timeout.py)

All tests use pytest with async support and mock external dependencies (LLM API, Textract).

### Testing Strategy: Fast Mocked Timeouts

**Critical:** Tests must run quickly by mocking timeouts, NOT waiting for real timeouts. All tests complete in < 1s each.

```python
import pytest
import asyncio
from unittest.mock import patch, AsyncMock
from freezegun import freeze_time  # For time manipulation

# Pattern 1: Mock asyncio.wait_for to immediately raise TimeoutError
@pytest.fixture
def mock_timeout():
    """Make asyncio.wait_for immediately raise TimeoutError."""
    async def instant_timeout(coro, timeout):
        coro.close()  # Clean up the coroutine
        raise asyncio.TimeoutError(f"Mocked timeout after {timeout}s")

    with patch("asyncio.wait_for", side_effect=instant_timeout):
        yield

# Pattern 2: Mock litellm.acompletion to raise timeout immediately
@pytest.fixture
def mock_llm_timeout():
    """Mock LLM to timeout immediately (no real waiting)."""
    async def timeout_immediately(*args, **kwargs):
        raise asyncio.TimeoutError("LLM request timed out")

    with patch("litellm.acompletion", side_effect=timeout_immediately):
        yield

# Pattern 3: Use freezegun to manipulate time for visibility timeout tests
@freeze_time("2024-01-01 12:00:00")
async def test_stale_message_detection():
    # Insert message with processing_started_at = 20 minutes ago
    # No actual waiting - time is frozen/manipulated
    pass

# Pattern 4: Mock the polling function to simulate Textract timeout (no real sleeps)
@pytest.fixture
def mock_textract_timeout():
    """Mock Textract to simulate timeout without real waiting."""
    call_count = 0
    async def mock_get_status(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count > 2:  # Simulate timeout after 2 polls
            raise asyncio.TimeoutError("Textract polling timed out")
        return {"JobStatus": "IN_PROGRESS"}

    # Also mock asyncio.sleep to be instant
    with patch("asyncio.sleep", return_value=None):
        with patch("textract_client.get_document_analysis", side_effect=mock_get_status):
            yield

# Pattern 5: Override timeout constants for tests
@pytest.fixture(autouse=True)
def fast_timeouts(monkeypatch):
    """Override timeout constants to small values for testing."""
    monkeypatch.setenv("LLM_REQUEST_TIMEOUT_SECS", "1")
    monkeypatch.setenv("OCR_TIMEOUT_SECS", "1")
    monkeypatch.setenv("QUEUE_VISIBILITY_TIMEOUT_SECS", "1")
```

**Key Principles:**
1. **Never wait for real timeouts** - Mock `asyncio.wait_for`, `asyncio.sleep`, or the underlying call
2. **Use freezegun** for visibility timeout tests - manipulate `datetime.now()` instead of sleeping
3. **Mock at the lowest level** - Mock `litellm.acompletion` directly, not `run_llm()`
4. **All "after ~Xs" references use mocks** - wall-clock time is near-zero
5. **Helper functions that reference sleep times are used with mocks only**

### Test Categories

#### A. Queue Visibility Timeout Tests

```python
@pytest.fixture
def mock_analytiq_client():
    """Create a mock analytiq client with in-memory MongoDB-like behavior."""
    client = MagicMock()
    client.env = "test"
    client.mongodb_async = MagicMock()
    return client
```

**Test 1: `test_recv_msg_claims_pending_message`**
- **Scenario:** Normal case - pending message is claimed
- **Setup:** Insert message with `status: "pending"`, `attempts: 0`
- **Action:** Call `recv_msg()`
- **Assert:** Message status changes to "processing", `processing_started_at` is set, `attempts` incremented to 1
- **Corner case:** Verify FIFO order (oldest message claimed first)

**Test 2: `test_recv_msg_reclaims_stale_processing_message`**
- **Scenario:** Worker crashed, message stuck in "processing" past visibility timeout
- **Setup:** Use `freeze_time`, insert message with `processing_started_at` = 20 minutes before frozen time
- **Action:** Call `recv_msg()`
- **Assert:** Stale message is reclaimed, `processing_started_at` updated to frozen now, `attempts` incremented
- **Corner case:** Message 14 min old (within timeout) should NOT be reclaimed

**Test 3: `test_recv_msg_skips_max_attempts`**
- **Scenario:** Message has exceeded MAX_QUEUE_ATTEMPTS
- **Setup:** Insert stale message with `attempts: 3`
- **Action:** Call `recv_msg()`
- **Assert:** Message is NOT claimed (returns None) - left for DLQ handling
- **Corner case:** Message with `attempts: 2` SHOULD be reclaimed

**Test 4: `test_recv_msg_prefers_pending_over_stale`**
- **Scenario:** Both pending and stale messages exist
- **Setup:** Insert pending message (newer) and stale processing message (older)
- **Action:** Call `recv_msg()`
- **Assert:** Older message is claimed (FIFO by created_at)

**Test 5: `test_send_msg_initializes_attempts`**
- **Scenario:** New message should have attempts=0
- **Action:** Call `send_msg()` with test payload
- **Assert:** Message has `status: "pending"`, `attempts: 0`, `created_at` set

**Test 6: `test_recover_stale_messages_bulk_reset`**
- **Scenario:** Worker startup recovery
- **Setup:** Use `freeze_time`, insert 5 messages: 2 stale processing, 1 fresh processing, 2 pending
- **Action:** Call `recover_stale_messages()`
- **Assert:** Returns 2, only the 2 stale messages reset to "pending"

**Test 7: `test_recover_stale_messages_skips_max_attempts`**
- **Scenario:** Don't recover messages that exceeded max attempts
- **Setup:** Insert stale message with `attempts: 3`
- **Action:** Call `recover_stale_messages()`
- **Assert:** Returns 0, message NOT reset (left for DLQ)

**Test 8: `test_move_to_dlq`**
- **Scenario:** Message exceeds max attempts, moved to dead letter
- **Action:** Call `move_to_dlq()` with error message
- **Assert:** Status is "dead_letter", `failed_at` set, `last_error` contains error

**Test 9: `test_concurrent_recv_msg_no_duplicate_claims`**
- **Scenario:** Race condition - two workers try to claim same message
- **Setup:** Single pending message, mock MongoDB's atomic findOneAndUpdate
- **Action:** Call `recv_msg()` twice concurrently with `asyncio.gather()`
- **Assert:** One returns message, other returns None (atomic MongoDB operation)

---

#### B. LLM Timeout Tests

```python
@pytest.fixture
def mock_litellm():
    """Mock litellm.acompletion for testing."""
    with patch("analytiq_data.llm.llm.litellm.acompletion") as mock:
        yield mock
```

**Test 10: `test_llm_completion_with_timeout_success`**
- **Scenario:** LLM responds within timeout
- **Setup:** Mock `litellm.acompletion` to return immediately
- **Action:** Call `_litellm_acompletion_with_retry()`
- **Assert:** Returns successfully, `timeout` param passed to litellm

**Test 11: `test_llm_completion_timeout_raises_error`**
- **Scenario:** LLM exceeds timeout
- **Setup:** Mock `litellm.acompletion` to raise `asyncio.TimeoutError` immediately
- **Action:** Call function
- **Assert:** Raises `asyncio.TimeoutError`
- **Corner case:** Verify stamina retry is triggered (timeout is retryable)

**Test 12: `test_llm_timeout_is_retryable`**
- **Scenario:** Timeout should trigger retry via stamina
- **Setup:** Mock to raise timeout on first call, succeed on second (no real sleep)
- **Action:** Call `_litellm_acompletion_with_retry()`
- **Assert:** Returns successfully after retry, called twice

**Test 13: `test_is_retryable_error_handles_timeout`**
- **Scenario:** `is_retryable_error()` recognizes timeout exceptions
- **Action:** Call with `asyncio.TimeoutError("timeout")`
- **Assert:** Returns True
- **Corner cases:** Test with various timeout error message formats

---

#### C. OCR Timeout Tests

```python
@pytest.fixture
def mock_textract():
    """Mock AWS Textract client."""
    with patch("analytiq_data.aws.textract.ad.aws.get_aws_client_async") as mock:
        yield mock
```

**Test 14: `test_textract_completes_within_timeout`**
- **Scenario:** OCR job succeeds within timeout
- **Setup:** Mock Textract to return SUCCEEDED after 3 polls, mock `asyncio.sleep` to be instant
- **Action:** Call `run_textract()`
- **Assert:** Returns blocks, no timeout error

**Test 15: `test_textract_timeout_during_polling`**
- **Scenario:** OCR job hangs (IN_PROGRESS indefinitely), timeout triggered
- **Setup:** Mock Textract to always return IN_PROGRESS, mock time to advance past timeout
- **Action:** Call `run_textract()`
- **Assert:** Raises `asyncio.TimeoutError`
- **Corner case:** S3 cleanup still happens in finally block

**Test 16: `test_textract_timeout_with_elapsed_time`**
- **Scenario:** Elapsed time check works correctly
- **Setup:** Mock `asyncio.get_event_loop().time()` to return advancing values
- **Action:** Call `run_textract()`
- **Assert:** Raises timeout when mocked elapsed time exceeds limit

**Test 17: `test_textract_s3_cleanup_on_timeout`**
- **Scenario:** S3 object should be cleaned up even on timeout
- **Setup:** Mock Textract to raise timeout
- **Action:** Call `run_textract()`, catch TimeoutError
- **Assert:** `s3_client.delete_object` was called in finally block

---

#### D. Partial LLM Failure Tests

```python
@pytest.fixture
def mock_run_llm():
    """Mock individual run_llm calls."""
    with patch("analytiq_data.llm.llm.run_llm") as mock:
        yield mock
```

**Test 18: `test_run_llm_for_prompts_all_succeed`**
- **Scenario:** All prompts complete successfully
- **Setup:** 3 prompt_revids, mock all to return results immediately
- **Action:** Call `run_llm_for_prompt_revids()`
- **Assert:** Returns 3 results, no exceptions in list

**Test 19: `test_run_llm_for_prompts_one_timeout`**
- **Scenario:** One prompt times out, others succeed
- **Setup:** 3 prompt_revids, mock second to raise TimeoutError immediately
- **Action:** Call function
- **Assert:** Returns [result, TimeoutError, result], 2 successes preserved

**Test 20: `test_run_llm_for_prompts_all_fail`**
- **Scenario:** All prompts fail (various errors)
- **Setup:** Mock all 3 to raise different exceptions
- **Action:** Call `run_llm_for_prompt_revids()`
- **Assert:** Returns [Exception, Exception, Exception]

**Test 21: `test_run_llm_for_prompts_mixed_errors`**
- **Scenario:** Mix of timeout, API error, and success
- **Setup:** Prompt 1 succeeds, Prompt 2 raises TimeoutError, Prompt 3 raises APIError
- **Action:** Call function
- **Assert:** Returns [result, TimeoutError, APIError]
- **Corner case:** Successful result is NOT affected by sibling failures

**Test 22: `test_llm_msg_handler_partial_failure_state`**
- **Scenario:** Document state after partial failure
- **Setup:** Mock 2/3 prompts to fail
- **Action:** Call `process_llm_msg()`
- **Assert:** Document state is `LLM_COMPLETED` (not FAILED), warning logged
- **Corner case:** Webhook error event NOT sent for partial failure

**Test 23: `test_llm_msg_handler_all_fail_state`**
- **Scenario:** Document state when all prompts fail
- **Setup:** Mock all prompts to fail
- **Action:** Call `process_llm_msg()`
- **Assert:** Document state is `LLM_FAILED`, webhook error event sent

---

#### E. Message Handler Integration Tests

**Test 24: `test_ocr_msg_handler_timeout_sets_failed_state`**
- **Scenario:** OCR times out, document should be marked failed
- **Setup:** Mock `run_textract` to raise `asyncio.TimeoutError` immediately
- **Action:** Call `process_ocr_msg()`
- **Assert:** Document state is `OCR_FAILED`, message sent to `ocr_err` queue

**Test 25: `test_llm_msg_handler_timeout_sets_failed_state`**
- **Scenario:** All LLM calls time out
- **Setup:** Mock all `run_llm` calls to raise TimeoutError immediately
- **Action:** Call `process_llm_msg()`
- **Assert:** Document state is `LLM_FAILED`

**Test 26: `test_msg_deleted_after_timeout`**
- **Scenario:** Queue message is deleted even after timeout error
- **Setup:** Mock to raise timeout immediately
- **Action:** Call `process_llm_msg()`
- **Assert:** `delete_msg()` called (message not left in processing)

**Test 27: `test_msg_handler_moves_to_dlq_on_max_attempts`**
- **Scenario:** Message with attempts=2 fails again, should go to DLQ
- **Setup:** Message with `attempts: 2`, mock LLM to fail
- **Action:** Call `process_llm_msg()`
- **Assert:** `move_to_dlq()` called, message status is "dead_letter"

---

#### F. Worker Startup Recovery Tests

**Test 28: `test_recover_all_queues_at_startup`**
- **Scenario:** Worker startup calls recovery for all queues
- **Setup:** Use `freeze_time`, insert stale messages in ocr, llm, kb_index, webhook queues
- **Action:** Call `recover_all_queues()`
- **Assert:** All stale messages reset to pending

**Test 29: `test_recovery_handles_empty_queues`**
- **Scenario:** No stale messages to recover
- **Action:** Call `recover_all_queues()` on empty queues
- **Assert:** No errors, returns 0 for each queue

**Test 30: `test_recovery_handles_db_errors`**
- **Scenario:** MongoDB error during recovery
- **Setup:** Mock collection to raise exception
- **Action:** Call `recover_all_queues()`
- **Assert:** Error logged, other queues still attempted

**Test 31: `test_recovery_is_idempotent`**
- **Scenario:** Calling recovery multiple times is safe
- **Setup:** Insert 2 stale messages
- **Action:** Call `recover_all_queues()` twice
- **Assert:** First call resets 2, second call resets 0 (no duplicates)

---

#### G. Environment Variable Override Tests

**Test 32: `test_timeout_env_vars_override_defaults`**
- **Scenario:** Environment variables change timeout values
- **Setup:** Set `LLM_REQUEST_TIMEOUT_SECS=60`, `OCR_TIMEOUT_SECS=120`
- **Action:** Reload module or call `_get_int_env()`
- **Assert:** Values are 60 and 120 respectively

**Test 33: `test_invalid_env_var_uses_default`**
- **Scenario:** Invalid env var value (e.g., "abc")
- **Setup:** Set `MAX_QUEUE_ATTEMPTS=invalid`
- **Action:** Call `_get_int_env("MAX_QUEUE_ATTEMPTS", 3)`
- **Assert:** Returns default value 3

---

### Test Utilities

```python
from datetime import datetime, UTC, timedelta
from bson import ObjectId

# Helper to create mock messages
def create_mock_message(status="pending", attempts=0, created_minutes_ago=0, processing_minutes_ago=None):
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

# These helpers are used WITH MOCKS - no real waiting occurs
async def hang_forever():
    """Simulates a hang - only used with mocked asyncio.sleep."""
    await asyncio.sleep(3600)  # Mocked to be instant

async def delayed_response(delay_secs, return_value):
    """Simulates delayed response - only used with mocked asyncio.sleep."""
    await asyncio.sleep(delay_secs)  # Mocked to be instant
    return return_value
```

---

### Running Tests

```bash
# Run all timeout-related tests
. .venv/bin/activate
pytest packages/python/tests/test_queue_timeout.py -v

# Run with coverage
pytest packages/python/tests/test_queue_timeout.py --cov=analytiq_data.queue --cov=analytiq_data.llm --cov=analytiq_data.aws.textract

# Run specific test category
pytest packages/python/tests/test_queue_timeout.py -k "test_recv_msg" -v
pytest packages/python/tests/test_queue_timeout.py -k "test_llm_timeout" -v
pytest packages/python/tests/test_queue_timeout.py -k "test_textract" -v
```

---

## Verification

1. **Unit tests:** Run `pytest packages/python/tests/test_queue_timeout.py -v` - all tests should pass in < 30s total
2. **Regression:** Run existing tests: `. .venv/bin/activate; pytest -n auto packages/python/tests/`
3. **Manual test:** Kill worker mid-processing, verify message is reclaimed after visibility timeout
4. **Integration:** Process a document end-to-end, verify states transition correctly
5. **Dead letter check:** Verify messages with 3+ failures appear in dead_letter status
