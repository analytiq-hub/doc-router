# Flows ↔ n8n compatibility (status + gaps)

This document captures the current state of DocRouter Flows compatibility with n8n:

- Can we map n8n workflow JSON 1:1 into our flow implementation?
- What is still missing?
- What a realistic path to “run a subset of n8n workflows unchanged” looks like.

It is meant as a planning artifact for reaching the long-term goal: **n8n workflow JSON + node
definitions should be importable and runnable** in DocRouter with minimal translation.

## Current answer: not yet 1:1

We are closer on **execution semantics** (stack/waiting-map, branch/merge, run-data recording)
and now have a more n8n-like **expression context** (added `$input`, `$item`, `$items`).

However, n8n workflow JSON and node definitions still will not “drop in” without a
translation/compatibility layer.

## What we already match (or are close to)

- **Execution engine shape**: queue/stack work items + waiting map for merge-style nodes + a
  per-node permanent `run_data` store is aligned with n8n’s conceptual model.
- **DAG validation**: we enforce DAG-only execution today, which matches a large subset of n8n
  workflows (but not loops/Wait/resume).
- **Branch/merge/skip semantics**: we model “empty output skips downstream” and merge waiting in
  a similar way.
- **Expressions (partial)**:
  - `$json`, `$node` are supported.
  - `$input`, `$item`, `$items` are supported (recently added), which is a step toward n8n’s
    `WorkflowDataProxy` model.

## What is still missing for true 1:1 n8n JSON + nodes

### 1) Node identity and connection keying

- **n8n**: `connections` are keyed by **node name**; `IConnection.node` refers to the
  destination **node name**.
- **DocRouter**: connections are keyed by **node id** (rename-safe).

**Implication**: importing n8n JSON requires either:
- A mapping layer (name → id) with an adapter that rewrites `connections`, *or*
- Storage changes so we can store and execute name-keyed graphs 1:1.

### 2) Node types and versioning

- **n8n** nodes are `type` + `typeVersion`, backed by `INodeTypeDescription` and a rich runtime
  API (`IExecuteFunctions`).
- **DocRouter** uses a simpler `NodeType` protocol: fixed-ish `min_inputs/max_inputs/outputs`,
  a JSON Schema for parameters, and `execute(context, node, inputs)`.

**Implication**: 1:1 compatibility needs:
- Versioned node descriptions (typeVersion-like behavior)
- A richer node runtime API (helpers, binary handling, credentials access, etc.)
- A strategy for “dynamic IO” that some n8n nodes use (variable inputs/outputs)

### 3) Expression compatibility (`WorkflowDataProxy`)

We improved merge semantics and added `$input/$item/$items`, but n8n expressions provide much
more surface area and semantics:

- `$env`, `$vars`, `$parameter`, `$prevNode`, `$workflow`, `$now`, `$jmespath`, etc.
- `$items('NodeName', branchIndex, runIndex)` and `$('NodeName').item` ergonomics
- Expression extensions (string/number/object helpers), and two evaluation backends
  (legacy evaluator + isolated-vm)

**Implication**: importing workflows that rely on these features will still break.

### 4) Paired item / lineage semantics

n8n relies on `pairedItem` to preserve item lineage across splits/merges. This impacts:
- UI lineage arrows
- helper semantics like `$('X').item` (“corresponding item” behavior)

DocRouter `FlowItem` has `paired_item`, but we do not currently maintain n8n-equivalent lineage
rules (and we do not expose a corresponding helper API in expressions).

### 5) Node execution contract and helper APIs

- **n8n**: node code runs with `IExecuteFunctions` which provides:
  - `getInputData(slot?)`, `getNodeParameter(...)`, `helpers.*`, binary helpers
  - credential access (`this.getCredentials(...)`)
  - static data access (`this.getWorkflowStaticData(...)`)
  - per-node execution metadata (runIndex, itemIndex) in a standardized way
- **DocRouter**: nodes are plain Python classes with `execute(context, node, inputs)`.

**Implication**: n8n node implementations cannot be ported “as-is”; they expect the helper API.

### 6) Connection types beyond `main`

n8n supports multiple connection lanes (`main` plus various `ai_*` lanes). DocRouter currently
only supports the `main` lane.

**Implication**: any workflow using AI lanes or non-main lanes cannot be represented 1:1 yet.

### 7) Triggers, activation, webhooks, and schedules

n8n has first-class lifecycle management:
- activation registry (`ActiveWorkflows`)
- webhook entity registration (static + dynamic paths), caching, request routing
- schedule triggers and pollers
- temporary webhooks for Wait/form nodes

DocRouter has partial inbound flow webhook support, but we do not match n8n’s activation and
registration behaviors 1:1.

### 8) Wait/resume execution model

n8n can pause executions and resume them later by serializing execution state (including the
execution stack) and resuming via timers or webhooks.

DocRouter does not implement Wait nodes or execution resume.

### 9) Credentials system

n8n’s credential system is integral to many nodes:
- encrypted storage
- expression resolution inside credentials
- OAuth refresh flows
- permissions/sharing rules

DocRouter does not implement an n8n-compatible credential system.

## What “1:1” likely means in practice

Achieving true 1:1 parity is a large scope. A practical approach is to define compatibility
tiers:

- **Tier 0 (Import-only)**: accept n8n JSON and store it, but don’t execute.
- **Tier 1 (Core execution)**: execute a subset of node types with `main` connections and a
  limited expression proxy.
- **Tier 2 (Ergonomics parity)**: implement the `WorkflowDataProxy`-style surface (or a close
  approximation) and preserve paired-item lineage.
- **Tier 3 (Platform parity)**: activation lifecycle, triggers, schedules, webhooks, Wait/resume,
  credentials, and multi-process push.

## Suggested next concrete steps

If the goal is “import and run a meaningful subset of n8n workflows soon”, the fastest path is:

- **Graph adapter**: an n8n JSON importer that produces our internal `flow_revision` shape
  (or a dual-mode engine that can run name-keyed graphs).
- **Expression proxy expansion**: implement the most-used `WorkflowDataProxy` capabilities:
  `$env`, `$vars`, `$parameter`, `$prevNode`, `$workflow`, and `$items(...)`.
- **Paired item support**: define and implement lineage rules for split/merge so item mapping is
  stable and UI/debugging semantics match expectations.
- **Node runtime helper API**: add a Python `ExecuteContext` layer so node implementations can
  be written in an n8n-like style.
- **Node subset port**: reimplement a small canonical set of nodes (Set, IF, Merge, HTTP Request,
  Webhook trigger) in Python with compatible parameters and behaviors.

