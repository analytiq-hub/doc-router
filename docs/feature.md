# Flow rerun storm: root cause and fix plan

## Problem summary

Bulk/rerun flow triggering can create a "storm" of duplicate, overlapping flow
executions that all compete for the same limited OCR (AWS Textract) capacity,
slowing everything down and — under sustained load — causing legitimate
in-flight executions to be churned by the queue's stale-message recovery.

This affects every trigger path that funnels through
`enqueue_docrouter_event_flow_run()` (`packages/python/analytiq_data/docrouter_flows/event_dispatch.py:248-316`):
the manual "rerun" button, bulk rerun, and `document.uploaded` events fired on
upload (including bulk/multi-file upload).

## Root cause chain

1. **No idempotency guard at the trigger layer.** `enqueue_docrouter_event_flow_run()`
   unconditionally inserts a new `flow_executions` doc and enqueues a `flow_run`
   message every time it's called — no check for an existing queued/running
   execution for the same `(flow_id, document_id)`. Repeated rerun clicks,
   retried/duplicated upload requests, or large bulk batches all create
   unbounded numbers of concurrent executions.

2. **Undersized shared OCR concurrency (per worker process).**
   `TEXTRACT_MAX_CONCURRENT` (default 32, tunable via system settings /
   `packages/python/analytiq_data/aws/textract.py`) is a **per-process**
   asyncio semaphore (`_textract_gate`). Each worker pod has its own gate; they
   do not coordinate across pods. Within one pod, all `flow_run` (and OCR)
   tasks on that process share the same slot pool.

   Worker concurrency is sized per queue (`n_flow_run_workers`, etc. in system
   settings; legacy `N_DOCROUTER_WORKERS` bootstraps all queues to the same
   count when no settings doc exists — `packages/python/analytiq_data/system/worker_counts.py`).
   Many concurrent flow runs on one pod therefore compete for the same ~32
   Textract slots. Confirmed via log inspection that this is self-inflicted
   contention, not AWS-side throttling (zero
   `ProvisionedThroughputExceededException` in captured logs).

3. **15-minute visibility timeout churns still-alive work.**
   Queue reclaim (`recover_stale_messages()` and the inline reclaim inside
   `recv_msg()`, `packages/python/analytiq_data/queue/queue.py:89-140` and
   `192-246`) resets any `flow_run` message whose `processing_started_at`
   exceeds `QUEUE_VISIBILITY_TIMEOUT_SECS` (900s), **without checking whether
   the underlying `flow_executions` doc is still alive and heartbeating**.
   When (2) pushes a flow's OCR step past 15 minutes, the still-running
   execution's queue claim is reset to `pending` even though the worker is
   healthy — causing extra claims, queue churn, and (in edge cases) scratch
   retries or resumed work on top of an already-overloaded system.

This is a feedback loop: more concurrent load -> slower OCR (semaphore
contention) -> executions approach the 15-minute timeout -> blind queue
reclaim churns them -> even more concurrent load.

Root cause = (1). Amplifier = (2). Escalator = (3). Fixing (3) alone stops
queue churn on genuinely-alive runs but not storms caused by repeated
clicking/retries/bulk fan-out in the first place. (1) is the fix that
actually prevents storms from being created.

## Two recovery layers (queue vs execution)

The codebase has **two independent recovery mechanisms**. They are not
redundant; Fix #2 only changes the queue layer.

| | **Queue recovery** | **Execution recovery** |
|---|---|---|
| **Functions** | `recover_stale_messages()`, `recv_msg()` inline reclaim | `recover_stale_flow_executions()`, `recover_orphaned_running_flow_executions_at_startup()` |
| **Collection** | `queues.flow_run` (etc.) | `flow_executions` |
| **Stale signal** | `processing_started_at` older than **900s** (`QUEUE_VISIBILITY_TIMEOUT_SECS`) | `last_heartbeat_at` older than **300s** (`FLOW_EXECUTION_STALE_SECS`) |
| **Action** | Reset message to `pending` (another worker may claim it) | Finalize as interrupted/stopped, or scratch-retry and optionally re-enqueue `flow_run` |
| **When it runs** | Worker startup (`recover_all_queues`) + every `recv_msg` poll | Worker startup (any `running` row) + every **60s** from `worker_flow_cleanup` |

**Why both exist:** queue messages and execution documents are separate
durability records. A worker can die leaving a `processing` queue row and a
`running` execution row out of sync. Queue recovery answers "can someone else
pick up this message?"; execution recovery answers "is this execution doc
still alive, and if not, how do we finalize or retry it?"

**Relevance to this storm:** under OCR contention, executions stay **alive**
(heartbeat every 5s) but run longer than 15 minutes. Execution recovery does
**not** fire (heartbeat is fresh). Queue recovery **does** fire at 15 minutes
and reclaims the message anyway — that is the escalator. Fix #2 makes queue
reclaim consult execution heartbeats so alive runs are left alone.
`recover_stale_flow_executions` is unchanged; it remains the safety net for
genuinely dead workers (heartbeat lost), not part of this fix.

## Fix #1: idempotency guard on trigger/enqueue

**Scope:** `enqueue_docrouter_event_flow_run()` only (document-event triggers:
rerun, upload dispatch, bulk rerun). Manual/webhook executions without
`trigger.document_id` are excluded from the partial index and unaffected.

**Precedent in the codebase:** `enqueue_scheduled_flow_run()`
(`packages/python/analytiq_data/flows/triggers/enqueue.py:115-207`) does a
pre-insert `find_one` on `trigger.dedupe_key` and relies on a permanent unique
index (`flows/triggers/service.py:146-150`). That is **not** fully race-safe on
its own (no `DuplicateKeyError` handler on `insert_one`). Fix #1 should be
stricter: index + `DuplicateKeyError` handling (patterns in
`flows/credential_runtime.py:207`, `flows/triggers/leader.py:55`,
`flows/triggers/leases.py:43`).

**Why we can't reuse `trigger.dedupe_key` directly:** that uniqueness is
*permanent* — designed so a specific external event (e.g. one Gmail message)
is only ever processed once. Document rerun/upload needs the opposite
lifecycle: block a second *concurrent* execution for the same document while
one is in flight, but allow a fresh one once it finishes. That needs a
**partial unique index** scoped by status:

```python
await db.flow_executions.create_index(
    [("flow_id", 1), ("trigger.document_id", 1)],
    unique=True,
    partialFilterExpression={
        "status": {"$in": ["queued", "running"]},
        "trigger.document_id": {"$exists": True, "$type": "string", "$gt": ""},
    },
    name="flow_executions_active_flow_document_unique",
)
```

The partial filter is scoped to document-event executions only. Manual/webhook
runs without `trigger.document_id` are excluded — otherwise MongoDB would index
missing fields as `null` and block unrelated concurrent runs on the same
`flow_id`.

`trigger.document_id` is already populated today (from `payload["document_id"]`
at `event_dispatch.py:211`, spread into `trigger` via `**payload` at
`event_dispatch.py:274`) — no schema change needed, just the index and a
guard.

**Implementation shape:** attempt the insert; on
`pymongo.errors.DuplicateKeyError`, look up the existing active execution
(`find_one({"flow_id": flow_id, "trigger.document_id": document_id, "status": {"$in": ["queued","running"]}})`)
and return *its* `execution_id` **without** enqueueing a second message. No
caller changes needed — both `rerun_flow_for_document()` and the frontend's
`pollFlowRerunUntilDone()`
(`packages/typescript/frontend/src/utils/flowRerunPoll.ts:18-51`) already just
poll whatever `execution_id` comes back. A second overlapping rerun click
transparently starts polling the *first* run's completion instead of spawning
a duplicate.

**Interactions with other execution paths (no change expected):**

- `enqueue_resume_execution` creates a *new* execution with the same
  `trigger.document_id` after the source is terminal (`interrupted`, etc.) —
  allowed because the partial index only covers `queued`/`running`.
- Scratch retry resets the *same* execution back to `queued` — same `_id`, no
  conflict.
- Auto-resume after recovery while a user retries the same document should be
  blocked by the index — desirable.

## Fix #2: heartbeat-aware stale-message recovery (queue layer only)

**The gap:** both `recover_stale_messages()` and `recv_msg()` reclaim stale
`processing` messages using only `processing_started_at` — no visibility into
whether the linked `flow_executions` doc is still alive.

**The existing liveness signal:** `_heartbeat_loop()`
(`packages/python/analytiq_data/msg_handlers/flow_run.py:20-29`) bumps
`flow_executions.last_heartbeat_at` every `HEARTBEAT_INTERVAL_SECS` (5s) once
`process_flow_run_msg` has claimed the execution as `running` (`flow_run.py:205-213`).
`recover_stale_flow_executions()` already uses this field for
*execution*-level staleness at the **300s** threshold; the queue layer just
doesn't consult it at the **900s** threshold.

**The fix:** before reclaiming a `flow_run` message purely because it's older
than `QUEUE_VISIBILITY_TIMEOUT_SECS` (900s), cross-check the linked
execution. Implement in `packages/python/analytiq_data/msg_handlers/flow_run.py`
(`recv_flow_run_msg`, `recover_stale_flow_run_messages`), called from
`packages/python/worker/worker.py` (`worker_flow_run`, `recover_all_queues`).
Use generic queue primitives from `packages/python/analytiq_data/queue/queue.py`
(`recv_pending_msg`, `list_stale_processing_messages`,
`try_reclaim_stale_processing_msg`, `release_stale_processing_msg`) — the queue
layer stays domain-agnostic.

1. Find candidate stale messages via `list_stale_processing_messages()`.
2. Batch-look-up linked `flow_executions` for those `execution_id` values.
3. Only reclaim if the execution is missing, terminal, or has a stale heartbeat.
   Leave messages alone when the execution is `running` with a fresh heartbeat.

**Pre-`running` edge case:** heartbeat starts only after status flips to
`running`. Between queue claim and that update, `last_heartbeat_at` is null. Do
**not** treat "missing heartbeat" alone as dead when `status == "queued"` and
`started_at` (or the message's `processing_started_at`) is recent.

**Tradeoff:** `flow_run` reclaim becomes a read+decide loop with a
cross-collection lookup in `msg_handlers/flow_run.py` — more expensive than the
blind `recv_msg` / `recover_stale_messages` used by other queues.

**Out of scope:** `recover_stale_flow_executions()` and startup orphan recovery
are unchanged. They handle dead workers at the execution-doc layer; this fix
stops the queue layer from disturbing alive ones.

## Tests

- Concurrent `enqueue_docrouter_event_flow_run` for the same
  `(flow_id, document_id)` → one execution, one queue message; second call
  returns the first `execution_id`.
- Second rerun click / duplicate upload dispatch → same behavior;
  `pollFlowRerunUntilDone` completes against the first run.
- Bulk upload of **distinct** documents still fans out one execution per
  document (no false dedupe).
- `recover_stale_messages` and `recv_msg` (`flow_run`): message past 900s +
  `running` execution with fresh heartbeat → **not** reclaimed.
- Same, but stale/missing heartbeat or terminal execution → reclaimed.
- Pre-`running` case: `queued` execution, null heartbeat, young
  `processing_started_at` → **not** reclaimed.

## Priority

1. Fix #1 — stops storms from being created at all.
2. Fix #2 — stops the 15-minute queue timeout from churning genuinely-alive
   work (`recv_flow_run_msg` + `recover_stale_flow_run_messages` in
   `msg_handlers/flow_run.py`).
3. Tune per-queue worker counts (`n_flow_run_workers`, etc.) and
   `textract_max_concurrent` in system settings — reduces how bad contention
   gets per pod when a burst legitimately happens (e.g. real bulk upload of
   many distinct new documents, which fix #1 does not address since those are
   legitimately distinct documents, not duplicates).
