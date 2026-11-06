# Flow executions deep link & filtering

Plan to fix **“Last run”** links from the document Flows sidebar and add **execution list filtering** on the per-flow **Executions** tab — so operators can jump straight to a run and narrow a long history.

**Reference UI (read first):** sibling tree `../n8n` → `packages/frontend/editor-ui/src/features/execution/executions/` (`WorkflowExecutionsView.vue`, `ExecutionsFilter.vue`, `executions.store.ts`). Use for behavior and layout only; do not copy naming.

**Status:** Not started.

---

## Problem

1. **Document sidebar → flow run:** `PDFFlowsSidebar` links “Last run …” to  
   `/orgs/{orgId}/flows/{flowId}?tab=executions`  
   even when `resultRow.execution_id` is known. The Executions tab opens on the **latest page-1 row** (auto-selects first list item), not the run that produced the document result.

2. **No filters on per-flow executions:** `FlowExecutionsView` loads `GET …/executions?flow_id=…` with pagination only. The API already accepts `status` and `mode` query params; the UI does not expose them.

3. **Deep-linked run can disappear:** If the target `execution_id` is not in the current page, `FlowExecutionsView` resets selection to `list[0]` — the user loses the intended run entirely.

---

## Goals

1. **Deep link** from document Flows tab (and anywhere else we have `flow_id` + `execution_id`) to that execution’s detail + logs on the flow Executions tab.
2. **Shareable URL** — refresh and copy-link preserve the focused execution.
3. **Filter** the per-flow execution list (phase 1: status + mode; phase 2: document + date range as needed).
4. **Keep editor tab URLs stable** — `?tab=editor` unchanged; execution param only matters on Executions tab.

---

## Current behavior (baseline)

| Area | Today |
|------|--------|
| Flow detail URL | `/orgs/{orgId}/flows/{flowId}?tab=editor\|executions` (`FlowDetailPageClient`, `tabFromQuery`). |
| Document “Last run” link | `PDFFlowsSidebar.tsx` → `?tab=executions` only (ignores `execution_id`). |
| Executions list | `FlowExecutionsView` → `listExecutions({ flowId, limit, offset })`. |
| Selection | On load, auto-selects first row unless user cleared selection. |
| Execution detail | `getExecution(flowId, executionId)` — works regardless of list page. |
| List API | `GET /v0/orgs/{orgId}/executions` with optional `flow_id`, `status`, `mode`, `limit`, `offset` (`flows.py` `list_executions`). |
| Org-wide executions | `FlowExecutionsAll` — same list API, no filters in UI. |

### Execution modes (for filters)

From `ExecutionContext.mode`: `manual`, `event`, `trigger`, `webhook`, `schedule`, `error`, `sub_flow`, `sub_flow_tool`, `chat`.

Document-scoped runs from bulk/sidebar re-run use **`event`** (trigger type `docrouter.event`, `trigger.document_id` set).

### Execution statuses (for filters)

`queued`, `running`, `success`, `error`, `stopped`, `interrupted` (`FlowExecutionStatus`).

---

## Reference: how the sibling workflow editor handles this

Patterns worth mirroring (neutral summary):

| Concern | Approach |
|---------|----------|
| **URL** | Execution id in the **route**, not only query: `/workflow/{workflowId}/executions/{executionId}` with optional `/{nodeId}` for node focus. |
| **Load** | `fetchExecution(executionId)` on route change **independently** of the list; merged with list row when present. |
| **Default** | If user lands on executions home with no id, redirect to first list item. |
| **Filters** | Popover filter panel (`ExecutionsFilter`): **status**, **date range**, **workflow version**, custom **metadata** key/value (EE), annotation tags/vote (EE). Debounced emit → store → `fetchExecutions` with query filter. |
| **Refresh** | Manual refresh + optional auto-refresh while tab visible. |

### DocRouter delta (intentional simplifications)

- Use **query param** `execution` on the existing flow detail URL instead of a nested route segment (smaller Next.js change):  
  `/orgs/{orgId}/flows/{flowId}?tab=executions&execution={executionId}`
- Phase 1 filters: **status** + **mode** only (API already supports both).
- Defer workflow-version filter until we expose revision labels in list API (n8n’s `workflowVersionId` filter).
- Defer custom metadata / annotation filters (not in our execution model today).

---

## Proposed URL & navigation

### Query parameters

| Param | Values | Notes |
|-------|--------|--------|
| `tab` | `editor` (default), `executions` | Existing. |
| `execution` | Mongo execution `_id` string | Optional. When `tab=executions`, open this run. Omit when no selection or user clears focus. |

Helper (new): `utils/flowPageUrl.ts`

```ts
flowPageHref(orgId, flowId, { tab?, execution? }, searchParams?)
```

- Preserves unrelated query keys when updating tab/execution.
- `execution` stripped when switching to `tab=editor`.

### Link updates

| Source | New href |
|--------|----------|
| `PDFFlowsSidebar` “Last run …” | `?tab=executions&execution={resultRow.execution_id}` |
| Future: logs panel “open in executions” | same pattern |
| `FlowExecutionsView` row click | `router.replace` with updated `execution` (avoid history spam) |

---

## UI behavior (per-flow Executions tab)

### Deep link / focus execution

1. `FlowDetailPageClient` reads `searchParams.get('execution')` and passes `focusExecutionId` to `FlowExecutionsView`.
2. On mount or `focusExecutionId` change:
   - Set `selectedId` to that id.
   - Call `getExecution` + load graph/logs (existing `loadDetailAndGraph`).
   - Do **not** replace selection with `list[0]` when the id is absent from the current page.
3. If `getExecution` returns 404 → show inline error; clear invalid `execution` from URL.
4. Optional polish: if focused run is not in `list`, show a slim banner above the list (“Showing run from link — may not be on this page”) and still render detail pane.

### Selection ↔ URL sync

- User clicks a list row → update `execution` query param.
- User clears focus in logs panel → remove `execution` param.
- Pagination change does not clear `execution` if that run is still the selection.

### Filters (phase 1)

Compact filter row under the “Executions” header (or filter popover if space is tight):

| Filter | UI | API |
|--------|-----|-----|
| Status | `All` + each `FlowExecutionStatus` | `status` query param |
| Mode | `All` + known modes | `mode` query param |

Behavior:

- Changing filter resets `page` to 0 and reloads list.
- Filters encoded in URL (recommended): `status=success&mode=event` so links are shareable.
- Badge/count of active filters (non-default) like the reference popover.

### Filters (phase 2 — optional)

| Filter | Needs |
|--------|--------|
| **Document** | `document_id` query on `list_executions` filtering `trigger.document_id` (index). High value for event flows. |
| **Date range** | `started_after` / `started_before` on list API + UI date pickers. |
| **Revision / version** | Join `flow_revisions` or expose `flow_version` on list items; filter `flow_revid` or version. |

---

## Backend changes

### Phase 0 — none required for deep link

`getExecution` already loads any run by id for the flow.

### Phase 1 — optional list hardening

- **`execution_id` lookup:** optional `GET …/executions?execution_id=…&flow_id=…` (limit 1) to validate deep links without full detail payload — *or* rely on `getExecution` only (frontend-only phase 0).

### Phase 2 — document filter

```python
# list_executions query extension
if document_id:
    query["trigger.document_id"] = document_id
```

Ensure index on `(organization_id, flow_id, trigger.document_id, started_at)` or reuse existing `started_at` sort with partial filter.

### Phase 2 — date range

```python
if started_after:
    query["started_at"] = {"$gte": parse_iso(started_after)}
if started_before:
    query.setdefault("started_at", {})["$lte"] = parse_iso(started_before)
```

---

## Frontend implementation phases

### Phase 0 — Deep link (MVP)

| File | Change |
|------|--------|
| `utils/flowPageUrl.ts` | New URL helpers. |
| `PDFFlowsSidebar.tsx` | Last-run `Link` includes `execution`. |
| `FlowDetailPageClient.tsx` | Read/pass `focusExecutionId`; preserve `execution` in `handleViewChange` when opening Executions. |
| `FlowExecutionsView.tsx` | Accept `focusExecutionId`, `onFocusExecutionIdChange`; fix auto-select logic; sync URL on selection. |

**Acceptance**

- Click “Last run” on document Flows tab → Executions tab opens with **that** run selected, logs visible.
- URL contains `execution=…`; reload keeps the same run.
- Run not on page 1 still opens correctly.

### Phase 1 — Status & mode filters

| File | Change |
|------|--------|
| `FlowExecutionsView.tsx` | Filter controls; pass `status`/`mode` to `listExecutions`; URL sync. |
| `flowPageUrl.ts` | Include filter params. |
| `FlowExecutionsAll.tsx` | (Optional) same status/mode filters for org-wide list. |

**Acceptance**

- Filter to `mode=event` shows document-triggered runs only.
- Filter + deep link compose: `?tab=executions&execution=…&mode=event`.

### Phase 2 — Document & date filters

- Backend query params + tests.
- Filter UI; link from document page could pre-fill `document_id` when opening flow executions (stretch).

---

## Tests

### Python

- `list_executions` with `status`, `mode` (may already be covered — add if missing).
- Phase 2: `document_id`, `started_after` / `started_before` filters.

### Frontend

- `flowPageUrl.ts` unit tests (build href, preserve params, strip `execution` on editor tab).
- `FlowExecutionsView`: deep-linked id not in mocked list still calls `getExecution` and keeps selection.
- Filter change resets page and updates API params.

### Manual

1. Document with flow result → expand Flows → click Last run → correct execution + logs.
2. Copy URL → new tab → same execution.
3. Paginate list while deep-linked → selection unchanged.
4. Apply status/mode filters → list narrows; deep link still works when run matches filter.

---

## Out of scope (for now)

- Nested Next.js route `/flows/[flowId]/executions/[executionId]` (query param is enough).
- Bulk delete / stop-by-filter (n8n has stop-many with filter; we only have per-row stop today).
- Execution annotation tags / vote filters.
- Auto-refresh polling on Executions tab (nice follow-up; editor logs already poll in some paths).

---

## Open questions

1. **Param name:** `execution` vs `executionId` — prefer short `execution` for URLs; align with existing `logsFocusExecutionId` state naming internally.
2. **Org-wide executions page:** apply same filter UX in `FlowExecutionsAll` in phase 1 or defer?
3. **Document filter discoverability:** should “Last run” also pass `mode=event` or `document_id` in the URL for context, or only `execution`?

---

## Checklist

- [ ] `docs/flow_executions_deep_link_plan.md` (this file)
- [ ] Phase 0: URL helper + sidebar link + focus execution without list reset
- [ ] Phase 1: status/mode filters (API wired in UI)
- [ ] Phase 2: document + date filters (API + UI)
- [ ] Unit tests per phase
