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
CanvasNode.vue                    outer wrapper: toolbar visibility, context menu, selection ring
├── CanvasNodeToolbar.vue         hover toolbar (run / disable / delete / ⋯)
├── CanvasNodeRenderer.vue        picks the render sub-component by type
│   ├── CanvasNodeDefault.vue     standard process node body (icon + name label below)
│   ├── CanvasNodeStickyNote.vue  sticky note
│   └── CanvasNodeAddNodes.vue    "+" ghost node at the end of a chain
└── CanvasHandleRenderer.vue      one instance per port (input or output)
    ├── CanvasHandleMainInput.vue    left-side rectangle dot
    ├── CanvasHandleMainOutput.vue   right-side dot + animated + button
    ├── CanvasHandleNonMainInput.vue bottom-side diamond (AI connections)
    └── CanvasHandleNonMainOutput.vue top-side diamond
        └── parts/
            ├── CanvasHandleDot.vue       filled circle — output connection point
            ├── CanvasHandleRectangle.vue filled rectangle — input connection point
            └── CanvasHandlePlus.vue      SVG line + rounded-rect + "+" path
```

---

### Node shape and CSS

**Standard (process) node** — `CanvasNodeDefault.vue`

```scss
.node {
  width:  100px;            /* fixed square by default */
  height: 100px;            /* grows with handle count: +42px per extra handle above 3 */
  border: 2px solid var(--color-foreground-xdark);
  border-radius: var(--border-radius-large);   /* ~12px — uniformly rounded */
  background: var(--color-node-background);    /* white */
  display: flex;
  align-items: center;
  justify-content: center;
}
```

**Trigger node** — same `.node` div but with the CSS class `.trigger` added:

```scss
&.trigger {
  border-radius: 36px var(--border-radius-large) var(--border-radius-large) 36px;
  /* left corners are much more rounded (36 px ≈ pill) */
  /* right corners use the standard radius (~12 px) */
}
```

This produces the distinctive pill-on-left / square-on-right shape that
visually distinguishes trigger (start) nodes from process nodes.

**Node name label** lives *below* the node box, not inside it:

```scss
.description {
  position: absolute;
  top: 100%;              /* sits directly below the node box */
  margin-top: var(--spacing-2xs);   /* ~4 px gap */
  width: 100%;
  min-width: calc(var(--canvas-node--width) * 2);  /* 200 px — wider than the box */
  display: flex;
  flex-direction: column;
  align-items: center;
}

.label {
  font-size: var(--font-size-m);    /* 14 px */
  font-weight: var(--font-weight-bold);
  text-align: center;
  -webkit-line-clamp: 2;            /* truncates after 2 lines */
  overflow: hidden;
}

.subtitle {
  font-size: var(--font-size-xs);   /* 12 px */
  color: var(--color-text-light);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
```

**State-driven border colours** (CSS class toggling on `.node`):

| Class | Border colour | When |
|---|---|---|
| `.selected` | box-shadow ring (sky blue) | node is selected |
| `.success` | `--color-success` (green) | run completed OK |
| `.error` | `--color-danger` (red) | run had issues |
| `.running` | `--color-node-running-border` + dimmed bg | currently executing |
| `.waiting` | `--color-secondary` (yellow) | paused / waiting |
| `.disabled` | `--color-foreground-base` (grey) | node is toggled off |
| `.pinned` | `--color-node-pinned-border` (amber) | data is pinned |

The `NodeIcon` (svg/image from the node type registry) is rendered as a child
inside `CanvasNode.vue`, centred inside the node box at 40 × 40 px (30 × 30 for
sub-configuration nodes).

---

### Hover toolbar — `CanvasNodeToolbar.vue`

The toolbar is an `absolute`-positioned div sitting **above** the node box:

```scss
/* CanvasNode.vue */
.canvasNodeToolbar {
  position: absolute;
  top: 0;
  left: 50%;
  transform: translate(-50%, -100%);  /* floats above the node */
  opacity: 0;
  transition: opacity 0.1s ease-in;
  z-index: 1;
}

/* revealed on node hover, focus, or when its own context menu is open */
.canvasNode:hover .canvasNodeToolbar,
.canvasNode:focus-within .canvasNodeToolbar,
.canvasNode.showToolbar .canvasNodeToolbar {
  opacity: 1;
}
```

The toolbar itself is a rounded pill containing icon buttons:

```scss
/* CanvasNodeToolbar.vue */
.canvasNodeToolbarItems {
  display: flex;
  align-items: center;
  background-color: var(--color-canvas-background);
  border-radius: var(--border-radius-base);
}
```

Buttons rendered (left → right):

| Button | Icon | `data-test-id` | Visible when |
|---|---|---|---|
| Run / test step | `play` | `execute-node-button` | not readOnly, not configuration-type |
| Disable / enable | `power-off` | `disable-node-button` | not readOnly, default type |
| Delete | `trash` | `delete-node-button` | not readOnly |
| Sticky color | colour swatches | — | sticky note only |
| More (⋯) | `ellipsis-h` | `overflow-node-button` | always |

The **⋯ button** opens the context menu (`useContextMenu`). When the context
menu is open with `source === 'node-button'`, `CanvasNode` adds the
`.showToolbar` class so the toolbar stays visible while the menu is open.

Emits from `CanvasNodeToolbar`: `run`, `toggle`, `delete`, `update`,
`open:contextmenu`.

---

### Output handle with + button — `CanvasHandleMainOutput.vue`

Each output port has two visual layers:

1. **`CanvasHandleDot`** — a filled circle (8 × 8 px) that is always visible.
   It is the Vue Flow `<Handle>` hit target for dragging connections.

2. **`CanvasHandlePlus`** — a small SVG that appears only when the output is
   **not yet connected** and the canvas is not in read-only mode:

```html
<!-- CanvasHandleMainOutput.vue (simplified) -->
<CanvasHandleDot />
<CanvasHandlePlus
  v-if="!isConnected && !isReadOnly"
  v-show="!isConnecting || isHovered"
  :type="runDataTotal > 0 ? 'success' : 'default'"
  :line-size="runDataTotal > 0 ? 80 : 46"
/>
```

`CanvasHandlePlus` is an SVG composed of three parts:

```
[---line---][+box]
```

- **line** — a horizontal `<line>` element from the dot to the box.
  Length is `lineSize` px (46 by default, 80 when run data is present).
- **+box** — a 24 × 24 px rounded-rect (`rx=4`) with a `+` path inside.
  Clicking it emits `add`, which is wired through `CanvasNode` to
  `useCanvasOperations.addNode()` — opening the node palette pre-wired to
  this output.

```scss
/* hover: box and path turn primary blue */
.plus:hover path { fill: var(--color-primary); }
.plus:hover rect { stroke: var(--color-primary); }

/* success state: line turns green */
.wrapper.success .line { stroke: var(--color-success); }
```

After a successful run the line turns green and the item count label
(`"1 item"`) appears above the + box. The + box itself disappears once the
output is connected (a real edge replaces it).

---

### Input handle — `CanvasHandleMainInput.vue`

Simpler than the output handle: just a `CanvasHandleRectangle` (a small
filled rectangle, 8 × 16 px) with an optional label to its left. No + button.
The rectangle is the Vue Flow `<Handle type="target">` hit target.

---

### Handle positioning

`CanvasNode.vue` computes handle positions via `createEndpointMappingFn`:

```typescript
// For N handles on one side, evenly space them:
offset: { top: `${(100 / (endpoints.length + 1)) * (index + 1)}%` }
```

Main inputs → `Position.Left`, offset along `top`.
Main outputs → `Position.Right`, offset along `top`.
Non-main inputs (AI) → `Position.Bottom`, offset along `left`.
Non-main outputs (AI) → `Position.Top`, offset along `left`.

---

### Edge rendering and edge hover toolbar

**`CanvasEdge.vue`** — SVG smooth-step path (Vue Flow's `BaseEdge`). Props:
`data: CanvasConnectionData`, `source`, `target`, `selected`, `hovered`,
`readOnly`.

Edge status colours (applied via `stroke` in `edgeStyle`):

| `data.status` / condition | Colour |
|---|---|
| `'success'` | `--color-success` (green) |
| `'pinned'` | `--color-secondary` (amber) |
| `'running'` | `--color-primary` (blue) |
| non-main connection (AI lane) | `--node-type-supplemental-color`; dashed (`strokeDasharray: '8,8'`) |
| selected | `--color-background-dark` (near-black) |
| hovered | `--color-primary` (overrides all above) |
| default | `--color-foreground-xdark` (dark grey) |

The edge has `interactionWidth: 40` — a 40 px invisible hit zone around the
path, making it easy to hover a thin line.

#### Edge hover state management (`Canvas.vue`)

`Canvas.vue` maintains a `edgesHoveredById: Record<string, boolean>` ref:

```typescript
// Vue Flow lifecycle hooks (from @vue-flow/core):
onEdgeMouseEnter(({ edge }) => { edgesHoveredById.value = { [edge.id]: true }; });
onEdgeMouseLeave(({ edge }) => { edgesHoveredById.value = { [edge.id]: false }; });
```

The `hovered` prop is passed into `CanvasEdge` from the edge slot template:
```html
<CanvasEdge :hovered="edgesHoveredById[edgeProps.id]" ... />
```

There is a second hover trigger: the toolbar label area inside the edge itself
fires `update:label:hovered` events, which also set `edgesHoveredById[id]` and
additionally set `edgesBringToFrontById[id] = true` so the hovered edge SVG is
rendered above any overlapping edges.

#### Edge label / toolbar toggle

`CanvasEdge.vue` uses Vue Flow's `<EdgeLabelRenderer>` to place an HTML `div`
at the midpoint of the path (`labelPosition` computed from
`getEdgeRenderData`). This div switches between two states:

```html
<EdgeLabelRenderer>
  <div :style="edgeToolbarStyle" :class="edgeToolbarClasses"
       @mouseenter="emit('update:label:hovered', true)"
       @mouseleave="emit('update:label:hovered', false)">

    <!-- When hovered and not readOnly → show toolbar -->
    <CanvasEdgeToolbar v-if="hovered && !readOnly" :type="connectionType"
                       @add="onAdd" @delete="onDelete" />

    <!-- Otherwise → show item count label -->
    <div v-else>{{ label }}</div>   <!-- e.g. "1 item" -->
  </div>
</EdgeLabelRenderer>
```

The label has a semi-transparent canvas-colour background so it appears to
float on the dotted grid.

#### `CanvasEdgeToolbar.vue` — the + and delete buttons

```html
<div class="canvasEdgeToolbar" data-test-id="canvas-edge-toolbar">
  <!-- + button: only for main connections, not AI lanes -->
  <N8nIconButton v-if="type === 'main'" icon="plus"
                 data-test-id="add-connection-button" @click="emit('add')" />

  <!-- delete button: always shown -->
  <N8nIconButton icon="trash"
                 data-test-id="delete-connection-button" @click="emit('delete')" />
</div>
```

Both are small `tertiary` icon buttons rendered side-by-side in a flex row,
with a 2 px border. The **+ button is hidden for AI / non-main lanes** (you
cannot insert a node in the middle of an AI tool connection).

#### What "+" does: insert node between two connected nodes

When the + button is clicked, `CanvasEdge` emits `add(connection)` with the
full `Connection` object (`source`, `target`, `sourceHandle`, `targetHandle`).

`Canvas.vue` re-emits this as `click:connection:add(connection)` to
`NodeView.v2.vue`, which calls:

```typescript
function onClickConnectionAdd(connection: Connection) {
  nodeCreatorStore.openNodeCreatorForConnectingNode({
    connection,
    eventSource: NODE_CREATOR_OPEN_SOURCES.NODE_CONNECTION_ACTION,
  });
}
```

`openNodeCreatorForConnectingNode` in `nodeCreator.store.ts`:
1. Looks up the source node and records it as `uiStore.lastSelectedNode`.
2. Stores the **entire original connection** in
   `uiStore.lastInteractedWithNodeConnection`.
3. Opens the node palette.

When the user picks a node type and it is created,
`useCanvasOperations.addNode` detects `lastInteractedWithNodeConnection` and
performs a **three-step splice**:

```typescript
// 1. Delete the original A→B edge
deleteConnection(lastInteractedWithNodeConnection);

// 2. The new node N was already connected: A→N (done by the normal add flow)

// 3. Re-create the severed B leg: N→B
createConnection({
  source: newNode.id,
  sourceHandle: '...',
  target: lastInteractedWithNodeConnection.target,
  targetHandle: lastInteractedWithNodeConnection.targetHandle,
});
```

Result: `A → N → B` replaces `A → B`, with N positioned between A and B on
the canvas.

#### DocRouter porting plan for edge toolbar

DocRouter's `FlowCanvasEdge.tsx` already uses `EdgeLabelRenderer` to show an
item-count label. The edge toolbar is the next step:

1. **Track hover state** in `FlowEditor.tsx`:
   ```typescript
   const [hoveredEdgeId, setHoveredEdgeId] = useState<string | null>(null);
   // React Flow's onEdgeMouseEnter / onEdgeMouseLeave props on <ReactFlow>
   onEdgeMouseEnter={(_, edge) => setHoveredEdgeId(edge.id)}
   onEdgeMouseLeave={()          => setHoveredEdgeId(null)}
   ```
   Pass `isHovered={edge.id === hoveredEdgeId}` through `edge.data` or via a
   custom edge prop.

2. **Switch the midpoint label** inside `FlowCanvasEdge.tsx`:
   ```tsx
   {isHovered ? (
     <div className="flex gap-1 ...">
       <button onClick={onAdd}>+</button>
       <button onClick={onDelete}>🗑</button>
     </div>
   ) : (
     <div>{label}</div>   // "N items"
   )}
   ```
   Wire `onMouseEnter` / `onMouseLeave` on the label div to keep it hovered
   while the mouse is on the buttons (same trick n8n uses).

3. **Delete handler**: React Flow's `deleteElements` or a custom
   `onEdgesDelete` callback keyed by `edge.id`.

4. **Insert handler**: on + click, record `edge` in a `pendingInsertEdge` ref,
   open `FlowNodePalette`, and on node-type selection:
   - Remove the original edge.
   - Create a new node at the midpoint between source and target.
   - Add `sourceNode → newNode` and `newNode → targetNode` edges.

---

### DocRouter current state and porting plan

DocRouter's `FlowCanvasNode.tsx` already implements the core shape correctly
using Tailwind classes on a React Flow `NodeProps` component. The following
table maps what's done vs what's missing:

| Feature | n8n impl | DocRouter status |
|---|---|---|
| Rounded-rect process node | `.node { border-radius: 12px }` | `rounded-2xl` — done |
| Pill-left trigger node | `.trigger { border-radius: 36px 12px 12px 36px }` | `rounded-r-[32px] rounded-l-md` — done |
| Node name label below box | `position: absolute; top: 100%` | label is inside the box — **gap** |
| Node icon centred in box | `NodeIcon` 40 × 40 inside box | single icon placeholder — partial |
| State border colours | CSS class toggling | only `disabled` opacity — **gap** |
| Hover toolbar above node | `opacity: 0` → `1` on `:hover` | not implemented — **gap** |
| Run button in toolbar | `N8nIconButton icon="play"` | not implemented — **gap** |
| Disable toggle in toolbar | `N8nIconButton icon="power-off"` | not implemented — **gap** |
| Delete in toolbar | `N8nIconButton icon="trash"` | not implemented — **gap** |
| ⋯ context menu button | `N8nIconButton icon="ellipsis-h"` | not implemented — **gap** |
| Output + button (unconnected) | `CanvasHandlePlus` SVG | plain `<Handle>` dot — **gap** |
| + button → open palette | emits `add` → opens node creator | not wired — **gap** |
| Item count label on edge (post-run) | label above + line turns green | `FlowCanvasEdge` shows count — partial |

**Recommended implementation order for DocRouter `FlowCanvasNode.tsx`:**

1. **Move label below the box** — position the name `div` with
   `position: absolute; top: 100%; left: 50%; transform: translateX(-50%)`
   so it floats below the node boundary (React Flow clips `overflow: visible`
   automatically).

2. **Add hover toolbar** — render a `div` with
   `position: absolute; bottom: 100%; left: 50%; transform: translateX(-50%)`
   containing icon buttons (run, disable, delete, ⋯). Use a `useState` hover
   flag toggled by `onMouseEnter` / `onMouseLeave` on the node root, and set
   `opacity: 0` / `opacity: 1` with a CSS transition. Wire `stopPropagation`
   on button clicks to prevent node selection.

3. **Add + button to unconnected outputs** — check whether any edge has
   `source === node.id && sourceHandle === outHandleId`. If not connected,
   render an SVG `+` next to the handle dot (positioned absolutely to the right
   of the handle). On click, emit upward (via `data.onAddNode(handleId)`) so
   `FlowEditor` can open `FlowNodePalette` pre-targeted to that output.

4. **State border colours** — map `executionNodeStatus` and `node.disabled`
   to Tailwind border classes: `border-emerald-500` (success), `border-red-400`
   (error), `border-yellow-400` (running/waiting), `border-gray-300`
   (disabled).

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
| Node label floats below the box (`position: absolute; top: 100%`) | Label rendered inside the box | Gap |
| `CanvasNodeToolbar` — hover toolbar (run / disable / delete / ⋯) | Not implemented | Gap |
| `CanvasHandlePlus` — + button on unconnected outputs | Not implemented | Gap |
| Edge hover toolbar (+ insert / delete connection) | Not implemented | Gap |
| `CanvasNodeStatusIcons` — running spinner, ✓ + count, ⚠ issues, waiting clock, pinned thumbtack | `ExecutionStatusBadge` (success/error/skipped only) | Partial |
| `CanvasNodeDisabledStrikeThrough` — horizontal line across disabled nodes | `opacity-60` only | Partial |
| `CanvasNodeTooltip` — auto-visible tooltip from `render.options.tooltip` | Not implemented | Gap |
| `CanvasNodeTriggerIcon` — ⚡ bolt to the left of trigger nodes | Not implemented | Gap |
| `CanvasNodeAddNodes` — dashed 100×100 "Add first step" button on empty canvas | Not implemented | Gap |
| `CanvasConnectionLine.vue` — animated in-progress drag line | React Flow default dashed | Built-in (unstyled) |

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

### Canvas controls and interactions

| n8n | DocRouter | Status |
|---|---|---|
| `CanvasControlButtons.vue` — zoom in/out/fit/reset panel (bottom-left) | React Flow built-in `<Controls>` | Available; wired? |
| `CanvasRunWorkflowButton.vue` — "Execute workflow" / "Waiting for trigger" / "Executing" button (bottom-center) | Not implemented | Gap |
| `CanvasClearExecutionDataButton.vue` — clears execution overlay after run | Not implemented | Gap |
| Minimap (`@vue-flow/minimap`, auto-hides 1 s after interaction) | Not implemented | Gap |
| Ctrl+C / Ctrl+X / Ctrl+V — copy / cut / paste nodes | Not implemented | Gap |
| Ctrl+D — duplicate selected nodes | Not implemented | Gap |
| Ctrl+A — select all nodes | Not implemented | Gap |
| Ctrl+Enter — execute workflow | Not implemented | Gap |
| Ctrl+S — save workflow | Not implemented | Gap |
| P — toggle pin on selected nodes | Not implemented | Gap |
| Delete / Backspace — delete selected nodes/edges | Not implemented | Gap |
| "Tidy up" context-menu / toolbar action (auto-arrange nodes) | Not implemented | Gap |
| "Duplicate" node context-menu action | Not implemented | Gap |
| "Convert to sub-workflow" context-menu action | Not applicable | Skip |
| Canvas chat panel (`CanvasChat.vue`) for Chat Trigger nodes | Not applicable | Skip |

### Workflow-level settings

| n8n | DocRouter | Status |
|---|---|---|
| Workflow settings modal (timezone, execution order, error workflow, save data policy) | Not implemented | Gap |
| Retry failed execution button | Not implemented | Gap |
| Execution annotation / voting (enterprise) | Not applicable | Skip |

### Real-time updates

| n8n | DocRouter | Status |
|---|---|---|
| WebSocket/SSE push | `useExecutionPoller` (2 s polling) | Polling only |
| Per-node live status during run | On poll result | Works |

### Priority gaps to close (suggested order)

Items are grouped by effort and impact. "Quick win" means a self-contained
change unlikely to touch shared state.

#### High impact — node canvas

1. **Node hover toolbar** (`CanvasNodeToolbar` pattern) — show a compact toolbar
   above the node on hover with Run / Disable / Delete / ⋯ actions. In React
   Flow this is best done with a `<NodeToolbar>` (built-in since RF 11) or an
   absolutely-positioned `div` inside the node rendered at `opacity-0` toggled
   to `opacity-100` on CSS `:hover`. Keep `pointer-events: none` when invisible.

2. **+ button on unconnected outputs** (`CanvasHandlePlus` pattern) — when a
   source handle has no connected edge, render a clickable `+` SVG/icon to the
   right of the handle. Clicking it opens the node palette pre-filtered to
   compatible nodes, then wires the new node automatically.
   - State: track which handles are unconnected (`edges` list + handle id).
   - Gate on `!readOnly` (hide during execution review).

3. **Edge hover toolbar** — on `onMouseEnter` / `onMouseLeave` for edges, show
   a `+` (insert node between) and a delete `×` button at the edge midpoint via
   `<EdgeLabelRenderer>`. The insert flow:
   1. Store the original connection (`source`, `sourceHandle`, `target`, `targetHandle`).
   2. Open the node palette.
   3. After the user picks a node: remove the original edge, keep the
      source→new-node edge the palette auto-creates, then add new-node→target.

4. **Node label below the box** — move the node `title` text from inside
   `FlowCanvasNode.tsx` to an absolutely-positioned `div` with
   `top: 100%; left: 50%; transform: translateX(-50%)` and
   `min-width: 200px; text-align: center`. The node icon takes the full box area.
   This matches n8n's visual language precisely.

5. **Status icons** (`CanvasNodeStatusIcons` pattern) — extend
   `ExecutionStatusBadge` in `FlowCanvasNode.tsx` to cover all states:
   - **running**: spinning animation overlay at ~40px centered on the node icon.
   - **success**: green ✓ badge + iteration count if > 1 run.
   - **error**: red ⚠ badge (already exists as `ExclamationCircleIcon`).
   - **waiting**: clock icon badge.
   - **pinned**: thumbtack icon, replaces the run-status badge.

6. **Disabled strikethrough** — when `node.disabled`, render a 1 px horizontal
   line (full node width + 12 px overflow on each side) at vertical midpoint,
   in addition to the existing `opacity-60`.

#### High impact — node config panel

7. **Floating prev/next node navigation** — add an `NDVFloatingNodes`-style
   component to `FlowNodeConfigModal.tsx` (or a future inline panel):
   - Left edge: one clickable badge per direct main-input parent node.
   - Right edge: one clickable badge per direct main-output child node.
   - Clicking a badge closes the current modal and re-opens it for that node.
   - Implementation: walk `edges` where `source === id` (children) and
     `target === id` (parents), look up each connected `FlowNode`, render a
     small icon button per result.

8. **Upstream node selector in Input panel** — inside the left "Input" column of
   `FlowNodeConfigModal.tsx`, add a `<select>` listing all ancestor nodes (walk
   edges recursively from the current node's inputs). Changing the selection
   re-renders the input preview using that ancestor's `run_data`.

9. **Table view for run data** — add a table mode next to the existing JSON tree
   in `FlowLogsPanel.tsx` / the Output panel of `FlowNodeConfigModal.tsx`.
   Algorithm: union all top-level keys across `data.main[0]` items into columns;
   cap at 40 columns; render with a scrollable `<table>`.

10. **Schema mode** — structural type tree built by deep-merging all items, then
    recursively inferring types. Renders as an indented tree with type badges.

#### Medium impact — canvas UX

11. **Execute workflow button** — a prominent button at the bottom-center of the
    canvas (or in a top toolbar). States: "Run flow" → "Executing…" (spinner) →
    back to idle. Wire to `POST /flows/{id}/executions` and start polling.

12. **Clear execution data** — after a run completes, show a small button
    (bottom-center or toolbar) to clear the `runData` overlay on all nodes,
    returning the canvas to edit-only state.

13. **Keyboard shortcuts** — wire the following in `FlowEditor.tsx` via
    `useKeyPress` / `useHotkeys`:
    - `Ctrl+A` — select all nodes.
    - `Ctrl+C` / `Ctrl+X` — copy / cut selected nodes (clone their `FlowNode`
      data + offset positions).
    - `Ctrl+V` — paste copied nodes at cursor position.
    - `Ctrl+D` — duplicate selected nodes (copy + paste in one step, offset 20 px).
    - `Delete` / `Backspace` — delete selected nodes and their edges.
    - `Ctrl+Enter` — run workflow.
    - `Ctrl+S` — save workflow.

14. **Search in node palette** — `FlowNodePalette.tsx`: add a text input that
    filters node type cards by label/description in real time.

15. **Empty canvas placeholder** — when there are zero nodes, show a dashed
    100×100 button labelled "Add first step" centred on the canvas. Clicking it
    opens the node palette.

#### Lower priority

16. **Inline node config panel** (NDV-style) — replace `FlowNodeConfigModal.tsx`
    with a right-side drawer that opens without a modal dialog, keeping the
    canvas visible. Requires a layout change in `FlowEditor.tsx`.

17. **Undo/redo** — command stack in `FlowEditor.tsx` for node add/remove,
    position moves, and parameter edits. Model after n8n's six command classes
    in `packages/editor-ui/src/models/history.ts`.

18. **Execution filter** — `FlowExecutionList.tsx`: add status and date-range
    filter controls above the table.

19. **Retry failed execution** — add a retry button on the execution detail view;
    call `POST /flows/{id}/executions/{eid}/retry`.

20. **Minimap** — React Flow ships `<MiniMap>` as a built-in component; wire it
    with auto-hide (set `style={{ opacity: 0 }}` and fade in/out on canvas
    interaction).

21. **Tidy up / auto-arrange** — add a toolbar button that runs a simple
    left-to-right topological sort of nodes and repositions them at a fixed grid.

22. **Non-main handles** — extend `FlowCanvasNode.tsx` to render separate handle
    types when a node type declares `ai_*` or other non-main connection lanes.

23. **Workflow settings modal** — workflow-level settings (timezone, execution
    order, error workflow, save data policy). Requires new backend fields.

24. **Trigger bolt icon** — render a ⚡ icon to the left of trigger nodes
    (quick win; purely visual).

25. **Node tooltip** — if a node type provides `render.options.tooltip`, show an
    auto-visible tooltip above the node (MUI `<Tooltip>` with `open={true}`).

26. **Binary data mode** — card-per-item viewer with download link; requires
    designing the `IBinaryData` storage model and a `/binary-data` endpoint.
    Lower priority until binary outputs are needed.
