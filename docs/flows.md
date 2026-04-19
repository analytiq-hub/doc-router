# doc-router flows — implementation plan

A **flow** is a saved, reusable processing pipeline: a directed graph of
**nodes** (OCR, LLM extraction, tag assignment, webhook call, schema validation,
branch/merge) connected by **edges**. A user draws it once on a canvas, saves
it, and can run it on demand against a document or a batch. This fills the gap
between the current single-document linear pipeline (upload → OCR → LLM) and a
configurable multi-step graph.

The design borrows concepts from [n8n.md](n8n.md) but is adapted to
doc-router's Python/FastAPI/MongoDB stack.

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
  "flow_version": 3
}
```

| Field | Meaning |
|-------|---------|
| `_id` | Stable `flow_id`. Never changes. |
| `organization_id` | Org scope. |
| `name` | Display name. Renames update this document only, no new revision. |
| `active` | Whether trigger-based auto-runs are enabled. |
| `flow_version` | Monotonic counter; incremented by `find_one_and_update($inc)` each time a content revision is created. |

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
  "static_data": null,
  "pin_data": null,
  "created_at": "...",
  "created_by": "<user_id>"
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
| `static_data` | Persistent cross-run state written by nodes (see below). `null` in v1. |
| `pin_data` | Per-node output overrides used for canvas testing (see below). `null` in v1. |
| `created_at` | Timestamp when this revision was saved. |
| `created_by` | `user_id` of the author. |

**List** returns the latest revision per `flow_id` (same `$group + $first`
aggregation used by prompts and schemas). **Get** takes a `flow_revid`.
**Update** inserts a new revision row and increments `flow_version`; a
name-only change updates `flows.name` in-place without creating a new revision.
**Delete** removes all revision rows and the stable header.

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
  "static_data": null,
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
across executions of the same flow. Analogous to n8n's `staticData`
(`IWorkflowBase.staticData: IDataObject`), which is updated in-place on the
`WorkflowEntity` row after each execution. In doc-router this will live on the
`flow_revision` (or a dedicated `flow_static_data` side-collection if write
frequency justifies it). Intended use: a webhook-trigger node that stores a
cursor or last-seen timestamp so it only fetches new documents on each run.

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

A Python registry (`analytiq_data/flows/node_registry.py`) maps a type key to
a descriptor:

```python
@dataclass
class NodeType:
    key: str               # e.g. "docrouter.llm_extract"
    label: str             # UI display name
    inputs: int            # number of main inputs (0 = trigger/entry)
    outputs: int           # number of main outputs
    parameter_schema: dict # JSON Schema for the node "parameters" field
    execute: Callable      # async fn(context, node, input_items) -> output_items
```

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

`json` is what every node reads and writes in the common case. For doc-router
nodes it typically contains document-scoped fields such as `document_id`,
`organization_id`, extraction results, tag lists, and any data produced by
earlier nodes.

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

`meta` carries lineage back to the input item(s) that produced each output
item (analogous to n8n's `pairedItem`). Used by the engine for fan-out
tracking and by the canvas UI for data-flow visualisation in v2. Steps should
not write to `meta` directly; the engine populates it.

The `execute` signature in full:

```python
async def execute(
    context: ExecutionContext,
    node: dict,                         # the node instance from the flow revision
    input_items: list[list[FlowItem]],  # one list per input slot
) -> list[list[FlowItem]]:              # one list per output slot
    ...
```

### Built-in node types

| Key | Inputs | Outputs | What it does |
|-----|--------|---------|--------------|
| `docrouter.trigger.manual` | 0 | 1 | Entry point for a manual run; emits the target document as a single item. |
| `docrouter.trigger.upload` | 0 | 1 | Fires when a new document is uploaded (requires `active: true` on the flow). |
| `docrouter.ocr` | 1 | 1 | Runs OCR on each input document. |
| `docrouter.llm_extract` | 1 | 1 | Runs LLM extraction with a linked prompt revision. |
| `docrouter.set_tags` | 1 | 1 | Assigns a configured set of tags to each input document. |
| `docrouter.webhook` | 1 | 1 | POSTs each item as JSON to a configured URL. |
| `docrouter.branch` | 1 | 2 | Routes items down output 0 or 1 based on a condition (v1: field equality check). |
| `docrouter.merge` | 2+ | 1 | Waits for all inputs then combines items and continues. |
| `docrouter.code` | 1 | 1 | Runs a small Python snippet (in-process, restricted helpers, no full sandbox in v1). |

---

## Layer 3 — Execution engine

**New module: `analytiq_data/flows/`**

```
analytiq_data/flows/
  __init__.py
  engine.py          # graph runner: topological order, fan-out, merge/wait
  execution.py       # execution record CRUD (MongoDB: flow_executions)
  node_registry.py   # type registry + built-in node implementations
  context.py         # ExecutionContext dataclass
  nodes/
    ocr_node.py
    llm_node.py
    tag_node.py
    webhook_node.py
    branch_node.py
    merge_node.py
    code_node.py
```

### Engine algorithm (`engine.py`)

1. Load the latest `flow_revision` for the given `flow_id`; build
   `nodes_by_id`; invert `connections` to `inputs_by_destination` (same
   inversion as `mapConnectionsByDestination` in n8n — see
   [n8n.md § 3. Execution engine](n8n.md)).
2. Find entry nodes: nodes with in-degree 0 or type `docrouter.trigger.*`.
3. Topological BFS: maintain a `ready_queue` and a `waiting` map
   (`node_id → remaining_input_count`).
4. For each ready node: look up node type → call
   `execute(context, node, input_items)` → `output_items`.
5. Fan-out: for each output edge, deliver items to the destination; decrement
   its waiting counter; enqueue the destination when its counter reaches 0.
6. Record per-node `run_data` in `ExecutionContext`; persist to
   `flow_executions` on completion.
7. On error: mark execution failed, store error message, respect
   `continueOnFail`.

### ExecutionContext (`context.py`)

```python
@dataclass
class ExecutionContext:
    analytiq_client: Any
    organization_id: str
    execution_id: str
    flow_id: str
    flow_revid: str          # the specific revision being executed
    run_data: dict[str, Any] # node_id -> output items (mirrors n8n runData)
    cancelled: bool = False
```

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
| `run_data` | Per-node output items |
| `error` | Error message if status is `"error"` |

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
| `POST` | `/v0/orgs/{org_id}/flows/{flow_id}/activate` | Set `active: true` (no new revision) |
| `POST` | `/v0/orgs/{org_id}/flows/{flow_id}/deactivate` | Set `active: false` (no new revision) |
| `POST` | `/v0/orgs/{org_id}/flows/{flow_id}/run` | Manual run against latest revision (body: `{ document_id? }`) |
| `GET` | `/v0/orgs/{org_id}/flows/{flow_id}/executions` | List executions |
| `GET` | `/v0/orgs/{org_id}/flows/{flow_id}/executions/{exec_id}` | Get execution + per-node output |
| `POST` | `/v0/orgs/{org_id}/flows/{flow_id}/executions/{exec_id}/stop` | Cancel a running execution |
| `GET` | `/v0/orgs/{org_id}/flows/node-types` | List available node type descriptors |

Auth: same `get_org_user` dependency used across all other routes.

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
`worker_ocr()` and `worker_llm()`. The engine runs inside this coroutine.

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

---

## Out of scope for v1

| Feature | Target |
|---------|--------|
| Expression language (`={{ $json.field }}`) | v2 |
| Sandboxed Code node (`vm2` / `isolated-vm`) | v2 |
| Sub-flows / nested runs | v2 |
| In-canvas data preview (n8n "run data" overlay) | v2 |

---

## Implementation order

```
1. analytiq_data/flows/   — engine + node registry (no API yet, unit-testable)
2. app/routes/flows.py    — CRUD + run + execution endpoints
3. worker flow_run handler — slow-run queue consumer
4. Frontend list page + canvas editor
5. Frontend run panel + execution status polling
```

Steps 1–3 are backend-only and can be developed and tested independently of
the frontend.
