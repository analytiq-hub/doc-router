# Document cases — implementation plan

Hyperscience groups work under a persisted **Case ID** ([case collation](https://help.hyperscience.ai/v43/docs/case-collation)). DocRouter cases mirror that: explicit membership, optional client-chosen ids (or auto-generated when omitted), tags and metadata on the case record.

## Goal

Org **cases** group documents for browse, bulk actions, and **one prompt over all documents in the case**. Uploads and flows **assign** documents; remove-from-case does **not** delete the document.

Org-wide **roles and permissions** (phase 3) are specified in [`permissions.md`](permissions.md). Per-case ACL stays deferred there.

Document **tags** still drive OCR/LLM/flows. Case tags/metadata classify the case only; assign does not copy case metadata onto documents unless a client or flow sets it.

## Decisions

- **Case row + `docs.case_id`.** One case per document in v1 (nullable). Many-to-many deferred.
- **Case id:** client-supplied or auto `DR-{ulid}`; unique per org; pattern `^[A-Za-z0-9._:-]{1,128}$` (URL-safe). Case-sensitive.
- **Tags and metadata** on cases, same as documents (`tag_ids`, `Dict[str, str]`, trim/empty rules). No server-side case-to-case links—metadata values are plain strings (e.g. `policy_number=POL-998` is not validated as another case id).
- **Unknown case id on assign fails by default.** `create_case_if_missing` defaults `false` (upload, PUT, bulk, assign API). Flow assign node defaults `true` (§5).
- **Delete case:** clear `case_id` on docs by default; optional org **admin** **cascade** deletes member documents via `delete_doc` (§2.4); see [`permissions.md`](permissions.md).
- **Phase 2:** case prompt runs; **retire** prompt `peer_match_keys` (removed from API; legacy request fields ignored—§4.1).
- **OCR re-run:** does **not** require refreshing stored LLM results (per-document or case-scoped). Re-run case or document prompts explicitly when new OCR text should be extracted.

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
| `updated_at` | 1 | Bumped on document **metadata** writes (below). Case run staleness (§4.2). |

Index: `(organization_id, case_id, upload_date desc)`.

**Document `updated_at`:** set when `document_name`, `tag_ids`, `metadata`, or `case_id` changes (upload, PUT, bulk, assign-to-case, flow writes that touch those fields). **Do not** bump on OCR completion or OCR re-run—stored LLM and case LLM results stay valid until the user re-runs a prompt. Use one document update helper for the fields above. Optional backfill: `updated_at = upload_date` where missing.

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
| GET/PUT/DELETE | `/v0/orgs/{org}/cases/{case_id}` | DELETE `?cascade=` — default `200`; `cascade=true` → **`202`** (see §2.3) |
| GET/POST/DELETE | `.../cases/{case_id}/documents` | Assign `{ document_ids, create_case_if_missing? }`; remove one doc |

Phase 2: `.../runs`, `.../results`.

**Documents API:** filter/bulk by `case_id`. Upload: optional `case_id` + `create_case_if_missing`. **`PUT /documents/{id}`:** omitted `case_id` → unchanged; `null` → remove; string → assign (use Pydantic sentinel so omitted ≠ null). Bulk: same semantics.

### 2.2 Assign, remove, concurrency

Use **MongoDB transactions** (same pattern as KB indexing). In one transaction: ensure case exists and `deleting_at` is null (else `400`/`409`); **touch** case `updated_at`; set docs' `case_id`. Upload includes insert in the same transaction; roll back stored files if the transaction fails.

Optional `create_case_if_missing`: upsert case with `$setOnInsert`; on duplicate key, retry transaction once.

Cap **1,000** documents per assign transaction; larger bulks batch.

### 2.3 Delete

1. Set `deleting_at` (transaction). A second DELETE with the same `cascade` flag **resumes** an interrupted delete; mismatched `cascade` → `409`.
2. **Default (`cascade=false`):** synchronous **`200`** — clear `case_id` on all member docs, delete case row and case runs (phase 2). Runs in the API request (fine for typical case sizes).
3. **`cascade=true` (org admin):** always **`202 Accepted`** — batch-delete member docs via **`delete_doc`** in a FastAPI background task, then remove the case row. Same response for empty or large cases; clients should not expect the case to disappear immediately. Poll **`GET .../cases/{case_id}`** until `404`, or refresh the cases list. If the process restarts mid-delete, call DELETE again with the same `cascade=true` to resume. UI confirms with count + typed case id.

Very large non-cascade deletes (many docs to unassign) may later move to **`202` + queue worker**; phase 1 keeps them synchronous.

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

Case runs replace peer grouping on single-document prompts. Field **removed** from API/SDK responses; server **ignores** legacy fields on write; no peer lookup in `_build_prompt_context`; UI control removed.

### 4.2 Runs

- `POST .../cases/{case_id}/runs` `{ prompt_id }` → `queues.case_llm`.
- Worker: all docs with `case_id`, sorted by upload date, cap 50, SPU pre-check (page floor), one `_build_prompt_context` call.
- **`case_llm_runs`** with `document_ids` snapshot; indexes in `index_registry.py`.
- **Stale** when: case membership ≠ run's `document_ids`; prompt revision ≠ run's `prompt_revid`; or any member document has `updated_at` **after** the run's `created_at` (name, tags, metadata, or case assignment—not OCR). OCR re-run alone does **not** mark results stale and does not auto-queue new LLM runs. Staleness reflects **structural** changes, not extraction quality after OCR.
- **Results:** `GET .../results?prompt_id=` — UI Results tab, run/re-run, JSON download (shipped). Optional later: grid layout, CSV, bulk “run missing” prompts on case.

Phase 3: start run requires **operator**, **builder**, or **admin** ([`permissions.md`](permissions.md)).

## 5. Flows — Assign to case (phase 3)

Flow node: `case_id` (or generate), `document_id`, `create_case_if_missing` default **true**, optional case display_name/tags/metadata. Calls same assign helper as API. Runs as system on execution; flow definitions editable only by **builder** or **admin** ([`permissions.md`](permissions.md)).

## 6. SDK / MCP

Case + document APIs in phase 1–2; case runs/results in phase 2. Member **`role`** and **`system_role`** in phase 3 ([`permissions.md`](permissions.md)). Phase 4: MCP/agent respect org role.

## 7. Phases

| Phase | Exit |
|-------|------|
| **1** | Cases, assign, delete, full `delete_doc`, UI, SDK, tests |
| **2** | Case runs + results; document `updated_at` on name/tag/metadata/case writes (not OCR); peer_match_keys removed |
| **3** | [`permissions.md`](permissions.md) on all REST; assign-to-case flow node (§5) |
| **4** | MCP/agent; optional case webhook events |

## 8. Why cases (not metadata-only groups)

Explicit membership and case-level tags/metadata; stable id like Hyperscience; one case per doc simplifies future per-case ACL. See [`document_groups_plan.md`](document_groups_plan.md) / [`document_group_plan2.md`](document_group_plan2.md) for abandoned approaches.

## 9. Open questions

1. Auto id: `DR-{ulid}` vs sequential.
2. Empty cases via `POST /cases` — allowed; confirm product copy.
3. Merge cases — defer.
4. Batch upload sharing one `case_id`.
5. Per-case ACL — see [`permissions.md`](permissions.md) deferred.

## 10. Deferred

Retention/scheduled deletion; multi-case membership; case JSON export; case-level LLM on case record; auto case prompt when processing complete; ImageRight import.
