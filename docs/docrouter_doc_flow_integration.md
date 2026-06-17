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

Today flows can reference a document through the `docrouter.trigger.manual` node,
but there is no automatic bridge between document lifecycle events and flow
execution.  This plan adds:


| Area         | What we add                                                                                                                                         |
| ------------ | --------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Triggers** | `docrouter.trigger` — single configurable trigger; fires on one of four events: `document.uploaded`, `document.error`, `llm.completed`, `llm.error` |
| **Nodes**    | `docrouter.ocr` — outputs `json.ocr_pages` (array, one entry per page)                                                                              |
| **Nodes**    | `docrouter.llm_run` — optional OCR input port (port 1, `docrouter.ocr` only); auto-injects `ocr_pages` into prompt when connected                   |
| **Nodes**    | `docrouter.map_reduce` — maps each page to a group key (via LLM or keyword rule), reduces into one sub-document per discovered entity               |
| **Nodes**    | `docrouter.save_result` — persists flow output as a named result on the originating document                                                        |
| **Nodes**    | `docrouter.save_as_document` — promotes a flow blob to a new permanent document record                                                              |
| **Blobs**    | Explicit dual-blob support: *document blobs* (`files:` bucket) and *flow blobs* (`flow_blobs:` bucket) both addressable in `BinaryRef.storage_id`   |


---

## 2. DocRouter Event Trigger

### 2.1 Purpose

A single configurable trigger node that fires when a document lifecycle event
occurs.  The `event_type` parameter selects which of four events to listen for:


| `event_type`        | Fires when                                                          |
| ------------------- | ------------------------------------------------------------------- |
| `document.uploaded` | A document is uploaded (or re-tagged, if `include_retagged` is set) |
| `document.error`    | A document enters an error state during processing                  |
| `llm.completed`     | An LLM run finishes successfully for a document                     |
| `llm.error`         | An LLM run fails for a document                                     |


### 2.2 Node key

```
docrouter.trigger
```

### 2.3 Parameter schema


| Parameter    | Type                                                                     | Applicable events            | Description                                                                                        |
| ------------ | ------------------------------------------------------------------------ | ---------------------------- | -------------------------------------------------------------------------------------------------- |
| `event_type` | `"document.uploaded" | "document.error" | "llm.completed" | "llm.error"` | all                          | Required.                                                                                          |
| `tag_ids`    | `array[string]`                                                          | all                          | Optional tag filter — fires if the document has **any** of these tags. Empty = match any document. |
| `prompt_id`  | `string`                                                                 | `llm.completed`, `llm.error` | Optional prompt filter — fires only for this prompt. Empty = any prompt.                           |


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
wiring through intermediate nodes.  Nodes such as `docrouter.save_result` read
`context.trigger_data["document_id"]` directly from this context object rather than
from the propagated `FlowItem`.  A flow whose graph contains no `docrouter.trigger`
node will have `context.trigger_data` set to `None`.

### 2.5 Backend integration points

A single dispatcher function `_dispatch_docrouter_event(org_id, event_type, doc_id, **event_kwargs)` is called from each lifecycle hook:


| Lifecycle hook                               | Event emitted       |
| -------------------------------------------- | ------------------- |
| Upload handler (`app/routes/documents.py`)   | `document.uploaded` |
| Document error path (worker)                 | `document.error`    |
| LLM completion path (`llm/llm.py`)           | `llm.completed`     |
| LLM error path (worker + API route)          | `llm.error`         |


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
    "tag_id": "…",
    "include_retagged": false,
    "prompt_id": "…"
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

---

## 3. OCR Node

### 3.1 Purpose

Standalone OCR step for use in multi-node flows (e.g. before `docrouter.map_reduce`
or when the flow author wants to inspect OCR output separately).

### 3.2 Node key

```
docrouter.ocr
```

### 3.3 Parameter schema


| Parameter      | Type                                         | Required | Description         |
| -------------- | -------------------------------------------- | -------- | ------------------- |
| `ocr_provider` | `"textract" | "mistral" | "pymupdf" | "llm"` | yes      | OCR backend to use. |


### 3.4 Input

- `binary.pdf` — required; raises an error if absent.

### 3.5 Behavior

1. Load `binary.pdf` into memory.
2. Run the selected OCR provider against the PDF bytes (does **not** write to the
   document OCR store — flow-scoped only).
3. Store `ocr_json` as a **flow blob** in GridFS `flow_blobs` keyed to this execution
   (purged when the execution is deleted).
4. Pass `binary.pdf` from the input through to the output unchanged.
5. Emit one output item per input item.

**Implementation notes:**

| Topic | Detail |
| --- | --- |
| `document_id` for Textract | `run_flow_ocr_on_pdf` passes `document_id="flow"` when the input item has no `document_id`. Textract job metadata may show that placeholder instead of a real document id. |
| Provider enum | `OCR_PROVIDERS` in `ocr_node.py` and `FLOW_OCR_PROVIDERS` in `services.py` are duplicated; could be unified later. |

### 3.6 Output

```
json:
  ocr_provider: str        # provider that ran
  ocr_pages:    list[str]  # plain-text per page, one entry per page (0-based)

binary:
  pdf:      BinaryRef      # passthrough
  ocr_json: BinaryRef      # full structured OCR result stored as a flow blob
```

`ocr_pages[N]` is the plain-text of page N.  Downstream nodes (`docrouter.llm_run`,
`docrouter.map_reduce`) read this array from the connected OCR input port.

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


| Port | Index | Required | Connection type   | Description                                          |
| ---- | ----- | -------- | ----------------- | ---------------------------------------------------- |
| main | 0     | yes      | `main`            | Primary data item (trigger output or upstream node). |
| ocr  | 1     | no       | `docrouter.ocr`   | OCR output item carrying `json.ocr_pages`.           |


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

## 5. Map/Reduce Node

### 5.1 Purpose

Given a large multi-entity document (e.g. a batch of patient records, each
identified by name, date of birth, and medical record number), classify each page
to extract a **group key**, then reassemble the pages that share the same key into
a separate sub-document per entity.

This is a map/reduce over pages:

- **Map**: run a classifier on each page to extract a structured group key.
- **Reduce**: group pages by key; reassemble each group into a sub-document PDF.

Groups are discovered **dynamically** from the document content — they do not need
to be declared in advance.

### 5.2 Node key

```
docrouter.map_reduce
```

### 5.3 Concept

```
Input:  one FlowItem  (large multi-entity PDF)      OCR item (required)
            │                                              │
     ┌──────▼───────────────────────────────────────────▼─┐
     │                    map_reduce                        │
     │  map:    page → group key (via LLM or keyword rule)  │
     │  reduce: group pages by key → sub-document per group │
     └──────────────────────────┬──────────────────────────┘
                                │ one item per discovered group
              ┌─────────────────┼────────────────┐
              ▼                 ▼                 ▼
     { name: "J. Smith",  { name: "A. Jones",  { key: null,
       dob: "1980-01-15",   dob: "1992-06-30",   page_indices: [7],
       mrn: "12345" }        mrn: "67890" }       total_pages: 8 }
     pages: [0,1,2]         pages: [3,4,5,6]     (unmatched)
```

### 5.4 Input ports


| Port | Index | Required | Connection type   | Description                                |
| ---- | ----- | -------- | ----------------- | ------------------------------------------ |
| main | 0     | yes      | `main`            | Document item carrying `binary.pdf`.       |
| ocr  | 1     | yes      | `docrouter.ocr`   | OCR output item carrying `json.ocr_pages`. |


### 5.5 Parameter schema


| Parameter              | Type                            | Description                                                                                                                                                                                                                                                                      |
| ---------------------- | ------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `classifier_type`      | `"llm_prompt" | "keyword_rule"` | How to extract the group key from each page.                                                                                                                                                                                                                                     |
| `classifier_prompt_id` | `string`                        | *(LLM only)* Prompt ID. The prompt receives `ocr_pages[N]` for one page and must return a JSON object whose fields form the group key (e.g. `{"patient_name": "…", "dob": "…", "mrn": "…"}`). Pages where the prompt returns `null` or an empty object are grouped as unmatched. |
| `key_fields`           | `array[string]`                 | *(LLM only)* Which fields of the prompt's return object to use as the group key (e.g. `["patient_name", "dob", "mrn"]`). Pages that agree on all key fields are merged into one group.                                                                                           |
| `keyword_rules`        | `array[{key, keywords[]}]`      | *(Keyword only)* Each rule has a `key` string and a list of keywords. First rule whose keywords all appear in `ocr_pages[N]` wins; its `key` becomes the group key for that page.                                                                                                |


### 5.6 Outputs

- Single output port (`outputs: 1`).
- Emits one `FlowItem` per discovered group, in the order the group key first
appears in the document.  Pages that produced no key are collected into a final
unmatched item (omitted if empty).
- Each item:
  ```
  json:
    group_key:    object | null      # extracted key fields, or null for unmatched
    page_indices: [0, 1, 2, …]      # 0-based page numbers in this group
    total_pages:  int                # total pages in the source document
  binary:
    pdf: BinaryRef                   # reassembled sub-document PDF (flow blob)
  ```

### 5.7 Backend implementation notes

- The classifier runs once per page against `ocr_pages[N]` from the OCR input.
- Group keys are compared by value equality across all `key_fields`; field order does not matter.
- Use **PyMuPDF** (`fitz`) to extract page subsets and reassemble per group.
- Reassembled PDFs are stored as flow blobs; use `docrouter.save_as_document` to
  promote them to permanent document records.
- The node returns a `list[FlowItem]` from a single output slot; the engine fans
these out to downstream nodes as a standard multi-item batch.

**Error handling:** if the LLM classifier returns malformed JSON or fails for a page,
that page is treated as unmatched (added to the `group_key: null` group) rather than
failing the entire node.  A keyword-rule classifier that matches no rule also produces
an unmatched page.  If the classifier fails for *all* pages the node raises an error
and the execution fails.

---

## 6. Save Result Node

### 6.1 Purpose

Persist a flow's output as a named result attached to the originating document,
making it visible in a new **Flows** section on the document page alongside the
existing **Prompts** section.  The node reads `document_id` from
`context.trigger_data` — the same mechanism used by the webhook response to
identify the trigger without requiring data propagation through intermediate nodes
— and writes to the `flow_results` collection (§8.2).

### 6.2 Node key

```
docrouter.save_result
```

### 6.3 Parameter schema


| Parameter     | Type     | Description                                                                                                   |
| ------------- | -------- | ------------------------------------------------------------------------------------------------------------- |
| `result_name` | `string` | Display name for this result (e.g. `"Invoice extraction"`). Shown as the row title in the document Flows tab. |

The node always saves the current item's JSON record as the result.  To shape the
data before saving, wire a code node upstream.


### 6.4 Input convention

The node reads `document_id` from `context.trigger_data["document_id"]`, which is
set by the trigger node when the execution starts.  Both `docrouter.trigger` and
`docrouter.trigger.manual` populate `trigger_data.document_id` — the manual trigger
is the primary path for testing flows before activating automatic dispatch.  No
wiring or propagation through intermediate nodes is required — `context.trigger_data`
is available to every node throughout the execution.

**Constraint:** a flow that contains a `docrouter.save_result` node must have either
a `docrouter.trigger` or a `docrouter.trigger.manual` node as a graph ancestor of it
(i.e. reachable by traversing edges upstream from `docrouter.save_result`).
Enforced in two places:

- **Flow editor:** rejects saving the flow with a clear error message.
- **Backend:** `POST /flows/{id}` (save) returns `400` if the constraint is violated,
  so API clients and the SDK cannot bypass it.

### 6.5 Output

Passes the input item through unchanged (passthrough node), so the result can be
wired to further nodes if needed.

```
json:  (same as input)
binary: (same as input)
```

Additionally upserts one `flow_results` document keyed on `(document_id, flow_id, node_id)` — replacing any prior result from this node (see §8.2):

```json
{
  "org_id": "…",
  "document_id": "…",
  "flow_id": "…",
  "node_id": "…",
  "result_name": "…",
  "execution_id": "…",
  "result": { … },
  "created_at": "…"
}
```

### 6.6 Document page — Flows section

The document detail page gains a **Flows** tab.  One row is shown per `(flow_id, node_id)` pair — the latest result only.  Each row shows:

- `result_name` as the row title
- flow name and node name as secondary context (looked up dynamically from the flow record; linked to the flow editor)
- Execution timestamp (linked to the execution trace)
- The `result` JSON rendered with the same viewer used for LLM prompt results

---

## 7. Dual Blob Support

### 7.1 Current state

`BinaryRef.storage_id` already encodes the bucket:


| Prefix                  | Bucket              | Used for                        |
| ----------------------- | ------------------- | ------------------------------- |
| `files:<key>`           | GridFS `files`      | Document PDFs and originals     |
| `flow_blobs:<path>`     | GridFS `flow_blobs` | Intermediate execution data     |
| `flow_pins:<path>`      | GridFS `flow_pins`  | Pinned output overrides         |
| *(none / `data` field)* | In-memory           | Small payloads during execution |


### 7.2 Document blobs vs flow blobs

We formalise the distinction:


| Concept           | Bucket       | Lifetime                                          | Who owns it        |
| ----------------- | ------------ | ------------------------------------------------- | ------------------ |
| **Document blob** | `files`      | Permanent (deleted when document deleted)         | Document lifecycle |
| **Flow blob**     | `flow_blobs` | Execution lifetime; GC'd when execution is purged | Flow execution     |


### 7.3 New node: `docrouter.save_as_document`

To bridge a flow blob back into the document store:

```
docrouter.save_as_document
```


| Parameter        | Type            | Description                                                     |
| ---------------- | --------------- | --------------------------------------------------------------- |
| `binary_key` | `string`        | Key in `item.binary` to promote (default `"pdf"`).                                              |
| `tag_ids`    | `array[string]` | Tags to assign to the new document.                                                             |
| `file_name`  | `string`        | Display name for the new document. If absent, falls back to the original document's file name. |


The new document is created in the same org as the running execution (taken from
the execution context).  It is not associated with the source document that
triggered the flow; it is a fully independent record within the org.

Output: one `FlowItem` with `json.document_id` pointing to the newly created
document record.

### 7.4 Blob resolution in the frontend

`flowExecutionBlob.ts` already resolves `storage_id` via
`GET /v0/orgs/{org}/flows/{flow}/executions/{exec}/blob?storage_id=…`.

The endpoint must be extended to handle `files:<key>` prefixes (today it only
handles `flow_blobs` and `flow_pins`).  Access control: the caller must be a
member of the org that owns the document.

---

## 8. Collections

### 8.1 `flow_triggers` (new)

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

### 8.2 `flow_results` (new)

Stores results written by `docrouter.save_result` nodes.

```json
{
  "_id": "<result_id>",
  "org_id": "…",
  "document_id": "…",
  "flow_id": "…",
  "node_id": "…",
  "result_name": "…",
  "execution_id": "…",
  "result": { },
  "created_at": "…"
}
```

Unique index: `(document_id, flow_id, node_id)` — upsert target; enforces one result per node per document.
Index: `(org_id, document_id)` for fast lookup from the document page.
Index: `(org_id, flow_id)` for listing results by flow.

### 8.3 Deletion cascades


| Delete event               | What is removed                                                                                 |
| -------------------------- | ----------------------------------------------------------------------------------------------- |
| **Flow execution deleted** | `flow_blobs` GridFS entries for that execution (includes `ocr_json` blobs from `docrouter.ocr`) |
| **Document deleted**       | All `flow_results` records with that `document_id`                                              |
| **Flow deleted**           | All `flow_triggers` rows for that `flow_id`; all `flow_results` records for that `flow_id`      |


---

## 9. Implementation Sequence

### 9.0 Migration / cleanup of existing nodes

Before implementing the nodes in this plan, the following existing artifacts must be
renamed or removed to avoid parallel implementations under different names:

| Existing name | Action | Target name (this plan) |
| --- | --- | --- |
| `docrouter.llm_extract` node (backend + frontend) | Rename | `docrouter.llm_run` |
| `docrouter.create_document` in `docrouter_binary.md` | Reconcile or remove | `docrouter.save_as_document` |
| `flow_trigger_registrations` collection (schedule/poll triggers) | Reconcile schema or rename | `flow_triggers` (§8.1) |

These renames should land as a single clean-up commit before any node work begins so
that the codebase uses this plan's names throughout.

### 9.1 Ordered steps

The following order minimises dependency risk:

1. ✅ **Dual blob resolution** (§7.4) — `get_execution_blob` extended to dispatch on
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

5. ✅ **OCR node** (§3) — reimplement; per-page `ocr_pages` array output; flow-blob
   `ocr_json`.

6. **LLM run node** (§4) — reimplement; optional OCR input port (port 1); automatic
   `ocr_pages` injection when port is connected.

7. **`docrouter.save_result` node + document page Flows section** (§6) —
   `flow_results` collection, node backend + registration, REST endpoint
   `GET /v0/orgs/{org}/documents/{id}/flow-results`, Flows tab on document page.

8. **`docrouter.map_reduce` node** (§5) — most complex; depends on OCR being reliable and
   PyMuPDF page extraction.  Ship after steps 1–7 are stable.

9. **`docrouter.save_as_document` node** (§7.3) — convenience bridge; ship together with or
   after map/reduce.

