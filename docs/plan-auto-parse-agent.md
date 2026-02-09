# Plan: Document Chat Agent with Tool Permissions

## Goals

- **Document agent chat**: A Claude Code-like chat interface on the document page where the user can create, edit, and run schemas and prompts by conversing with an LLM agent that has tools.
- **@ mentions**: Reference existing schemas, prompts, and tags by typing `@` in the chat input, with autocomplete. The agent sees the full content of referenced artifacts.
- **Tool permissions**: The agent proposes actions (create schema, update prompt, run extraction, etc.) and the user approves or rejects each one — like Claude Code's permission model. Users can also enable auto-approve.
- **Auto-create on upload**: On document upload, the agent runs headlessly (all tools auto-approved) to propose a schema, prompt, and extraction. Results are stored as "proposed" for the user to review and refine via chat.

---

## 1. Chat Tab on the Document Page

**Current layout** (`/orgs/[orgId]/docs/[id]`):

- **Left panel (PDFSidebar)**: Tabs **Extraction** | **Forms**.
- **Right panel**: PDFViewer (PDF + optional OCR text panel).

**Add a third tab: "Agent"** (next to Extraction and Forms in `PDFSidebar.tsx`).

When **Agent** is selected, the left panel shows:

1. **Chat message list**: Scrollable conversation history. Messages from the agent can contain text, code blocks (schema JSON, prompt text), and **pending action cards** (tool calls awaiting approval).
2. **Pending action cards**: When the agent proposes a tool call (e.g. "Create schema 'Invoice'"), it appears as a card with:
   - Tool name and parameters (human-readable summary + expandable raw JSON).
   - **Approve** / **Reject** buttons.
   - Optional **Edit** (modify parameters before approving, e.g. tweak a schema field).
3. **Current extraction panel** (collapsible): Shows the latest extraction result (if any) — same field-value display as the Extraction tab. Updated live when the agent runs extraction or patches fields.
4. **Chat input**: Text input with `@` mention autocomplete. Send button. Settings gear for auto-approve toggle and model selection.

**Auto-approve toggle**: A setting (per-session, stored in frontend state) with options:
- **Ask every time** (default): Every tool call shows as a pending action card.
- **Auto-approve all**: Tool calls execute immediately, results stream back. The action cards still appear in the message list (for auditability) but are already in "approved" state.
- Possible future: per-tool-type granularity (e.g. auto-approve reads, ask for writes).

---

## 2. @ Mention System

### 2.1 Frontend

- When the user types `@` in the chat input, show a dropdown/popover with searchable entity list.
- **Entity types**:
  - **Schemas**: Listed by name + version (e.g. `@Invoice Schema v3`). Fetched from `GET /v0/orgs/{org_id}/schemas`.
  - **Prompts**: Listed by name (e.g. `@extract-totals`). Fetched from `GET /v0/orgs/{org_id}/prompts`.
  - **Tags**: Listed by name (e.g. `@billing`). Fetched from `GET /v0/orgs/{org_id}/tags`.
- On selection, insert a mention token into the input: display text `@Invoice Schema v3`, backed by structured data `{ type: "schema", id: "<schema_revid>" }`.
- The chat input sends both the display text (for LLM context) and the structured references (for backend resolution).

### 2.2 Backend resolution

- The chat endpoint receives `mentions: [{ type, id }]` alongside `messages`.
- Backend resolves each mention to its full content:
  - Schema → full JSON Schema definition.
  - Prompt → prompt text + linked schema + model + tag_ids.
  - Tag → tag name + metadata.
- Resolved content is injected into the **system message** so the LLM can reason about it:
  ```
  The user has referenced the following artifacts:

  [Schema: "Invoice Schema v3"]
  { "type": "json_schema", "json_schema": { "name": "Invoice", "schema": { ... } } }

  [Prompt: "extract-totals"]
  Content: "Extract the following fields from the invoice: ..."
  Linked schema: Invoice Schema v3
  Model: gpt-4o-mini
  Tags: billing
  ```

### 2.3 Caching

- Frontend caches the entity lists (schemas, prompts, tags) on tab open and refreshes on mutation (after a tool call creates/updates an artifact). This keeps `@` autocomplete fast without excessive API calls.

---

## 3. Backend: Agent Tools and Chat Protocol

### 3.1 Agent tools

The LLM agent has access to the same schema, prompt, and tag tools as the MCP server (mirrored in Python), plus document-specific tools for extraction and OCR. All tools are defined as OpenAI-compatible function schemas.

**Schema tools** (mirrors MCP):

| Tool | Parameters | Effect |
|------|-----------|--------|
| `create_schema` | `name`, `response_format` (full SchemaResponseFormat body) | Creates a new schema in the org. Returns `schema_revid`. |
| `get_schema` | `schema_revid` | Returns the full schema definition. |
| `list_schemas` | `skip?`, `limit?`, `name_search?` | Lists schemas in the org. Returns names, IDs, versions. |
| `update_schema` | `schema_id`, `response_format` | Creates a new version of an existing schema. Returns `schema_revid`. |
| `delete_schema` | `schema_id` | Deletes a schema. |
| `validate_schema` | `schema` (JSON string) | Validates schema format for correctness and DocRouter compliance. Returns ok or error details. |
| `validate_against_schema` | `schema_revid`, `data` | Validates data against a schema. Returns ok or validation errors. |

**Prompt tools** (mirrors MCP):

| Tool | Parameters | Effect |
|------|-----------|--------|
| `create_prompt` | `name`, `content`, `schema_id?`, `schema_version?`, `model?`, `tag_ids?` | Creates a new prompt. Returns `prompt_revid`. |
| `get_prompt` | `prompt_revid` | Returns the full prompt (content, linked schema, model, tags). |
| `list_prompts` | `skip?`, `limit?`, `document_id?`, `tag_ids?`, `name_search?` | Lists prompts in the org. Returns names, IDs, versions. |
| `update_prompt` | `prompt_id`, `content?`, `schema_id?`, `tag_ids?`, `model?` | Creates a new version of an existing prompt. Returns `prompt_revid`. |
| `delete_prompt` | `prompt_id` | Deletes a prompt. |

**Tag tools** (mirrors MCP):

| Tool | Parameters | Effect |
|------|-----------|--------|
| `create_tag` | `name`, `color` | Creates a new tag. Returns `tag_id`. |
| `get_tag` | `tag_id` | Returns tag details (name, color). |
| `list_tags` | `skip?`, `limit?`, `name_search?` | Lists tags in the org. |
| `update_tag` | `tag_id`, `name?`, `color?` | Updates a tag's properties. |
| `delete_tag` | `tag_id` | Deletes a tag. |

**Document & extraction tools** (specific to the document agent):

| Tool | Parameters | Effect |
|------|-----------|--------|
| `get_ocr_text` | `page_num?` | Returns OCR text for the current document (optionally a specific page). |
| `run_extraction` | `prompt_revid?` | Runs LLM extraction on the current document with the given (or most recent) prompt. Returns the extraction result. |
| `get_extraction_result` | `prompt_revid?` | Returns the current extraction result for the document. |
| `update_extraction_field` | `path`, `value` | Patches a single field in the current extraction result. Returns updated extraction. |

**Working extraction state**: The agent loop (`agent_loop.py`) maintains a `working_state` dict that tracks the current context:

```python
working_state = {
    "schema_revid": str | None,     # Last created/updated schema
    "prompt_revid": str | None,     # Last created/updated prompt
    "extraction": dict | None,      # Last extraction result
}
```

- `run_extraction` updates `working_state.prompt_revid` and `working_state.extraction`.
- `update_extraction_field` patches `working_state.extraction` (and writes to DB).
- `create_schema` / `update_schema` update `working_state.schema_revid`.
- `create_prompt` / `update_prompt` update `working_state.prompt_revid`.
- `get_extraction_result` reads from `working_state.extraction` (falling back to DB if not set).
- `system_prompt.py` injects `working_state.extraction` into the system message each LLM turn so the agent sees the latest result.
- For "proposed" documents (after auto-create), `working_state` is initialized from the document's `auto_create_schema_revid`, `auto_create_prompt_revid`, and the stored extraction result. The user can then refine via chat, which updates `working_state` normally.

**Total: 23 tools** (7 schema + 5 prompt + 5 tag + 4 document/extraction + 2 help — see below).

**Help tools** (injected as tool descriptions, not callable — the agent's system prompt includes this guidance):

| Tool | Effect |
|------|--------|
| `help_schemas` | Returns detailed guidance on creating schemas (format, constraints, examples). Equivalent to MCP's `help_schemas`. |
| `help_prompts` | Returns detailed guidance on creating prompts (format, linking to schemas, model selection). Equivalent to MCP's `help_prompts`. |

These can be implemented as actual callable tools (agent calls `help_schemas` to get guidance before creating a schema) or baked into the system prompt. Recommendation: make them callable tools so the agent can pull guidance on demand without bloating every request's system message.

All tools use **internal Python service functions** (not HTTP self-calls). Refactor schema/prompt/tag CRUD from route handlers into shared service functions in `analytiq_data/common/`.

**Schema format constraint**: `create_schema` and `update_schema` validate that `response_format` conforms to `SchemaResponseFormat` and that the inner schema passes `Draft7Validator.check_schema()`. On validation failure, the tool returns an error message (not an HTTP error) so the LLM can self-correct.

### 3.2 Chat protocol (tool permission loop)

The chat is a multi-step protocol between frontend and backend, similar to Claude Code's permission model:

```
Frontend                          Backend                          LLM
   |                                 |                              |
   |-- POST /chat (messages, mentions) -->                          |
   |                                 |-- build context + send -->   |
   |                                 |                              |
   |                                 |<-- response (text + tool_calls)
   |                                 |                              |
   |<-- SSE: text chunks             |                              |
   |<-- SSE: tool_calls (pending)    |                              |
   |                                 |                              |
   |   [user reviews pending actions]|                              |
   |                                 |                              |
   |-- POST /chat/approve            |                              |
   |   { approvals: [               |                              |
   |     { call_id, approved: true },|                              |
   |     { call_id, approved: false }|                              |
   |   ]}                            |                              |
   |                                 |-- execute approved tools     |
   |                                 |-- append tool results        |
   |                                 |-- send to LLM again -------> |
   |                                 |                              |
   |                                 |<-- response (text, maybe more tool_calls)
   |<-- SSE: text chunks             |                              |
   |<-- SSE: done (or more tool_calls)|                             |
```

**Key details**:

- **`POST /v0/orgs/{org_id}/documents/{doc_id}/chat`**: Starts a chat turn. Body: `{ messages, mentions?, model?, stream? }`. Backend builds system message (document context, resolved mentions, tool definitions), sends to LLM.
- **Auth**: Chat and approve endpoints use the same document-level auth as other document routes (e.g. org member with access to the document). No additional checks.
- **SPU / cost**: Each LLM call within the agent loop consumes SPU. Rather than estimating total cost upfront, **each individual LLM call checks SPU independently** — the agent loop's LLM calls go through litellm which already calls `check_spu_limits` per invocation (same as `run_llm`). If the org runs out of credits mid-loop, the current LLM call fails, the agent loop surfaces the error as a tool result or final message, and the turn ends. Similarly, `run_extraction` (which internally calls `run_llm`) does its own SPU check. This matches existing behavior and avoids needing to reserve or predict total credits for a multi-step turn.
- **Streaming**: The backend streams text chunks via SSE as they arrive. When the LLM returns tool_calls, the backend streams a `tool_calls` event with the pending calls and **pauses** (does not execute them).
- **`POST /v0/orgs/{org_id}/documents/{doc_id}/chat/approve`**: Frontend sends approvals/rejections for each pending tool call. Backend executes approved tools, constructs tool result messages, appends rejected tool messages ("User rejected this action"), and sends the updated message list back to the LLM for the next turn.
- **Loop**: This continues until the LLM responds with only text (no tool calls), or until a max iteration limit (e.g. 10 tool-call rounds).
- **Auto-approve mode**: If the frontend sends `auto_approve: true` in the initial chat request, the backend executes all tool calls immediately without pausing — same as Claude Code's "allow all" mode. Tool calls still appear in the streamed output for auditability.
- **Auto-approve requires streaming**: With `auto_approve: true`, a single request can involve 10+ LLM calls and tool executions. Non-streaming would hit HTTP timeouts. Therefore `auto_approve: true` requires `stream: true`; the backend rejects the request otherwise. In streaming mode the SSE connection stays open, and the frontend sees tool calls + results as they happen.

### 3.3 Session state

The chat/approve loop requires the backend to hold intermediate state (pending tool calls, message history for the current turn) between the two requests. Options:

- **In-memory with session ID**: The `/chat` endpoint returns a `turn_id`. The `/chat/approve` endpoint references it. Backend holds pending state in a short-lived cache (e.g. dict keyed by turn_id, TTL 5 minutes). Simple, works for v1.
- **Database-backed sessions**: Store in MongoDB. More durable but overkill for v1.

Recommendation: in-memory cache for v1. If the server restarts mid-turn, the user simply re-sends their message.

### 3.4 Context budget

To prevent token limit issues:

- **System message**: Document context (OCR excerpt capped at ~2k tokens) + resolved @ mentions + current extraction + tool definitions. Estimated ~3–4k tokens.
- **Conversation history**: Client sends full history; backend truncates to last N messages (e.g. 20) before sending to LLM. Older messages are dropped.
- **Total budget**: Target ~8k tokens for context, leaving the rest for the LLM's generation and tool call reasoning.

---

## 4. Auto-Create on Upload (Headless Agent)

The worker is invoked **only** when auto-create is selected on upload; interactive chat in the Agent tab runs in the foreground in the HTTP request.

### 4.1 Trigger

On document upload (dashboard/upload flow), add an **"Auto-create schema & prompt"** checkbox (default on or off, configurable per org). When enabled:

1. Document is uploaded and OCR begins as usual.
2. After OCR completes (detected by the worker), the worker enqueues an **auto-create task**.
3. The auto-create task runs the same agent with all tools auto-approved, no user in the loop.

### 4.2 Headless pipeline

The headless agent is the same LLM agent (same tools, same system prompt) but with a **fixed initial user message**:

> "Analyze this document. Create a schema that captures the key, repeatable fields for documents like this — focus on fields that would be uniform across similar documents, not every detail. Then create a prompt for extracting those fields, and run the extraction."

The agent runs with `auto_approve: true`, so it calls `create_schema` → `create_prompt` → `run_extraction` without pausing. The refinement loop (agent reviews its own output and optionally calls `update_schema` / `update_prompt` / `run_extraction` again) is also auto-approved, capped at 2 iterations.

### 4.3 "Proposed" state

After the headless agent finishes, the results are stored on the document:

```python
{
    "auto_create_status": "proposed",  # "proposed" | "accepted" | "rejected"
    "auto_create_schema_revid": "...",
    "auto_create_prompt_revid": "...",
    "auto_create_done_at": datetime,
    "auto_create_agent_log": [...]     # The full message history (for replay/review)
}
```

When the user opens the document page:
- The **Agent tab** shows the auto-create result with a summary: "I created schema 'Invoice' and prompt 'extract-invoice-fields'. Here's what I extracted: ..."
- The **current extraction panel** shows the result.
- The user can:
  - **Accept**: Mark as accepted. Prompt appears in Extraction tab normally.
  - **Refine via chat**: "Add a `payment_terms` field to the schema" → agent proposes `update_schema` → user approves → agent re-runs extraction.
  - **Reject**: Discard schema, prompt, and extraction. Mark as rejected.

### 4.4 Error handling

- If OCR fails, auto-create is skipped.
- If any LLM call in the headless pipeline fails, set `auto_create_status: "failed"` with error details.
- **Persistence**: Schema and prompt are created in the DB as the agent runs (so the agent receives `schema_revid` / `prompt_revid` for `run_extraction`). Only after the first successful extraction do we set the document's `auto_create_*` fields and mark status as `"proposed"`. On failure before that, we do not write `auto_create_*` to the document; the schema and prompt may remain in the DB as orphans (useful for debugging). Optionally, add a cleanup step that deletes orphan schema/prompt created in the same run when status is set to `"failed"`.
- Worker timeout: cap headless agent at 120s total. If exceeded, fail gracefully.

---

## 5. Reusing Existing Infrastructure

**Conclusion: do not call the MCP server from FastAPI. Reuse the workflow and API semantics in Python.**

- The MCP server is a **stdio-based tool server** — the AI agent runs externally (Cursor/Claude) and calls MCP tools. The MCP server forwards to the DocRouter REST API.
- The document chat agent runs **server-side** in Python. It should use internal Python functions, not subprocess/stdio.

**What to reuse from MCP**:
- **Workflow steps**: get OCR → propose schema → create schema → generate prompt → create prompt → run extraction → refine. Same sequence, now driven by the LLM agent with tools instead of a hardcoded pipeline.
- **System prompts**: Adapt the natural language instructions from MCP/CLAUDE docs for "propose a schema for similar documents" and "generate an extraction prompt" into the agent's system message.
- **API contracts**: Schema and prompt formats must match what the REST API expects.
- **Validation**: Reuse `Draft7Validator.check_schema()` and `SchemaResponseFormat` validation.

**What NOT to do**: Do not spawn the MCP server subprocess. Do not try to share the agent process.

---

## 6. File Structure

### 6.1 Design principle: additive, not rewriting

The agent is a **new module alongside existing code**. Existing route handlers, data layer files, and tests are not modified (except two small touchpoints: adding a tab button in `PDFSidebar.tsx` and registering a new router in `main.py`).

The agent tool functions do their own DB operations directly (like the existing `analytiq_data/common/` helpers do), rather than calling route handlers. This avoids coupling the agent to FastAPI request/response and auth middleware.

### 6.2 Backend (Python)

```
packages/python/
├── analytiq_data/
│   ├── agent/                          # NEW — all agent logic lives here
│   │   ├── __init__.py
│   │   ├── tools/                      # One file per tool group
│   │   │   ├── __init__.py             # Re-exports all tool functions
│   │   │   ├── schema_tools.py         # create/get/list/update/delete/validate schema
│   │   │   ├── prompt_tools.py         # create/get/list/update/delete prompt
│   │   │   ├── tag_tools.py            # create/get/list/update/delete tag
│   │   │   ├── extraction_tools.py     # run_extraction, get/update result, get_ocr_text
│   │   │   └── help_tools.py           # help_schemas, help_prompts (reads knowledge_base md files)
│   │   ├── tool_registry.py            # OpenAI function schemas for all tools + dispatch map
│   │   ├── agent_loop.py              # Core loop: LLM call → check tool_calls → return or pause
│   │   ├── system_prompt.py           # Builds system message (doc context, mentions, instructions)
│   │   └── session.py                 # In-memory turn state cache (pending tool calls, TTL)
│   ├── common/
│   │   ├── schemas.py                 # EXISTING — keep as-is (get_schema_id, etc.)
│   │   ├── prompts.py                 # EXISTING — keep as-is (get_prompt_id, etc.)
│   │   ├── tags.py                    # EXISTING — keep as-is (get_tag_id, etc.)
│   │   └── ...
│   └── ...
├── app/
│   ├── routes/
│   │   ├── agent.py                   # NEW — chat + approve endpoints (thin, delegates to agent_loop)
│   │   ├── schemas.py                 # EXISTING — unchanged
│   │   ├── prompts.py                 # EXISTING — unchanged
│   │   ├── tags.py                    # EXISTING — unchanged
│   │   └── ...
│   ├── main.py                        # MODIFIED — add: from app.routes.agent import agent_router
│   └── ...
├── worker/
│   ├── worker.py                      # MODIFIED — add auto-create message handler
│   └── ...
└── tests/
    ├── agent/                         # NEW — agent test directory
    │   ├── __init__.py
    │   ├── test_schema_tools.py       # Unit tests for schema tool functions
    │   ├── test_prompt_tools.py       # Unit tests for prompt tool functions
    │   ├── test_tag_tools.py          # Unit tests for tag tool functions
    │   ├── test_extraction_tools.py   # Unit tests for extraction tool functions
    │   ├── test_tool_registry.py      # Tests for tool schema definitions + dispatch
    │   ├── test_agent_loop.py         # Tests for agent loop with mocked LLM
    │   ├── test_agent_chat.py         # Integration tests for chat/approve endpoints
    │   └── conftest_agent.py          # Agent-specific fixtures (mock LLM, sample doc, etc.)
    ├── conftest.py                    # EXISTING — unchanged
    └── ...
```

### 6.3 Frontend (TypeScript)

```
packages/typescript/frontend/src/
├── components/
│   ├── agent/                         # NEW — self-contained agent UI
│   │   ├── AgentTab.tsx               # Top-level tab component (orchestrates state)
│   │   ├── AgentChat.tsx              # Chat message list (scrollable, renders AgentMessage[])
│   │   ├── AgentMessage.tsx           # Single message: text, code blocks, or tool call card
│   │   ├── ToolCallCard.tsx           # Pending action: tool name, params, Approve/Reject/Edit
│   │   ├── MentionInput.tsx           # Chat text input with @ trigger
│   │   ├── MentionDropdown.tsx        # Autocomplete popover (schemas, prompts, tags)
│   │   ├── ExtractionPanel.tsx        # Collapsible current extraction display
│   │   ├── AutoCreateReview.tsx       # Banner for "proposed" auto-create results (Accept/Reject)
│   │   └── useAgentChat.ts           # Hook: manages chat state, SSE streaming, approve calls
│   ├── PDFSidebar.tsx                 # MODIFIED — add "Agent" tab button + render AgentTab
│   └── ...existing unchanged...
├── app/
│   └── ...existing unchanged...
└── ...
```

### 6.4 What gets modified in existing files

| File | Change | Size |
|------|--------|------|
| `app/main.py` | Add `from app.routes.agent import agent_router` + `app.include_router(agent_router)` | 2 lines |
| `PDFSidebar.tsx` | Add "Agent" tab button + conditional render of `<AgentTab />` | ~10 lines |
| `worker/worker.py` | Add auto-create message handler (imports from `analytiq_data/agent/`) | ~15 lines |

Everything else is new files.

### 6.5 Key design decisions in the file structure

**Why `analytiq_data/agent/` and not `app/agent/`?**
The agent logic (tools, loop, system prompt) needs to run both in the FastAPI server (for interactive chat) and in the worker (for headless auto-create). Putting it in `analytiq_data/` (the shared data layer) makes it importable from both, matching the existing pattern where `analytiq_data/llm/llm.py` is used by both `app/routes/llm.py` and `worker/`.

**Why separate tool files instead of one big file?**
Each tool group (schema, prompt, tag, extraction) maps 1:1 to a collection of related DB operations. This keeps files under ~200 lines, makes them independently testable, and mirrors the MCP server's organization.

**Why `tool_registry.py`?**
Single source of truth for: (a) OpenAI function schema definitions (sent to the LLM), (b) mapping from tool name → Python function. Adding a new tool means adding it in one place. The registry is also what gets sent in the LLM `tools` parameter.

**Why `useAgentChat.ts` hook?**
Encapsulates the SSE streaming, message state, pending tool calls, and approve/reject flow in one reusable hook. `AgentTab.tsx` stays simple — it just renders the UI from the hook's state.

---

## 7. Testing Strategy

### 7.1 Layers

```
┌─────────────────────────────────────────────────────────┐
│  Integration tests (test_agent_chat.py)                 │
│  FastAPI TestClient → chat/approve endpoints → mocked LLM│
├─────────────────────────────────────────────────────────┤
│  Agent loop tests (test_agent_loop.py)                  │
│  Mocked LLM → verify tool dispatch, stop conditions     │
├─────────────────────────────────────────────────────────┤
│  Tool unit tests (test_*_tools.py)                      │
│  Real test DB → verify each tool function in isolation   │
└─────────────────────────────────────────────────────────┘
```

### 7.2 Tool unit tests (`test_schema_tools.py`, `test_prompt_tools.py`, etc.)

Each tool function is a **pure async function** with signature:
```python
async def create_schema(analytiq_client, org_id: str, params: dict) -> dict:
```

Tests call the function directly against the test database (same `test_db` + `unique_db_name` fixtures from existing `conftest.py`). No HTTP, no auth, no LLM.

Example:
```python
@pytest.mark.asyncio
async def test_create_and_get_schema(test_db, analytiq_client):
    result = await create_schema(analytiq_client, TEST_ORG_ID, {
        "name": "Invoice",
        "response_format": { "type": "json_schema", "json_schema": { ... } }
    })
    assert "schema_revid" in result

    fetched = await get_schema(analytiq_client, TEST_ORG_ID, {
        "schema_revid": result["schema_revid"]
    })
    assert fetched["name"] == "Invoice"

@pytest.mark.asyncio
async def test_create_schema_invalid_format(test_db, analytiq_client):
    result = await create_schema(analytiq_client, TEST_ORG_ID, {
        "name": "Bad",
        "response_format": { "type": "json_schema", "json_schema": { "schema": "not valid" } }
    })
    assert "error" in result  # Tool returns error, not exception
```

This gives **coverage of every DB operation the agent can perform**, independently of the LLM and HTTP layers.

### 7.3 Agent loop tests (`test_agent_loop.py`)

Mock `litellm.acompletion` to return scripted responses. Verify the loop's control flow:

- **Text-only response** → loop exits, returns text.
- **Tool call response** → loop pauses, returns pending tool calls (in non-auto-approve mode).
- **Tool call response in auto-approve** → loop executes tools, calls LLM again with tool results, handles follow-up.
- **Max iterations** → loop stops after N tool-call rounds.
- **Rejected tool call** → "User rejected this action" message sent to LLM, loop continues.
- **Tool execution error** → error message sent to LLM as tool result, loop continues (LLM can self-correct).

Example:
```python
@pytest.mark.asyncio
async def test_agent_loop_auto_approve(mock_litellm, test_db, analytiq_client):
    # Script: LLM calls create_schema, then create_prompt, then text response
    mock_litellm.side_effect = [
        mock_response(tool_calls=[{"function": {"name": "create_schema", "arguments": "..."}}]),
        mock_response(tool_calls=[{"function": {"name": "create_prompt", "arguments": "..."}}]),
        mock_response(content="Done! I created the schema and prompt."),
    ]
    result = await run_agent_loop(analytiq_client, org_id, doc_id, messages, auto_approve=True)
    assert result.text == "Done! I created the schema and prompt."
    assert mock_litellm.call_count == 3
```

### 7.4 Chat endpoint integration tests (`test_agent_chat.py`)

Use `FastAPI TestClient` (same pattern as existing `test_schemas.py`, `test_llm_chat.py`). Mock `litellm.acompletion`. Test the full HTTP flow:

1. `POST /v0/orgs/{org_id}/documents/{doc_id}/chat` → verify SSE response contains text chunks and tool_calls event.
2. `POST /v0/orgs/{org_id}/documents/{doc_id}/chat/approve` with `turn_id` → verify tools execute, LLM called again, final response returned.
3. Auto-approve mode → verify single request completes the full loop.
4. @ mention resolution → verify mentioned schema/prompt content appears in the LLM's messages.

### 7.5 What we do NOT test

- **LLM output quality**: The agent's ability to propose good schemas depends on the LLM model. This is tested manually or via evals, not unit tests.
- **Frontend**: No frontend test framework exists in the current codebase. Frontend testing can be added later.
- **Existing route handlers**: They have their own tests already. We don't re-test them.

### 7.6 Fixtures (`conftest_agent.py`)

```python
@pytest_asyncio.fixture
async def sample_document(test_db, analytiq_client):
    """Insert a document with OCR text into the test DB."""
    ...

@pytest_asyncio.fixture
async def sample_schema(test_db, analytiq_client):
    """Insert a schema for @ mention tests."""
    ...

@pytest.fixture
def mock_litellm(monkeypatch):
    """Mock litellm.acompletion to return scripted responses."""
    ...
```

---

## 8. Implementation Order

### Phase 1: Backend agent core
1. **Tool functions**: Implement `analytiq_data/agent/tools/` — all 23 tool functions, each doing direct DB operations. Test each with `test_*_tools.py`.
2. **Tool registry**: `tool_registry.py` — OpenAI function schemas + dispatch map. Test with `test_tool_registry.py`.
3. **Agent loop**: `agent_loop.py` — core loop (LLM call → tool_calls check → pause or execute → loop). Test with `test_agent_loop.py` (mocked LLM).
4. **System prompt**: `system_prompt.py` — builds system message from document context, OCR text, mentions, instructions.
5. **Session state**: `session.py` — in-memory dict with TTL.
6. **Chat + approve endpoints**: `app/routes/agent.py` — thin HTTP layer. Test with `test_agent_chat.py`.
7. **Register router**: Add 2 lines to `main.py`.

### Phase 2: Frontend chat tab
8. **AgentTab + AgentChat + AgentMessage**: Core chat UI.
9. **useAgentChat hook**: SSE streaming, message state, approve/reject calls.
10. **ToolCallCard**: Pending action cards with Approve/Reject.
11. **ExtractionPanel**: Collapsible extraction result.
12. **Auto-approve toggle**: Setting in chat input.
13. **PDFSidebar.tsx**: Add "Agent" tab button.

### Phase 3: @ mentions
14. **MentionInput + MentionDropdown**: @ autocomplete fetching from existing list APIs.
15. **Backend mention resolution**: Resolve mention IDs → inject full content into system message.

### Phase 4: Auto-create on upload
16. **Worker handler**: After OCR completes, enqueue auto-create task.
17. **Headless agent run**: Same agent loop with `auto_approve=True`, fixed initial message, results stored as "proposed."
18. **AutoCreateReview**: Banner in Agent tab for proposed results (Accept/Reject/Refine).

### Phase 5: Polish
19. **Model selection**: Dropdown in chat input.
20. **Agent log replay**: Show headless agent conversation in Agent tab.
21. **Save with tag shortcut**: Offer to assign tag after accepting.

---

## 9. Open Decisions

- **Which LLM model for the agent**: Claude sonnet.
- **Auto-create default on/off**: Per-upload toggle? Start with a per-upload checkbox, default off.
- **Prompt visibility**: Auto-created prompts (before user accepts) — visible in Extraction tab or hidden? Recommendation: visible but marked as "(auto-created, pending review)".
- **Max tool-call rounds**: max 10 tool calls in auto mode.

---
