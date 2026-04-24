# n8n Editor-UI Reference

Frontend architecture of the n8n workflow editor, organized as a porting guide
for DocRouter's flows UI. All paths are relative to
`n8n/packages/editor-ui/src/` unless noted otherwise.

**Tech stack**: Vue 3 (Composition API) · Pinia stores · Vue Router ·
Vue Flow (`@vue-flow/core`) · Monaco Editor · Axios

Our equivalent: React · Zustand or local state · React Router · React Flow
(`reactflow`) · Monaco Editor · Axios — most concepts map 1-to-1.

---

## Table of contents

1. [Canvas / workflow editor](#1-canvas--workflow-editor)
2. [Node design and rendering](#2-node-design-and-rendering)
3. [Node palette (add-node sidebar)](#3-node-palette-add-node-sidebar)
4. [Node configuration panel (NDV)](#4-node-configuration-panel-ndv)
5. [Execution logs and history](#5-execution-logs-and-history)
6. [Real-time push events](#6-real-time-push-events)
7. [State management](#7-state-management)
8. [Key data types](#8-key-data-types)
9. [Porting notes for DocRouter](#9-porting-notes-for-docrouter)

---

## 1. Canvas / workflow editor

### Main entry point

**`views/NodeView.vue`** (156 KB) — the outer shell. Hosts the canvas, wires
keyboard shortcuts, manages drag-drop from the palette, and dispatches save /
run / activate actions.

### Canvas component hierarchy

```
NodeView.vue
└── WorkflowCanvas.vue          wraps Vue Flow; maps engine format → canvas format
    └── Canvas.vue              Vue Flow instance; owns zoom/pan/selection
        ├── CanvasNode.vue      one node bubble (per node in the graph)
        ├── CanvasEdge.vue      one connection line (per edge)
        ├── CanvasBackground.vue  dotted grid
        └── CanvasControlButtons.vue  zoom-in / zoom-out / fit-view buttons
```

#### `Canvas.vue`

Props: `nodes`, `connections`, `readOnly`, `executing`, `eventBus`

Key emits: `update:node:position`, `create:connection`, `run:workflow`,
`update:modelValue`

Uses `VueFlow` from `@vue-flow/core`. Binds `CanvasNode` and `CanvasEdge` as
custom node/edge types. Handles keyboard bindings (delete selected,
ctrl+z undo) and the canvas context menu.

#### `WorkflowCanvas.vue`

Bridges the engine's `IWorkflow` format and Vue Flow's `nodes[]` + `edges[]`
arrays via the `useCanvasMapping` composable. Also handles zoom-to-fit on first
load and "fallback" placeholder nodes.

Props: `workflow`, `workflowObject`, `readOnly`, `executing`

### Canvas composables

| Composable | File | Purpose |
|---|---|---|
| `useCanvasOperations` | `composables/useCanvasOperations.ts` | Add / remove / duplicate / move nodes; create / delete connections; copy-paste |
| `useCanvasMapping` | `composables/useCanvasMapping.ts` | Convert `IWorkflow → { nodes, edges }` for Vue Flow; inverse for saves |
| `useCanvasPanning` | `composables/useCanvasPanning.ts` | Wheel zoom, middle-mouse pan |
| `useCanvasMouseSelect` | `composables/useCanvasMouseSelect.ts` | Rubber-band (rectangle) selection |
| `useCanvasTraversal` | `composables/useCanvasTraversal.ts` | Find up/downstream nodes; used for partial re-runs |

### History (undo / redo)

**`stores/history.store.ts`** — Pinia store. Commands are classes:

| Command | Payload |
|---|---|
| `AddNodeCommand` | new `INode` |
| `RemoveNodeCommand` | removed `INode` |
| `RenameNodeCommand` | old name, new name |
| `MoveNodeCommand` | node id, old pos, new pos |
| `AddConnectionCommand` | `IConnection` |
| `RemoveConnectionCommand` | `IConnection` |

Every mutating canvas operation pushes a command; ctrl+z pops and reverses it.

---

## 2. Node design and rendering

### Node component tree

```
CanvasNode.vue              outer wrapper (toolbar, context menu, selection border)
└── CanvasNodeRenderer.vue  picks the render component by node type
    ├── CanvasNodeDefault.vue     standard process node
    ├── CanvasNodeStickyNote.vue  sticky note
    └── CanvasNodeAddNodes.vue    the "+" ghost node shown at the end of a chain
```

#### `CanvasNode.vue`

Props: `selected`, `data: CanvasNodeData`, `hovered`, `readOnly`

Emits: `add`, `delete`, `run`, `select`, `toggle`, `activate`,
`open:contextmenu`, `update`, `move`

Renders a node toolbar on hover (run this node, open config, delete). Wraps the
render component in a selection border and handles the context-menu trigger.

#### `CanvasNodeDefault.vue`

The standard bubble. Shows:
- Node type icon (loaded from `n8n-design-system`)
- Node name (bold)
- Execution status overlay (spinner / green-check / red-x)
- Pinned-data indicator
- Error count badge

#### Connection handles — `CanvasHandleRenderer.vue`

Renders the input (left) and output (right) connection points. Handle shapes
differ by type:

| Handle type | Shape | Used for |
|---|---|---|
| Main input/output | Circle | Normal data flow |
| Non-main input | Diamond | AI sub-connections (tools, embeddings, …) |
| Plus | `+` button | Shortcut to add next node |

Props: `inputs`, `outputs`, `mainInputs`, `mainOutputs`, `nonMainInputs`,
`nonMainOutputs`

### Edge rendering

**`CanvasEdge.vue`** — SVG cubic bezier. Props: `data: CanvasConnectionData`,
`source`, `target`, `selected`.

Edge status colours:

| `data.status` | Colour |
|---|---|
| `'success'` | green |
| `'error'` | red |
| `'pinned'` | yellow |
| `'running'` | animated blue |

**`CanvasEdgeToolbar.vue`** — delete button shown on edge hover.

---

## 3. Node palette (add-node sidebar)

### Component hierarchy

```
NodeCreator.vue             slide-in panel; keyboard navigation; scrim overlay
└── NodesListPanel.vue      main panel: search bar + categorised node list
    ├── SearchBar.vue        debounced text input
    ├── CategorizedItemsRenderer.vue  grouped node/subcategory rendering
    │   └── ItemsRenderer.vue         flat item list
    │       ├── NodeItem.vue          individual node card
    │       ├── CategoryItem.vue      category header
    │       └── SubcategoryItem.vue   subcategory row
    └── NoResults.vue        empty state
```

All files under `components/Node/NodeCreator/`.

### View stack navigation

The palette uses a **stacked view** model (breadcrumb-style drill-down):
- Root view: full category tree
- Click a category → push `subcategoryView` onto the stack
- Click a node → emit `nodeTypeSelected`; panel closes

Managed by the `useViewStacks` composable inside the `nodeCreator.store.ts`
Pinia store.

### Drag and drop

Each `NodeItem` sets `draggable` and on `dragstart` writes the node type key
into `dataTransfer` with the key `DRAG_EVENT_DATA_KEY` (a string constant).

`NodeView.vue`'s `onDrop` handler:
1. Reads the key from `dataTransfer`.
2. Translates the drop coordinates from viewport to canvas space.
3. Calls `useCanvasOperations.addNode(type, position)`.

### Search and ordering

`SearchBar` emits a debounced string. `useNodeCreatorStore` filters
`mergedNodes` (all node types) by name, description, and tags. `OrderSwitcher`
toggles between alphabetical and "recommended" (usage-frequency) ordering.

---

## 4. Node configuration panel (NDV)

NDV = "Node Details View". Opens when a node is double-clicked or its config
button is pressed.

### Panel layout

```
NodeDetailsView.vue
├── NDVFloatingNodes.vue        floating node-icon badges around the panel edges (prev/next navigation)
├── NDVDraggablePanels.vue      three resizable columns
│   ├── InputPanel.vue          left:  input data for the current run
│   │   └── InputNodeSelect.vue   dropdown to pick which upstream node to display
│   ├── NodeSettings.vue        center: parameter form
│   │   └── NDVSubConnections.vue  list of non-main connected nodes (AI tools, etc.)
│   └── OutputPanel.vue         right: execution output
└── TriggerPanel.vue            replaces InputPanel for trigger nodes
```

### Floating node navigation — `NDVFloatingNodes.vue`

This is the **prev / next node** feature the user sees around the node popup.
The component renders small clickable node-icon badges positioned at three edges
of the NDV panel:

| Position | CSS class | Nodes shown | Direction |
|---|---|---|---|
| Left edge | `inputMain` | Direct main-input parents (one icon per connected upstream node) | ← prev |
| Right edge | `outputMain` | Direct main-output children (one icon per connected downstream node) | → next |
| Top edge | `outputSub` | Non-main child nodes (AI tools, embeddings, vector stores, …) | ↑ sub |

Clicking any badge emits `switchSelectedNode(nodeName)`, which bubbles up to
`NodeView` and re-opens the NDV for that node. Keyboard shortcut: `Shift+Alt+Cmd/Ctrl+Arrow`.

For a node with multiple outputs (fan-out), **one badge per downstream node**
appears on the right edge. For a multi-input merge node, **one badge per
upstream node** appears on the left edge. So "one per input and one per output"
is literal.

```typescript
// NDVFloatingNodes.vue — connectedNodes computed
const connectedNodes = {
  inputMain:  workflow.getParentNodes(rootNode.name, 'main', depth=1),  // prev
  outputMain: workflow.getChildNodes(rootNode.name,  'main', depth=1),  // next
  outputSub:  workflow.getChildNodes(rootNode.name,  'ALL_NON_MAIN'),   // sub
};
```

`switchSelectedNode` event chain:
`NDVFloatingNodes → NodeSettings → NDVDraggablePanels → NodeDetailsView → NodeView`

NodeView handles it by calling `ndvStore.setActiveNodeName(name)`.

### Input node selector — `InputNodeSelect.vue`

Within `InputPanel`, a `<select>` dropdown lets the user choose **which
upstream node's output** to display as the current node's input data. The list
is populated by `workflow.getParentNodesByDepth(activeNode.name)` — all
ancestors at any depth, not just direct parents.

Each option shows:
- Node type icon
- Node name (truncated)
- Subtitle: which input slot it connects to, or how many hops away it is

For multi-input nodes, the subtitle shows the input slot name (e.g. "Input 1 &
Input 2") when a node is wired to multiple slots simultaneously.

The current selection is stored as `currentNodeName` (a parent node name) in
`InputPanel` state. Changing the dropdown re-renders `RunData` with that
ancestor's `runData` output.

### Parameter form — `NodeSettings.vue`

Receives the selected `INode` and its `INodeTypeDescription`. Renders
`ParameterInputList`, which walks the type's `properties[]` array and emits
`valueChanged` for each edit.

Prop: `nodeType: INodeTypeDescription`
Emit: `valueChanged`

### Parameter input components

| Component | When used |
|---|---|
| `ParameterInputList.vue` | top-level list; groups params by displayOptions |
| `ParameterInput.vue` | one parameter; dispatches to a typed sub-input |
| `ParameterInputWrapper.vue` | adds label, hint text, and validation errors |
| `CollectionParameter.vue` | `type: 'collection'` — nested key/value |
| `FixedCollectionParameter.vue` | `type: 'fixedCollection'` — fixed-key groups |
| `MultipleParameter.vue` | `type[]` — repeatable rows |
| `ExpressionParameterInput.vue` | expression (`={{ … }}`) mode |
| `ParameterIssues.vue` | inline validation error list |

Specialised editors (opened in a drawer/modal):

| Editor | Trigger |
|---|---|
| `CodeNodeEditor/` | parameter with `typeOptions.editor: 'codeNodeEditor'` |
| `JsonEditor/` | parameter with `type: 'json'` |
| `SqlEditor/` | parameter with `typeOptions.editor: 'sqlEditor'` |
| `HtmlEditor/` | parameter with `typeOptions.editor: 'htmlEditor'` |
| `ResourceLocator/` | parameter with `type: 'resourceLocator'` |

All code editors use **Monaco Editor**.

### Input / Output panels

**`InputPanel.vue`** — shows `runData[prevNode][runIndex]` items for the
currently selected node's input slot.

**`OutputPanel.vue`** — shows `runData[selectedNode][runIndex]` items. Has two
modes: `regular` (data output) and `logs` (execution log lines for code nodes).

Both share the **`RunData.vue`** component for data rendering.

The full set of display modes (type `IRunDataDisplayMode` in `Interface.ts`):

```typescript
type IRunDataDisplayMode = 'table' | 'json' | 'binary' | 'schema' | 'html' | 'ai';
```

`RunData` automatically selects the initial mode: if the run data contains any
binary entries it switches to `'binary'`; otherwise it defaults to `'table'`.
The user can toggle freely between all modes using a tab bar at the top of the
panel.

`RunDataSearch.vue` adds a cross-item text search that works in all modes.

---

### Display mode: Table (`RunDataTable.vue`)

**Component**: `components/RunDataTable.vue` (lazy loaded)

**What it shows**: one row per `INodeExecutionData` item, one column per
top-level key of `item.json`. Columns are discovered dynamically by union-ing
all keys across all items (sparse rows get `undefined` for missing columns).

**`convertToTable` algorithm** (inside `RunDataTable.vue`):
1. Walk every item's `json` object and collect all unique top-level keys as
   `tableColumns`.
2. For each item, produce a row array aligned to `tableColumns`. Missing keys
   become `undefined`.
3. Track `hasJson[column]` — if any cell is a nested object, that column gets an
   expand icon; clicking opens a JSON tree inline.
4. A hard cap of `MAX_COLUMNS_LIMIT = 40` columns is enforced; if exceeded a
   warning is shown.

**`ITableData` shape**:
```typescript
interface ITableData {
  columns:  string[];          // ordered column names
  data:     GenericValue[][];  // rows × columns, sparse (undefined for missing)
  hasJson:  { [column: string]: boolean };  // which columns have nested objects
  metadata: {
    hasExecutionIds: boolean;
    data: Array<INodeExecutionData['metadata'] | undefined>;
  };
}
```

The metadata field enables a "view sub-execution" link column when items carry
a `metadata.subExecution` reference (used by Execute Workflow nodes).

Table cells support **drag-to-expression**: dragging a cell emits a
`MappingPill` that drops into a parameter input field as `{{ $json.fieldName }}`.

---

### Display mode: JSON (`RunDataJson.vue`)

**Component**: `components/RunDataJson.vue` (lazy loaded)

**What it shows**: the raw `item.json` object for the selected item index, rendered
as a collapsible tree using `vue-json-pretty` (or a similar library). Each node
in the tree is drag-able to parameter inputs for expression mapping.

**Data path**: `runData[nodeName][runIndex].data.main[outputIndex][itemIndex].json`

A pagination bar under the tree lets the user page through items
(`currentPage`, `pageSize` — default 10 items per page).

---

### Display mode: Schema (`VirtualSchema.vue`)

**Component**: `components/VirtualSchema.vue` (lazy loaded)

**What it shows**: a structural type tree — the shape of the data without the
actual values. Useful for understanding a node's output contract without needing
a live run.

**How the schema is built** (`composables/useDataSchema.ts → getSchema`):

```typescript
// Merges all items first, then walks the merged object recursively
function getSchemaForExecutionData(data: IDataObject[]): Schema {
  const merged = merge({}, ...data);  // lodash deep-merge all items
  return getSchema(merged);           // recursive type inference
}
```

`getSchema` is a recursive function that walks the merged object and returns a
`Schema` node:

```typescript
type Schema =
  | { type: 'object';    value: Array<{ key: string } & Schema>; path: string }
  | { type: 'array';     value: Array<{ key: string } & Schema>; path: string }
  | { type: 'string' | 'number' | 'boolean'; value: string; path: string }
  | { type: 'null';      value: '[null]'; path: string }
  | { type: 'undefined'; value: 'undefined'; path: string }
```

The resulting tree is then **flattened** into a virtual list
(`flattenSchema`) so it can be rendered efficiently with a virtual scroller,
with each row knowing its depth and whether it is collapsed.

Schema nodes are drag-able to parameter inputs exactly like JSON mode cells.

---

### Display mode: Binary (`BinaryDataDisplay.vue` / `BinaryDataDisplayEmbed.vue`)

**What it is**: the binary display mode replaces the data panels entirely when
node output contains `INodeExecutionData.binary` entries. It renders one card
per item that contains binary keys, each showing metadata and action buttons.

**`IBinaryData` type** (from `packages/workflow/src/Interfaces.ts`):

```typescript
type BinaryFileType = 'text' | 'json' | 'image' | 'audio' | 'video' | 'pdf' | 'html';

interface IBinaryData {
  [key: string]: string | number | undefined;  // index signature
  data:           string;   // base64 payload (in-memory) or storage mode tag (external)
  mimeType:       string;   // e.g. 'image/png', 'application/pdf'
  fileType?:      BinaryFileType;
  fileName?:      string;
  directory?:     string;
  fileExtension?: string;
  fileSize?:      string;   // human-readable, e.g. '1.2 MB'
  id?:            string;   // present when stored externally; absent when in-memory
}
```

`IBinaryKeyData` is the per-item envelope:
```typescript
interface IBinaryKeyData {
  [propertyName: string]: IBinaryData;   // e.g. { data: IBinaryData, thumbnail: IBinaryData }
}
```

A node's output item can thus carry **multiple named binary attachments**
(`data`, `thumbnail`, `screenshot`, …).

**Two storage strategies** (controlled by `N8N_DEFAULT_BINARY_DATA_MODE`):

| Mode | `data` field | `id` field | How to retrieve |
|---|---|---|---|
| `'default'` (in-memory) | base64-encoded bytes | absent | `atob(data)` directly in browser |
| `'filesystem'` or `'filesystem-v2'` | the string `"filesystem"` | `"filesystem:<fileId>"` | fetch from `GET /rest/binary-data?id=…` |
| `'s3'` | the string `"s3"` | `"s3:<fileId>"` | same endpoint, streams from S3 |

When `id` is present, `data` is just the mode name (not actual bytes). The
frontend always checks `id` first.

**REST endpoint** (`packages/cli/src/controllers/binary-data.controller.ts`):

```
GET /rest/binary-data
  ?id=<binaryDataId>         required; format "<mode>:<fileId>"
  ?action=view|download      view sets no Content-Disposition; download sets attachment
  ?fileName=<name>           optional; used in Content-Disposition header
  ?mimeType=<type>           optional; sets Content-Type header

Response: binary stream (Content-Type from mimeType or metadata lookup)
```

Note: this endpoint is **excluded from session auth** (no cookie check) so that
`<embed>` and `<img>` tags can load it directly from the browser without needing
custom headers.

**URL construction** (`workflows.store.ts → getBinaryUrl`):

```typescript
function getBinaryUrl(id: string, action: 'view'|'download', fileName: string, mimeType: string): string {
  const url = new URL(`${restUrl}/binary-data`);
  url.searchParams.append('id', id);
  url.searchParams.append('action', action);
  if (fileName) url.searchParams.append('fileName', fileName);
  if (mimeType) url.searchParams.append('mimeType', mimeType);
  return url.toString();
}
```

**Rendering by file type** (`BinaryDataDisplayEmbed.vue`):

| `fileType` | Element | Notes |
|---|---|---|
| `'image'` | `<img src="...">` | URL is `getBinaryUrl(id, 'view', …)` |
| `'video'` | `<video><source></video>` | autoplay |
| `'audio'` | `<audio><source></audio>` | autoplay |
| `'pdf'` | `<embed>` | fills panel |
| `'json'` | `VueJsonPretty` | fetches text, parses JSON, renders tree |
| `'html'` | `RunDataHtml.vue` | fetches text, renders in sandboxed iframe |
| `'text'` | `<embed>` | raw text via URL |
| other / absent | `<embed class="other">` | browser handles it |

For **in-memory** data (no `id`): JSON/HTML are decoded via `atob(data)` and
rendered inline. Others are rendered as `data:<mimeType>;base64,<data>` data
URIs — no HTTP round-trip needed.

For **external** data (`id` present): JSON/HTML are fetched via `fetch(binaryUrl)`;
images/video/audio/PDF/other use the URL directly as `<img src>` / `<embed src>`.

**Action buttons** (shown in the binary card before the viewer):

| Button | `isViewable` condition | Action |
|---|---|---|
| View | `fileType` is one of the 7 types above | Opens `BinaryDataDisplay` full-panel viewer |
| Download | `mimeType && fileName` both present | `saveAs(getBinaryUrl(id, 'download', …))` or blob from base64 |

---

### NDV state — `stores/ndv.store.ts`

Key state:

| Field | Type | Purpose |
|---|---|---|
| `activeNodeName` | `string \| null` | Which node is open |
| `inputPanelDisplayMode` | `'table' \| 'json' \| 'schema'` | Left panel mode |
| `outputPanelDisplayMode` | same | Right panel mode |
| `mainPanelDimensions` | `{ relativeLeft, relativeRight, relativeWidth }` | Panel sizes |
| `hoveringItem` | `{ itemIndex, node, outputIndex }` | Paired-item highlight |
| `expressionOutputItemIndex` | `number` | Which item to evaluate expressions against |

---

## 5. Execution logs and history

### Executions view structure

```
ExecutionsView.vue            route: /workflow/:id/executions
└── WorkflowExecutionsList.vue
    ├── WorkflowExecutionsSidebar.vue   left panel: scrollable list of cards
    │   ├── ExecutionsFilter.vue        status / date / tag filters
    │   └── WorkflowExecutionsCard.vue  one row per execution
    └── WorkflowExecutionsPreview.vue   right panel: full execution detail
```

All files under `components/executions/workflow/`.

### `WorkflowExecutionsSidebar.vue`

Props: `workflow`, `executions`, `loading`, `loadingMore`, `temporaryExecution`

- Renders `WorkflowExecutionsCard` for each execution.
- Auto-scrolls to the active (running) execution.
- **Auto-refresh**: polls `listExecutions` every 4 seconds when any execution
  is in a non-terminal state. Configurable via `autoRefreshDelay`.

### `WorkflowExecutionsCard.vue`

One execution summary row. Displays:
- Status icon (spinner / green-check / red-x)
- Human-readable timestamp ("2 minutes ago")
- Duration
- Error message excerpt (if failed)
- Trigger mode label

Clicking a card sets `executions.store.activeExecution` and shows the preview.

### `ExecutionsFilter.vue`

Filter controls: status (running / success / error / waiting), date range,
workflow tags. Emits `update:filters`. The parent re-fetches from the API on
every change.

### `WorkflowExecutionsPreview.vue`

Shows a read-only canvas overlay of the selected execution. Nodes are coloured
by their per-node `executionStatus` in `runData`. Panel buttons:

- **Delete** — `deleteExecution()`
- **Retry** — `retryExecution()`
- **Stop** — `stopExecution()` (only when running)
- **Debug** — re-open editor in debug mode (partial re-run from a breakpoint)

Enterprise edition adds an annotation panel (`WorkflowExecutionAnnotationPanel.ee.vue`)
for tagging and voting on executions.

### Global executions list (all workflows)

`components/executions/global/GlobalExecutionsList.vue` — same card/filter
pattern but includes the workflow name column and spans all workflows.

### Execution data rendering — `RunData.vue`

The same component used in OutputPanel is also used in the execution preview to
show per-node output data. The execution detail just passes a read-only `runData`
object instead of live execution data.

Key props:
- `workflow` — the workflow definition (to look up node names)
- `runIndex` — which run attempt (for nodes that ran multiple times)
- `node` — the selected node name
- `paneType` — `'input'` or `'output'`

Errors are rendered by `NodeErrorView.vue` inside `RunData`.

### Executions store — `stores/executions.store.ts`

| Field | Type | Purpose |
|---|---|---|
| `activeExecution` | `ExecutionSummary \| null` | Currently selected in the sidebar |
| `executionsById` | `Map<string, ExecutionSummary>` | Cache |
| `filters` | `ExecutionFilterType` | Status, date, tags |
| `autoRefresh` | `boolean` | Toggle sidebar polling |
| `autoRefreshDelay` | `number` | Default 4000 ms |

Key methods: `fetchExecutions(filters, cursor)`, `deleteExecution(id)`,
`retryExecution(id)`, `stopExecution(id)`, `getActiveExecution()`.

### Execution API — `api/workflows.ts`

| Method | Purpose |
|---|---|
| `getExecutions(filters, limit, cursor)` | paginated list |
| `getExecutionData(id)` | full execution with `runData` |
| `getActiveExecutions()` | currently running |
| `deleteExecution(id)` | delete |
| `stopExecution(id)` | stop running |
| `retryExecution(id, loadWorkflow)` | retry failed |

---

## 6. Real-time push events

### Push connection

The frontend opens a persistent connection to `/push?pushRef=<uuid>` (WebSocket
or SSE, configurable). The server streams execution lifecycle events over it.

The push channel is identified by a `pushRef` UUID assigned per browser session.
When the editor launches an execution via `POST /rest/workflows/{id}/run`, it
sends its `pushRef` so the backend knows where to stream events.

### Event types (from `@n8n/api-types/src/push/`)

| Event type | When | Payload |
|---|---|---|
| `executionStarted` | execution begins | `{ executionId, workflowId }` |
| `nodeExecuteBefore` | before a node runs | `{ nodeName }` |
| `nodeExecuteAfter` | after a node completes | `{ nodeName, data: ITaskData }` |
| `executionFinished` | execution ends | `{ executionId, data: IRun }` |
| `executionProgress` | incremental progress | `{ executionId }` |

### Frontend handling

The `NodeView` subscribes to the push channel via a composable / event bus.
On `nodeExecuteAfter`, it updates `runData[nodeName]` in the workflow store so
the canvas and NDV panels refresh immediately without polling.

On `executionFinished`, the execution is added to `executions.store` and the
sidebar refreshes.

**DocRouter v1 uses polling** — there is no WebSocket server. For a future
upgrade, replace `useExecutionPoller` with a WebSocket push subscription using
the same event type names.

---

## 7. State management

n8n uses **Pinia** (Vue equivalent of Zustand). The following stores are relevant
to the flows UI:

| Store | File | Owns |
|---|---|---|
| `workflowsStore` | `stores/workflows.store.ts` | All workflow data: nodes, connections, `runData`, active execution status |
| `canvasStore` | `stores/canvas.store.ts` | Canvas UI state: `isDragging`, `nodeViewScale`, JSPlumb instance |
| `ndvStore` | `stores/ndv.store.ts` | NDV open/close, panel sizes, display modes, hovering item |
| `executionsStore` | `stores/executions.store.ts` | Execution list, filters, auto-refresh |
| `nodeCreatorStore` | `stores/nodeCreator.store.ts` | Palette open/close, view stacks, search results |
| `historyStore` | `stores/history.store.ts` | Undo/redo command stack |

---

## 8. Key data types

### Canvas node data — `CanvasNodeData` (`types/canvas.ts`)

```typescript
interface CanvasNodeData {
  id: string;
  name: string;
  type: string;         // node type key
  typeVersion: number;
  disabled: boolean;
  inputs: CanvasConnectionPort[];
  outputs: CanvasConnectionPort[];
  connections: {
    inputs: INodeConnections;
    outputs: INodeConnections;
  };
  issues: { items: string[]; visible: boolean };
  pinnedData: { count: number; visible: boolean };
  execution: {
    status?: ExecutionStatus;   // 'running' | 'success' | 'error' | 'waiting'
    running: boolean;
    waiting?: string;
  };
  runData: {
    outputMap: ExecutionOutputMap;
    iterations: number;
    visible: boolean;
  };
  render: RenderConfig;         // which render component to use
}
```

### Canvas edge data — `CanvasConnectionData`

```typescript
interface CanvasConnectionData {
  source: CanvasConnectionPort;
  target: CanvasConnectionPort;
  status?: 'success' | 'error' | 'pinned' | 'running';
}
```

### Execution summary — `ExecutionSummary`

```typescript
interface ExecutionSummary {
  id: string;
  workflowId: string;
  status: ExecutionStatus;
  mode: WorkflowExecuteMode;
  startedAt: Date;
  stoppedAt?: Date;
  lastNodeExecuted?: string;
  retryOf?: string;
  retrySuccessId?: string;
  // ... annotation fields (enterprise)
}
```

### Node type description — `INodeTypeDescription`

The static schema that drives both the palette and the config panel:

```typescript
interface INodeTypeDescription {
  name: string;
  displayName: string;
  version: number | number[];
  description: string;
  group: string[];         // used for palette categorisation
  icon?: string;
  inputs: string[];        // e.g. ['main']
  outputs: string[];
  outputNames?: string[];
  properties: INodeProperties[];   // parameter schema
  credentials?: INodeCredentialDescription[];
  defaults: { name: string; color: string };
}
```

`INodeProperties` is the per-parameter descriptor: `name`, `type`, `default`,
`displayName`, `description`, `options`, `displayOptions`, `typeOptions`.

---

## 9. Porting notes for DocRouter

DocRouter already has its own flows UI under
`packages/typescript/frontend/src/components/flows/`. The table below maps each
n8n UI concept to the closest DocRouter equivalent and flags gaps.

### Canvas layer

| n8n | DocRouter | Status |
|---|---|---|
| `Canvas.vue` + `WorkflowCanvas.vue` (Vue Flow) | `FlowEditor.tsx` (React Flow) | Exists |
| `useCanvasMapping` — engine ↔ canvas conversion | `revisionToRF` / `rfToRevision` in `flowRf.ts` | Exists |
| `useCanvasOperations` — add / delete / move | Inline in `FlowEditor.tsx` | Partial; could extract |
| `useCanvasPanning` — wheel zoom | React Flow built-in | Built-in |
| History / undo | Not implemented | Gap |

### Node rendering

| n8n | DocRouter | Status |
|---|---|---|
| `CanvasNodeDefault.vue` | `FlowCanvasNode.tsx` | Exists |
| `CanvasEdge.vue` | `FlowCanvasEdge.tsx` | Exists |
| Status colour overlay (running/success/error) | `flowNodeRunStatus.ts` | Exists |
| Input/output handles by type (main vs non-main) | Single handle type only | Gap |

### Node palette

| n8n | DocRouter | Status |
|---|---|---|
| `NodeCreator.vue` slide-in panel | `FlowNodePalette.tsx` | Exists |
| Drag-and-drop onto canvas | `FlowNodePalette.tsx` | Exists |
| Category grouping | By `category` field | Exists |
| Search / filter | Not implemented | Gap |
| Keyboard navigation | Not implemented | Gap |

### Node configuration

| n8n concept | DocRouter equivalent | Status |
|---|---|---|
| NDV — resizable 3-panel layout | `FlowNodeConfigModal.tsx` (modal) | Different UX |
| `NodeSettings.vue` — parameter form | `flowNodeConfigFields.tsx` | Exists |
| Schema-driven field types (string/bool/select) | Implemented | Exists |
| Monaco for code parameters | Implemented | Exists |
| `InputPanel` / `OutputPanel` — live run data | `flowNodeIoPreview.ts` | Exists (partial) |
| `InputNodeSelect` — dropdown to pick upstream node | Not implemented | Gap |
| `NDVFloatingNodes` — prev/next node badges (one per input, one per output) | Not implemented | Gap |
| Table mode (`convertToTable`) — one row per item, one col per JSON key | Not implemented | Gap |
| JSON mode — paginated `item.json` tree view | JSON only (no paging) | Partial |
| Schema mode (`VirtualSchema`) — structural type tree | Not implemented | Gap |
| Binary mode — card per item, viewer per named attachment | Not implemented | Gap |
| Binary: `IBinaryData` with external `id` reference + `/rest/binary-data` endpoint | Not designed yet | Gap |
| Pinned data | Not implemented | Gap |

### Execution logs

| n8n concept | DocRouter equivalent | Status |
|---|---|---|
| `WorkflowExecutionsList.vue` | `FlowExecutionList.tsx` | Exists |
| `WorkflowExecutionsCard.vue` (status, time) | `FlowExecutionList.tsx` rows | Exists |
| `ExecutionsFilter.vue` | Not implemented | Gap |
| `WorkflowExecutionsPreview.vue` — canvas overlay | `FlowExecutionsView.tsx` | Partial |
| Per-node status on canvas after run | `flowNodeRunStatus.ts` | Exists |
| Per-node output tree (run_data viewer) | `FlowLogsPanel.tsx` | Exists (partial) |
| `RunDataTable` (tabular item display) | Not implemented | Gap |
| Execution annotation / voting (enterprise) | Not applicable | Skip |

### Real-time updates

| n8n | DocRouter | Status |
|---|---|---|
| WebSocket/SSE push | `useExecutionPoller` (2 s polling) | Polling only |
| Per-node live status during run | On poll result | Works |

### Priority gaps to close (suggested order)

1. **Floating prev/next node navigation** — add an `NDVFloatingNodes`-style
   component to `FlowNodeConfigModal.tsx` (or a future inline panel):
   - Left edge: one clickable badge per direct main-input parent node.
   - Right edge: one clickable badge per direct main-output child node.
   - Clicking a badge closes the current modal and re-opens it for that node.
   - Implementation: from the open node's `id`, walk `edges` to find
     `source === id` (children) and `target === id` (parents), look up the
     connected node's `FlowNode`, and render a small icon button per node.
2. **Upstream node selector in Input panel** — inside the left "Input" column of
   `FlowNodeConfigModal.tsx`, add a `<select>` that lists all ancestor nodes
   (walk edges recursively from the current node's inputs). Changing the
   selection re-renders the input preview using that ancestor's `run_data`.
3. **Search in node palette** — `FlowNodePalette.tsx`: add a text input that
   filters node type cards by label/description.
4. **Table view for run data** — `FlowLogsPanel.tsx`: add a table mode next to
   the existing JSON tree, showing `data.main[0]` items as columns.
5. **Execution filter** — `FlowExecutionList.tsx`: add status and date-range
   filter controls above the table; pass to `listExecutions`.
6. **Inline node config panel** (NDV-style) — replace `FlowNodeConfigModal.tsx`
   with a right-side panel that opens without a modal dialog, keeping the canvas
   visible.
7. **Undo/redo** — add a command stack to `FlowEditor.tsx` for node add/remove
   and position moves.
8. **Non-main handles** — extend `FlowCanvasNode.tsx` to render separate handle
   types when a node type declares `ai_*` or other non-main connection lanes.
