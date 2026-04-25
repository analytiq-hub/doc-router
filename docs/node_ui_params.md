# Node UI — Parameters, Expressions, IO, and Pinning (Plan)
This document describes the **frontend UX** and the minimum supporting **data model / API surface**
needed for node parameter editing, expression inputs, IO inspection (Schema/Table/JSON), and
pinning / overriding node outputs in DocRouter flows.

It is written to mirror the most useful parts of n8n's node UX while staying consistent with
DocRouter's engine contracts (see `docs/flows2.md`) and the current Flows UI implementation
in `packages/typescript/frontend/src/components/flows/`.

All n8n paths below are relative to `n8n/packages/editor-ui/src/`.

---

## 1. Goals

- **Parameter editing**: schema-driven parameter forms that support both literal values and expressions.
- **IO inspection**: show a node's **Input** and **Output** in three formats: **Schema**, **Table**, **JSON**.
- **Drag & drop**: allow dragging values/paths from IO into:
  - parameter inputs (string/number/boolean),
  - JSON editor parameters (object/array),
  - code blocks (Monaco) for code nodes.
- **Pin results**: allow pinning a node's output from a prior run so downstream nodes can be configured
  deterministically without re-running.
- **Edit outputs**: allow lightweight editing of a pinned output (or "mock output") and persist it as pin data.

Non-goals (v1):
- Full spreadsheet-like editing of arbitrary large result sets.
- Perfect parity with n8n's internal expression language; DocRouter expressions remain **Python-eval based**.

---

## 2. Current state (codebase today)

- Node configuration UI is `FlowNodeConfigModal.tsx`, which already has an **Input** and **Output**
  column, but renders IO as **raw JSON only** (`<pre>{JSON.stringify(...)}</pre>`).
- Parameter fields are schema-driven (`flowNodeConfigFields.tsx`) and already support Monaco for
  `python_code` / `js_code` / `ts_code` and for object/array parameters (JSON mode).
- Engine already supports `pin_data` on revisions (see `docs/flows2.md` mapping to n8n `pinData`),
  but the UI does not yet expose pin/edit semantics.

### 2.1 Backend API coverage

All routes are in `packages/python/app/routes/flows.py`.

| Need | Endpoint | Status |
|------|----------|--------|
| Flow + revision CRUD | `GET/PUT /flows/{id}`, `GET /flows/{id}/revisions/{rev}` | ✅ Complete |
| `pin_data` on revision | `FlowRevision.pin_data: dict[str,Any] \| None` — saved and returned | ✅ Complete |
| Engine respects `pin_data` | `engine.py:323–325` — skips node execution when id is in `pin_data` | ✅ Complete |
| Trigger / list / stop execution | `POST /flows/{id}/run`, `GET /executions`, `POST /executions/{eid}/stop` | ✅ Complete |
| Full execution + `run_data` | `GET /flows/{id}/executions/{eid}` returns entire `run_data` dict | ✅ Complete |
| Node types + parameter schemas | `GET /flows/node-types` — returns key, label, category, `parameter_schema` | ✅ Complete |
| Per-node output fetch | No dedicated endpoint — frontend must parse `execution.run_data[node_id]` | ⚠️ Workaround |
| Pin data update without full save | No `PATCH` for `pin_data` alone — must PUT the full revision | ⚠️ Workaround |

**`run_data` per-node shape** (from `engine.py`):

```python
run_data[node_id] = {
    "status": "success" | "error" | "skipped",
    "start_time": "<iso datetime>",
    "execution_time_ms": int,
    "data": {"main": [ [{"json": {...}, "binary": {}, "meta": {}}], ... ]},
    "error": dict | None,
}
```

The frontend accesses a node's output items as `run_data[node_id].data.main[0]`
(first output slot, list of items). No additional backend work is needed to start
the frontend implementation — both workarounds are acceptable for v1.

---

## 3. UX model

### 3.1 IO tabs: Schema / Table / JSON

For both **Input** and **Output** panels in the node modal:

- Add a compact tab switcher with 3 tabs:
  - **Schema**: inferred field list + types (best-effort) with nesting support.
  - **Table**: rows/columns view for arrays of objects (best-effort); falls back to a message when not tabular.
  - **JSON**: pretty JSON viewer (read-only) with expand/collapse (or Monaco read-only JSON).

Notes:
- We do **best-effort inference** from the current sample item(s) (like n8n).
- Table view should support "first N rows" for large arrays.
- Output "JSON" view should default to showing **item 0** for parity with table/schema inference.

#### n8n reference — IO tabs

**Tab switcher** — `components/RunData.vue`

`N8nRadioButtons` bound to `displayMode` (stored in ndv.store with localStorage persistence).
Mode values: `'table'` (default for Output), `'json'`, `'schema'`, plus `'binary'` when binary
items are present.

```typescript
// stores/ndv.store.ts
inputPanelDisplayMode:  'schema'  // localStorage default
outputPanelDisplayMode: 'table'   // localStorage default
```

**Schema mode** — `components/VirtualSchema.vue` + `composables/useDataSchema.ts`

`getSchemaForExecutionData(items)` deep-merges all items then calls `getSchema(merged)`
recursively to infer types. Result is a `Schema` tree:

```typescript
type Schema =
  | { type: 'object' | 'array'; value: Array<{ key: string } & Schema>; path: string }
  | { type: 'string' | 'number' | 'boolean'; value: string; path: string }
  | { type: 'null' | 'undefined'; value: string; path: string }
```

The tree is flattened via `flattenSchema()` for a virtual-scroll list renderer.
`filterSchema()` filters it by search term (recursive).

**Table mode** — `components/RunDataTable.vue`, function `convertToTable()`

```typescript
// Input: INodeExecutionData[]  Output: ITableData
interface ITableData {
  columns:  string[];            // union of top-level JSON keys across all items
  data:     GenericValue[][];    // rows × columns; undefined where key is absent
  hasJson:  { [col: string]: boolean };  // true → column has nested objects → expand icon
  metadata: { hasExecutionIds: boolean; data: (ITaskMetadata | undefined)[] };
}
```

Algorithm: iterate items → collect unique keys → for each item produce a row aligned to columns.
Cap: `MAX_COLUMNS_LIMIT = 40`.

**JSON mode** — `components/RunDataJson.vue`

Renders `item.json` using `VueJsonPretty` with `virtual` prop (virtual-scroll for large trees).
Paginated: 10 items per page. Each value/path node is draggable (see §5).

---

### 3.2 Editing / pinning outputs

In **Output** panel:

- Add a **Pin output** toggle/button:
  - When enabled, the current output preview becomes the pinned value for this node.
  - Persisted into the revision's `pin_data` on Save.
- Add an **Edit pinned output** action:
  - Opens an editor (Monaco JSON) for the pinned payload.
  - On save, validates JSON and updates the pinned payload.
- Add a **Clear pin** action to remove `pin_data[nodeId]`.

In the canvas:
- Indicate pinned nodes (small "pin" badge) and optionally show "Pinned" in the node modal header.

#### n8n reference — pin button and storage

**Pin button** — `components/RunDataPinButton.vue`

`thumbtack` icon; active (filled) when `pinnedData.hasData`. Emits `togglePinData` when clicked.
Disabled for binary output nodes.

**`usePinnedData` composable** — `composables/usePinnedData.ts`

| Method | What it does |
|--------|-------------|
| `data` | `computed` → `workflowsStore.pinData[nodeName]` |
| `hasData` | `computed` → `data.value != null` |
| `setData(rawJson, source)` | Validates JSON syntax + size, calls `workflowsStore.pinData({ node, data })` |
| `unsetData(source)` | Removes entry, calls `workflowsStore.unpinData({ node })` |

`source` is a string enum (`'pin-icon-click'`, `'save-edit'`, `'on-ndv-close-modal'`, etc.) used for telemetry.

**Pin storage shape** — `stores/workflows.store.ts`

```typescript
// workflow.pinData in the workflow store
type IPinData = { [nodeName: string]: INodeExecutionData[] }

// pinData() action stores items as:
workflow.value.pinData[node.name] = data.map(item => ({ json: item.json }));
```

Keyed by **node name** (not id). Saved as part of the workflow JSON on every Save.

**`RunData.vue` toggle handler** (`onTogglePinData`):
- if `pinnedData.hasData` → `unsetData('pin-icon-click')`
- else → `setData(rawInputData.value, 'pin-icon-click')` then re-validate node parameter issues.

**Canvas badge** — `components/canvas/elements/nodes/render-types/CanvasNodeDefault.vue`

`hasPinnedData` from `useCanvasNode()` adds CSS class `$style.pinned` on the node element.
`useCanvasNode` reads it from `data.value.pinnedData.count > 0`.

---

### 3.3 Where pinning applies

Pinning should apply at **engine runtime**:
- For a pinned node, the engine uses pinned data as the node's output without executing the node,
  so downstream nodes see stable data.

This matches n8n semantics and the existing `pin_data` field on revisions.

---

## 4. Data model & persistence

### 4.1 `pin_data` shape (frontend-friendly)

We should standardize a minimal JSON shape in `FlowRevision.pin_data`:

```json
{
  "<node_id>": {
    "main": [
      [ { "json": { "...": "..." } } ]
    ]
  }
}
```

Rationale:
- This is close to n8n's "runData-ish" representation and aligns with how our `run_data` is shaped today.
- It supports multiple items and can be extended later for multiple outputs.

> **n8n divergence**: n8n keys `pinData` by node **name**; DocRouter should key by node **id** to
> survive node renames. The engine must use the same key convention.

### 4.2 SDK types

Add explicit TS types in `@docrouter/sdk` (or extend existing `types/flows.ts`) for:
- `FlowPinData`
- `FlowPinNodeOutput`
- helpers for coercing "simple JSON" → pin shape and vice versa.

### 4.3 Saving

`FlowDetailPageClient.tsx` already calls `saveRevision(...)` with `pin_data`.
We'll extend the UI so editing/pinning updates local `revision.pin_data` and the Save flow persists it.

---

## 5. Expressions + drag & drop

### 5.1 Expression representation

We will support an **expression string** form in parameter values using a simple convention:

- **Literal strings**: stored as normal strings.
- **Expression strings**: stored as strings prefixed with `=` (like n8n), e.g.:
  - `={{ $json.invoice_id }}` (UI sugar)
  - `= _json["invoice_id"]` (engine-native)

Plan:
- UI accepts both styles and normalizes to engine-native Python expression on save.
- UI shows a small "fx" indicator when the value is an expression.

#### n8n reference — expression encoding and editor

**Detection** — `utils/nodeTypesUtils.ts`, `isValueExpression()`:

```typescript
function isValueExpression(parameter: INodeProperties, value: unknown): boolean {
    if (typeof value !== 'string') return false;
    return value.startsWith('=');   // first char determines mode
}
```

**`ExpressionParameterInput.vue`** — inline CodeMirror editor for expression values.
- `isAssignment` prop: when true, renders a `=` prefix label before the editor.
- Wraps `InlineExpressionEditorInput` (CodeMirror) and a `DraggableTarget` drop zone.
- `onDrop(value)` calls `dropInExpressionEditor(editorView, mouseEvent, value)`.

**`useExpressionEditor.ts`** — CodeMirror composable:
- `updateSegments()` parses the editor tree into `Resolvable` (inside `{{ }}`) vs `Plaintext` segments.
- Exposes `editor: Ref<EditorView>` and `segments: Ref<Segment[]>`.

**`ParameterInputWrapper.vue`** outer wrapper provides the literal↔expression mode toggle button
(small "fx" icon). Toggling prepends or strips the `=` from the stored value.

### 5.2 Drag payload format

When dragging a value/path from IO, set `dataTransfer` with one canonical mime type:

- `application/docrouter-flow-value`

Payload JSON:

```json
{
  "kind": "jsonPath",
  "source": "nodeOutput|nodeInput",
  "nodeId": "<node_id>",
  "path": ["field", "nested", 0, "id"],
  "exampleValue": 123
}
```

The drop target decides how to convert this into:
- a literal value (insert `exampleValue`),
- or an expression string (insert something like `=_node["<nodeId>"]["json"]["field"]["nested"][0]["id"]`).

#### n8n reference — drag & drop system

n8n uses a **custom mouse-event drag system**, not the HTML5 Drag API. The key pieces:

**`Draggable.vue`** — drag source wrapper

Detects `mousedown → mousemove` on elements with `data-target="mappable"`.
On drag start, calls `ndvStore.draggableStartDragging({ type, data, dimensions })`.
Renders a floating `MappingPill` component at the cursor during the drag.
`type = 'mapping'`, `targetDataKey = 'mappable'`.

**Data attributes** on draggable items (set in RunDataTable / RunDataJson / VirtualSchema):

```html
data-target="mappable"
data-value="<the resolved value>"
data-name="<field display name>"
data-path="<dot-notation path>"
data-depth="<nesting depth>"
```

**`MappingPill.vue`** — drag preview pill, changes color based on `canDrop` state.

**`DraggableTarget.vue`** — drop zone wrapper for parameter inputs

On `mouseenter`, calls `ndvStore.setActiveTarget(this)`.
On `mouseup`, emits `'drop'` with `ndvStore.draggableData` (the path string, e.g. `"$json.fieldName"`).

**`plugins/codemirror/dragAndDrop.ts`** — drop into CodeMirror

```typescript
// Insert into expression editor (ExpressionParameterInput):
function dropInExpressionEditor(view: EditorView, event: MouseEvent, value: string): void
// Insert into code editor (code nodes):
function dropInCodeEditor(view: EditorView, event: MouseEvent, value: string): void
```

Both find the position under the mouse cursor in the CodeMirror view, then insert/replace text.
`dropInExpressionEditor` checks if the cursor is inside a `Resolvable` node; if so it unwraps
the `=` prefix before inserting the path.

**DocRouter porting notes:**
- The ndvStore drag state (`draggableStartDragging`, `draggableData`, `setActiveTarget`) can be
  replicated with a React context or a Zustand store slice.
- The `data-target / data-value / data-path` attribute convention is portable as-is.
- For Monaco (used in DocRouter for code params), use the Monaco `editor.onDropIntoEditor` API
  or listen for `dragover/drop` on the editor DOM element and call
  `editor.executeEdits(...)` to insert the path at the drop position.

### 5.3 Drop targets

- **Text inputs**: on drop, insert expression (default) or literal (modifier key).
- **Monaco code**: insert an expression snippet at cursor:
  - Python: `_node["<id>"]["json"]["..."]`
  - JS/TS nodes (if supported): `$node["<name>"].json...` (or DocRouter equivalent).
- **Monaco JSON parameter**: insert a JSON literal (or a string expression, depending on schema).

We'll implement drop handling in a reusable hook (e.g. `useFlowValueDropTarget`) so all fields behave consistently.

---

## 6. IO views implementation details

### 6.1 Schema view

Input: sample JSON value(s).
Output: a tree of inferred fields:
- `name`: string
- `amount`: number
- `items`: array<object>
  - `sku`: string

Implementation (mirroring `useDataSchema.ts`):
- Deep-merge all items (lodash `merge({}, ...items)`) to get a single representative object.
- Traverse recursively; infer primitive types via `typeof`; treat `null` as `'null'`, arrays as `'array'`.
- For arrays: infer element type from the first non-null element.
- Cap depth (e.g. 6) and node count to avoid rendering huge payloads.
- `filterSchema(schema, term)` recursively prunes nodes not matching `term`.

### 6.2 Table view

If the sample is an array of objects:
- Columns = union of top-level keys (cap at 25; n8n caps at 40).
- Rows = first N items (cap at 50).
- `hasJson[col]` → render an expand icon in the column header to view nested object inline.

If not tabular:
- Show a helpful empty state ("Not a table: expected an array of objects.").

### 6.3 JSON view

Prefer a collapsible JSON viewer (e.g. `react-json-view` or a lightweight tree component);
fallback to Monaco read-only JSON.

Drag affordances:
- In Schema + Table, make each field/column header draggable to emit a path payload.
- In JSON view, support dragging a selected path (optional later; Schema/Table gets us 80%).

---

## 7. Execution semantics for pinned outputs

Engine behavior (target):
- During execution, when a node has pinned output in `pin_data`, treat it as that node's output and
  skip execution (and mark status as `success` with a "pinned" flag in `run_data`).

UI behavior:
- In Logs/Executions, show pinned nodes as "Pinned" and allow opening the pinned payload.

---

## 8. Implementation sequence (frontend-first plan)

1. **Refactor IO rendering** in `FlowNodeConfigModal.tsx`:
   - Replace `<pre>` blocks with an `IoViewer` component supporting Schema/Table/JSON tabs.
   - Implement `inferSchema(items)` (mirrors `useDataSchema.ts → getSchemaForExecutionData`).
   - Implement `convertToTable(items)` (mirrors `RunDataTable.vue → convertToTable`).
2. **Add drag sources** in Schema/Table views:
   - Add `data-target`, `data-value`, `data-path` attributes on draggable cells/rows.
   - Implement a `FlowDraggable` wrapper (mirrors `Draggable.vue`) using React mouse events.
   - Render a floating `MappingPill`-style div during drag.
3. **Add drop targets** in parameter inputs and Monaco editors:
   - Implement `FlowDraggableTarget` wrapper (mirrors `DraggableTarget.vue`).
   - For text inputs: on drop, insert expression string.
   - For Monaco: use `editor.executeEdits` to insert path at drop position.
4. **Add pin UI** in Output panel:
   - Pin/clear/edit pinned output buttons (mirror `RunDataPinButton.vue`).
   - `usePinData` React hook (mirrors `usePinnedData.ts`): `setData`, `unsetData`, `hasData`.
   - Update local `revision.pin_data` on toggle.
5. **Persist pin_data on save** (already wired) and show pinned indicator on canvas node.
6. **(Optional) Wire engine behavior** if not already implemented: pinned outputs override execution.

---

## 9. Open questions (to resolve while implementing)

- **Expression language**: do we standardize on `=` + Python-only, or also accept `{{ }}` UI sugar?
- **Path syntax**: do we expose `_json` / `_node` variables directly, or keep a "docrouter expression builder" layer?
- **Multi-output support**: current engine notes suggest multi-output is limited; pin shape should still be future-proof.
- **Pin key**: n8n keys `pinData` by node **name**; DocRouter should key by node **id** to survive
  renames — confirm the engine uses the same key.
- **Drag system**: custom mouse events (n8n approach) vs. HTML5 Drag API. Custom is more flexible
  for the floating pill, but HTML5 is simpler to implement. Decide before starting step 2.
