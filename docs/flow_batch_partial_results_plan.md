# Batch node partial results: persist on error/interrupt + canvas progress

Plan to save **all completed item output** when a batch node (OCR, LLM, etc.) finishes, errors on an item, is cooperatively stopped, or the worker is interrupted — and to show **completed/total item count** on the executions canvas.

**Reference:** n8n sibling tree `../n8n` (read-only for behavior; do not copy naming).

**Implementation order:** Phase 1 → Phase 2 → Phase 3 (all shipped).

---

## Implementation status (Jul 2026)

| Phase | Status | Summary |
|-------|--------|---------|
| **1** | Shipped | Wave checkpoints, cooperative-stop persist, recovery `partial`, Executions + Editor `N/M` badge |
| **2** | Shipped | Per-item error isolation, partial persist on error, engine merge keeps `data.main` |
| **3** | Shipped | Item skip on resume, `rerunFlowForDocument` `mode`, bulk + sidebar UI |

### Shipped backend

| Module | What |
|--------|------|
| `flows/item_batch.py` | `on_items_checkpoint`, `continue_on_item_error`, `FlowBatchItemErrors`, `on_fatal_item_error` |
| `flows/batch_progress.py` | `persist_batch_node_partial`, resume helpers, fatal-error callback |
| `flows/engine.py` | Error path merges partial `data.main`; preserves `items_skipped_on_resume` on success |
| `flows/recovery.py` | `running` → `partial` on interrupt; `last_node_executed` in recovery projection |
| `flows/resume.py` | `find_resumable_batch_execution` |
| `docrouter_flows/nodes/ocr_node.py`, `llm_node.py` | Checkpoints, resume skip, error persist |
| `docrouter_flows/document_flow_sidebar.py` | `rerun_flow_for_document(..., mode=force\|incomplete_only)` |
| `app/routes/flows.py` | `RerunFlowForDocumentRequest` body |

### Shipped frontend

| Module | What |
|--------|------|
| `flowNodeRunStatus.ts` | `getNodeBatchProgressFromRunData`, `partial` status |
| `FlowCanvasNode.tsx` | `N/M` badge on **top edge** (rounded rect); live from `execution.run_data` in Editor + Executions |
| `FlowExecutionsView.tsx` | Lightweight poll refresh via `onExecutionChange` |
| `flowResume.ts` | Resume label with remaining items |
| `FlowLogsPanel.tsx` | Uses `resumeExecutionLabel` |
| `DocumentBulkRunFlows.tsx` | Rerun mode radio (force / incomplete only), sessionStorage |
| `PDFFlowsSidebar.tsx` | Uses same sessionStorage rerun mode |
| `sdk/docrouter-org.ts` | `rerunFlowForDocument(..., { mode })` |

### Tests

- `test_docrouter_item_batch.py`, `test_flow_batch_progress.py`, `test_flow_execution_recovery.py`
- `test_flow_batch_partial_phase2_3.py`
- `flowNodeRunStatus.spec.ts`, `flowResume.spec.ts`

### UI notes (post-implementation)

- **Node badge:** `10/13` on top edge of batch node (not on arrows).
- **Arrow labels:** existing `N items` from `len(data.main[0])` — completed count only, not `N/M`.
- **Editor:** badge updates via logs-panel poll + `FlowExecutionVisualProvider` (no WebSocket).

---

## How n8n handles this

n8n’s model is **node-atomic**, not item-atomic:

| Aspect | n8n behavior |
|--------|----------------|
| **Unit of scheduling** | One node invocation at a time; items are arrays passed into `execute()` |
| **Mid-loop checkpoint** | **No** — if a node throws mid-internal-loop, no item progress is saved for that node |
| **Partial on error** | **Upstream completed nodes** stay in `runData`; failing node gets `executionStatus: error`, usually **empty output** |
| **Item-level partial success** | Only if the **node implementation** returns a mix of success/error items in one response (e.g. `onError: continueErrorOutput` routing) |
| **Persistence timing** | Optional `saveExecutionProgress` after **each completed node** (full `IRunExecutionData` snapshot, `status: running`) |
| **Worker crash** | Queue recovery marks execution `crashed`; retains last DB snapshot if progress saves were enabled |
| **Canvas UI** | WebSocket `nodeExecuteBefore` → running spinner; `nodeExecuteAfter` → item counts on **edges**; **no per-item progress inside the node** |
| **Explicit batching** | Loop Over Items (`SplitInBatches`) re-enters the node with multiple `runIndex` entries — batching is a **graph pattern**, not engine item checkpointing |

**Takeaway for DocRouter:** n8n does **not** save half-finished item batches on error either. Our gap is larger because we batch hundreds of items **inside** one node (`map_flow_items_batch`) and only persist once at the end. Adopting **full partial snapshots at defined trigger points** plus **item counters on the canvas** is the right direction; true item-resume requires new engine work n8n also lacks.

---

## DocRouter before this work (historical)

| Scenario | `run_data[node_id]` (before) |
|----------|------------------------------|
| All items succeed | Full `data.main` at node end; checkpoint in `completed_nodes` |
| **Cooperative stop** mid-batch | Partial items; persisted only when `execute()` returned |
| **Error** on one item | Node `status: error`, **`data.main: []`** |
| **Worker interrupt** mid-batch | Current node **absent** from `run_data` |

## DocRouter after (current)

| Scenario | `run_data[node_id]` |
|----------|---------------------|
| All items succeed | Full `data.main`; checkpoint in `completed_nodes` |
| **Cooperative stop** | Partial items + counters; final persist on return |
| **Error** on item(s) | `status: error`, **partial `data.main`**, `items_failed`, error envelope |
| **Worker interrupt** | Last wave checkpoint; recovery sets `status: partial` |
| **Resume (Phase 3)** | Skips completed `meta.item_index`; `items_skipped_on_resume` on success |

---

## Goals

1. **Persist all completed items** when a batch node errors on an item (not only on cooperative stop).
2. **Persist all completed items** when a worker dies mid-batch (best-effort via last checkpoint).
3. **Persist all completed items** on cooperative stop (explicit snapshot before node returns).
4. **Persist all completed items** at normal node completion (existing final persist; authoritative).
5. **Show `completed/total`** on the executions canvas while a batch node is running and after partial completion.
6. **Bulk rerun choice** (Phase 3): force full rerun vs rerun incomplete items only.
7. **Preserve** upstream checkpoints, billing, and binary blob storage semantics.
8. **Align with n8n UX** where reasonable (running node, item counts) without copying their WebSocket stack in Phase 1.

---

## Non-goals (initial phases)

- Changing n8n-style graph batching (SplitInBatches equivalent).
- Live WebSocket push for editor “Execute flow” (poll-only for executions view in Phase 1).
- Partial persist for **non-batch** per-item engine loop (lower priority; different code path).
- Mid-node checkpoints for nodes with **sequential** processing (`batch_size` unset or `1`).
- **Counters-only** mid-run snapshots — every persist includes the full list of completed `FlowItem`s in `data.main`.
- Per-item Mongo writes (331 items → 331 writes).

---

## When partial persist applies

Partial persist is **not** global for every item-processing node. It applies only when **both** are true:

1. **Node type supports batching** — `supports_batch_size: true` on the node type (e.g. `docrouter.ocr`, `docrouter.llm_run`).
2. **Batch level configured on the node** — revision node has `batch_size > 1` (via `resolve_node_batch_size(node)`; default `1` is sequential and **excluded**).

Nodes with `batch_size=1`: **no** mid-node checkpoints; only final persist when `execute()` returns (today’s behavior).

Helper (implementation):

```python
def node_uses_batch_partial_persist(node: dict, node_type) -> bool:
    return bool(getattr(node_type, "supports_batch_size", False)) and resolve_node_batch_size(node) > 1
```

---

## Persist policy — four triggers only

Every partial snapshot writes the **full list of completed items so far** into `data.main[0]` (plus counters). Never persist counters without items.

| Trigger | When | `run_data[node_id].status` | Notes |
|---------|------|----------------------------|-------|
| **1. Normal end** | `execute()` returns; engine final persist | `success` (or `skipped`) | Authoritative; adds to `completed_nodes` |
| **2. Item error** | Per-item handler catches an exception (Phase 2) | `error` | Persist **all items completed before the failure** + error envelope; do **not** replace with `data.main: []` |
| **3. Cooperative stop** | `should_stop` true; in-flight work drained | `running` → engine sets execution `stopped`; node `success` with partial data | Explicit persist **before** `execute()` returns |
| **4. Worker interrupt** | Worker dies mid-batch; recovery marks execution `interrupted` | `running` at last checkpoint → normalized to `partial` | Requires **interrupt checkpoints** during the batch (see below) |

**Interrupt checkpoints (trigger 4 only):** While a batch node is running, persist all completed items **once per batch wave** so a hard kill retains the last full snapshot. This is not a separate “UI persist mode” — it is the durability mechanism for worker interrupt.

- Track `finished_count` under a lock in `item_batch.py`.
- Invoke checkpoint when `finished_count % batch_size == 0` or `finished_count == total`.
- Do **not** use “in-flight count drops to zero” — the current worker pool keeps up to `batch_size` items in flight continuously until the batch finishes or stop is requested.
- Optional throttle floor (e.g. ≥1 s between checkpoint writes) if waves finish faster than 1 s apart.
- Example: `batch_size=32`, 331 items → ~11 checkpoint writes, each with all completed items at that point.

**Cooperative stop (trigger 3):** After stop is detected and in-flight items finish, call the same persist helper with all completed items **before** returning from the node. Do not rely solely on the engine’s post-`execute()` persist (that already works today for stop, but an explicit mid-node snapshot ensures consistency with interrupt/error paths).

**Item error (trigger 2):** On first fatal item error (when `continue_on_item_error` is false), persist immediately with every item that finished successfully up to that point — including items from the current in-flight wave that already completed. Phase 1 wave checkpoints alone can lose up to `batch_size − 1` items on error; Phase 2 closes that gap.

---

## Proposed `run_data` shape (batch nodes)

Extend `run_data[node_id]` (backward compatible — old executions omit new fields):

```json
{
  "status": "running | success | error | partial | stopped",
  "start_time": "...",
  "execution_index": 0,
  "items_total": 331,
  "items_completed": 149,
  "items_failed": 1,
  "data": { "main": [[ /* FlowItem[] — all completed items so far; may be partial */ ]] },
  "error": { /* present when status=error; may coexist with partial data */ },
  "source": [...],
  "logs": null,
  "trace": null
}
```

**Semantics:**

- `items_total` — input item count (`len(input_items)`), including items skipped for missing binary.
- `items_completed` — items that **finished successfully**; equals `len(data.main[0])` when failures are not stored inline. Skipped items (e.g. no PDF) do not increment `items_completed` but still count toward `items_total`.
- `items_failed` — optional; count of items that raised when using per-item error collection (Phase 2).
- `status: running` — interrupt checkpoint during batch; execution still `running`.
- `status: partial` — node did not finish cleanly (interrupt recovery); execution `interrupted`.
- On **error with partial data**: `status: error`, partial `data.main`, `error` describes first fatal or summary error. Execution stays `error` (no new execution-level `partial` status).
- On **cooperative stop**: node entry has partial `data.main`; node `status: success`; execution `stopped`.

---

## Phase 1 — Interrupt checkpoints + cooperative stop + canvas progress ✅

### 1a. Batch checkpoint callback (for worker interrupt) — shipped

In `item_batch.py`:

- Add optional `on_items_checkpoint(completed: int, total: int, results: list[T | None])`.
- Under a lock, increment `finished_count` after each item completes; invoke callback when `finished_count % batch_size == 0` or `finished_count == total`.
- On cooperative stop: after in-flight work drains, invoke callback once more with final partial results (trigger 3).
- **Do not** register when `batch_size <= 1` or node type lacks `supports_batch_size`.

New module `packages/python/analytiq_data/flows/batch_progress.py`:

- `persist_batch_node_partial(context, node_id, node, items_total, results: list)` — build `run_data[node_id]` with `status: running`, full partial `data.main` (all non-`None` completed items), `items_total` / `items_completed`; call `persist_run_data(..., last_node_executed=node_id)` **without** `record_checkpoint`.
- `make_batch_checkpoint_callback(context, node, node_type)` — returns `None` if `not node_uses_batch_partial_persist(node, node_type)`; otherwise returns the checkpoint hook with optional ≥1 s throttle between DB writes.

Wire from `ocr_node.py` and `llm_node.py` only when callback is non-`None`.

### 1b. Final persist (trigger 1 — normal end)

When `execute()` returns:

- **Success / stop-partial:** engine merge sets final item list; `status: success`; `record_checkpoint=True` when appropriate.
- **Overwrite** last interrupt checkpoint with authoritative final output.

### 1c. Worker interrupt (trigger 4)

Interrupt checkpoints from 1a mean `flow_executions.run_data` already contains all completed items + counters when the worker dies.

In `recovery.py`:

- When marking `interrupted`, if `last_node_executed` has `status: running` and partial `data.main`, rewrite node entry to `status: partial`.
- Do **not** add to `completed_nodes` (node did not finish cleanly).
- Note: execution may stay `running` until stale heartbeat (default 300 s) or startup recovery; UI may show `running` badge until recovery sets execution `interrupted` and node `partial`.

### 1d. Frontend — completed count on canvas

| File | Change |
|------|--------|
| `flowNodeRunStatus.ts` | `getNodeBatchProgressFromRunData`, extend `applyExecutionStatusToNodes` with `executionBatchProgress`; handle `partial` status |
| `FlowCanvasNode.tsx` | `N/M` badge on **top edge** (rounded rect); `partial` → amber badge |
| `FlowExecutionsView.tsx` | `onExecutionChange` poll refresh |
| Editor (`FlowEditor` via `FlowCanvasNode`) | Badge from live `execution.run_data` |

**Canvas refresh (lightweight):** On poll, update `detail` / `run_data` and re-run `applyExecutionStatusToNodes` on existing `viewNodes`. Do **not** re-fetch revision on every 2 s poll. Edge item counts update via existing `edgesWithRunDataItemCounts` once `detail.run_data` changes.

**Display rules:**

- Show `completed/total` when `items_total > 0` and (`status === running` OR `status === partial` OR `completed < total`).
- On terminal `error` with partial data: show error badge **and** count pill (e.g. `149/331`).
- Hide pill on clean `success` with all items done.

### 1e. Tests

- Python: checkpoint **not** registered when `batch_size=1`; registered when `batch_size=32`; persist once per wave boundary; throttling.
- Python: checkpoint `run_data` includes full `data.main` items, not counters alone; recovery normalizes `running` → `partial`.
- Python: cooperative stop triggers explicit persist with all completed items before node return.
- Frontend: `flowNodeRunStatus.spec.ts` for counter parsing and `partial` status; optional component test.

---

## Phase 2 — Persist on item error (trigger 2) ✅

### 2a. Per-item error isolation — shipped

- `continue_on_item_error=True` for `docrouter.ocr` and `docrouter.llm_run` (`continue_on_item_error_for_node`).
- `FlowBatchItemErrors` raised after all in-flight work when any item failed.
- `make_batch_fatal_error_callback` for non-continue path (other node types).
- OCR/LLM call `persist_batch_node_partial(..., status=error, items_failed=...)` before re-raising.

### 2b. Engine error path — shipped

Engine `on_error: stop` branch merges existing partial `data.main` + counters instead of replacing with `[]`.

### 2c. `on_error: continue` vs item-level continue

- Node `on_error: continue` (existing) — whole node emits one error item downstream.
- **Item-level continue** — OCR/LLM default; failures collected; node errors with partial successes when any item failed.

### 2d. Tests — shipped

`test_flow_batch_partial_phase2_3.py`, extended `item_batch` tests.

---

## Phase 3 — Resume incomplete items + bulk rerun mode ✅

### 3a. Item skip on resume — shipped

- `load_batch_resume_items()` reads completed items by `meta.item_index` from partial/error run entries.
- OCR/LLM `_run_item` returns cached items for skipped indices.
- `items_skipped_on_resume` preserved on final success persist.

### 3b. Bulk / single-doc rerun — shipped

- API: `POST .../run/{document_id}` body `{ "mode": "force" | "incomplete_only" }`.
- `incomplete_only`: `find_resumable_batch_execution` → `enqueue_resume_execution`; 409 if none or revision changed.
- Bulk UI rerun mode radio; sidebar uses same sessionStorage key.

### 3c. Execution logs — shipped

- `resumeExecutionLabel()` → “Resume (N items remaining)” when partial batch data present.

### 3d. Tests — shipped

`test_flow_batch_partial_phase2_3.py`, `flowResume.spec.ts`.

**Not shipped (optional follow-up):** per-row bulk hint (“149/331 OCR done — resume available”); disable incomplete mode in UI when no partial execution exists (API returns 409 today).

---

## n8n patterns to adopt vs skip

| Adopt | Skip |
|-------|------|
| Persist execution progress while `running` (interrupt checkpoints) | Mid-item checkpoint inside n8n native nodes (they don’t do it) |
| Item counts on canvas / edges | Full WebSocket push stack in v1 (poll is enough for executions tab) |
| Explicit `interrupted` vs `error` | Renaming to n8n terms (`runData`, `runIndex`) |
| Full partial payload at checkpoint (not counters-only) | SplitInBatches graph pattern (we already batch inside OCR node) |

---

## Files changed (by phase)

| Phase | Backend | Frontend |
|-------|---------|----------|
| 1 ✅ | `item_batch.py`, `batch_progress.py`, `node_settings.py`, `ocr_node.py`, `llm_node.py`, `recovery.py` | `flowNodeRunStatus.ts`, `FlowCanvasNode.tsx`, `FlowExecutionsView.tsx` |
| 2 ✅ | `item_batch.py`, `engine.py`, OCR/LLM error persist | Partial/error pill styling on canvas |
| 3 ✅ | `resume.py`, `batch_progress.py`, `document_flow_sidebar.py`, `routes/flows.py` | `DocumentBulkRunFlows.tsx`, `PDFFlowsSidebar.tsx`, `flowResume.ts`, `FlowLogsPanel.tsx`, SDK |

---

## Rollout (completed)

1. Phase 1: wave checkpoints when `batch_size > 1`; Editor + Executions `N/M` badge.
2. Phase 2: item errors retain partial `data.main`.
3. Phase 3: bulk/sidebar `incomplete_only` rerun + item skip on resume.

Manual verification: kill worker mid-batch, stop mid-batch, inject OCR/LLM failure, bulk rerun incomplete only.

---

## Success criteria

| Scenario | Before | After |
|----------|--------|-------|
| Error on item 150/331 | `data.main: []` | All items that completed before failure in `run_data`, error set |
| Worker interrupt at 149/331 | No entry for OCR node | Partial entry with all 149 completed items |
| Executions canvas during OCR | Static until node completes | `149/331` updates every ~2 s (from checkpoint poll) |
| Cooperative stop | Partial saved at node return | Explicit persist with all completed items; counters match |
| Normal end | Full `data.main` | Unchanged; authoritative final persist |
| Checkpoint persist, `batch_size=1` | N/A | No mid-node writes |
| Checkpoint persist, `batch_size=32` | N/A | ~1 write per wave; each includes full completed items |
| Bulk rerun incomplete only | Always full rerun | Skips completed batch items; resume execution |
| Bulk rerun force | Same as today | Full new execution |

---

## Decisions (formerly open questions)

1. **Execution-level status** when node has partial + error: keep execution `error` / `interrupted` / `stopped`; use node-level `partial` only for interrupt recovery. No new execution-level `partial`.
2. **Counters-only mid-run:** rejected. Every persist includes full completed `FlowItem`s in `data.main`.
3. **Item-level continue default:** `true` for `docrouter.ocr` and `docrouter.llm_run`; `false` for other node types.
4. **Editor run poll:** shipped via logs panel + `FlowExecutionVisualProvider` (no WebSocket).
5. **Incomplete-only bulk default:** default `force`; optional localStorage for last user choice.

---

## References

- `packages/python/analytiq_data/flows/item_batch.py`
- `packages/python/analytiq_data/flows/node_settings.py` — `resolve_node_batch_size`, batch persist gate
- `packages/python/analytiq_data/flows/engine.py` — `persist_run_data`, error path ~1251–1273
- `packages/python/analytiq_data/flows/recovery.py`
- `packages/python/analytiq_data/flows/resume.py`
- `packages/typescript/frontend/src/components/DocumentBulkRunFlows.tsx`
- n8n: `packages/cli/src/execution-lifecycle/save-execution-progress.ts`
- n8n: `packages/frontend/editor-ui/src/features/workflows/canvas/composables/useCanvasMapping.ts`
- Prior art (reverted): batch progress conversation — checkpoint persist + canvas pill pattern
