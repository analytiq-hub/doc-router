# n8n architecture reference

This document describes the n8n implementation accurately, organized as a
**blueprint** for [flows.md](flows.md). Each section names the concept, shows
where n8n implements it, and ends with a **doc-router note** — what to adopt,
adapt, or skip.

Paths are relative to the n8n repo root unless noted. The n8n repo may drift;
treat this as a snapshot.

---

## 1. Workflow document model

### What it is

A **workflow** is the persisted artifact: a graph of node instances plus
metadata. At rest it is a database row (`WorkflowEntity`, stored via
TypeORM). In memory n8n constructs a `Workflow` object that builds two
adjacency maps from the stored `connections` object.

### Key types

| Type | File | Role |
|------|------|------|
| `INode` | `packages/workflow/src/interfaces.ts:1344` | One node instance in the graph. |
| `IConnections` | `packages/workflow/src/interfaces.ts:417` | The full edge map: `{ [sourceNodeName]: INodeConnections }`. |
| `INodeConnections` | same file:412 | Per-node edges: `{ [connectionType]: NodeInputConnections }`. |
| `NodeInputConnections` | same file:405 | `Array<IConnection[] \| null>` — one slot per output index; inner array = fan-out targets. |
| `IConnection` | same file:89 | One edge target: `{ node: string, type: NodeConnectionType, index: number }`. |
| `NodeConnectionTypes` | same file:2354 | Enum-like const: `Main = 'main'`, plus AI variants (`AiTool`, `AiLanguageModel`, …). |
| `Workflow` (class) | `packages/workflow/src/workflow.ts:59` | Runtime object: builds `connectionsBySourceNode` and `connectionsByDestinationNode` on construction; holds `nodes: INodes` (keyed by name). |
| `WorkflowParameters` | same file:47 | Constructor bag: `id`, `name`, `nodes[]`, `connections`, `active`, `nodeTypes`, `staticData`, `settings`, `pinData`. |

### INode fields

| Field | Type | Notes |
|-------|------|-------|
| `id` | string | Stable UUID. |
| `name` | string | **Unique within the workflow.** Used as the key in `connections` and in `runData`. |
| `type` | string | Registry key, e.g. `n8n-nodes-base.httpRequest`. |
| `typeVersion` | number | Selects the parameter schema / behavior version for that type. |
| `position` | `[number, number]` | Canvas `[x, y]`. Editor-only; not used by the engine. |
| `parameters` | object | Type-specific config. Opaque to the engine; resolved by the node type. |
| `credentials` | object? | `{ [slotName]: { id: string\|null, name: string } }`. Secrets stored separately. |
| `disabled` | boolean? | Skip node during execution. |
| `continueOnFail` | boolean? | Continue workflow even when this node errors. |
| `onError` | enum? | `'stopWorkflow' \| 'continueRegularOutput' \| 'continueErrorOutput'`. |
| `retryOnFail` / `maxTries` / `waitBetweenTries` | … | Retry policy. |
| `alwaysOutputData` | boolean? | Emit a placeholder item when output would be empty. |
| `executeOnce` | boolean? | Run once per workflow execution regardless of item count. |
| `notes` / `notesInFlow` | string / boolean? | Editor annotations; ignored by the engine. |
| `webhookId` | string? | Webhook/trigger registration key. |

### connections storage format

`connections` is indexed by **source node name** (not id). The `node` field
inside each `IConnection` target also refers to the **destination node name**.

```
connections: {
  [sourceNodeName: string]: {
    [connectionType: string]:      // usually "main"
      Array<                       // one slot per output index
        IConnection[] | null       // inner array = fan-out targets from that output
      >
  }
}
```

Example — one source, two output branches, each going to a different node:

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

Example — fan-out from a single output to two nodes:

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

### Graph traversal utilities

`packages/workflow/src/common/` exports helpers used throughout the engine:

```typescript
import { getParentNodes, getChildNodes, mapConnectionsByDestination } from 'n8n-workflow';

// connections is indexed by source; must invert first to find parents
const byDest = mapConnectionsByDestination(workflow.connections);
const parents = getParentNodes(byDest, 'NodeName', 'main', 1);

// children use the source-indexed map directly
const children = getChildNodes(workflow.connections, 'NodeName', 'main', 1);
```

`Workflow` pre-builds both maps as `connectionsBySourceNode` and
`connectionsByDestinationNode` at construction time.

**doc-router note.** The node/connection JSON shape is a good model to
follow. The one difference worth considering: n8n keys edges by node
**name** (stable for display, fragile to renames); doc-router can key by
node **id** for rename-safety. Whichever you choose, nodes and edges must
agree on the same key.

### Portable workflow JSON format

n8n does not have a separate export format. The same `IWorkflowBase` shape is
used for database storage, API responses, file import, and source-control
export (`ExportableWorkflow`,
`packages/cli/src/modules/source-control.ee/types/exportable-workflow.ts`).

**`IWorkflowBase`** (`packages/workflow/src/interfaces.ts:2885`) — the
canonical portable document:

```json
{
  "id": "abc123",
  "name": "Invoice processing",
  "active": false,
  "isArchived": false,
  "versionId": "<uuid>",
  "activeVersionId": "<uuid>",
  "nodes": [ ],
  "connections": { },
  "settings": {
    "timezone": "UTC",
    "executionOrder": "v1",
    "executionTimeout": 3600,
    "saveDataErrorExecution": "all",
    "saveDataSuccessExecution": "none",
    "saveManualExecutions": true,
    "errorWorkflow": "<workflow-id>"
  },
  "staticData": { },
  "pinData": { },
  "meta": { "templateId": "...", "instanceId": "..." },
  "createdAt": "2024-01-01T00:00:00.000Z",
  "updatedAt": "2024-01-02T00:00:00.000Z"
}
```

`IWorkflowToImport` (`packages/cli/src/interfaces.ts:63`) omits `staticData`,
`pinData`, `createdAt`, `updatedAt`, and `activeVersion`, and adds `owner`
(personal email or team id/name) and `parentFolderId`. The graph fields
(`nodes`, `connections`) are identical in all variants.

**`staticData`** (`IDataObject`) — persistent key/value state written by
trigger and webhook nodes across executions (e.g. a cursor position for
polling). Updated in-place on `WorkflowEntity` after each execution; not
versioned separately.

**`pinData`** (`IPinData: { [nodeName]: INodeExecutionData[] }`) — per-node
output overrides keyed by node **name**. When set, the engine substitutes
pinned data for the real execution output, letting developers iterate on
downstream nodes without re-running expensive upstream steps. Stored on the
workflow row and sent to the canvas UI; cleared per node by the user.

**`meta`** (`WorkflowFEMeta`) — frontend and template provenance fields:
`templateId`, `instanceId`, `onboardingId`,
`templateCredsSetupCompleted`. No effect on execution.

**Version history** is stored separately in the `WorkflowHistory` table
(`packages/@n8n/db/src/entities/workflow-history.ts`). A history row contains
`versionId`, `workflowId`, `nodes`, `connections`, `authors`, `name`,
`description`, `autosaved`, and timestamps. The active version is pointed to by
`WorkflowEntity.activeVersionId`; the current graph on `WorkflowEntity` itself
is the live editable copy.

**`IWorkflowSettings`** (`packages/workflow/src/interfaces.ts:3111`) — notable
fields beyond timezone and timeout:

| Field | Meaning |
|-------|---------|
| `executionOrder` | `'v0'` (legacy) or `'v1'` (current). Controls the engine's node scheduling order. |
| `errorWorkflow` | ID of another workflow to trigger when this one fails. |
| `saveDataErrorExecution` / `saveDataSuccessExecution` | `'all'` \| `'none'` — whether to persist execution data. |
| `callerPolicy` | Which workflows are allowed to call this one as a sub-workflow. |
| `availableInMCP` | Whether the workflow is exposed as an MCP tool. |

**doc-router note.** `staticData`, `pinData`, and `meta` should be reserved
in the `flow_revisions` schema from the start (stored as `null` in v1) so the
storage format and export contract do not need a breaking change when they are
activated. See [flows.md § Future fields](flows.md).

---

## 2. Node type registry

### What it is

Separates **"what types can appear on the canvas"** from **"what a specific
workflow stores"**. Each node type is a class implementing `INodeType`
(or `INodeTypeBase`), registered in `INodeTypes`. At runtime n8n resolves
a node's type + version to get its `description` (parameter schema,
inputs/outputs, credentials) and its `execute` / trigger hooks.

### Key interfaces

| Interface | File | Role |
|-----------|------|------|
| `INodeType` | `packages/workflow/src/interfaces.ts` | Base contract: `description: INodeTypeDescription`, plus optional `execute`, `trigger`, `webhook`, `poll`, `supplyData` hooks. |
| `INodeTypeDescription` | same file | Metadata: `name`, `displayName`, `version`, `inputs`, `outputs`, `properties` (parameter definitions), `credentials`, `defaults`. |
| `INodeTypes` | same file | Registry interface: `getByName(name)`, `getByNameAndVersion(name, version)`. |

### Node implementation pattern

Built-in nodes live in `packages/nodes-base/nodes/`. Each folder typically
contains `<Name>.node.ts` (the type class), any helper files, and tests.
The `execute` method receives `IExecuteFunctions` (context) and returns
`INodeExecutionData[][]` — one inner array per output, each element is one
item.

**doc-router note.** Implement a step type registry as a Python dict
`{ key: StepType }`. Each `StepType` holds a JSON Schema for `parameters`,
input/output counts, and an async `execute(context, node, items)` callable.
This gives you the same separation between the canvas palette and the stored
graph.

---

## 3. Execution engine

### Overview

`WorkflowExecute` (`packages/core/src/execution-engine/workflow-execute.ts`)
runs a `Workflow` instance. It is constructed with `additionalData`
(credentials resolver, hooks, push transport) and a `mode`
(`'manual' | 'trigger' | 'webhook' | …`).

Entry points:
- `run(options)` — full execution from a start node.
- `runPartialWorkflow2(…)` — re-run only dirty nodes (canvas "run from here").

Both return a `PCancelable<IRun>` — cancellable by calling `.cancel()` on
the returned object.

### Main loop (`processRunExecutionData`)

`processRunExecutionData` is the core loop (`workflow-execute.ts:1426`).
Steps:

1. `workflow.expression.acquireIsolate()` — pins a VM isolate for expression
   evaluation (no-op in legacy mode).
2. `hooks.runHook('workflowExecuteBefore', …)` — persistence, telemetry.
3. **Loop** while `runExecutionData.executionData.nodeExecutionStack` is
   non-empty:
   - Dequeue `IExecuteData` (the next node + its input items + source info).
   - Call the node's `execute` (or poll/webhook/trigger) hook via
     `NodeExecuteFunctions`.
   - On success: store `ITaskData` in `runData[node.name]`; push successor
     nodes + their inputs onto `nodeExecutionStack`.
   - On failure: store error in `ITaskData`; honour `continueOnFail` /
     `onError`.
4. `workflow.expression.releaseIsolate()` in `finally`.
5. `hooks.runHook('workflowExecuteAfter', …)` — persist `IRun`.

### Run state types

| Type | File | Role |
|------|------|------|
| `IRun` | `packages/workflow/src/interfaces.ts:2691` | Top-level result: `data: IRunExecutionData`, `status`, `startedAt`, `stoppedAt`, `mode`. |
| `IRunExecutionData` | `packages/workflow/src/run-execution-data/` | Versioned (v0/v1). Contains `startData`, `resultData` (including `runData`), and `executionData` (stack + waiting maps). |
| `IRunData` | `packages/workflow/src/interfaces.ts:2727` | `{ [nodeName]: ITaskData[] }` — per-node output, array because a node can run multiple times (loops). |
| `ITaskData` | same file:2824 | One node execution result: `startTime`, `executionTime`, `executionStatus`, `data: ITaskDataConnections`, `error?`. |
| `ITaskDataConnections` | same file:2852 | `{ [connectionType]: Array<INodeExecutionData[] \| null> }` — the node's output items. |
| `IWaitingForExecution` | same file:2860 | `{ [nodeName]: { [runIndex]: ITaskDataConnections } }` — inputs for nodes waiting on multi-input merge. |
| `nodeExecutionStack` | inside `executionData` | Stack of `IExecuteData` — nodes ready to run with their input data. |

### Item data format

Each item the engine passes between nodes is `INodeExecutionData`
(`interfaces.ts:1456`):

```typescript
interface INodeExecutionData {
  json: IDataObject;         // the primary payload
  binary?: IBinaryKeyData;   // optional file attachments
  error?: NodeApiError | NodeOperationError;
  pairedItem?: IPairedItemData | IPairedItemData[] | number;
}
```

**doc-router note.** The engine's core pattern — a stack of ready work
units, a waiting map for merge nodes, per-node `runData` as the persistent
output record — is directly reusable. In Python: maintain a `deque` of
ready `(node_id, input_items)` tuples and a `dict[node_id, int]` counting
remaining inputs still needed before enqueuing a merge node.

---

## 4. HTTP surfaces

### Public API (external / API-key)

- **Base path**: `/api/v1` (from `openapi.yml` `servers[0].url`).
- **Auth**: `X-N8N-API-KEY` header or Bearer JWT
  (`packages/cli/src/public-api/v1/openapi.yml`, `components.securitySchemes`).
- **Spec**: `packages/cli/src/public-api/v1/openapi.yml`.

| Resource | Paths (prefix `/api/v1`) | Methods |
|----------|--------------------------|---------|
| Workflows | `/workflows` | `GET`, `POST` |
| Workflow | `/workflows/{id}` | `GET`, `PUT`, `DELETE` |
| Version | `/workflows/{id}/{versionId}` | `GET` |
| Activate / deactivate | `/workflows/{id}/activate`, `…/deactivate` | `POST` |
| Archive / unarchive | `/workflows/{id}/archive`, `…/unarchive` | `POST` |
| Transfer / tags | `/workflows/{id}/transfer`, `…/tags` | `PUT` |
| Executions | `/executions`, `/executions/{id}` | `GET` |
| Stop one / bulk stop | `/executions/{id}/stop`, `/executions/stop` | `POST` |
| Retry | `/executions/{id}/retry` | `POST` |
| Delete execution | `/executions/{id}` | `DELETE` |
| Execution tags | `/executions/{id}/tags` | `GET`, `PUT` |

**Important gap**: the public API has **no** `POST /workflows/{id}/run`.
On-demand manual execution exists only on the internal REST API (below).
External callers normally activate a workflow and invoke it via a webhook
or schedule trigger.

### Internal REST API (browser session)

- **Base path**: `/rest`.
- **Auth**: session cookie + CSRF; not the public API-key model.
- **Controllers**: `packages/cli/src/workflows/workflows.controller.ts`,
  `packages/cli/src/executions/executions.controller.ts`.

Notable differences from the public API:

| Capability | Internal (`/rest`) | Public (`/api/v1`) |
|------------|--------------------|--------------------|
| Update workflow | `PATCH /workflows/{id}` (partial) | `PUT /workflows/{id}` (full replace) |
| Manual run | `POST /workflows/{id}/run` ✓ | **Not available** |
| Stop many | `POST /executions/stopMany` | `POST /executions/stop` (filter body) |
| Bulk delete | `POST /executions/delete` | `DELETE /executions/{id}` (one at a time) |

The internal controller also exposes workflow collaboration (`write-lock`),
sharing (`PUT /{id}/share`), last-successful execution, and "new workflow
name" helpers that have no public equivalent.

### doc-router goal: one contract

n8n's split is a product history artifact. For doc-router, expose a
**single route tree** (`/v0/orgs/{org_id}/…`) used by both the UI client
and automation clients:

1. One update verb and DTO — not different shapes per caller.
2. Manual run available to API-key callers, not just session users.
3. Auth as a dimension only — session vs API key routes to the same
   handlers; optional narrower scopes for keys, not different paths.

---

## 5. Expression evaluation

### What expressions are

Expressions are **small snippets** embedded in string-valued node
parameters. The convention is a leading `=`: `"={{ $json.url }}"`.
They are resolved by the engine (or UI preview) when a parameter value
is needed, turning the template into a concrete value for the current item.
They are **not** the same as the Code node.

### Resolution pipeline

1. **Detect** — `isExpression(value)` (`packages/workflow/src/expressions/expression-helpers.ts`).
   If true, strip the leading `=` and evaluate; otherwise return the literal.
2. **Build context** — `WorkflowDataProxy`
   (`packages/workflow/src/workflow-data-proxy.ts`) wraps the current
   workflow, run data, and item index in a proxy object that exposes
   `$json`, `$node`, `$input`, `$items`, `$env`, `$evaluateExpression`,
   etc. as lazy getters.
3. **Evaluate** — `WorkflowExpression` →`Expression`
   (`packages/workflow/src/expression.ts`) strips the `=`, applies syntax
   extensions via `@n8n/tournament`, then calls `renderExpression`.

### Two evaluation modes

Configured once at startup via `Expression.initExpressionEngine()`
(`expression.ts:247`), called from `packages/cli/src/commands/base-command.ts`.

| Mode | Where | Mechanism |
|------|-------|-----------|
| **`legacy`** (default) | Same Node.js process | `@n8n/tournament` transforms and evaluates. AST passes (`ThisSanitizer`, `PrototypeSanitizer`, `DollarSignValidator`) block common escape patterns. Lighter but weaker isolation. |
| **`vm`** | Same Node.js process, isolated V8 heap | `@n8n/expression-runtime`: `ExpressionEvaluator` + `IsolatedVmBridge` (`isolated-vm`). Memory limit, timeout, pooled isolates. Same AST hooks run around eval. |

`IS_FRONTEND` guard in `Expression.renderExpression` forces legacy mode in
the browser bundle regardless of config.

Per-execution isolate lifecycle: `processRunExecutionData` calls
`workflow.expression.acquireIsolate()` before the loop and
`releaseIsolate()` in `finally` (`workflow-execute.ts:1458`, `:2333`).

**doc-router note.** If doc-router ever supports inline expressions in step
parameters, treat them as a separate security class from full script
execution: short strings, high call frequency, need `$json`-style bindings.
Do not `eval` raw user strings in the API process. In v1 skip expressions
entirely and use literal parameter values only.

---

## 6. Code node — JavaScript

### Pipeline

1. `Code.node.ts` (`packages/nodes-base/nodes/Code/Code.node.ts`) reads
   `parameters.jsCode` and `mode` (`runOnceForAllItems` or
   `runOnceForEachItem`).
2. `JsTaskRunnerSandbox` (`same dir/JsTaskRunnerSandbox.ts`) calls
   `IExecuteFunctions.startJob('javascript', settings, itemIndex)`.
3. `startJob` → `additionalData.startRunnerTask` → `TaskRequester`
   (`packages/cli/src/task-runners/task-managers/task-requester.ts`):
   serialises the task and sends it to a **separate OS process**.
4. `JsTaskRunner`
   (`packages/@n8n/task-runner/src/js-task-runner/js-task-runner.ts`):
   - Creates a **`node:vm`** context (`createContext` + `runInContext`)
     with a configurable timeout.
   - **`secure` mode** (default): freezes builtins, blocks
     `Error.prepareStackTrace` escape patterns, replaces `require` with an
     allowlist (`createRequireResolver`).
   - **`insecure` mode**: `new Function + with(context)` — easier to
     escape; for trusted/self-hosted environments only.
   - Exposes narrow RPC so user code can request input items and
     `$`-style proxy data from the main process rather than receiving the
     full execution blob.
   - Chunks per-item runs (e.g. 1000 items) to bound IPC payload size.

**doc-router note.** Process boundary first (worker process), then VM
policy inside the worker. Allowlisted imports, timeouts, no silent access
to host env. In doc-router v1 the `code` step runs in-process with a
restricted helper set; move to a subprocess sandbox in v2.

---

## 7. Code node — Python

1. Same `Code.node.ts`; language parameter selects Python.
2. `PythonTaskRunnerSandbox`
   (`packages/nodes-base/nodes/Code/PythonTaskRunnerSandbox.ts`) calls
   `startJob('python', taskSettings, …)`.
3. CLI starts and communicates with `@n8n/task-runner-python`
   (`packages/cli/src/task-runners/task-runner-process-py.ts`): a dedicated
   Python interpreter (project venv), not CPython embedded in the Node thread.
4. If Python/venv is missing, `getRunnerStatus('python')` returns
   `'unavailable'` so the UI can fail fast.

**doc-router note.** Same pattern as JS: orchestrator in Python, execution
in a child subprocess with a strict IPC contract and no shared mutable
filesystem unless intended. Another interpreter means another deployable
and another version pin.

---

## 8. Reference index

| Concept | Location in n8n repo |
|---------|----------------------|
| `INode`, `IConnections`, `IConnection` | `packages/workflow/src/interfaces.ts` |
| `NodeConnectionTypes` (enum) | same file:2354 |
| `NodeInputConnections`, `INodeConnections` | same file:405, 412 |
| `IRun`, `IRunData`, `ITaskData`, `IWaitingForExecution` | same file:2691–2880 |
| `Workflow` class (runtime, builds both adjacency maps) | `packages/workflow/src/workflow.ts:59` |
| `WorkflowParameters` (constructor bag) | same file:47 |
| Graph traversal helpers | `packages/workflow/src/common/` |
| `IRunExecutionData` v1 | `packages/workflow/src/run-execution-data/run-execution-data.v1.ts` |
| `WorkflowExecute` (engine) | `packages/core/src/execution-engine/workflow-execute.ts` |
| `processRunExecutionData` (main loop) | same file:1426 |
| `Expression` class + `initExpressionEngine` | `packages/workflow/src/expression.ts:227` |
| `WorkflowDataProxy` (`$json`, `$node`, … bindings) | `packages/workflow/src/workflow-data-proxy.ts` |
| `WorkflowExpression` | `packages/workflow/src/workflow-expression.ts` |
| VM expression runtime | `packages/@n8n/expression-runtime/` |
| Legacy expression evaluator (`@n8n/tournament`) | `packages/workflow/src/expression-evaluator-proxy.ts` |
| Code node entry (JS + Python) | `packages/nodes-base/nodes/Code/Code.node.ts` |
| JS task sandbox | `packages/nodes-base/nodes/Code/JsTaskRunnerSandbox.ts` |
| JS worker implementation | `packages/@n8n/task-runner/src/js-task-runner/js-task-runner.ts` |
| Python task sandbox | `packages/nodes-base/nodes/Code/PythonTaskRunnerSandbox.ts` |
| Python worker process (CLI) | `packages/cli/src/task-runners/task-runner-process-py.ts` |
| `startJob` (node → task runner bridge) | `packages/core/src/execution-engine/node-execution-context/base-execute-context.ts` |
| Public OpenAPI spec | `packages/cli/src/public-api/v1/openapi.yml` |
| Public workflow handlers | `packages/cli/src/public-api/v1/handlers/workflows/workflows.handler.ts` |
| Internal REST workflows controller | `packages/cli/src/workflows/workflows.controller.ts` |
| Internal REST executions controller | `packages/cli/src/executions/executions.controller.ts` |
| Workflow create/update DTO validation | `packages/@n8n/api-types/src/dto/workflows/base-workflow.dto.ts` |
