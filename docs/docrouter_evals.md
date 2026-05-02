# DocRouter flow evaluations — implementation plan

This document describes how to add **flow evaluations** (workflow-level regression / quality tests) to DocRouter, in the spirit of n8n **Test definitions / Evaluations** (see n8n `packages/cli/src/evaluation/`, editor **Test definition** views). It is a **product plan**, not a shipped feature.

## Goals

- Let teams **define named tests** against a flow (or a fixed revision): given controlled inputs, **re-run** the graph and **compare** results to expectations.
- Support **repeatable** runs in CI or on a schedule, with **pass/fail** and optional **numeric metrics** (latency, custom scores from an evaluator).
- Reuse existing engine behavior where possible: **`pin_data`**, **execution records**, **`run_data`**, optional **partial** or **step** execution for fast feedback.

Non-goals for an initial version:

- Pixel-perfect parity with n8n Enterprise evaluation UI or every n8n metric type.
- Arbitrary **node mocking** inside the graph (valuable later; see §6).

## Concepts (vocabulary)

| Concept | Meaning |
|--------|--------|
| **Evaluation definition** | Metadata: human name, owning `organization_id`, target **`flow_id`**, pinned **`flow_revid`** (optional; default “active” revision), tags, disabled flag. |
| **Fixture** | A **frozen input context** for a run: e.g. `trigger_data`, per-node **`pin_data`** overrides, optional `parameters` overrides for selected nodes (advanced). Equivalent to building a repeatable “world state” before execution. |
| **Baseline snapshot** | Optional stored **`run_data`** (or hashed subset of node outputs) from a reference execution used for **comparison** (“golden” run). |
| **Assertion profile** | How to decide pass/fail: strict JSON equality on selected node outputs, JSON Schema validation, JMESPath/jq predicates, or **delegate to another flow** (evaluator subgraph). |
| **Evaluation run** | One attempt: executes the flow under test with the fixture, applies assertions, stores outcome + logs + timings. |

## What exists today (building blocks)

Relevant docs and code paths:

- **Authoring overrides:** `pin_data` on [`flow_revisions`](./flows2.md) — substitutes outputs for pinned nodes and skips their execution (`run_flow` in `packages/python/analytiq_data/flows/engine.py`).
- **Durable executions:** [`flow_executions`](./flows2.md); API under `packages/python/app/routes/flows.py` (run, list, fetch `run_data`).
- **Replay / partial semantics:** Engine supports **`dirty_node_ids`** and **`allowed_nodes`**-style subsets for reuse of prior `run_data` (step / scoped runs — see engine and frontend “Execute step” flows).

Evaluations **compose** these: they do not require a separate interpreter until you choose an “evaluator flow” strategy (§4.3).

## Target architecture

### 1. Data model (MongoDB)

Suggested collections (names indicative):

**`flow_eval_definitions`**

- `organization_id`, `flow_id`
- `name`, `description`, `tags`
- `flow_revid` (nullable → resolve to active revision at run time, or forbid for strict CI)
- `fixture`: JSON blob (trigger payload, `pin_data` map, optional param patches)
- `assertion_kind`: enum e.g. `json_match` | `schema` | `jmespath` | `evaluator_flow`
- `assertion_spec`: JSON — structure depends on `assertion_kind` (paths to compare, schema refs, JMESPath rules, or `evaluator_flow_id` + revision)
- Optional `baseline_execution_id` (reference run to diff against instead of inlined expected JSON)

**`flow_eval_runs`**

- `eval_definition_id`, `organization_id`, `triggered_by` (user / api / scheduler)
- `execution_id_under_test` (FK to `flow_executions`)
- Optional `evaluation_execution_id` (if assertion uses a second flow)
- `status`: `passed` | `failed` | `error` | `running`
- `metrics`: opaque JSON (`duration_ms`, custom floats from evaluator output)
- `failure_detail`: structured diff / message caps

Index by org + definition + created time for dashboards.

### 2. HTTP API (`/v0/orgs/{org}/flows/…`)

Rough surface:

| Method | Path | Purpose |
|--------|------|--------|
| `POST` | `…/eval-definitions` | Create definition |
| `GET` | `…/eval-definitions` | List (filter `flow_id`) |
| `GET`/`PATCH`/`DELETE` | `…/eval-definitions/{id}` | CRUD |
| `POST` | `…/eval-definitions/{id}/run` | enqueue / sync run |
| `GET` | `…/eval-definitions/{id}/runs` | history |

Reuse existing **`POST …/runs`** internally to create `flow_executions` for the workflow under test, passing **`pin_data`** and **`trigger_data`** from the fixture. Assertions run **after** execution completes (worker or synchronous API depending on SLA).

### 3. Runner (service layer)

 Pseudocode responsibilities:

1. Resolve **revision** (`flow_revid` or active).
2. Merge **fixture `pin_data`** onto revision `pin_data` (document merge rules — fixture wins).
3. Create execution with **`mode`** e.g. `evaluation` (optional; useful for analytics) and **`trigger_data`** from fixture.
4. Run **full** flow (preferred v1); fetch final `run_data`.
5. Resolve **baseline** expected outputs (stored JSON vs snapshot from `baseline_execution_id`).
6. Execute **assertion profile** → set `passed`/`failed`.

Runs should be **idempotent-friendly**: same fixture + same revision ⇒ comparable results (excluding timestamps); consider stripping volatile fields in comparators.

### 4. Assertion strategies (phased)

#### 4.1 JSON match (MVP)

- Compare `run_data[node_id].data.main` (or selected slot) to expected structure for a **fixed list of node ids**.
- Use deep equality with optional **ignore paths** (`meta`, `execution_time_ms`, etc.).

#### 4.2 JSON Schema on outputs

- For each target node output, validate against schema stored on the definition or referenced by URI.

#### 4.3 Evaluator flow (n8n-style)

- Second flow receives a **payload** `{ "baseline_run_data": …, "actual_run_data": … }` (possibly trimmed) via a synthetic trigger or a dedicated “evaluation input” convention.
- Last node emits a **single item** `{ "passed": bool, "metrics": { … } }` (contract documented in [`docs/docrouter_nodes.md`](./docrouter_nodes.md)-style appendix).
- DocRouter merges `metrics` into `flow_eval_runs.metrics`.

Defer until declarative/`python_class` ergonomics are solid; powerful for LLM-heavy flows.

### 5. Frontend

Phases:

1. **Flow editor**: “Evaluations” panel — list definitions, **Run**, view last status (badge).
2. **Definition editor**: form for fixture (`pin_data` JSON Monaco + presets from current canvas pins), assertion type, baseline picker (choose past execution).
3. **Runs** tab: timeline, diff viewer (borrow patterns from [`FlowLogsPanel`](../packages/typescript/frontend/src/components/flows/FlowLogsPanel.tsx) IO viewers).

### 6. Later: mocks and isolation

n8n can point some nodes at **mock pin data** while executing the rest; DocRouter already pins whole node outputs. Extend with:

- **Per-node mocks** listed in fixture (explicit node ids), without editing the revision document.
- **Stub credentials** hook (depends on credential system — see [`n8n_port_guide.md`](./n8n_port_guide.md) §7).

## Implementation phases (recommended)

| Phase | Deliverable | Outcome |
|-------|-------------|--------|
| **1** | `flow_eval_definitions` + `flow_eval_runs` + minimal API + internal runner with **`json_match`** assertions | Headless / API-only evals; CI can call `POST …/run` |
| **2** | Baseline from **existing execution id**; ignore-path lists; stable ordering for list outputs | Less brittle golden tests |
| **3** | UI list + run + view diff | Authors can manage evals without curl |
| **4** | JSON Schema assertions | Contract tests on node outputs |
| **5** | Evaluator flow + metrics aggregation | Parity with n8n’s “second workflow” pattern |
| **6** | Scheduler / webhooks on eval failure | Ops integration |

## Security and tenancy

- All routes **org-scoped**; definitions and runs must check **flow ownership** same as existing flow APIs.
- Fixture and baseline payloads may contain **PII** — apply same retention as `flow_executions` (`save_execution_data` settings).
- Eval runs consume **compute** like normal runs; rate-limit anonymous `POST …/run`.

## Related documents

- [`docs/flows2.md`](./flows2.md) — revisions, `pin_data`, executions model
- [`docs/flows_workflow_interop.md`](./flows_workflow_interop.md) — n8n comparison (expressions, semantics gaps)
- [`docs/n8n_port_guide.md`](./n8n_port_guide.md) — credentials and ported nodes (feeds evals on integration flows)

## Summary

DocRouter can implement **flow evaluations** without new core engine semantics: **persist definitions + fixtures**, **drive `run_flow` with `pin_data`**, then **post-process `run_data`**. The main engineering work is **data model + runner + API**, then **UI** and progressively richer **assertion** and **evaluator flow** modes.
