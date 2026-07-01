# DocRouter — Document ↔ Flow Integration Plan

This document specifies the design for integrating the document processing pipeline
(upload → OCR → LLM → tagging) with the flow execution engine.  The goal is to let
users wire document events into flows and to expose document-processing capabilities
as first-class, configurable flow nodes.

**Related docs:**

- [Flows architecture (`flows2.md`)](./flows2.md)
- [Node format (`docrouter_nodes.md`)](./docrouter_nodes.md)
- [Binary handling (`docrouter_binary.md`)](./docrouter_binary.md)

---

## 1. Overview

Document-scoped flows use **`docrouter.trigger`** — a configurable event trigger that
fires on document lifecycle events (`document.uploaded`, `document.error`,
`llm.completed`, `llm.error`).  Re-running a flow for a real document uses
`POST …/flows/{flow_id}/run/{document_id}` (`rerun_flow_for_document`), which
re-dispatches the matching lifecycle event on the active revision.

For **editor testing** without a live document, use **`docrouter.trigger`** with
**pin data** on the trigger node (JSON fields + `files:` binary refs for PDF /
original).  The generic **`flows.trigger.manual`** node remains available for
non-document tool and automation graphs.

This plan adds:


| Area         | What we add                                                                                                                                                                                                                                       |
| ------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Triggers** | `docrouter.trigger` — single configurable trigger; fires on one of four events: `document.uploaded`, `document.error`, `llm.completed`, `llm.error`; `report_result` parameter auto-captures the last node output into the document Flows section |
| **Nodes**    | `docrouter.ocr` — outputs `json.ocr_pages` (array, one entry per page)                                                                                                                                                                            |
| **Nodes**    | `docrouter.llm_run` — optional OCR input port (port 1, `docrouter.ocr` only); auto-injects `ocr_pages` into prompt when connected                                                                                                                 |
| **Nodes**    | `docrouter.document_split` — fan-out: one output item per selected page of the input PDF                                                                                                                                                          |
| **Blobs**    | Explicit dual-blob support: *document blobs* (`files:` bucket) and *flow blobs* (`flow_blobs:` bucket) both addressable in `BinaryRef.storage_id`                                                                                                 |


---

## 2. DocRouter Event Trigger

### 2.1 Purpose

A single configurable trigger node that fires when a document lifecycle event
occurs.  The `event_type` parameter selects which of four events to listen for:


| `event_type`        | Fires when                                         |
| ------------------- | -------------------------------------------------- |
| `document.uploaded` | A document is uploaded                             |
| `document.error`    | A document enters an error state during processing |
| `llm.completed`     | An LLM run finishes successfully for a document    |
| `llm.error`         | An LLM run fails for a document                    |


### 2.2 Node key

```
docrouter.trigger
```

### 2.3 Parameter schema


| Parameter       | Type                                                                                      | Applicable events            | Description                                                                                                                                                                               |
| --------------- | ----------------------------------------------------------------------------------------- | ---------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `event_type`    | `"document.uploaded" \| "document.error" \| "llm.completed" \| "llm.error"`              | all                          | Required.                                                                                                                                                                                 |
| `tag_ids`       | `array[string]`                                                                           | all                          | Optional tag filter — fires if the document has **any** of these tags. Empty = match any document.                                                                                        |
| `prompt_id`     | `string`                                                                                  | `llm.completed`, `llm.error` | Optional prompt filter — fires only for this prompt. Empty = any prompt.                                                                                                                  |
| `report_result` | `boolean`                                                                                 | all                          | When `true` (default), the engine automatically captures the last node's output at execution completion and stores it in `flow_results` for display in the document Flows section (§2.8). |


### 2.4 Trigger output

All events share a common document metadata block.  Event-specific fields are
present only for the relevant `event_type`.

```
json:
  event_type:   str          # one of the four event names
  document_id:  str
  file_name:    str          # original filename as uploaded
  mime_type:    str
  upload_date:  str          # ISO 8601 datetime
  tag_ids:      list[str]   # all tag IDs on the document at trigger time
  tag_names:    list[str]   # parallel array of tag names (snapshot; "" for unknown)
  metadata:     dict[str, str]

  # llm.completed and llm.error
  prompt_id:    str
  prompt_revid: str
  prompt_name:  str          # snapshot at dispatch time

  # llm.completed only
  llm_run_id:          str
  trigger_llm_result:  <result JSON>   # renamed to avoid collision with docrouter.llm_run output

  # document.error / llm.error
  error_message:  str
  error_code:     str | null

binary:
  pdf:      BinaryRef → storage_id "files:<doc.pdf_file_name>"
  original: BinaryRef → storage_id "files:<doc.mongo_file_name>"  (omitted if same as pdf)
```

`doc.pdf_file_name` is the document record's `pdf_file_name` field — the GridFS key for
the converted PDF.  `doc.mongo_file_name` is the document record's `mongo_file_name`
field — the GridFS key for the original upload, of the form `<document_id><ext>`.
`original` is omitted when no conversion was needed (`pdf_file_name == mongo_file_name`).

The trigger emits exactly one `FlowItem` per event.

In addition to the `FlowItem`, the trigger node writes the full event payload into
the execution context under the key `trigger_data`.  `context.trigger_data` is a
dict containing all JSON fields listed above for the relevant `event_type`, and it
is available to every node throughout the execution without requiring explicit
wiring through intermediate nodes.  Nodes can read `context.trigger_data["document_id"]`
directly from this context object rather than from the propagated `FlowItem`.  A flow
whose graph contains no `docrouter.trigger` node will have `context.trigger_data` set
to `None`.

### 2.5 Backend integration points

A single dispatcher function `_dispatch_docrouter_event(org_id, event_type, doc_id, **event_kwargs)` is called from each lifecycle hook:


| Lifecycle hook                             | Event emitted       |
| ------------------------------------------ | ------------------- |
| Upload handler (`app/routes/documents.py`) | `document.uploaded` |
| Document error path (worker)               | `document.error`    |
| LLM completion path (`llm/llm.py`)         | `llm.completed`     |
| LLM error path (worker + API route)        | `llm.error`         |


The dispatcher queries `flow_triggers` by `(org_id, trigger_type)`, evaluates
`tag_id` and `prompt_id` filters, and enqueues a `flow_run` job for each match.
Dispatch is **asynchronous** — the lifecycle hook returns immediately and does not
wait for flows to execute.  Dispatch is also **at-least-once**: if a lifecycle hook
retries after the dispatcher has already run, a duplicate `flow_run` job may be
enqueued; flow implementations should be idempotent where writing the same result
twice is acceptable.  Re-uploading the same file always fires the trigger because a
re-upload creates a new document record and is treated as a fresh `document.uploaded`
event regardless of `include_retagged`.

### 2.6 Activation / deactivation

- **Save (`PUT /v0/orgs/{org}/flows/{id}`)** — validates `docrouter.trigger` node
parameters (e.g. `event_type` must be one of the four values) and returns `400`
on error.  Does **not** write or modify `flow_triggers` rows — trigger rows are
only written at activation time.  This ensures that saving a new revision while a
flow is already active never disrupts ongoing dispatch.
- **Activate (`POST /v0/orgs/{org}/flows/{id}/activate`)** — deletes any existing
`flow_triggers` rows for the flow, then upserts one row per `docrouter.trigger`
node found in the target revision:
  ```json
  {
    "trigger_type": "document.uploaded" | "document.error" | "llm.completed" | "llm.error",
    "flow_id": "…", "org_id": "…", "flow_revid": "…", "trigger_node_id": "…",
    "tag_ids": ["…"],
    "prompt_id": "…",
    "report_result": true
  }
  ```
  A unique index on `(flow_id, trigger_node_id)` ensures repeated activation calls
  are idempotent and cannot produce duplicate dispatch rows.
- **Deactivate / delete** — removes all `flow_triggers` rows for that flow.
- The dispatcher queries `flow_triggers` by `(org_id, trigger_type)`, then confirms
the matched flow is still active and that `flow.active_flow_revid == row.flow_revid`
before enqueuing — no full flow scan needed at event time.

### 2.7 Deletion safety for `tag_id` and `prompt_id` references

`docrouter.trigger` nodes can reference `tag_ids` or a `prompt_id` as filters.
Tags and prompts can be deleted at any time — deletion is not blocked.  Instead,
the UI surfaces the broken reference directly in the trigger node config panel so
the user is aware and can correct it.

**Trigger config panel warnings** ✅ implemented.  Each picker component
(`FlowOrgTagMultiPickerField`, `FlowOrgEntityPickerField`) individually resolves its
stored IDs against the org's current entities on load.  Tags or prompts that no
longer exist are shown with a `deleted` chip in-place so the user can see and clear
them.  The flow remains saveable and activatable with a deleted reference; at
dispatch time the filter simply never matches, so the trigger is silenced until the
user corrects the node.

**Historic run records.**  Flow executions are immutable event logs.  The only
impact of a deletion is display: the UI cannot resolve a name for a deleted entity.

1. **Snapshot names at dispatch time** ✅ implemented.  `build_docrouter_event_payload`
  stores `tag_names` (parallel array to `tag_ids`, one name per tag on the document)
   and `prompt_name`.  All names are resolved at the moment the trigger fires so
   execution records are self-contained.
2. **Graceful UI fallback** ✅ implemented.  The execution trace view displays
  `[deleted]` for any tag or prompt name that resolves to an empty string, covering
   runs that predate the name snapshot fields.

### 2.8 Automatic result capture (`report_result`)

When `report_result` is `true` (the default), the flow engine automatically
captures the output of the last node in the graph after execution completes and
writes it to the `flow_results` collection (§6.2), keyed on `(document_id, flow_id)`.
No explicit save-result node is needed.

The result is displayed in a **Flows** section on the document detail page.  One row
is shown per flow that has a `docrouter.trigger` with `report_result` enabled:

- Flow name (linked to the flow editor)
- Execution timestamp (linked to the execution trace)
- Last-node JSON output rendered with the same viewer used for LLM prompt results
(read-only; not editable)

If a document has no `docrouter.trigger` with `report_result` enabled, the Flows
section is not shown on the document page.  If the flow re-runs, only the latest
result is retained — the previous `flow_results` record is overwritten.

---

## 3. OCR Node

### 3.1 Purpose

Standalone OCR step for use in multi-node flows (e.g. before `docrouter.llm_run`
when the flow author wants to inspect OCR output separately).

### 3.2 Node key

```
docrouter.ocr
```

### 3.3 Parameter schema


| Parameter      | Type                                         | Required | Description         |
| -------------- | -------------------------------------------- | -------- | ------------------- |
| `ocr_provider` | `"textract" | "mistral" | "pymupdf" | "llm"` | yes      | OCR backend to use. |


### 3.4 Input

- `binary.pdf` — preferred; when absent, the first binary property on the item (stable
property-name order) is used and any additional attachments are ignored. Input items with
no binary attachment are skipped (no output item).

### 3.5 Behavior

1. Load the selected PDF binary into memory (`binary.pdf`, or the first binary property).
2. Run the selected OCR provider against the PDF bytes (does **not** write to the
  document OCR store — flow-scoped only).
3. Store `ocr_json` as a **flow blob** in GridFS `flow_blobs` keyed to this execution
  (purged when the execution is deleted).
4. Pass `binary.pdf` from the input through to the output unchanged.
5. Emit one output item per input item.

**Implementation notes:**


| Topic                   | Detail                                                                                                                                                        |
| ----------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Provider enum           | `OCR_PROVIDER_CHOICES` in `services.py` is the single source; `parameter_schema` in `ocr_node.py` and `ocr.manifest.json` derive from / must match it.        |
| OCR job correlation     | `flow_ocr_document_id()` in `services.py` tags provider logs with the item's `document_id` when present; falls back to `execution_id` for pinned PDFs in the editor. |
| No document store write | `run_flow_ocr_on_pdf` does not persist to the document OCR store — flow-scoped only.                                                                          |


### 3.6 Output

```
json:
  ocr_provider: str        # provider that ran
  ocr_pages:    list[str]  # plain-text per page, one entry per page (0-based)

binary:
  pdf:      BinaryRef      # passthrough
  ocr_json: BinaryRef      # full structured OCR result stored as a flow blob (flow_blobs bucket)
```

`ocr_pages[N]` is the plain-text of page N.  Downstream nodes (`docrouter.llm_run`)
read this array from the connected OCR input port.

The output port uses connection type `"docrouter.ocr"` — it can only be wired to
`docrouter.ocr`-typed input ports on downstream nodes.

### 3.7 UI

- `ocr_provider` rendered as a dropdown.

---

## 4. LLM Run Node

### 4.1 Purpose

Run a configured prompt against a document's OCR text.  OCR is supplied via an
optional second input port connected to a `docrouter.ocr` node.  If the OCR port
is connected, OCR pages are automatically injected into the prompt context; if not,
no OCR text is included.

### 4.2 Node key

```
docrouter.llm_run
```

### 4.3 Parameter schema


| Parameter   | Type     | Required | Description                                                          |
| ----------- | -------- | -------- | -------------------------------------------------------------------- |
| `prompt_id` | `string` | yes      | Prompt to run. Dropdown populated from `GET /v0/orgs/{org}/prompts`. |


### 4.4 Input ports


| Port | Index | Required | Connection type | Description                                          |
| ---- | ----- | -------- | --------------- | ---------------------------------------------------- |
| main | 0     | yes      | `main`          | Primary data item (trigger output or upstream node). |
| ocr  | 1     | no       | `docrouter.ocr` | OCR output item carrying `json.ocr_pages`.           |


The OCR port uses connection type `"docrouter.ocr"`, which only the output of
`docrouter.ocr` nodes carries.  Enforcement is structural:

- **UI:** the drag layer rejects a drop when source and target port connection types differ.
- **Workflow validation:** the engine checks all connection types at activation time;
a mismatch raises a configuration error before any execution begins.

### 4.5 Behavior

1. If the OCR input port (index 1) is connected: read `json.ocr_pages` from the
  paired OCR item and join the page strings with `\n` to form the OCR text, then
   inject it into the prompt context automatically.
   No explicit configuration required — presence of the connection is the signal.
2. If the OCR port is not connected: call the LLM without OCR context (the prompt
  must be self-contained or reference data available in the flow item's JSON).
3. Load the prompt (and its JSON schema if configured) by `prompt_id`.
4. Call the LLM with the assembled context.
5. Parse and validate the response against the schema (if present).
6. Pass `binary.pdf` from the main input through to the output unchanged.
7. Emit one output item per input item.

### 4.6 Output

```
json:
  prompt_id:  str
  llm_result: <result JSON>

binary:
  pdf:  BinaryRef   # passthrough from main input
```

`binary.original` from the trigger is not propagated; downstream nodes that need it can access it directly from the trigger output.

### 4.7 UI

- `prompt_id` rendered as a searchable dropdown.
- Node canvas shows two input handles: **main** (left, connection type `main`) and
**ocr** (bottom-left, connection type `docrouter.ocr` — shown with a distinct colour/icon).

---

## 5. Dual Blob Support

### 5.1 Current state

`BinaryRef.storage_id` already encodes the bucket:


| Prefix                  | Bucket              | Used for                        |
| ----------------------- | ------------------- | ------------------------------- |
| `files:<key>`           | GridFS `files`      | Document PDFs and originals     |
| `flow_blobs:<path>`     | GridFS `flow_blobs` | Intermediate execution data     |
| `flow_pins:<path>`      | GridFS `flow_pins`  | Pinned output overrides         |
| *(none / `data` field)* | In-memory           | Small payloads during execution |


### 5.2 Document blobs vs flow blobs

We formalise the distinction:


| Concept           | Bucket       | Lifetime                                          | Who owns it        |
| ----------------- | ------------ | ------------------------------------------------- | ------------------ |
| **Document blob** | `files`      | Permanent (deleted when document deleted)         | Document lifecycle |
| **Flow blob**     | `flow_blobs` | Execution lifetime; GC'd when execution is purged | Flow execution     |


### 5.3 Blob resolution in the frontend

`flowExecutionBlob.ts` already resolves `storage_id` via
`GET /v0/orgs/{org}/flows/{flow}/executions/{exec}/blob?storage_id=…`.

The endpoint must be extended to handle `files:<key>` prefixes (today it only
handles `flow_blobs` and `flow_pins`).  Access control: the caller must be a
member of the org that owns the document.

---

## 6. Collections

### 6.1 `flow_triggers` (new)

Unified indexed rows for all docrouter trigger types.  The `trigger_type`
discriminator determines which fields are relevant for dispatch.

```json
{
  "_id": "<trigger_row_id>",
  "org_id": "…",
  "flow_id": "…",
  "flow_revid": "…",        // revision the trigger was registered against
  "trigger_node_id": "…",
  "trigger_type": "document.uploaded" | "document.error" | "llm.completed" | "llm.error",
  "tag_ids": ["…"],          // optional tag filter — any-match (all types)
  "prompt_id": "…",         // optional prompt filter (llm.completed / llm.error only)
  "report_result": true,    // mirrors the trigger node's report_result parameter
  "created_at": "…",
  "updated_at": "…"
}
```

`flow_revid` is written by `sync_docrouter_flow_triggers` at activation time.  The
dispatcher checks that `flow.active_flow_revid == row.flow_revid` before enqueuing,
so stale trigger rows left over from a previous activation cannot fire against a newer
(or rolled-back) revision.

Unique index: `(flow_id, trigger_node_id)` — enforces idempotent activation.
Index: `(org_id, trigger_type)` — primary dispatch index.

### 6.2 `flow_results` (new)

Stores results automatically captured by the engine when `report_result` is enabled
on the originating trigger (see §2.8).

```json
{
  "_id": "<result_id>",
  "org_id": "…",
  "document_id": "…",
  "flow_id": "…",
  "execution_id": "…",
  "result": { },
  "created_at": "…"
}
```

Unique index: `(document_id, flow_id)` — upsert target; one result per flow per document (latest run wins).
Index: `(org_id, document_id)` for fast lookup from the document page.
Index: `(org_id, flow_id)` for listing results by flow.

### 6.3 Deletion cascades


| Delete event               | What is removed                                                                                 |
| -------------------------- | ----------------------------------------------------------------------------------------------- |
| **Flow execution deleted** | `flow_blobs` GridFS entries for that execution (includes `ocr_json` blobs from `docrouter.ocr`) |
| **Document deleted**       | All `flow_results` records with that `document_id`                                              |
| **Flow deleted**           | All `flow_triggers` rows for that `flow_id`; all `flow_results` records for that `flow_id`      |


---

## 7. Implementation Sequence

### 7.0 Migration / cleanup of existing nodes

Before implementing the nodes in this plan, the following existing artifacts must be
renamed or removed to avoid parallel implementations under different names:


| Existing name                                                    | Action                     | Target name (this plan) |
| ---------------------------------------------------------------- | -------------------------- | ----------------------- |
| `docrouter.llm_extract` node (backend + frontend)                | Rename                     | `docrouter.llm_run`     |
| `docrouter.create_document` in `docrouter_binary.md`             | Remove                     | *(no longer planned)*   |
| `flow_trigger_registrations` collection (schedule/poll triggers) | Reconcile schema or rename | `flow_triggers` (§6.1)  |


These renames should land as a single clean-up commit before any node work begins so
that the codebase uses this plan's names throughout.

### 7.1 Ordered steps

The following order minimises dependency risk:

1. ✅ **Dual blob resolution** (§5.3) — `get_execution_blob` extended to dispatch on
  `files:`, `flow_blobs:`, and `flow_pins:` prefixes; org-ownership check on `files:`
   keys; `_parse_binary_storage_id` / `_binary_blob_http_response` helpers extracted.
   Frontend `flowExecutionBlob.ts` comment updated; `isFetchableExecutionBlobStorageId`
   guard added.  Tests: `test_flow_execution_blob_http.py`.
2. ✅ **DocRouter event trigger** (§2) — `flow_triggers` collection with indexes;
  `send_docrouter_event` / `send_docrouter_error_event` dispatcher; lifecycle hooks
   wired in `documents.py` (upload), `msg_handlers/ocr.py` (document error),
   `llm/llm.py` (llm.completed), `msg_handlers/llm.py` + `routes/llm.py` (llm.error);
   `DocRouterEventTriggerNode` registered; activate/deactivate/delete wired in
   `flows.py`; `validate_docrouter_trigger_params` called on save for early feedback
   without touching trigger rows.  Tests: `test_docrouter_event_trigger.py`.
3. ✅ **Stale reference warnings for `tag_ids` / `prompt_id`** (§2.7):
  - ✅ `tag_id` → `tag_ids` (array, any-match); `FlowOrgTagMultiPickerField` component
   resolves each tag ID and renders a `deleted` chip for any that no longer exist.
  - ✅ `FlowOrgEntityPickerField` resolves `prompt_id` and renders a `deleted` chip if
  missing; wired via `x-ui-widget: org_prompt_picker` in the node manifest.
  - ✅ `build_docrouter_event_payload` snapshots `tag_names` and `prompt_name` at
  dispatch time so execution records are self-contained.
  - ✅ Execution trace UI: renders `[deleted]` where tag/prompt name is empty.
4. ✅ **Typed connection ports**:
  - ✅ `port_types.py` — `ConnectionType = Literal["main", "docrouter.ocr"]`,
   `normalize_connection_type`, `input_port_types_for`, `output_port_types_for`.
  - ✅ `connections.py` — `NodeConnection.connection_type` widened to `ConnectionType`;
  `coerce_json_connections_to_dataclasses` preserves `connection_type` from JSON
  instead of hardcoding `"main"`.
  - ✅ `engine.py` `validate_revision` — checks edge `connection_type` against both
  the source output port type and the destination input port type; raises
  `FlowValidationError` on mismatch.
  - ✅ `lazy_builtin_node.py` / `builtin_loader.py` — load `input_port_types` and
  `output_port_types` from node manifests; `ocr.manifest.json` declares
  `output_port_types: ["docrouter.ocr"]`.
  - ✅ SDK `flow-port-types.ts` — `inputPortType`, `outputPortType`,
  `portTypesCompatible`, `edgeConnectionType`; `FlowNodeType` gains
  `input_port_types` / `output_port_types`; `FlowNodeConnection.connection_type`
  widened; `revisionToRF` stores `data.connectionType` on edges; `rfToConnections`
  reads it back.
  - ✅ `FlowCanvasNode.tsx` — OCR input handles rendered at `Position.Bottom`
  (bottom-left) with a distinct violet style; output handles coloured by port type.
  - ✅ `FlowEditor.tsx` — `isValidConnection` rejects drops when port types are
  incompatible; `onConnect` stores `connectionType` in edge data; inline node
  insertion checks compatibility on both sides.
  - Tests: `test_flow_connection_types.py` (backend), `flow-rf.test.ts` (SDK roundtrip).
5. ✅ **OCR node** (§3) — reimplemented with `ocr_provider` parameter
  (`"textract" | "mistral" | "pymupdf" | "llm"`).
  - `resolve_pdf_binary_ref` helper (`document_binary.py`) locates the input PDF from
  `binary["pdf"]`, the sole PDF-mime ref, or the single binary property.
  - `run_flow_ocr_on_pdf` in `services.py` runs the selected provider on in-memory
  bytes without writing to the document OCR store; `flow_ocr_document_id` tags
  provider logs with the item's `document_id` (falls back to `execution_id`).
  - `ocr_pages_plain_text_list` in `ocr.py` extracts per-page plain text for all four
  OCR formats.
  - `ocr_json` stored as a flow blob via `save_execution_binary_blob` (GridFS
  `flow_blobs`, purged with the execution); falls back to inline `data` in unit tests
  (no real client).
  - `get_revision_pin_blob` endpoint extended to accept `files:` prefix in addition to
  `flow_pins:`, with `_require_flow_pins_key_for_revision` / `_flow_pins_key_authorized_for_revision`
  helpers that also accept cross-revision `pin_data` keys.
  - Frontend: `FlowRevisionPinBlobContext` added to `flowExecutionBlob.ts`; `canFetchFlowBinaryRef` /
  `fetchFlowBinaryRef` route download requests to execution or pin endpoint;
  `IoViewer`, `IoBinaryPanel`, `FlowInputUpstreamList`, `FlowNodeConfigModal` wired.
  - Tests: `test_docrouter_ocr_node.py` (node unit tests), `test_flow_pins_http.py`
  (pin endpoint including `files:` prefix and cross-revision auth),
  `test_flow_execution_blob_http.py` (execution blob roundtrip and error cases).
6. ✅ **LLM run node** (§4) — reimplemented; optional OCR input port (port 1,
  `docrouter.ocr` only); `ocr_pages` automatically injected into prompt context when
   port is connected.
  - `run_flow_llm_run` in `services.py`; SPU billing via `spu_llm_min_for_page_count`
  (`when_empty=1`); `agent_completion` public wrapper used for LLM call.
  - Merge node: wired input slots pre-computed by `merge_wired_input_indices` before
  BFS; engine waits for all wired slots, not just `min_inputs`.
  - Tests: `test_docrouter_llm_node.py`.
7. ✅ **Document Flows section** (§2.8) — engine captures last-node output at execution
  completion when `report_result=true` on the trigger; upsert into `flow_results`
   keyed on `(document_id, flow_id)`; `report_result` stored on `flow_triggers` row at
   activation time; `GET /v0/orgs/{org}/flows?document_id={id}` and
   `GET /v0/orgs/{org}/flows/result/{id}?flow_id=…` REST endpoints;
   Flows tab on document detail page (read-only result viewer).
8. ✅ **Removed `docrouter.trigger.manual`** — document runs go through event trigger +
   `POST …/flows/{flow_id}/run/{document_id}` only; editor testing uses
   `docrouter.trigger` pin data or `flows.trigger.manual` for non-document graphs.
   `POST …/flows/{flow_id}/run` no longer accepts `document_id`.

