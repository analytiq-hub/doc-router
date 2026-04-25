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
| `DELETE /v0/orgs/{org_id}/flows/{flow_id}` | ✓ |

FastAPI route coverage is complete for v1.

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

## 3. Frontend — file layout (current)

The flows UI is implemented and wired into the org sidebar. The app uses App
Router pages under `src/app/` plus `src/components/flows/` building blocks.

```
src/app/orgs/[organizationId]/
  flows/
    page.tsx                                Flow list page (tabs: flows | flow-create)
    [flowId]/
      page.tsx                              Server wrapper → FlowDetailPageClient
      FlowDetailPageClient.tsx              Client page: editor + executions tabs, load/save/run/activate

src/components/flows/
  FlowList.tsx                              List flows (edit/run/activate/deactivate/delete) + pagination
  FlowCreate.tsx                            Create flow (name only) → navigates to editor
  FlowStatusBadge.tsx                       Active/inactive badge
  useFlowApi.ts                             Hook creating `DocRouterOrgApi`

  FlowCanvasViewTabs.tsx                    Editor / Executions tab switcher
  FlowToolbar.tsx                           Inline rename + Save / Execute / Activate / Deactivate
  FlowEditor.tsx                            React Flow canvas (D&D nodes, connect edges, insert-on-edge)
  FlowNodePalette.tsx                       Node type palette (search, grouped by category, draggable)
  FlowNodeConfigModal.tsx                   Node settings modal (incl. read-only mode in executions view)
  flowNodeConfigFields.tsx                  Parameter schema → form/Monaco field renderers

  FlowCanvasNode.tsx                        Custom RF node renderer (trigger + process shapes, toolbars)
  FlowCanvasEdge.tsx                        Custom edge renderer (labels + inline insert/delete affordances)
  flowRfCanvasTypes.ts                      RF nodeTypes/edgeTypes registration
  flowCanvasActionsContext.tsx              Canvas actions + execution visual contexts

  FlowExecutionsView.tsx                    Executions tab (list + read-only graph view + per-node status)
  FlowExecutionList.tsx                     Alternate executions table w/ inline JSON (currently unused)
  FlowLogsPanel.tsx                         Bottom logs panel (polls getExecution; node IO previews)

  canvasGrid.ts                             Grid snap helpers
  flows-canvas.css                          Canvas styling
  flowNodeRunStatus.ts                      Run-data → per-node status mapping helpers
  flowNodeIoPreview.ts                      Build per-node input/output previews from run_data + edges
  flowUiClasses.ts                          Shared class strings
  useInlineNameWidthPx.ts                   Inline name sizing helper
```

---

## 4. Phase 1 — Flow list and management (implemented)

**Goal**: list, create, rename, delete, activate, deactivate, and manually run
flows without a graph editor.

### 4.1 `flows/page.tsx` (done)

Tab bar with "Flows" and "Create Flow" tabs, using `useSearchParams` for tab
state in the URL.

```tsx
'use client'
export default function FlowsPage({ params }) {
  const { organizationId } = use(params);
  // tab: 'flows' | 'flow-create'
  return (
    <div className="p-4">
      {/* tab bar */}
      <div role="tabpanel">
        {tab === 'flows' && <FlowList organizationId={organizationId} />}
        {tab === 'flow-create' && <FlowCreate organizationId={organizationId} />}
      </div>
    </div>
  );
}
```

### 4.2 `FlowList.tsx` (done)

Table columns: Name, Status (active badge), Version, Last updated, Actions.

Actions per row:
- **Edit** → navigate to `/orgs/{org}/flows/{flowId}`
- **Run** → calls `runFlow` and reloads the list
- **Activate / Deactivate** → toggles activation
- **Delete** → confirmation dialog, then `deleteFlow`

Pagination: `limit=20`, offset-based, same pattern as `PromptList`.

### 4.3 `FlowCreate.tsx` (done)

Single text field for name. On submit calls `createFlow`, then navigates to
`/orgs/{org}/flows/{flowId}` so the user lands in the editor.

### 4.4 Sidebar navigation entry (done)

Added to the org sidebar (`src/components/Layout.tsx`). Route:
`/orgs/{organizationId}/flows`.

---

## 5. Phase 2 — Graph editor (implemented)

**Goal**: a visual canvas where users can build, edit, and save flow graphs.

### 5.1 `flows/[flowId]/page.tsx` (done)

Two-tab layout: **Editor** and **Executions** (query param `tab=editor|executions`).

On mount (`FlowDetailPageClient.tsx`):
1. Load `getFlow(flowId)` and `listFlowNodeTypes()` in parallel.
2. If there is a latest revision, load `getRevision(flowId, latestRevisionId)` and populate canvas.
3. If there is no revision yet, start with a blank revision containing a trigger node.

### 5.2 `FlowEditor.tsx` (done)

Built on `reactflow` (already in `package.json` at `^11.11.4`).

```
┌─────────────────────────────────────────────────────────┐
│  FlowToolbar (save | execute | activate | status badge) │
├─────────────────────────────────────────────────────────┤
│  React Flow canvas (nodes + edges)                      │
│  - Right-side buttons: add/search palette               │
│  - Bottom: zoom controls + “Execute workflow”           │
├─────────────────────────────────────────────────────────┤
│  FlowLogsPanel (collapsible)                            │
└─────────────────────────────────────────────────────────┘

Palette and node configuration are modal/drawer based:
- Node palette opens as a right-side drawer.
- Node configuration opens as `FlowNodeConfigModal` (double-click node).
```

State is hosted by `FlowDetailPageClient.tsx` (nodes/edges/revision/name/active,
dirty fingerprinting). `FlowEditor.tsx` is a controlled component.

**Conversion between engine and React Flow formats (done, moved to SDK):**

The engine stores `nodes[]` + `connections` (source-keyed dict). React Flow uses
`nodes[]` + `edges[]`. The round-trip helpers live in the TypeScript SDK now:

```typescript
revisionToRF(revision: FlowRevision, nodeTypesByKey?: Record<string, FlowNodeType>): { nodes; edges }
rfToRevision(rfNodes: FlowRfNode[], rfEdges: FlowRfEdge[], current: FlowRevision, name: string): SaveRevisionParams
revisionContentFingerprint(...)
```

Unit tests: `packages/typescript/sdk/tests/unit/flow-rf.test.ts`.

**Adding nodes (done)**:
- Drag from `FlowNodePalette` onto the canvas (HTML D&D + `onDrop`).
- Also supported: open palette drawer and double-click a node type to insert at view center.

**Connecting nodes (done)**: `onConnect` validates source output index and
destination input index against node type bounds. Invalid connections are
rejected (no edge added).

**Insert node on edge (done)**: edges expose an “insert” flow that opens the
palette; the chosen node type is inserted inline and rewires source → new → target.

**Deleting nodes/edges (done)**: node toolbars and edge controls call back into
the parent via `flowCanvasActionsContext.tsx`.

### 5.3 `FlowNodePalette.tsx` (done)

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

### 5.4 Node configuration UI (done, modal-based)

The editor uses `FlowNodeConfigModal.tsx` (not a right sidebar panel). It shows
editable node settings driven by the node type’s `parameter_schema` and supports
a `readOnly` mode (used by the executions view).

Parameter form rendering rules:
- `string` with key `python_code` or `js_code` or `ts_code` → Monaco Editor
  (already in `package.json` at `^4.6.0`) with the appropriate language mode.
- `string` → `<TextField>`
- `number` → `<TextField type="number">`
- `boolean` → `<Switch>`
- `object` / `array` → Monaco Editor in JSON mode.

Also supports:
- Node name (editable, must be unique within the flow)
- `disabled` toggle
- `on_error` select (`stop` / `continue`)

Changes apply to local state immediately; Save persists a new revision.

### 5.5 `FlowToolbar.tsx` (done)

```
[flow name]  [active badge]   |  [Save]  [Run]  [Activate / Deactivate]
```

**Save**: calls `saveRevision`. Passes current `latest_revision.flow_revid` as
`base_flow_revid`. On 409 (concurrent edit), shows an error toast.

**Run**: calls `runFlow`; the page focuses the returned execution id in the logs panel.

**Activate**: calls `activateFlow` (uses the latest saved revision). Disabled
if there are unsaved changes (`isDirty`).

**Deactivate**: calls `deactivateFlow` with a confirmation dialog.

### 5.6 Custom React Flow renderers (done)

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

### 5.7 Execution polling + status overlay (done, no dedicated hook)

Polling is implemented inside `FlowLogsPanel.tsx` (2s while `queued|running`)
and inside `FlowExecutionsView.tsx` (3s list refresh while any run is active).
Per-node badges/overlays use `flowNodeRunStatus.ts`.

---

## 6. Phase 3 — Execution history tab (implemented)

### 6.1 Executions tab (done)

The page uses `FlowExecutionsView.tsx` (sidebar list + read-only graph view +
node modal). It auto-refreshes the list when there are active runs.

`FlowExecutionList.tsx` exists as an alternate executions table with inline JSON
detail and a Stop button; it is currently not used by the page.

### 6.2 Logs panel (done)

`FlowLogsPanel.tsx` provides an in-editor logs view with per-node input/output
previews derived from `run_data` and the current graph wiring.

---

## 7. Implementation sequence

This section is kept as a dependency chain, but updated to reflect what exists
in the codebase today.

### Step 1 — FastAPI routes (done)
FastAPI route coverage is complete for v1 (incl. delete).

### Step 2 — TypeScript SDK flows + RF helpers (done)
- `packages/typescript/sdk/src/types/flows.ts`
- `packages/typescript/sdk/src/docrouter-org.ts` flows methods
- `packages/typescript/sdk/src/flow-rf.ts` (`revisionToRF`, `rfToRevision`, etc.)
- Unit tests: `packages/typescript/sdk/tests/unit/flow-rf.test.ts`

### Step 3 — Phase 1 UI: list + create + sidebar (done)
- `flows/page.tsx`, `FlowList.tsx`, `FlowCreate.tsx`, `FlowStatusBadge.tsx`, `useFlowApi.ts`
- Org sidebar entry in `src/components/Layout.tsx`

### Step 4 — Phase 2 UI: editor canvas (done)
- `flows/[flowId]/page.tsx` + `FlowDetailPageClient.tsx` wiring
- `FlowEditor.tsx` (React Flow canvas), `FlowNodePalette.tsx`, `FlowToolbar.tsx`
- Custom node/edge renderers: `FlowCanvasNode.tsx`, `FlowCanvasEdge.tsx`
- Node configuration modal: `FlowNodeConfigModal.tsx` + schema-driven fields
- Insert-on-edge and node/edge actions via `flowCanvasActionsContext.tsx`

### Step 5 — Phase 3 UI: executions + logs (done)
- Executions tab: `FlowExecutionsView.tsx` (list + read-only graph + node modal)
- In-editor logs: `FlowLogsPanel.tsx` (polling + IO previews)

### Remaining gaps / follow-ups (as of now)
1. **Decide on one executions UI**: keep `FlowExecutionsView.tsx` and remove or repurpose the unused `FlowExecutionList.tsx`.
2. **Stop execution from executions view**: `FlowExecutionsView.tsx` currently doesn’t expose Stop; `FlowExecutionList.tsx` does.
3. **Rename flow from list**: list page supports edit/run/activate/delete, but not rename inline (rename is in editor toolbar).
4. **Polish run UX**: after `runFlow`, optionally auto-switch to the Executions tab (currently it focuses the logs panel).

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

**No SSE / WebSocket**: the server only supports polling. Polling is implemented
in `FlowLogsPanel.tsx` (2s while `queued|running`) and `FlowExecutionsView.tsx`
(3s list refresh while any run is active).
