# DocRouter Flows — Architecture and Implementation Guide

A **flow** is a saved, reusable automation pipeline: a directed acyclic graph
(DAG) of **nodes** connected by **edges**. Flows let users compose multi-step
document workflows (upload → OCR → LLM extraction → tagging → webhook) that run
reliably in the background, with durable execution state and per-node output
stored in MongoDB.

This document is the definitive guide for someone new to the codebase. It covers
what we built, how it maps to n8n's architecture, what is already running, and
what is still on the roadmap.

---

## 1. How this relates to n8n

We modelled DocRouter flows on n8n's execution model (see `docs/n8n.md`) while
keeping it Python-native and much simpler. The table below maps the key concepts.

| n8n concept | n8n location | DocRouter equivalent | Notes |
|-------------|-------------|---------------------|-------|
| `IWorkflowBase` / `WorkflowEntity` | `packages/workflow/src/Interfaces.ts` | `flows` + `flow_revisions` collections | We split the stable header from the immutable graph snapshot |
| `INode` | `Interfaces.ts` | `nodes[]` in revision | Same shape; we key edges by node **id** not name |
| `IConnections` / `IConnection` | `Interfaces.ts` | `Connections` / `NodeConnection` | Same three-level structure: source → type → output-slot → fan-out list |
| `INodeType` protocol | `Interfaces.ts` | `NodeType` Protocol in `node_registry.py` | `execute(context, node, inputs)` → `list[list[FlowItem]]` |
| `nodeExecutionStack` (deque) | `WorkflowExecute.ts` | `collections.deque[_WorkItem]` in `engine.py` | BFS work queue; `_WorkItem` carries node_id + input slots |
| `waitingExecution` map | `WorkflowExecute.ts` | `merge_waiting: dict[node_id, list[...]]` in `engine.py` | Accumulates partial inputs for merge nodes |
| `INodeExecutionData` | `Interfaces.ts` | `FlowItem` dataclass in `items.py` | `json` primary payload, `binary` attachments, `meta`, `paired_item` |
| `runData[nodeName]` / `ITaskData` | `Interfaces.ts` | `context.run_data[node_id]` / `NodeRunData` | Written after each node; persisted incrementally to MongoDB |
| `pinData` | `Interfaces.ts` | `pin_data` in `flow_revisions` | Per-node output overrides; coerced to `FlowItem` at runtime |
| `continueOnFail` / `onError` | `INode` | `on_error: "stop" \| "continue"` on node shape | `"continue"` emits an error-envelope item and proceeds |
| `WorkflowDataProxy` (`$json`, `$node`) | `workflow-data-proxy.ts` | `expressions.py` (`$json` → `_json`, `$node` → `_node`) | AST-validated Python eval; no JS/TypeScript |
| JS/Python Code node (subprocess) | `Code.node.ts`, task runner | `flows.code` + `code_runner.py` | Subprocess with JSON stdin/stdout; restricted builtins |
| `WorkflowExecuteMode` | `Interfaces.ts` | `ExecutionMode` literal | `"manual" \| "trigger" \| "webhook" \| "schedule" \| "error"` |
| Bull queue job | `scaling.service.ts` | `queues.flow_run` (MongoDB-backed) | Same role: decouple HTTP trigger from execution worker (no Bull in DocRouter) |
| Worker `JobProcessor` | `job-processor.ts` | `process_flow_run_msg` in `msg_handlers/flow_run.py` | Loads revision, builds context, calls `run_flow` |
| `last_heartbeat_at` / stale detection | heartbeat loop | `_heartbeat_loop` task in `flow_run.py` | Asyncio background task; every 5 s; cancelled in `finally` |
| `errorWorkflow` setting | `IWorkflowSettings` | `settings.error_flow_id` | Dispatched when execution ends in `"error"` status |

**Key differences from n8n:**
- No TypeScript / JavaScript anywhere. Python is the only in-product code path.
- Flows are **DAGs only** — no looping, no cycles.
- No credentials system yet; credentials are passed through `analytiq_client`.
- No real-time push (WebSocket/SSE) yet — clients poll the execution document.
- Inbound **flow** webhooks: `POST /v0/webhooks/{webhook_id}` exists and enqueues a run when a `flow_webhook_routes` document is present. There is still no `flows.trigger.webhook` **node type** in the registry, and **activate/deactivate** do not create or delete `flow_webhook_routes` rows in the current code — routes must be inserted out-of-band (or a future API will do it). Schedule triggers and sub-flows / Wait nodes are not implemented.

---

## 2. Architecture overview

The implementation is split into two packages so the generic engine stays
testable without any DocRouter dependencies.

```
packages/python/
  analytiq_data/
    flows/                    ← Generic engine (DocRouter-independent)
    docrouter_flows/          ← DocRouter nodes + service helpers
    msg_handlers/flow_run.py  ← Queue worker entry point
  app/routes/flows.py         ← FastAPI HTTP routes
  worker/worker.py            ← Background worker (consumes flow_run queue)
  tests_flow/                 ← Engine unit tests (no MongoDB)
  tests/test_flows_e2e.py     ← Integration tests (MongoDB + HTTP)
```

### Generic engine (`analytiq_data/flows/`)

Knows only about the abstract node registry and `FlowItem`. Has no knowledge of
documents, OCR, LLMs, or MongoDB schemas beyond the `flow_executions` collection
it writes to via `analytiq_client`.

### DocRouter integration (`analytiq_data/docrouter_flows/`)

Registers DocRouter-specific node types (OCR, LLM extraction, tagging, manual
trigger). Node implementations call module-level async helpers from `services.py`
using `context.analytiq_client`.

### HTTP layer (`app/routes/flows.py`)

CRUD routes for flows, revisions, executions; `POST` to run a flow; stop and list
executions. Also `POST /v0/webhooks/{webhook_id}` to enqueue a run from an
inbound HTTP request. All paths enqueue `flow_run` messages; the API does not
run the engine directly.

### Worker (`worker/worker.py` → `msg_handlers/flow_run.py`)

Dequeues `flow_run` messages, claims the execution document with a
compare-and-set (filter `{"status": "queued"}`), then calls
`ad.flows.run_flow(...)`.

---

## 3. Data model

Three MongoDB collections drive the execution lifecycle.

### `flows` — stable flow header

One document per logical flow. Holds the display name, active/inactive state,
and a pointer to the currently deployed revision.

```json
{
  "_id": "<flow_id>",
  "organization_id": "<org_id>",
  "name": "Invoice processing",
  "active": false,
  "active_flow_revid": null,
  "flow_version": 3,
  "created_at": "...", "created_by": "...",
  "updated_at": "...", "updated_by": "..."
}
```

Rules: saving a new revision does **not** change `active_flow_revid`. Activation
sets `active = true` and pins `active_flow_revid`. Name-only changes do not
create a new revision.

### `flow_revisions` — immutable graph snapshot

One document per saved graph. **Never mutated after creation.** Old revisions
remain runnable by `flow_revid`.

```json
{
  "_id": "<flow_revid>",
  "flow_id": "<flow_id>",
  "nodes": [...],
  "connections": {...},
  "settings": {
    "execution_timeout_seconds": null,
    "error_flow_id": null,
    "save_execution_data": "all"
  },
  "pin_data": null,
  "graph_hash": "<sha256>",
  "engine_version": 1
}
```

`pin_data` is a per-node output override used for authoring: when set, the
engine substitutes the pinned items for the node's live output and skips
execution. Items are coerced to `FlowItem` instances at runtime.

### `flow_executions` — one per run

```json
{
  "_id": "<exec_id>",
  "status": "queued | running | success | error | stopped",
  "started_at": "...", "finished_at": null,
  "last_heartbeat_at": "...",
  "stop_requested": false,
  "run_data": {},
  "error": null,
  "trigger": { "type": "manual", "document_id": null }
}
```

Execution documents in MongoDB also include `organization_id`, `flow_id`, `flow_revid`, `mode` (`"manual"`, `"webhook"`, etc.), and optional fields such as `last_node_executed`, `wait_till`, `retry_of`, and `parent_execution_id` (see `app/routes/flows.py` and the `flow_run` handler).

`run_data` maps `node_id` to a `NodeRunData` record written after each node:

```json
{
  "<node_id>": {
    "status": "success | error | skipped",
    "start_time": "...",
    "execution_time_ms": 312,
    "data": { "main": [[{ "json": {}, "binary": {}, "meta": {}, "paired_item": null }]] },
    "error": null
  }
}
```

---

## 4. Node model

### Node shape (inside `flow_revisions.nodes[]`)

```json
{
  "id":   "stable UUID within the flow",
  "name": "unique display label",
  "type": "flows.code",
  "position": [240, 300],
  "parameters": {},
  "disabled": false,
  "on_error": "stop",
  "retry_on_fail": false,
  "max_tries": 1,
  "wait_between_tries_ms": 1000,
  "notes": null,
  "webhook_id": null
}
```

### Connection map

Edges are keyed by **source node id** (not name — unlike n8n). Each edge
records the destination node id and which input slot to feed.

```python
# Connections = dict[src_node_id, {"main": [slot0_targets, slot1_targets, ...]}]
# Each slot is a list[NodeConnection] | None

@dataclass
class NodeConnection:
    dest_node_id: str
    connection_type: Literal["main"]
    index: int   # which input slot on the destination node
```

The engine calls `coerce_json_connections_to_dataclasses()` at the start of
`run_flow` to convert any dict-form connections (from MongoDB) to dataclasses.
Legacy field names `node` / `node_id` are also accepted.

### `NodeType` protocol

Every node type is a plain Python class satisfying this protocol:

```python
class NodeType(Protocol):
    key:              str      # registry key, e.g. "flows.code"
    label:            str
    description:      str
    category:         str
    is_trigger:       bool     # True → seeds execution (no inputs)
    is_merge:         bool     # True → engine accumulates inputs before running
    min_inputs:       int
    max_inputs:       int | None
    outputs:          int
    output_labels:    list[str]
    parameter_schema: dict     # JSON Schema validated before execution

    async def execute(
        self,
        context: ExecutionContext,
        node: dict,
        inputs: list[list[FlowItem]],   # one list per input slot
    ) -> list[list[FlowItem]]: ...      # one list per output slot

    def validate_parameters(self, params: dict) -> list[str]: ...
```

Register a node type with `ad.flows.register(MyNodeType())`.

### Built-in node types

Registered in `register_builtin.py` (five node types; **only one trigger: `flows.trigger.manual`**):

| Key | `is_trigger` | `is_merge` | Inputs | Outputs | Description |
|-----|:-----------:|:----------:|:------:|:-------:|-------------|
| `flows.trigger.manual` | ✓ | ✗ | 0 | 1 | Emits the run seed item (used with manual and revision runs) |
| `flows.webhook` | ✗ | ✗ | 1 | 1 | Outbound: POSTs each item’s JSON to a URL |
| `flows.branch` | ✗ | ✗ | 1 | 2 | Routes items to `true`/`false` slot |
| `flows.merge` | ✗ | ✓ | 2+ | 1 | Waits for all inputs, concatenates |
| `flows.code` | ✗ | ✗ | 1 | 1 | Runs a Python snippet in a subprocess |

**Inbound HTTP (not a separate trigger node type):** `POST /v0/webhooks/{webhook_id}` (`app/routes/flows.py`) looks up `flow_webhook_routes` by `_id`, inserts a `flow_executions` document with `mode: "webhook"`, and enqueues `flow_run`. The graph’s trigger node remains `flows.trigger.manual` (or `docrouter.trigger.manual`); the request body/headers are available in `ExecutionContext` trigger / code context. Populating `flow_webhook_routes` on flow activation is **not** wired in the codebase yet.

**Not implemented:** `flows.trigger.webhook` / `flows.trigger.schedule` as registry entries; cron/scheduler; upload-dispatched run from document upload (upload still fires `document.uploaded` product webhooks and enqueues OCR, not `flow_run` unless added elsewhere).

---

## 5. Execution engine

### Entry point

```python
result = await ad.flows.run_flow(context=ctx, revision=revision_dict)
# result: {"status": "success" | "stopped"}
```

`run_flow` is the only public entry point. It:
1. Coerces connections from dicts to dataclasses.
2. Validates the revision (11 rules — uniqueness, reachability, DAG, parameter schemas).
3. Seeds the BFS work queue with the trigger node.
4. Delegates to `_execute_loop`.
5. Wraps in `asyncio.wait_for` if `settings.execution_timeout_seconds` is set.

### Main loop (`_execute_loop`)

Analogous to n8n's `processRunExecutionData`. Runs until both the work queue
and the merge-waiting map are empty.

```
while work or merge_waiting:
    1. Poll MongoDB for cooperative stop (read_stop). If set → return "stopped".
    2. If work is empty but merge_waiting is non-empty → flush stuck merges
       (treat None slots as empty lists for skipped upstream branches).
    3. Dequeue _WorkItem(node_id, inputs).
    4. Disabled node → emit empty outputs, record "skipped".
    5. pin_data hit → use pinned FlowItems (coerced), skip execute.
    6. All input slots empty → emit empty outputs, record "skipped"
       (branch-skipping rule: empty output ⟹ downstream skipped).
    7. Resolve parameters (expressions) — see below.
    8. await node_type.execute(context, resolved_node, inputs).
    9. Handle errors: on_error="stop" → raise; on_error="continue" → emit error item.
   10. Write NodeRunData to context.run_data and persist to MongoDB.
   11. For each non-empty output slot:
       - Non-merge destinations → enqueue immediately with their input slice.
       - Merge destinations → accumulate in merge_waiting;
         enqueue when all min_inputs slots are filled.
```

### Parameter expressions

Before calling `execute()`, the engine resolves any parameter values that start
with `=` via `resolve_parameters()` in `expressions.py`. This is the Python
equivalent of n8n's `WorkflowDataProxy`.

**Per-item resolution (default path):** for nodes that are **not** merge nodes, `_execute_loop` in `engine.py` evaluates `=` parameters **once per input `FlowItem`**, calls `execute` for that single item, then concatenates output lists across items (n8n-style). Merge nodes and the “all inputs empty” skip path use a **single** `resolve_parameters` pass with the **first** item across the input slots (or `None` if there are no items).

```python
# In a node's parameters:
{"value": "=$json['amount']"}          # per input item: that item’s json
{"label": "=$node['ocr1']['main'][0][0]['text']"}  # reads prior node output
```

Variables in scope for each evaluation:
- `$json` — the current item's `.json` dict (in per-item mode, the item being processed; in merge/single pass, the “first” item as described above).
- `$node` — dict of completed node outputs, keyed by node id.
  Shape: `{node_id: {"status": "...", "main": [[item_json, ...], ...]}}`.

Safety: expressions are parsed with `ast.parse(mode="eval")`. Any AST node type
not in an explicit allow-set raises `ExpressionError`. Function calls (`ast.Call`)
and names starting with `__` are rejected. Evaluation uses
`eval(code, {"__builtins__": {}}, env)`.

Expression errors are raised inside the existing `except Exception` block and
respect the node's `on_error` policy.

### `flows.code` subprocess

```python
def run(items: list[dict], context: dict) -> list[dict]:
    # items: list of item.json dicts from the input slot
    # context: execution metadata
    return [{"result": items[0]["amount"] * 1.1}]
```

The snippet runs in a child process started with `sys.executable -I -S` (isolated
mode, no site-packages). The subprocess receives JSON on stdin and writes JSON to
stdout. Only a small allowlist of builtins is available; `__import__` is not.

Context dict available inside the snippet:

```python
{
    "trigger":          {...},    # trigger_data from the execution context
    "node_id":          "...",
    "mode":             "manual",
    "nodes":            {...},    # materialized prior node outputs (same shape as $node)
    "organization_id":  "...",
    "execution_id":     "...",
    "flow_id":          "...",
    "flow_revid":       "...",
}
```

---

## 6. Module reference

```
analytiq_data/flows/
  __init__.py           Re-exports everything; exposes register_docrouter_nodes()
  context.py            ExecutionContext dataclass, ExecutionMode literal
  engine.py             run_flow, validate_revision, FlowValidationError,
                        _execute_loop (per-item param resolution for non-merge nodes),
                        persist_run_data, read_stop, canonical_graph_hash,
                        _bson_serialize_value / _bson_serialize_run_data
                        (converts FlowItem/BinaryRef → BSON-safe dicts for Mongo)
  expressions.py        ExpressionError, eval_expression, resolve_parameters,
                        materialize_node_data
  items.py              FlowItem, BinaryRef dataclasses;
                        coerce_flow_item / coerce_flow_item_list / coerce_binary_ref
                        (strict coercion from dicts; raise ValueError on bad types)
  connections.py        NodeConnection, Connections type;
                        coerce_json_connections_to_dataclasses
  node_registry.py      NodeType Protocol, register(), get(), list_all()
  execution.py          NodeRunData helpers
  register_builtin.py   register_builtin_nodes() — registers five built-ins
  code_runner.py        run_python_code() — subprocess executor for flows.code
  nodes/
    trigger_manual.py   flows.trigger.manual
    webhook.py          flows.webhook  (outbound HTTP)
    branch.py           flows.branch
    merge.py            flows.merge
    code.py             flows.code

analytiq_data/docrouter_flows/
  register.py           register_docrouter_nodes()
  services.py           get_document, run_ocr, run_llm_extract, set_tags,
                        get_runtime_state, set_runtime_state
  nodes/
    manual_trigger_node.py   docrouter.trigger.manual
    ocr_node.py              docrouter.ocr
    llm_node.py              docrouter.llm_extract
    tag_node.py              docrouter.set_tags

analytiq_data/msg_handlers/
  flow_run.py           process_flow_run_msg:
                          - compare-and-set claim (filter status="queued")
                          - _heartbeat_loop background task (every 5 s)
                          - calls ad.flows.run_flow
                          - handles timeout / error / stop

app/routes/flows.py     FastAPI routes (see `docs/flows.md`):
                          CRUD for flows + revisions, manual run, stop,
                          execution history, node-type list, and
                          `POST /v0/webhooks/{webhook_id}` (inbound flow trigger)

worker/worker.py        worker_flow_run — consumes flow_run queue messages

tests_flow/
  conftest.py           sys.path setup
  test_flows_engine.py  Validation + run_flow (code, branch, merge, pin_data)
  test_expressions.py   $json/$node resolution, on_error, unsafe-call rejection

tests/
  test_flows_e2e.py     HTTP + MongoDB integration test (TestClient + real Mongo)
```

---

## 7. Execution lifecycle (end to end)

**Manual (or `flow_revid` from API):**

```
User / API client
  │
  POST /v0/orgs/{org_id}/flows/{flow_id}/run
  │
  app/routes/flows.py
    1. Create flow_executions doc (status="queued")
    2. Enqueue flow_run message (flow_id, flow_revid, exec_id, trigger)
    3. Return { execution_id } (HTTP 200; async execution is queue-backed)
  │
  ▼
  queues.flow_run (MongoDB-backed queue)
  │
  ▼
  worker/worker.py → process_flow_run_msg
    1. Load flow_executions + flow_revisions from Mongo
    2. Compare-and-set: update status "queued" → "running"
       (drops message if matched_count == 0 — already claimed)
    3. Start _heartbeat_loop asyncio.Task (bumps last_heartbeat_at every 5 s)
    4. Build ExecutionContext
    5. await ad.flows.run_flow(context, revision)
         └─ validate_revision (11 rules)
         └─ _execute_loop (BFS over nodes)
              └─ resolve_parameters (expressions; per item for non-merge nodes)
              └─ node_type.execute(context, node, inputs)
              └─ persist_run_data → Mongo update (run_data + last_heartbeat_at)
    6. Cancel heartbeat task
    7. Update flow_executions (status, finished_at)
    8. Delete queue message
```

**Webhook-shaped runs:** `POST /v0/webhooks/{webhook_id}` creates the execution
(`status="queued"`, `mode="webhook"`, trigger payload from the HTTP request) and
enqueues the same `flow_run` message shape; the worker path is identical from
the compare-and-set step onward. The caller must have inserted a
`flow_webhook_routes` document whose `_id` is `webhook_id` (the codebase does
not yet create this row when a flow is activated).

---

## 8. Validation rules

`validate_revision` enforces all 11 rules before execution starts (and also at
save / activate time):

1. `nodes[].id` unique within the revision.
2. `nodes[].name` unique within the revision.
3. Every connection source node id exists in `nodes`.
4. Every connection destination `dest_node_id` exists in `nodes`.
5. Every connection destination `index` is within the declared input count.
6. Every connection source output slot index is within declared output count.
7. Graph is acyclic (topological sort succeeds).
8. Exactly one trigger node (`is_trigger = True`).
9. Every non-trigger node is reachable from the trigger node.
10. Every node's `parameters` validate against its type's `parameter_schema`.
11. `pin_data` keys refer to node ids that exist in `nodes`.

Unknown node types raise `FlowValidationError` (not `KeyError`).

---

## 9. Running tests

```bash
# Engine unit tests — no MongoDB, no HTTP
pytest packages/python/tests_flow/

# Integration tests — requires running MongoDB (MONGO_URI in .env)
pytest packages/python/tests/ -k flows
```

Engine tests run `run_flow` with `analytiq_client=None`, which causes
`persist_run_data` and `read_stop` to no-op.

---

## 10. Implementation status

### Done (current tree)

| Area | Status |
|------|--------|
| Generic engine: BFS loop, branch/merge/skip semantics | ✓ Complete |
| Validation: all 11 rules, `FlowValidationError` | ✓ Complete |
| `FlowItem` / `BinaryRef` dataclasses + coercion | ✓ Complete |
| `NodeType` protocol + in-memory registry | ✓ Complete |
| Built-in nodes (five): `flows.trigger.manual`, `flows.webhook` (outbound), `flows.branch`, `flows.merge`, `flows.code` | ✓ Complete |
| Per-item `=` parameters and per-item `execute` for **non-merge** nodes (`engine._execute_loop`) | ✓ Complete |
| `flows.code` subprocess runner (restricted builtins, JSON contract) | ✓ Complete |
| Expression engine (`$json`, `$node`, AST safety) | ✓ Complete |
| `resolve_parameters` + `materialize_node_data` for expressions and code context | ✓ Complete |
| `pin_data` coercion (`coerce_flow_item_list`) | ✓ Complete |
| `_bson_serialize_value` — FlowItem/BinaryRef → BSON-safe for Mongo | ✓ Complete |
| `coerce_json_connections_to_dataclasses` — dict → dataclass at run time | ✓ Complete |
| `persist_run_data` — incremental Mongo write after each node | ✓ Complete |
| `read_stop` — cooperative cancellation between nodes | ✓ Complete |
| Worker: compare-and-set claim, heartbeat loop, timeout, error handling; `recover_all_queues` at process startup (stale **queue** messages) | ✓ Complete |
| DocRouter nodes: `docrouter` manual trigger, OCR, LLM extract, set tags | ✓ Complete |
| HTTP routes: CRUD, manual run, stop, execution history, node-type list | ✓ Complete |
| Inbound **flow** webhook: `POST /v0/webhooks/{webhook_id}` (reads `flow_webhook_routes`, enqueues `flow_run`) | ✓ HTTP handler |
| E2E integration test (`test_flows_e2e.py`) | ✓ Complete |

### Next steps (roadmap)

| Feature | What it needs | Notes |
|---------|--------------|--------|
| **`flow_webhook_routes` lifecycle** | Create/update/delete documents when a flow is activated or deactivated (or a dedicated admin API) — see `docs/flows.md` §15 | `POST /v0/webhooks/{webhook_id}` already **reads** this collection; nothing in the repo **writes** it yet |
| **`flows.trigger.schedule` / cron** | Cron registration at activation, tick → `flow_run` | Not started |
| **Upload → flow** | Dispatch `flow_run` on `document.uploaded` (or similar) for matching active flows | Upload still enqueues OCR and product `webhooks` only |
| **Stale-execution recovery** (execution docs) | Sweep `flow_executions` stuck in `running` with an old `last_heartbeat_at` | Different from `recover_stale_messages` on the queue |
| **Dynamic node types** (API + MongoDB) | e.g. `flow_node_type_definitions` + CRUD + loader | Needs design |
| **First-class flow builder UI** | Wire React Flow (already used in the app for other workflows) to flow CRUD and execution status | Product milestone |

### Known limitations (by design for v1)

- **Merge nodes** use a **single** `resolve_parameters` pass with the first
  available input item, then one `execute` with merged inputs. **Non-merge**
  nodes get per-item `=` evaluation and one `execute` per item.
- `flows.code` is **not** a full multi-tenant sandbox. The subprocess boundary and
  restricted builtins are a v1 precaution; seccomp / WASM isolation is a later
  concern.
- Flows are **DAGs only** — no looping, no Wait nodes, no execution resume.
- No SSE / WebSocket push — clients poll `GET .../executions/{exec_id}`.
