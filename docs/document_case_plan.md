# Document cases — implementation plan

Hyperscience groups work under a persisted **Case ID** ([case collation](https://help.hyperscience.ai/v43/docs/case-collation)). DocRouter cases mirror that: explicit membership, optional client-chosen ids (or auto-generated when omitted), tags and metadata on the case record.

## Goal

Org **cases** group documents for browse, bulk actions, and **one prompt over all documents in the case**. Uploads and flows **assign** documents; remove-from-case does **not** delete the document.

**Phase 3** adds **org-wide permissions** on all org REST (not cases only). Per-case ACL is deferred.

Document **tags** still drive OCR/LLM/flows. Case tags/metadata classify the case only; assign does not copy case metadata onto documents unless a client or flow sets it.

## Decisions

- **Case row + `docs.case_id`.** One case per document in v1 (nullable). Many-to-many deferred.
- **Case id:** client-supplied or auto `DR-{ulid}`; unique per org; pattern `^[A-Za-z0-9._:-]{1,128}$` (URL-safe). Case-sensitive.
- **Tags and metadata** on cases, same as documents (`tag_ids`, `Dict[str, str]`, trim/empty rules). No server-side case-to-case links—metadata values are plain strings (e.g. `policy_number=POL-998` is not validated as another case id).
- **Unknown case id on assign fails by default.** `create_case_if_missing` defaults `false` (upload, PUT, bulk, assign API). Flow assign node defaults `true` (§6).
- **Delete case:** clear `case_id` on docs by default; optional admin **cascade** deletes member documents via `delete_doc` (§2.4).
- **Phase 2:** case prompt runs; **retire** prompt `peer_match_keys` (API accepts, ignores—§4.1).

## 1. Data model

### 1.1 `cases`

```json
{
  "organization_id": "org1",
  "case_id": "CLM-123",
  "display_name": "Smith — auto loss",
  "tag_ids": ["..."],
  "metadata": { "claim_date": "2026-09-14", "policy_number": "POL-998" },
  "deleting_at": null,
  "created_by": "...",
  "created_at": "...",
  "updated_at": "..."
}
```

- Indexes: unique `(organization_id, case_id)`; `(organization_id, updated_at desc)`; `(organization_id, tag_ids)`. Optional metadata wildcard on `cases` if needed (MongoDB 7+).
- `updated_at` bumps on case edits and on assign/remove (§2.2).
- `deleting_at`: set during delete; case hidden from lists; assigns return `409`.
- **Document count:** computed at read time, not stored.

### 1.2 `docs`

| Field | Phase | Notes |
|-------|-------|--------|
| `case_id` | 1 | `str \| null` |
| `updated_at` | 1 | Bumped on every document write (below). Case run staleness (§4.2). |

Index: `(organization_id, case_id, upload_date desc)`.

**Document `updated_at`:** set whenever `document_name`, `tag_ids`, `metadata`, or `case_id` changes, and when OCR completes (anything that changes prompt `include` inputs). Use one document update helper on upload, PUT, bulk, assign-to-case, worker OCR, and flow writes. Optional backfill: `updated_at = upload_date` where missing.

### 1.3 Document vs case

| | Case | Document |
|---|------|----------|
| Purpose | Business grouping, case-level fields | File processing, extraction |
| Tags | e.g. claim / policy (org-defined) | Processing tags |

## 2. Backend (phase 1)

Module `analytiq_data/common/cases.py` (eager import in `common/__init__.py`).

**Operations:** CRUD; `list_cases` (search, tags, metadata_search, dates); assign/remove; `count_documents_in_case`. All membership changes go through assign/remove helpers (upload, PUT, bulk, case routes, flow node).

### 2.1 Routes (`app/routes/cases.py`)

| Method | Path | Notes |
|--------|------|--------|
| GET/POST | `/v0/orgs/{org}/cases` | Create; duplicate `case_id` → `409` |
| GET/PUT/DELETE | `/v0/orgs/{org}/cases/{case_id}` | DELETE `?cascade=` |
| GET/POST/DELETE | `.../cases/{case_id}/documents` | Assign `{ document_ids, create_case_if_missing? }`; remove one doc |

Phase 2: `.../runs`, `.../results`.

**Documents API:** filter/bulk by `case_id`. Upload: optional `case_id` + `create_case_if_missing`. **`PUT /documents/{id}`:** omitted `case_id` → unchanged; `null` → remove; string → assign (use Pydantic sentinel so omitted ≠ null). Bulk: same semantics.

### 2.2 Assign, remove, concurrency

Use **MongoDB transactions** (same pattern as KB indexing). In one transaction: ensure case exists and `deleting_at` is null (else `400`/`409`); **touch** case `updated_at`; set docs' `case_id`. Upload includes insert in the same transaction; roll back stored files if the transaction fails.

Optional `create_case_if_missing`: upsert case with `$setOnInsert`; on duplicate key, retry transaction once.

Cap **1,000** documents per assign transaction; larger bulks batch.

### 2.3 Delete

1. Set `deleting_at` (transaction).
2. **Default:** clear `case_id` on all member docs; delete case row and case runs (phase 2). In-request for moderate sizes; **`202` + worker** for very large cases.
3. **`cascade=true` (admin):** worker batch-deletes docs via **`delete_doc`**, then case row. UI confirms with count + typed case id.

**`delete_doc` (phase 1):** must remove stored files, flow results, the docs row, LLM/OCR, and KB index entries; extend as needed for flow executions, form submissions, etc.

Deleting a document does not delete the case (case may be empty).

### 2.4 Tests (`test_cases.py`)

Validation, CRUD, assign paths, `create_case_if_missing`, PUT omitted/null/string, delete/cascade, tags/metadata search, concurrent assign vs delete, `delete_doc` completeness.

## 3. Frontend (phase 1)

- **Cases** list + **case detail** (tags, metadata, documents, delete with cascade).
- **Documents:** filter by case; upload assign (explicit “create case” → `create_case_if_missing`); case chip on document; bulk assign/remove.

URLs: `/orgs/{orgId}/cases`, `/orgs/{orgId}/cases/{caseId}`, `/docs?case_id=`.

## 4. Case prompt runs (phase 2)

### 4.1 Retire `peer_match_keys`

Case runs replace peer grouping on single-document prompts. Keep field on API/SDK optional + deprecated; server **ignores** on write; responses `[]`; drop from revision equality and `_build_prompt_context` peer lookup; remove UI control; update tests and release notes.

### 4.2 Runs

- `POST .../cases/{case_id}/runs` `{ prompt_id }` → `queues.case_llm`.
- Worker: all docs with `case_id`, sorted by upload date, cap 50, token check, one `_build_prompt_context` call.
- **`case_llm_runs`** with `document_ids` snapshot; indexes in `index_registry.py`.
- **Stale** when: case membership ≠ run's `document_ids`; prompt revision ≠ run's `prompt_revid`; or any member document has `updated_at` **after** the run's `created_at` (covers name/tags/metadata/OCR changes without extra fields).
- **Results:** `GET .../results?prompt_id=` — grid like v1 group results; UI Results tab, run/re-run, CSV, run missing via bulk LLM on case.

Phase 3: start run requires document **read_write** (§5).

## 5. Org permissions (phase 3)

Each org member (non-admin) gets:

- **`document_access`:** `read_only` | `read_write`
- **`permissions`:** subset of `tags`, `schemas`, `prompts`, `forms`, `flows`, or `all` (config **definitions**, not org admin)

Admins: full admin + implicit read_write + all config.

**Migration:** existing members → `read_write` + `permissions: ["all"]`. New members default read_write, no config perms until granted.

| Write requires | |
|----------------|--|
| Upload, edit docs/cases, bulk, OCR/LLM/flow runs, case runs | `read_write` |
| Tag/schema/prompt/form/flow definitions | matching permission |
| Org settings, members, billing | admin |

Read config (tags, prompts, etc.) stays open to all members. Flows run as system; **`flows`** permission is powerful (can change documents including case membership via §6).

Enforce with FastAPI deps on every org route; route-table regression test; API tokens inherit user; UI disables writes globally.

Deferred: per-case ACL, KB permission name (§10).

## 6. Flows — Assign to case (phase 3)

Flow node: `case_id` (or generate), `document_id`, `create_case_if_missing` default **true**, optional case display_name/tags/metadata. Calls same assign helper as API. Runs as system on execution; authored by users with `flows` permission.

## 7. SDK / MCP

Phase 1–3: case + document APIs as above; phase 2 runs/results; phase 3 member permission fields; phase 4 MCP tools respect user permissions.

## 8. Phases

| Phase | Exit |
|-------|------|
| **1** | Cases, assign, delete, full `delete_doc`, UI, SDK, tests |
| **2** | Case runs + results; document `updated_at` on all write paths; ignore `peer_match_keys` |
| **3** | Org permissions on all REST; assign-to-case node |
| **4** | MCP/agent; optional case webhook events |

## 9. Why cases (not metadata-only groups)

Explicit membership and case-level tags/metadata; stable id like Hyperscience; one case per doc simplifies future per-case ACL. See [`document_groups_plan.md`](document_groups_plan.md) / [`document_group_plan2.md`](document_group_plan2.md) for abandoned approaches.

## 10. Open questions

1. Auto id: `DR-{ulid}` vs sequential.
2. Empty cases via `POST /cases` — allowed; confirm product copy.
3. Merge cases — defer.
4. Batch upload sharing one `case_id`.
5. Per-case ACL later.
6. Required metadata per case tag (JSON Schema) — defer.
7. KB: own permission vs `all` only.

## 11. Deferred

Retention/scheduled deletion; multi-case membership; case JSON export; case-level LLM on case record; auto case prompt when processing complete; ImageRight import; access audit.
