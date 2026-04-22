# DocRouter Flows — Technical Design Spec (v3)

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

- Add a reusable flow engine that is independent of DocRouter-specific logic.
- Support versioned flow definitions.
- Support manual runs and trigger-based runs.
- Support a small set of built-in generic nodes plus DocRouter nodes.
- Persist execution state and execution history.
- Support a React Flow canvas editor.
- Keep runtime semantics simple and deterministic.

### Non-goals for v1

- Expression language (`={{ $json.field }}`)
- Looping / cycles / re-entrant execution
- Multi-trigger flows
- Sub-flows
- Sandboxed user code
- SSE streaming for execution progress
- Full n8n compatibility

---

## 3. Architectural split

The implementation is intentionally split into two layers.

### 3.1 Generic flow engine

Package: `analytiq_data/flows/`

Responsibilities:

- flow validation
- node registry
- graph execution
- execution persistence helpers
- built-in generic nodes

This package must not import DocRouter-specific code.

### 3.2 DocRouter integration layer

Package: `app/flows/`

Responsibilities:

- registering DocRouter node types
- document fetch / OCR / LLM / tagging integrations
- trigger dispatch integration
- FastAPI routes
- worker integration

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
8. `flows.code` is internal/admin-only in v1 and disabled by default.

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
- `flow_version`: monotonic version counter
- `updated_at`, `updated_by`: audit fields

#### Rules

- Manual runs may default to the latest revision unless the caller provides a
  specific `flow_revid`.
- Trigger-based runs must use `active_flow_revid`.
- Saving a new revision does not change `active_flow_revid`.
- Activating a flow sets both `active = true` and `active_flow_revid`.
- Deactivating a flow clears `active_flow_revid`.

### 5.2 `flow_revisions` collection (immutable graph snapshots)

One document per saved graph revision.

```json
{
  "_id": "<flow_revid>",
  "flow_id": "<flow_id>",
  "flow_version": 3,
  "nodes": [],
  "connections": {},
  "settings": {},
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
- `nodes`: node definitions
- `connections`: adjacency map
- `settings`: flow-level execution settings
- `pin_data`: optional authoring/debug state
- `graph_hash`: canonical hash of `{nodes, connections, settings}`
- `engine_version`: flow-engine semantics version
- `created_at`, `created_by`: audit fields

#### Rules

- Flow revisions are immutable.
- Old revisions remain runnable by `flow_revid`.
- Name-only updates do not create a new revision.
- `pin_data` belongs to the revision because it is tied to a specific graph.

### 5.3 `flow_runtime_state` collection (cross-run persistent state)

Use a separate collection for state that must survive across runs and across
revisions.

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
- future `static_data`

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
  "status": "running",
  "started_at": "2026-04-22T00:00:00Z",
  "finished_at": null,
  "stop_requested": false,
  "run_data": {},
  "error": null,
  "trigger": {
    "type": "manual",
    "document_id": null
  }
}
```

#### Meaning

- `status`: `running | success | error | stopped`
- `stop_requested`: cooperative cancellation flag
- `run_data`: per-node outputs in storage-safe form
- `trigger`: origin metadata

#### Storage rules

- Large binary data must not be stored inline in `run_data`.
- Persist binary references (`storage_id`) instead.
- JSON payloads may be truncated or capped by policy.
- `error` may be a string in v1 and a structured object in v2.

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
  "disabled": false,
  "continueOnFail": false,
  "notes": "optional"
}
```

### Node field meanings

- `id`: stable UUID within the flow
- `name`: human-readable label, unique within the flow
- `type`: node type registry key
- `position`: canvas coordinates (editor-only)
- `parameters`: type-specific config
- `disabled`: skip this node at runtime
- `continueOnFail`: convert node failure into data and continue
- `notes`: editor-only annotation

### 6.2 Connection shape

Connections follow an n8n-style adjacency map, keyed by **source node id**.

```text
connections: {
  [sourceNodeId: string]: {
    "main": Array<Array<{ node: string, type: "main", index: number }>>
  }
}
```

- `node` refers to the destination node id.
- Edges are keyed by node **id**, not node **name**.
- This makes the graph rename-safe.

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

---

## 8. Validation rules

A flow revision is valid only if all of the following hold.

1. `nodes[].id` is unique.
2. `nodes[].name` is unique.
3. Every edge source exists.
4. Every edge destination exists.
5. Every edge output slot is valid for the source node type.
6. Every edge input slot is valid for the destination node type.
7. The graph is acyclic.
8. The flow contains exactly one trigger node.
9. Every node's `parameters` validate against its JSON schema.
10. Disconnected subgraphs are rejected in v1.

Validation should run on:

- create
- update
- import
- activate
- execution startup

---

## 9. Node registry

### 9.1 Protocol

```python
from typing import Protocol, runtime_checkable

@runtime_checkable
class NodeType(Protocol):
    key: str
    label: str
    min_inputs: int
    max_inputs: int | None
    outputs: int
    parameter_schema: dict

    async def execute(
        self,
        context: "ExecutionContext",
        node: dict,
        input_items: list[list["FlowItem"]],
    ) -> list[list["FlowItem"]]: ...
```

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
    json: dict
    binary: dict[str, "BinaryRef"]
    meta: dict
```

### `BinaryRef`

```python
@dataclass
class BinaryRef:
    mime_type: str
    file_name: str | None
    data: bytes | None
    storage_id: str | None
```

### Semantics

- `json` is the main payload.
- `binary` carries file references.
- `meta` carries lineage and routing metadata.
- Nodes should treat `meta` as engine-managed data.

---

## 11. Node types in v1

### 11.1 Built-in generic nodes

| Key | Inputs | Outputs | Description |
|-----|--------|---------|-------------|
| `flows.trigger.manual` | 0 | 1 | Emits the manual-run seed item. |
| `flows.webhook` | 1 | 1 | POSTs item JSON to a configured URL. |
| `flows.branch` | 1 | 2 | Routes items to one of two outputs based on a condition. |
| `flows.merge` | 2+ | 1 | Waits for all inputs, then concatenates them into one output list. |
| `flows.code` | 1 | 1 | Runs a small Python snippet. Internal/admin-only in v1. |

### 11.2 DocRouter nodes

| Key | Inputs | Outputs | Description |
|-----|--------|---------|-------------|
| `docrouter.trigger.manual` | 0 | 1 | Emits the target document as one item. |
| `docrouter.trigger.upload` | 0 | 1 | Fires when a document is uploaded and the flow is active. |
| `docrouter.ocr` | 1 | 1 | Runs OCR on the input document(s). |
| `docrouter.llm_extract` | 1 | 1 | Runs linked prompt-based extraction. |
| `docrouter.set_tags` | 1 | 1 | Applies configured tags. |
| `docrouter.webhook` | 1 | 1 | Sends data through DocRouter's webhook infrastructure. |

### Note on manual trigger nodes

DocRouter flows should use `docrouter.trigger.manual` explicitly when they need
document-aware manual runs. Avoid framing this as an engine-level "override" of
`flows.trigger.manual`; they are separate node types with separate semantics.

---

## 12. Execution semantics

### 12.1 Module layout

```text
analytiq_data/flows/
  __init__.py
  context.py
  engine.py
  execution.py
  node_registry.py
  nodes/
    trigger_node.py
    webhook_node.py
    branch_node.py
    merge_node.py
    code_node.py

app/flows/
  __init__.py
  nodes/
    manual_trigger_node.py
    upload_trigger_node.py
    ocr_node.py
    llm_node.py
    tag_node.py
    webhook_node.py
```

### 12.2 ExecutionContext

```python
@dataclass
class ExecutionContext:
    organization_id: str
    execution_id: str
    flow_id: str
    flow_revid: str
    run_data: dict[str, Any]
    services: Any
    stop_requested: bool = False
    logger: Any | None = None
```

`services` is intentionally opaque to the engine.

### 12.3 Core execution model

- Load the exact `flow_revid` to execute.
- Validate the revision.
- Build a topological order.
- Seed the trigger node.
- Execute nodes once, in topological order.
- Each node receives one item list per input slot.
- Each node returns one item list per output slot.
- Downstream input buffers accumulate upstream outputs.
- A node becomes runnable when all required inputs are present.
- Persist execution progress incrementally.
- Before each node, check `stop_requested`.

### 12.4 Merge semantics

In v1, `flows.merge` does exactly one thing:

- concatenate all input-slot item lists into one output list

This is intentionally simple and deterministic.

### 12.5 Error handling

If `continueOnFail = false`:

- node failure ends the execution with `status = error`

If `continueOnFail = true`:

- emit a single output item with an error envelope
- continue downstream execution

Example error envelope:

```json
{
  "json": {
    "_error": {
      "node_id": "<node_id>",
      "message": "..."
    }
  },
  "binary": {},
  "meta": {}
}
```

### 12.6 Stop semantics

- Stop is cooperative, not preemptive.
- The stop endpoint sets `flow_executions.stop_requested = true`.
- The worker checks for stop between node executions.
- v1 does not attempt to hard-kill in-flight node code.

---

## 13. API design

FastAPI route file: `app/routes/flows.py`

### 13.1 Routes

| Method | Path | Purpose |
|--------|------|---------|
| `POST` | `/v0/orgs/{org_id}/flows` | Create a flow |
| `GET` | `/v0/orgs/{org_id}/flows` | List latest revisions |
| `GET` | `/v0/orgs/{org_id}/flows/{flow_id}/revisions/{flow_revid}` | Get a specific revision |
| `PUT` | `/v0/orgs/{org_id}/flows/{flow_id}` | Save a new revision |
| `DELETE` | `/v0/orgs/{org_id}/flows/{flow_id}` | Delete flow + revisions + runtime state |
| `GET` | `/v0/orgs/{org_id}/flows/{flow_id}/versions` | List revisions |
| `POST` | `/v0/orgs/{org_id}/flows/{flow_id}/activate` | Activate a revision |
| `POST` | `/v0/orgs/{org_id}/flows/{flow_id}/deactivate` | Deactivate the flow |
| `POST` | `/v0/orgs/{org_id}/flows/{flow_id}/run` | Start a manual run |
| `GET` | `/v0/orgs/{org_id}/flows/{flow_id}/executions` | List executions |
| `GET` | `/v0/orgs/{org_id}/flows/{flow_id}/executions/{exec_id}` | Get execution detail |
| `POST` | `/v0/orgs/{org_id}/flows/{flow_id}/executions/{exec_id}/stop` | Request stop |
| `GET` | `/v0/orgs/{org_id}/flows/node-types` | List node type descriptors |

### 13.2 Save request

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
- If `base_flow_revid` is stale, return `409 Conflict`.
- If only the name changes and `graph_hash` is unchanged, update the stable
  header only.

### 13.3 Activate request

Optional request body:

```json
{
  "flow_revid": "<optional>"
}
```

If omitted, activate the latest revision.

### 13.4 Run request

```json
{
  "flow_revid": "<optional>",
  "document_id": "<optional>"
}
```

---

## 14. Worker integration

Queue-dispatched runs should use the existing worker infrastructure.

### Queue payload

```python
await ad.queue.send_msg(analytiq_client, "flow_run", {
    "flow_id": flow_id,
    "flow_revid": flow_revid,
    "execution_id": exec_id,
    "organization_id": org_id,
})
```

### Worker rules

- The worker must execute the exact `flow_revid` from the queue message.
- It must never re-resolve "latest" at runtime.
- It must check `stop_requested` between node executions.
- Once enqueued, the run is immutable with respect to flow content.

### v1 progress model

Frontend polls execution status every 2 seconds.

---

## 15. Trigger dispatch

Trigger-based execution needs a way to resolve active flows for a given event.

Possible implementation choices:

- direct MongoDB query
- in-memory index refreshed on activate/deactivate
- small helper keyed by `(organization_id, trigger_type)`

Regardless of implementation, dispatch must resolve the exact
`active_flow_revid` for each matching flow.

---

## 16. Frontend canvas

React Flow is already installed and will be used for the editor.

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

- prevent obviously invalid saves where possible
- show backend validation errors clearly
- show stale-editor conflicts (`409 Conflict`)
- show both latest revision and active revision
- show execution history and per-node output/status

---

## 17. Implementation order

1. `analytiq_data/flows/` — validation, registry, engine
2. `app/flows/` — DocRouter node registrations
3. `app/routes/flows.py` — CRUD, activate, run, execution endpoints
4. worker `flow_run` handler
5. frontend list page + canvas editor
6. frontend run panel + polling

Steps 1 to 4 are backend-only and should be fully unit/integration tested before
frontend work depends on them.

---

## 18. Main improvements from the previous draft

This version makes the design clearer by:

- removing ambiguity around the active revision
- separating revision content from persistent runtime state
- making DAG-only execution explicit
- making merge behavior explicit
- avoiding confusion between `flows.trigger.manual` and
  `docrouter.trigger.manual`
- using a clearer revision-read route shape
- tightening save concurrency and stop semantics
