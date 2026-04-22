# doc-router flows — implementation plan

A **flow** is a saved, reusable processing pipeline: a directed graph of
**nodes** (OCR, LLM extraction, tag assignment, webhook call, schema validation,
branch/merge) connected by **edges**. A user draws it once on a canvas, saves
it, and can run it on demand against a document or a batch. This fills the gap
between the current single-document linear pipeline (upload → OCR → LLM) and a
configurable multi-step graph.

The design borrows concepts from [n8n.md](n8n.md) but is adapted to
doc-router's Python/FastAPI/MongoDB stack.

**Separation of concerns:** the flow engine (`analytiq_data/flows/`) is
deliberately kept free of any doc-router domain logic. It knows nothing about
documents, OCR, prompts, or schemas. Doc-router-specific node types are
registered at application startup from `app/flows/`. This lets the engine be
released or used independently.

---

## Layer 1 — Document model (storage)

Flows follow the same `{resource}_id` / `{resource}_revid` versioning scheme
used by prompts and schemas. Two MongoDB collections:

### `flows` collection (stable header)

One document per flow, keyed by `_id` = `flow_id`. Holds identity and mutable
state that is **not** versioned:

```json
{
  "_id": "<ObjectId>",
  "organization_id": "...",
  "name": "Invoice processing",
  "active": false,
  "active_flow_revid": "<flow_revid|null>",
  "flow_version": 3
}
```

| Field | Meaning |
|-------|---------|
| `_id` | Stable `flow_id`. Never changes. |
| `organization_id` | Org scope. |
| `name` | Display name. Renames update this document only, no new revision. |
| `active` | Whether trigger-based auto-runs are enabled. |
| `active_flow_revid` | Pins the exact revision used for trigger-based runs. `null` when inactive. |
| `flow_version` | Monotonic counter; incremented by `find_one_and_update($inc)` each time a content revision is created. |

Clarifications:

- **Trigger-based runs** (upload/webhook/poll) must execute `active_flow_revid`.
- **Manual runs** may default to the latest revision, but can also accept an explicit `flow_revid`.
- Saving a new revision does **not** implicitly change `active_flow_revid`.
- Activating a flow sets `active = true` and sets `active_flow_revid` to either the latest revision or an explicitly supplied revision.
- Deactivating a flow sets `active = false` and `active_flow_revid = null`.

### `flow_revisions` collection (versioned content)

One document per saved version of the graph. The `_id` of each row is the
`flow_revid` returned to callers:

```json
{
  "_id": "<ObjectId>",
  "flow_id": "<flow_id>",
  "flow_version": 3,
  "nodes": [],
  "connections": {},
  "settings": {},
  "pin_data": null,
  "created_at": "...",
  "created_by": "<user_id>",
  "graph_hash": "<sha256>",
  "engine_version": 1
}
```

| Field | Meaning |
|-------|---------|
| `_id` | `flow_revid`. Identifies this specific revision. |
| `flow_id` | FK → `flows._id`. |
| `flow_version` | Version number at the time this revision was saved. |
| `nodes` | Array of node instances (see node shape below). |
| `connections` | Source-keyed adjacency map (see connection shape below). |
| `settings` | Flow-level execution policy (timeout, error handling, etc.). |
| `pin_data` | Per-node output overrides used for canvas testing (see below). `null` in v1. |
| `created_at` | Timestamp when this revision was saved. |
| `created_by` | `user_id` of the author. |
| `graph_hash` | Hash of canonical `{nodes, connections, settings}` for cheap equality checks and “rename-only” detection. |
| `engine_version` | Execution semantics version for future migrations (even if node types don’t carry a per-node version in v1). |

Clarifications:

- `flow_revisions` are **immutable snapshots**. Old revisions remain runnable by `flow_revid`.
- `pin_data` belongs on the revision because it is authoring/debug state tied to a specific graph.

**List** returns the latest revision per `flow_id` (same `$group + $first`
aggregation used by prompts and schemas). **Get** takes a `flow_revid`.
**Update** inserts a new revision row and increments `flow_version`; a
name-only change updates `flows.name` in-place without creating a new revision.
**Delete** removes all revision rows and the stable header.

### `flow_runtime_state` collection (persistent cross-run state)

Persistent state that must survive across executions and across revisions (for example poll cursors) should not live on a revision. Store it separately:

```json
{
  "_id": "<ObjectId>",
  "flow_id": "<flow_id>",
  "organization_id": "<org_id>",
  "node_id": "<node_id>",
  "data": {},
  "updated_at": "...",
  "updated_by_execution_id": "<exec_id>"
}
```

Rules:

- State is keyed by `flow_id` + `node_id` (not `flow_revid`), so a new revision inherits the same runtime state unless explicitly reset.
- This is the future home of `static_data`.

### Portable export format

A flow revision is self-contained and portable. The export document adds `name`
from the stable header so the file is readable without a separate lookup:

```json
{
  "flow_id": "<ObjectId>",
  "flow_version": 3,
  "name": "Invoice processing",
  "nodes": [
    {
      "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
      "name": "Run OCR",
      "type": "docrouter.ocr",
      "position": [240, 300],
      "parameters": {},
      "disabled": false,
      "continueOnFail": false
    },
    {
      "id": "b2c3d4e5-f6a7-8901-bcde-f12345678901",
      "name": "Extract invoice fields",
      "type": "docrouter.llm_extract",
      "position": [480, 300],
      "parameters": { "prompt_revid": "..." }
    }
  ],
  "connections": {
    "a1b2c3d4-e5f6-7890-abcd-ef1234567890": {
      "main": [
        [{ "node": "b2c3d4e5-f6a7-8901-bcde-f12345678901", "type": "main", "index": 0 }]
      ]
    }
  },
  "settings": {},
  "pin_data": null,
  "created_at": "2024-01-02T00:00:00Z",
  "created_by": "<user_id>"
}
```

On **import**: if `flow_id` already exists in the org, a new revision is
created under that `flow_id` and `name` is updated on the stable header. If
`flow_id` is absent or belongs to a different org, a new stable header is
created and the `flow_id` in the imported document is remapped.

Edges reference node **`id`** (UUID), not node **`name`**. This makes the graph
rename-safe. On import, node `id` collisions within the same flow are resolved
by remapping to fresh UUIDs and rewriting the `connections` map accordingly.

### Future fields: `static_data`, `pin_data`, `meta`

These three fields are reserved now so the storage schema and export format do
not need a breaking change when they are activated. They are stored as `null`
and ignored by the engine in v1.

**`static_data`** — persistent key/value state that a node can read and write
across executions of the same flow. In doc-router this will live in
`flow_runtime_state` (keyed by `flow_id` + `node_id`), not on `flow_revisions`.
Intended use: a trigger/poll node that stores a cursor or last-seen timestamp so
it only fetches new documents on each run.

**`pin_data`** — per-node output overrides keyed by node `id`. When a node has
pinned data the engine substitutes it for the real execution output, letting
authors iterate on downstream nodes without re-running expensive upstream nodes
(OCR, LLM). Analogous to n8n's `pinData` (`IPinData: { [nodeName]:
INodeExecutionData[] }`). In the canvas UI this corresponds to the "pin output"
action on a node after a test run.


### Node shape

| Field | Type | Meaning |
|-------|------|---------|
| `id` | string | Stable UUID for this node instance within the flow. |
| `name` | string | Human label, unique within the flow. |
| `type` | string | Registry key, e.g. `"docrouter.llm_extract"`. |
| `position` | `[number, number]` | Canvas coordinates `[x, y]`. Editor-only. |
| `parameters` | object | Type-specific config (opaque to engine). |
| `disabled` | boolean? | Skip this node during execution. |
| `continueOnFail` | boolean? | Continue flow when this node errors. |
| `notes` | string? | Editor-only annotation. |

Key decisions diverging from n8n:

- **Edges keyed by node `id`** (UUID), not `name`. Nodes can be freely
  renamed; id-keyed edges are stable.
- **No `typeVersion` per node in v1** — node types are versioned in the type
  registry, not stored per node instance.
- **`active` flag lives on the stable header**, not in a revision, so
  activate/deactivate never creates a new revision.
  Trigger runs execute `active_flow_revid`, not “latest”.

### Connection shape

Same structure as n8n (see [n8n.md § 1. Workflow document model](n8n.md)):

```
connections: {
  [sourceNodeId: string]: {
    "main": Array<Array<{ node: string, type: "main", index: number }>>
  }
}
```

`node` in each target refers to the **destination node `id`** (not `name`).

---

## Layer 2 — Node type registry

`analytiq_data/flows/node_registry.py` defines the `NodeType` Protocol and a
module-level registry. The engine is only aware of the Protocol; all concrete
node types are registered from outside by the application layer.

### NodeType Protocol

```python
from typing import Protocol, runtime_checkable

@runtime_checkable
class NodeType(Protocol):
    key: str               # unique type key, e.g. "flows.branch"
    label: str             # UI display name
    min_inputs: int        # minimum number of main input slots (0 = trigger/entry)
    max_inputs: int | None # maximum number of main input slots (None = unbounded)
    outputs: int           # number of main output slots
    parameter_schema: dict # JSON Schema for the node "parameters" field

    async def execute(
        self,
        context: "ExecutionContext",
        node: dict,                        # node instance from the flow revision
        input_items: list[list["FlowItem"]],
    ) -> list[list["FlowItem"]]: ...
```

### Registration

```python
# node_registry.py
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

The engine calls `node_registry.get(node["type"])` at runtime. It never
imports concrete node implementations directly.

### Item format

`FlowItem` is the **only thing that crosses a node boundary**. A node receives
a list of these items as input and returns lists of them as output. Nothing
else — not `run_data`, not other nodes' outputs, not any shared mutable store
— is accessible through the normal execution path.

```python
@dataclass
class FlowItem:
    json:    dict                  # primary payload: arbitrary key/value data
    binary:  dict[str, BinaryRef] # file attachments keyed by name, e.g. "data"
    meta:    dict                  # lineage and routing hints (internal use)
```

`json` is what every node reads and writes in the common case.

`binary` travels alongside `json` when a node produces or consumes file data.
Each key is a named attachment:

```python
@dataclass
class BinaryRef:
    mime_type:  str        # e.g. "application/pdf"
    file_name:  str | None # original filename
    data:       bytes | None  # inline for small files
    storage_id: str | None    # reference to MongoDB blob for large files
```

Storage rule (v1):

- `binary.data` must not be persisted inline inside `flow_executions.run_data` except for small debug payloads under a configurable size cap. Durable execution storage should persist `storage_id` references, not raw bytes.

`meta` carries lineage back to the input item(s) that produced each output
item (analogous to n8n's `pairedItem`). Used by the engine for fan-out
tracking and by the canvas UI for data-flow visualisation in v2. Nodes should
not write to `meta` directly; the engine populates it.

### Engine-built-in node types

These generic nodes are registered automatically when `analytiq_data/flows` is
imported. They have no dependency on doc-router domain logic.

| Key | Inputs | Outputs | What it does |
|-----|--------|---------|--------------|
| `flows.trigger.manual` | 0 | 1 | Entry point for a manual run; emits the seed item supplied by the caller. |
| `flows.webhook` | 1 | 1 | POSTs each item as JSON to a configured URL. |
| `flows.branch` | 1 | 2 | Routes items down output 0 or 1 based on a field equality condition. |
| `flows.merge` | 2+ | 1 | Waits for all inputs, then combines items and continues. |
| `flows.code` | 1 | 1 | Runs a small Python snippet. **Admin/internal-only in v1**. Disabled by default. No sandbox guarantees. |

### Doc-router node types (registered externally)

Doc-router-specific nodes live in `app/flows/nodes/` and are registered at
application startup. They depend on `analytiq_client` carried in
`ExecutionContext.services`.

| Key | Inputs | Outputs | What it does |
|-----|--------|---------|--------------|
| `docrouter.trigger.manual` | 0 | 1 | Manual-run entry; emits the target document as a single item. |
| `docrouter.trigger.upload` | 0 | 1 | Fires when a new document is uploaded (requires `active: true`). |
| `docrouter.ocr` | 1 | 1 | Runs OCR (Textract) on each input document. |
| `docrouter.llm_extract` | 1 | 1 | Runs LLM extraction with a linked prompt revision. |
| `docrouter.set_tags` | 1 | 1 | Assigns a configured set of tags to each input document. |
| `docrouter.webhook` | 1 | 1 | POSTs each item via doc-router's webhook mechanism (signing, retries). |

`docrouter.trigger.manual` overrides `flows.trigger.manual` when the caller
supplies a `document_id`; it fetches the document and sets `document_id`,
`organization_id`, and a `BinaryRef` on the seed item before emitting it.

`docrouter.webhook` wraps the generic `flows.webhook` behaviour and integrates
with doc-router's existing webhook infrastructure (HMAC signing, delivery
retries, event log).

---

## Validation rules (v1)

Before a flow revision can be executed (and ideally before it can be saved), it
must pass structural validation.

A revision is valid only if all of the following hold:

1. `nodes[].id` is unique within the revision.
2. `nodes[].name` is unique within the revision.
3. Every edge source node exists.
4. Every edge destination node exists.
5. Every edge output slot is within the source node type’s declared output range.
6. Every edge input slot is within the destination node type’s declared input range.
7. The graph is **acyclic** (DAG-only in v1).
8. The flow contains exactly **one trigger node** in v1.
9. All node `parameters` validate against the node type’s `parameter_schema`.
10. Disabled nodes may exist, but connections to/from them are still validated structurally.

Additional v1 constraints:

- Cycles are rejected.
- Disconnected subgraphs are rejected unless explicitly supported later.
- Exactly one trigger node is allowed in v1 (multi-trigger flows are v2).

## Layer 3 — Execution engine

### Module layout

```
analytiq_data/flows/            # standalone engine — no doc-router imports
  __init__.py                   # imports node_registry; registers built-in nodes
  engine.py                     # graph runner: topological BFS, fan-out, merge/wait
  execution.py                  # flow_executions CRUD (MongoDB)
  node_registry.py              # NodeType Protocol + register() / get() / list_all()
  context.py                    # ExecutionContext, FlowItem, BinaryRef
  nodes/                        # engine built-in node implementations
    trigger_node.py             # flows.trigger.manual
    webhook_node.py             # flows.webhook
    branch_node.py              # flows.branch
    merge_node.py               # flows.merge
    code_node.py                # flows.code

app/flows/                      # doc-router node package — registered at startup
  __init__.py                   # calls node_registry.register() for each node below
  nodes/
    manual_trigger_node.py      # docrouter.trigger.manual
    upload_trigger_node.py      # docrouter.trigger.upload
    ocr_node.py                 # docrouter.ocr
    llm_node.py                 # docrouter.llm_extract
    tag_node.py                 # docrouter.set_tags
    webhook_node.py             # docrouter.webhook (wraps flows.webhook + signing)
```

`app/main.py` imports `app/flows` so registration happens before the first
request.

### Engine algorithm (`engine.py`)

1. Load the target `flow_revid` (do not resolve “latest” during worker execution)
   and build `nodes_by_id`.
2. Validate the revision (see § Validation rules).
3. Build `inputs_by_destination` from `connections` (destination-indexed adjacency).
4. Compute a topological order; reject if the graph is cyclic.
5. Seed the trigger node with the initial item list.
6. Execute each node at most **once per execution** in topological order.
7. Each node receives `input_items: list[list[FlowItem]]`, one list per input slot.
8. Each node returns `output_items: list[list[FlowItem]]`, one list per output slot.
9. For each outgoing edge, append output items into the destination node’s input slot buffer.
10. A node becomes runnable when all required input slots have been populated by upstream completion.
11. Persist node completion incrementally to `flow_executions`.
12. On terminal success, mark execution `success`.
13. On stop request, mark execution `stopped` at the next safe cancellation boundary (between node executions).
14. On error, mark execution `error` unless handled by `continueOnFail`.

### Execution semantics (v1)

- A node runs at most once per execution.
- v1 supports DAG-style batch propagation, not cycles/loop nodes/re-entry.
- `flows.merge` concatenates all input-slot item lists into one output list, preserving lineage metadata in `meta`.
- `continueOnFail = true` converts a node failure into an output item with an error envelope in `json._error`, and downstream execution continues.
- `continueOnFail = false` fails the execution.

### ExecutionContext (`context.py`)

```python
@dataclass
class ExecutionContext:
    organization_id: str
    execution_id: str
    flow_id: str
    flow_revid: str           # the specific revision being executed
    run_data: dict[str, Any]  # node_id -> output items (mirrors n8n runData)
    services: Any             # opaque to the engine; node implementations cast as needed
    stop_requested: bool = False
    logger: Any | None = None
```

`services` is intentionally typed `Any`. The engine never reads it. Each
registered node type casts it to whatever its implementation requires (e.g.
`analytiq_client` for doc-router nodes).

Stop semantics:

- `stop_requested` is hydrated from the persisted `flow_executions.stop_requested` flag between node executions.
- Nodes are not required to poll it internally in v1; the engine checks it at safe boundaries.

### Execution records (`flow_executions` collection)

| Field | Meaning |
|-------|---------|
| `_id` | Execution ID |
| `flow_id` | Parent flow (stable) |
| `flow_revid` | Specific revision that was executed |
| `organization_id` | Org scope |
| `status` | `"running"` \| `"success"` \| `"error"` \| `"stopped"` |
| `started_at` | Timestamp |
| `finished_at` | Timestamp (set on terminal status) |
| `stop_requested` | Cooperative cancellation flag set by the stop endpoint. |
| `run_data` | Per-node output items |
| `error` | Error message if status is `"error"` |
| `trigger` | Origin metadata, e.g. `{ type: "manual", document_id?: ... }`. |

Recommended execution document shape:

```json
{
  "_id": "<exec_id>",
  "flow_id": "<flow_id>",
  "flow_revid": "<flow_revid>",
  "organization_id": "<org_id>",
  "status": "running",
  "started_at": "...",
  "finished_at": null,
  "stop_requested": false,
  "run_data": {},
  "error": null,
  "trigger": {
    "type": "manual",
    "document_id": "<document_id|null>"
  }
}
```

Run data storage rules:

- `run_data` stores per-node outputs in a **storage-safe** form:
  - JSON payloads may be truncated/capped by policy.
  - binaries must be stored as references (`storage_id`), not raw bytes.
- `error` can start as a string in v1 but should become a structured object in v2.

---

## Layer 4 — API routes

New route file: `app/routes/flows.py`. Single contract — UI client and API-key
automation clients use the same paths and DTOs (no internal/external split; see
[n8n.md § 4. HTTP surfaces](n8n.md)).

| Method | Path | Action |
|--------|------|--------|
| `POST` | `/v0/orgs/{org_id}/flows` | Create flow; returns `flow_id` + `flow_revid` |
| `GET` | `/v0/orgs/{org_id}/flows` | List flows (latest revision per flow, pagination + filters) |
| `GET` | `/v0/orgs/{org_id}/flows/{flow_revid}` | Get a specific revision |
| `PUT` | `/v0/orgs/{org_id}/flows/{flow_id}` | Save new revision (or rename-only if graph unchanged) |
| `DELETE` | `/v0/orgs/{org_id}/flows/{flow_id}` | Delete all revisions + stable header |
| `GET` | `/v0/orgs/{org_id}/flows/{flow_id}/versions` | List all revisions for a flow |
| `POST` | `/v0/orgs/{org_id}/flows/{flow_id}/activate` | Set `active: true` and pin `active_flow_revid` (no new revision) |
| `POST` | `/v0/orgs/{org_id}/flows/{flow_id}/deactivate` | Set `active: false` (no new revision) |
| `POST` | `/v0/orgs/{org_id}/flows/{flow_id}/run` | Manual run against latest revision (body: `{ document_id? }`) |
| `GET` | `/v0/orgs/{org_id}/flows/{flow_id}/executions` | List executions |
| `GET` | `/v0/orgs/{org_id}/flows/{flow_id}/executions/{exec_id}` | Get execution + per-node output |
| `POST` | `/v0/orgs/{org_id}/flows/{flow_id}/executions/{exec_id}/stop` | Cancel a running execution |
| `GET` | `/v0/orgs/{org_id}/flows/node-types` | List all registered node type descriptors |

Auth: same `get_org_user` dependency used across all other routes.

### Save flow endpoint (`PUT /v0/orgs/{org_id}/flows/{flow_id}`)

Request body must include the base revision for optimistic concurrency:

```json
{
  "base_flow_revid": "<flow_revid>",
  "name": "Invoice processing",
  "nodes": [],
  "connections": {},
  "settings": {}
}
```

Rules:

- `base_flow_revid` is required.
- If `base_flow_revid` is not the latest revision for the flow, return `409 Conflict`.
- If only `name` changes and the `graph_hash` is unchanged, update `flows.name` only (no new revision).

### Activate endpoint (`POST /v0/orgs/{org_id}/flows/{flow_id}/activate`)

Optionally accept a body to pin a specific revision:

```json
{ "flow_revid": "<optional>" }
```

Rules:

- If omitted, activate the latest revision.
- Activation writes `active = true` and `active_flow_revid = chosen_revid`.

### Stop endpoint (`POST /v0/orgs/{org_id}/flows/{flow_id}/executions/{exec_id}/stop`)

- The endpoint sets `stop_requested = true` on the execution record.
- It does not guarantee immediate termination; the worker stops at the next safe boundary between node executions.

---

## Layer 5 — Worker integration

A manual run that includes slow nodes (multi-doc OCR, large LLM calls) is
dispatched via the existing queue rather than blocking the HTTP response:

```python
await ad.queue.send_msg(analytiq_client, "flow_run", {
    "flow_id": flow_id,
    "flow_revid": flow_revid,
    "execution_id": exec_id,
    "organization_id": org_id,
})
```

`worker.py` gains a `worker_flow_run()` coroutine alongside the existing
`worker_ocr()` and `worker_llm()`. The engine runs inside this coroutine,
with `ExecutionContext.services` set to the worker's `analytiq_client`.

Worker rules:

- The worker must execute the **exact `flow_revid`** passed in the queue message (never resolve “latest” at runtime).
- Queue-dispatched runs are immutable with respect to flow content: once enqueued, they always execute that `flow_revid`.
- Before each node execution, the worker re-reads (or checks) the execution’s persisted `stop_requested` flag.

Real-time progress in v1: poll `GET .../executions/{exec_id}` every 2 s on the
frontend. Upgrade to SSE (same pattern as the agent chat stream) in v2.

---

## Layer 6 — Frontend canvas

React Flow (`reactflow ^11.11.4`) is already installed. New pages and
components:

```
src/app/orgs/[orgId]/flows/              ← flow list page
src/app/orgs/[orgId]/flows/[flowId]/     ← canvas editor + run panel
src/components/flows/
  FlowCanvas.tsx          ← ReactFlow canvas, node drag/drop, edge drawing
  FlowNodeTypes.tsx        ← custom node renderers per node type
  FlowParameterPanel.tsx   ← right panel for editing selected node parameters
  FlowRunPanel.tsx         ← run button, execution history, per-node status
  useFlowEditor.ts         ← save/load, auto-save with debounce
  useFlowRun.ts            ← trigger run, poll/stream execution progress
```

UI constraints:

- The editor should prevent saving invalid graphs that fail backend validation.
- If save returns `409 Conflict`, the UI should show a “newer revision exists” conflict state.
- The activation UI should show both the latest saved revision and the currently active revision (`active_flow_revid`).

---

## Out of scope for v1

| Feature | Target |
|---------|--------|
| Expression language (`={{ $json.field }}`) | v2 |
| Sandboxed Code node (`vm2` / `isolated-vm`) | v2 |
| General multi-trigger flows | v2 |
| Cycles / loop nodes / re-entrant execution | v2 |
| Sub-flows / nested runs | v2 |
| In-canvas data preview (n8n "run data" overlay) | v2 |
| SSE progress streaming | v2 |

---

## Implementation order

```
1. analytiq_data/flows/   — engine + node registry (no API yet, unit-testable)
2. app/flows/             — doc-router node registrations
3. app/routes/flows.py    — CRUD + run + execution endpoints
4. worker flow_run handler — slow-run queue consumer
5. Frontend list page + canvas editor
6. Frontend run panel + execution status polling
```

Steps 1–4 are backend-only and can be developed and tested independently of
the frontend.
