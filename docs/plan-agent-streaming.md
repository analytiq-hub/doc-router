## Plan: True Streaming for Document Agent

### Implementation Status (as of 2026-02-14)

**Phases 1–3 are implemented.** Phase 4 (streaming `/chat/approve`) is not yet started.

| Phase | Description | Status |
|-------|-------------|--------|
| Phase 1 | Cosmetic stream of final text only | Done |
| Phase 2 | True LLM streaming (`assistant_text_chunk`, `thinking_chunk`, `assistant_text_done`, `thinking_done`, `done`) | Done |
| Phase 3 | Tool-related events (`tool_calls`, `tool_result`, `round_executed`) for `/chat` | Done |
| Phase 4 | Streaming support for `/chat/approve` | Not started |

**Known bugs status (as of 2026-02-14):** 3 fixed (7.1, 7.2, 7.3), 1 partially fixed (7.7), 5 still open (7.4, 7.5, 7.6, 7.8, 7.9). See section 7 for details.

#### What is implemented

**Backend (`packages/python/analytiq_data/agent/`)**
- `agent_loop.py`: Single `run_agent_turn()` handles both streaming and non-streaming via an optional `stream_handler` callback. When `stream_handler` is provided, emits `assistant_text_chunk`, `thinking_chunk`, `assistant_text_done`, `thinking_done`, `tool_calls`, `tool_result`, `round_executed`, and `done` events. LLM streaming goes through `ad.llm.agent_completion_stream()`.
- `run_agent_approve()`: Non-streaming only. Executes tools, calls LLM once, returns JSON. Handles up to two additional LLM rounds for auto-approved follow-up tool calls.
- `session.py`: In-memory turn state store keyed by `turn_id` with 5-minute TTL. Used when backend pauses on pending tool calls.
- `system_prompt.py`: Builds system message with document context, OCR excerpt, resolved @mentions, current extraction, working state, and resource-link formatting instructions.
- `threads.py`: MongoDB persistence for chat threads (`agent_threads` collection). Supports list, get, create, append, truncate-and-append, update title, delete.
- `tool_registry.py`: 25 tools (13 read-only, 12 read-write). OpenAI function-calling format definitions + dispatch.
- `tools/`: Six tool modules — `document_tools`, `extraction_tools`, `schema_tools`, `prompt_tools`, `tag_tools`, `help_tools`.

**Backend routes (`packages/python/app/routes/agent.py`)**
- `POST /chat`: Supports `stream: true` (SSE via `StreamingResponse` + `asyncio.Queue`) and `stream: false` (JSON).
- `POST /chat/approve`: JSON only. Persists assistant message to thread.
- `GET /chat/tools`: Returns read-only and read-write tool lists.
- CRUD for threads: `GET/POST /chat/threads`, `GET/DELETE /chat/threads/{thread_id}`.

**Frontend (`packages/typescript/frontend/src/components/agent/`)**
- `useAgentChat.ts`: Main hook. SSE consumer in `runStreamingChat()` handles all event types. Thread management (create, load, delete, startNewChat). Auto-approved tools persisted in localStorage per org+doc. Custom event `agent-extraction-updated` dispatched on extraction changes.
- `AgentTab.tsx`: Top-level component with input area, model/tools dropdowns, thread dropdown, dictation.
- `AgentChat.tsx`: Renders conversation as turns (user + assistant groups). Sticky header with editable question for resubmit-from-turn. Approve all / reject all buttons.
- `AgentMessage.tsx`: Renders assistant messages with markdown (ReactMarkdown + remark-gfm), custom resource URI links (`schema_rev:`, `prompt:`, etc.), diff blocks, thinking blocks, tool call cards, executed rounds.
- `ToolCallCard.tsx`: Per-tool-call approve/reject/always-approve UI with expandable arguments.
- `ThinkingBlock.tsx`: Collapsible thinking/reasoning display with live timer.
- `ThreadDropdown.tsx`: Thread history dropdown with time grouping (today/yesterday/this week/older).
- `ExtractionPanel.tsx`: Collapsible JSON display of current extraction (defined but not wired into the UI).
- `useDictation.ts`: Web Speech API hook for voice input.

---

### Goals

- **True streaming** of:
  - Assistant text (token/chunk level) as it's generated
  - Thinking/reasoning as it's generated
  - Tool calls and tool results per round
  - Final summary (`executed_rounds`, `working_state`, etc.)
- Preserve existing approval model (pause vs auto‑approve).
- Keep non‑streaming API behavior working as today.

---

### 1. Event Schema (SSE Payloads)

All streaming uses a single SSE channel with JSON payloads that include a `type` field.

- **Conversation lifecycle**
  - `type: "error"`
    - `{ type, error }`
  - `type: "done"`
    - `{ type: "done", result: FinalResult }`
    - `FinalResult` ≈ current `result` dict (`text`, `thinking`, `executed_rounds`, `working_state`, `turn_id`, `tool_calls`).

- **Assistant text + thinking**
  - `type: "assistant_text_chunk"`
    - `{ type, chunk, round_index }`
  - `type: "assistant_text_done"`
    - `{ type, full_text, round_index }`
  - `type: "thinking_chunk"`
    - `{ type, chunk, round_index }`
  - `type: "thinking_done"`
    - `{ type, thinking, round_index }`

- **Tools / rounds**
  - `type: "tool_calls"` (LLM decided to call tools)
    - `{ type, round_index, tool_calls: [{ id, name, arguments }] }`
  - `type: "tool_result"` (per tool)
    - `{ type, round_index, call_id, name, success, result?, preview?, error? }`
  - `type: "round_executed"`
    - `{ type, round_index, thinking, tool_calls }`

> **Note on `round_index`**: this is **0‑indexed** and increments once per LLM/tool round within a single turn.

---

### 2. Backend: Streaming Agent Loop

#### 2.1 Architecture (implemented)

A single `run_agent_turn()` function handles both paths:

```python
async def run_agent_turn(
    ...,
    stream_handler: Optional[Callable[[str, Any], Awaitable[None]]] = None,
) -> dict:
```

- When `stream_handler` is `None`: non-streaming path, uses `ad.llm.agent_completion()`, returns JSON dict.
- When `stream_handler` is provided: streaming path, uses `ad.llm.agent_completion_stream()`, calls `stream_handler(event_type, payload)` for each event, returns final result dict.

The route creates an `asyncio.Queue`, wraps it in a `stream_handler` closure, and runs the agent turn in a background task. The SSE generator reads from the queue and yields `data:` frames.

#### 2.2 Per‑round behavior (implemented)

For each agent round (bounded by `MAX_TOOL_ROUNDS = 10`):

1. **Call LLM with streaming** via `ad.llm.agent_completion_stream()` which yields `(event_type, payload)` tuples for `"content"`, `"thinking"`, `"message"`, and `"usage"` events.

2. **No tool calls** → emit `thinking_done` (if thinking), `assistant_text_done`, `done`, return.

3. **Has tool calls + needs approval** → save turn state in-memory, return `turn_id` + `tool_calls` via `done` event.

4. **Has tool calls + auto-approved** → emit `tool_calls`, execute tools (emitting `tool_result` per tool via `on_tool_result` callback), emit `round_executed`, append to `llm_messages`, continue loop.

5. **Max rounds reached** → emit `assistant_text_done` with "(Max tool rounds reached.)", emit `done`.

---

### 3. Backend Routes: `/chat` and `/chat/approve`

#### 3.1 `POST /v0/orgs/{org}/documents/{doc}/chat` (implemented)

- **Non‑streaming (`stream=false`)**: Calls `run_agent_turn()` without `stream_handler`, returns JSON. Persists to thread via `_append_assistant_to_thread()`.
- **Streaming (`stream=true`)**: Creates `asyncio.Queue`, runs `run_agent_turn()` with queue-based `stream_handler` in a background task. SSE generator reads from queue, emits `data:` frames. On `done` event with no `turn_id`, persists to thread inline.

#### 3.2 `POST /chat/approve` (implemented, non-streaming only)

- Calls `run_agent_approve(turn_id, approvals)` which:
  1. Retrieves and clears in-memory turn state.
  2. Executes approved/rejected tools.
  3. Calls LLM once with tool results.
  4. If LLM returns more tool calls: applies same approval logic (up to one more auto-execute round).
- Persists assistant message to thread if `thread_id` provided.

#### 3.3 Other endpoints (implemented)

- `GET /chat/tools`: Returns `{ read_only: [...], read_write: [...] }`.
- `GET /chat/threads`: Lists threads for document+user, most recent first.
- `POST /chat/threads`: Creates new thread.
- `GET /chat/threads/{id}`: Gets thread with full messages and extraction.
- `DELETE /chat/threads/{id}`: Deletes thread.

---

### 4. Frontend: `useAgentChat` Streaming (implemented)

#### 4.1 Event handling

The SSE consumer in `runStreamingChat()` handles:

- **Initialization**: Appends placeholder `{ role: 'assistant', content: '', thinking: undefined, executedRounds: undefined }`.
- **`assistant_text_chunk`**: Appends `chunk` to placeholder's `content`.
- **`thinking_chunk`**: Appends `chunk` to placeholder's `thinking`.
- **`assistant_text_done`**: Reconciles `content` with `full_text`.
- **`thinking_done`**: Sets `thinking` on placeholder.
- **`tool_calls`**: Pushes new `ExecutedRound` with tool calls into `executedRounds`.
- **`round_executed`**: Merges thinking + tool_calls into existing round by index.
- **`done`**: Reconciles final `content`, `thinking`, `executedRounds`, `toolCalls`. Updates extraction from `working_state`. Sets `pendingTurnId` + `pendingToolCalls` if `turn_id` present. Refreshes thread list.
- **`error`**: Shows error, removes placeholder.

#### 4.2 Approval flow (implemented)

- `approveToolCalls()` POSTs to `/chat/approve` (non-streaming JSON).
- Response may include new `turn_id` + `tool_calls` (chains approvals).
- Updates extraction, dispatches `agent-extraction-updated` event.

#### 4.3 Thread management (implemented)

- Auto-creates thread on first message if none selected.
- `sendMessageWithHistory()` supports resubmit-from-turn with `truncate_thread_to_message_count`.
- Thread list refreshed after each completed turn.
- Auto-titles thread from first user message (first 50 chars).

---

### 5. Migration & Phasing

1. **Phase 1**: Cosmetic stream of final text only. **Done.**
2. **Phase 2**: True LLM streaming with `assistant_text_chunk`, `thinking_chunk`, `assistant_text_done`, `thinking_done`, `done`. **Done.**
3. **Phase 3**: Tool-related events (`tool_calls`, `tool_result`, `round_executed`) for `/chat`. **Done.**
4. **Phase 4**: Streaming support for `/chat/approve`. **Not started.**

---

### 6. Operational Considerations & Edge Cases

#### 6.1 Thinking streaming fallback

- Not all providers expose reasoning/"thinking" tokens in a streaming‑friendly way.
- Implemented behavior:
  - If `thinking_chunk` events are emitted during the stream, they are used as‑is.
  - If no thinking deltas are available but the final message has `thinking`:
    - Emit a single `thinking_done` event with the full thinking content at the end of the round.
  - `_should_use_thinking_param()` proactively skips the thinking parameter when the last assistant message has tool_calls but no thinking_blocks (avoids LiteLLM warning).
  - `_thinking_blocks_for_api()` only includes thinking blocks that have a valid `signature` (required by Anthropic).

#### 6.2 Tool call assembly from streamed deltas

- `ad.llm.agent_completion_stream()` accumulates tool call deltas internally and yields a complete `message` object with resolved `tool_calls` only after the stream finishes.
- The agent loop processes the complete tool_calls list as a batch.

#### 6.3 Error handling during auto‑approve

- If a tool execution fails:
  - `_execute_tool_calls()` catches the exception and returns `{"error": err_msg}` as the tool result content.
  - Emits `tool_result` with `success=False` and `error`.
  - The error is sent to the LLM as a tool result so it can self-correct.
- SPU limit errors terminate the turn early with `{"error": str(e)}`.

#### 6.4 Cancellation / client abort

- Frontend uses `AbortController` for the fetch request.
- `cancelRequest()` aborts the controller, sets `loading=false`, removes the pending user message if no response was received.
- Backend: the `generate_sse()` generator has a `finally` block that cancels the background task.

#### 6.5 Thread persistence & reconnection

- Persistence occurs only on `done` event where `turn_id is None` (no pending approval).
- For approval flows, persistence is in `post_chat_approve`.
- `_append_assistant_to_thread()` handles both append and truncate-and-append (for resubmit-from-turn).
- On reconnection, frontend loads thread via `GET /chat/threads/{id}`; partial streaming state is lost.

#### 6.6 Backpressure & chunking policy

- **Not yet implemented.** The SSE queue is unbounded (`asyncio.Queue()` with no maxsize).
- Heartbeat/keepalive not implemented.

#### 6.7 Event ordering guarantees

Within a single round (`round_index`), events are emitted in order:

1. `thinking_chunk`* (0 or more)
2. `assistant_text_chunk`* (0 or more) — note: thinking and text chunks may interleave depending on provider
3. `thinking_done` (if thinking present)
4. `assistant_text_done` (if text present)
5. `tool_calls` (if any)
6. `tool_result`* (0 or more, for auto‑approved tools)
7. `round_executed` (when auto‑approved and tools executed)

`done` is emitted after the final round completes (or early on pause/error).

#### 6.8 Heartbeat / keepalive

- **Not yet implemented.** Planned: emit `:keepalive\n\n` SSE comments when no data events for 10–20 seconds.

---

### 7. Known Bugs

#### 7.1 ~~BUG: In-memory session store doesn't scale and never GCs stale entries~~ (Fixed)
**File:** `packages/python/analytiq_data/agent/session.py:15`

~~`_store` is a module-level dict. Entries that are never fetched via `get_turn_state` are never cleaned up — they accumulate forever.~~

**Fixed (2026-02-14):** Lazy TTL-based eviction added — `get_turn_state` checks `_created_at` against `_TTL_SEC` (5 min) and deletes expired entries on read.

**Remaining concern:** GC is lazy (only on read), so entries never fetched accumulate until process restart. The in-memory store is still per-process, so multi-worker deployments (e.g. gunicorn) may route the approve call to a different worker. Consider Redis/MongoDB for cross-process state.

#### 7.2 ~~BUG: `handleApproveOne` inverts approval for all other tool calls~~ (Fixed)
**File:** `packages/typescript/frontend/src/components/agent/AgentChat.tsx:225-232`

~~When the user approves one tool call, every other pending tool call is set to `!approved` (i.e. rejected). The intended behavior is likely to only submit the clicked one, or to leave others as-is.~~

**Fixed (2026-02-14):** Changed `!approved` to `false` for non-clicked tool calls. When approving one, that one is approved and others are rejected. When rejecting one, that one is rejected and others are also rejected (no longer incorrectly approved).

#### 7.3 ~~BUG: `run_agent_approve` returns stale text after auto-executing follow-up tool calls~~ (Fixed)
**File:** `packages/python/analytiq_data/agent/agent_loop.py`

~~After the first LLM call in `run_agent_approve`, if the model returns more tool calls and they are all auto-approved, the code executes them but returns the text from *before* execution. The user sees the text from the LLM call that produced the tool calls, not a final summary of the tool results.~~

**Fixed (2026-02-14):** `run_agent_approve` now makes a second `agent_completion` call after executing auto-approved follow-up tool calls, returning fresh `text` and `thinking_text` from the final LLM response.

#### 7.4 BUG: `_sanitize_messages_for_llm` drops `thinking_blocks` field
**File:** `packages/python/analytiq_data/agent/agent_loop.py:93-141`

When reconstructing messages, the sanitizer only copies `role`, `content`, `tool_calls`, and `tool_call_id`. It drops `thinking_blocks` from assistant messages. Since `thinking_blocks` are required by the Anthropic API when continuing a conversation where thinking was present, this can cause API errors when reloading a thread.

#### 7.5 BUG: Redundant `tool_calls`/`text`/`thinking_text` recomputation after if/else block
**File:** `packages/python/analytiq_data/agent/agent_loop.py:442-444`

Lines 442-444 re-extract `tool_calls`, `text`, and `thinking_text` from `message` after the streaming/non-streaming if/else block. In the non-streaming path, the function already returned if there are no tool calls. These lines only execute in the streaming path where the values were already computed. Harmless but confusing — should be removed.

#### 7.6 BUG: `_tool_call_to_dict` has a redundant fallback
**File:** `packages/python/analytiq_data/agent/agent_loop.py:25`

```python
tid = getattr(tc, "id", None) or getattr(tc, "id", "")
```

Both `getattr` calls access the same attribute `"id"`. The second is redundant; should likely be `tc.get("id", "")` for the dict fallback.

#### 7.7 BUG: Thread `document_id` not validated on get/delete (Partially fixed)
**File:** `packages/python/app/routes/agent.py`, `packages/python/analytiq_data/agent/threads.py`

Route handlers for `get_thread` and `delete_thread` validate that the `document_id` exists, and queries are scoped by `organization_id` + `created_by`. However, the underlying `threads.get_thread` and `threads.delete_thread` functions do NOT include `document_id` in their MongoDB query filters. A user can access a thread from a different document within the same org if they know the `thread_id`.

**Fix:** Add `document_id` to the query filter in `get_thread` and `delete_thread` in `threads.py`.

#### 7.8 BUG: `_set_nested` doesn't handle `None` intermediate values
**File:** `packages/python/analytiq_data/agent/tools/extraction_tools.py:100-129`

When traversing a path like `items.0.amount`, if `items[0]` is `None` (appended as a placeholder), the code tries to index into `None`, causing a `TypeError` not caught by the `(ValueError, KeyError, IndexError)` handler.

**Fix:** Add `TypeError` and `AttributeError` to the except clause, or check for `None` during traversal.

#### 7.9 BUG: `_resolve_mentions` doesn't validate ObjectId format
**File:** `packages/python/app/routes/agent.py:87-127`

If a user sends a malformed mention ID, `ObjectId(mid)` throws `bson.errors.InvalidId`, resulting in a 500 error.

**Fix:** Wrap in try/except or validate format before calling `ObjectId()`.

---

### 8. Improvements

#### 8.1 No rate limiting on chat/approve endpoints
**File:** `packages/python/app/routes/agent.py`

No rate limiting. A user could rapidly fire requests and incur large LLM costs. Consider per-user or per-org rate limiting.

#### 8.2 Thread messages can grow unboundedly
**File:** `packages/python/analytiq_data/agent/threads.py:115-146`

`append_messages` uses `$push: {"$each": new_messages}` with no cap. A long conversation could exceed the 16MB BSON document limit. Consider capping messages per thread or paginating.

#### 8.3 No MongoDB index on `agent_threads` collection
**File:** `packages/python/analytiq_data/agent/threads.py:57-62`

`list_threads` queries by `{organization_id, document_id, created_by}` and sorts by `updated_at`. Without a compound index, this will be a collection scan on larger deployments. Add a migration with an appropriate index.

#### 8.4 `loadModels` has a stale closure over `model`
**File:** `packages/typescript/frontend/src/components/agent/useAgentChat.ts:702-714`

`loadModels` depends on `model` in its dependency array but also calls `setModel` conditionally. If `model` changes, the callback is recreated, which re-triggers any effect that depends on `loadModels`. Could cause redundant API calls.

#### 8.5 `sendMessage` captures stale `messages` in its closure
**File:** `packages/typescript/frontend/src/components/agent/useAgentChat.ts:518-573`

`sendMessage` has `messages` in its dependency array and builds `messageListForApi` from the captured `messages` value. If messages are being updated from a previous streaming response when `sendMessage` is called, the captured `messages` could be stale. Using a ref for messages would be safer.

#### 8.6 Approve endpoint doesn't support streaming
**File:** `packages/python/app/routes/agent.py:308-347`

`post_chat` supports `stream: true` for SSE, but `post_chat_approve` always returns JSON. If a tool call triggers a chain of auto-approved follow-ups, the user waits with no feedback. This is the Phase 4 gap.

#### 8.7 `delete_schema` checks all prompt revisions, not just latest
**File:** `packages/python/analytiq_data/agent/tools/schema_tools.py:229`

`delete_schema` queries `prompt_revisions` for any revision that references the schema. A schema can never be deleted if it was ever used by any prompt, even if the current revision no longer uses it.

**Fix:** Only check the latest revision per prompt_id.

#### 8.8 `create_schema` auto-versions when name matches (case-insensitive)
**File:** `packages/python/analytiq_data/agent/tools/schema_tools.py:74-80`

If the LLM picks a name matching an existing schema, it silently creates a new version rather than a separate schema. The user asks to "create" but gets a version bump. Consider making this explicit in the tool description or returning a warning.

#### 8.9 No test coverage for streaming path or thread persistence
**File:** `packages/python/tests/agent/test_agent_loop.py`

Tests cover the non-streaming path, session state, and helper functions. Missing coverage for:
- SSE streaming path (`stream_handler` usage)
- Thread creation/append on the approve endpoint
- `truncate_and_append_messages` flow
- End-to-end tool execution (tools are mocked at the LLM level)

#### 8.10 Private API `ad.llm._extract_thinking_from_response` usage
**File:** `packages/python/analytiq_data/agent/agent_loop.py:403`

The agent loop calls `ad.llm._extract_thinking_from_response(message)` — a private function. If the LLM module is refactored, this breaks silently. Make it a public API or move the logic into the agent module.

#### 8.11 `ExtractionPanel` component is unused
**File:** `packages/typescript/frontend/src/components/agent/ExtractionPanel.tsx`

`ExtractionPanel` is defined but not imported anywhere. The `extraction` state exists in `useAgentChat` but is never rendered. Either wire it up or remove.

#### 8.12 SSE queue is unbounded
**File:** `packages/python/app/routes/agent.py:207`

`asyncio.Queue()` has no maxsize. For long-running turns with many tool rounds, the queue could grow large if the client reads slowly. Consider bounding or implementing backpressure.
