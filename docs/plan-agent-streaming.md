## Plan: True Streaming for Document Agent

### Goals

- **True streaming** of:
  - Assistant text (token/chunk level) as it’s generated
  - Thinking/reasoning as it’s generated
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
    - `{ type: "done", final: FinalResult }`  
    - `FinalResult` ≈ current `result` dict (`text`, `thinking`, `executed_rounds`, `working_state`, `turn_id`, `tool_calls`).

- **Assistant text + thinking**
  - `type: "assistant_text_chunk"`  
    - `{ type, chunk, round_index }`
  - `type: "assistant_text_done"`  
    - `{ type, full_text, round_index }` (optional, for reconciliation)
  - `type: "thinking_chunk"` (optional, if provider exposes reasoning stream)  
    - `{ type, chunk, round_index }`
  - `type: "thinking_done"`  
    - `{ type, full_thinking, round_index }`

- **Tools / rounds**
  - `type: "tool_calls"` (LLM decided to call tools)  
    - `{ type, round_index, tool_calls: [{ id, name, arguments }] }`
  - `type: "tool_result"` (per tool or batched)  
    - `{ type, round_index, call_id, name, success, result?, preview?, error? }`  
      - `result` can contain the full tool output (e.g. structured JSON or text).
      - `preview` is an optional short summary for compact UI display.
  - `type: "round_executed"` (what is currently stored in `executed_rounds[i]`)  
    - `{ type, round_index, thinking, tool_calls }`

> **Note on `round_index`**: this is **0‑indexed** and increments once per LLM/tool round within a single turn.

---

### 2. Backend: Streaming Agent Loop

#### 2.1 APIs

Keep two paths:

- **Non‑streaming (current behavior)**  
  ```python
  async def run_agent_turn(..., auto_approve: bool, ...) -> dict:
      ...
  ```

- **Streaming orchestrator (new)**  
  ```python
  class AgentEvent(TypedDict, total=False):
      type: Literal[
          "assistant_text_chunk",
          "assistant_text_done",
          "thinking_chunk",
          "thinking_done",
          "tool_calls",
          "tool_result",
          "round_executed",
          "done",
          "error",
      ]
      # plus payload fields as per schema above

  async def stream_agent_turn(..., auto_approve: bool, ...) -> AsyncIterator[AgentEvent]:
      ...
  ```

#### 2.2 Per‑round behavior

For each agent round (bounded by a `MAX_TOOL_ROUNDS` limit):

1. **Call LLM with streaming**

   ```python
   async for delta in litellm.acompletion(..., stream=True):
       # content deltas
       if delta.choices[0].delta.content:
           text_delta = delta.choices[0].delta.content
           text_so_far += text_delta
           yield {"type": "assistant_text_chunk", "chunk": text_delta, "round_index": i}

       # reasoning / thinking deltas (if supported)
       if reasoning_delta:
           thinking_so_far += reasoning_delta
           yield {"type": "thinking_chunk", "chunk": reasoning_delta, "round_index": i}
   ```

   After the stream completes, we have the final assistant message with possible `tool_calls`.

2. **No tool calls (final answer)**  
   If `tool_calls == []`:

   ```python
   if text_so_far:
       yield {"type": "assistant_text_done", "full_text": text_so_far, "round_index": i}
   if thinking_so_far:
       yield {"type": "thinking_done", "full_thinking": thinking_so_far, "round_index": i}

   final_result = {
       "text": text_so_far,
       "thinking": thinking_so_far,
       "working_state": working_state,
       "executed_rounds": executed_rounds or None,
   }
   yield {"type": "done", "final": final_result}
   return
   ```

3. **Has tool calls**

   After streaming the LLM round:

   ```python
   if text_so_far:
       yield {"type": "assistant_text_done", "full_text": text_so_far, "round_index": i}
   if thinking_so_far:
       yield {"type": "thinking_done", "full_thinking": thinking_so_far, "round_index": i}

   pending = [_tool_call_to_dict(tc) for tc in tool_calls]
   yield {"type": "tool_calls", "round_index": i, "tool_calls": pending}
   ```

   - **Approval required (`auto_approve=False` + write tools)**:

     - Build `final_result`:

       ```python
       final_result = {
           "text": text_so_far,
           "thinking": thinking_so_far,
           "working_state": working_state,
           "tool_calls": pending,
           "turn_id": generated_turn_id,
       }
       yield {"type": "done", "final": final_result}
       return
       ```

     - State for `turn_id` is stored in the existing in‑memory session.

   - **Auto‑approved (`auto_approve=True` or tool in `auto_approved_tools`)**:

     - Execute each tool call:

       ```python
       for tc in pending:
           result_str = await execute_tool(...)
           yield {
               "type": "tool_result",
               "round_index": i,
               "call_id": tc["id"],
               "name": tc["name"],
               "success": True/False,
               "preview": result_preview,
               "error": error_message_if_any,
           }
       ```

     - Append to `executed_rounds`:

       ```python
       executed_rounds.append({"thinking": thinking_so_far, "tool_calls": pending})
       yield {
           "type": "round_executed",
           "round_index": i,
           "thinking": thinking_so_far,
           "tool_calls": pending,
       }
       ```

     - Add assistant+tool messages to `llm_messages` and continue loop to next round.

4. **Max rounds reached**

   After `MAX_TOOL_ROUNDS`:

   ```python
   final_result = {
       "text": "(Max tool rounds reached.)",
       "thinking": None,
       "working_state": working_state,
       "executed_rounds": executed_rounds or None,
   }
   yield {"type": "assistant_text_done", "full_text": final_result["text"], "round_index": i}
   yield {"type": "done", "final": final_result}
   return
   ```

5. **Approve path (`/chat/approve`)**

   - Similar structure, but:
     - First execute approved tools (no streaming).
     - Then run **one** streaming LLM round, emitting the same events as above.

---

### 3. Backend Routes: `/chat` and `/chat/approve`

#### 3.1 `/v0/orgs/{org}/documents/{doc}/chat`

- **Non‑streaming (`request.stream == False`)**  
  - Call `run_agent_turn(...)` as today.
  - Persist final assistant message + `executed_rounds` + `working_state` into the thread as currently implemented.

- **Streaming (`request.stream == True`)**

  ```python
  @agent_router.post("/v0/orgs/{organization_id}/documents/{document_id}/chat")
  async def post_chat(..., request: ChatRequest, ...):
      ...
      if request.stream:
          async def generate_sse():
              async for event in stream_agent_turn(...):
                  yield f"data: {json.dumps(event)}\n\n"
                  if event["type"] == "done" and event["final"].get("turn_id") is None:
                      # Persist final assistant message to thread here
          return StreamingResponse(generate_sse(), media_type="text/event-stream", ...)

      # Fallback non-streaming:
      result = await run_agent_turn(...)
      # Persist and return as JSON
  ```

#### 3.2 `/chat/approve`

- Same pattern:
  - `stream=False` → existing behavior with `run_agent_approve`.
  - `stream=True` → `stream_agent_approve` that:
    - Executes tools.
    - Streams one LLM round via events.
    - Emits `done` when complete; if `turn_id` still present, frontend will show new pending tool calls.

---

### 4. Frontend: `useAgentChat` Streaming v2

#### 4.1 Event handling

Extend the SSE consumer in `useAgentChat` to handle the richer event set:

- **Initialization**
  - On first event, append a placeholder assistant message:

    ```ts
    const placeholder: AgentChatMessage = {
      role: 'assistant',
      content: '',
      thinking: null,
      executedRounds: [],
      toolCalls: [],
    };
    ```

- **`assistant_text_chunk`**
  - Append `chunk` to `content` of the placeholder.

- **`assistant_text_done`**
  - Optionally reconcile `content` with `full_text`.

- **`thinking_chunk` / `thinking_done`**
  - Accumulate into `message.thinking` (already rendered via `ThinkingBlock` in `AgentMessage`).

- **`tool_calls`**
  - Update:
    - `pendingToolCalls` state (for approval UI).
    - `message.toolCalls` so the current assistant message shows pending tool cards.

- **`tool_result`**
  - Update status/preview for the matching tool card (e.g. mark as completed, show error).

- **`round_executed`**
  - Push/merge into `message.executedRounds` so each auto‑executed round appears live (existing `AgentMessage` already renders `executedRounds`).

- **`done`**
  - Use `final` payload to:
    - Reconcile `content`, `thinking`, `executedRounds`.
    - Update `extraction` from `final.working_state.extraction`.
    - Set `pendingTurnId` + `pendingToolCalls` if `final.turn_id` is present.
  - Clear `loading`.

- **`error`**
  - Show error, remove placeholder assistant message, clear `loading`.

#### 4.2 Approval flow

- When `done.final.turn_id` is present:
  - Treat as “pause for approval”:
    - Show current text + thinking.
    - Render pending tool cards from `final.tool_calls`.
    - Set `pendingTurnId` and `pendingToolCalls` as today.
  - Further streaming happens on `/chat/approve` when the user approves/rejects.

---

### 5. Migration & Phasing

1. **Phase 1 (current)**: Cosmetic stream of final text only (already implemented).
2. **Phase 2**: Switch LLM calls in the agent loop to use `stream=True`, emit:
   - `assistant_text_chunk`
   - `assistant_text_done` (plus `thinking_done` as a fallback if no thinking chunks)
   - `done` (no tool events yet, `/chat` only).
3. **Phase 3**: Add tool‑related events for `/chat`:
   - `tool_calls`, `tool_result`, `round_executed`
   - Wire them into `useAgentChat` and `AgentMessage` for the initial `/chat` turn.
4. **Phase 4**: Add streaming support to `/chat/approve` path with **identical event semantics** (including tool events) so approval responses stream in the same way as initial chat turns.

This yields **true, progressive streaming** for both the assistant’s reasoning and text, plus live visibility into each tool round while preserving the existing approval model and non‑streaming APIs.

---

### 6. Operational Considerations & Edge Cases

#### 6.1 Thinking streaming fallback

- Not all providers expose reasoning/“thinking” tokens in a streaming‑friendly way.
- Behavior:
  - If `thinking_chunk` events are emitted during the stream, they are used as‑is.
  - If no thinking deltas are available but the final message has `thinking`:
    - Emit a single `thinking_done` event with the full thinking content at the end of the round.

#### 6.2 Tool call assembly from streamed deltas

- OpenAI‑style streams may deliver tool_calls as partial JSON across multiple deltas.
- The agent loop must:
  - Accumulate raw tool_call deltas until the stream is finished.
  - Only after having a complete, valid list of tool_calls:
    - Construct the normalized `pending = [_tool_call_to_dict(...)]`.
    - Emit a single `tool_calls` event per round.

#### 6.3 Error handling during auto‑approve

- If a tool execution fails while `auto_approve=True`:
  - Emit a `tool_result` event with `success=False` and `error`.
  - Still append that tool call to `executed_rounds` with the error context.
  - Continue the loop and send the resulting tool messages to the LLM so it can self‑correct, unless:
    - The failure is systemic (e.g. SPU limit, auth), in which case:
      - Emit an `error` event and terminate the turn early.

#### 6.4 Cancellation / client abort

- Frontend already uses an `AbortController` for `/chat`.
- Backend behavior:
  - When the HTTP client closes the SSE connection (or aborts):
    - The FastAPI `StreamingResponse` generator should detect disconnect and stop iterating over `stream_agent_turn`.
    - The agent loop should be allowed to finish the *current* LLM call/tool execution but not start new rounds.
  - No `done` event is guaranteed on client‑initiated abort; frontend should:
    - Treat abrupt end‑of‑stream with no `done` as “canceled”.

#### 6.5 Thread persistence & reconnection

- Thread persistence:
  - Only when receiving a `done` event whose `final.turn_id is None` (no pending approval) do we persist the assistant message and `executed_rounds` to the thread.
  - For approval flows (`turn_id` present), persistence remains in `/chat/approve` as today.
- Reconnection:
  - If the SSE connection drops mid‑stream:
    - Frontend can re‑load the thread via existing `GET /chat/threads/{id}`.
    - The stored thread state reflects only *completed* turns; partial streaming state is not persisted.
    - UX: show partial assistant message as “canceled” and rely on the reloaded thread for authoritative history.

#### 6.6 Backpressure & chunking policy

- To avoid flooding slow clients:
  - Use *logical* chunks (e.g. small phrases or token groups) rather than single characters.
  - Optionally buffer and flush:
    - After N characters/tokens **or**
    - On a short timer (e.g. every 30–50ms), whichever comes first.
- The SSE queue in the route should either:
  - Be bounded (log a warning if overflow occurs), or
  - Drop older fine‑grained chunks in favor of newer ones in extreme cases (while still ultimately emitting `assistant_text_done` and `done`).

#### 6.7 Event ordering guarantees

- Within a **single round** (`round_index`), events must be emitted in a predictable order so the frontend can build a consistent view:

  1. `thinking_chunk`* (0 or more)
  2. `thinking_done` (if any thinking is present)
  3. `assistant_text_chunk`* (0 or more)
  4. `assistant_text_done` (if any text is present)
  5. `tool_calls` (if any)
  6. `tool_result`* (0 or more, for auto‑approved tools)
  7. `round_executed` (when auto‑approved and tools executed)

- `done` is emitted **after** the final round completes (or early on pause/error), and is unique per turn.

#### 6.8 Heartbeat / keepalive

- For long‑running tool executions or slow LLM responses, emit periodic SSE **comments** as heartbeats to avoid idle timeouts in proxies/load balancers:

  - Example heartbeat frame: `":keepalive\n\n"`
  - Emitted from the route generator when no data events have been sent for a configurable interval (e.g. 10–20 seconds).



