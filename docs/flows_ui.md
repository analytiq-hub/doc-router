# Flows UI — Implementation Plan

This document covers the full implementation plan for the Flows UI: FastAPI
gaps, TypeScript SDK additions, and the Next.js frontend. It is ordered as a
dependency chain — each section must be complete before the next begins.

---

## 1. FastAPI status

All core flow routes are implemented in `app/routes/flows.py`:

| Route | Status |
|-------|--------|
| `GET /v0/orgs/{org_id}/flows/node-types` | ✓ |
| `POST /v0/orgs/{org_id}/flows` | ✓ |
| `GET /v0/orgs/{org_id}/flows` | ✓ |
| `GET /v0/orgs/{org_id}/flows/{flow_id}` | ✓ |
| `PATCH /v0/orgs/{org_id}/flows/{flow_id}` | ✓ |
| `PUT /v0/orgs/{org_id}/flows/{flow_id}` (save revision) | ✓ |
| `GET /v0/orgs/{org_id}/flows/{flow_id}/revisions` | ✓ |
| `GET /v0/orgs/{org_id}/flows/{flow_id}/revisions/{flow_revid}` | ✓ |
| `POST /v0/orgs/{org_id}/flows/{flow_id}/activate` | ✓ |
| `POST /v0/orgs/{org_id}/flows/{flow_id}/deactivate` | ✓ |
| `POST /v0/orgs/{org_id}/flows/{flow_id}/run` | ✓ |
| `GET /v0/orgs/{org_id}/flows/{flow_id}/executions` | ✓ |
| `GET /v0/orgs/{org_id}/flows/{flow_id}/executions/{exec_id}` | ✓ |
| `POST /v0/orgs/{org_id}/flows/{flow_id}/executions/{exec_id}/stop` | ✓ |
| `POST /v0/webhooks/{webhook_id}` | ✓ |
| `DELETE /v0/orgs/{org_id}/flows/{flow_id}` | **Missing** |

The only gap is a delete route for the flow header document. Add it to
`flows.py` before starting the SDK layer.

---

## 2. TypeScript SDK additions

**File**: `packages/typescript/sdk/src/types/flows.ts` (new)
**File**: `packages/typescript/sdk/src/types/index.ts` (re-export)
**File**: `packages/typescript/sdk/src/docrouter-org.ts` (new section)

### 2.1 Types — `types/flows.ts`

```typescript
// ---- Node types ----

export interface FlowNodeType {
  key: string;
  label: string;
  description: string;
  category: string;
  is_trigger: boolean;
  is_merge: boolean;
  min_inputs: number;
  max_inputs: number | null;
  outputs: number;
  output_labels: string[];
  parameter_schema: Record<string, unknown>;
}

export interface ListNodeTypesResponse {
  items: FlowNodeType[];
  total: number;
}

// ---- Flow header ----

export interface FlowHeader {
  flow_id: string;
  organization_id: string;
  name: string;
  active: boolean;
  active_flow_revid: string | null;
  flow_version: number;
  created_at: string;
  created_by: string;
  updated_at: string;
  updated_by: string;
}

// ---- Revision ----

export interface FlowRevisionSummary {
  flow_revid: string;
  flow_version: number;
  graph_hash: string;
  created_at: string;
  created_by: string;
}

export interface FlowRevision extends FlowRevisionSummary {
  flow_id: string;
  nodes: FlowNode[];
  connections: FlowConnections;
  settings: Record<string, unknown>;
  pin_data: Record<string, unknown> | null;
  engine_version: number;
}

export interface FlowNode {
  id: string;
  name: string;
  type: string;
  position: [number, number];
  parameters: Record<string, unknown>;
  disabled?: boolean;
  on_error?: 'stop' | 'continue';
  notes?: string | null;
}

export interface FlowNodeConnection {
  dest_node_id: string;
  connection_type: 'main';
  index: number;
}

export type FlowConnections = Record<
  string,
  { main: Array<FlowNodeConnection[] | null> }
>;

// ---- List responses ----

export interface FlowListItem {
  flow: FlowHeader;
  latest_revision: FlowRevisionSummary | null;
}

export interface ListFlowsResponse {
  items: FlowListItem[];
  total: number;
}

export interface ListRevisionsResponse {
  items: FlowRevisionSummary[];
  total: number;
}

// ---- Execution ----

export type FlowExecutionStatus = 'queued' | 'running' | 'success' | 'error' | 'stopped';

export interface FlowExecution {
  execution_id: string;
  flow_id: string;
  flow_revid: string;
  organization_id: string;
  mode: string;
  status: FlowExecutionStatus;
  started_at: string;
  finished_at: string | null;
  last_heartbeat_at: string | null;
  stop_requested: boolean;
  last_node_executed: string | null;
  run_data: Record<string, unknown>;
  error: Record<string, unknown> | null;
  trigger: Record<string, unknown>;
}

export interface ListExecutionsResponse {
  items: FlowExecution[];
  total: number;
}

// ---- Request params ----

export interface CreateFlowParams {
  name: string;
}

export interface SaveRevisionParams {
  base_flow_revid: string;
  name: string;
  nodes: FlowNode[];
  connections: FlowConnections;
  settings?: Record<string, unknown>;
  pin_data?: Record<string, unknown> | null;
}

export interface RunFlowParams {
  flow_revid?: string;
  document_id?: string;
}
```

### 2.2 New methods in `DocRouterOrg`

Add a `// ---------------- Flows ----------------` section at the end of
`docrouter-org.ts` with these methods:

```typescript
// Node types
async listFlowNodeTypes(): Promise<ListNodeTypesResponse>

// Flow CRUD
async createFlow(params: CreateFlowParams): Promise<{ flow: FlowHeader }>
async listFlows(params?: { limit?: number; offset?: number }): Promise<ListFlowsResponse>
async getFlow(flowId: string): Promise<FlowListItem>
async patchFlow(flowId: string, params: { name: string }): Promise<FlowListItem>
async deleteFlow(flowId: string): Promise<void>
async saveRevision(flowId: string, params: SaveRevisionParams): Promise<{ flow: FlowHeader; revision: FlowRevision | null }>

// Revisions
async listRevisions(flowId: string, params?: { limit?: number; offset?: number }): Promise<ListRevisionsResponse>
async getRevision(flowId: string, flowRevid: string): Promise<FlowRevision>

// Activation
async activateFlow(flowId: string, flowRevid?: string): Promise<FlowListItem>
async deactivateFlow(flowId: string): Promise<FlowListItem>

// Execution
async runFlow(flowId: string, params?: RunFlowParams): Promise<{ execution_id: string }>
async listExecutions(flowId: string, params?: { limit?: number; offset?: number }): Promise<ListExecutionsResponse>
async getExecution(flowId: string, executionId: string): Promise<FlowExecution>
async stopExecution(flowId: string, executionId: string): Promise<{ ok: boolean }>
```

---

## 3. Frontend — file layout

The flows section follows the same pattern as `prompts/` and `schemas/`:
a page-level tab container with child components.

```
src/app/orgs/[organizationId]/
  flows/
    page.tsx                      Flow list page (tab: list | create)
    [flowId]/
      page.tsx                    Flow editor page (tab: editor | executions)

src/components/flows/
  FlowList.tsx                    Table of flows with actions
  FlowCreate.tsx                  Create-flow form (name only)
  FlowEditor.tsx                  React Flow canvas + side panels
  FlowNodePalette.tsx             Left sidebar: draggable node type cards
  FlowNodeConfigPanel.tsx         Right sidebar: parameter form for selected node
  FlowToolbar.tsx                 Top bar: save / run / activate / deactivate
  FlowExecutionList.tsx           Execution history table
  FlowExecutionDetail.tsx         Run data tree / node status overlay
  FlowStatusBadge.tsx             Coloured badge for execution status
  useFlowApi.ts                   Hook wrapping DocRouterOrg flow methods
  useExecutionPoller.ts           Hook polling getExecution until terminal status
```

---

## 4. Phase 1 — Flow list and management

**Goal**: list, create, rename, delete, activate, deactivate, and manually run
flows without a graph editor.

### 4.1 `flows/page.tsx`

Mirrors `prompts/page.tsx`: tab bar with "Flows" and "Create Flow" tabs.
Uses `useSearchParams` for tab state in the URL.

```tsx
'use client'
export default function FlowsPage({ params }) {
  const { organizationId } = use(params);
  // tab: 'list' | 'create'
  return (
    <div className="p-4">
      {/* tab bar */}
      <div role="tabpanel">
        {tab === 'list'   && <FlowList   organizationId={organizationId} />}
        {tab === 'create' && <FlowCreate organizationId={organizationId} />}
      </div>
    </div>
  );
}
```

### 4.2 `FlowList.tsx`

Table columns: Name, Status (active badge), Version, Last updated, Actions.

Actions per row:
- **Edit** → navigate to `/orgs/{org}/flows/{flowId}`
- **Run** → call `runFlow`, show snackbar with execution id
- **Activate / Deactivate** → toggle with confirmation for deactivate
- **Delete** → confirmation dialog, then `deleteFlow`

Pagination: `limit=20`, offset-based, same pattern as `PromptList`.

### 4.3 `FlowCreate.tsx`

Single text field for name. On submit calls `createFlow`, then navigates to
`/orgs/{org}/flows/{flowId}` so the user lands in the editor.

### 4.4 Sidebar navigation entry

Add "Flows" to the org sidebar navigation (wherever `Prompts`, `Documents`,
etc. appear). Route: `/orgs/{organizationId}/flows`.

---

## 5. Phase 2 — Graph editor

**Goal**: a visual canvas where users can build, edit, and save flow graphs.

### 5.1 `flows/[flowId]/page.tsx`

Two-tab layout: **Editor** and **Executions**.

On mount:
1. Load `getFlow(flowId)` → display name and active status in the toolbar.
2. Load `getRevision(flowId, latestRevisionId)` → populate the canvas.
3. Load `listFlowNodeTypes()` → populate the node palette.

### 5.2 `FlowEditor.tsx`

Built on `reactflow` (already in `package.json` at `^11.11.4`).

```
┌─────────────────────────────────────────────────────────┐
│  FlowToolbar (save | run | activate | status badge)     │
├──────────────┬──────────────────────────┬───────────────┤
│ NodePalette  │   React Flow canvas      │ NodeConfig    │
│ (node types  │   (nodes + edges)        │ Panel         │
│  draggable)  │                          │ (params for   │
│              │                          │  selected     │
│              │                          │  node)        │
└──────────────┴──────────────────────────┴───────────────┘
```

**State model:**

```typescript
interface EditorState {
  nodes: RFNode[];        // React Flow node objects
  edges: RFEdge[];        // React Flow edge objects
  selectedNodeId: string | null;
  isDirty: boolean;       // unsaved changes
  isSaving: boolean;
  isRunning: boolean;
  lastExecution: FlowExecution | null;
}
```

**Conversion between engine and React Flow formats:**

The engine stores `nodes[]` and `connections` (source-keyed dict). React Flow
uses `nodes[]` (with `position`) and `edges[]` (source/target pairs). Two
helper functions handle the round-trip:

```typescript
function revisionToRF(revision: FlowRevision): { nodes: RFNode[]; edges: RFEdge[] }
function rfToRevision(rfNodes: RFNode[], rfEdges: RFEdge[], current: FlowRevision): SaveRevisionParams
```

**Adding nodes**: drag from `FlowNodePalette` onto the canvas. On drop, create
a new node with a UUID id, the dropped type's key, default position, and an
empty `parameters` object. React Flow's `onDrop` + `onDragOver` handlers manage
this.

**Connecting nodes**: React Flow's built-in edge drawing. `onConnect` validates
that the source output index and destination input index are within the node
type's declared bounds. Invalid connections are rejected silently (no edge
added).

**Deleting nodes/edges**: React Flow's `onNodesDelete` / `onEdgesDelete`
callbacks update state. Deleting a node removes all its edges too.

### 5.3 `FlowNodePalette.tsx`

Left sidebar. Groups node types by `category`. Each entry is a draggable card
showing `label` and `description`. On drag start sets `dataTransfer` with the
node type key.

```tsx
<div
  draggable
  onDragStart={(e) => e.dataTransfer.setData('application/flow-node-type', nt.key)}
>
  {nt.label}
</div>
```

### 5.4 `FlowNodeConfigPanel.tsx`

Right sidebar. Rendered when `selectedNodeId` is set. Shows a form for the
selected node's `parameters`, driven by the node type's `parameter_schema`.

Parameter form rendering rules:
- `string` with key `python_code` or `js_code` or `ts_code` → Monaco Editor
  (already in `package.json` at `^4.6.0`) with the appropriate language mode.
- `string` → `<TextField>`
- `number` → `<TextField type="number">`
- `boolean` → `<Switch>`
- `object` / `array` → Monaco Editor in JSON mode.

Also shows:
- Node name (editable, must be unique within the flow)
- `disabled` toggle
- `on_error` select (`stop` / `continue`)

Changes are applied to local state immediately (the canvas is the source of
truth until Save).

### 5.5 `FlowToolbar.tsx`

```
[flow name]  [active badge]   |  [Save]  [Run]  [Activate / Deactivate]
```

**Save**: calls `saveRevision`. Passes current `latest_revision.flow_revid` as
`base_flow_revid`. On 409 (concurrent edit), shows an error toast.

**Run**: calls `runFlow`, then starts the execution poller (§5.7), switches to
the Executions tab.

**Activate**: calls `activateFlow` (uses the latest saved revision). Disabled
if there are unsaved changes (`isDirty`).

**Deactivate**: calls `deactivateFlow` with a confirmation dialog.

### 5.6 Custom React Flow node renderer

Each node on the canvas is rendered by a custom node component that shows:
- Node type label (small, grey)
- Node name (bold)
- Input handles (left side, one per `min_inputs`)
- Output handles (right side, one per `outputs`, labelled with `output_labels`)
- Error / skipped / success status badge when an execution result is loaded

Register custom node types:

```typescript
const nodeTypes = useMemo(() => ({
  'flow-node': FlowCanvasNode,
}), []);
```

All engine node types map to the same `'flow-node'` React Flow node type; the
display varies only by data (label, handle counts, status).

### 5.7 `useExecutionPoller.ts`

Polls `getExecution` every 2 seconds until `status` is `success | error |
stopped`. Returns the latest `FlowExecution`. The editor uses this to overlay
per-node status badges on the canvas.

```typescript
function useExecutionPoller(
  orgApi: DocRouterOrg,
  flowId: string,
  executionId: string | null,
): { execution: FlowExecution | null; isPolling: boolean }
```

---

## 6. Phase 3 — Execution history tab

### 6.1 `FlowExecutionList.tsx`

Table columns: Started, Mode, Status, Duration, Actions.

Actions:
- **View** → expand `FlowExecutionDetail` inline or navigate to a detail panel.
- **Stop** → calls `stopExecution` (only shown when status is `queued | running`).

Polling: when any row is in `queued | running` state, poll `listExecutions`
every 3 seconds to refresh status.

### 6.2 `FlowExecutionDetail.tsx`

Shows the `run_data` for a completed execution. Two views:
- **Node summary**: table of node id → status → execution_time_ms.
- **Node output**: collapsible JSON tree for each node's `data.main` output.
  Use a simple recursive JSON renderer or `react-json-view`.

When an execution is selected, the Editor tab can also use this data to overlay
per-node status on the canvas (green border = success, red = error, grey =
skipped).

---

## 7. Implementation sequence

### Step 1 — FastAPI gap (30 min)
Add `DELETE /v0/orgs/{org_id}/flows/{flow_id}` to `flows.py`.

### Step 2 — TypeScript SDK (2 h)
1. Create `types/flows.ts` with all types from §2.1.
2. Re-export from `types/index.ts`.
3. Add flow methods to `docrouter-org.ts` (§2.2).
4. Build and verify `npm run build` in the SDK package.

### Step 3 — Phase 1 UI (1 day)
1. `FlowList.tsx` + `FlowCreate.tsx` + `FlowStatusBadge.tsx`.
2. `flows/page.tsx` tab container.
3. `useFlowApi.ts` hook.
4. Add "Flows" to the org sidebar.
5. Verify list, create, rename, delete, activate, run all work end-to-end.

### Step 4 — Phase 2 UI: canvas (2–3 days)
1. `revisionToRF` / `rfToRevision` helpers (no React, pure functions — test
   them independently).
   - Add unit tests that round-trip `FlowRevision → (RF nodes/edges) → SaveRevisionParams`
     and cover edge cases (multi-output, fan-out, multi-input merge, sparse slots).
2. `FlowNodePalette.tsx`.
3. `FlowEditor.tsx` with React Flow canvas, drag-and-drop, edge drawing.
4. `FlowNodeConfigPanel.tsx` with Monaco for code nodes.
5. `FlowToolbar.tsx` with save / run / activate.
6. `flows/[flowId]/page.tsx` wiring it together.

### Step 5 — Phase 3 UI: executions (1 day)
1. `useExecutionPoller.ts`.
2. `FlowExecutionList.tsx` with polling.
3. `FlowExecutionDetail.tsx` with run_data tree.
4. Per-node status overlay on the canvas.

---

## 8. Key implementation notes

**`base_flow_revid` on save**: The `PUT` route requires the client to pass the
current latest revision id as `base_flow_revid` so the server can detect
concurrent edits (409 if another save happened first). The editor must track
the last-saved `flow_revid` and pass it on every save.

**New flow with no revisions**: When `createFlow` returns, the flow has no
revisions and `latest_revision` is `null`. The editor must handle this: start
with an empty canvas (just the manual trigger node pre-placed), and pass `""`
or `"new"` as `base_flow_revid`. The server accepts this when there are no
existing revisions (`latest` is `None`).

**React Flow coordinate system**: positions are in canvas pixels. Store them
in `FlowNode.position` and round to integers before saving to keep the revision
JSON stable.

**Edge index semantics**: a React Flow edge from node A output 0 to node B
input slot 1 maps to a `NodeConnection` with `dest_node_id=B.id`, `index=1`,
in `connections["A"]["main"][0]`. The output slot index is the position of the
source handle in the `connections[src]["main"]` array; the `index` field on
the connection is the destination input slot. These must match the `outputs`
and `max_inputs` declared by the node types.

**Monaco for code nodes**: use `@monaco-editor/react` (already in
`package.json`). The language for `python_code` parameters is `"python"`;
for `js_code` → `"javascript"`; for `ts_code` → `"typescript"`. Height should
be `300px` by default with a vertical resize handle.

**No SSE / WebSocket**: the server only supports polling. The `useExecutionPoller`
hook is sufficient. Poll interval: 2 s during active execution, stop when
terminal status is reached.
