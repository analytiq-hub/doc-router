# DocRouter Flows — Technical Design Spec (v4)

## 1. Purpose

A **flow** is a saved, reusable processing pipeline represented as a directed
acyclic graph (**DAG**) of **nodes** connected by **edges**.

Flows let users compose multi-step document workflows such as:

- document upload trigger
- OCR
- LLM extraction
- branching / routing
- tagging
- webhooks

This closes the gap between DocRouter's current linear pipeline
(`upload -> OCR -> LLM`) and a configurable graph-based automation layer.

---

## 2. Goals and non-goals

### Goals for v1

- **Python backend only** (API, engine, workers, persistence). **No in-product
  editor UI** in v1; clients may drive flows via HTTP/API and tests.
- Add a reusable flow engine that is independent of DocRouter-specific logic.
- Support versioned flow definitions, manual runs, and durable execution
  (`flow_run` queue + `run_data`).
- Support built-in generic nodes (including **branch**, **merge**, and
  **`flows.code` — in-process code execution** with explicit, test-covered
  semantics) plus DocRouter nodes where needed.
- **Unit tests** (see §18) covering **code execution**, **branch**, and **merge**
  behavior in the engine, without MongoDB/HTTP in the default flow test target.
- Persist execution state and execution history.
- Keep runtime semantics simple and deterministic.

### Non-goals for v1

- In-app / React Flow (or any) **graph editor** — deferred to a **later
  product version** (see §17).
- **Inline expression language** in node parameters (`={{ … }}` style) — not in
  the initial shipped subset; a **concrete pre-UI backend plan** (expressions
  in parameters and in `flows.code`, without n8n-style **TypeScript** code
  nodes) is in **§20**.
- Looping / cycles / re-entrant execution
- Multi-trigger flows
- Sub-flows
- **Strong sandboxing** of code in `flows.code` (e.g. seccomp, WASM, separate
  OS process per node) — v1 may run snippets **in-process** with size/time
  limits; hard isolation is a later concern.
- SSE streaming for execution progress
- Full n8n compatibility
- Execution pause / resume (Wait nodes) — schema fields are reserved
- **Trigger-based automation** (upload / inbound webhook / schedule) may ship
  after v1 core backend; see §18 Phase 3

---

## 3. Architectural split

The implementation is intentionally split into two layers.

### 3.1 Generic flow engine

Package: `analytiq_data/flows/`

Responsibilities:

- flow validation
- node registry
- graph execution (`run_flow` in `engine.py`)
- incremental `run_data` persistence and cooperative stop (`persist_run_data`, `read_stop` in `engine.py`, using `analytiq_client` on the context)
- built-in generic nodes

This package must not import DocRouter-specific code.

### 3.2 DocRouter integration layer

Package: `analytiq_data/docrouter_flows/` (DocRouter nodes + service helpers; not
under `app/` so queue workers can import it without loading FastAPI).

Responsibilities:

- registering DocRouter node types (`register_docrouter_nodes`)
- document fetch / OCR / LLM / tagging integrations (`services.py`)

HTTP routes and queue wiring stay in `app/` (`app/routes/flows.py`, worker
startup), but DocRouter flow *implementations* live next to the generic engine.

This separation keeps the engine reusable and easy to test.

---

## 4. v1 decisions locked in

The following are explicit v1 decisions.

1. Flows are **DAGs only**.
2. A flow has **exactly one trigger node**.
3. A node runs **at most once per execution**.
4. Trigger-based runs execute the revision pinned in
   `flows.active_flow_revid`.
5. Saving a new revision does **not** automatically change the active revision.
6. Runtime state that must survive across executions lives outside the flow
   revision, in a separate collection.
7. Execution history stores **storage-safe** outputs only; large binary payloads
   are referenced, not embedded.
8. `flows.code` is part of **v1 backend** (implemented and covered by unit
   tests), with **restricted semantics** (e.g. in-process, admin/trusted
   parameter surface); it is not a full multi-tenant sandbox.
9. Branch skipping: a node that emits an **empty list** on an output port causes
   all nodes connected to that port to be skipped for this execution.
10. Error-output routing (`on_error = 'continue_error_output'`) is reserved in the
    schema but not required to be implemented in v1 node types.

---

## 5. Storage model

Flows follow the same `{resource}_id` / `{resource}_revid` pattern already used
for prompts and schemas.

### 5.1 `flows` collection (stable header)

One document per logical flow.

```json
{
  "_id": "<flow_id>",
  "organization_id": "<org_id>",
  "name": "Invoice processing",
  "active": false,
  "active_flow_revid": null,
  "flow_version": 3,
  "created_at": "2026-04-22T00:00:00Z",
  "created_by": "<user_id>",
  "updated_at": "2026-04-22T00:00:00Z",
  "updated_by": "<user_id>"
}
```

#### Meaning

- `_id`: stable `flow_id`
- `organization_id`: org scope
- `name`: display name
- `active`: whether trigger-based auto-runs are enabled
- `active_flow_revid`: exact revision currently deployed for trigger-based runs
- `flow_version`: monotonic version counter, incremented on every revision save
- `created_at`, `created_by`: immutable audit fields set at creation
- `updated_at`, `updated_by`: updated on every header or revision change

#### Rules

- Manual runs may default to the latest revision unless the caller provides a
  specific `flow_revid`.
- Trigger-based runs must use `active_flow_revid`.
- Saving a new revision does not change `active_flow_revid`.
- Activating a flow sets both `active = true` and `active_flow_revid`.
- Deactivating a flow sets `active = false` and clears `active_flow_revid`.
- Name-only changes update the header only; they do not create a new revision
  and do not change `flow_version`.

### 5.2 `flow_revisions` collection (immutable graph snapshots)

One document per saved graph revision.

```json
{
  "_id": "<flow_revid>",
  "flow_id": "<flow_id>",
  "flow_version": 3,
  "nodes": [],
  "connections": {},
  "settings": {
    "execution_timeout_seconds": null,
    "error_flow_id": null,
    "save_execution_data": "all"
  },
  "pin_data": null,
  "graph_hash": "<sha256>",
  "engine_version": 1,
  "created_at": "2026-04-22T00:00:00Z",
  "created_by": "<user_id>"
}
```

#### Meaning

- `_id`: revision id (`flow_revid`)
- `flow_id`: parent flow id
- `flow_version`: snapshot version number
- `nodes`: node definitions (see §6.1)
- `connections`: typed adjacency map (see §6.2)
- `settings`: flow-level execution settings (see §5.2.1)
- `pin_data`: optional per-node output overrides keyed by node id (see §5.2.2)
- `graph_hash`: canonical SHA-256 of `{nodes, connections, settings}` for
  deduplication
- `engine_version`: flow-engine semantics version; allows future engine changes
  without breaking old revisions
- `created_at`, `created_by`: audit fields

#### Rules

- Flow revisions are immutable once created.
- Old revisions remain runnable by `flow_revid`.
- Name-only updates do not create a new revision.

#### 5.2.1 `settings` fields

| Field | Type | Default | Meaning |
|-------|------|---------|---------|
| `execution_timeout_seconds` | `int \| null` | `null` | Hard timeout for the entire execution. `null` = no limit. |
| `error_flow_id` | `str \| null` | `null` | Flow ID to trigger automatically when this flow fails (see §13). |
| `save_execution_data` | `"all" \| "none"` | `"all"` | Whether to persist node output in `run_data`. |

#### 5.2.2 `pin_data` semantics

`pin_data` is a per-node output override used for authoring and debug:

```json
{
  "<node_id>": [
    { "json": { "invoice_total": 42.00 }, "binary": {}, "meta": {}, "paired_item": null }
  ]
}
```

When `pin_data[node_id]` is set, the engine **substitutes the pinned items for
the node's live output** and skips actual execution of that node. This lets
authors iterate on downstream nodes without re-running expensive upstream steps.
`pin_data` belongs to the revision because it is tied to a specific graph.

### 5.3 `flow_runtime_state` collection (cross-run persistent state)

State that must survive across runs and across revisions.

```json
{
  "_id": "<state_id>",
  "flow_id": "<flow_id>",
  "organization_id": "<org_id>",
  "node_id": "<node_id>",
  "data": {},
  "updated_at": "2026-04-22T00:00:00Z",
  "updated_by_execution_id": "<exec_id>"
}
```

#### Intended uses

- poll cursors
- last-seen timestamps
- trigger watermarks

#### Rules

- Key by `flow_id + node_id`, not `flow_revid`.
- A new revision inherits the same runtime state unless explicitly reset.

### 5.4 `flow_executions` collection

One document per execution.

```json
{
  "_id": "<exec_id>",
  "flow_id": "<flow_id>",
  "flow_revid": "<flow_revid>",
  "organization_id": "<org_id>",
  "mode": "manual",
  "status": "running",
  "started_at": "2026-04-22T00:00:00Z",
  "finished_at": null,
  "last_heartbeat_at": "2026-04-22T00:00:05Z",
  "stop_requested": false,
  "last_node_executed": null,
  "wait_till": null,
  "retry_of": null,
  "parent_execution_id": null,
  "run_data": {},
  "error": null,
  "trigger": {
    "type": "manual",
    "document_id": null
  }
}
```

#### Field meanings

| Field | Type | Notes |
|-------|------|-------|
| `mode` | `ExecutionMode` | `"manual" \| "trigger" \| "webhook" \| "error" \| "schedule"` |
| `status` | string | `"running" \| "success" \| "error" \| "stopped"` |
| `last_heartbeat_at` | datetime | Updated by the worker every ~5 s. Used for stale-execution detection. |
| `stop_requested` | bool | Cooperative cancellation flag set by the stop endpoint. |
| `last_node_executed` | str? | Node id of the most recently completed node. For debugging. |
| `wait_till` | datetime? | Reserved for future pause/resume. Always `null` in v1. |
| `retry_of` | str? | Reserved: execution id this is a retry of. |
| `parent_execution_id` | str? | Reserved: for future sub-flow calls. |
| `run_data` | dict | Per-node outputs (see §5.4.1). |
| `error` | dict? | Structured error envelope (see §5.4.2). |
| `trigger` | dict | Typed trigger origin (see §5.4.3). |

#### 5.4.1 `run_data` shape

`run_data` maps node id to a `NodeRunData` record:

```json
{
  "<node_id>": {
    "status": "success",
    "start_time": "2026-04-22T00:00:01Z",
    "execution_time_ms": 312,
    "data": {
      "main": [
        [
          { "json": {}, "binary": {}, "meta": {}, "paired_item": null }
        ]
      ]
    },
    "error": null
  }
}
```

`data` mirrors the `NodeOutputData` structure: `{ "main": list_of_output_slots }`.
Each output slot is a list of `FlowItem` objects. Slot index corresponds to the
output port index declared by the node type.

`status` is one of `"success" | "error" | "skipped"`. A node is `"skipped"` when
all of its input ports received empty lists (see §12.3 branch-skipping rule).

#### 5.4.2 `error` envelope

```json
{
  "message": "OCR service returned 503",
  "node_id": "<node_id>",
  "node_name": "Run OCR",
  "stack": "Traceback ..."
}
```

Always a structured object — never a bare string. Set when `status = "error"`.

#### 5.4.3 `trigger` discriminated union

```json
{ "type": "manual",   "document_id": "<doc_id>" }
{ "type": "upload",   "document_id": "<doc_id>", "upload_event_id": "<evt_id>" }
{ "type": "webhook",  "webhook_id": "<wh_id>", "method": "POST",
                      "headers": {}, "body": {} }
{ "type": "schedule", "scheduled_at": "2026-04-22T00:00:00Z" }
{ "type": "error",    "failed_execution_id": "<exec_id>" }
```

#### Stale-execution recovery

At worker startup, and periodically during operation, sweep
`flow_executions` for documents where `status = "running"` and
`last_heartbeat_at < now - 2 × heartbeat_interval`. Mark each such execution
`status = "error"` with `error.message = "Worker crashed or lost heartbeat"`.

---

## 6. Flow definition model

### 6.1 Node shape

```json
{
  "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "name": "Run OCR",
  "type": "docrouter.ocr",
  "position": [240, 300],
  "parameters": {},
  "webhook_id": null,
  "disabled": false,
  "on_error": "stop",
  "retry_on_fail": false,
  "max_tries": 1,
  "wait_between_tries_ms": 1000,
  "notes": "optional"
}
```

#### Node field meanings

| Field | Type | Notes |
|-------|------|-------|
| `id` | string | Stable UUID within the flow. Set at node creation; never changes. |
| `name` | string | Human-readable label, unique within the flow. |
| `type` | string | Node type registry key. |
| `position` | `[int, int]` | Canvas `[x, y]` coordinates. Editor-only; ignored by engine. |
| `parameters` | dict | Type-specific config, validated against the node type's `parameter_schema`. |
| `webhook_id` | `str \| null` | Stable UUID for webhook-trigger nodes. Set at creation; persists across revisions. `null` for all other node types. |
| `disabled` | bool | If `true`, the engine **skips this node and emits empty output on all its ports**, causing all downstream branches to be skipped. |
| `on_error` | `OnError` | Error handling policy (see below). Default `"stop"`. |
| `retry_on_fail` | bool | Retry on failure. Default `false`. |
| `max_tries` | int | Maximum attempts including the first. Default `1`. |
| `wait_between_tries_ms` | int | Delay between retries in ms. Default `1000`. |
| `notes` | `str \| null` | Editor-only annotation; ignored by engine. |

#### `OnError` enum

```python
OnError = Literal["stop", "continue", "continue_error_output"]
```

| Value | Behaviour |
|-------|-----------|
| `"stop"` | Node failure ends the execution with `status = "error"`. |
| `"continue"` | Emit a single error-envelope item on output port 0 and continue. |
| `"continue_error_output"` | Reserved. Emit error item on the dedicated error output port (requires node type to declare it). Not required in v1 implementations. |

### 6.2 Connection types and shape

#### `ConnectionType`

```python
ConnectionType = Literal["main"]
# Extend here as needed, e.g. "error_output" in future.
```

#### `NodeConnection`

```python
@dataclass
class NodeConnection:
    dest_node_id:   str
    connection_type: ConnectionType  # v1: always "main" (per-output-lane)
    index: int                       # destination input slot index
```

#### Adjacency map

Connections are keyed by **source node id** (not name). The destination
`dest_node_id` is the target node id. The save API also accepts legacy keys
`node` / `node_id` and `type` instead of `dest_node_id` / `connection_type` for
the same fields (coerced in `app/routes/flows.py`).

```
NodeOutputSlots  = list[list[NodeConnection] | None]
# Outer index = output slot index.
# Inner list  = fan-out targets from that slot (may be empty).
# None        = slot exists but has no connections (preserves sparse indices).

NodeConnections  = dict[ConnectionType, NodeOutputSlots]
# Usually just {"main": [...]}.

Connections      = dict[str, NodeConnections]
# Top-level map keyed by source node id.
```

Example — one source, two output branches:

```json
{
  "a1b2c3": {
    "main": [
      [{ "dest_node_id": "d4e5f6", "connection_type": "main", "index": 0 }],
      [{ "dest_node_id": "g7h8i9", "connection_type": "main", "index": 0 }]
    ]
  }
}
```

Example — fan-out from one output to two nodes:

```json
{
  "a1b2c3": {
    "main": [
      [
        { "dest_node_id": "d4e5f6", "connection_type": "main", "index": 0 },
        { "dest_node_id": "g7h8i9", "connection_type": "main", "index": 0 }
      ]
    ]
  }
}
```

---

## 7. Export and import

### 7.1 Export format

A flow export is self-contained and includes the flow name for readability.

```json
{
  "flow_id": "<flow_id>",
  "flow_version": 3,
  "name": "Invoice processing",
  "nodes": [],
  "connections": {},
  "settings": {},
  "pin_data": null,
  "created_at": "2026-04-22T00:00:00Z",
  "created_by": "<user_id>"
}
```

### 7.2 Import rules

- If `flow_id` already exists in the org, import creates a new revision under
  that flow.
- If `flow_id` does not exist or belongs to another org, create a new stable
  flow header and remap `flow_id`.
- If imported node ids collide within the destination flow, remap them and
  rewrite `connections` accordingly.
- `webhook_id` values are preserved on import to maintain existing webhook URLs.
  If a `webhook_id` is already registered to a different flow in this org,
  generate a new one and record the remap.

---

## 8. Validation rules

A flow revision is valid only if all of the following hold.

1. `nodes[].id` is unique within the revision.
2. `nodes[].name` is unique within the revision.
3. Every connection source node id exists in `nodes`.
4. Every connection destination `dest_node_id` exists in `nodes`.
5. Every connection destination `index` is within the declared input count of
   the destination node type.
6. Every connection source output slot index is within the declared output count
   of the source node type.
7. The graph is acyclic (topological sort succeeds).
8. The revision contains **exactly one** trigger node
   (a node whose type has `is_trigger = True`).
9. Every non-trigger node is reachable from the trigger node by following edges
   in the `connections` map.
10. Every node's `parameters` validate against its type's `parameter_schema`.
11. `pin_data` keys, if present, refer to node ids that exist in `nodes`.

Validation runs on: create, update, import, activate, and execution startup.

---

## 9. Node registry

### 9.1 `NodeType` protocol

```python
from typing import Protocol, runtime_checkable

@runtime_checkable
class NodeType(Protocol):
    key:              str           # registry key, e.g. "docrouter.ocr"
    label:            str           # display name, e.g. "Run OCR"
    description:      str           # one-line description for UI palette
    category:         str           # palette grouping, e.g. "DocRouter", "Generic"
    is_trigger:       bool          # True for trigger nodes (min_inputs == 0, seeds execution)
    is_merge:         bool          # True for merge-style nodes; engine accumulates inputs before running
    min_inputs:       int           # minimum required input slots (0 for triggers)
    max_inputs:       int | None    # None = unbounded
    outputs:          int           # number of output slots
    output_labels:    list[str]     # human-readable label per output slot, len == outputs
    parameter_schema: dict          # JSON Schema for parameters

    async def execute(
        self,
        context: "ExecutionContext",
        node:    dict,
        inputs:  list[list["FlowItem"]],  # one list per input slot
    ) -> list[list["FlowItem"]]: ...      # one list per output slot

    def validate_parameters(self, params: dict) -> list[str]:
        # Optional cross-field validation beyond JSON Schema.
        # Return a list of error messages; empty list = valid.
        ...
```

`output_labels` example for `flows.branch`: `["true", "false"]`.
`output_labels` example for `docrouter.ocr`: `["output"]`.

### 9.2 Registry API

```python
_registry: dict[str, NodeType] = {}

def register(node_type: NodeType) -> None:
    _registry[node_type.key] = node_type

def get(key: str) -> NodeType:
    if key not in _registry:
        raise KeyError(f"Unknown node type: {key!r}")
    return _registry[key]

def list_all() -> list[NodeType]:
    return list(_registry.values())
```

The engine knows only the registry interface.

---

## 10. Runtime item model

`FlowItem` is the only data structure that crosses a node boundary.

```python
@dataclass
class FlowItem:
    json:        dict
    binary:      dict[str, "BinaryRef"]
    meta:        dict
    paired_item: int | list[int] | None = None
```

### `BinaryRef`

```python
@dataclass
class BinaryRef:
    mime_type:  str
    file_name:  str | None
    data:       bytes | None    # in-memory, not persisted inline in run_data
    storage_id: str | None      # reference for large/persisted payloads
```

### Field semantics

| Field | Notes |
|-------|-------|
| `json` | Primary payload. Every node reads and writes this. |
| `binary` | Named file attachments. Keyed by attachment name (e.g. `"data"`). |
| `meta` | Engine-managed metadata: `source_node_id`, `item_index`, routing hints. Nodes should not mutate `meta`. |
| `paired_item` | Lineage: the index (or indices) of the input item this output item was derived from. Used by future expression support and UI lineage arrows. Nodes should set this when the mapping is 1-to-1 or 1-to-many. |

---

## 11. Node types in v1

### 11.1 Built-in generic nodes

| Key | `is_trigger` | Inputs | Outputs | Output labels | Description |
|-----|-------------|--------|---------|---------------|-------------|
| `flows.trigger.manual` | ✓ | 0 | 1 | `["output"]` | Emits the manual-run seed item. |
| `flows.trigger.webhook` | ✓ | 0 | 1 | `["output"]` | Starts a run when an HTTP request arrives on the registered webhook URL. |
| `flows.trigger.schedule` | ✓ | 0 | 1 | `["output"]` | Starts a run on a cron schedule. |
| `flows.webhook` | ✗ | 1 | 1 | `["output"]` | POSTs item JSON to a configured URL. |
| `flows.branch` | ✗ | 1 | 2 | `["true", "false"]` | Routes items to one of two outputs based on a condition. |
| `flows.merge` | ✗ | 2+ | 1 | `["output"]` | Waits for all inputs, then concatenates them into one output list. |
| `flows.code` | ✗ | 1 | 1 | `["output"]` | Runs a small Python snippet (v1 backend; in-process, test-covered; not a hard sandbox). |

### 11.2 DocRouter nodes

| Key | `is_trigger` | Inputs | Outputs | Output labels | Description |
|-----|-------------|--------|---------|---------------|-------------|
| `docrouter.trigger.manual` | ✓ | 0 | 1 | `["output"]` | Emits the target document as one item. |
| `docrouter.trigger.upload` | ✓ | 0 | 1 | `["output"]` | Fires when a document is uploaded and the flow is active. |
| `docrouter.ocr` | ✗ | 1 | 1 | `["output"]` | Runs OCR on the input document(s). |
| `docrouter.llm_extract` | ✗ | 1 | 1 | `["output"]` | Runs linked prompt-based extraction. |
| `docrouter.set_tags` | ✗ | 1 | 1 | `["output"]` | Applies configured tags. |
| `docrouter.webhook` | ✗ | 1 | 1 | `["output"]` | Sends data through DocRouter's webhook infrastructure. |

### Note on manual trigger nodes

`docrouter.trigger.manual` is a separate node type from `flows.trigger.manual`
with separate semantics: it requires a `document_id` parameter and emits a
document item. Use it explicitly in flows that need document-aware manual runs.

### `flows.trigger.webhook` registration

When a flow containing a `flows.trigger.webhook` node is activated:

1. The engine calls the webhook node's registration hook.
2. A webhook routing record is inserted (see §15).
3. The public URL is `POST /v0/webhooks/{node.webhook_id}`.
4. On deactivation, the routing record is removed.

`node.webhook_id` is set at node creation time and **never changes**, even when
the flow is saved as a new revision or imported. This ensures the webhook URL
remains stable across edits.

### `flows.trigger.schedule` parameters

```json
{
  "cron": "0 2 * * *",
  "timezone": "UTC"
}
```

At activation, the schedule is registered with the scheduler. The scheduler
calls `trigger_dispatch` at each firing time (see §15).

---

## 12. Execution semantics

### 12.1 Module layout

```text
analytiq_data/flows/
  __init__.py
  context.py            ExecutionContext, ExecutionMode
  engine.py             run_flow, validate_revision, FlowValidationError,
                        persist_run_data, read_stop, canonical_graph_hash,
                        _bson_serialize_value, _bson_serialize_run_data
  execution.py          NodeRunData, run_data helpers
  expressions.py        ExpressionError, eval_expression, resolve_parameters,
                        materialize_node_data
  items.py              FlowItem, BinaryRef, coerce_flow_item,
                        coerce_flow_item_list, coerce_binary_ref
  connections.py        NodeConnection, connection_type literal, Connections,
                        coerce_json_connections_to_dataclasses
  node_registry.py      NodeType protocol, register(), get(), list_all()
  register_builtin.py   register_builtin_nodes()
  nodes/
    trigger_manual.py
    webhook.py
    branch.py
    merge.py
    code.py             flows.code subprocess node

analytiq_data/msg_handlers/
  flow_run.py           process_flow_run_msg → ad.flows.run_flow

analytiq_data/docrouter_flows/
  __init__.py
  register.py           register_docrouter_nodes()
  services.py           module-level async helpers (see §12.3)
  nodes/
    manual_trigger_node.py
    ocr_node.py
    llm_node.py
    tag_node.py
```

### 12.2 `ExecutionMode`

```python
ExecutionMode = Literal["manual", "trigger", "webhook", "schedule", "error"]
```

### 12.3 DocRouter integration surface (`analytiq_data/docrouter_flows/services.py`)

The generic engine does **not** know about documents, OCR, or tags. DocRouter
node implementations import **module-level async functions** from
`analytiq_data.docrouter_flows.services`. The first argument is always the
`analytiq_client` (typically `context.analytiq_client`); there is no
`FlowServices` protocol object on the context.

Current helpers include:

- `get_document`, `run_ocr`, `run_llm_extract`, `set_tags`
- `get_runtime_state`, `set_runtime_state` (§5.3)

Outbound HTTP for generic `flows.call_webhook`–style behavior is implemented in
`analytiq_data/flows` (e.g. `nodes/webhook.py` via `httpx`), not through this
module.

Node implementations are tested by stubbing or monkeypatching these functions
or by passing a test `analytiq_client` / mock database layer, depending on the
test style.

### 12.4 `ExecutionContext`

```python
@dataclass
class ExecutionContext:
    organization_id:  str
    execution_id:     str
    flow_id:          str
    flow_revid:       str
    mode:             ExecutionMode
    trigger_data:     dict                    # typed trigger origin (§5.4.3)
    run_data:         dict[str, Any]          # accumulated NodeRunData, written incrementally
    analytiq_client:  Any                     # process client; used by engine + services
    stop_requested:   bool = False
    logger:           Any | None = None
```

`trigger_data` makes the trigger origin (document id, webhook body, scheduled
time) available to all downstream nodes without requiring them to read `run_data`
from the trigger node.

### 12.5 Core execution model

1. Load the exact `flow_revid` to execute.
2. Validate the revision.
3. Build the adjacency maps (source-indexed and destination-indexed).
4. Seed the work queue: create one `(trigger_node, input_slots=[])` work item.
5. **Main loop** — while the work queue is non-empty **or** the merge-waiting map
   is non-empty (see §12.7):
   a. Poll MongoDB for a cooperative stop via `read_stop(context)`; update
      `context.stop_requested`. If set, return `status = "stopped"`.
   b. If the work queue is empty but merge nodes are still waiting, flush those
      merges: enqueue one work item per waiting merge, treating any still-`None`
      slots as empty lists (skipped upstream branches).
   c. Dequeue `(node, input_slots)`.
   d. If `node.disabled`, emit empty output on all ports and continue.
   e. If `pin_data[node.id]` is set, use pinned items as output; skip execution.
   f. If all input slots are empty lists (skipped inputs), mark node `"skipped"`,
      emit empty output on all ports, continue. (Branch-skipping rule.)
   g. Call `node_type.execute(context, node, input_slots)`.
   h. On error: apply `node.on_error` policy (stop, continue, or continue_error_output).
   i. Write `NodeRunData` to `context.run_data[node.id]` and call
      `persist_run_data(context, run_data)` (incremental Mongo `flow_executions`
      update).
   j. For each output slot `i`:
      - If the output list is non-empty: enqueue all nodes connected to slot `i`
        with the corresponding items as their input.
      - If the output list is empty: do **not** enqueue connected nodes.
        (This is the branch-skipping rule — see §4 decision 9.)
   k. For merge nodes: accumulate inputs in a waiting map; enqueue when the
      prefix covering at least the merge type’s `min_inputs` has no `None` left
      (see §12.7). Otherwise leave the merge in the waiting map.
6. Mark execution `success` (or `error` if any node failed with `on_error = "stop"`).

### 12.6 Fan-out semantics

When output slot `i` has multiple connections (fan-out), each downstream node
receives the **same item list** as its own independent input. Downstream nodes
run sequentially (not in parallel) in v1. The order of processing is
breadth-first by connection order.

### 12.7 Merge semantics

`flows.merge` runs after each input slot has a defined list of items. It
concatenates all input-slot item lists into one output list. The order is by
input slot index ascending.

The merge waiting map is analogous to n8n's `waitingExecution`:
`dict[node_id, list[list[FlowItem] | None]]`. A slot is `None` until data
arrives. The node is enqueued as soon as every slot in the **prefix** checked
by the engine (length `max(node_type.min_inputs, 1)`) is non-`None` (the built-in
merge has `min_inputs = 2`).

If the work queue would otherwise be empty and merge nodes are still waiting
(typically after skipped upstream branches that never send into every slot), the
engine **flushes** them: the merge is enqueued with any remaining `None` slots
treated as empty lists, then executed under the normal rules.

### 12.8 Error handling

If `on_error = "stop"` (default):

- Node failure ends the execution with `status = "error"`.
- `flow_executions.error` is populated with the structured error envelope.

If `on_error = "continue"`:

- Emit a single error-envelope item on output port 0.
- Continue downstream execution.

Error envelope item:

```json
{
  "json": {
    "_error": {
      "node_id": "<node_id>",
      "node_name": "Run OCR",
      "message": "..."
    }
  },
  "binary": {},
  "meta": {},
  "paired_item": null
}
```

### 12.9 Stop semantics

- Stop is cooperative, not preemptive.
- The stop endpoint sets `flow_executions.stop_requested = true`.
- Before each dequeued node, `read_stop` reloads the execution document and
  updates `context.stop_requested` (see §12.5 step 5a). If set, `run_flow`
  returns with `status = "stopped"`.
- v1 does not attempt to hard-kill in-flight node code.

### 12.10 Execution timeout

If `settings.execution_timeout_seconds` is set, the worker wraps
`analytiq_data.flows.run_flow(...)` in `asyncio.wait_for(..., timeout=N)`. On
timeout, the execution is marked `status = "error"` with
`error.message = "Execution timed out"`.

---

## 13. Error flow triggering

When `flow_executions.status` transitions to `"error"` and
`settings.error_flow_id` is set:

1. Check that `error_flow_id` ≠ current `flow_id` (loop protection).
2. Check that current `mode` ≠ `"error"` (loop protection).
3. Enqueue a new execution of `error_flow_id` with `mode = "error"` and
   `trigger = { "type": "error", "failed_execution_id": "<exec_id>" }`.
4. The trigger node of the error flow receives the failed execution's error
   envelope as its seed item.

---

## 14. API design

FastAPI route file: `app/routes/flows.py`

### 14.1 Routes

| Method | Path | Purpose |
|--------|------|---------|
| `POST` | `/v0/orgs/{org_id}/flows` | Create a flow |
| `GET` | `/v0/orgs/{org_id}/flows` | List flows (latest revision per flow) |
| `GET` | `/v0/orgs/{org_id}/flows/{flow_id}` | Get one flow header + active revision info |
| `PATCH` | `/v0/orgs/{org_id}/flows/{flow_id}` | Update name only (no new revision) |
| `PUT` | `/v0/orgs/{org_id}/flows/{flow_id}` | Save a new revision |
| `DELETE` | `/v0/orgs/{org_id}/flows/{flow_id}` | Delete flow + revisions + runtime state + executions |
| `GET` | `/v0/orgs/{org_id}/flows/{flow_id}/revisions` | List revisions |
| `GET` | `/v0/orgs/{org_id}/flows/{flow_id}/revisions/{flow_revid}` | Get a specific revision |
| `POST` | `/v0/orgs/{org_id}/flows/{flow_id}/activate` | Activate a revision |
| `POST` | `/v0/orgs/{org_id}/flows/{flow_id}/deactivate` | Deactivate the flow |
| `POST` | `/v0/orgs/{org_id}/flows/{flow_id}/run` | Start a manual run |
| `GET` | `/v0/orgs/{org_id}/flows/{flow_id}/executions` | List executions |
| `GET` | `/v0/orgs/{org_id}/flows/{flow_id}/executions/{exec_id}` | Get execution detail |
| `POST` | `/v0/orgs/{org_id}/flows/{flow_id}/executions/{exec_id}/stop` | Request stop |
| `GET` | `/v0/orgs/{org_id}/flows/node-types` | List node type descriptors |
| `POST` | `/v0/webhooks/{webhook_id}` | Inbound webhook trigger (outside org path) |

### 14.2 Pagination

All list endpoints accept:

| Query param | Default | Notes |
|-------------|---------|-------|
| `limit` | `50` | Max items per page. |
| `offset` | `0` | Skip this many items. |

Response includes `{ "items": [...], "total": N }`.

### 14.3 Save request (`PUT`)

```json
{
  "base_flow_revid": "<flow_revid>",
  "name": "Invoice processing",
  "nodes": [],
  "connections": {},
  "settings": {}
}
```

#### Save rules

- `base_flow_revid` is required.
- If `base_flow_revid` is not the current latest revision, return `409 Conflict`.
- If only the name changes and `graph_hash` is unchanged, treat as a name-only
  update (update header only; do not create a revision; return `200` not `201`).
- Otherwise create a new revision, increment `flow_version`, return `201`.

### 14.4 Name-only update (`PATCH`)

```json
{ "name": "New name" }
```

Updates `flows.name`, `flows.updated_at`, `flows.updated_by`. Does not create a
revision. Returns `200`.

### 14.5 Activate request

Optional body:

```json
{ "flow_revid": "<optional>" }
```

If omitted, activates the latest revision. Validates the target revision before
activating. Registers webhooks and schedules.

### 14.6 Run request

```json
{
  "flow_revid": "<optional>",
  "document_id": "<optional>"
}
```

`flow_revid` defaults to the latest revision for manual runs. `document_id` is
passed as `trigger_data.document_id` and made available to trigger nodes.

---

## 15. Trigger dispatch and webhook routing

### Trigger dispatch

On a trigger event (upload, schedule, webhook), the dispatcher must:

1. Query `flows` for all documents where `active = true` and `organization_id`
   matches (and trigger type matches).
2. For each match, read `active_flow_revid`.
3. Enqueue a `flow_run` worker message.

Implementation choices for the active-flow index:

- Direct MongoDB query (simple; acceptable for v1).
- In-memory index refreshed on activate/deactivate (faster; add later if needed).

Regardless of implementation, dispatch must resolve the exact `active_flow_revid`.

### Webhook routing table

The webhook routing table maps `webhook_id → (flow_id, active_flow_revid)`.

- Populated at activation; cleared at deactivation.
- Stored in MongoDB (collection `flow_webhook_routes`) **and** cached in memory.
- Cache is invalidated on activate/deactivate.

Schema:

```json
{
  "_id": "<webhook_id>",
  "flow_id": "<flow_id>",
  "organization_id": "<org_id>",
  "flow_revid": "<flow_revid>",
  "node_id": "<node_id>",
  "method": "POST",
  "created_at": "2026-04-22T00:00:00Z"
}
```

The inbound route `POST /v0/webhooks/{webhook_id}`:

1. Look up `webhook_id` in cache → `flow_id`, `flow_revid`, `node_id`.
2. Build trigger data from request (method, headers, body).
3. Enqueue `flow_run` worker message.
4. Return `200 { "execution_id": "..." }` immediately (async).

---

## 16. Worker integration

Queue-dispatched runs use the existing worker infrastructure.

### Queue payload

```python
await ad.queue.send_msg(analytiq_client, "flow_run", {
    "flow_id":         flow_id,
    "flow_revid":      flow_revid,
    "execution_id":    exec_id,
    "organization_id": org_id,
    "trigger":         {"type": "manual", "document_id": "..."},
})
```

(`trigger` matches `flow_executions.trigger` and is copied into
`ExecutionContext.trigger_data` by the handler.)

### Worker rules

- Handler: `analytiq_data.msg_handlers.process_flow_run_msg` loads the
  revision, builds an `ExecutionContext` (including `analytiq_client`), and
  runs `analytiq_data.flows.run_flow`.
- Execute the exact `flow_revid` from the queue message. Never re-resolve "latest".
- **Compare-and-set claim**: before calling `run_flow`, update the execution document
  with filter `{"status": "queued"}`. If `matched_count == 0` the message was already
  claimed by another worker; delete it and return.
- **Heartbeat**: an `asyncio.Task` (`_heartbeat_loop`) is started immediately after the
  claim and cancelled in a `finally` block after `run_flow` returns. It wakes every
  `HEARTBEAT_INTERVAL_SECS` (5 s) and writes `last_heartbeat_at` to MongoDB. This
  ensures liveness is maintained even during a single long-running node (e.g. a slow
  `flows.code` subprocess), not just at node boundaries.
- Cooperative stop: `read_stop` between node executions (see §12.9).
- On completion (success or error), set `finished_at` and final `status`.
- On startup, sweep for stale executions (see §5.4 stale-execution recovery).

### Progress model (v1 backend)

Any client (tests, scripts, or a **future** UI) may poll
`GET /v0/orgs/{org_id}/flows/{flow_id}/executions/{exec_id}`.
Incremental `run_data` written after each node provides per-node progress.

---

## 17. Frontend canvas (deferred past v1)

**v1 does not include** an in-product flow editor. The following targets a
**later version** once the backend and `flows.code` tests are stable.

React Flow is a likely choice for the editor when UI work starts.

### Proposed structure

```text
src/app/orgs/[orgId]/flows/
src/app/orgs/[orgId]/flows/[flowId]/
src/components/flows/
  FlowCanvas.tsx
  FlowNodeTypes.tsx
  FlowParameterPanel.tsx
  FlowRunPanel.tsx
  useFlowEditor.ts
  useFlowRun.ts
```

### UI requirements

- Prevent obviously invalid saves where possible (client-side validation).
- Show backend validation errors clearly.
- Show stale-editor conflicts (`409 Conflict`).
- Show both latest revision and active revision.
- Show execution history and per-node output/status.
- Label output wires with `output_labels` from the node type descriptor.
- Display `on_error` setting per node in the parameter panel.

---

## 18. Implementation plan

### Phase 1 — Core engine (`analytiq_data/flows/`) — **Complete**

All steps below are implemented and covered by `tests_flow/`.

**Step 1.1 — Types and items** ✓
Files: `items.py`, `connections.py`
- `FlowItem`, `BinaryRef` dataclasses
- `NodeConnection` (`dest_node_id`, `connection_type: Literal[“main”]`, `index`), `Connections` map type

**Step 1.2 — Node registry** ✓
File: `node_registry.py`
- `NodeType` Protocol (including `is_merge: bool` — see §9.1)
- `register()`, `get()`, `list_all()`

**Step 1.3 — Validation + engine** ✓
Files: `engine.py`, `execution.py`, `context.py`
- `validate_revision` / `FlowValidationError` — all 11 rules from §8; unknown
  node types raise `FlowValidationError` (not `KeyError`)
- `run_flow` wraps `_execute_loop` with optional `asyncio.wait_for`
- `_execute_loop` uses `collections.deque` for O(1) pop; `start_datetime`
  captured before execution; merge detection via `is_merge` (not key string);
  merge-slot list extended rather than reset on growth; `float(timeout)` not `int`
- `ExecutionContext` in `context.py`

**Step 1.4 — Built-in generic nodes + registration** ✓
Files: `register_builtin.py`, `nodes/{trigger_manual,webhook,branch,merge,code}.py`
- All five node types registered by `register_builtin_nodes()`
- Every node class sets `is_trigger` and `is_merge`

**Step 1.5 — `flows.code` (v1)** ✓
File: `nodes/code.py`, `code_runner.py`
- Runs a Python snippet in a separate subprocess (`sys.executable -I -S`)
- JSON stdin/stdout contract; safe builtins (no `__import__`)
- `_minimal_env()` passes only `PATH`
- Subprocess context: `{“trigger”, “node_id”, “mode”, “nodes”, “organization_id”, “execution_id”, “flow_id”, “flow_revid”}` (§20.4 Option B already implemented)

**Step 1.6 — Expression engine** ✓  (§20.3)
File: `expressions.py`
- `ExpressionError(ValueError)` for validation and evaluation failures
- `_rewrite_vars`: `$json` → `_json`, `$node` → `_node`
- `_validate_expr_ast`: walks AST, rejects any node type not in explicit allow-set; `ast.Call` is excluded from the allow-set; names starting with `__` are rejected
- `eval_expression(expr, *, item, run_data)`: parses, validates AST, evaluates with `{“__builtins__”: {}}` and `{_json, _node}` in scope
- `resolve_parameters(params, *, item, run_data)`: recursively resolves `=`-prefixed strings, passes everything else through unchanged
- `materialize_node_data(run_data)`: flattens `FlowItem` objects to their `.json` dicts for use in expression scope and subprocess context

**Step 1.7 — Pin-data hardening** ✓  (§20.6)
File: `items.py`
- `coerce_binary_ref(raw) -> BinaryRef`: strict type-checking; raises `ValueError` on invalid fields
- `coerce_flow_item(raw) -> FlowItem`: accepts `FlowItem` (no-op) or `dict`; raises `ValueError` on invalid fields (consistent with `FlowValidationError` / `ExpressionError` which are both `ValueError` subclasses)
- `coerce_flow_item_list(raw) -> list[FlowItem]`: accepts `None` (→ `[]`) or list
- `coerce_json_connections_to_dataclasses(raw)` in `connections.py`: converts MongoDB dict connections to `NodeConnection` dataclasses; handles legacy field names (`node`/`node_id`/`node`)

**Tests: `packages/python/tests_flow/`**

```
tests_flow/
  conftest.py            Ensures `packages/python` is on `sys.path`
  test_flows_engine.py   Validation (DAG accept, cycle reject) + run_flow
                         (code node output, branch/merge skip flush)
  test_expressions.py    $json / $node resolution, on_error continue path,
                         unsafe-call rejection, pin_data visible via $node
```

Run: `pytest packages/python/tests_flow/` (no MongoDB required; `analytiq_client=None`).

---

### Phase 2 — DocRouter integration (implemented: routes, services, nodes, worker)

**Collections / persistence**
- Flow CRUD, revisions, and executions: Motor queries in `app/routes/flows.py`
  (no separate `app/flows/db.py`).

**Routes**
- `app/routes/flows.py` — HTTP API from §14 (as wired in `app/main.py`).

**Services**
- `analytiq_data/docrouter_flows/services.py` — module-level async helpers using
  `analytiq_client` (see §12.3).

**DocRouter nodes + registration**
- `analytiq_data/docrouter_flows/nodes/{manual_trigger_node,ocr_node,llm_node,tag_node}.py`
- `analytiq_data/docrouter_flows/register.py` — `register_docrouter_nodes()` (also
  available as `ad.flows.register_docrouter_nodes`, a thin wrapper in
  `analytiq_data/flows/__init__.py`)

**Queue worker**
- `worker/worker.py` — `worker_flow_run` consumes `flow_run` messages
- `analytiq_data/msg_handlers/flow_run.py` — `process_flow_run_msg` →
  `ad.flows.run_flow`

**Tests**
- `packages/python/tests/test_flows_e2e.py` — `TestClient` + per-test Mongo (`test_db`):
  create/save a revision, `POST /run` (queued execution + `queues.flow_run` message), then
  `process_flow_run_msg` with the in-process app client (the background `flow_run` worker is
  stubbed in that module to avoid a stale-`ENV` database mismatch; production uses
  `worker_flow_run` → the same handler). Asserts on `flow_executions` and `GET .../executions/...`.

---

### Phase 3 — Deferred (post–v1 backend)

- **Frontend / React Flow canvas** and in-app editor UX (see §17).
- `flows.trigger.webhook` (inbound webhook route, routing table)
- `flows.trigger.schedule` (cron registration)
- `docrouter.trigger.upload` (upload event dispatch)

---

### Implementation order within phases

Phase 1: `1.1 → 1.2 → 1.3 → 1.4 → 1.5` — keep `make tests-flow` green; expand
`tests_flow` until branch, merge, and `flows.code` execution are covered.

Phase 2: register DocRouter node types and services before relying on
production routes; keep `process_flow_run_msg` and `run_flow` in sync when
execution semantics change.

---

## 19. Main improvements from v3

- Added `ConnectionType` literal and `NodeConnection` (`dest_node_id`,
  `connection_type`, `index`); adjacency map types fully specified.
- Defined `run_data` shape (`NodeRunData` with status, timing, items, error).
- Typed `flow_revisions.settings` with `execution_timeout_seconds`,
  `error_flow_id`, `save_execution_data`.
- Replaced `continueOnFail: bool` with `on_error: OnError` enum on node shape.
- Added `mode`, `last_node_executed`, `last_heartbeat_at`, `wait_till`,
  `retry_of`, `parent_execution_id` to `flow_executions`.
- Typed `trigger` field as a discriminated union.
- Defined `pin_data` execution semantics explicitly (§5.2.2).
- Defined `disabled` node semantics explicitly (emit empty output, skip branches).
- Defined branch-skipping rule explicitly: empty output → skip connected nodes.
- Added `paired_item` to `FlowItem` for lineage tracking.
- `ExecutionContext` uses `analytiq_client` and `mode` + `trigger_data` (no
  `FlowServices` object; DocRouter helpers live in
  `analytiq_data/docrouter_flows/services.py`).
- Engine entry points: `run_flow`, `persist_run_data`, `read_stop` in
  `analytiq_data/flows/engine.py`.
- Added `is_trigger`, `output_labels`, `description`, `category`,
  `validate_parameters` to `NodeType` protocol.
- Added `webhook_id` to node shape; added `flows.trigger.webhook` and
  `flows.trigger.schedule` to the node table with registration semantics.
- Fixed validation rule 10: "reachable from trigger" (not "no disconnected subgraphs").
- Added validation for `connections.index` bounds and `pin_data` key references.
- Added `created_at`/`created_by` to `flows` collection.
- Added stale-execution recovery via heartbeat.
- Added `GET /flows/{flow_id}`, `PATCH /flows/{flow_id}`, pagination, webhook
  inbound route, `GET /flows/{flow_id}/revisions` to the API table.
- Added §13 (error flow triggering) and §15 (webhook routing table).
- Merged §14 worker integration with heartbeat and stale-execution rules.

---

## 20. n8n comparison and pre-UI backend backlog

This section compares the **current DocRouter flows backend** to the n8n
reference (`docs/n8n.md` and the upstream n8n TypeScript tree when needed) and
lists **what is already implemented**, **what is still missing** before a
first-class **UI** (see §17), and a **suggested implementation order**. It does
**not** require TypeScript/JavaScript code nodes; Python remains the only
in-product code path.

### 20.1 Feature matrix (user-facing capabilities)

| Capability | n8n (see `docs/n8n.md`) | DocRouter today | Verdict |
|------------|-------------------------|-----------------|--------|
| **TypeScript / JS code node** | Yes (`Code.node.ts`, task runner) | Not present (out of product scope) | **Skip** — we keep Python-only `flows.code`. |
| **Python code node** | Yes (separate task runner) | Yes — `flows.code` runs a subprocess with JSON items + context | **Have** — extend **context** when expressions land (§20.4). |
| **Expressions in string parameters** | Yes — `={{ … }}` via `WorkflowDataProxy` + `WorkflowExpression` (§19 in `n8n.md`) | **No** — parameters are used as static JSON after schema validation | **Add** before UI (§20.3, §20.4). |
| **“Between nodes” / wiring data** | n8n does **not** put expressions on connection objects; the **downstream node’s parameters** reference upstream output via `$node[…]`, `$json`, etc. (same engine as other params) | No expression resolution anywhere | **Add** the same *mental model*: **per-item parameter resolution** using current item + prior `run_data` (optional: dedicated **Set / Edit Fields** node later; edge-attached transforms are *not* required for parity with n8n’s core model). |
| **Expressions inside `flows.code` (Python)** | Code node is separate from expressions; n8n JS code uses `$input`, etc. | `run_python_code` gets a **fixed** `context` dict (trigger, ids, mode, …) — no `$node` / templated param strings | **Add** after parameter expressions: inject an **evaluated** `context` and/or allow selected parameters to be pre-resolved expression strings (§20.4). |
| **Same node type used multiple times in one flow** | Yes — unique **name** per node, same `type` many times | Yes — `nodes[].id` and `nodes[].name` must be **unique**; `type` may repeat (e.g. two `flows.code` nodes) | **Supported** — no change required; the UI just needs distinct labels/ids. |
| **Pin data (mock node output, skip execution)** | `pinData` on workflow; engine substitutes | **Spec + API + engine**: `flow_revisions.pin_data` validated; `run_flow` uses pinned list as output **without** `execute` | **Mostly have** — **hardening** likely needed: items coming from JSON/API should be **coerced to `FlowItem` / `BinaryRef`** before the inner loop (today the engine may pass through raw `dict` structures; any node that assumes `FlowItem` attributes can break). **Add** coercion + unit tests. |
| **User-defined node types via API, stored in DB** | Community nodes ship as code packages; n8n Cloud differs | Node types only exist in **code** — `ad.flows.register(…)` at process startup | **Missing** — new collection, CRUD API, and loader that **merges** with builtins (§20.5). |

### 20.2 What the backend already provides (summary)

- **Versioned graph**: `flows` + `flow_revisions` (nodes, `connections`, `settings`, `pin_data` field).
- **Execution**: `flow_executions`, `run_data`, `queues.flow_run`, `process_flow_run_msg` → `run_flow`.
- **Registry (built-in + DocRouter)**: `register_builtin_nodes`, `register_docrouter_nodes` — `NodeType` protocol, JSON Schema on `parameters`, `validate_revision`, DAG + merge behavior, branch skip, `disabled`, `on_error` where implemented.
- **Multiplicity of types per flow**: multiple nodes may share the same `type` key; identity is `id` + `name`.

### 20.3 Plan: parameter expressions (n8n-style, Python backend)

**Goal:** For each **string** field in a node’s `parameters`, support a
**literal** value or a **templated** value evaluated before `execute()` runs,
analogous to n8n’s `={{ $json.field }}` / `$node[…]`.

#### Design

**New file: `analytiq_data/flows/expressions.py`**

1. **Surface syntax** — A string parameter value starting with `=` is an
   expression; everything else is a literal. Matches n8n’s single-cell `=`
   convention.

2. **Variables in scope:**
   - `$json` — current item’s `.json` dict (or `{}` if the node has no input).
   - `$node` — a plain `dict` keyed by node id; each value is
     `{“main”: [[item_json, …], …], “status”: “…”}` with `FlowItem` objects
     already materialized to their `.json` dicts. Only completed nodes appear.

   `$json` and `$node` are preprocessed to valid Python identifiers (`_json`,
   `_node`) before `ast.parse`.

3. **Safety** — Parse with `ast.parse(mode=’eval’)`. Walk the AST and reject
   any node type not in an explicit allow-set. Allowed: `Constant`, `Name`,
   `Attribute`, `Subscript`, `BinOp`, `UnaryOp`, `BoolOp`, `Compare`,
   `IfExp`, `Slice`, `List`, `Tuple`, `Dict`. **`ast.Call` is not in the
   set** — no function calls. Evaluate with
   `eval(compiled, {“__builtins__”: {}}, env)`. Wrap in `ExpressionError`
   on failure.

4. **`resolve_parameters(params, *, item, run_data) -> dict`** — walks the
   params dict recursively, evaluates `=`-prefixed strings, passes everything
   else through unchanged. Lists and nested dicts are resolved recursively.

5. **Integration in `_execute_loop`** — inside the existing `try` block, just
   before `node_type.execute()`:
   ```python
   first_item = next((it for slot in wi.inputs for it in slot), None) if wi.inputs else None
   resolved_node = {**node, “parameters”: resolve_parameters(
       node.get(“parameters”) or {}, item=first_item, run_data=context.run_data)}
   out_lists = await node_type.execute(context, resolved_node, wi.inputs)
   ```
   The original node dict is not mutated. Expression errors respect `on_error`
   because they are raised inside the existing `except Exception` block.

6. **Limitation (document):** expressions resolve against the *first* input
   item, because `execute()` receives all items at once. Per-item resolution
   would require changing the `NodeType.execute` signature and is deferred.

**Tests to add in `tests_flow/test_expressions.py`:**
- `=$json[“x”]` resolves against item json
- `=$node[“t1”][“main”][0][0][“trigger”][“x”]` resolves from prior run_data
- Undefined key raises `ExpressionError` → caught by `on_error`
- Unsafe construct (`=__import__(‘os’)`) rejected before eval
- `pin_data`-pinned outputs are visible via `$node` as if the node had run

**”Between nodes”:** Parameter-side resolution (above) matches n8n’s model.
Edge-attached transforms are not required for parity and are not planned.

### 20.4 Plan: expressions + `flows.code`

Both options below apply simultaneously; they are independent changes.

- **Option A — parameter expressions (same as any other node):** The
  `python_code` string parameter is a literal (not an expression — a code string
  starting with `=` would be a syntax error anyway). Other parameters on the
  `flows.code` node (e.g. a future `timeout_seconds` override) can use `=`
  expressions normally via the §20.3 resolver. No special handling required.

- **Option B — enriched subprocess context (implement alongside §20.3):** Add a
  `"nodes"` key to the context dict passed to `run_python_code`, populated from
  `materialize_node_data(context.run_data)` (the same helper used by §20.3):
  ```python
  ctx = {
      "trigger": context.trigger_data,
      "node_id": node.get("id"),
      "mode": context.mode,
      "nodes": materialize_node_data(context.run_data),
  }
  ```
  This lets user snippets access prior node outputs:
  ```python
  def run(items, context):
      text = context["nodes"]["ocr1"]["main"][0][0].get("text", "")
  ```
  The subprocess still receives only JSON-serializable data; no expression
  engine inside the sandbox.

- **Out of scope:** Re-implementing n8n’s in-sandbox JavaScript Code node APIs;
  keep one clear Python `run(items, context)` contract.

### 20.5 Plan: dynamic node types (API + MongoDB) — **Deferred; needs design first**

**Goal:** Orgs can **register** new node *definitions* without redeploying the
API, with definitions persisted in MongoDB and merged into the same execution
path as built-ins.

**Why deferred:** Requires a new collection, CRUD routes, a startup loader,
`validate_revision` changes to accept dynamic keys, and a security model for
what implementations are allowed. This is ~2–3 days of work and should be
planned as a separate ticket once §20.3 is stable.

**Agreed shape (for the ticket):**

1. **Collection `flow_node_type_definitions`** — fields: `organization_id`,
   `key` (unique per org), `version`, `label`, `description`, `category`,
   `parameter_schema` (JSON Schema), `min_inputs`, `max_inputs`, `outputs`,
   `output_labels`, `is_trigger`, `is_merge`, and an **`implementation`**
   discriminated union:
   - `http_proxy` — outbound HTTP call with URL/headers/body as expression
     strings (§20.3); the only v1 implementation type.
   - `invoke_internal` — delegates to an existing built-in key with fixed
     behavior (useful for aliasing).
   - Future: `wasm` / `remote_plugin` — not in v1.

2. **API** — CRUD under `/v0/orgs/{org_id}/flows/node-types` (admin-only);
   list endpoint merges DB-defined and built-in types.

3. **Loader** — On API/worker startup and after any write: load org-visible
   definitions, instantiate wrapper `NodeType` classes, call `register()`.
   Cache invalidation: re-load on write; per-execution re-fetch is not needed.

4. **Validation** — `validate_revision` already calls `ad.flows.get(type)`;
   the loader ensures dynamic types are registered before validation runs.

5. **Security** — Never execute raw Python from DB. Default to declarative
   `http_proxy` only. Add rate limits and audit log before shipping.

### 20.6 Plan: `pin_data` hardening (blocking for trustworthy UI)

**Gap:** Pin data stored in MongoDB comes back as plain `dict`s. The engine
passes them unchanged to downstream nodes; any node that accesses `.json`,
`.binary`, or `.meta` as attributes gets `AttributeError`.

1. **Coercion functions** — Add to `items.py`:
   - `coerce_binary_ref(raw) -> BinaryRef`
   - `coerce_flow_item(raw) -> FlowItem` — accepts `FlowItem` (no-op) or `dict`
     (maps `json`, `binary`, `meta`, `paired_item` fields; coerces binary refs)
   - `coerce_flow_item_list(raw) -> list[FlowItem]`

2. **Call site** — One line change in `_execute_loop`, pin_data branch:
   ```python
   pinned = coerce_flow_item_list(pin_data[node["id"]] or [])
   out_lists = [pinned] + [[] for _ in range(outputs_count - 1)]
   ```

3. **Tests** — Add to `tests_flow/`:
   - Pin a node with raw dict items; assert downstream `flows.code` sees
     `FlowItem` with correct `.json`.
   - Pin with a binary ref dict; assert `BinaryRef` fields are set correctly.

### 20.7 Suggested implementation order (before UI)

| Step | Section | Effort | Depends on | Status |
|------|---------|--------|------------|--------|
| 1 | **Pin data coercion + tests** (§20.6) | ~1 h | — | **Complete** (Phase 1 Step 1.7) |
| 2 | **Expression engine v1** (§20.3) | ~1 day | — | **Complete** (Phase 1 Step 1.6) |
| 3 | **`flows.code` enriched context** (§20.4 Option B) | ~1 h | §20.3 (`materialize_node_data`) | **Complete** (Phase 1 Step 1.5) |
| 4 | **Dynamic node types** (§20.5) | ~2–3 days | §20.3 (expressions in `http_proxy`) | Needs design ticket |

After steps 1–3 the backend is in a good position to support the **canvas UI**
(§17) with n8n-like authoring patterns without copying every n8n internal
(queue, webhooks, credentials) — those remain incremental Phase 3 work.
