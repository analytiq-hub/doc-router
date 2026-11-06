# Bulk Run Flows (Actions)

Plan for a **Bulk Run Flows** action in the document Actions modal. Operators can re-run document-scoped flows across many documents with the same **missing / outdated / all** modes as **Bulk Run LLM**, using the **`docrouter.trigger`** event trigger only.

**Completion** matches the document **Flows** tab: a flow is **complete** for a document when a `flow_results` row exists for `(document_id, flow_id)` — the same JSON returned by `GET …/flows/result/{document_id}`.

**Implementation order:** Shared poll util → Phase 1 (bulk analyze API) → Phase 2 (bulk execute UI). Phase 3 (document sidebar parity) is done and serves as the execute/poll reference.

**Status:** Phase 3 document sidebar parity is **largely done** (Flows tab UX, re-run polling, URL tabs). Phases 1–2 (bulk analyze + bulk execute UI) are **not started**.

---

## Goals

1. **Backfill** flow results on existing documents after flow graph changes, tag retagging, or skipped upload-time triggers (e.g. conditional OCR plan).
2. **Re-run outdated** flows when the active flow revision is newer than the revision that produced the stored result.
3. Re-run **event-trigger** document flows from bulk actions — same path as the document UI (`rerunFlowForDocument`).
4. **Parallel execution** with the same UX patterns as `DocumentBulkRunLLM.tsx` (analyze → confirm → progress rows → cancel).
5. Align **missing / outdated / all** semantics with operator mental model from Bulk LLM, adapted to **flow version** instead of prompt version.

---

## Current behavior (baseline)

| Area | Today |
|------|--------|
| Document page URL | `/orgs/{orgId}/docs/{documentId}` with optional `?tab=extraction\|flows\|forms` (default: extraction, param omitted). Other query params preserved (e.g. `?bbox`). Implemented in `PDFSidebar.tsx`, `utils/docPageUrl.ts`. |
| Document sidebar tabs | **Extraction** (default), **Flows** (when matching flows exist), **Forms** (when matching forms exist). Tab switches update URL via `<Link replace>`; refresh restores tab. Invalid `?tab=flows\|forms` falls back to extraction after probes finish. |
| Document Flows tab | Lists flows whose **event** trigger tag filter matches the document (`list_matching_flows_for_document`). Flow rows start **collapsed** when the Flows panel is opened; expanding a row **refetches** list metadata + `GET …/flows/result/{document_id}?flow_id=…` (no list polling). |
| Captured result | `flow_results` collection; `has_captured_result` = row exists for `(document_id, flow_id)`. |
| Single re-run | `POST …/flows/{flow_id}/run/{document_id}` → `rerun_flow_for_document` — re-dispatches lifecycle event on active revision. Spinner polls **`GET …/flows/result/{document_id}?flow_id=…`** until `execution_id` matches the new run (not `GET …/executions/{id}`, which returns full `run_data` and can time out on large runs). |
| Bulk actions | No bulk flow operation in `DocumentBulkUpdate.tsx`. |
| Outdated signal in UI | Flows tab shows `flow_version` from result execution vs latest revision when expanded (`PDFFlowsSidebar`). |

### Event types (event trigger only)

`docrouter.trigger` (node type) fires on `document.uploaded`, `document.error`, `llm.completed`, `llm.error`. Bulk re-run uses the same re-dispatch logic as `rerun_flow_for_document` (including LLM context lookup for `llm.*` events).

At execution time the stored trigger `type` is **`docrouter.event`** (`DOCROUTER_EVENT_TRIGGER_KIND`); eligibility and UI still refer to the **`docrouter.trigger`** node on the revision graph.

### Result capture gate

`maybe_capture_docrouter_flow_result` only captures when:

- execution `status == success`
- `mode == "event"`
- trigger `type == docrouter.event`
- trigger has `document_id`
- trigger / `flow_triggers` row has `report_result` enabled (default true)

---

## Completion semantics (source of truth)

A document–flow pair is **complete** when:

```text
flow_results.find_one({ org_id, document_id, flow_id }) exists
```

This is exactly what the UI uses (`has_captured_result`, `getDocumentFlowResult`).

| Mode | Include pair when |
|------|-------------------|
| `missing` | No `flow_results` row for `(document_id, flow_id)`. |
| `outdated` | No `flow_results` row **or** stored result’s flow revision version &lt; active flow revision version (same as Bulk LLM). |
| `all` | Every eligible `(document_id, flow_id)` match (force re-run). |

### Outdated (flow version)

Mirror Bulk LLM’s prompt-version check:

1. Load `flow_results.execution_id` → `flow_executions.flow_revid` → `flow_revisions.flow_version` (**stored_version**). Same path as `getDocumentFlowResult` in `document_flow_sidebar.py`.
2. Load flow header `active_flow_revid` → `flow_revisions.flow_version` (**active_version**). Use the **revision** document, not `flows.flow_version` on the header (header can drift).
3. **Outdated** when `stored_version < active_version`.

Edge cases:

- Flow **inactive** → exclude from bulk analyze (cannot enqueue; same rule as `rerun_flow_for_document`).
- No `active_flow_revid` → exclude.
- `report_result=false` on trigger → exclude from bulk (no document Flows result expected; optional admin override later).
- `execution_id` missing or revision deleted → treat as **outdated** (re-run on active revision).
- Execution **queued/running** for same flow+doc → v1: allow duplicate enqueue (same as Bulk LLM).

### Eligibility (which pairs exist)

**Event trigger (`docrouter.trigger`):**

- Flow is **active** with valid `active_flow_revid`.
- Revision has a non-disabled `docrouter.trigger` node with `report_result` not false.
- Document `tag_ids` overlap trigger `tag_ids` (`tag_filter_matches_document` — same helper as dispatch).
- Optional **anchor tag** (bulk UI): trigger `tag_ids` must include anchor tag **and** document must match trigger tag filter.
- Multiple `docrouter.trigger` nodes on one revision → use the same rule as `list_matching_flows_for_document` / `_event_type_from_revision` (first non-disabled matching node).

### Bulk vs document Flows tab (intentional differences)

| Rule | Document Flows tab | Bulk analyze |
|------|-------------------|--------------|
| Inactive flows | Shown; re-run disabled | Excluded |
| `report_result=false` | Still listed | Excluded |

Bulk UI should note: **“Only active flows with result capture enabled.”** Operators may see a flow on a document page that does not appear in bulk.

### `llm.completed` / `llm.error` prerequisites

**Policy (v1): sidebar parity.** Bulk analyze includes eligible pairs even when no matching `llm_runs` row exists. `rerun_flow_for_document` best-effort loads LLM context (`_latest_llm_context_for_flow_rerun`); runs may fail or time out without a prior LLM result. Operators typically run **Bulk LLM** first, then bulk **missing** for `llm.*` flows (see conditional OCR section).

### Flow discovery inputs

Analyze requires **at least one** of `flow_ids` (non-empty) or `tag_id`. API returns `400` if neither is set. UI disables Analyze until the operator picks flows and/or an anchor tag.

When **both** are set:

- **`tag_id`** — merged into `document_filters.tag_ids` (narrows documents) and contributes to flow discovery.
- **`flow_ids`** — explicit candidate set.
- **Resulting flows** = `flow_ids ∩ discover_event_flows_for_tag(tag_id)` (intersection, not union). Flows outside the intersection are omitted.

When **only `flow_ids`** — use those flows (active, org-scoped); documents from grid filters only.

When **only `tag_id`** — discover flows from `flow_triggers`; documents narrowed by anchor tag + grid filters.

---

## Target behavior

### Actions modal — new **Flows** group

Add **Run Flows** under a **Flows** group in `DocumentBulkUpdate.tsx`.

**Inputs** (same document preview grid as other bulk actions):

| Control | Purpose |
|---------|---------|
| Document filter | Inherited from grid: name search, tag filters, metadata search. |
| Anchor tag (optional) | When set: added to document tag filter; discovers **event** flows via `flow_triggers`. Required if no flows selected in picker. |
| Flow picker (multi) | Select flows to run. Auto-suggested from anchor tag. Required if no anchor tag. When both set, analyze uses **intersection**. |
| Execution mode | `outdated` (default) \| `missing` \| `all` — same labels as Bulk Run LLM. |
| Parallel runs | Reuse `runWithConcurrency` + session key (default 2 for flows; configurable). |

**Analyze step:** call bulk-analyze API → show grouped rows by flow (like prompt groups in Bulk LLM).

**Execute step:** for each `(flow_id, document_id)` enqueue run, poll until `flow_results.execution_id` matches the new execution, refresh progress rows.

**Progress UI:** per row `pending | running | completed | error | cancelled`; show `flow_name`, `document_name`, optional `reason` (`missing`, `outdated`, `forced`).

### Execute path (per pair)

| Trigger type | API | Notes |
|--------------|-----|-------|
| `docrouter.trigger` | `POST …/flows/{flow_id}/run/{document_id}` | Existing `rerun_flow_for_document`. |

**Poll for completion (recommended — matches document Flows tab):**

```typescript
// Lightweight; safe for large run_data graphs (OCR splits, etc.)
GET …/flows/result/{document_id}?flow_id={flow_id}
// Done when result.execution_id === newExecutionId
```

Do **not** poll `GET …/flows/{flow_id}/executions/{execution_id}` in a tight loop for progress — that endpoint includes full `run_data` and can hit the 60s HTTP timeout on heavy runs.

**Success** for progress row: `flow_results.execution_id` matches the enqueued execution (same as sidebar re-run).

**Error** when poll times out (e.g. 180s) or enqueue fails. Note: `maybe_capture_docrouter_flow_result` only upserts on `status == success`; a failed execution leaves the old `execution_id` in `flow_results`, so the poll never matches and the row ends in **error** (indistinguishable from a slow run in v1). v2: lightweight execution status endpoint to fail fast on terminal errors.

---

## Phase 0 — Shared poll util (before Phase 2)

Extract `pollFlowRerunUntilDone` from `PDFFlowsSidebar.tsx` into `utils/flowRerunPoll.ts` (shared `POLL_MS` = 600, `MAX_WAIT_MS` = 180_000, 404-tolerant). Import from both sidebar and bulk component so poll semantics stay in sync.

---

## Phase 1 — Bulk analyze API

Mirror `analytiq_data/llm/bulk_analyze.py` → `analytiq_data/docrouter_flows/bulk_analyze.py`.

### Endpoint

```text
POST /v0/orgs/{organization_id}/flows/bulk-analyze
Body: {
  mode: "all" | "missing" | "outdated",
  tag_id?: string,                    // anchor tag for event-flow discovery + doc filter
  flow_ids?: string[],                // explicit event-trigger flows
  document_filters: {
    tag_ids?: string[],
    name_search?: string,
    metadata_search?: Record<string, string>,
    filters?: Record<string, unknown>
  }
}
Response: {
  total_executions: int,
  groups: [
    {
      flow_id: string,
      flow_name: string,
      flow_version: int,              // active revision version
      event_type?: string,
      executions: [
        { document_id, document_name, reason?: "missing" | "outdated" | "forced" }
      ]
    }
  ]
}
```

### Validation

- `400` if neither `tag_id` nor non-empty `flow_ids` is provided.

### Logic

1. Validate discovery inputs (above).
2. `list_all_matching_docs(...)` — merge `document_filters.tag_ids` with optional `tag_id`.
3. **Discover flows** (via `flow_triggers`, not a full `flows` collection scan):
   - `discovered = discover_event_flows_for_tag(db, org_id, tag_id)` when `tag_id` set — query `flow_triggers` where `org_id` matches, `tag_ids` contains `tag_id`, and `report_result != false`; join to **active** flow headers with valid `active_flow_revid`.
   - `explicit = flow_ids` (org-scoped, active only) when `flow_ids` set.
   - **Candidate flows:** `explicit` only, `discovered` only, or `explicit ∩ discovered` when both set.
4. For each candidate flow, load active revision + matching `flow_triggers` row; skip if no valid trigger or `report_result=false`. Populate group `event_type` from `flow_triggers.event_type`.
5. For each document × flow: skip if `!tag_filter_matches_document(trigger.tag_ids, doc.tag_ids)`.
6. Batch-load `flow_results` for all `(doc_ids × flow_ids)` — no per-pair queries.
7. For `outdated`, batch-resolve stored `flow_version` from `execution_id` (single aggregation on `flow_executions` + `flow_revisions`).
8. Apply mode filter via `flow_pair_needs_run`; attach `reason` (`missing`, `outdated`, `forced` for `all`); build `groups` (omit empty groups).

### Helpers (new)

```python
async def get_active_flow_trigger_info(db, org_id, flow_id) -> FlowTriggerInfo | None
async def discover_event_flows_for_tag(db, org_id, tag_id) -> list[str]  # flow_triggers query + active header join
async def batch_flow_result_stored_versions(db, execution_ids: list[str]) -> dict[str, int]
def flow_pair_needs_run(mode, has_result, stored_version, active_version) -> bool
```

---

## Phase 2 — Bulk execute UI

### Frontend files

| File | Change |
|------|--------|
| `utils/flowRerunPoll.ts` | Shared poll helper (extracted from sidebar) |
| `PDFFlowsSidebar.tsx` | Import shared poll util |
| `DocumentBulkRunFlows.tsx` | New; clone structure from `DocumentBulkRunLLM.tsx` |
| `DocumentBulkUpdate.tsx` | Add `runFlowsOperations` under **Flows** group |
| `docrouter-org.ts` / SDK | `bulkAnalyzeFlows`, types |
| `app/routes/flows.py` | `bulk-analyze` route |

### Execute (frontend-driven v1)

No server-side bulk-enqueue required initially:

```typescript
const { execution_id } = await api.rerunFlowForDocument(flowId, documentId);
// Poll getFlowDocumentResult until execution_id matches (see Execute path above)
```

Import `pollFlowRerunUntilDone` from `utils/flowRerunPoll.ts`.

**Parallelism:** default **2** (flows are heavier than LLM calls); persist in `docrouter.bulkFlowParallelRuns` session key.

### UX patterns (copy from `DocumentBulkRunLLM.tsx`)

- `runWithConcurrency` worker pool with cancel support.
- `analyzeGenerationRef` / `isCancelledRef` — stale analyze and mid-run cancel.
- `analysisAbortController` for in-flight analyze requests.
- Session-stored parallel run count with clamp (min 1, max 50).
- Analyze disabled until `tag_id` and/or flow picker satisfied.
- Helper text: active flows with result capture only; for `llm.*` flows, run LLM first when needed.

### Tests (Phase 1 + 2)

- `missing`: doc with no `flow_results` included; with result excluded.
- `outdated`: stored `flow_version` &lt; active included; current excluded; uses revision version not header.
- `all`: all eligible pairs included with `reason: forced`.
- Event flow: doc without matching tags excluded.
- Inactive flow excluded.
- `report_result=false` flow excluded (via `flow_triggers` / revision check).
- Respect document grid filters.
- Anchor tag narrows documents and contributes to flow discovery.
- `flow_ids` only — explicit flows, no tag discovery.
- `tag_id` only — discovers via `flow_triggers`.
- `flow_ids` + `tag_id` — **intersection**; empty intersection → zero executions.
- Neither `flow_ids` nor `tag_id` → `400`.
- `llm.completed` flow on doc without `llm_runs` — included in analyze (sidebar parity); document expected execute behavior.
- Multiple trigger nodes — same first-match rule as sidebar.
- Large doc set — batch `flow_results` load + version aggregation (no N+1).

---

## Phase 3 — Document sidebar parity

**Status: implemented** (reference for bulk UX and polling).

### Document page URL tabs

| URL | Sidebar panel |
|-----|----------------|
| `/orgs/{orgId}/docs/{docId}` | Extraction (default) |
| `?tab=flows` | Flows |
| `?tab=forms` | Forms |

- Helpers: `utils/docPageUrl.ts` (`sidebarTabFromQuery`, `docPageHref`, `docPageHrefWithSearch`).
- `PDFSidebar.tsx`: tab links update URL; invalid tab redirected to extraction after flow/form probes resolve.
- Wrap `PDFSidebar` in `Suspense` on the doc page (required for `useSearchParams`).

### Flows tab (`PDFFlowsSidebar.tsx`)

| Behavior | Detail |
|----------|--------|
| List on load | `GET …/flows?document_id=…`; show tab when `items.length > 0`. |
| Collapsed by default | All flow accordion rows collapsed when Flows panel opens (`panelActive`); no auto-expand first flow. |
| Expand → fetch | Manual expand clears cached result, refreshes flow list, fetches `GET …/flows/result/…`. |
| Re-run spinner | `POST …/run/{document_id}` then poll `getFlowDocumentResult` until `execution_id` matches; generation token cancels stale polls. |
| Version badge | Header shows `(vN)` from result revision when expanded, else latest revision. |
| Inactive flows | Shown in list; re-run disabled; “Inactive” badge. |

Parity with **Extraction** tab: collapsed until expand, fetch-on-expand, no background list polling.

---

## Interaction with conditional OCR plan

When uploads skip OCR and stay `uploaded`:

- `document.uploaded` still fires → event flows on that trigger still run at upload.
- Flows on `llm.completed` **do not** run until LLM runs → bulk **missing** mode backfills those pairs after Bulk LLM / manual LLM.

Bulk Run Flows is the operator tool to **catch up** documents that missed event-driven runs.

---

## Out of scope (v1)

- Server-side `POST …/flows/bulk-run` enqueue (fewer HTTP round-trips) — optional later.
- Flows without `report_result` / sub-flow-only flows.
- Polling webhook on flow completion.
- Auto-run on flow activation (separate backfill product decision).
- `flows.trigger.webhook` / schedule / chat triggers — DocRouter document triggers only.
- Deep-link expanded flow row (`?tab=flows&flow={flowId}`) or prompt row — optional later.

---

## File checklist

### Phase 0

- [ ] `utils/flowRerunPoll.ts` — extract `pollFlowRerunUntilDone`
- [ ] `PDFFlowsSidebar.tsx` — use shared poll util

### Phase 1

- [ ] `docrouter_flows/bulk_analyze.py`
- [ ] `app/routes/flows.py` — `bulk-analyze` route
- [ ] `tests/flows/test_bulk_analyze_flows.py`

### Phase 2

- [ ] `DocumentBulkRunFlows.tsx`
- [ ] `DocumentBulkUpdate.tsx`
- [ ] SDK: `bulkAnalyzeFlows`, types

### Phase 3

- [x] `PDFFlowsSidebar.tsx` — list, expand fetch, re-run poll, version badge, inactive handling
- [x] `PDFSidebar.tsx` — Extraction / Flows / Forms tabs, URL sync
- [x] `utils/docPageUrl.ts` — `?tab=` helpers
- [x] `PDFFormsTabProbe.tsx` — forms tab visibility probe
- [x] Doc page `Suspense` wrapper for sidebar

---

## Reference

- Bulk LLM: `DocumentBulkRunLLM.tsx`, `analytiq_data/llm/bulk_analyze.py`
- Bulk OCR (parallel pattern): `DocumentBulkRunOCR.tsx`, `analytiq_data/ocr/bulk_analyze.py`
- Flow results: `flow_results.py`, `GET …/flows/result/{document_id}`
- Event re-run: `rerun_flow_for_document` in `document_flow_sidebar.py`
- Tag match: `tag_filter_matches_document` in `event_dispatch.py`
- Flow trigger index: `flow_triggers` collection, `sync_docrouter_flow_triggers` in `event_dispatch.py`
- Document Flows UI: `PDFFlowsSidebar.tsx`, `PDFSidebar.tsx`, `list_matching_flows_for_document`
- Document flow integration: `docs/docrouter_doc_flow_integration.md`
