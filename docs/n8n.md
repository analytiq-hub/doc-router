# n8n architecture reference

Complete architecture blueprint for rebuilding n8n in Python, organized section by
section. Each section names the concept, shows the TypeScript implementation, and
ends with a **doc-router note** describing what to adopt, adapt, or skip.

Paths are relative to the n8n repo root. File names are case-sensitive
(e.g. `Interfaces.ts`, `Workflow.ts`, `WorkflowExecute.ts`).

---

## Table of contents

1. [Workflow document model](#1-workflow-document-model)
2. [Node type registry](#2-node-type-registry)
3. [Execution engine](#3-execution-engine)
4. [Execution data flow](#4-execution-data-flow)
5. [Trigger system](#5-trigger-system)
6. [Activation system](#6-activation-system)
7. [Webhook registration and routing](#7-webhook-registration-and-routing)
8. [Credential storage and resolution](#8-credential-storage-and-resolution)
9. [Multi-process and queue architecture](#9-multi-process-and-queue-architecture)
10. [Execution lifecycle hooks](#10-execution-lifecycle-hooks)
11. [Push / real-time transport](#11-push--real-time-transport)
12. [Execution resumption — Wait nodes](#12-execution-resumption--wait-nodes)
13. [Error workflow triggering](#13-error-workflow-triggering)
14. [Sub-workflow execution](#14-sub-workflow-execution)
15. [Static data persistence](#15-static-data-persistence)
16. [Permission and ownership model](#16-permission-and-ownership-model)
17. [Concurrency and rate controls](#17-concurrency-and-rate-controls)
18. [HTTP surfaces](#18-http-surfaces)
19. [Expression evaluation](#19-expression-evaluation)
20. [Code node — JavaScript](#20-code-node--javascript)
21. [Code node — Python](#21-code-node--python)
22. [Reference index](#22-reference-index)

---

## 1. Workflow document model

### What it is

A **workflow** is the persisted artifact: a graph of node instances plus
metadata. At rest it is a database row (`WorkflowEntity`, stored via TypeORM).
In memory n8n constructs a `Workflow` object that builds two adjacency maps from
the stored `connections` object.

### Key types

| Type | File | Role |
|------|------|------|
| `INode` | `packages/workflow/src/Interfaces.ts` | One node instance in the graph. |
| `IConnections` | same file | The full edge map: `{ [sourceNodeName]: INodeConnections }`. |
| `INodeConnections` | same file | Per-node edges: `{ [connectionType]: NodeInputConnections }`. |
| `NodeInputConnections` | same file | `Array<IConnection[] \| null>` — one slot per output index; inner array = fan-out targets. |
| `IConnection` | same file | One edge target: `{ node: string, type: NodeConnectionType, index: number }`. |
| `NodeConnectionTypes` | same file | Const enum: `Main = 'main'`, plus AI variants (`AiTool`, `AiLanguageModel`, …). |
| `Workflow` (class) | `packages/workflow/src/Workflow.ts` | Runtime object: builds `connectionsBySourceNode` and `connectionsByDestinationNode` on construction; holds `nodes: INodes` (keyed by name). |
| `WorkflowParameters` | same file | Constructor bag: `id`, `name`, `nodes[]`, `connections`, `active`, `nodeTypes`, `staticData`, `settings`, `pinData`. |

### Why n8n separates `IConnection`, `NodeInputConnections`, and `IConnections`

n8n models edges at **three levels** because each has a distinct shape:

- **`IConnection` (atomic edge endpoint)**: one destination — `{ node, type, index }`.
  This is the leaf object in stored workflow JSON.

- **`NodeInputConnections` (port-indexed adjacency list for one node/type)**:
  `Array<IConnection[] | null>`.
  - In the persisted, **source-indexed** `connections` document, the outer index
    is an **output index** and the inner array is **fan-out** targets.
  - In the derived, **destination-indexed** map (`connectionsByDestinationNode`),
    the outer index is an **input index** and the inner array is **fan-in** sources.
  - `null` gaps preserve sparse indices (unconnected ports on a switch node, etc.)

- **`INodeConnections` / `IConnections` (workflow adjacency map)**:
  dictionary layers that make the whole graph serializable:
  `{ [sourceNodeName]: { [connectionType]: NodeInputConnections } }`.
  n8n persists this map by source node, then inverts it at runtime for fast parent lookups.

### INode fields

| Field | Type | Notes |
|-------|------|-------|
| `id` | string | Stable UUID. |
| `name` | string | **Unique within workflow.** Used as key in `connections` and `runData`. |
| `type` | string | Registry key, e.g. `n8n-nodes-base.httpRequest`. |
| `typeVersion` | number | Selects parameter schema / behavior version. |
| `position` | `[number, number]` | Canvas `[x, y]`. Editor-only; ignored by engine. |
| `parameters` | object | Type-specific config, opaque to engine. |
| `credentials` | object? | `{ [slotName]: { id: string\|null, name: string } }`. |
| `disabled` | boolean? | Skip during execution. |
| `continueOnFail` | boolean? | Continue even when this node errors. |
| `onError` | enum? | `'stopWorkflow' \| 'continueRegularOutput' \| 'continueErrorOutput'`. |
| `retryOnFail` / `maxTries` / `waitBetweenTries` | … | Retry policy. |
| `alwaysOutputData` | boolean? | Emit placeholder when output would be empty. |
| `executeOnce` | boolean? | Run once per execution regardless of item count. |
| `notes` / `notesInFlow` | string / boolean? | Editor annotations; ignored by engine. |
| `webhookId` | string? | Webhook/trigger registration key. |

### connections storage format

`connections` is indexed by **source node name** (not id). The `node` field
inside each `IConnection` target also refers to the **destination node name**.

```
connections: {
  [sourceNodeName: string]: {
    [connectionType: string]:       // usually "main"
      Array<                        // one slot per output index
        IConnection[] | null        // inner array = fan-out targets
      >
  }
}
```

Example — one source, two output branches:

```json
{
  "Split": {
    "main": [
      [{ "node": "Branch A", "type": "main", "index": 0 }],
      [{ "node": "Branch B", "type": "main", "index": 0 }]
    ]
  }
}
```

Example — fan-out from one output to two nodes:

```json
{
  "HTTP Request": {
    "main": [
      [
        { "node": "Code",   "type": "main", "index": 0 },
        { "node": "Logger", "type": "main", "index": 0 }
      ]
    ]
  }
}
```

### Connection patterns (fan-in, fan-out, multi-port, sparse)

- **Chain (A → B → C)**: single entry in `A.main[0]` pointing at `B`, etc.
- **Fan-out (B → C1, C2, C3)**: one output index has multiple `IConnection` targets.
- **Fan-in (A1, A2, A3 → B)**: multiple sources each contain a target pointing to `B`; in the destination-indexed map these appear together under `B.main[inputIndex]`.
- **Multiple input indices**: `IConnection.index` encodes which destination input to use.
- **Sparse ports**: `null` gaps preserve output/input indices for unconnected ports.

### Connection types (`main` vs `ai_*`)

The `type` string in `IConnection` is a **connection lane**. It keeps different
categories of wiring separate within the same `connections` JSON shape.

**`main`** (`NodeConnectionType.Main`) is the default lane for workflow execution.

The `ai_*` lanes are used by LangChain/AI nodes to wire capabilities and artifacts
(models, tools, documents, embeddings, vector stores) without treating them as
ordinary item streams:

- `ai_tool` — connects tool nodes to an agent/chain.
- `ai_document` — connects document loaders/splitters to downstream consumers.
- `ai_embedding` — connects an embedding provider.
- `ai_vectorStore` — connects a vector store resource.

### Graph traversal utilities

```typescript
import { getParentNodes, getChildNodes, mapConnectionsByDestination } from 'n8n-workflow';

const byDest = mapConnectionsByDestination(workflow.connections);
const parents = getParentNodes(byDest, 'NodeName', 'main', 1);
const children = getChildNodes(workflow.connections, 'NodeName', 'main', 1);
```

`Workflow` pre-builds both maps as `connectionsBySourceNode` and
`connectionsByDestinationNode` at construction time.

Source: `packages/workflow/src/common/`

**doc-router note.** The node/connection JSON shape is a good model to follow.
Key difference to consider: n8n keys edges by node **name** (fragile to renames);
doc-router can key by node **id** for rename-safety. Whichever you choose, nodes
and edges must agree on the same key.

### Portable workflow JSON format

n8n uses one `IWorkflowBase` shape for database storage, API responses, file
import, and source-control export.

**`IWorkflowBase`** (`packages/workflow/src/Interfaces.ts`) — the canonical document:

```json
{
  "id": "abc123",
  "name": "Invoice processing",
  "active": false,
  "isArchived": false,
  "versionId": "<uuid>",
  "activeVersionId": "<uuid>",
  "nodes": [],
  "connections": {},
  "settings": {
    "timezone": "UTC",
    "executionOrder": "v1",
    "executionTimeout": 3600,
    "saveDataErrorExecution": "all",
    "saveDataSuccessExecution": "none",
    "saveManualExecutions": true,
    "errorWorkflow": "<workflow-id>"
  },
  "staticData": {},
  "pinData": {},
  "meta": { "templateId": "...", "instanceId": "..." },
  "createdAt": "2024-01-01T00:00:00.000Z",
  "updatedAt": "2024-01-02T00:00:00.000Z"
}
```

**`staticData`** — persistent key/value state written by trigger/webhook nodes
across executions (e.g. a cursor position for polling). Updated in-place on
`WorkflowEntity` after each execution; not versioned.

**`pinData`** (`IPinData: { [nodeName]: INodeExecutionData[] }`) — per-node output
overrides keyed by node **name**. When set the engine substitutes pinned data for
the real execution output. Stored on the workflow row.

**`IWorkflowSettings`** notable fields:

| Field | Meaning |
|-------|---------|
| `executionOrder` | `'v0'` (legacy) or `'v1'` (current). Controls node scheduling order. |
| `errorWorkflow` | ID of another workflow to trigger when this one fails. |
| `saveDataErrorExecution` / `saveDataSuccessExecution` | `'all'` \| `'none'`. |
| `callerPolicy` | Which workflows may call this one as a sub-workflow. |
| `availableInMCP` | Expose as an MCP tool. |

**Version history** is stored separately in `WorkflowHistory`.
A history row contains `versionId`, `workflowId`, `nodes`, `connections`,
`authors`, `name`, `description`, `autosaved`, and timestamps.

**doc-router note.** Reserve `staticData`, `pinData`, and `meta` in the
`flow_revisions` schema from the start (stored as `null` in v1) so the storage
format and export contract do not need breaking changes later.

---

## 2. Node type registry

### What it is

Separates **"what types can appear on the canvas"** from **"what a specific
workflow stores"**. Each node type is a class implementing `INodeType`,
registered in `INodeTypes`. At runtime n8n resolves a node's type + version to
get its `description` (parameter schema, inputs/outputs, credentials) and its
`execute` / trigger hooks.

### Key interfaces

| Interface | File | Role |
|-----------|------|------|
| `INodeType` | `packages/workflow/src/Interfaces.ts` | Base: `description: INodeTypeDescription`, plus optional `execute`, `trigger`, `webhook`, `poll`, `supplyData` hooks. |
| `INodeTypeDescription` | same file | Metadata: `name`, `displayName`, `version`, `inputs`, `outputs`, `properties`, `credentials`, `defaults`. |
| `INodeTypes` | same file | Registry: `getByName(name)`, `getByNameAndVersion(name, version)`. |

### Node implementation pattern

Built-in nodes live in `packages/nodes-base/nodes/`. Each folder typically
contains `<Name>.node.ts`, helpers, and tests. The `execute` method receives
`IExecuteFunctions` and returns `INodeExecutionData[][]` — one inner array per
output, each element is one item.

**doc-router note.** Implement a step type registry as a Python dict
`{ key: StepType }`. Each `StepType` holds a JSON Schema for `parameters`,
input/output counts, and an async `execute(context, node, items)` callable.

---

## 3. Execution engine

### Overview

`WorkflowExecute` (`packages/core/src/WorkflowExecute.ts`) runs a `Workflow`
instance. It is constructed with `additionalData` (credentials resolver, hooks,
push transport) and a `mode` (`'manual' | 'trigger' | 'webhook' | …`).

Entry points:
- `run(options)` — full execution from a start node.
- `runPartialWorkflow2(…)` — re-run only dirty nodes (canvas "run from here").
- `runPartialWorkflow(…)` — used for execution resumption (Wait nodes).

All return a `PCancelable<IRun>` — cancellable by calling `.cancel()`.

### Main loop (`processRunExecutionData`)

`processRunExecutionData` is the core loop inside `WorkflowExecute.ts`.

1. `workflow.expression.acquireIsolate()` — pins a VM isolate for expression
   evaluation (no-op in legacy mode).
2. `hooks.runHook('workflowExecuteBefore', …)` — persistence, telemetry.
3. **Loop** while `runExecutionData.executionData.nodeExecutionStack` is non-empty:
   - Dequeue `IExecuteData` (the next node + its input items + source info).
   - Call the node's `execute` (or poll/webhook/trigger) hook via `NodeExecuteFunctions`.
   - On success: store `ITaskData` in `runData[node.name]`; push successor nodes
     onto `nodeExecutionStack`.
   - On failure: store error in `ITaskData`; honour `continueOnFail` / `onError`.
4. `workflow.expression.releaseIsolate()` in `finally`.
5. `hooks.runHook('workflowExecuteAfter', …)` — persist `IRun`.

### Run state types

| Type | File | Role |
|------|------|------|
| `IRun` | `packages/workflow/src/Interfaces.ts` | Top-level result: `data: IRunExecutionData`, `status`, `startedAt`, `stoppedAt`, `mode`. |
| `IRunExecutionData` | `packages/workflow/src/run-execution-data/` | Contains `startData`, `resultData` (including `runData`), and `executionData` (stack + waiting maps). |
| `IRunData` | `packages/workflow/src/Interfaces.ts` | `{ [nodeName]: ITaskData[] }` — per-node output (array because a node can run multiple times). |
| `ITaskData` | same file | One node execution result: `startTime`, `executionTime`, `executionStatus`, `data: ITaskDataConnections`, `error?`. |
| `ITaskDataConnections` | same file | `{ [connectionType]: Array<INodeExecutionData[] \| null> }` — the node's output items. |
| `IWaitingForExecution` | same file | `{ [nodeName]: { [runIndex]: ITaskDataConnections } }` — inputs for merge-waiting nodes. |
| `nodeExecutionStack` | inside `executionData` | Array of `IExecuteData` — nodes ready to run. Consumed as a queue (FIFO via `shift()`). |

### Canonical execution data path

```
runExecutionData.resultData.runData[nodeName][runIndex].data?.[connectionType]?.[portIndex]
```

(execution → node → run → lane → port)

### How the stack and waiting maps work

- **`nodeExecutionStack: IExecuteData[]`**: despite the name, consumed as a queue
  (FIFO, `shift()`). Items may be re-prioritized by pushing/unshifting. Each entry
  already contains the node plus its fully prepared input bag (`data`) and provenance
  (`source`).

- **`waitingExecution: IWaitingForExecution`**: holding map for not-yet-runnable nodes,
  keyed by destination node name and run index. Stores *partially assembled* input bags
  for merge-style nodes when some input ports have not received data yet.

- **`waitingExecutionSource`**: mirrors `waitingExecution` but stores `ISourceData` per
  input port for lineage reconstruction.

Typical flow:

1. A node finishes and produces outputs.
2. The engine routes items along `connections` to destination nodes.
3. If destination has all required inputs filled → enqueue `IExecuteData`.
4. If not → park partial input bag in `waitingExecution` until remaining inputs arrive.

### Item data format

`INodeExecutionData` is the **only thing that crosses a node boundary**:

```typescript
interface INodeExecutionData {
  json:        IDataObject;
  binary?:     IBinaryKeyData;
  error?:      NodeApiError | NodeOperationError;
  pairedItem?: IPairedItemData | IPairedItemData[] | number;
}
```

`json` is the primary payload. `binary` carries file attachments. `pairedItem`
records lineage back to input items for UI arrows and `$('NodeName').item`.

**doc-router note.** The stack / waiting-map / permanent-output-record pattern
is directly reusable in Python: `deque` of `(node_id, input_items_by_slot)` work
units, `dict[node_id, list[items | None]]` waiting map, `dict[node_id, output]`
permanent output store written once and never mutated.

---

## 4. Execution data flow

### The unit of work: `IExecuteData`

```typescript
interface IExecuteData {
  node:    INode;
  data:    ITaskDataConnections;               // input items ready to consume
  source:  ITaskDataConnectionsSource | null;  // provenance
  runIndex?: number;
}
```

`ITaskDataConnections` is the input bag:

```typescript
{ "main": [ [item0, item1, …],    // input slot 0
             [item0, item1, …] ] } // input slot 1 (merge node)
```

### How a node reads its input

The `execute(this: IExecuteFunctions)` context exposes:

- `getInputData(inputIndex?, connectionType?)` — returns `INodeExecutionData[]`
  for one input slot. Most nodes call this with no arguments (slot 0).
- `getInputSourceData(inputIndex?)` — returns provenance.

Both read from `executionData.data` on the stack entry. The node never reads
`runData` directly.

### How a node writes its output

`execute()` returns `INodeExecutionData[][]` — one inner array per output index:

```typescript
[
  [out0_item0, out0_item1],  // output 0
  [out1_item0],              // output 1
]
```

After the node returns, the engine stores the result permanently:

```typescript
taskData.data = { main: nodeSuccessData };
runData[nodeName].push(taskData);
```

`runData` is the **permanent record**. Expressions read from it via
`WorkflowDataProxy`; the node itself never writes to it directly.

### Branching

A node with two outputs returns two inner arrays. The engine walks
`connectionsBySourceNode[nodeName].main`:

```
for outputIndex in connectionsBySourceNode[nodeName].main:
  for each connectionData at that outputIndex:
    if nodeSuccessData[outputIndex] is non-empty:
      addNodeToBeExecuted(connectionData, outputIndex, nodeSuccessData, …)
```

Non-empty output → successor enqueued. Empty output → branch skipped.

### Fan-out (one output → multiple nodes)

`connectionsBySourceNode[nodeName].main[0]` can hold multiple `IConnection`
entries. `addNodeToBeExecuted` is called once per connection; each downstream
node receives the same item array and runs independently.

### Merging (multiple inputs → one node)

`addNodeToBeExecuted` checks `connectionsByDestinationNode[node].main.length`.
If > 1, the engine accumulates partial inputs in `waitingExecution`:

```
waitingExecution[nodeName][runIndex].main[inputSlot] = items | null
```

Slots start as `null`. Once all slots are filled, the complete
`ITaskDataConnections` is moved to `nodeExecutionStack`.

**Partial-data exception:** if `nodeExecutionStack` empties but
`waitingExecution` is non-empty, the engine checks each waiting node's
`requiredInputs`. If the node type does not require all inputs it is enqueued
with whatever data is available.

### Accessing previous nodes via expressions

`WorkflowDataProxy` provides `$node['Name']` and `$json` by reading
`runData[nodeName][runIndex].data.main[outputIndex][itemIndex].json`.
This is a **read-only** view over completed nodes, separate from live
`executionData.data`. Getters are lazy.

### Summary diagram

```
nodeExecutionStack (IExecuteData[])
  └─ dequeue → node.execute(data.main[0])
                  │
                  └─ returns INodeExecutionData[][]
                        │
              ┌─────────┴──────────┐
       store in runData        for each output[i]:
       (permanent record)        for each connection at output[i]:
                                   single-input target → enqueue directly
                                   multi-input target  → fill waitingExecution slot
                                                          └─ all slots full? → enqueue
```

---

## 5. Trigger system

### What it is

The trigger system is how n8n **starts** workflow executions without a manual
button-press. A trigger is a node whose `INodeType` implements a `trigger` (event-
push) or `poll` (periodic pull) hook instead of `execute`.

### Key types

| Type | File | Role |
|------|------|------|
| `ITriggerFunctions` | `packages/workflow/src/Interfaces.ts` | Execution context for trigger hooks; exposes `emit(data)` and `emitError(error)`. |
| `ITriggerResponse` | same file | Object returned by trigger hook; includes `closeFunction` for cleanup and (in manual mode) `manualTriggerResponse` promise. |
| `IPollFunctions` | same file | Execution context for poll hooks; exposes `helpers`, no `emit` — return items normally. |

### ActiveWorkflows

`packages/core/src/ActiveWorkflows.ts` — manages which workflows are currently
listening for events.

```typescript
activeWorkflows.add(
  workflowId,
  workflow,
  additionalData,
  mode,          // 'activate' | 'trigger' | 'webhook'
  activation,
  getTriggerFunctions,
  getPollFunctions
)
```

For each trigger node in the workflow, `ActiveWorkflows.add()` calls
`TriggersAndPollers.runTrigger()` (or `runPoll()`).
Results are stored in `IWorkflowData.triggerResponses[]` so the `closeFunction`
can be called on deactivation.

### TriggersAndPollers

`packages/core/src/TriggersAndPollers.ts`:

- `runTrigger(workflow, node, getTriggerFunctions, additionalData, mode, activation)`
  - In `'manual'` mode: wraps the trigger response in a promise that resolves when
    the first `emit()` fires (useful for "test" runs from the UI).
  - In `'trigger'` / `'webhook'` modes: starts the trigger and returns immediately.
- `runPoll(…)` — similar; schedules the poll on a timer; on each tick, calls
  `workflow.execute()` with items returned by the poll hook.

### Trigger lifecycle

1. REST endpoint `POST /workflows/{id}/activate` is called.
2. `WorkflowEntity` is loaded from DB.
3. `ActiveWorkflows.add()` is called; each trigger node type's `trigger()` hook runs.
4. The trigger node registers an external listener (webhook, cron, pub/sub, etc.)
   and returns an `ITriggerResponse`.
5. When the external event fires, the trigger calls `emit(data)`.
6. `emit` enqueues an `IExecuteData` on `nodeExecutionStack` and calls
   `additionalData.hooks.workflowExecuteBefore` — starting a new execution.
7. On deactivation, `closeFunction` is called for each stored trigger response.

### Poll cycle

Poll nodes (e.g., RSS feed, email polling) use a simpler pattern:

1. `runPoll()` schedules a timer (interval from node parameters).
2. On each tick, the poll hook's return value is fed to `WorkflowExecute.run()`.
3. `staticData` is used to store the last-seen cursor/ID to avoid re-processing.

**doc-router note.** Implement two parallel activation paths: *push triggers*
(register listener, call back into engine on event) and *poll triggers* (cron
job, run engine with returned items). Both paths hand items to the same
execution engine.

---

## 6. Activation system

### Workflow states

```
inactive ─── activate ──▶ active ─── deactivate ──▶ inactive
                                └── archive ──▶ archived
```

### Activation flow

1. `POST /api/v1/workflows/{id}/activate` (public) or
   `POST /rest/workflows/{id}/activate` (internal).
2. `WorkflowRepository.findOne(id)` loads the entity.
3. `WorkflowEntity.active` is set to `true` and saved to DB.
4. `ActiveWorkflows.add(…)` registers all trigger/poll nodes in memory.
5. Webhooks are registered in `WebhookEntity` (see §7).

In **queue mode** the main process still calls `ActiveWorkflows.add()` —
workers do not hold activation state; they only run executions dispatched via
the queue.

### Execution modes (`WorkflowExecuteMode`)

| Mode | When |
|------|------|
| `'manual'` | User presses "Execute" in the canvas UI. |
| `'trigger'` | Execution started by a trigger node firing. |
| `'webhook'` | Execution started by an incoming webhook request. |
| `'error'` | Running an error workflow (see §13). |
| `'scheduled'` | Poll/cron execution. |
| `'integrated'` | Sub-workflow execution (see §14). |
| `'cli'` | Execution started from the n8n CLI. |

### Activation modes (`WorkflowActivateMode`)

| Mode | When |
|------|------|
| `'activate'` | User manually activates via UI/API. |
| `'update'` | Workflow is re-activated after a save (while already active). |
| `'init'` | Server startup — re-activating all previously active workflows. |
| `'leadershipChange'` | Multi-main: new leader node takes over activation. |

**doc-router note.** Persist `active` on the workflow record. Keep an in-memory
registry of active workflows (or rely on the DB + WaitTracker polling). On
process restart, re-activate all workflows that were active at shutdown by
querying the DB.

---

## 7. Webhook registration and routing

### What a webhook is in n8n

A **webhook** is a persisted URL path ↔ workflow binding. When an HTTP request
arrives on that path, the engine starts the bound workflow.

### WebhookEntity

`packages/cli/src/databases/entities/WebhookEntity.ts`:

| Field | Type | Notes |
|-------|------|-------|
| `workflowId` | string | Bound workflow. |
| `webhookPath` | string | URL path, e.g. `/webhook/abc123/invoice`. May contain `:param` segments. |
| `method` | string | `GET`, `POST`, etc. |
| `webhookId` | string | Stable UUID assigned to the trigger node. |
| `node` | string | Node name in the workflow. |
| `pathLength` | number | Pre-computed for sort order during matching. |

### Registration

When a workflow is activated:
1. For each node implementing `INodeType.webhook`, the engine calls the node's
   `webhookMethods.createWebhook()` hook.
2. The hook calls `additionalData.createWebhookIfNotExists()` which inserts a
   `WebhookEntity` row and populates the in-memory cache.

On deactivation, `deleteWebhook()` is called and the row is deleted.

### WebhookService

`packages/cli/src/webhooks/WebhookService.ts`:

- `findCached(method, path)` — checks Redis/memory cache first.
- `findStaticWebhook(method, path)` — exact path match in DB.
- `findDynamicWebhook(method, path)` — matches `:param` style segments; returns
  extracted path params.
- `populateCache()` — called at startup; loads all active webhooks into cache.

### Request routing

`packages/cli/src/webhooks/WebhookRequestHandler.ts`:

1. Parse incoming request (body, query, headers, path params).
2. `WebhookService.find(method, path)` → `WebhookEntity`.
3. Load `WorkflowEntity` by `webhookId`.
4. Build input items from the request.
5. Call `WorkflowExecutionService.runWorkflow(workflow, 'webhook', …)`.
6. Wait for `sendResponse` hook if the node is configured for synchronous response.

### Wait / form webhooks

Temporary webhooks registered by Wait nodes and Form nodes during an execution:

- **`WaitingWebhooks`** (`packages/cli/src/webhooks/WaitingWebhooks.ts`) — manages
  webhooks that resume a paused execution.
- **`WaitingForms`** (`packages/cli/src/webhooks/WaitingForms.ts`) — manages
  form submission webhooks.

Both are cleaned up immediately after the execution resumes.

**doc-router note.** A webhook registry with static+dynamic path matching is a
natural fit for Python (e.g. a trie or a sorted list by path length for
disambiguation). Cache all active webhooks in memory at startup; invalidate on
registration/deregistration.

---

## 8. Credential storage and resolution

### Storage schema

**`CredentialsEntity`** (`packages/cli/src/databases/entities/CredentialsEntity.ts`):

| Field | Type | Notes |
|-------|------|-------|
| `id` | string | UUID. |
| `name` | string | Display name. |
| `type` | string | Credential type key, e.g. `"httpBasicAuth"`. |
| `data` | string | **Encrypted JSON string.** |
| `homeProjectId` | string | Owning project. |

### Encryption

`packages/core/src/Cipher.ts` — AES-256-GCM using `encryptionKey` from
`GlobalConfig`. The `Credentials` class (`packages/core/src/Credentials.ts`)
wraps the entity:

- `setData(plainObject)` — encrypts and stores in `entity.data`.
- `getData()` — decrypts and returns the plain object.

The encryption key is never exposed in API responses; only decrypted at
execution time.

### How a node references credentials

`INode.credentials` holds **references**, not secrets:
```json
{ "oauth2Api": { "id": "abc123", "name": "My Slack" } }
```
The key (`"oauth2Api"`) is a credential slot name declared in the node type's
`INodeTypeDescription.credentials[]`.

### Resolution at execution time

**`CredentialsHelper`** (`packages/cli/src/CredentialsHelper.ts`):

1. `getDecrypted(additionalData, nodeCredentials, credentialType, mode, executeData)`
2. Load `CredentialsEntity` from DB by `id`.
3. Decrypt via `Cipher.decrypt()`.
4. Apply expression evaluation within credential parameters (e.g., `"={{ $env.TOKEN }}"`).
5. Apply OAuth2 token refresh if needed (calls OAuth2 refresh flow).
6. Short-lived in-process cache to avoid repeated DB hits per item.

Exposed to node code as:

```typescript
const creds = await this.getCredentials('oauth2Api');
// creds is the plain decrypted object
```

### Credential types registry

`CredentialTypes` service loads type definitions from `packages/*/credentials/*.ts`
files. Each credential type defines a parameter schema and an optional
`authenticate()` hook that injects Authorization headers or similar.

### Permission model

Credentials are owned by a project (`homeProjectId`). Sharing is managed via the
`SharedCredentials` relation (see §16). A workflow can only use a credential if
its owning project has a `SharedCredentials` row for that credential with
sufficient role.

**doc-router note.** Encrypt credential data with AES-256-GCM (or Fernet in
Python). Never store or return decrypted credential data outside the execution
path. Cache decrypted credentials for the duration of a single execution only.

---

## 9. Multi-process and queue architecture

### Two execution modes

| Mode | Config | Description |
|------|--------|-------------|
| **Regular** | `executions.mode = 'regular'` | All executions run in the single main Node.js process. |
| **Queue** | `executions.mode = 'queue'` | Executions are enqueued to a Bull/Redis queue; separate worker processes consume and run them. |

### Regular mode

- `WorkflowExecute` runs directly in the main process.
- Concurrency limited by `ConcurrencyControlService` (see §17).
- Suitable for low-volume or single-instance deployments.

### Queue mode components

```
Browser / API client
      │
      ▼
Main process (one or more)
  ├── Receives triggers / webhooks
  ├── Creates ExecutionEntity in DB (status = 'new')
  ├── Enqueues Job { executionId } to Bull queue (Redis)
  └── Listens to job progress messages for real-time UI updates
      │
      ▼ (Redis / Bull)
Worker processes (N)
  ├── Dequeue job from Bull
  ├── Load ExecutionEntity + WorkflowEntity from DB
  ├── Run WorkflowExecute
  ├── Send progress messages to main via job.progress()
  └── Write final IRun to ExecutionEntity
```

### Bull queue

`packages/cli/src/scaling/scaling.service.ts`:

- Queue name: constant from `scaling.types.ts`.
- Backend: Redis (configured via `queue.bull.redis.*`).
- Job data: `JobData = { executionId: string, loadStaticData: boolean }`.
- Bull handles retries, dead-letter, and job prioritization.
- `ScalingService.addJob(jobData, priority)` — main process enqueues.
- `ScalingService.setupWorker(concurrency)` — worker process registers Bull handler.

### Worker process

`packages/cli/src/commands/worker.ts` — CLI entry point.

`JobProcessor` (`packages/cli/src/scaling/job-processor.ts`):
1. Dequeue job.
2. Load execution state from DB.
3. Instantiate `WorkflowExecute` + `additionalData`.
4. Run `workflowExecute.processRunExecutionData()`.
5. Call `job.progress(message)` at key lifecycle points to relay events to main.

### Job messages (Worker → Main IPC)

`JobMessage` is a discriminated union sent via `job.progress()`:

| Message | When |
|---------|------|
| `JobFinishedMessage` | Execution completed successfully. |
| `JobFailedMessage` | Execution failed with an error. |
| `RespondToWebhookMessage` | Webhook-triggered execution has a response ready (relay to waiting HTTP caller). |
| `NodeExecutionCompletedMessage` | Node finished; relay to frontend push service. |

### Multi-main pub/sub

For deployments with multiple main instances, `Push.send()` may not know which
main owns the browser session. Solution:

- **`Publisher`** (`packages/cli/src/scaling/pubsub/publisher.service.ts`) — sends
  a relay command over Redis pub/sub.
- **`Subscriber`** (`packages/cli/src/scaling/pubsub/subscriber.service.ts`) — each
  main listens; the one that owns the session relays the push event to the browser.

**doc-router note.** For v1, regular mode (single process) is sufficient. Design
the engine as a pluggable `Executor` interface so queue-backed execution can be
swapped in later. Celery + Redis is the natural Python equivalent of Bull.

---

## 10. Execution lifecycle hooks

### What hooks are

Functions injected into `IWorkflowExecuteAdditionalData` at execution setup.
Multiple hook functions can be registered for the same event (arrays). Errors in
hooks are caught and logged without failing the execution.

### Hook events

| Hook | Signature | When | Purpose |
|------|-----------|------|---------|
| `workflowExecuteBefore` | `(workflow, data) => Promise<void>` | Before any node runs | Setup: initialize execution record, telemetry. |
| `workflowExecuteAfter` | `(fullRunData: IRun) => Promise<void>` | After all nodes finish (success or error) | Save execution to DB, trigger error workflow if needed, send completion push events, save staticData. |
| `nodeExecuteBefore` | `(nodeName) => Promise<void>` | Before a node runs | Push `nodeExecuteBefore` event to UI. |
| `nodeExecuteAfter` | `(nodeName, data: ITaskData) => Promise<void>` | After a node completes | Push `nodeExecuteAfter` event to UI, save execution progress to DB. |
| `sendResponse` | `(response: IExecuteResponsePromiseData) => Promise<void>` | When webhook/manual execution has a synchronous response ready | Return the HTTP response to the waiting caller. |

### Hook sets (registered in `workflow-execute-additional-data.ts`)

- **`hookFunctionsPush()`** — registers `nodeExecuteBefore`, `nodeExecuteAfter`,
  `workflowExecuteAfter` to push real-time events to the frontend (see §11).
- **`hookFunctionsSave()`** — registers `nodeExecuteAfter` to write node output to DB
  (`saveExecutionProgress`); registers `workflowExecuteAfter` to persist the final
  execution record.
- **`hookFunctionsRequest()`** — registers `sendResponse` to resolve the waiting HTTP
  response promise.

### `WorkflowHooks` class

`packages/workflow/src/WorkflowHooks.ts`:

```typescript
await hooks.executeHookFunctions('workflowExecuteAfter', [fullRunData]);
```

Iterates all registered hook functions for the event and calls them in order.

### `saveExecutionProgress`

`packages/cli/src/execution-lifecycle-hooks/save-execution-progress.ts`:

Registered in the `nodeExecuteAfter` hook. After each node completes, writes
`runData[nodeName]` to the DB so that partially-complete executions can be
inspected or resumed. Respects `saveDataSuccessExecution` / `saveDataErrorExecution`
settings on the workflow.

**doc-router note.** Implement hooks as a list of async callables per event name.
The execution engine calls `await hooks.emit('nodeExecuteAfter', node, task_data)`
after each node. Separate persistence hooks from push hooks — persistence is
always enabled; push is only enabled when a session is watching.

---

## 11. Push / real-time transport

### What it is

The mechanism by which execution progress (node started, node finished, execution
finished) is streamed to the browser in real-time without polling.

### Push service

`packages/cli/src/push/index.ts` — main service, supports two backends:

| Backend | Config | Notes |
|---------|--------|-------|
| `WebSocketPush` | `push.backend = 'websocket'` | Bidirectional; full duplex. |
| `SSEPush` | `push.backend = 'sse'` | HTTP Server-Sent Events; one-way (server→client). |

Each active browser session has a `pushRef` UUID. The frontend establishes a
long-lived connection to `/push?pushRef=<uuid>`.

### Key push event types

From `packages/@n8n/api-types/src/push/`:

| Type | When |
|------|------|
| `executionStarted` | Execution starts; includes execution ID. |
| `nodeExecuteBefore` | Before node runs. |
| `nodeExecuteAfter` | After node completes; includes task data. |
| `executionFinished` | Execution complete; includes final run data. |
| `executionProgress` | Progress update. |

### Push lifecycle

1. Frontend connects to `/push?pushRef=<uuid>` with session auth.
2. Push service stores the connection keyed by `pushRef`.
3. During execution, lifecycle hooks call `push.send(eventType, data, pushRef)`.
4. In multi-main setups, if `pushRef` is unknown to this main, a relay command is
   published via Redis pub/sub to reach the correct main (see §9).
5. The owning main sends the serialized event to the browser over WebSocket or SSE.
6. Frontend updates the canvas in real time.

**doc-router note.** WebSocket is the natural choice. In Python: FastAPI
WebSocket endpoint, keep a `dict[pushRef, WebSocket]` registry. Emit events from
lifecycle hooks. For multi-process setups, relay via Redis pub/sub.

---

## 12. Execution resumption — Wait nodes

### What it is

A node can pause the entire workflow execution at a point and resume it later:
after a time interval, after a webhook is received, or after a form is submitted.

### WaitNode

`packages/nodes-base/nodes/Wait/Wait.node.ts` — implements the pause. In its
`execute()` body it calls:

```typescript
await this.putExecutionToWait(waitTill);
return [[]];  // empty output; engine sees execution as suspended
```

`waitTill` is a `Date`; `Date('indefinite')` means "wait forever for an event".

### Execution pause mechanics

1. `putExecutionToWait(waitTill)` sets `runExecutionData.waitTill` on the engine.
2. After the main loop exits, `workflowExecuteAfter` detects `waitTill` is set.
3. The execution is saved to DB with `status = 'waiting'` and the `waitTill` timestamp.
4. If `waitTill` is set for a webhook/form, a `WaitingWebhook` or `WaitingForm`
   is registered (see §7).

### Resumption by timer (`WaitTracker`)

`packages/cli/src/WaitTracker.ts`:

- Service that polls the DB for executions where `waitTill <= now`.
- Runs on the leader node in multi-main setups.
- On each tick, calls `WorkflowRunner.startExecution(executionId)` for each
  ready execution.

### Resumption by webhook/form

When the webhook or form submission arrives:

1. `WaitingWebhooks` / `WaitingForms` resolves the matching `executionId`.
2. Loads the saved `IRunExecutionData` from DB.
3. Re-enters `WorkflowExecute.runPartialWorkflow(…)` — **not** `run()`.
4. Only the Wait node and its successors run; prior nodes' `runData` is intact.

### State preservation

All node outputs produced before the pause are in `runData` in DB. The
`executionData.nodeExecutionStack` is serialized as part of `IRunExecutionData`.
On resumption the stack is restored and execution continues from where it stopped.

**doc-router note.** Implement a `waitTill` field on the execution record. A
scheduler process polls for expired waits and re-enqueues them. Serializing the
execution stack to DB requires that all items in `nodeExecutionStack` are
JSON-serializable.

---

## 13. Error workflow triggering

### What it is

When a workflow execution fails, n8n can automatically trigger a separate
"error workflow" to handle the failure (alerting, logging, cleanup).

### Configuration

- **External error workflow**: `IWorkflowSettings.errorWorkflow = "<workflow-id>"` —
  a completely separate workflow that will be executed.
- **Internal error handler**: any workflow can have an `ErrorTrigger` node
  (`n8n-nodes-base.errorTrigger`). If present, it acts as a fallback handler
  within the same workflow definition.

`GlobalConfig.nodes.errorTriggerType` sets the string that identifies the error
trigger node type.

### Detection and dispatch

`executeErrorWorkflow()` in
`packages/cli/src/workflow-execute-additional-data.ts`:

1. Called from `workflowExecuteAfter` hook when `fullRunData.data.resultData.error`
   is present.
2. Checks `workflowData.settings.errorWorkflow` for an external workflow ID.
3. If external workflow exists AND current workflow is not already `mode === 'error'`
   (loop protection) AND current workflow is not the same as the error workflow:
   triggers it.
4. Checks for an internal `ErrorTrigger` node; if found, triggers the error flow
   internally.

### Error data passed to error workflow

```typescript
{
  execution: {
    id: executionId,
    url: pastExecutionUrl,
    error: { message, stack },
    lastNodeExecuted: nodeName,
    mode: executionMode,
    retryOf: executionId  // if this was a retry
  },
  workflow: {
    id: workflowId,
    name: workflowName
  }
}
```

For trigger-level errors (no execution ID):
`{ trigger: { error, mode } }` instead of `execution`.

### Execution

`WorkflowExecutionService.executeErrorWorkflow(workflowId, errorData, project)`:
- Mode is set to `'error'`.
- Input to the trigger node is the error data struct above.
- The error workflow executes normally (same engine, same hooks).

**doc-router note.** Implement `errorWorkflow` as a first-class workflow setting.
Guard against infinite loops: if current mode is `'error'` and the error workflow
is the same workflow, skip. Pass a standard error envelope as input items.

---

## 14. Sub-workflow execution

### What it is

One workflow can invoke another as a step ("Execute Workflow" node). The child
workflow runs synchronously or asynchronously and its output is returned to the
parent as items.

### Invocation path

`BaseExecuteContext.executeWorkflow()` in
`packages/core/src/node-execution-context/base-execute-context.ts`:

1. Calls `additionalData.executeWorkflow(workflowInfo, inputData, options)`.
2. Implementation in `workflow-execute-additional-data.ts` calls
   `WorkflowExecutionService.executeSubworkflow()`.
3. Sub-workflow loaded from DB (by `workflowInfo.id`) or inline code
   (`workflowInfo.code`).
4. A new `WorkflowExecute` instance is created with fresh `runExecutionData`.
5. Results (`INodeExecutionData[][]`) are returned to the parent node's `execute()`.

### Options

- `doNotWaitToFinish: true` — parent node returns immediately; child runs in
  background. Parent output is empty.
- `parentExecution: RelatedExecution` — metadata linking child to parent for UI
  lineage and loop detection.

### Caller policy (security)

**`SubworkflowPolicyChecker`**
(`packages/cli/src/subworkflows/subworkflow-policy-checker.service.ts`):

| Policy | Behavior |
|--------|----------|
| `'any'` | Any workflow may call this one. |
| `'workflowsFromSameOwner'` | Only workflows in the same project may call. |
| `'workflowsFromAList'` | Only workflows in an explicit whitelist may call. |

Policy is stored in `Workflow.settings.callerPolicy`. Default from
`GlobalConfig.workflows.callerPolicyDefaultOption`.

**doc-router note.** Implement sub-flow calls via a recursive engine invocation
with a fresh execution context. Thread a `parentExecutionId` through for loop
detection. Implement caller policy as an allow-list check before launching the
child.

---

## 15. Static data persistence

### What it is

`staticData` is a mutable key/value store available to trigger and poll nodes
across executions. Common use: storing the last-seen item ID / timestamp for
incremental polling.

### Lifecycle

1. `Workflow.staticData` is loaded from `WorkflowEntity.staticData` (JSON column)
   at execution setup.
2. During execution, node code mutates it:
   ```typescript
   const staticData = this.getWorkflowStaticData('global');
   staticData.lastId = newId;
   ```
3. Any mutation sets `staticData.__dataChanged = true`.
4. After `workflowExecuteAfter`, if `__dataChanged` is true,
   `WorkflowStaticDataService.saveStaticDataById(workflowId, data)` writes it back.

### Storage

`packages/cli/src/workflows/workflow-static-data.service.ts`:

- `getStaticDataById(workflowId)` — `SELECT staticData FROM workflow WHERE id = ?`
- `saveStaticDataById(workflowId, data)` — `UPDATE workflow SET staticData = ? WHERE id = ?`

Stored as a JSON column on `WorkflowEntity`. Not versioned; not part of workflow
history.

In regular mode, saved synchronously after execution. In queue mode, saved on
the worker process after job completion.

**doc-router note.** Store `static_data` as a JSONB column on the workflow record.
Write it back after each trigger/poll execution. Include a dirty flag to avoid
unnecessary writes.

---

## 16. Permission and ownership model

### Projects

Every resource (workflow, credential, execution) is owned by exactly one
**project**. Projects are the unit of multi-tenancy.

**`Project`** entity (`packages/cli/src/databases/entities/project.ts`):

| Field | Type | Notes |
|-------|------|-------|
| `id` | string | UUID. |
| `name` | string | Display name. |
| `type` | `'personal' \| 'team'` | Personal: one per user, auto-created. Team: shared. |

### Sharing relations

Resources are shared across projects via **join tables with a role column**:

**`SharedWorkflow`**: `(workflowId, projectId, role)` where role is one of:
- `'workflow:owner'` — the owning project.
- `'workflow:editor'` — shared with edit permission.
- `'workflow:reader'` — shared with read-only access.

**`SharedCredentials`**: same pattern for credentials.

### Access control

**`PermissionChecker`** (`packages/cli/src/user-management/permission-checker.ts`):

```typescript
hasWorkflowAccess(userId, workflowId) → boolean
```

Checks if the user's active project has a `SharedWorkflow` row with the required
role. No direct user→resource permission; all mediated through the project.

**`OwnershipService`** (`packages/cli/src/services/ownership.service.ts`):

```typescript
getWorkflowProjectCached(workflowId) → Project
```

Returns the owning project; cached to avoid repeated DB hits.

### Role-based access (global roles)

Users also have a global instance role: `'global:owner'`, `'global:admin'`,
`'global:member'`. Admins can access any resource; members are restricted to
their own projects.

**doc-router note.** The project/sharing/role model maps naturally to an
organization model with member roles. Keep ownership as a FK on each resource;
implement sharing as a join table. All permission checks should go through a
single `has_access(user_id, resource_id, required_role)` function.

---

## 17. Concurrency and rate controls

### Regular mode: `ConcurrencyControlService`

`packages/cli/src/concurrency/concurrency-control.service.ts`:

- Enabled only when `executions.concurrency.productionLimit > 0`.
- `throttle(mode, executionId)` — if at capacity, the execution waits in a
  FIFO `ConcurrencyQueue` (`packages/cli/src/concurrency/concurrency-queue.ts`).
- `release(mode)` — called after execution completes; unblocks the next
  waiting execution.
- Emits telemetry events when the limit is hit: `'execution-throttled'`,
  `'execution-released'`.

### Queue mode: implicit concurrency

In queue mode, concurrency = number of workers × concurrency per worker
(`ScalingService.setupWorker(concurrency)`). Bull distributes jobs across
available workers automatically.

### Execution timeout

- Per-workflow: `IWorkflowSettings.executionTimeout` (seconds).
- Global default: `executions.timeout`.
- Hard cap: `executions.maxTimeout`.
- Enforced in `JobProcessor.processJob()` by comparing elapsed wall-clock time.
  If exceeded, execution fails with a timeout error.

### Task runner concurrency

Code nodes (JS/Python) use a separate concurrency pool managed by `TaskManager`.
This limits the number of concurrent user code tasks independent of workflow
concurrency.

**doc-router note.** Implement a semaphore-based concurrency limiter at the
execution layer. Use `asyncio.Semaphore(max_concurrent)` in Python. Per-workflow
timeout: wrap each `execute()` in `asyncio.wait_for(coro, timeout=N)`.

---

## 18. HTTP surfaces

### Public API (external / API-key)

- **Base path**: `/api/v1`
- **Auth**: `X-N8N-API-KEY` header or Bearer JWT
- **Spec**: `packages/cli/src/public-api/v1/openapi.yml`

| Resource | Path (prefix `/api/v1`) | Methods |
|----------|-------------------------|---------|
| Workflows | `/workflows` | `GET`, `POST` |
| Workflow | `/workflows/{id}` | `GET`, `PUT`, `DELETE` |
| Version | `/workflows/{id}/{versionId}` | `GET` |
| Activate / deactivate | `/workflows/{id}/activate`, `…/deactivate` | `POST` |
| Archive / unarchive | `/workflows/{id}/archive`, `…/unarchive` | `POST` |
| Transfer / tags | `/workflows/{id}/transfer`, `…/tags` | `PUT` |
| Executions | `/executions`, `/executions/{id}` | `GET` |
| Stop / bulk stop | `/executions/{id}/stop`, `/executions/stop` | `POST` |
| Retry | `/executions/{id}/retry` | `POST` |
| Delete execution | `/executions/{id}` | `DELETE` |
| Execution tags | `/executions/{id}/tags` | `GET`, `PUT` |

**Important gap**: the public API has **no** `POST /workflows/{id}/run`.
Manual execution exists only on the internal REST API.

### Internal REST API (browser session)

- **Base path**: `/rest`
- **Auth**: session cookie + CSRF

Notable differences from public API:

| Capability | Internal (`/rest`) | Public (`/api/v1`) |
|------------|--------------------|--------------------|
| Update workflow | `PATCH /{id}` (partial) | `PUT /{id}` (full replace) |
| Manual run | `POST /workflows/{id}/run` ✓ | Not available |
| Stop many | `POST /executions/stopMany` | `POST /executions/stop` (filter body) |
| Bulk delete | `POST /executions/delete` | `DELETE /executions/{id}` (one at a time) |

**doc-router note.** Expose a **single route tree** (`/v0/orgs/{org_id}/…`)
used by both UI and automation clients: one update verb, manual run available
to API-key callers, auth as a dimension (session vs API key routes to the same
handler).

---

## 19. Expression evaluation

### What expressions are

Small snippets embedded in string node parameters, conventionally prefixed with
`=`: `"={{ $json.url }}"`. They are resolved when a parameter value is needed,
turning the template into a concrete value for the current item.

### Resolution pipeline

1. **Detect** — `isExpression(value)`: if true, strip `=` and evaluate; otherwise
   return the literal.
2. **Build context** — `WorkflowDataProxy`
   (`packages/workflow/src/workflow-data-proxy.ts`) wraps current workflow, run
   data, and item index. Exposes `$json`, `$node`, `$input`, `$items`, `$env`,
   `$vars`, `$evaluateExpression` as lazy getters.
3. **Evaluate** — `WorkflowExpression` → `Expression`
   (`packages/workflow/src/expression.ts`) strips `=`, applies syntax extensions
   via `@n8n/tournament`, then calls `renderExpression`.

### Two evaluation modes

Configured once at startup via `Expression.initExpressionEngine()`.

| Mode | Mechanism |
|------|-----------|
| **`legacy`** (default) | `@n8n/tournament` transforms and evaluates in the same Node.js process. AST passes block common escape patterns. |
| **`vm`** | `@n8n/expression-runtime`: isolated V8 heap (`isolated-vm`). Memory limit, timeout, pooled isolates. |

Per-execution isolate lifecycle: `acquireIsolate()` before the main loop,
`releaseIsolate()` in `finally`.

**doc-router note.** In v1, skip inline expressions — use literal parameter
values only. If expressions are added later, treat them as a separate security
class from full script execution. Do not `eval` raw user strings in the API
process.

---

## 20. Code node — JavaScript

### Pipeline

1. `Code.node.ts` reads `parameters.jsCode` and `mode`
   (`runOnceForAllItems` or `runOnceForEachItem`).
2. `JsTaskRunnerSandbox` calls `IExecuteFunctions.startJob('javascript', settings, itemIndex)`.
3. `startJob` → `additionalData.startRunnerTask` → `TaskRequester` serializes the
   task and sends it to a **separate OS process**.
4. `JsTaskRunner` in the subprocess:
   - Creates a `node:vm` context with configurable timeout.
   - **`secure` mode** (default): freezes builtins, blocks `Error.prepareStackTrace`
     escapes, replaces `require` with an allowlist.
   - **`insecure` mode**: `new Function + with(context)` — for trusted environments.
   - Exposes narrow RPC so user code can request input items via IPC rather than
     receiving the full execution blob.
   - Chunks per-item runs to bound IPC payload size.

**doc-router note.** Process boundary first, VM policy inside the worker.
Allowlisted imports, timeouts, no silent access to host env.

---

## 21. Code node — Python

Same pattern as JS:

1. `Code.node.ts` selects Python via language parameter.
2. `PythonTaskRunnerSandbox` calls `startJob('python', …)`.
3. CLI (`packages/cli/src/task-runners/task-runner-process-py.ts`) manages a
   dedicated Python interpreter (project venv).
4. If Python/venv is missing, `getRunnerStatus('python')` returns `'unavailable'`.

**doc-router note.** Orchestrator in Python, execution in a child subprocess
with a strict IPC contract. Another interpreter means another deployable and
another version pin.

---

## 22. Reference index

### Workflow document model

| Concept | File |
|---------|------|
| `INode`, `IConnections`, `IConnection`, `NodeInputConnections` | `packages/workflow/src/Interfaces.ts` |
| `NodeConnectionTypes` | same file |
| `Workflow` class (builds both adjacency maps) | `packages/workflow/src/Workflow.ts` |
| `WorkflowParameters` | same file |
| Graph traversal helpers | `packages/workflow/src/common/` |
| `IRunExecutionData` v1 | `packages/workflow/src/run-execution-data/run-execution-data.v1.ts` |

### Execution engine

| Concept | File |
|---------|------|
| `WorkflowExecute` (engine entry point) | `packages/core/src/WorkflowExecute.ts` |
| `IRun`, `IRunData`, `ITaskData`, `IWaitingForExecution` | `packages/workflow/src/Interfaces.ts` |
| `INodeExecutionData` | same file |
| `WorkflowDataProxy` (`$json`, `$node`, … bindings) | `packages/workflow/src/workflow-data-proxy.ts` |
| `WorkflowHooks` class | `packages/workflow/src/WorkflowHooks.ts` |

### Trigger and activation

| Concept | File |
|---------|------|
| `ActiveWorkflows` (activation registry) | `packages/core/src/ActiveWorkflows.ts` |
| `TriggersAndPollers` (runs trigger/poll hooks) | `packages/core/src/TriggersAndPollers.ts` |
| `ITriggerFunctions`, `ITriggerResponse`, `IPollFunctions` | `packages/workflow/src/Interfaces.ts` |
| `WorkflowActivateMode`, `WorkflowExecuteMode` | same file |

### Webhooks

| Concept | File |
|---------|------|
| `WebhookEntity` | `packages/cli/src/databases/entities/WebhookEntity.ts` |
| `WebhookService` (find, cache, register) | `packages/cli/src/webhooks/WebhookService.ts` |
| `WebhookRequestHandler` | `packages/cli/src/webhooks/WebhookRequestHandler.ts` |
| `WaitingWebhooks` | `packages/cli/src/webhooks/WaitingWebhooks.ts` |
| `WaitingForms` | `packages/cli/src/webhooks/WaitingForms.ts` |

### Credentials

| Concept | File |
|---------|------|
| `Cipher` (AES-256-GCM encrypt/decrypt) | `packages/core/src/Cipher.ts` |
| `Credentials` class | `packages/core/src/Credentials.ts` |
| `CredentialsEntity` | `packages/cli/src/databases/entities/CredentialsEntity.ts` |
| `CredentialsHelper` (resolution + caching) | `packages/cli/src/CredentialsHelper.ts` |
| `SharedCredentials` repository | `packages/cli/src/databases/repositories/shared-credentials.repository.ts` |

### Multi-process / queue

| Concept | File |
|---------|------|
| `ScalingService` (Bull queue setup) | `packages/cli/src/scaling/scaling.service.ts` |
| `scaling.types.ts` (`JobData`, `JobMessage` …) | `packages/cli/src/scaling/scaling.types.ts` |
| `JobProcessor` (worker-side job handler) | `packages/cli/src/scaling/job-processor.ts` |
| Worker CLI entry point | `packages/cli/src/commands/worker.ts` |
| `Publisher` / `Subscriber` (multi-main pub/sub) | `packages/cli/src/scaling/pubsub/` |
| `ConcurrencyControlService` | `packages/cli/src/concurrency/concurrency-control.service.ts` |
| `ConcurrencyQueue` | `packages/cli/src/concurrency/concurrency-queue.ts` |

### Lifecycle hooks and push

| Concept | File |
|---------|------|
| Hook registration and hook sets | `packages/cli/src/workflow-execute-additional-data.ts` |
| `saveExecutionProgress` hook | `packages/cli/src/execution-lifecycle-hooks/save-execution-progress.ts` |
| `Push` service (WebSocket/SSE) | `packages/cli/src/push/index.ts` |
| `WebSocketPush` | `packages/cli/src/push/websocket.push.ts` |
| `SSEPush` | `packages/cli/src/push/sse.push.ts` |
| Push type definitions | `packages/@n8n/api-types/src/push/` |

### Resumption, errors, sub-workflows, static data

| Concept | File |
|---------|------|
| `Wait` node | `packages/nodes-base/nodes/Wait/Wait.node.ts` |
| `WaitTracker` (timer-based resumption) | `packages/cli/src/WaitTracker.ts` |
| `executeErrorWorkflow` | `packages/cli/src/workflow-execute-additional-data.ts` |
| `ErrorTrigger` node | `packages/nodes-base/nodes/ErrorTrigger/ErrorTrigger.node.ts` |
| `WorkflowExecutionService` (sub-workflow, error workflow) | `packages/cli/src/workflows/workflow-execution.service.ts` |
| `SubworkflowPolicyChecker` | `packages/cli/src/subworkflows/subworkflow-policy-checker.service.ts` |
| `WorkflowStaticDataService` | `packages/cli/src/workflows/workflow-static-data.service.ts` |

### Permissions and ownership

| Concept | File |
|---------|------|
| `Project` entity | `packages/cli/src/databases/entities/project.ts` |
| `OwnershipService` | `packages/cli/src/services/ownership.service.ts` |
| `PermissionChecker` | `packages/cli/src/user-management/permission-checker.ts` |
| `SharedWorkflow` repository | `packages/cli/src/databases/repositories/shared-workflow.repository.ts` |

### Expressions and code execution

| Concept | File |
|---------|------|
| `Expression` class + `initExpressionEngine` | `packages/workflow/src/expression.ts` |
| `WorkflowExpression` | `packages/workflow/src/workflow-expression.ts` |
| VM expression runtime | `packages/@n8n/expression-runtime/` |
| Legacy evaluator (`@n8n/tournament`) | `packages/workflow/src/expression-evaluator-proxy.ts` |
| Code node entry (JS + Python) | `packages/nodes-base/nodes/Code/Code.node.ts` |
| JS task sandbox | `packages/nodes-base/nodes/Code/JsTaskRunnerSandbox.ts` |
| JS worker implementation | `packages/@n8n/task-runner/src/js-task-runner/js-task-runner.ts` |
| Python task sandbox | `packages/nodes-base/nodes/Code/PythonTaskRunnerSandbox.ts` |
| Python worker process (CLI) | `packages/cli/src/task-runners/task-runner-process-py.ts` |

### HTTP API

| Concept | File |
|---------|------|
| Public OpenAPI spec | `packages/cli/src/public-api/v1/openapi.yml` |
| Public workflow handlers | `packages/cli/src/public-api/v1/handlers/workflows/workflows.handler.ts` |
| Internal REST workflows controller | `packages/cli/src/workflows/workflows.controller.ts` |
| Internal REST executions controller | `packages/cli/src/executions/executions.controller.ts` |
| Workflow create/update DTO validation | `packages/@n8n/api-types/src/dto/workflows/base-workflow.dto.ts` |
