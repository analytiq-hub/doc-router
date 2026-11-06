---
marp: true
title: DocRouter Flows — Architecture & Implementation
paginate: true
theme: default
style: |
  section { font-size: 28px; }
  h1 { font-size: 42px; }
  h2 { font-size: 34px; }
  code { font-size: 22px; }
  table { font-size: 22px; }
  ul, ol { font-size: 26px; }
---

<!-- _class: lead -->

# DocRouter Flows

## Architecture & Practical Implementation

Visual workflows for document processing, automation, and AI agents

---

# Agenda

1. Why workflows in DocRouter
2. End-to-end architecture
3. Layering: generic engine vs document product
4. Data model — Mongo, items, expressions
5. Execution path & durability
6. Implementation milestones
7. Design decisions
8. What’s next

---

# The problem we set out to solve

DocRouter already had a strong document pipeline:

**Upload → OCR → LLM → Review → Export**

Customers needed more than a fixed pipeline:

- Branching, merging, and custom logic
- Event-driven and scheduled automation
- Integration with email / drive / chat
- Agents that call tools
- Human-in-the-loop inspection of every step

→ Build a **first-class workflow system**, not a one-off script runner.

---

# Product goals

| Goal | Approach |
|------|----------|
| Familiar authoring | Visual DAG editor (React Flow) |
| Document-native | First-class OCR / LLM / split nodes |
| Safe custom code | Sandboxed Python code node |
| Operable | Executions list, logs, I/O viewers, resume |
| Multi-tenant | Org-scoped flows, credentials, triggers |
| Light ops | Same MongoDB + workers — no Temporal cluster |

---

# End-to-end architecture

```text
┌──────────────────────┐   /v0/orgs/{org}/flows/*   ┌─────────────────┐
│  Next.js Flows UI    │ ─────────────────────────► │  FastAPI        │
│  React Flow canvas   │                            │  flows API      │
│  Executions / logs   │ ◄───────────────────────── │  credentials    │
└──────────────────────┘         SDK                └────────┬────────┘
                                                             │
                         MongoDB: flows, revisions,          │
                         executions, triggers, blobs, queue  │
                                                             ▼
                                                    ┌─────────────────┐
                                                    │  Worker         │
                                                    │  flow_run queue │
                                                    │  → run_flow()   │
                                                    └─────────────────┘
```

---

# Package layering

Two packages on purpose:

| Package | Responsibility |
|---------|----------------|
| `analytiq_data/flows/` | Product-agnostic DAG engine, builtins, credentials, triggers, code sandbox, agent loop |
| `analytiq_data/docrouter_flows/` | Document event trigger, OCR / LLM / split nodes, result capture, bulk analyze |

**UI:** `packages/typescript/frontend/src/components/flows/`  
**API:** `app/routes/flows.py` (+ chat, credentials)  
**Worker:** `worker_flow_run` → `msg_handlers/flow_run.py` → `engine.run_flow`

---

# Authoring path

1. User builds a graph in **FlowEditor** (React Flow)
2. Save → validate revision → immutable row in **`flow_revisions`**
3. Activate → register rows in **`flow_triggers`**
4. Inactive flows do not receive schedule / document / poll triggers

Editor can also run an unsaved **`revision_snapshot`** for test runs without polluting production revisions.

---

# Run path

1. **Trigger** fires (manual, webhook, schedule, poll, chat, document event, resume)
2. Insert **`flow_executions`** with `status: queued`
3. Enqueue **`flow_run`** message
4. Worker loads revision (or snapshot), builds **`ExecutionContext`**
5. Engine walks the DAG; after each node → **checkpoint**
6. Terminal status: `success` | `error` | `stopped` | `interrupted`
7. Document flows may capture last output into **`flow_results`**

---

# Data model (MongoDB)

| Collection | Holds |
|------------|--------|
| `flows` | Header: name, active revision, org, tool flags |
| `flow_revisions` | Immutable graph: nodes, connections, settings, pin data, `graph_hash` |
| `flow_executions` | Runtime: status, `run_data`, `completed_nodes`, heartbeats, errors |
| `flow_triggers` | Active schedule / poll / event registrations |
| `flow_results` | Last-node output for document Flows sidebar |
| `flow_blobs` | GridFS binaries for execution / OCR / pins |
| queue `flow_run` | Async work messages |

---

# Runtime data model: items

The unit of data between nodes is a **`FlowItem`**:

```text
FlowItem {
  json:   dict          # structured fields (metadata, OCR pages, LLM result, …)
  binary: { name → BinaryRef }   # named attachments (PDF, image, …)
  meta:   dict          # engine bookkeeping (e.g. source_node_id, item_index)
  paired_item: int | …  # which upstream item this output row came from
}
```

**JSON vs binary**

| | JSON | Binary |
|---|------|--------|
| What | Serializable dict payload | File bytes (PDF, image, …) |
| In `run_data` | Stored inline | **`BinaryRef` only** — mime, file name, `storage_id` |
| Storage | Execution document | GridFS: `files:…` (docs) or `flow_blobs:…` (run) |
| Load bytes | — | `get_binary_stream(ref)` |

A node’s output is **lanes of item lists**: `data.main = [ [item, …], … ]` (one list per output slot). Edges wire slot → downstream input.

---

# How nodes process & reference items

**Processing**

1. Engine gathers upstream outputs into **input slots**: `inputs: list[list[FlowItem]]`
2. Parameters with a leading `=` are evaluated, then `NodeType.execute(context, node, inputs)` runs
3. Modes:
   - **Batch** — one call with the full input lists (merge / multi-item aware nodes)
   - **Per-item** — one call per item; params re-resolved for that row; outputs concatenated; `paired_item` set
4. Node returns new item lists (1:1, fan-out, or filter). Downstream nodes see only wired slots.

**Referencing prior data** (`=` expressions — Python subset, no `$` aliases)

| Binding | Meaning |
|---------|---------|
| `=_json['field']` | Current input item’s JSON |
| `=_binary['pdf']` | Current item’s binary **metadata** (not raw bytes) |
| `=_node['OCR'].json['…']` | Same row from a prior node **by display name** |
| `=_node['OCR'].output[1].json` | Other output slot of that node |
| `=_input['all']` / `=_input['item']` | All input slots / current row |
| `=_items['nodeId']` | Full prior outputs keyed by **node id** |

Code nodes receive the same item lists in `run(items, context)` and read/write `json` / `binary` directly.

---

# Revision graph shape

```text
nodes[]:
  { id, name, type, position, parameters, credentials?, … }

connections:
  { [sourceId]: { main: [ [ { dest_node_id, connection_type, index } ] ] } }
```

**Typed ports** (not only `main`):

- `docrouter.ocr` — OCR → LLM wiring
- `flows.tool` — agent tool attachments (outside the main DAG walk)

---

# Node catalog (shipped)

**DocRouter:** `docrouter.trigger`, `docrouter.ocr`, `docrouter.llm_run`, `docrouter.document_split`

**Triggers / core:** manual, schedule, webhook, chat, tool · HTTP · branch · merge · code · execute_flow

**AI:** `flows.agent` + `tool_code` / `kb_tool` / `flow_tool` / `tool_executor`

**Integrations:** Gmail, Google Drive, OneDrive, Outlook (+ poll triggers)

Lazy registration via JSON **manifests** + `LazyBuiltinNode` so the palette doesn’t import every executor at startup.

---

# Engine loop (simplified)

```text
run_flow()
  → validate_revision()
  → pick start trigger
  → _execute_loop:
       skip if node_id ∈ completed_nodes   # resume
       honor pin data (manual / editor)
       resolve =expressions
       NodeType.execute(context, node, inputs)
       fan-out via main (and tool wires)
       persist_run_data()                  # checkpoint
```

Batch nodes checkpoint mid-wave (`item_batch` / `batch_progress`) so long fan-outs can resume partially.

---

# Durability: checkpoints, not Temporal

| Temporal | DocRouter |
|----------|-----------|
| Separate workflow cluster | Same MongoDB + workers |
| Event history + replay | Node-level checkpoints |
| Deterministic workflow code | Unrestricted Python nodes |
| Stronger guarantees | Lighter ops |

After each successful node:

1. Write output to `run_data[node_id]`
2. `$addToSet` into `completed_nodes`
3. Heartbeat ~every 5s (`last_heartbeat_at`)

Stale after ~300s → recovery decides: **stopped** / **checkpoint resume** / **scratch retry** / **interrupted**

---

# Resume model

- Flow setting: **`resume_on_restart`**
- Auto-resume creates a **new** execution seeded from checkpoints; original → `interrupted`
- Manual resume from UI for terminal runs
- Mid-batch crash → node status **`partial`**; resume skips completed items
- Action nodes (email, webhooks) should be **idempotent** if auto-resume is on

See also: `docs/flow_durability.md`, `docs/flow_resume.md`

---

# Implementation milestones

How we actually built it — in order of leverage.

---

# Milestone 1 — Foundation

**Ship a real DAG product, not a prototype**

- Generic engine (`engine.py`, registry, connections, items)
- Mongo revisions + executions
- Org-scoped FastAPI CRUD / run / executions
- React Flow editor + palette + node config
- `flow_run` worker consumer

Outcome: save a graph, activate it, run it, inspect node I/O.

---

# Milestone 2 — Durability & editor UX

**Make runs operable under failure**

- Heartbeat + stale recovery
- Checkpoint resume + manual resume
- Pin data for editor testing
- Execute-step / dirty-node invalidation
- Logs panel + I/O viewers

Outcome: workers can die; operators can resume; authors can debug subgraphs.

---

# Milestone 3 — Document ↔ flow integration

**Make DocRouter documents first-class in the graph**

- `docrouter.trigger` on lifecycle events (`document.uploaded`, `llm.completed`, …)
- Nodes: OCR, LLM run, document split
- Dual blobs: `files:` (documents) + `flow_blobs:` (execution)
- `flow_results` + PDF Flows sidebar
- Tag / prompt filters on triggers

Outcome: replace “fixed pipeline only” with configurable document workflows.

---

# Milestone 4 — Code node hardening

**Custom logic without compromising the platform**

- Contract: `def run(items, context)`
- Subprocess sandbox
- AST / import allowlists
- No arbitrary FS or network from user code

Outcome: power users extend flows safely.  
(Plans: `flows_code_node_plan.md`; v2/v3 drafts folded into the shipped runner.)

---

# Milestone 5 — Agent + tools

**LLM orchestration inside the same graph**

- `flows.agent` with tool-calling loop
- Tool ports: code, knowledge base, nested flow, tool executor
- Chat trigger + streaming UI
- Flows callable as tools (`callable_as_tool`)

Outcome: agents are nodes — not a separate product surface.

---

# Milestone 6 — Integrations & credentials

**Connect to the systems customers already use**

- Gmail / Google Drive / OneDrive / Outlook (actions + poll triggers)
- Org-scoped credential store + OAuth callback
- Credential injection into node execute
- Schedule / poll leader via `FlowTriggerService`

Outcome: inbound mail/files can start document processing automatically.

---

# Milestone 7 — Scale & batch behavior

**Long runs and many documents**

- Wave checkpoints + per-item errors
- Canvas `N/M` progress badges
- Resume skip for completed items; rerun modes (`force` / `incomplete_only`)
- Bulk analyze + bulk re-run from document UI

Outcome: partial failure is visible and recoverable, not all-or-nothing.

---

# Milestone 8 — Packaging polish

**Keep the engine maintainable as node count grew**

- JSON manifests per builtin
- `LazyBuiltinNode` deferred imports
- Palette grouping (docrouter / app / flow / ai / core / trigger)
- Feature license gate: `require_feature("flows")`
- Typed TypeScript SDK (`DocRouterOrgApi` + flow RF helpers)

---

# Practical file map

| Question | Start here |
|----------|------------|
| How does a run execute? | `analytiq_data/flows/engine.py` |
| Worker entry? | `msg_handlers/flow_run.py` |
| Docs fire flows? | `docrouter_flows/event_dispatch.py` |
| What nodes exist? | `*.manifest.json` + builtin loaders |
| Canvas? | `components/flows/FlowEditor.tsx` |
| HTTP API? | `app/routes/flows.py` |
| Crash / resume? | `recovery.py`, `resume.py` |
| Tests | `packages/python/tests/flows/` |

---

# Design decisions that stuck

1. **Generic engine vs product nodes** — keep `flows/` DocRouter-agnostic
2. **Immutable revisions** — production runs pinned revids; editor uses snapshots
3. **Checkpoints over Temporal** — same Mongo, simpler ops
4. **Typed ports** — OCR and tool wires are first-class, not hacks on `main`
5. **BinaryRef** — large payloads stay in GridFS; `run_data` stores refs
6. **n8n-inspired UX, DocRouter naming** — learn from sibling editor patterns without copying product identifiers
7. **Activate model** — triggers only while active
8. **Sandbox code** — isolate untrusted Python

---

# What’s next (planned)

| Area | Intent |
|------|--------|
| OCR cache | Reuse prior OCR on matching config + input |
| Execution pruning | Soft/hard prune beyond age-based delete |
| Executions deep links | Shareable URLs into a specific run / node |
| Usage telemetry | SPUs for pages / steps / items |
| Agent polish | Fuller flow picker, more integration tests |

Plans live under `docs/flow_*_plan.md` and related files.

---

<!-- _class: lead -->

# Summary

**Editor → API → Mongo → Queue → Checkpoint engine**

Extended with document nodes, sandboxed code, agents, and integrations — all org-scoped and operable.

Workflows turned DocRouter from a fixed pipeline into a **composable automation platform**.
