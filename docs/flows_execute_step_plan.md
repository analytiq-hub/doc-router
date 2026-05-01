# Execute Step (single-node test run) — execution plan

This document compares **n8n**’s “Execute step” / partial manual execution with **DocRouter** today, lists API and engine gaps, and proposes a phased implementation so Edit mode can run **one node** (and any **missing upstream** precursors) like n8n’s red **Execute step** control.

## Reference: how n8n does it

### UI entry points

- **Node canvas toolbar**: `CanvasNodeToolbar.vue` → `executeNode()` → emits run with source `Node.executeNode`.
- **Node detail / NDV**: `Node.vue` → `executeNode()` → `emit('runWorkflow', node.name, 'Node.executeNode')`.
- **Central orchestration**: `packages/editor-ui/src/composables/useRunWorkflow.ts` → `runWorkflow({ destinationNode, source })`.

### Request payload (conceptual)

The editor calls the workflows **run** API with a rich body (see `workflows.store.ts` / `IStartRunData`), including:

| Field | Role |
|--------|------|
| `workflowData` | Current workflow JSON (nodes, connections, pin data, …) |
| `destinationNode` | **Node name** of the node to execute (n8n stops partial execution at this node’s completion for “step” UX) |
| `runData` | Prior **test** execution outputs keyed by **node name** (shape `IRunData`) — used to **reuse** upstream results |
| `startNodes` | Per-branch **restart points**: first upstream nodes (walking from destination’s **direct parents**) that lack run data / pin data or failed |
| `dirtyNodeNames` | Nodes whose parameters changed after their last run — forces re-execution even if `runData` exists (`partialExecutionVersion === 1` path) |
| `partialExecutionVersion` | Query flag (`-1` = server default, `0` = legacy `runPartialWorkflow`, `1` = `runPartialWorkflow2`) |

### Server routing

- `packages/cli/src/workflows/workflow-execution.service.ts` → `executeManually()` builds `IWorkflowExecutionDataProcess` and starts `WorkflowRunner`.
- `packages/cli/src/manual-execution.service.ts` → `runManually()`:
  - **No** `runData` / **no** `startNodes` → full run (`WorkflowExecute.run`), optionally still passing `destinationNode` in some paths.
  - **Has** `runData` + `startNodes` → **partial** execution: `runPartialWorkflow` or `runPartialWorkflow2` depending on `partialExecutionVersion`.

### Frontend algorithm for “Execute step”

`useRunWorkflow.ts` → `consolidateRunDataAndStartNodes(directParentNodes, runData, pinData, workflow)`:

- Walk from each **direct parent** of `destinationNode` up the main graph.
- For each branch, find the **first** node (moving upstream) that has **no** successful run entry and **no** pin data (or that **failed**); that node becomes a **`startNode`** for this partial run.
- Nodes **above** that gap that already have good run data are copied into a **trimmed** `newRunData` so the backend **reuses** them.

So: **precursors without run data run first**; precursors **with** valid test data are **not** re-run (unless marked dirty in v1).

---

## DocRouter today

### FastAPI

- **`POST /v0/orgs/{organization_id}/flows/{flow_id}/run`** (`packages/python/app/routes/flows.py`)
  - Body: `RunFlowRequest` — only `flow_revid` (optional) and `document_id` (optional).
  - Creates a **new** `flow_executions` document with **`run_data: {}`**, enqueues `flow_run`.

There is **no** field for:

- target / destination node id  
- client-supplied seed `run_data`  
- dirty-node hints  

### Worker + engine

- `packages/python/analytiq_data/msg_handlers/flow_run.py` loads revision + execution, builds `ExecutionContext` with stored `run_data`, calls `ad.flows.run_flow(...)`.
- `packages/python/analytiq_data/flows/engine.py` → `run_flow`:
  - Validates revision (single trigger, DAG, …).
  - Starts **`work`** from the **sole trigger** with empty inputs.
  - Runs **`_execute_loop`** until the queue is empty (full graph).
- **`pin_data`** on the revision is already respected (short-circuit like n8n pins).

### TypeScript SDK

- `RunFlowParams` in `packages/typescript/sdk/src/types/flows.ts` only mirrors `flow_revid` and `document_id`.
- `DocRouterOrgApi.runFlow()` posts that body only.

### Frontend

- “Execute workflow” runs the full flow and polls/logs execution (`FlowDetailPageClient` → `api.runFlow`).
- Node config modal / IoViewer do **not** yet expose **Execute step** or “run previous nodes for input”.

---

## Gap analysis

| Capability | n8n | DocRouter |
|------------|-----|-----------|
| Run full graph from trigger | Yes | Yes |
| Run **up to** a given node (stop downstream) | Yes (`destinationNode` + partial runner) | **No** |
| Seed execution with **existing** test `run_data` | Yes | **No** (always `{}`) |
| Per-branch **start** nodes when inputs are partially materialized | Yes | **No** |
| Re-run when parameters **newer** than last run | Yes (`dirtyNodeNames`) | **Not applicable yet** |
| Live push of node finishes | Push / websocket | **Polling** `getExecution` (acceptable for v1) |

**Conclusion:** FastAPI and the engine **do not** yet expose the primitives needed for n8n-style Execute step. The **queue + incremental `run_data` persistence** model is compatible; we need **request fields**, **validation**, and an **engine mode** (or sibling entrypoint) that implements partial execution and stop-at-target.

---

## Design goals (DocRouter)

1. **Execute step** on node **N**: after the run, **`run_data[N]`** exists (success or error), same schema as full runs.
2. **Precursors without usable output** (no entry in supplied editor `run_data`, not satisfied by `pin_data`, or previous error) **run first**, in correct dependency order.
3. **Precursors with valid cached `run_data`** from the **current editor test session** are **reused** (no re-execution), matching n8n’s default behavior.
4. **Optional later**: `dirty_node_ids` (or parameter-version timestamps) to invalidate cache for changed nodes. Precedence rule (set in P1, enforced in P2): if a node id appears in both `run_data` seed **and** `dirty_node_ids`, the dirty flag wins — the node is forced to re-execute and its seed entry is ignored. This must not be designed in reverse.
5. **Security / consistency**: server validates `flow_revid`, node ids belong to revision, and seeded `run_data` keys are **subset of revision node ids** (strip unknown keys). Each seed entry must also conform to the stored node-output shape (`{ "status": "success"|"error", "data": { "main": [[...]] }, ... }`); entries that fail shape validation are **rejected with a 422** rather than silently dropped, so clients learn of malformed payloads instead of getting a silent partial execution.

**Identifiers:** DocRouter uses **node `id`** (UUID) in `run_data` and connections; n8n uses **display names** in `IRunData`. The API and plan should use **`target_node_id`** and seed maps keyed by **id** (aligned with existing execution JSON).

---

## Proposed API

### Option A (recommended): extend `POST .../run`

Add optional fields to `RunFlowRequest` (all optional; default preserves today’s full-run behavior):

```json
{
  "flow_revid": "...",
  "document_id": "...",
  "target_node_id": "<uuid>",
  "run_data": { "<node_id>": { "status": "success", "data": { "main": [...] }, ... } },
  "dirty_node_ids": ["<uuid>"]
}
```

Semantics when `target_node_id` is set:

- Treat as **partial manual execution**: merge `run_data` into the new execution document’s initial `run_data` (after validation), then run engine in **step mode** until `target_node_id` completes; do not schedule **downstream** of the target.
- When `target_node_id` is **omitted**, behavior unchanged (full run from trigger).

**Pros:** one URL, worker already consumes `flow_run` with execution id.  
**Cons:** slightly more branching in route + handler.

### Option B: dedicated `POST .../run-step`

Same body shape but explicit URL for clarity and stricter validation. Option B has an additional naming advantage: the request body field `run_data` (client-supplied seed) would otherwise share a name with the execution document field `run_data` (engine-written outputs), creating confusion in code review and logs. A separate endpoint makes the distinction obvious at the call site. Still recommended to go with Option A for v1 simplicity, but this tradeoff is noted.

Either way, the worker message can stay `{ flow_id, flow_revid, execution_id, organization_id, trigger }` and load options from **`flow_executions`** (new fields on the execution document set at insert time).

**Execution document additions** (Mongo `flow_executions`):

- `target_node_id: str | null` — if set, partial + stop after this node.  
- `initial_run_data: dict | null` — stored separately from `run_data` (engine-written outputs) so the seed the client supplied is always inspectable independently of what the engine wrote. The engine merges `initial_run_data` into its working `context.run_data` at startup, but the two fields remain distinct in the document.  
- `dirty_node_ids: list[str] | null` — optional for phase 2.

---

## Engine plan (`analytiq_data/flows/engine.py`)

### New entrypoint (name sketch)

`async def run_flow_partial(...)` **or** `run_flow(..., *, target_node_id=None, seed_run_data=None)`:

1. **Validate** revision (reuse `validate_revision`).
2. **Resolve target**: `target_node_id` in `nodes_by_id`, reachable from trigger (reuse reachability logic from trigger).
3. **Merge seed**: copy validated `seed_run_data` into `context.run_data` (deep merge per node or replace per node — match current BSON shape from `_execute_loop` / `persist_run_data`).
4. **Compute “upstream closure”** of `target_node_id` (all nodes on at least one path from trigger to target). Ignore nodes outside closure for scheduling (downstream of target never enqueued). For a diamond DAG (A→B→D, A→C→D, target=D) the closure is {A, B, C, D}; both B and C must be satisfied before D is enqueued. If B has seed data but C does not, C becomes a start node and the engine runs A→C before proceeding to D; B is reused from seed.
5. **Determine start frontier** (n8n-equivalent, id-based):
   - For each **incoming edge bundle** into nodes on the way to target, walk upstream until hitting trigger or a node with **reusable** output:
     - Reuse if: `context.run_data` has successful `data.main` for that node **and** node id ∉ `dirty_node_ids`, **or** node has `pin_data`.
   - First node on each branch that is **not** reusable becomes a **start** node; build its `_WorkItem` **inputs** from merged `run_data` / pins the same way the engine would after a real run (extract outputs from parent node ids for the correct output slot / index).
   - **Merge nodes with partial seed inputs**: if a merge node in the closure has _some_ parents with reusable output and _some_ without, it is **not** itself a start node — it waits as normal. The missing-input branches each get their own start node (the first non-reusable node walking upstream on that branch). The merge node is enqueued only after all its required inputs within the closure have completed or been supplied from `run_data`. If a branch feeding a merge node is entirely outside the upstream closure (no path from trigger to target through it), that branch's input is expected to be present in the seed; if it is absent, return a validation error rather than silently hanging.
6. **Run `_execute_loop` variant** that:
   - Only enqueues destinations inside the upstream closure (or stop scheduling past target).
   - **After** `target_node_id` is written to `run_data`, **drain or skip** further work (clear `work` / `merge_waiting` or use a flag).

**Edge cases to document in implementation:**

- **Merge nodes**: only enqueue when all required inputs in closure are satisfied (same as today, but closure-limited).
- **Branches not taken** toward target: should not run; topology must be restricted to nodes **on some path** trigger → target.
- **Trigger**: if trigger has no seed and needs `document_id`, same as full manual run.
- **Errors**: if a precursor fails, target may not run; persist like full run and set execution `error` / status appropriately.

### Tests

Tests live in `packages/python/tests_flow/` (the existing flow test directory, not `tests/`). Each case uses a small hardcoded DAG fixture with a mock node executor so tests run without external services.

Required test fixtures and assertions:

| Case | Fixture topology | What to assert |
|------|-----------------|----------------|
| (a) Reuse seed | A→B→C, target=C, seed has B | B not re-executed; C output uses B's seed as input |
| (b) Run missing upstream | A→B→C, target=C, seed empty | A and B execute before C; all three appear in `run_data` |
| (c) Stop after target | A→B→C→D, target=B | Only A and B execute; C and D absent from `run_data` |
| (d) Diamond + partial seed | A→B→D, A→C→D, target=D, seed has B | A and C execute; B reused from seed; D executes last |
| (e) Merge node missing branch seed | A→B→D, A→C→D, target=D, seed has B but closure check fails for C's branch | C's branch runs; merge node D fires after both inputs present |
| (f) Error in precursor | A→B→C, target=C, B raises error | Execution stops; `run_data` has B with error status; C absent; execution status = error |

---

## Frontend plan

1. **SDK**: extend `RunFlowParams` + `runFlow()` body with optional `target_node_id`, `run_data`, `dirty_node_ids`.
2. **Editor state**: keep using **`executionForIo`** (or a dedicated “test execution” id) as the source of **seed** `run_data` for the next step run (same object n8n’s store holds).
3. **FlowNodeConfigModal** (or parameters header): **Execute step** button — calls `runFlow` with `target_node_id` + current `run_data` snapshot, then **poll** `getExecution` / refresh logs like full run.
4. **Input panel — “Execute previous nodes”** (P2, n8n parity): deferred to P2. When implemented, the semantics are: run the full upstream closure of the open node — i.e., `target_node_id` is set to the open node itself and the engine stops after it, but the intent is to populate the node's _inputs_ for inspection rather than its output. For a node with a single parent this is identical to “Execute step” on that parent. For a node with **multiple parents** all parents (and their transitive ancestors) are included in the closure; each runs in dependency order, reusing seed data where available. The frontend should not guess a “first non-trigger upstream” in the multi-parent case — it must let the engine compute the full frontier from `target_node_id`.

---

## Phased rollout

| Phase | Scope |
|-------|--------|
| **P0** | API + execution fields + engine: **no seed** — run **only** subgraph trigger → `target_node_id` (always correct, slower). Validates plumbing. The API **accepts** `run_data` and `dirty_node_ids` in the request body and persists them in `flow_executions` as `initial_run_data` / `dirty_node_ids`, but the engine **ignores** them and always starts from the trigger. This keeps the wire format stable across phases. |
| **P1** | Seed `run_data` + reuse + stop after target (**full n8n-style** precursor logic). |
| **P2** | `dirty_node_ids` or parameter-version integration + “Execute previous nodes” UX polish. |
| **P3** | Consider execution `mode: "manual_step"` vs `"manual"` for analytics / UI filters. |

---

## Files likely touched

- `packages/python/app/routes/flows.py` — request model, `run_flow` insert fields.  
- `packages/python/analytiq_data/msg_handlers/flow_run.py` — pass new options into engine.  
- `packages/python/analytiq_data/flows/engine.py` — partial + stop logic; possibly small helpers for “inputs from `run_data`”.  
- `packages/python/tests_flow/` — new cases.  
- `packages/typescript/sdk/src/types/flows.ts`, `docrouter-org.ts` — client.  
- `packages/typescript/frontend/src/components/flows/FlowNodeConfigModal.tsx` (and/or toolbar) — **Execute step** UI.

---

## Open questions

1. **Unsaved graph**: n8n saves before run; DocRouter should either **require saved revision** (`flow_revid` must match last save) or accept **inline graph** in the body (larger change). Recommend **require save** for v1.  
2. **Concurrent runs**: disable Execute step while an execution is running, or allow parallel test executions with separate execution ids (simpler: **disable** like n8n’s `workflowRunning`).  
3. **Webhook / schedule triggers**: Execute step only for **manual** document flows initially; other trigger types may need explicit mock trigger data.

---

## Summary

| Layer | Ready today? | Action |
|-------|----------------|--------|
| FastAPI `POST /run` | Partial | Extend request + persist execution options. |
| Worker | Yes | Read options from execution doc; call new engine mode. |
| Engine | No | Implement partial subgraph + optional seed + stop-at-target. |
| SDK / UI | No | Extend types + add Execute step + polling. |

n8n’s **`destinationNode` + `runData` + `startNodes` + partial runner** map cleanly to DocRouter’s **`target_node_id` + seeded `run_data` (by node id) + frontier construction + bounded `_execute_loop`**, reusing existing **`run_data`** persistence and validation.
