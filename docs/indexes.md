# MongoDB Index Management Plan

Plan to consolidate how DocRouter creates, updates, and retires MongoDB indexes. Goal: **one coordinated, lock-protected reconcile step after migrations**, plus **idempotent create-only safety nets at startup** — never destructive index ops in FastAPI lifespan.

**Motivation:** A customer deploy failed startup when 16 Uvicorn workers concurrently ran `drop_index` + `create_index` on `prod.flow_executions`. MongoDB aborted in-flight index builds (`IndexBuildAborted`, code 276) when another worker issued `dropIndexes`.

**Status** (as of 2026-07-02; current schema version **44**):

| Item | State |
|------|--------|
| Registry + `reconcile_indexes()` under migration lock | **Done** — `index_registry.py`, `index_reconcile.py` |
| Lifespan safety: remove `drop_index`, fix `init_payments` | **Done** |
| Wire reconcile into `run_migrations` (lock even when schema current) | **Done** |
| Legacy auto-named index rename on reconcile | **Done** — drop same-key legacy name, create canonical name |
| Explicit `name=` on flow-trigger startup indexes | **Done** |
| `ensure_index` default `drop_other_indexes=False` | **Done** |
| Consolidate scattered startup `ensure_*` calls | **Done** — `ensure_runtime_indexes()` in `main.py` |
| Expand registry to migration-only indexes | **Done** — Phase 2 entries + worker queues + deprecated `token_1` |
| CI lint for destructive index ops outside migrate/reconcile | **Not started** (Phase 4) |

No separate index-only migration (e.g. “migration 45”) — reconcile under lock supersedes it.

---

## Goals

1. **No index drops in lifespan** — FastAPI startup runs once per Uvicorn worker (and per replica); destructive ops race.
2. **Schema/index definition changes** happen under the **migration lock** (versioned migration or post-migrate reconcile).
3. **Missing indexes** are healed automatically on deploy without requiring a version bump every time.
4. **Explicit retirement** of deprecated indexes — never auto-drop “unknown” indexes.
5. **Dev ergonomics** — fresh local DBs still get indexes even if someone skips the compose `migrate` service.

---

## Non-goals

- Replacing versioned migrations for **data backfills** or one-time data transforms.
- Auto-detecting and dropping “unused” indexes from production (too risky; query patterns and manual ops are invisible to code).
- Reconciling **dynamic** collection names (e.g. `queues.kb_index_*`) in a static registry — those stay feature-local.

---

## Current state (after Phase 1)

### Where indexes are created today

| Layer | Entry point | Lock? | Destructive ops? | When it runs |
|-------|-------------|-------|------------------|--------------|
| **Migrations + reconcile** | `migrate.py`, `startup.setup_database()` → `run_migrations()` | **Yes — always** | Reconcile only (under lock) | Every `run_migrations` call |
| **Deploy housekeeping** | `release_all_in_flight_queue_claims()` inside `run_migrations` | N/A | No | Every `run_migrations` call |
| **Lifespan** | `app/main.py` | No | **No** — create-only (`init_payments` uses `drop_other_indexes=False`) | Every Uvicorn worker |
| **Flow trigger service** | `ensure_flow_trigger_indexes()` via `start_flow_trigger_service()` | No | **No** — create-only | Every worker, if `FLOW_SCHEDULER_ENABLED=1` |
| **Feature-local lazy** | e.g. `ensure_reconciliation_lock_indexes` | No | No (create only) | On first use |

### Who runs migrations in production

| Path | When it runs | Notes |
|------|--------------|-------|
| **`migrate.py`** (compose/K8s migrate job) | Once per deploy, before backends | **Primary** prod path |
| **`startup.setup_admin` → `setup_database`** | When `ADMIN_EMAIL` and `ADMIN_PASSWORD` are set | Dev / bootstrap; also runs reconcile under lock |
| **Typical prod (no admin env)** | Workers never call `run_migrations` | Index correctness depends on migrate job |

### Lifespan index ensures (today)

Single call from `packages/python/app/main.py`:

- `ad.mongodb.ensure_runtime_indexes(db)` — create-only, all registry indexes (including flow paths), not gated on `FLOW_SCHEDULER_ENABLED`

`init_payments` is Stripe sync only. `start_flow_trigger_service` starts listeners only.

### Incident root cause (2026-07-02)

`ensure_docrouter_flow_trigger_indexes` previously called `drop_index` on every worker startup, racing with concurrent `create_index` calls (`IndexBuildAborted`, code 276).

**Fixed in Phase 1:** reconcile owns drop+recreate under lock; lifespan is create-only.

### Legacy auto-named indexes

Pre-Phase-1 startup code created indexes without explicit `name=` (e.g. `flow_id_1_node_id_1`). Reconcile now detects same-key legacy indexes and replaces them with canonical registry names (drop legacy + create named). Without this, MongoDB returns `IndexOptionsConflict` (code 85).

---

## Design principles

### 1. Two classes of index operations

| Class | Examples | Where |
|-------|----------|--------|
| **Reconcile** (may drop + recreate) | Partial filter changed, unique flag changed, legacy name rename | Migration lock only |
| **Ensure** (create if absent) | Same spec as production; idempotent | Lifespan / dev safety net |

### 2. Lifespan rules

- **Allowed:** `create_index` with stable, documented spec (no-op if index matches).
- **Forbidden:** `drop_index`, `dropIndexes`, `ensure_index(..., drop_other_indexes=True)`.
- **Rationale:** N workers × M replicas = uncoordinated writers.

### 3. Migration lock rules

- **Versioned migrations:** one-time schema/data changes; may include index create/drop tied to that change.
- **Post-migrate reconcile:** desired-state sync for the **curated registry**; runs under the same lock on every deploy.

### 4. Deprecation rules

- Retired indexes are listed in `DEPRECATED_INDEXES` (name + collection), not inferred.
- Remove from registry + add to deprecated list in the **same PR** that stops using the index in queries.

### 5. Explicit index names

Every registry entry and lifespan `create_index` uses an explicit `name=`. Reconcile renames legacy auto-generated names on first deploy after Phase 1.

---

## Target architecture (implemented)

```
deploy
  │
  ├─ migrate.py / setup_database()
  │     │
  │     ├─ release_all_in_flight_queue_claims()     # every call, no lock
  │     │
  │     ├─ acquire migration_lock                   # every call (no fast-path skip)
  │     │
  │     ├─ run pending versioned migrations         # if schema_version != target
  │     │
  │     ├─ reconcile_indexes(db)                    # under lock, every deploy
  │     │     ├─ for spec in EXPECTED_INDEXES:
  │     │     │     create | skip | drop+recreate | rename legacy same-key index
  │     │     └─ for spec in DEPRECATED_INDEXES: drop if exists
  │     │
  │     └─ release migration_lock
  │
  └─ backend workers (lifespan)
        └─ ensure_runtime_indexes(db)              # create-only; same registry as reconcile
```

### Implementation modules

| Module | Role |
|--------|------|
| `analytiq_data/mongodb/index_registry.py` | `IndexSpec`, `EXPECTED_INDEXES`, `DEPRECATED_INDEXES`, shared dedupe constants |
| `analytiq_data/mongodb/index_reconcile.py` | `reconcile_indexes()`, spec comparison, legacy rename |
| `analytiq_data/migrations/migration.py` | Calls `reconcile_indexes` after migrations under lock |

### `reconcile_indexes(db)` behavior

1. For each `IndexSpec` in `EXPECTED_INDEXES`:
   - If named index missing but **same-key legacy index exists** → drop legacy, create canonical name (counts as `updated`).
   - If missing entirely → `create_index` (`created`).
   - If present and spec matches → skip (`unchanged`).
   - If present and spec differs → log warning, `drop_index(name)`, `create_index` (`updated`).
2. For each entry in `DEPRECATED_INDEXES` → `drop_index` if exists (`dropped`).
3. Log summary: created / updated / dropped / unchanged counts.

**Do not:** drop indexes not listed in either registry (protects manual prod indexes until explicitly deprecated).

**Spec comparison:** normalized keys, unique, sparse, `partialFilterExpression`, `expireAfterSeconds`.

---

## Relationship to versioned migrations

| Concern | Versioned migration | Registry reconcile |
|---------|---------------------|-------------------|
| Index added with new feature | Add to registry | Registry is source of truth |
| Index **definition** change | Optional one-time migration for history | Registry encodes new spec; reconcile fixes drift |
| Legacy auto-named index | N/A | Reconcile renames on deploy |
| Data backfill | Migration only | N/A |
| Rollback (`down()`) | Migration drops indexes it created | Remove from registry / add to deprecated |

**New indexes:** add to `EXPECTED_INDEXES` in `index_registry.py`. No schema bump required for index-only changes.

---

## Registry inventory

### Phase 1 — in registry today (`EXPECTED_INDEXES`)

| Collection | Index name | Keys / options |
|------------|------------|----------------|
| `embedding_cache` | `chunk_hash_embedding_model_unique` | `(chunk_hash, embedding_model)` unique |
| `credentials` | `credentials_org_kind_key` | `(organization_id, kind_key)` |
| `flow_oauth_states` | `flow_oauth_states_ttl` | `expires_at` TTL |
| `payments_usage_records` | `org_timestamp_idx` | `(org_id, timestamp)` |
| `flow_static_data` | `flow_static_data_flow_node_unique` | `(flow_id, node_id)` unique |
| `flow_trigger_leases` | `flow_trigger_leases_expires_at_ttl` | `expires_at` TTL |
| `flow_trigger_registrations` | `flow_trigger_registrations_flow_node_rule_unique` | `(flow_id, node_id, rule_index)` unique |
| `flow_trigger_registrations` | `flow_trigger_registrations_flow_id` | `(flow_id)` |
| `flow_executions` | `flow_executions_trigger_dedupe_key_unique` | `trigger.dedupe_key` unique sparse |
| `flow_executions` | `flow_executions_active_flow_document_unique` | `(flow_id, trigger.document_id)` unique + partial filter |
| `flow_triggers` | `flow_triggers_flow_node_unique` | `(flow_id, trigger_node_id)` unique |
| `flow_triggers` | `flow_triggers_org_trigger_type` | `(org_id, trigger_type)` |
| `flow_results` | `flow_results_doc_flow_unique` | `(document_id, flow_id)` unique |
| `flow_results` | `flow_results_org_document` | `(org_id, document_id)` |
| `flow_results` | `flow_results_org_flow` | `(org_id, flow_id)` |

Lifespan `ensure_*` calls remain as create-only safety nets (redundant with reconcile after migrate). Phase 2 indexes are in the same `EXPECTED_INDEXES` tuple — see **Phase 2 registry additions** under Implementation phases.

### Excluded from static registry

- **Atlas Search** (`kb_vectors_*` / `kb_lexical_index`) — created via `createSearchIndexes` per KB
- **`migration_lock`**, internal lock collections
- **`reconciliation_locks`** — lazy create-only on first KB reconcile

Worker **`queues.kb_index_*`** collections are included dynamically when present (same index templates as static queues).

---

## Implementation phases

### Phase 1 — Registry, reconcile, and lifespan safety (**done**)

- [x] `index_registry.py` — 15 indexes, dedupe constants
- [x] `index_reconcile.py` — spec match, legacy same-key rename, summary logging
- [x] `run_migrations` — lock on every call, reconcile after migrations
- [x] Lifespan: remove `drop_index` from `ensure_docrouter_flow_trigger_indexes`
- [x] Lifespan: explicit names on flow-trigger indexes; `init_payments` non-destructive
- [x] `ensure_index` default `drop_other_indexes=False`
- [x] Tests: `packages/python/tests/test_index_reconcile.py`

### Phase 2 — Expand registry (**done**)

- [x] Audit `create_index` in `migration.py` (webhooks, queues, docs, llm_runs, KB, prompts, flows, chat, GridFS, access_tokens)
- [x] Add 26 Phase 2 `IndexSpec` rows to `index_registry.py` (37 fixed + queue templates)
- [x] Worker queue indexes via `WORKER_QUEUE_INDEX_TEMPLATES` × static queues + dynamic `queues.kb_index_*`
- [x] GridFS indexes with `skip_if_collection_missing` until bucket namespaces exist
- [x] `DEPRECATED_INDEXES`: legacy `access_tokens.token_1`
- [x] Tests: queue indexes, GridFS skip, deprecated drop

**Still excluded:** Atlas Search lexical indexes (`kb_vectors_*`), dynamic KB queue provisioning, `reconciliation_locks` lazy ensures.

### Phase 2 registry additions (beyond Phase 1)

| Area | Indexes |
|------|---------|
| `access_tokens` | `access_tokens_fingerprint_unique` |
| `webhook_deliveries` | `webhook_deliveries_org_created_at`, `webhook_deliveries_status_next_attempt_at`, `webhook_deliveries_org_webhook_created_at` |
| `webhook_endpoints` | `webhook_endpoints_org_created_at` |
| `document_index` | `kb_id_document_id_unique_idx`, `document_id_idx` |
| `docs` | `org_upload_date_idx` |
| `llm_runs` | `doc_prompt_version_idx`, `doc_prompt_revid_idx` |
| `knowledge_bases` | `reconcile_status_idx` |
| `prompt_revisions` | `prompt_id_latest_idx`, `prompt_id_tag_ids_idx` |
| `schema_revisions` | `schema_id_latest_idx` |
| `prompts` | `organization_id_idx` |
| `credentials` | `credentials_org_name_unique`, `credentials_org_updated_at` |
| `flow_executions` | `flow_executions_org_started_at`, `flow_executions_org_flow_started_at` |
| `flows` | `flows_org_updated_at` |
| `chat_threads` | `chat_threads_doc_list_idx`, `chat_threads_kb_list_idx` |
| GridFS | `files.files`, `files.chunks`, `ocr.files`, `ocr.chunks` (when present) |
| Worker queues | `status_created_at_idx`, `status_processing_attempts_idx` per queue collection |

### Phase 3 — Consolidate startup (**done**)

- [x] `ensure_runtime_indexes()` — create-only path in `index_reconcile.py`
- [x] `main.py` — one call replaces scattered `ensure_*`
- [x] Removed index creation from `start_flow_trigger_service`
- [x] Removed index creation from `init_payments`
- [x] Flow indexes no longer gated on `FLOW_SCHEDULER_ENABLED`
- [x] `MIGRATIONS.md` cross-link to `docs/indexes.md`
- [x] Tests: `test_ensure_runtime_indexes_create_only_no_recreate`

Legacy `ensure_*` helpers remain in feature modules for targeted tests; production path uses registry + reconcile / `ensure_runtime_indexes` only.

### Phase 4 — Ops & docs

1. Runbook: index build slow on large collection — monitor `currentOp` during first reconcile after spec change.
2. CI lint: `drop_index` / `dropIndexes` / `drop_other_indexes=True` only in `migrations/` and `index_reconcile.py`.

---

## Testing plan

| Test | Status | Purpose |
|------|--------|---------|
| `test_reconcile_creates_missing_indexes` | Done | Fresh DB gets all registry indexes |
| `test_reconcile_idempotent_when_aligned` | Done | Second run is all `unchanged` |
| `test_index_spec_matches_partial_filter` | Done | Mismatched partial filter triggers recreate |
| `test_reconcile_renames_legacy_auto_named_index` | Done | `flow_id_1_node_id_1` → canonical name |
| `test_parallel_ensure_docrouter_flow_trigger_indexes` | Done | 16 workers, create-only, no race |
| `test_run_migrations_reconciles_when_schema_current` | Done | Reconcile runs at v44 without new migration |
| Deploy smoke (`N_UVICORN_WORKERS=16`) | Manual | No `IndexBuildAborted` after migrate |

---

## Rollout notes

- **No schema bump required** — reconcile runs under lock even when schema stays at v44.
- **Migrate before backend** on every deploy (reconcile is not per-worker).
- **First deploy after Phase 1** on existing DBs may show `updated` counts as legacy auto-named indexes are renamed.
- Large `flow_executions` collections: first reconcile may take time building the partial unique index — monitor `currentOp`.
- High worker counts are safe: lifespan is create-only; destructive work runs once under lock.

---

## Open questions (resolved / remaining)

1. ~~Reconcile on every deploy vs only on version bump?~~ **Resolved:** every deploy under lock.
2. ~~Should backend workers call reconcile?~~ **Resolved:** only via `run_migrations` (migrate job or dev bootstrap), never per Uvicorn worker concurrently.
3. **Background index builds:** confirm MongoDB server version behavior for `background=True` (semantics changed in 4.2+).

---

## References

- `packages/python/analytiq_data/mongodb/index_registry.py` — registry and dedupe constants
- `packages/python/analytiq_data/mongodb/index_reconcile.py` — reconcile logic
- `packages/python/analytiq_data/migrations/migration.py` — lock, `run_migrations`
- `packages/python/analytiq_data/docrouter_flows/event_dispatch.py` — docrouter trigger indexes (create-only)
- `packages/python/analytiq_data/flows/triggers/service.py` — flow trigger indexes (explicit names)
- `packages/python/app/main.py` — lifespan ensures
- `packages/python/app/startup.py` — admin-gated migration path
- `packages/python/app/routes/payments.py` — `init_payments`
- `packages/python/migrate.py` — compose/k8s migrate entry
- `packages/python/tests/test_index_reconcile.py` — reconcile tests
- Customer log: `log3.txt` (2026-07-02, `IndexBuildAborted` on startup)
