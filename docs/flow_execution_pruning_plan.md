# Flow execution pruning (n8n-style, per-organization)

Replace the current global age-only hard delete (`FLOW_EXECUTION_RETENTION_DAYS`) with an **n8n-modeled two-phase prune** (soft delete → hard delete), with **retention policy configurable per organization** (not environment variables). Use n8n’s defaults as DocRouter’s defaults.

**Reference:** sibling tree `../n8n` — `packages/cli/src/services/pruning/executions-pruning.service.ts`, `packages/@n8n/config/src/configs/executions.config.ts`, `ExecutionRepository.softDeletePrunableExecutions` / `findSoftDeletedExecutions`.

**Related code today:**

- `packages/python/worker/worker.py` → `worker_flow_cleanup` (hourly hard delete by `finished_at`, env `FLOW_EXECUTION_RETENTION_DAYS` default 30)
- Manual delete: `packages/python/app/routes/flows.py` → `_delete_execution_blobs_and_doc`
- Org settings precedent: `organizations.ocr_config` / `OrganizationEdit.tsx`

**Implementation order:** Phase 1 (schema + soft/hard prune + per-org config API) → Phase 2 (org settings UI) → Phase 3 (remove env retention; list/filter soft-deleted) → Phase 4 (optional keep/pin exempt).

---

## Goals

1. Age **and** count-based pruning of finished flow executions, matching n8n’s two-phase design.
2. All prune **policy** knobs live on the organization document; admins change them in the product, not via deploy env.
3. Safe grace period between “hidden/queued for delete” and permanent blob+row removal.
4. Keep stale-execution recovery (`recover_stale_flow_executions`) separate from pruning.
5. **Preserve document-attached flow outputs** across execution prune; delete them only with the document (see below).

## Non-goals

- Execution **annotations** (n8n EE up/down vote, notes, annotation tags) in v1 — DocRouter has no equivalent UX. Call out a simple **keep/pin** flag as a later exempt mechanism if needed.
- Per-flow override of prune settings (org-level only for v1).
- Changing how executions are created, resumed, or listed beyond excluding soft-deleted rows by default.
- Mongo TTL indexes for `flow_executions` (app-driven soft/hard delete stays explicit so blobs are cleaned).
- Pruning or GC of `flow_results` by age/count — those rows are document-scoped product data, not execution history.

---

## `flow_results` vs execution prune

Document-attached captured outputs live in **`flow_results`** (one row per `(document_id, flow_id)`). That collection is **out of scope for prune**.

| Event | `flow_executions` + `flow_blobs` | `flow_results` |
|-------|----------------------------------|----------------|
| Soft/hard **execution prune** | Soft-delete then hard-delete | **Do not touch** |
| Manual delete of an execution | Hard-delete (today) | **Do not touch** |
| **Document delete** | (unchanged) | **Delete** via `delete_flow_results_for_document` (already in `documents.py`) |
| **Flow delete** | Delete executions for the flow | Delete via `delete_flow_results_for_flow` (already in `flows.py`) — unchanged; not part of prune |

Hard-delete helpers used by the prune worker must only remove the execution row and its `flow_blobs` prefix — never call `delete_flow_results_*`.

**Implication:** after a successful run is pruned, `flow_results.execution_id` may point at a missing `flow_executions` document. Document Flows UI / bulk “outdated” checks must tolerate a missing execution (treat stored JSON + revision metadata on the `flow_results` row as authoritative; do not require the execution to still exist). Add/adjust tests for that path.

---

## Current behavior (baseline)

| Piece | Behavior |
|-------|----------|
| Worker | `worker_flow_cleanup` every **1 hour** |
| Policy | `FLOW_EXECUTION_RETENTION_DAYS` (default **30**), process-wide |
| Delete | Immediate hard delete of `success` / `error` / `cancelled` with `finished_at < cutoff` + `flow_blobs` prefix |
| Soft delete | None |
| Max count | None |
| Org config | None |

---

## Target behavior (n8n model)

### Two phases

1. **Soft delete** — set `deleted_at` on finished, eligible executions. Rows remain in Mongo; default list/detail APIs hide them (or treat as gone). Blobs still present until hard delete.
2. **Hard delete** — for rows with `deleted_at` older than the org’s hard-delete buffer: delete `flow_blobs` under `{execution_id}/`, then delete the `flow_executions` document (same cleanup as today’s manual delete helper). **Do not** delete or update `flow_results`.

### Eligibility (soft delete)

Terminal statuses only: `success`, `error`, `cancelled` (same as today). Never soft-delete `running`, `waiting`, or other non-terminal states.

An execution is soft-deletable if **either**:

- **Age:** `finished_at <= now - max_age_hours`, or
- **Count:** among that org’s non-deleted finished executions, it falls outside the newest `max_count` by `finished_at` (then `_id`) — i.e. keep the newest N per org; older surplus is marked.

If both age and count apply, union of candidates (same idea as n8n’s OR of time-based and count-based predicates). `max_count = 0` means unlimited (age-only), matching n8n.

### Hard-delete buffer

Only hard-delete when `deleted_at <= now - hard_delete_buffer_hours`. Default **1 hour** — grace so a just-pruned run is not wiped instantly.

### Worker cadence

Replace the single hourly hard-delete loop with a cleanup worker that:

- Continues **stale recovery** on its own short interval (keep today’s ~60s).
- Runs a **tick** often enough to honor per-org intervals (recommend fixed **60s** tick; do not put the tick in env).
- For each organization with pruning enabled, if enough time has passed since that org’s last soft/hard pass (see below), run soft then/or hard for that org only.

Per-org soft/hard **intervals** are policy (“how often we reconsider this org”), not process env vars. Track `last_soft_prune_at` / `last_hard_prune_at` either:

- on the organization document, or
- in a small `flow_prune_state` collection keyed by `organization_id`

(Prefer updating timestamps on the org doc only if write volume is fine; otherwise a side collection avoids churning org documents.)

---

## Per-organization settings

Store under `organizations.flow_execution_prune` (mirror `ocr_config`: nested object, merge with defaults when missing).

| Field | Type | Default (n8n) | Meaning |
|-------|------|---------------|---------|
| `enabled` | bool | `true` | Master switch for this org |
| `max_age_hours` | int | `336` (14 days) | Soft-delete finished runs older than this |
| `max_count` | int | `10000` | Keep at most this many non-deleted finished runs per org; `0` = unlimited |
| `hard_delete_buffer_hours` | int | `1` | Minimum age of `deleted_at` before hard delete |
| `soft_delete_interval_minutes` | int | `60` | Minimum minutes between soft-delete passes for this org |
| `hard_delete_interval_minutes` | int | `15` | Minimum minutes between hard-delete passes for this org |

**Validation (API):** non-negative ints; `max_age_hours` / buffer reasonable upper clamps (e.g. age ≤ 8760, intervals ≤ 10080); reject unknown keys; merge partial updates like `apply_ocr_config_update`.

**Not env vars:** remove use of `FLOW_EXECUTION_RETENTION_DAYS` once this ships. Optional one-release read of the old env only as a migration hint is unnecessary if defaults match product intent (14d vs old 30d — document the default change in release notes).

### API / UI

- Extend org GET/PATCH models in `app/routes/orgs.py` and frontend `organizations.ts` / `OrganizationEdit.tsx` with `flow_execution_prune`.
- Org admins only (same auth as other org settings).
- UI: short explanation + toggles/fields for the six knobs; show defaults as placeholders.

---

## Data model

### `flow_executions`

- Add optional `deleted_at: datetime | null` (absent/`null` = active).
- Soft delete: `$set: { deleted_at: now }`.
- Indexes (add via `index_registry` + migration):
  - Soft candidates: `{ organization_id: 1, deleted_at: 1, finished_at: 1, status: 1 }` (or equivalent supporting age query with `deleted_at: null`).
  - Hard candidates: `{ deleted_at: 1 }` (partial filter `deleted_at` exists) or `{ organization_id: 1, deleted_at: 1 }`.
  - Count-based prune: rely on existing org/`finished_at` list indexes; verify with explain on large fixtures.

### List / get behavior

- Default list executions: `{ deleted_at: null }` (or `$in: [null]` / field missing).
- GET by id: 404 if soft-deleted (same as hard-deleted for clients), unless an explicit admin `include_deleted` is added later (not required for v1).
- Manual DELETE endpoint: keep immediate hard delete (blobs + row); do not require soft phase.

---

## Soft-delete algorithm (per org)

Pseudo:

```
cfg = merge_org_flow_prune(org.flow_execution_prune)
if not cfg.enabled: return

# Age-based
age_cutoff = now - timedelta(hours=cfg.max_age_hours)
mark deleted_at where:
  organization_id = org
  deleted_at is null
  status in terminal
  finished_at < age_cutoff

# Count-based (if max_count > 0)
keep_ids = newest max_count finished non-deleted for org (sort finished_at desc, _id desc)
mark deleted_at where:
  organization_id = org
  deleted_at is null
  status in terminal
  _id not in keep_ids
```

Batch updates (e.g. `update_many` with `_id: { $in: batch }`) to avoid unbounded memory.

## Hard-delete algorithm (per org)

```
buffer_cutoff = now - timedelta(hours=cfg.hard_delete_buffer_hours)
for each execution where organization_id = org and deleted_at <= buffer_cutoff (batch of 100):
  delete_blobs_by_prefix(flow_blobs, f"{execution_id}/")
  delete flow_executions doc
  # never: delete_flow_results_* 
```

Reuse `_delete_execution_blobs_and_doc` (or extract shared helper used by HTTP delete and worker). That helper must remain execution-scoped only.

If a batch is full (100), run another hard pass soon for that org (n8n speeds hard interval to ~1s when backlog is high — optional; v1 can just complete multiple batches in one hard pass up to a safety cap).

---

## Worker changes

Refactor `worker_flow_cleanup`:

1. Keep heartbeat + `recover_stale_flow_executions` (~60s).
2. On each tick (~60s): load orgs that need soft and/or hard work (enabled + interval elapsed).
3. Soft-delete per due org; hard-delete per due org.
4. Update per-org last-run timestamps.
5. Log counts with `organization_id` and phase.

Multi-replica: only one cleanup worker should run cluster-wide (today a single `flow_cleanup_0` task is started per process — if multiple worker processes exist, add a **leader lease** similar to flow scheduler, or document that only one worker role runs `flow_cleanup`). Call this out explicitly in implementation.

---

## vs n8n (intentional differences)

| n8n | DocRouter |
|-----|-----------|
| Global env config | Per-organization document + API/UI |
| Annotated executions exempt | No annotations in v1; optional later **keep/pin** |
| Instance-wide max count | **Per-organization** max count |
| Soft/hard intervals via env | Per-org interval fields; worker tick fixed in code |
| `stoppedAt` | `finished_at` |
| SQL soft-delete column | Mongo `deleted_at` |

---

## Phases

### Phase 1 — Backend prune engine

- [ ] `flow_execution_prune` merge/validate helpers (`analytiq_data/flows/prune_config.py` or similar)
- [ ] Org create/get/update API fields
- [ ] `deleted_at` on executions; indexes
- [ ] Soft + hard prune functions; wire `worker_flow_cleanup`
- [ ] Tests: age, count, buffer, disabled org, terminal-only, blob cleanup
- [ ] Tests: hard prune leaves `flow_results` intact; document delete still removes `flow_results`
- [ ] Sidebar / result GET tolerates pruned `execution_id` (missing execution)
- [ ] Stop reading `FLOW_EXECUTION_RETENTION_DAYS` (or ignore with log warning)

### Phase 2 — Org settings UI

- [ ] Types + `OrganizationEdit` section for flow execution pruning
- [ ] Copy explaining soft vs hard and defaults (14 days / 10k / 1h buffer)

### Phase 3 — API visibility polish

- [ ] Ensure all execution list/detail paths exclude soft-deleted
- [ ] Release notes: default retention **30 days → 14 days** (n8n default) unless org overrides

### Phase 4 (optional follow-up) — Keep / pin

- [ ] `keep: true` (or bookmark) on execution exempts from soft delete — lightweight stand-in for n8n annotations
- [ ] UI affordance on execution detail

---

## Test plan

- Soft-delete by age; newer run untouched.
- Soft-delete by count with `max_count=1`; newest kept, older marked.
- `max_count=0` → no count-based soft delete.
- Soft-deleted row excluded from list; hard delete after buffer removes row + blobs.
- Hard delete does not touch rows with recent `deleted_at` inside buffer.
- `enabled=false` → no soft/hard for that org; other orgs unaffected.
- Running/waiting never soft-deleted.
- Manual DELETE still hard-deletes immediately.
- Interval gating: second soft pass within `soft_delete_interval_minutes` is a no-op.
- After hard prune of an execution that was captured into `flow_results`, the `flow_results` row remains and document result API still returns it.
- Document delete removes matching `flow_results` (existing behavior; regression-test).

---

## Defaults cheat sheet (ship these)

```text
enabled: true
max_age_hours: 336
max_count: 10000
hard_delete_buffer_hours: 1
soft_delete_interval_minutes: 60
hard_delete_interval_minutes: 15
```

Same numbers as n8n `EXECUTIONS_DATA_PRUNE*` defaults; stored per org instead of env.
