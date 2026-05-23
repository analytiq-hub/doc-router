# Full execution trace and logging (plan)

This document plans **n8n-style step-by-step execution logging** for DocRouter flows: durable per-node records, rich errors, optional HTTP/integration traces, and a logs UI that makes failures easy to follow.

**Related docs**

- Engine and `run_data` today: [`flows2.md`](./flows2.md)
- Logs panel UX (partial): [`flows_logs_ui_plan.md`](./flows_logs_ui_plan.md), [`n8n_ui.md`](./n8n_ui.md) §5
- n8n execution model reference: [`n8n.md`](./n8n.md) (stack / waiting maps, `ITaskData`, error workflow)
- Binary offload (must stay compatible): [`docrouter_binary.md`](./docrouter_binary.md)

---

## Goals

1. **Step-by-step visibility** — After a run, see which nodes executed, in what order, with timing and status (success / error / skipped / waiting).
2. **Actionable failures** — On error: node id/name, human message, **Python stack trace**, and (where useful) structured HTTP/API context (method, URL, status, truncated body).
3. **Item lineage** — For multi-item runs, know which upstream node/slot/item produced each output (n8n `source` / `paired_item` parity).
4. **Incremental persistence** — Keep writing progress after each node (today’s `persist_run_data`) so long runs and crashes still leave a trace.
5. **UI parity (core)** — Logs panel Overview/Details, Executions tab, and node modal I/O columns all consume the same normalized execution payload.

## Non-goals (initial phases)

- OpenTelemetry / distributed tracing across services
- Log streaming over WebSockets during run (polling `GET execution` is enough for v1)
- Sub-workflow / nested execution trees (no child workflow runs yet)
- PII redaction policy engine (n8n’s `redactedError`) — design hooks only
- Replacing worker stdout logging; trace data lives in MongoDB, worker logs stay for ops

---

## Current state (DocRouter)

| Area | Today | Gap vs n8n |
|------|--------|------------|
| **Storage** | `flow_executions.run_data[node_id]` — one record per node per run | n8n: `runData[nodeName][]` — **array** of runs per node (retries, per-item batches) |
| **Timing** | `start_time`, `execution_time_ms`, `status` | n8n: `startTime`, `executionTime`, `executionIndex`, `executionStatus` |
| **Errors** | `{ message, node_id, node_name, stack: null }` always | n8n: full `ExecutionError` (message, description, stack, httpCode, …) |
| **Top-level error** | `flow_executions.error` — message only, stack null | n8n: `resultData.error` + last node executed |
| **Provenance** | `FlowItem.meta`, partial `paired_item` | n8n: `ITaskData.source[]` per input slot |
| **Node console** | `run_data[node_id].logs` for **`flows.code`** only | n8n: log output mode for code nodes; integration nodes rely on error + data |
| **UI** | `FlowLogsPanel` Overview/Details, `IoViewer`, Download JSON | n8n: log tree, sub-execution links, richer error panel |
| **Integration debug** | Exception string only (e.g. Google Drive API message) | No request/response envelope |

Key code paths today:

- Engine loop: `packages/python/analytiq_data/flows/engine.py` (`_execute_loop`, `persist_run_data`)
- Worker: `packages/python/analytiq_data/msg_handlers/flow_run.py`
- Context: `packages/python/analytiq_data/flows/context.py` (`node_logs`)
- UI: `packages/typescript/frontend/src/components/flows/FlowLogsPanel.tsx`, `flowNodeRunErrorDetails.tsx`

---

## Target model (n8n-aligned, DocRouter ids)

DocRouter keeps **stable node `id`** as the `run_data` key (see [`flows2.md`](./flows2.md)); display names come from revision `nodes[].name`.

### 1. Per-node run record (`NodeRunData` v2)

Evolve the shape stored under `run_data[node_id]` (backward compatible: readers accept v1 and v2).

```json
{
  "status": "success | error | skipped | running",
  "start_time": "2026-05-23T11:20:33.123Z",
  "execution_time_ms": 412,
  "execution_index": 3,
  "data": { "main": [[{ "json": {}, "binary": {}, "meta": {}, "paired_item": null }]] },
  "error": null,
  "source": [
    { "previous_node_id": "trigger-1", "previous_node_output": 0, "previous_node_run": 0 }
  ],
  "logs": ["line from code node print()"],
  "trace": []
}
```

| Field | Purpose |
|-------|---------|
| `execution_index` | Global order counter within the execution (n8n `executionIndex`) |
| `source` | Per input slot: which upstream node/output/run fed this execution (n8n `ISourceData`, but **id**-keyed) |
| `logs` | Text lines (code node today; optional structured events later) |
| `trace` | **New:** ordered debug events (see below) |

**Multi-run per node (phase 2+):** Optional migration to `run_data[node_id]` → **array** of records (true n8n parity for per-item re-executions). Phase 1 keeps one merged record per node; store `runs: NodeRunData[]` only when a node executes multiple times with distinct errors/outputs.

### 2. Trace events (`trace[]`)

Lightweight, append-only events captured during `execute()` — not a second logging system.

```json
{
  "ts": "2026-05-23T11:20:37.456Z",
  "level": "info | warn | error | debug",
  "kind": "http | oauth | validation | engine",
  "message": "POST https://www.googleapis.com/upload/drive/v3/files → 404",
  "detail": {
    "method": "POST",
    "url": "https://www.googleapis.com/upload/drive/v3/files",
    "status_code": 404,
    "response_preview": "Not Found",
    "duration_ms": 128
  }
}
```

Rules:

- Cap `response_preview` length (e.g. 2 KB); never store secrets or full OAuth tokens.
- Integration nodes opt in via a small helper (`flows.trace_http_request(...)`).
- Engine may emit `kind: "engine"` events (parameter resolution failed, branch skipped, merge waiting).

### 3. Error envelope (`error` v2)

Unify node-level and execution-level errors:

```json
{
  "message": "Google Drive API POST /upload/drive/v3/files failed (404): Not Found",
  "node_id": "n-drive-2",
  "node_name": "Google Drive",
  "stack": "Traceback (most recent call last):\n  ...",
  "cause": "GoogleDriveApiError",
  "http_code": 404,
  "description": null
}
```

Population rules:

- On node failure: `traceback.format_exc()` when the raised exception is not intentionally user-facing-only.
- Top-level `flow_executions.error`: copy the **same** envelope from the failing node when the run stops (`on_error: stop`).
- `flow_run.py` outer `except`: set `stack` from traceback there too (revision missing, timeout, etc.).

UI: `NodeRunErrorDetails` already renders `stack` when present; extend with optional HTTP block from `trace` or `http_code`.

---

## n8n reference (what we are matching)

| n8n concept | Location (reference tree) | DocRouter equivalent |
|-------------|---------------------------|----------------------|
| `resultData.runData` | `packages/workflow/src/interfaces.ts` (`ITaskData`) | `flow_executions.run_data` |
| Write after each node | `packages/core/src/execution-engine/workflow-execute.ts` | `engine._execute_loop` + `persist_run_data` |
| Log tree UI | `packages/frontend/editor-ui/src/features/execution/logs/` | `FlowLogsPanel`, `FlowExecutionsView` |
| Run data viewer | `RunData.vue`, Schema/Table/JSON | `IoViewer.tsx` |
| Error on task | `taskData.error`, `executionStatus: 'error'` | `run_data[].error`, `status: 'error'` |
| Source lineage | `ISourceData` on `ITaskStartedData` | `source[]` on `NodeRunData` (planned) |

n8n does **not** expose a separate “full trace file”; the combination of **runData + error stacks + (optional) node logs** *is* the trace. DocRouter adds explicit `trace[]` for HTTP/integration debugging because our nodes are thin Python wrappers.

---

## Architecture

```mermaid
flowchart TB
  subgraph engine [Python engine]
    Loop["_execute_loop"]
    TraceCtx["TraceContext on ExecutionContext"]
    Persist["persist_run_data"]
    Loop --> TraceCtx
    Loop --> Persist
  end

  subgraph nodes [Node execute]
    Code["flows.code → logs[]"]
    HTTP["flows.http_request → trace http"]
    App["flows.google_drive → trace http"]
  end

  Loop --> nodes

  subgraph store [MongoDB]
    Exec["flow_executions"]
  end

  Persist --> Exec

  subgraph ui [Frontend]
    Logs["FlowLogsPanel"]
    ExecView["FlowExecutionsView"]
    Modal["FlowNodeConfigModal I/O"]
  end

  Exec --> Logs
  Exec --> ExecView
  Exec --> Modal
```

---

## Implementation phases

### Phase 0 — Quick wins (1–2 PRs)

**Backend**

1. Capture **stack traces** in `engine.py` when recording `error_env` and when re-raising.
2. Mirror stack on `flow_executions.error` in `flow_run.py` and webhook/manual failure paths in `app/routes/flows.py`.
3. Set `last_node_executed` on execution document (n8n parity) when a node fails or completes.

**Frontend**

4. In Logs **Details**, add a **Trace** section (collapsible): render `error.stack` + pretty-print `trace[]` if present.
5. Document **Download JSON** as the supported “export full trace” path in UI copy.

**Tests**

- Engine test: failing node persists non-null `error.stack`.
- API test: `GET execution` returns stack for failed run.

### Phase 1 — Trace context and HTTP integration (2–3 PRs)

**Backend**

1. [x] Add `TraceContext` on `ExecutionContext` (or per-node buffer flushed into `run_data[node_id].trace`).
2. [x] Helpers in `packages/python/analytiq_data/flows/trace.py`:
   - `trace_event(context, node_id, level, kind, message, detail=None)`
   - `trace_http(context, node_id, *, method, url, status_code, duration_ms, response_preview=None)`
3. [x] Wire **HTTP Request** and **Google Drive** (and future app nodes) through `trace_http` on 4xx/5xx and optionally on success at `LOG_LEVEL=debug`.
4. [x] Add `execution_index` increment in `_execute_loop` (monotonic counter on context).

**Frontend**

5. [x] **Trace tab** next to Input/Output in Logs Details (Table of events, expandable JSON detail).
6. [x] Filter: All / Errors / HTTP.

**SDK/types**

7. [x] Extend `@docrouter/sdk` `FlowExecution` / run_data types for `trace`, `execution_index`, `last_node_executed`.

### Phase 2 — Source lineage and multi-item clarity (2 PRs)

**Backend**

1. When enqueueing work, attach `source` to the node run record from `_WorkItem` (upstream node id, output slot, run index).
2. Ensure `FlowItem.paired_item` is set consistently for per-item nodes (branch, HTTP, Google Drive).
3. Optional: store `input_snapshot` hash or item count in trace (not full payload — size).

**Frontend**

4. In IoViewer schema mode, show **“from Manual trigger · item 0”** using `source` / `paired_item`.
5. Overview list: secondary line “← upstream node name” when available.

### Phase 3 — Logs UI parity (2–3 PRs)

Build on [`flows_logs_ui_plan.md`](./flows_logs_ui_plan.md) remaining items:

1. **Log tree ordering** — Sort/filter by `execution_index` (not only `start_time` string).
2. **Running state** — While `status === 'running'`, poll and append nodes as they appear (already partial).
3. **Executions tab** — Same Details/Trace experience as editor logs panel (`FlowExecutionsView`).
4. **Failed node auto-select** — On error, select first `status === 'error'` node in Details.
5. Resizable panels (done in node modal; mirror in logs if needed).

Reference: `../n8n/packages/frontend/editor-ui/src/features/execution/logs/logs.utils.ts` (`createLogTreeRec`, `findLogEntryRec`).

### Phase 4 — Optional advanced (later)

- **`run_data[node_id].runs[]`** when the same node executes multiple times with different outcomes (merge re-runs, retries).
- **Worker log correlation** — `execution_id` in every worker log line; link from UI “Server logs” doc (not in-app tail).
- **Error workflow** — Trigger flow on failure (see [`n8n.md`](./n8n.md) §13); consume same error envelope.
- **Retention** — TTL or size cap on `trace[]` per execution; trim on persist.

---

## Backend design notes

### TraceContext API (sketch)

```python
# packages/python/analytiq_data/flows/trace.py

MAX_TRACE_EVENTS_PER_NODE = 200
MAX_PREVIEW_LEN = 2048

def append_trace(
    context: ExecutionContext,
    node_id: str,
    *,
    level: str,
    kind: str,
    message: str,
    detail: dict[str, Any] | None = None,
) -> None: ...
```

Flush into `run_data[node_id]["trace"]` inside the existing block that sets `logs` in `engine.py`.

### Error capture (sketch)

```python
except Exception as e:
    import traceback
    error_env = {
        "message": str(e),
        "node_id": node["id"],
        "node_name": node_label,
        "stack": traceback.format_exc(),
        "cause": type(e).__name__,
        "http_code": getattr(e, "status_code", None),
    }
```

Use `format_exc()` only for unexpected failures; for `FlowValidationError` / user config errors, stack may be omitted or shortened.

### Persistence and size

- `trace[]` and `error.stack` count toward BSON document size — enforce caps before `persist_run_data`.
- Do not store request/response bodies for binary uploads; metadata only.
- Credentials: never log headers containing `Authorization`.

### API

No new endpoints required for v1: extend existing `GET /v0/orgs/{org}/flows/{flow_id}/executions/{id}` payload.

Optional later:

- `GET .../executions/{id}/trace` — paged trace for very large runs (if we split trace to a separate collection).

---

## Frontend design notes

### Logs Details layout (target)

```
┌─────────────────────────────────────────────────────────────┐
│ Error in 4s                    [Overview | Details]           │
│ EXECUTION FAILED  <message>                                 │
├──────────────────┬──────────────────────────────────────────┤
│ Node list        │  Google Drive · error · 12ms              │
│ ● Manual trigger │  [Input | Output | Trace]                 │
│ ● Google Drive   │  ─────────────────────────────────────── │
│ ○ Google Drive 1 │  Trace / stack / IoViewer                 │
└──────────────────┴──────────────────────────────────────────┘
```

**Trace tab content (priority order):**

1. Node error (`NodeRunErrorDetails` — message + stack)
2. Table of `trace[]` events (time, level, kind, message)
3. Expand row → `detail` JSON

### Shared types

Centralize in `packages/typescript/sdk/src/types/flows.ts`:

- `FlowNodeRunError`
- `FlowTraceEvent`
- `FlowNodeRunData`

Preview builders (`flowNodeIoPreview.ts`) should expose `trace` alongside `logs`.

---

## Testing strategy

| Layer | Tests |
|-------|--------|
| Engine | Fail node → `stack` present; `execution_index` monotonic; trace cap enforced |
| HTTP / Drive nodes | Mock httpx → 404 produces `trace` event with url/status |
| API | Execution JSON schema includes new fields; backward compat with old executions |
| Frontend | Unit: trace table renders; Details selects error node; stack visible |
| E2E | `test_flows_e2e.py`: run failing flow → fetch execution → assert trace/error |

---

## Migration and compatibility

- **Readers** must treat missing `trace`, `stack`, `execution_index`, `source` as empty/null (old executions).
- **Writers** add fields incrementally; no migration script for historical rows.
- **Download JSON** remains the audit export format; document field meanings in [`flows2.md`](./flows2.md) when v2 lands.

---

## Success criteria

1. User can open a failed run, select the failing node, and see **message + stack + HTTP trace** without reading worker logs.
2. Overview lists nodes in **execution order** with clear success/error/skipped icons.
3. Downloaded execution JSON is sufficient for support/debug handoff (“full trace”).
4. No regression in BSON size limits or binary offload ([`docrouter_binary.md`](./docrouter_binary.md)).
5. Behavior is documented; n8n reference cited only in docs, not in product code identifiers.

---

## Suggested first PR (Phase 0 checklist)

- [x] `engine.py`: populate `error.stack` with `traceback.format_exc()`
- [x] `flow_run.py` + routes: top-level `error.stack` + `last_node_executed`
- [x] `flowNodeRunErrorDetails.tsx`: show HTTP hint if `http_code` set
- [x] `FlowLogsPanel`: Trace section (stack + code logs; events placeholder)
- [x] Tests + update [`flows2.md`](./flows2.md) error envelope example
- [ ] Link this doc from [`CLAUDE.md`](../CLAUDE.md) or [`flows2.md`](./flows2.md) “See also”
