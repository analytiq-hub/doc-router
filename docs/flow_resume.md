# Flow Resume Plan

## Goal

Allow a flow execution that was interrupted (worker death, cooperative stop) to be
resumed from its last completed node instead of re-running from scratch.

---

## Flow Setting: `resume_on_restart`

Stored in `FlowRevision.settings` (and mirrored to the `flows` header document).

```json
{ "resume_on_restart": false }
```

| Property | Value |
|----------|-------|
| Type | boolean |
| Default | `false` |
| Scope | per-flow revision (`settings` dict) |

When `true`, the worker recovery pass will automatically create a resume execution
for any `stopped` execution of this flow whose worker died. Executions marked
`error` (unclean crash) are **not** auto-resumed by default — see [Safety](#safety)
below.

---

## How Resume Works

### Concept

`run_data` already stores per-node outputs in MongoDB, written by `persist_run_data`
after each node completes. Resume exploits this as a free checkpoint log:

1. A _resume execution_ is a new execution document seeded with the `run_data` and
   `completed_nodes` from the interrupted execution.
2. The engine skips any node whose id appears in `completed_nodes`, using its cached
   output from `run_data` instead of re-running.
3. From the user's perspective the new execution runs to completion; the original
   execution stays in its terminal state (`stopped` / `error`) for audit purposes.

### Why `completed_nodes` and not just `run_data`?

`run_data[node_id]` can be partially written if the worker dies mid-serialisation.
A separate `completed_nodes: list[str]` list, appended **after** `run_data` is
confirmed written, is the authoritative signal that a node's output is safe to reuse.

---

## Data Model Changes

### `flow_executions` collection

Two new fields on every execution document:

| Field | Type | Description |
|-------|------|-------------|
| `completed_nodes` | `list[str]` | Node ids whose output is confirmed persisted. Appended after each successful `persist_run_data`. |
| `resumed_from` | `str \| null` | `_id` of the interrupted execution this one resumes. `null` for fresh runs. |

### `flows` collection header

No change — `resume_on_restart` lives only in `flow_revisions.settings` and is read
at execution time.

---

## Engine Changes (`analytiq_data/flows/engine.py`)

### 1. Write `completed_nodes` after each node

In `persist_run_data`, after writing `run_data`, also push the node id to
`completed_nodes`:

```python
await db.flow_executions.update_one(
    {"_id": ObjectId(context.execution_id)},
    {
        "$set": {"run_data": stored, "last_heartbeat_at": now, ...},
        "$addToSet": {"completed_nodes": last_node_executed},   # new
    },
)
```

`$addToSet` is idempotent, so a retried write never duplicates entries.

### 2. Skip completed nodes at dispatch time

In `_execute_loop`, before invoking a node:

```python
if node["id"] in context.completed_nodes:
    # reuse cached output from run_data; do not re-execute
    context.run_data[node["id"]] = resume_run_data[node["id"]]
    continue
```

`context.completed_nodes` is populated from the execution document when the context
is constructed (see below).

### 3. `ExecutionContext` carries resume state

Add two fields:

```python
@dataclass
class ExecutionContext:
    ...
    completed_nodes: frozenset[str] = field(default_factory=frozenset)
    resumed_from: str | None = None
```

---

## Recovery Changes (`analytiq_data/flows/recovery.py`)

### Current behaviour

`recover_stale_flow_executions` marks orphaned `running` executions as `stopped` (if
`stop_requested`) or `error` (otherwise) and calls
`maybe_capture_docrouter_flow_result` for stopped ones.

### New behaviour for `stopped` + `resume_on_restart`

After marking an execution `stopped`, check whether its flow has
`resume_on_restart: true`. If so, enqueue a resume execution:

```python
if status == "stopped" and _flow_has_resume_on_restart(revision):
    await _enqueue_resume_execution(db, exec_doc, revision, run_data, completed_nodes)
```

`_enqueue_resume_execution`:
1. Inserts a new `flow_executions` document with:
   - `status: "queued"`
   - `resumed_from: str(original_exec_oid)`
   - `run_data: <copy from interrupted execution>`
   - `completed_nodes: <copy from interrupted execution>`
   - All other fields (flow_id, org, trigger, mode, revision_snapshot) cloned from original.
2. Pushes the new execution id onto the appropriate worker queue (same path as a
   normal `run_flow` message).

### No auto-resume for `error` executions

Executions that crash without `stop_requested` are not auto-resumed. The operator
must decide whether to retry manually (see [Manual Resume API](#manual-resume-api)).

---

## Manual Resume API

Even when `resume_on_restart` is `false`, users can trigger a resume from the UI.

### Endpoint

```
POST /v0/orgs/{organization_id}/flows/{flow_id}/executions/{exec_id}/resume
```

- Requires the source execution to be in a terminal state (`stopped`, `error`).
- Returns a new `FlowExecution` document (the resumed execution).
- The source execution gains a `resumed_by: <new_exec_id>` field to prevent double-
  resuming.

### Guard against double-resume

Before creating the resume execution:

```python
await db.flow_executions.update_one(
    {"_id": source_oid, "resumed_by": {"$exists": False}},   # atomic guard
    {"$set": {"resumed_by": new_exec_id}},
)
```

If `modified_count == 0`, another resume already exists; return 409 Conflict.

---

## UI Changes

### Executions list (`PDFFlowsSidebar`)

- Stopped/error executions with at least one `completed_node` show a **Resume**
  action alongside the existing **Re-run** action in the kebab menu.
- Resume is labelled "Resume from checkpoint" to distinguish it from "Re-run from
  scratch".
- A resumed execution shows a "↩ Resumed" badge with a link to the original.

### Flow settings panel

Add a **"Auto-resume on restart"** toggle (default off) that writes
`settings.resume_on_restart`.

---

## Safety {#safety}

### Why `completed_nodes` is sufficient

`completed_nodes` is only written after `run_data` is confirmed persisted. A node
that appears there has fully finished — its side effects are already committed and
skipping re-execution is always correct. The in-flight node (running when the worker
died) is never in `completed_nodes`, so it is always re-executed from scratch. No
per-node idempotency flag is needed.

### Crash vs. stop distinction

| Execution state | Auto-resume | Manual resume |
|-----------------|-------------|---------------|
| `stopped` (cooperative) | Yes, if `resume_on_restart` | Yes |
| `error` (crash) | No | Yes (with confirmation dialog warning about possible double side-effects) |

---

## Implementation Phases

### Phase 1 — Checkpoint tracking (no resume yet)

1. Add `$addToSet: completed_nodes` to `persist_run_data`.
2. Add `completed_nodes` and `resumed_from` fields to new execution documents.
3. Add `completed_nodes` to the `FlowExecution` response model and SDK type.
4. Write tests verifying `completed_nodes` grows as nodes execute.

### Phase 2 — Engine skip logic

1. Add `completed_nodes` and `resumed_from` to `ExecutionContext`.
2. Implement skip-if-in-completed_nodes in `_execute_loop`.
3. Write unit tests: engine with pre-seeded `run_data` + `completed_nodes` skips
   the right nodes and produces correct output.

### Phase 3 — Manual resume endpoint

1. `POST .../executions/{exec_id}/resume` with double-resume guard.
2. SDK method `resumeExecution(flowId, execId)`.
3. UI: "Resume from checkpoint" action in kebab menu (gated on `completed_nodes`
   being non-empty).

### Phase 4 — Auto-resume on restart

1. `resume_on_restart` setting: parse in flow validation, expose in settings panel.
2. `_enqueue_resume_execution` in `recovery.py`.
3. Integration test: kill worker mid-flow, restart, verify resume execution
   completes and skips already-completed nodes.

