# Flow Durability: What Happens When a Worker Dies?

When you build a workflow system, one of the hardest problems is not making things
run — it is making them keep running correctly after something goes wrong. Servers
crash. Processes are killed by the OS. Kubernetes reschedules pods mid-execution.
Cloud spot instances vanish without warning. Whatever your infrastructure, workers
die while work is in progress, and the system has to decide what to do about it.

This post explains the two main approaches to this problem — the one taken by
Temporal and the one taken by DocRouter — and the tradeoffs behind each.

---

## The Core Problem

A workflow is a sequence of nodes. Each node does some work: calls an LLM, fetches
a document, writes a result to a database, sends a message to an external system.
Nodes take time, and time creates risk. If the worker process executing node N is
killed before N finishes, you are left with a partially executed workflow. The
question is: what does the system do next?

There are three possible answers:

1. **Mark the workflow as failed** and let the operator decide what to do.
2. **Restart the workflow from scratch**, re-executing every node from the beginning.
3. **Resume the workflow from the last completed node**, skipping work already done.

Each answer involves a different set of assumptions about the nodes in your workflow.

---

## Temporal: Replay Semantics

Temporal takes a fundamentally different approach from most workflow systems. It does
not think in terms of "the worker died." Instead, Temporal models a workflow as an
append-only event history. Every significant event — task scheduled, task completed,
timer fired, signal received — is durably written to Temporal's persistence layer
before anything acts on it.

When a worker is assigned a workflow task, it does not execute the workflow from
scratch. It *replays* the event history. The workflow code runs again from the top,
but for any event that already exists in the history, the code fast-forwards through
it rather than re-executing the underlying work. Only when replay reaches the
frontier of the history — the point where new work needs to happen — does the worker
actually call out to external systems.

This means that from Temporal's perspective, worker death is not a special case. A
workflow task that was in-flight when a worker died simply gets rescheduled. Another
worker picks it up, replays the history to the same point, and continues. The
workflow itself never "knows" the previous worker existed.

### What this requires from your code

Replay semantics place a strict requirement on workflow code: it must be
*deterministic*. Given the same event history, the workflow code must make exactly
the same decisions every time it replays. This rules out certain operations directly
inside workflow code:

- You cannot call `time.now()` — use Temporal's timer APIs instead.
- You cannot generate random numbers — Temporal provides a seeded random source.
- You cannot make direct network calls from workflow code — all I/O must go through
*activities*, which are the units of work that interact with the outside world.

Activities are the escape valve. They can be non-deterministic, have side effects,
and take as long as they need. Temporal records the result of each activity
completion in the event history. On replay, a completed activity's result is read
from history rather than re-executed.

### Heartbeating

Long-running activities report progress back to Temporal via *heartbeats*. If an
activity stops heartbeating, Temporal considers it lost and schedules it again
(subject to retry policy). Activities are expected to be idempotent — if they are
re-executed, the end state should be the same as if they ran once.

### The cost

Temporal's guarantees come at a price. The infrastructure overhead is significant:
Temporal requires its own server cluster with a separate database, typically
Cassandra or PostgreSQL, maintained alongside your application. The programming model
has learning curve — developers must understand the determinism constraint and
structure their code accordingly. For simple workflows or small teams, the
operational burden can outweigh the benefits.

---

## DocRouter: Checkpoint-Based Recovery

DocRouter takes a pragmatic approach suited to its architecture. Workflows run as
Python functions executing a directed graph of nodes. There is no separate workflow
server — the same MongoDB database that stores documents, forms, and results also
stores execution state. The worker is a straightforward async Python process.

### Heartbeats and stale detection

Every running execution records a `last_heartbeat_at` timestamp in MongoDB, updated every few seconds by the engine. If a worker dies, the heartbeat stops. A recovery process — running both at worker startup and periodically during normal operation — scans for executions whose heartbeat has not been updated within a configurable window (default: 300 seconds). These are considered orphaned.

### Checkpoints

Rather than replaying event history, DocRouter uses checkpoints. After each node
completes successfully, the engine does two things atomically:

1. Writes the node's full output to `run_data[node_id]` in the execution document.
2. Appends the node's id to a `completed_nodes` list using MongoDB's `$addToSet`.

The two-step structure is deliberate. `run_data` stores the actual output; 
`completed_nodes` is the authoritative record of which nodes finished cleanly. A
node that was executing when the worker died will have nothing in `completed_nodes`
for that node id — its `run_data` entry, if any, may be a partial write.

### Recovery decisions

When a stale execution is detected, the system makes one of three decisions based on
the execution's state and the flow's settings:

**Stop requested:** If the user had requested a cooperative stop before the worker
died, the execution is marked `stopped`. No resume is attempted — the user's intent
was to stop.

**Checkpoint resume:** If the flow has `resume_on_restart: true` in its settings and
at least one node is in `completed_nodes`, a new execution document is created. It is
seeded with the `run_data` and `completed_nodes` from the interrupted execution. The
original execution is marked `interrupted`. When the worker picks up the new
execution, the engine skips any node whose id appears in `completed_nodes`, reusing
its cached output from `run_data`. Only nodes that were not completed — including the
one that was in-flight — are re-executed.

**Scratch retry:** If `resume_on_restart: true` but there are no checkpoints (the
worker died before any node completed), the execution is reset to `queued` with
cleared state. It will be re-executed from scratch.

**Finalize as interrupted:** If `resume_on_restart` is not enabled, the execution is
marked `interrupted` with an error describing the cause. No automatic retry is
attempted. The user can still trigger a manual resume from the UI.

### What this requires from your nodes

The checkpoint model makes a simpler assumption than Temporal's determinism
requirement: nodes in `completed_nodes` had their side effects committed. The
checkpoint is only written after the node returns successfully, so if the worker died
mid-node, that node is not in `completed_nodes` and will be re-executed.

This is safe for nodes that read or extract data — OCR, LLM extraction, schema
validation. For nodes that write to external systems — sending an email, posting to
a webhook, writing to an ERP — re-execution after a crash could cause a double
write. DocRouter's approach to this is the same as most practical workflow systems:
design action nodes to be idempotent where possible, and use the `interrupted` status
(without auto-resume) for flows where that is not achievable.

### The tradeoff

DocRouter's approach is lighter to operate than Temporal. There is no separate
workflow server to run and maintain. The persistence layer is the same MongoDB
instance already used for everything else. The programming model for node authors is
unrestricted Python — no determinism constraints, no special APIs for timers or
random numbers.

The cost is weaker durability guarantees. Temporal can recover a workflow from any
point in its history, with full fidelity, regardless of how long recovery takes.
DocRouter recovers from the last completed node checkpoint. If a node takes a long
time and produces no intermediate checkpoints, and the worker dies during that node,
the node must be re-executed from scratch. For long-running LLM calls or OCR jobs
this is usually acceptable; for workflows with tightly coupled external state it
requires more care.

---

## Comparison


|                                 | Temporal                         | DocRouter                              |
| ------------------------------- | -------------------------------- | -------------------------------------- |
| **Recovery unit**               | Activity (fine-grained)          | Node (coarse-grained)                  |
| **State storage**               | Temporal server + dedicated DB   | MongoDB (shared with app)              |
| **Replay model**                | Full event history replay        | Checkpoint skip                        |
| **Code constraints**            | Deterministic workflow code      | None                                   |
| **In-flight node on crash**     | Rescheduled, retried             | Re-executed from scratch               |
| **Infrastructure overhead**     | High (separate cluster)          | Low (existing MongoDB)                 |
| **Double side-effect risk**     | Managed via activity idempotency | Managed via `completed_nodes` contract |
| **Long-running node mid-crash** | Activity heartbeat → reschedule  | Re-executed from scratch               |


---

## Why This Design for DocRouter?

DocRouter's primary workload is document extraction pipelines: OCR a document, run
it through an LLM, validate the output against a schema, store the result. Most
nodes are pure read-and-extract operations. They produce the same result if run
twice. The crash-recovery risk is low for this workload, and when it does occur, the
checkpoint model handles it efficiently.

For the cases where idempotency matters — integration nodes writing to external
systems — DocRouter's `interrupted` status and manual resume give operators
visibility and control without the complexity of a full Temporal deployment.

The result is a system that fits within a standard web application stack, can be
self-hosted on a single server, and recovers correctly from the most common failure
modes without requiring developers to learn a new programming model.