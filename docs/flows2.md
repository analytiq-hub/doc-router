# DocRouter Flows — Architecture and Implementation Guide

A **flow** is a saved, reusable automation pipeline: a directed acyclic graph
(DAG) of **nodes** connected by **edges**. Flows let users compose multi-step
document workflows (upload → OCR → LLM extraction → tagging → webhook) that run
reliably in the background, with durable execution state and per-node output
stored in MongoDB.

This document is the definitive guide for someone new to the codebase. It covers
what we built, how it maps to n8n's architecture, what is already running, and
what is still on the roadmap.

**See also:** [Full execution trace and logging (`docrouter_fulltrace.md`)](./docrouter_fulltrace.md) for step-by-step error/stack/trace UX.

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
| `WorkflowDataProxy` (`$json`, `$node`) | `workflow-data-proxy.ts` | `expressions.py` (`_json`, `_node`, … injected into eval env) | AST-validated Python eval; no JS/TypeScript |
| JS/Python Code node (subprocess) | `Code.node.ts`, task runner | `flows.code` + `code_runner.py` | Subprocess with JSON stdin/stdout; restricted builtins |
| `WorkflowExecuteMode` | `Interfaces.ts` | `ExecutionMode` literal | `"manual" \| "trigger" \| "webhook" \| "schedule" \| "error"` |
| Bull queue job | `scaling.service.ts` | `queues.flow_run` (MongoDB-backed) | Same role: decouple HTTP trigger from execution worker (no Bull in DocRouter) |
| Worker `JobProcessor` | `job-processor.ts` | `process_flow_run_msg` in `msg_handlers/flow_run.py` | Loads revision, builds context, calls `run_flow` |
| `last_heartbeat_at` / stale detection | heartbeat loop | `_heartbeat_loop` task in `flow_run.py` | Asyncio background task; every 5 s; cancelled in `finally` |
| `errorWorkflow` setting | `IWorkflowSettings` | `settings.error_flow_id` | Dispatched when execution ends in `"error"` status |

**Key differences from n8n:**
- No TypeScript / JavaScript anywhere. Python is the only in-product code path.
- Flows are **DAGs only** — no looping, no cycles.
- **Flow credentials:** org-scoped saved credentials (`credentials` collection), credential kinds under `schemas/credential-kinds/`, REST under `/v0/orgs/{org}/credentials` and `/credential-kinds`; nodes may declare `credential_slots` and store `credentials: { "<slot>": "<credential_id>" }` on each node (see `docs/docrouter_credentials.md`).
- No real-time push (WebSocket/SSE) yet — clients poll the execution document.
- Inbound **flow** webhooks: `POST /v0/webhooks/{webhook_id}` exists and enqueues a run when a `flow_webhook_routes` document is present. There is still no `flows.trigger.webhook` **node type** in the registry, and **activate/deactivate** do not create or delete `flow_webhook_routes` rows in the current code — routes must be inserted out-of-band (or a future API will do it). **Schedule and poll triggers** are not implemented; see **§11** for the plan (including Google Drive trigger).

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
  tests/flows/                ← Flow engine + HTTP integrations (fixtures from `tests/conftest.py`)
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

`run_data` maps `node_id` to a `NodeRunData` record written after each node:

```json
{
  "<node_id>": {
    "status": "success | error | skipped",
    "start_time": "...",
    "execution_time_ms": 312,
    "execution_index": 3,
    "data": { "main": [[{ "json": {}, "binary": {}, "meta": {}, "paired_item": null }]] },
    "error": {
      "message": "...",
      "node_id": "...",
      "node_name": "...",
      "stack": "Traceback ...",
      "cause": "RuntimeError",
      "http_code": 404
    },
    "logs": ["optional code node console lines"],
    "trace": []
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
  "webhook_id": null,
  "credentials": {}
}
```

Optional **`credentials`** maps a node type’s **credential slot** name to a saved org credential document id (see `docs/docrouter_credentials.md`). Omit the field or use `{}` when no slots are bound.

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

`parameter_schema` may include **`x-ui-*`** vendor keys for the flow editor (groups, visibility, widget hints, regex/require-when messages for the modal; see `docs/flow_parameter_schema_ui_plan.md`). The **browser** compiles the same schema with AJV (after expression sentinels) for inline errors and save gating; see `docs/node_param_validation.md`. The engine’s Draft 7 validator still applies to saved node **`parameters`** only; extra `x-*` entries on the schema object are ignored by validation.

Register a node type with `ad.flows.register(MyNodeType())`.

### Built-in node types

Registered in `register_builtin.py` (five node types; **only one trigger: `flows.trigger.manual`**):

| Key | `is_trigger` | `is_merge` | Inputs | Outputs | Description |
|-----|:-----------:|:----------:|:------:|:-------:|-------------|
| `flows.trigger.manual` | ✓ | ✗ | 0 | 1 | Emits one item with empty JSON `{}` (n8n-style); execution still carries `trigger` on `flow_executions` and in Code `context` |
| `flows.http_request` | ✗ | ✗ | 1 | 1 | Outbound HTTP (method, URL, body modes, optional header/query auth credentials) |
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
    7. Resolve parameters (expressions).
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

**Per-item resolution (default path):** for nodes that are **not** merge nodes, `_execute_loop` in `engine.py` evaluates `=` parameters **once per input `FlowItem`**, calls `execute` for that single item, then concatenates output lists across items (n8n-style).

**Merge nodes:** merge nodes resolve `=` parameters **once per node execution** (not per item). Expressions can access *all* incoming items via `_input["all"]`.

```python
# In a node's parameters:
{"value": "=_json['amount']"}          # per input item: that item’s json
{"label": "=_node['ocr1']['main'][0][0]['text']"}  # reads prior node output (id-keyed today; name-keyed planned)
{"x": "=_input['item']['json']['amount']"}         # same as _json for non-merge nodes
{"x": "=_input['all'][1][0]['json']['amount']"}    # merge node: slot 1, item 0
```

Variables in scope for each evaluation (Python identifiers; **no** `$` prefix):
- `_json` — the current item's `.json` dict (for non-merge nodes in per-item mode; `{}` for merge-node parameter resolution).
- `_binary` — current item's binary metadata (no raw bytes).
- `_item` — the full current item object: `{"json", "binary", "meta", "paired_item"}` (non-merge per-item mode only; `None` for merge-node parameter resolution).
- `_input` — input context object:
  - `all`: `list[list[item]]` across input slots, where each `item` is `{"json","binary","meta","paired_item"}`
  - `item`: the current item (same shape as `_item`) in per-item mode
  - `input_index`, `item_index`: indices for the current item in per-item mode
- `_node` — dict of completed node outputs, keyed by node id (JSON-only).
  Shape: `{node_id: {"status": "...", "main": [[item_json, ...], ...]}}`.
- `_items` — alias for the JSON-only `_node` view (convenience).

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
    "nodes":            {...},    # materialized prior node outputs (same shape as _node in expressions)
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
  credential_kind_registry.py  load credential kind JSON from schemas/credential-kinds/
  credentials.py        fetch_credential_fields — decrypt org credential by id
  nodes/
    trigger_manual.py   flows.trigger.manual
    http_request.py     flows.http_request  (outbound HTTP)
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
app/routes/flows_credentials.py   credential kinds list + org credential CRUD (`/credential-kinds`, `/credentials` under the org)

worker/worker.py        worker_flow_run — consumes flow_run queue messages

tests/flows/
  test_flows_engine.py  Validation + run_flow (code, branch, merge, pin_data)
  test_expressions.py   _json/_node resolution, on_error, unsafe-call rejection
  test_flows_e2e.py     HTTP + MongoDB integration (TestClient + real Mongo)
  …                     other flow HTTP/schema/credentials tests (`tests/conftest.py` fixtures)
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

`validate_revision` enforces all 12 rules before execution starts (and also at
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
12. If present, each node's `credentials` map uses only slot names declared on that node type's `credential_slots`, and values are strings (credential ids) or empty.

Unknown node types raise `FlowValidationError` (not `KeyError`).

---

## 9. Running tests

```bash
# Engine unit tests — no MongoDB, no HTTP
pytest packages/python/tests/flows/

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
| Built-in nodes (five): `flows.trigger.manual`, `flows.http_request` (outbound HTTP), `flows.branch`, `flows.merge`, `flows.code` | ✓ Complete |
| Per-item `=` parameters and per-item `execute` for **non-merge** nodes (`engine._execute_loop`) | ✓ Complete |
| `flows.code` subprocess runner (restricted builtins, JSON contract) | ✓ Complete |
| Expression engine (`_json`, `_node`, AST safety) | ✓ Complete |
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
| **Trigger platform** (schedule, poll, activation registry) | See **§11** | Foundation for schedule + Google Drive trigger; not started |
| **`flow_webhook_routes` lifecycle** | Create/update/delete documents when a flow is activated or deactivated (or a dedicated admin API) — see `docs/flows.md` §15 | `POST /v0/webhooks/{webhook_id}` already **reads** this collection; nothing in the repo **writes** it yet |
| **`flows.trigger.schedule`** | Cron trigger node + platform scheduler | Depends on §11.1–11.5 |
| **`flows.trigger.google_drive`** (poll) | Poll trigger node + poll framework | Depends on §11.1–11.4, §11.6–11.7; reuses `flows.google_drive` API helpers |
| **Upload → flow** | Dispatch `flow_run` on `document.uploaded` (or similar) for matching active flows | Upload still enqueues OCR and product `webhooks` only |
| **Stale-execution recovery** (execution docs) | Sweep `flow_executions` stuck in `running` with an old `last_heartbeat_at` | Different from `recover_stale_messages` on the queue |
| **Dynamic node types** (API + MongoDB) | e.g. `flow_node_type_definitions` + CRUD + loader | Design: `docs/dynamic_node_types.md` |
| **First-class flow builder UI** | Wire React Flow (already used in the app for other workflows) to flow CRUD and execution status | Product milestone |

### Known limitations (by design for v1)

- **Merge nodes** resolve `=` parameters **once** per node execution (not per item).
  Expressions can access all inputs via `_input["all"][slot_idx][item_idx]["json"]`
  (and `_input["all"][...]["binary"/"meta"]`). **Non-merge** nodes get per-item `=`
  evaluation and one `execute` per item; the “current item” is also exposed as
  `_input["item"]` / `_item`.
- `flows.code` is **not** a full multi-tenant sandbox. The subprocess boundary and
  restricted builtins are a v1 precaution; seccomp / WASM isolation is a later
  concern.
- Flows are **DAGs only** — no looping, no Wait nodes, no execution resume.
- No SSE / WebSocket push — clients poll `GET .../executions/{exec_id}`.

---

## 11. Trigger platform (plan)

This section is the implementation plan for **scheduled** and **polling** triggers:
`flows.trigger.schedule`, a poll framework (Google Drive and future integrations), and the
**activation lifecycle** that wires them to the existing `flow_run` queue and worker.

**Reference (n8n):** `docs/n8n.md` §5 (TriggersAndPollers, poll cycle), sibling tree
`../n8n/packages/core/src/execution-engine/scheduled-task-manager.ts`,
`../n8n/packages/core/src/execution-engine/active-workflows.ts`,
`../n8n/packages/nodes-base/nodes/Schedule/ScheduleTrigger.node.ts`,
`../n8n/packages/nodes-base/nodes/Google/Drive/GoogleDriveTrigger.node.ts`.

### 11.1 Current state

| Capability | Status |
|------------|--------|
| Manual run (`POST .../flows/{id}/run`) | ✓ |
| Inbound flow webhook (`POST /v0/webhooks/{webhook_id}`) | ✓ handler; routes not auto-created on activate |
| Flow activate / deactivate (DB flag + pinned revision) | ✓ sets `flows.active` only — **no in-memory trigger registry** |
| `ExecutionMode` includes `"schedule"` | ✓ in `context.py`; unused |
| Cron / poll scheduler | ✗ |
| Workflow **static data** (poll cursors) | ✗ (see `flow_runtime_state` — node-scoped, not trigger-oriented) |
| `flows.trigger.schedule` | ✗ |
| `flows.trigger.google_drive` (or poll variant) | ✗ |
| `flows.google_drive` action node | ✓ experimental; API/helpers reusable for poll trigger |

Activation today validates the revision and sets `active = true`. Nothing registers
timers, webhooks, or poll jobs. Workers (`worker_flow_run`, possibly `N_DOCROUTER_WORKERS > 1`)
only **consume** `flow_run` messages; they must not own trigger scheduling.

### 11.2 n8n reference and delivery guarantees

n8n splits trigger activation into two paths (see `docs/n8n.md`):

1. **Push triggers** — `trigger()` registers a listener; on event, `emit()` starts an execution.
2. **Poll triggers** — node declares `polling: true`; platform injects shared **`pollTimes`**
   (cron, default every minute), registers crons via `ScheduledTaskManager`, and on each tick
   calls the node’s **`poll()`** hook. Non-empty poll output is passed into the same execution
   engine (`mode: 'scheduled'`).

**Schedule Trigger** (`ScheduleTrigger.node.ts`) is **not** a poll node: it implements
`trigger()` and registers its own cron rules directly. Poll nodes (Google Drive, Gmail, RSS, …)
share the poll-times machinery.

#### What n8n guarantees (and what it does not)

| Layer | Guarantee | Mechanism |
|-------|-----------|-----------|
| **Multi-main cron** | **At most one tick executes per cron registration** across main processes | `ScheduledTaskManager` runs the cron callback only when `instanceSettings.isLeader` is true; follower mains register crons but no-op on tick (`scheduled-task-manager.ts` ~L78). Leader election via Redis (`multi-main-setup.ee.ts`). |
| **Queue mode workers** | Workers **never** run trigger/poll registration | Main process holds `ActiveWorkflows`; workers only run queued executions (`docs/n8n.md` §6). |
| **Poll cursor / dedup** | **Best-effort**, not exactly-once | Per-node static data (e.g. Google Drive `lastTimeChecked`) narrows the Drive query window. Cursor is updated at end of `poll()` **before** deciding whether to return items (`GoogleDriveTrigger.node.ts` ~L508–511). |
| **Per external event** | **No exactly-once** | Same file can appear in two runs if modified twice across windows, if static data fails to persist after `emit`, or on leader failover mid-tick. One poll returning *N* files → **one** execution with *N* items (not *N* executions). |
| **Execution enqueue** | **No cross-run idempotency key** | Each successful poll `emit` creates a new execution; no dedup by file id or event id. |

**Conclusion for DocRouter:** Match n8n’s practical bar — **avoid duplicate scheduler ticks**
across processes, use cursors to minimize duplicate *items*, accept rare duplicate *runs* in
corner cases. Do **not** promise exactly-once delivery unless we add stronger idempotency
(§11.4) and accept the product trade-offs (missed events vs duplicates).

### 11.3 Platform architecture

Introduce a **trigger runner** role separate from `flow_run` workers. Same codebase, different
responsibility: register active flows, fire crons/polls, enqueue executions.

```
┌─────────────────────────────────────────────────────────────────┐
│  API / trigger-runner process (one leader at a time)            │
│  ┌──────────────────┐    activate/deactivate    ┌─────────────┐ │
│  │ ActiveFlowRegistry│ ◄─────────────────────── │ flows.py    │ │
│  └────────┬─────────┘                           └─────────────┘ │
│           │ register crons / poll jobs                           │
│           ▼                                                      │
│  ┌──────────────────┐   tick (leader only)   ┌─────────────────┐ │
│  │ FlowScheduler    │ ─────────────────────► │ PollRunner /    │ │
│  │ (cron, TZ)       │                        │ ScheduleRunner  │ │
│  └──────────────────┘                        └────────┬────────┘ │
│                                                        │ poll()  │
│                                                        ▼         │
│                                              enqueue flow_run    │
└──────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
                          queues.flow_run  ──►  worker_flow_run (×N)
                                    │
                                    ▼
                          process_flow_run_msg → run_flow
```

#### New / extended persistence

| Store | Purpose |
|-------|---------|
| `flows.active` + `active_flow_revid` | Already exists; source of truth for which revision to run |
| **`flow_static_data`** (new) | Per `(flow_id, node_id)` JSON blob for poll cursors (`last_time_checked`, etc.). Mirrors n8n `workflow.staticData`. Persist after each poll tick (compare-and-set on `__data_changed` flag or unconditional `$set` of known keys). |
| **`flow_trigger_registrations`** (new, optional) | Materialized cron/poll schedule for crash recovery and observability: `{ flow_id, node_id, trigger_kind, cron_expr, timezone, next_run_at }`. Rebuilt on activate. |
| **`flow_trigger_leases`** (new) | Short-lived lease per `(flow_id, node_id, tick_key)` for multi-process dedup (§11.4). TTL ≈ 2× max poll duration. |
| `flow_executions` | Extend `trigger` subdoc: `{ type, mode, poll_tick_id?, items_count? }` |
| `queues.flow_run` | Unchanged message shape; add optional `trigger_meta` for logging |

#### Activation lifecycle (target)

1. **`POST .../activate`** (after validation): set `active`, pin revision, then call
   `ActiveFlowRegistry.register(flow_id, revision)`.
2. Registry loads trigger node(s), dispatches by kind:
   - **`flows.trigger.schedule`** → register cron rule(s) from node parameters.
   - **Poll types** (`polling: true` on node class) → register cron from **`poll_times`**
     (platform-owned parameter, like n8n’s injected `pollTimes`; min interval **1 minute**).
   - **`flows.trigger.webhook`** (future) → upsert `flow_webhook_routes`.
   - Push triggers (future) → register external subscription.
3. **`POST .../deactivate`**: deregister all crons/polls for `flow_id`, delete webhook routes,
   clear in-memory state. **Do not** delete `flow_static_data` (cursor survives re-activate).
4. **Process startup**: leader loads all `flows` where `active=true`, registers each (same as
   n8n main restart). Followers skip tick execution.

#### NodeType protocol extensions

```python
class NodeType(Protocol):
    ...
    is_trigger: bool
    polling: bool = False          # True → platform calls poll(), not execute(), on tick

    async def poll(
        self,
        context: PollContext,      # static_data R/W, credentials, org, flow ids
        node: dict,
    ) -> list[list[FlowItem]] | None: ...   # None → no run

    # schedule trigger uses trigger path instead:
    async def on_schedule_tick(
        self, context: PollContext, node: dict
    ) -> list[list[FlowItem]]: ...          # always emits ≥1 item (often [{}])
```

Keep **`execute()`** for the trigger node during a **manual test run** from the editor
(n8n `mode === 'manual'`): poll types may return sample data or raise if none found.

#### Enqueue contract (shared by schedule + poll)

On tick, after optional lease acquisition (§11.4):

1. Call `poll()` / schedule hook → `items: list[list[FlowItem]] | None`.
2. If `items` is `None` or all slots empty → persist static data, **do not** enqueue.
3. Else insert `flow_executions` (`status=queued`, `mode=schedule`, `trigger={...}`).
4. Enqueue `flow_run` with `exec_id`, `flow_id`, `active_flow_revid`, trigger payload.
5. Worker path unchanged (compare-and-set claim → `run_flow`).

Trigger node **`execute()`** during the run: for poll/schedule triggers, emit the items
already captured in `trigger_data` (or re-derive from static context) so downstream nodes
see the same shape as n8n’s trigger output.

### 11.4 Multi-worker and multi-process safety

DocRouter may run **`N_DOCROUTER_WORKERS > 1`** `flow_run` workers. The trigger platform must
separate **scheduling** from **execution** (same split as n8n queue mode).

#### Scheduler: one logical leader

| Approach | Notes |
|----------|-------|
| **A. Mongo leader lease** (recommended v1) | Collection `flow_scheduler_leader`: `{ _id: "leader", holder: host_id, expires_at }`. Only holder runs cron callbacks. Renew every *T*/3; TTL *T* (e.g. 30s). Same pattern as n8n Redis leader key. |
| B. Dedicated single replica | Operate trigger runner only on one deployment; simpler ops, weaker HA. |
| C. External cron (K8s CronJob) | Calls internal `POST .../flows/{id}/tick`; pushes complexity to infra. |

All API/worker processes may **load** cron definitions for fast deactivate, but **only the
leader executes ticks** (mirror n8n `isLeader` gate).

#### Per-tick dedup (minimize duplicate runs)

Even with one leader, overlapping ticks (slow poll + next cron) or leader failover can overlap.
Layer defenses:

1. **In-flight guard** — before `poll()`, `findOneAndUpdate` on `flow_trigger_leases`:
   `{ flow_id, node_id, tick_key }` with `expires_at > now`. If insert/update fails, skip tick.
2. **Cursor monotonicity** — store `last_time_checked` in static data; poll query uses
   `> last_time_checked` (Drive pattern). Advance cursor **after** successful API fetch,
   persist **before** enqueue (n8n order). On enqueue failure, cursor already advanced →
   prefer **at-most-once** over replay storm (same trade-off as n8n).
3. **Optional idempotency key** (phase 2) — unique index on
   `flow_executions.trigger.dedupe_key` (e.g. `sha256(flow_id + node_id + tick_key)`).
   Enqueue becomes upsert-or-skip; eliminates duplicate executions if lease fails open.
4. **`flow_run` claim** — existing compare-and-set on `status: queued → running` already
   prevents double execution of the **same** exec doc; does not help if two exec docs were
   created.

**Target:** duplicates **rare** under normal operation (single leader, 1-minute min poll interval,
lease + cursor). **Not** a hard exactly-once guarantee unless we add (3) and accept missing
events when enqueue fails after cursor advance.

#### Workers

Multiple `worker_flow_run` tasks are **safe** for trigger-initiated runs: each message is one
execution doc; first claimant wins. Triggers must **never** call `run_flow` inline in the worker
OCR/LLM loops.

### 11.5 Schedule trigger (`flows.trigger.schedule`)

Port behaviour from n8n **Schedule Trigger** (not the poll framework):

| Aspect | Plan |
|--------|------|
| **Node key** | `flows.trigger.schedule` |
| **Category** | `trigger` |
| **Parameters** | Interval rules (seconds/minutes/hours/days/weeks/months) + custom cron + timezone; JSON Schema with `x-ui-*` for the editor |
| **Activation** | `on_schedule_tick` or lightweight `trigger()` registers one or more cron expressions per rule |
| **Output** | One item `{ "timestamp": "<iso>", "rule_index": 0 }` per firing (empty `{}` acceptable) |
| **Mode** | `ExecutionMode = "schedule"` |
| **Min interval** | Match n8n poll floor: **≥ 1 minute** for production (stricter for sub-minute if needed later) |
| **Editor** | Palette under Triggers; manual “Test trigger” runs next tick logic once without activating |

No static data required unless we add “run once” / recurrence bookkeeping later (n8n
`recurrenceCheck` for advanced rules — defer to v2).

**Tests:** cron expression builder unit tests; integration test with frozen clock mocks
scheduler tick → queued execution → worker completes.

### 11.6 Poll trigger framework

Shared infrastructure for Google Drive, Gmail, RSS, etc.

| Piece | Detail |
|-------|--------|
| **`poll_times` parameter** | Platform-injected fixed collection (hidden in UI or “Poll times” group), default `{ "item": [{ "mode": "everyMinute" }] }`. Compiled to cron via shared helper (port n8n `toCronExpression`). |
| **`PollContext`** | `get_static_data()` / `set_static_data()`, credentials, `mode` (`manual` \| `schedule`), `analytiq_client`, org/flow/node ids |
| **`FlowScheduler.register_poll(flow_id, node_id, cron_exprs, callback)`** | Same backend as schedule crons |
| **Activation test** | First poll on activate runs once with `testing=True`; failure blocks activation (n8n behaviour) |
| **Error handling** | Poll exception on tick → log + optional flow error notification; do not deactivate automatically |

Node class sets `polling = True` and implements `poll()`. Registry lists poll types separately
for validation (exactly one trigger; poll types count as triggers).

### 11.7 Google Drive trigger — upgrade path

**n8n source:** `GoogleDriveTrigger.node.ts` — `polling: true`, `poll()` with
`lastTimeChecked`, Drive `files.list` query on `createdTime` / `modifiedTime`, events:
file/folder created/updated in folder, specific file updated, folder metadata updated.

**Today (interim, no trigger platform):**

| Workaround | Limitation |
|------------|------------|
| Manual run | No automation |
| Schedule + `flows.google_drive` **Search** | Polls inside the flow graph on each run; wastes runs when empty; cursor must live in `flow_runtime_state` via Code node — fragile, not productized |
| Inbound webhook + Drive push notifications | Not implemented; Drive changes API is push-capable but needs HTTPS endpoint registration |

**Target node:** `flows.trigger.google_drive` (experimental gate alongside `flows.google_drive`).

| Phase | Deliverable |
|-------|-------------|
| **1 — Platform** | §11.3–11.4: registry, leader scheduler, static data, enqueue |
| **2 — Poll framework** | §11.6: `poll_times`, `PollContext`, activation test |
| **3 — Drive trigger** | Port n8n `poll()` logic into `analytiq_data/flows/nodes/google_drive/trigger.py`; reuse `api.py`, `helpers.py`, OAuth credential slot `google_drive_oauth2` |
| **4 — Editor** | Trigger palette entry, icon (`google_drive`), parameters: `trigger_on`, `event`, file/folder resource locators, `options.file_type`; hide `poll_times` or expose under “Advanced” |
| **5 — Migration** | Flows using Schedule+Search: document one-time migration to replace trigger subgraph with single trigger node; optional import tool |

**Parameter parity (v1):**

- `trigger_on`: `specific_file` \| `specific_folder`
- `event`: `fileCreated`, `fileUpdated`, `folderCreated`, `folderUpdated`, `watchFolderUpdated`
- Resource locators aligned with action node (`x-ui-enum-by`, list search methods)
- `authentication`: OAuth2 (service account defer)

**Output items:** one item per Drive file metadata dict (same fields as n8n `returnJsonArray(files)`).

**Static data:** `{ "last_time_checked": "<iso-utc>" }` under node id in `flow_static_data`.

### 11.8 Phased rollout

| Phase | Scope | Exit criteria |
|-------|--------|---------------|
| **T0** | Design doc (this section) | Reviewed |
| **T1** | Leader election + `FlowScheduler` + activate/deactivate hooks | Active schedule flow enqueues `flow_run` on cron; deactivate stops ticks |
| **T2** | `flows.trigger.schedule` node + tests | E2E: activate → wait/mock tick → execution success |
| **T3** | `flow_static_data` + poll framework | Dummy poll node in tests |
| **T4** | `flows.trigger.google_drive` | Parity tests against mocked Drive API (mirror `tests/flows/nodes/google_drive/`) |
| **T5** | `flow_webhook_routes` on activate + `flows.trigger.webhook` node | Optional; parallel track |

**Out of scope for T1–T4:** Gmail trigger, Drive push webhooks, sub-minute schedules,
exactly-once idempotency index (optional T4+), SSE execution push.

**Config:** `FLOW_SCHEDULER_ENABLED=1`, `FLOW_SCHEDULER_LEADER_TTL_SECS=30` on processes
that may become leader; workers unchanged (`N_DOCROUTER_WORKERS`).
