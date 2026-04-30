# Flows UI — Logs panel improvements (plan)

This doc describes the next set of improvements for the **in-editor Logs panel** (`FlowLogsPanel.tsx`) to better match the UX patterns from the reference implementation in the sibling `n8n` repo.

## Goals

- Match the **Overview / Details** mental model used by `n8n` executions UI.
- In **Details**, render both **Parameters** and **Results** with a viewer that supports **Schema / Table / JSON** modes (like `n8n`’s run data display).
- Trigger nodes should **only display Results** (no Parameters/Inputs).
- Add an **Edit node** action (like `n8n`’s “open settings” / edit icon), but **do not** implement “start node”/trigger execution buttons.

## Reference notes (from `../n8n`)

- **Execution preview view**: `n8n/packages/editor-ui/src/views/WorkflowExecutionsView.vue`
  - Shows a left execution list and a right preview.
  - Uses auto-refresh while executions are active.
- **Run data viewer**: `n8n/packages/editor-ui/src/components/RunData.vue`
  - Supports **display modes** (Schema/Table/JSON, plus others like Binary/HTML in some cases).
  - Has a notion of **trigger nodes** (different layout: trigger doesn’t show the same input pane).
- **Table + JSON** implementations:
  - Table: `n8n/packages/editor-ui/src/components/RunDataTable.vue`
  - JSON: `n8n/packages/editor-ui/src/components/RunDataJson.vue`
- **“Edit/open settings” affordance** is wired through NDV panels via `open-settings` events (see `OutputPanel.vue` and `NodeDetailsView.vue`), which ultimately opens the node settings panel for the active node.

## Current DocRouter implementation (today)

- `packages/typescript/frontend/src/components/flows/FlowLogsPanel.tsx`
  - One expandable bottom panel with:
    - A run summary header.
    - A list of node run entries.
    - Per-node “Details” expansion that renders **Input** and **Output** using `JSON.stringify(...)` inside `<pre>`.
- `packages/typescript/frontend/src/components/flows/IoViewer.tsx`
  - Already provides a reusable viewer with **Schema / Table / JSON** modes and drag-to-expression support.
- `packages/typescript/frontend/src/components/flows/FlowNodeConfigModal.tsx`
  - Already provides richer per-node UI (parameters + IO) but is optimized for the editor modal and includes pinning/edit affordances.

## Proposed UX changes

### 1) Logs panel: two tabs (Overview / Details)

- Add a small tab switcher in the Logs panel (top right of the panel header area):
  - **Overview**: run-level summary + node list (status/timing). Selecting a node updates the selected node id.
  - **Details**: shows a structured view for the **selected node**.

Notes:
- The Logs panel should remember the last selected tab for the current execution (local component state is fine).
- If no node is selected, Details shows an empty state (“Select a node”).
- Clicking a node in the Overview node list should **select that node and open Details** immediately (no per-row “Details” button).

### 2) Details layout and viewers (Schema/Table/JSON)

In Details, show two sections similar to `n8n`’s “INPUT / OUTPUT” panes, but adapted to our data model:

- **INPUT**
  - Value source: the node’s **current graph node definition** (from `graphNodes` / `FlowNode.parameters`, plus maybe `disabled`, `on_error`, etc.).
  - Render with `IoViewer` so the user can switch **Schema/Table/JSON**.
  - This is *not* the same as input items; it’s the node configuration snapshot.

- **OUTPUT**
  - Value source: the node’s run output items derived from `run_data` (we already compute these in `buildNodeOutputPreview`).
  - Render with `IoViewer` so the user can switch **Schema/Table/JSON**.
  - Use the same “first item as sample” semantics as `IoViewer` for Schema/JSON, and treat arrays of objects as Table.

Trigger-node special case:
- If the selected node’s type is a trigger (`FlowNodeType.is_trigger === true`), **hide INPUT** and only show **OUTPUT**.

### 3) Edit node button (no trigger/start buttons)

Add an **Edit** icon/button in the Details header (next to the node name), mirroring `n8n`’s “open settings” affordance.

- Clicking **Edit** should open the node configuration UI in an editable state.
- Implementation approach:
  - Add a callback prop to `FlowLogsPanel` like `onEditNode?: (nodeId: string) => void`.
  - In `FlowDetailPageClient.tsx`, wire it to:
    - switch view to `tab=editor`
    - focus/select the node on canvas
    - open the node configuration modal for that node (requires `FlowEditor` to accept a controlled “open config modal” node id, or expose an imperative API).

Explicit non-goals:
- Do **not** add “execute node / start trigger” buttons here (n8n has them in some trigger contexts).

## Implementation steps (suggested order)

1. **Refactor `FlowLogsPanel.tsx` state model**
   - Add `activeTab: 'overview' | 'details'`
   - Add `selectedNodeId` (separate from the existing `detailsNodeId` pattern)
   - Keep existing polling behavior.

2. **Implement Overview tab UI**
   - Use the existing node run entry list, but make rows selectable (single selection).
   - Remove per-row “Details” button/expansion; clicking a row should set `selectedNodeId` and switch to the Details tab.

3. **Implement Details tab UI**
   - Compute:
     - `selectedNode` (from `graphNodes`)
     - `selectedNodeType` (from `graphNodes` data or `nodeTypes` mapping if needed)
     - `nodeParametersValue` (object: `selectedNode.data.flowNode.parameters` plus key metadata)
     - `nodeResultsValue` (array/object from `run_data`, using existing preview builders)
   - Render:
     - `IoViewer` for INPUT (unless trigger node)
     - `IoViewer` for OUTPUT
   - Add empty states for missing data (no run data yet, node not found in graph, etc.).

4. **Add Edit node action plumbing**
   - Add `onEditNode` prop to `FlowLogsPanel`.
   - Add `onEditNode` handler in `FlowDetailPageClient.tsx`.
   - Extend `FlowEditor` API to open the node config modal programmatically:
     - Option A (preferred): add props `configOpenNodeId?: string | null` + `onConfigOpenNodeIdChange?`
     - Option B: expose an imperative ref API.

5. **Trigger node behavior**
   - Ensure trigger nodes only show Results in Details.

6. **QA checklist**
   - Run a flow, open logs, switch Overview/Details.
   - Select a node and view Parameters/Results in Schema/Table/JSON.
   - Verify Table mode shows a table for arrays of objects; otherwise shows “Not a table” message.
   - Trigger node shows Results only.
   - Edit button opens the node config modal in the editor (and does nothing in read-only contexts, if applicable).

## Files expected to change

- `packages/typescript/frontend/src/components/flows/FlowLogsPanel.tsx`
- `packages/typescript/frontend/src/components/flows/IoViewer.tsx` (likely **no changes**, but may need small props to better match the UX)
- `packages/typescript/frontend/src/app/orgs/[organizationId]/flows/[flowId]/FlowDetailPageClient.tsx`
- `packages/typescript/frontend/src/components/flows/FlowEditor.tsx` (to support programmatic open of node config modal)

