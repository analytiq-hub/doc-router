# Document cases — implementation plan

Hyperscience groups work under a persisted **Case ID** created by **case collation** (flows attach files and documents to a case over time). See [Hyperscience Cases](https://help.hyperscience.ai/v43/docs/case-collation).

This plan is the DocRouter version of that model. Cases can still **mirror** business IDs in metadata (claim number, policy number) without replacing them.

## Goal

Give each org **cases**: stable IDs that **explicitly** group documents for browse, review, bulk actions, and **one prompt over all documents in the case**. Uploads and flows **assign** documents to a case. Removing a document from a case does **not** delete the document.

Access control is **org-wide permissions** (document access roles plus separate configuration permissions) enforced on **all org-scoped REST operations** in a later phase—not cases only. Per-case ACL is deferred.

**Document** tags still drive OCR, tag prompts, and flows. **Case** tags and metadata classify cases (for example claim vs policy, dates); they do not run document pipelines unless a flow explicitly reads case fields (phase 3+). Case collation assigns documents; it does not copy case metadata onto documents automatically.

## Decisions

- **Case is a first-class record**, not a computed metadata filter. Membership is stored on the document (`case_id`) and maintained by assign/remove APIs and flow nodes.
- **One primary case per document** in v1 (`docs.case_id` nullable). A document with no case behaves as today. Many-to-many (document in multiple cases) is deferred; HS can attach pages/docs flexibly, but insurance UX usually assumes one business case per file.
- **Case ID** is a string, unique per org, chosen by the client or auto-generated (e.g. `DR-{ulid}`) when omitted on create. Do not require a specific prefix; customers may use `CLM-123` as the case id. Allowed characters are limited so the id is safe in URL paths (§1.3).
- **Cases have tags and metadata like documents.** Same org **tags** collection (`tag_ids` on the case). Case **`metadata`** is `Dict[str, str]` with the same normalization rules as document metadata (trim, empty removes key). Example: a case tagged `claim` with metadata `claim_date` and `policy_number`.
- **No case-to-case links.** Case metadata values are plain strings. The server never interprets a metadata value as a reference to another case. "Claim" and "policy" in this plan are examples of tags and metadata an org might use; nothing in code knows about them.
- **Document metadata stays separate.** Files keep their own tags/metadata for extraction. Flows or UI may copy fields from case → document or document → case; that is explicit, not implicit on assign.
- **Assigning to an unknown case id fails by default.** Upload, `PUT /documents`, bulk assign and the assign endpoint take `create_case_if_missing` (default `false`); an unknown `case_id` returns `400`. This stops a typo (`CLM-0123`) from silently creating a stray case. The flow node (§6) opts in explicitly.
- **Deleting a case** removes the case row and clears `case_id` on member documents by default. **Cascade delete documents** is an explicit admin option (§2.4).
- **Retire `peer_match_keys` in phase 2** when case prompt runs land (§4.1). The prompt API stays backward compatible.
- **Indexes:** see §1.1 and §1.2.

## 1. Data model

### 1.1 `cases` collection

```json
{
  "_id": ObjectId("..."),
  "organization_id": "org1",
  "case_id": "CLM-123",
  "display_name": "Smith — auto loss, 2026-09-14",
  "tag_ids": ["<tag id for claim>"],
  "metadata": {
    "claim_date": "2026-09-14",
    "policy_number": "POL-998"
  },
  "deleting_at": null,
  "created_by": "<user id>",
  "created_at": "...",
  "updated_at": "..."
}
```

- Unique index `(organization_id, case_id)`.
- Index `(organization_id, updated_at desc)` for the cases table. `updated_at` changes on case edits **and** on document assign/remove (§2.3), so sorting by it shows recently active cases first.
- Index `(organization_id, tag_ids)` for the tag filter.
- Optional `(organization_id, metadata.$**)` compound wildcard index if case list metadata search becomes hot (MongoDB 7.0+).
- `deleting_at` is set while a delete is in progress (§2.4). Cases with `deleting_at` set are hidden from lists and reject assigns.
- **Document count** for list/detail UI is computed at read time (`countDocuments` / `$match` on `docs.case_id`), not stored on the case row.
- Optional later: `scheduled_deletion_at`, retention (HS Machine Collation `retention_period`) — §11.

### 1.2 `docs` fields

| Field | Type | Notes |
|-------|------|-------|
| `case_id` | `str \| null` | Phase 1. Org-scoped logical id matching `cases.case_id`, not ObjectId |
| `ocr_completed_at` | `datetime \| null` | Phase 2. Set when OCR finishes. Used for case run staleness (§4.2) |
| `metadata_updated_at` | `datetime \| null` | Phase 2. Set on every document metadata write. Used for case run staleness (§4.2) |

Index: `(organization_id, case_id, upload_date desc)` for case document lists.

### 1.3 Case ID rules

- Trim on write, then validate against `^[A-Za-z0-9._:-]{1,128}$`. Anything else returns `400`. This keeps case ids safe in URL paths (`/cases/{case_id}`) without encoding, and rules out `/`, `?`, `#`, `%` and whitespace.
- Case ids are case-sensitive: `CLM-123` and `clm-123` are different cases.
- Validator `validate_case_id` shared by API and flows.
- Auto-generated ids (`DR-{ulid}`) satisfy the same pattern.
- **Create case** explicitly (`POST /cases`), or implicitly on assign only when `create_case_if_missing=true` (§2.3).
- Any member with document write permission (§5) may change `display_name`, tags and metadata. Changing `case_id` itself is **move merge** (advanced, deferred)—v1: case id immutable.

### 1.4 Case tags

- Reuse the org **`tags`** collection and tag IDs exactly as documents do (`app/routes/documents.py` validation: tags must exist in the org).
- Tags distinguish case **kind** (e.g. tag `claim`, tag `policy`) and drive list filters (`GET /cases?tag_ids=`). They do **not** by themselves run LLM on member documents.
- Case tag prompts / case-level flows (run prompt on case record, not only on case documents) are **deferred** (§11).

### 1.5 Case metadata

- **Shape:** `Dict[str, str]`, same as document metadata.
- **Normalization:** `apply_case_metadata_rules(metadata)` — trim values; remove keys whose value is empty after trimming.
- **List/search:** `GET /cases` accepts `metadata_search` with the same `key=value` comma encoding as `GET /documents`. For example, `GET /cases?metadata_search=policy_number=POL-998` finds every case carrying that policy number.

Documents inside a claim case keep **document-level** metadata (page type, extracted fields). Case metadata holds **case-level** facts (loss date, policy number).

### 1.6 Document vs case fields

| Layer | Tags | Metadata examples |
|-------|------|-------------------|
| **Case** | `claim`, `policy` | `claim_date`, `policy_number` |
| **Document** | processing tags | `doc_type`, extracted vendor fields |

Assigning a document to a case does not merge case metadata onto the document. Upload may default document metadata from case metadata only when the client or a flow sets it.

## 2. Backend — cases and assignment (phase 1)

### 2.1 Data layer (`analytiq_data/common/cases.py`)

Add an explicit eager import in `analytiq_data/common/__init__.py` (no lazy loading, per CLAUDE.md).

- `get_case`, `list_cases` (search by `case_id`, `tag_ids`, `metadata_search`, date range, sort, paging; excludes cases with `deleting_at` set)
- `create_case`, `update_case` (display_name, tag_ids, metadata — validate tags)
- `validate_case_id`, `apply_case_metadata_rules`
- `delete_case(org, case_id, *, cascade_documents)` (§2.4)
- `assign_documents_to_case(org, doc_ids, case_id, *, create_case_if_missing)` (§2.3)
- `remove_documents_from_case(org, doc_ids)` — sets `case_id` null
- `list_documents_in_case` — wraps `list_docs` with `case_id` filter
- `count_documents_in_case(case_id)` — for list/detail responses

Every membership change goes through `assign_documents_to_case` / `remove_documents_from_case`: upload, `PUT /documents`, bulk update, the case documents endpoints, and the flow node (phase 3).

### 2.2 Routes (`app/routes/cases.py`)

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/v0/orgs/{org}/cases` | List cases (search by case_id, tags, metadata, filter updated/created range, sort) |
| `POST` | `/v0/orgs/{org}/cases` | Create `{ case_id?, display_name?, tag_ids?, metadata? }`. Existing `case_id` returns `409` |
| `GET` | `/v0/orgs/{org}/cases/{case_id}` | Detail; `document_count` in response (computed) |
| `PUT` | `/v0/orgs/{org}/cases/{case_id}` | Update display_name, tag_ids, metadata (full metadata replace, same as document PUT) |
| `DELETE` | `/v0/orgs/{org}/cases/{case_id}?cascade=false` | Delete case row and clear `case_id` on docs; or cascade delete docs (§2.4) |
| `GET` | `/v0/orgs/{org}/cases/{case_id}/documents` | Documents in case (same filters as main list) |
| `POST` | `/v0/orgs/{org}/cases/{case_id}/documents` | Assign `{ document_ids: [], create_case_if_missing?: false }` |
| `DELETE` | `/v0/orgs/{org}/cases/{case_id}/documents/{document_id}` | Remove from case (not delete doc) |

Phase 2: `/cases/{case_id}/runs`, `/cases/{case_id}/results`.

**Documents API:**

- `GET /documents` and bulk request bodies accept optional `case_id` as a filter.
- Upload (JSON and multipart) accepts optional `case_id` and `create_case_if_missing`. The document is inserted and assigned in one transaction (§2.3).
- `PUT /documents/{id}` accepts `case_id`:
  - field **omitted** → case unchanged
  - explicit **`null`** → remove from case
  - a **string** → assign to that case (with optional `create_case_if_missing`)

  Use a sentinel default in the Pydantic model so "omitted" and "null" are distinguishable. Today's `metadata` field does not make that distinction; `case_id` must.
- Bulk update accepts `case_id` with the same semantics, applied to every selected document.

### 2.3 Assignment and concurrency

Assign, remove, upload-with-case and delete can race. Resolve this with MongoDB transactions. The KB indexer already uses `session.with_transaction` (`analytiq_data/kb/indexing.py`), so deployments already run as replica sets.

**Assign** (`assign_documents_to_case`), one transaction:

1. If `create_case_if_missing=true`, upsert the case row (`$setOnInsert` the new case fields). If another request creates the same case concurrently, the unique index raises `DuplicateKeyError`; catch it and retry the transaction once, which then finds the existing row.
2. Conditionally **touch** the case row: `update_one({organization_id, case_id, deleting_at: null}, {$set: {updated_at: now}})`. If it matches nothing, the case is unknown or being deleted: abort with `400` (unknown) or `409` (being deleted).
3. `update_many` the documents' `case_id`. Documents must belong to the org.

Touching the case row in step 2 is what makes this safe. Snapshot reads alone would allow write skew (assign reads the case, delete removes it, both commit). Because assign and delete both **write** the case row, MongoDB raises a write conflict and `with_transaction` retries the loser, which then sees the committed state.

**Upload with `case_id`** runs the same steps plus the document insert in one transaction. File storage happens before the transaction; if the transaction fails, the upload route deletes the stored files and returns the error.

**Remove** (`remove_documents_from_case`): one transaction that touches the case row (for `updated_at`) and sets `case_id: null` on the documents.

**Bulk sizes:** cap one assign transaction at 1,000 documents. Larger bulk assigns run in batches of 1,000, each its own transaction; each batch is safe on its own.

### 2.4 Delete semantics

**Step 1, always:** in a transaction, set `deleting_at` on the case row (failing with `404` if it is already gone or being deleted). From this point the case is hidden from lists, and every assign fails at step 2 of §2.3 with `409`. Any assign that committed before this point is already visible to the next step.

**Delete case (default, `cascade=false`):**

2. `update_many({organization_id, case_id}, {$set: {case_id: null}})` on `docs`.
3. Delete `case_llm_runs` for the case (phase 2).
4. Delete the case row.

Steps 2–4 are idempotent. For cases up to about 10,000 documents they run in the request. Larger cases enqueue a `case_delete` worker message and return `202`; the case stays hidden meanwhile.

**Delete case `cascade=true`** (admin only; the UI shows the document count and requires typing the case id):

2. Enqueue a `case_delete` worker message and return `202`.
3. The worker deletes member documents in batches through `delete_doc_full`, re-querying `{organization_id, case_id}` each batch, so a crash or retry carries on where it stopped.
4. Then delete `case_llm_runs` and the case row.

**`delete_doc_full`** is a new helper and a **phase 1** requirement because of cascade delete. Today cleanup is split between the `DELETE /documents/{id}` route (original file, PDF rendition, `flow_results`) and `ad.common.delete_doc` (`llm_runs`, OCR, KB index and vectors), and several collections keyed by document are missed altogether, so a deleted document's data survives even now. `delete_doc_full` removes all of it:

- stored files: original and PDF rendition
- OCR (GridFS `ocr`), `llm_runs`, `flow_results`
- `flow_executions` whose `trigger.document_id` matches, and their `flow_blobs`
- `form_submissions`
- `document_index` entries and `kb_vectors_<kb_id>` chunks, then refresh the KB's cached counts
- `agent_threads`
- `webhook_deliveries` for the document

The single-document delete route and bulk delete switch to it as well.

**Delete document:** unchanged apart from using `delete_doc_full`. The case stays, even if it becomes empty.

### 2.5 Tests (`test_cases.py`)

- Case id validation (pattern, length, trimming, case sensitivity); unique per org; cross-org isolation
- Create, list, search, sort; duplicate create returns `409`
- Assign on upload, `PUT /documents`, bulk update, and `POST /cases/{id}/documents`; remove; computed document count matches direct query
- `PUT /documents`: omitted `case_id` leaves the case unchanged; `null` removes it
- Unknown `case_id` returns `400` unless `create_case_if_missing=true`; concurrent implicit creates of the same id produce one case
- Assign to a case with `deleting_at` set returns `409`
- Race test: run assign and delete concurrently many times; no document ends up with a `case_id` that has no case row
- `GET /documents?case_id=` and bulk respect `case_id`
- Delete case vs cascade; document survives remove-from-case; cascade worker rerun after a simulated crash finishes the job
- `delete_doc_full` leaves no row keyed by the document in any collection listed in §2.4
- Case tags: invalid tag id → 400; list filter by tag
- Case metadata normalization; `metadata_search` on cases

## 3. Frontend (phase 1)

### 3.1 Navigation

- **Cases** under org (parallel to Documents): table — Case ID, display name, tags, document count (from API), `updated_at`; filters by tag and metadata search (same UX patterns as document list).
- **Case detail** page: summary, **tags** editor, **metadata** editor, documents table, remove from case, link to document viewer, delete case (with the cascade option for admins).

### 3.2 Documents page integration

- Optional filter **Case** (picker or case id from URL `/docs?case_id=CLM-123`).
- Upload: **Assign to case** (existing case autocomplete). Creating a new case from the upload form is an explicit "Create case CLM-123" choice that sets `create_case_if_missing=true`.
- Document detail: show case chip linking to case detail.
- Bulk: assign to case / remove from case.

URL: `/orgs/{orgId}/cases`, `/orgs/{orgId}/cases/{caseId}`, documents deep link with `case_id`.

## 4. Case prompt runs (phase 2)

Replace peer-metadata grouping (§4.1) and align with HS "review all case documents together."

### 4.1 Retire `peer_match_keys`

Today, prompt revisions can list metadata keys so a single-document LLM run pulls in peer documents and saves one combined result on the source document. Case runs replace that behavior.

- **API stays compatible.** `PromptConfig` in `app/routes/prompts.py` keeps the `peer_match_keys` field, so clients that still send it get no `422`. The server ignores the value: it is not stored on new revisions, and responses always return `peer_match_keys: []`. Mark the field deprecated in the model description and OpenAPI docs.
- **Revision equality.** The check in `prompts.py` that decides whether a `PUT` creates a new prompt revision compares `peer_match_keys` against the latest revision. Drop that comparison; otherwise an old revision with stored keys never compares equal and every save creates a new revision.
- **Stored values are ignored.** Existing revisions keep the field in MongoDB. `get_prompt_group_config` (`common/prompts.py`) stops returning it.
- **SDKs:** TypeScript and Python prompt models keep the field as optional and deprecated.
- **UI:** remove the "Grouped Inputs → Metadata group-by keys" control from `PromptCreate.tsx`. Keep the `include` controls (OCR text, PDF, metadata keys); single-document runs and case runs both use them.
- **Context building:** remove peer-document lookup from `_build_prompt_context` in `llm/llm.py`. Refactor it to take an explicit ordered list of documents. Single-document runs pass one document; case runs pass the case's documents. `peer_run`, `match_values` and `match_document_ids` on `llm_runs` go away.
- **Tests:** delete or rewrite peer-grouping tests in `test_llm_prompt_context.py`; add a test that a `PUT` with `peer_match_keys` succeeds and the value is ignored.
- **Release notes:** prompt-level grouping is retired; cases and case runs replace it.

### 4.2 Run lifecycle

- **Start:** `POST /v0/orgs/{org}/cases/{case_id}/runs` `{ prompt_id }` → returns the run id and enqueues a message on `queues.case_llm`.
- **Worker** (`worker/worker.py`, same pattern as LLM queue handlers): load all documents with `case_id`, sorted by `upload_date`, and build one multi-document prompt via the refactored `_build_prompt_context`. The prompt revision's `include` settings (OCR text, PDF, metadata keys) apply unchanged. Message shape `{ organization_id, case_id, prompt_id, run_id }`, idempotent on `run_id`.
- **Storage:** `case_llm_runs`: `{ organization_id, case_id, prompt_id, prompt_revid, document_ids, result, prompt_used, status, error, created_by, created_at }`. `document_ids` is the snapshot of the case at run time.
- **Indexes:** `case_llm_runs` `(organization_id, case_id, prompt_id, created_at desc)`. Add `queues.case_llm` and `queues.case_delete` to `WORKER_QUEUE_COLLECTIONS` in `analytiq_data/mongodb/index_registry.py`.
- **Staleness:** a run is **stale** when its inputs changed since it ran:
  - the case's current documents differ from `document_ids` (assign/remove)
  - a document's OCR was redone after the run (`ocr_completed_at`, when `include.ocr_text` is on)
  - a document's metadata changed after the run (`metadata_updated_at`, for keys in `include.metadata_keys`, or any key when it is `["*"]`)
  - the prompt has a newer revision than `prompt_revid`

  Per-document LLM results are not inputs to a case run, so they do not affect staleness. The UI shows a "Re-run" button for stale runs.
- **Readiness:** the run does not wait for document processing. If any document has not finished OCR while `include.ocr_text` is on, the run fails with a message listing those documents.
- **Limits:** cap a run at a configurable number of documents (default 50) and check the estimated token count against the model's context window before calling the LLM (PDF `include` is the usual driver of oversize). Fail with a clear message rather than truncating.
- **Billing:** charge SPUs as the per-document LLM path does, using the total page count.
- **Permissions:** phase 2, any org member (as today); phase 3 requires document **read_write** to start runs (§5).
- **No automatic trigger.** Runs are started by a user or through the API (§11).

### 4.3 Case results view

A table of each document's extracted fields across the case.

**Endpoint:** `GET /v0/orgs/{org}/cases/{case_id}/results?prompt_id=&skip&limit`

- Lists the case's documents with the same match query as `GET /documents`. For each one, fetch the latest `llm_runs` result for `prompt_id` (existing lookup logic in `ad.llm.get_llm_result`). Batch this with one `$in` and `$sort`/`$group` aggregation instead of N lookups; `llm/bulk_analyze.py` has a similar aggregation to model on.
- Columns come from the prompt's response JSON Schema (top-level properties, nested objects flattened to dotted keys). This fixes the column order and holds for documents without results.
- Each row has `document_id`, `document_name`, `upload_date`, `state`, `has_result`, `is_edited` (a human updated the result), and `fields: {key: value}`.
- If `prompt_id` is omitted, return the prompts that have results in the case, so the UI can offer a picker.

**UI** on case detail:

- **Run prompt** with stale/re-run markers for the latest case run per prompt
- **Results** tab: prompt picker (defaults to the prompt with the most results in the case), MUI DataGrid with one row per document and one column per field plus a status column (no result, pending, done, edited); clicking a row opens the document with the extraction sidebar
- CSV export, built client-side from the loaded rows
- "Run missing" button that calls the existing bulk-run LLM path scoped to the case

## 5. Org permissions (phase 3)

Each org `members[]` entry gains two independent settings next to the existing `role` (`admin` | `user`):

- a **document access role**: `read_only` or `read_write`
- a set of **configuration permissions**: any of `tags`, `schemas`, `prompts`, `forms`, `flows`, or `all`

They are independent because users differ along both axes: some users may edit flows, while others may only upload documents.

```json
{ "user_id": "...", "role": "user", "document_access": "read_write", "permissions": ["prompts", "schemas"] }
```

- **`all`** grants every configuration permission, including ones added later. It does not grant org administration.
- **Org admins** (`role: admin`) implicitly have `read_write` and `all`, plus org administration (settings, invites, billing, members).
- **Migration:** existing non-admin members get `document_access: read_write` and `permissions: ["all"]`, which matches what they can do today: tags, schemas, prompts, forms and flows are all editable by any member now (`get_org_user` in `tags.py`, `schemas.py`, `prompts.py`, `forms.py`, `flows.py`). New members default to `read_write` with no configuration permissions; admins grant more.
- This plan adds cases in phases 1–2 **without** new confidentiality; phase 3 turns on gating for the whole org API, not only `/cases`.

### 5.1 Permission matrix

| Area | Read | Write |
|------|------|-------|
| Documents, cases, extraction results, case runs and results, OCR/LLM/flow **runs on documents**, uploads, bulk actions | any member | document `read_write` |
| Tag definitions | any member | `tags` |
| Schemas | any member | `schemas` |
| Prompts | any member | `prompts` |
| Forms (definitions) | any member | `forms` |
| Flows (definitions, activation, credentials) | any member | `flows` |
| Org settings, members, invites, billing, webhooks config | admin | admin |

Notes:

- Reading configuration is open to every member, because using the app (picking a tag on upload, viewing an extraction) needs it.
- Configuration permissions are independent of document access. A user with `flows` and `read_only` can author flows but cannot upload or edit documents by hand. Activated flows run as system, so `flows` is a powerful permission: an active flow can change any document, including case membership (§6). Grant it accordingly.
- Form **submissions** on documents are document writes (`read_write`); form **definitions** need `forms`.
- Knowledge bases are not in the list above. Decide in phase 3 whether KB definitions get their own `knowledge_bases` permission or fall under `all` only (§10).

### 5.2 Enforcement

- **Central dependencies** in FastAPI, built on `get_org_user` in `app/auth.py`: `require_doc_read`, `require_doc_write`, `require_permission("flows")` (and the other configuration permissions), `require_org_admin`. Every org router handler declares exactly one.
- **Coverage:** all user-facing org REST under `app/routes/` — documents (including upload and bulk), cases, tags, schemas, prompts, forms, LLM runs, flows, knowledge bases, webhooks — and SDK/MCP paths that hit those routes. Workers, flow **execution** internals, and system callbacks run as system; **user-triggered** enqueue endpoints still require document `read_write`.
- **API tokens** use the owning user's document access role and permissions.
- **Frontend:** hide/disable create, edit, delete, upload, bulk, and run actions according to the user's role and permissions across the app, not only on case pages. Server remains source of truth (`403`).
- **Regression:** `test_org_permissions.py` plus a **route-table test** that enumerates every registered org route and asserts its declared requirement, so new routes cannot ship without one.

No per-case or per-document ACL in this plan. Deferred: restrict by case id, HS-style flow visibility, break-glass.

## 6. Flows — case collation (phase 3)

HS **Machine Collation** equivalent: a flow node **Assign to case**.

- Inputs: `case_id` (expression from trigger/metadata) or empty → generate id; `document_id` from trigger; `create_case_if_missing` (default `true` for this node, since collation usually creates cases), optional `display_name`, `tag_ids`, `metadata` (set or merge on case).
- Calls `assign_documents_to_case`, so it gets the same validation and concurrency handling as the API (§2.3).
- **Permissions:** the node runs as system when the flow executes, with no per-user check. Flows are authored and activated by users with the `flows` permission (§5); today any member can. Without per-case ACL, case membership is not a security boundary, so this is acceptable. If per-case ACL is added later (§10), this node becomes a way to move documents between cases and needs its own check.
- Optional: copy selected case metadata fields onto the document metadata on assign.

Bulk collation (array of assignments) can follow for submission-style uploads.

## 7. SDK, MCP, agent

**TypeScript SDK (by phase):**

- Phase 1: case CRUD with `tagIds` and `metadata`; `listCases({ tagIds, metadataSearch })`; `listCaseDocuments`, `assignToCase`, `removeFromCase` (with `createCaseIfMissing`); `listDocuments({ caseId })`; `updateDocument` and uploads with `caseId`; types mirror document tag/metadata patterns
- Phase 2: `runCasePrompt`, `listCaseRuns`, `getCaseResults`; prompt types keep `peer_match_keys` as optional and deprecated (§4.1)
- Phase 3: member `documentAccess` and `permissions` on org member types; no special case-only client

**Python SDK:** `cases.py` module mirroring routes; prompt models keep `peer_match_keys` as optional and deprecated.

**Phase 4 MCP/agent:** case read/run tools, with the same role and permissions as the user on every tool; read-only users get read tools only.

## 8. Delivery phases

| Phase | Exit criteria |
|-------|----------------|
| **1** | Cases CRUD with tags/metadata, assign/remove with transactions, `create_case_if_missing`, `PUT /documents` `case_id`, case + document list filters, delete with `deleting_at` and cascade, `delete_doc_full`, cases UI + doc integration, SDK, `test_cases.py` |
| **2** | Case prompt runs + results; `case_llm_runs`; staleness fields on `docs`; retire `peer_match_keys` (API accepts and ignores) |
| **3** | Document access roles and configuration permissions enforced on **all** org REST; member migration; route-table tests; app-wide permission-aware UI; flow **Assign to case** node |
| **4** | MCP/agent case read/run tools (subject to user's role and permissions); case events (`document.case_assigned`, `document.case_removed`) for webhooks and flow triggers |

Ship phase 3 backend and UI together so permissions are never UI-only.

## 9. Why cases rather than metadata groups

An earlier design grouped documents by metadata value (`claim_number = CLM-123`) with no case record. Cases were chosen instead because:

- a case has its own identity, tags and metadata, separate from any document's
- membership is explicit, so assigning a document doesn't depend on its metadata being spelled exactly right
- one primary case per document keeps future per-case ACL simple (no intersection across groups)

Business IDs can still live in document or case metadata and be searched with `metadata_search`.

## 10. Open questions

1. **Auto case id format** — `DR-{ulid}` vs sequential; customer-facing ids only when supplied.
2. **Empty cases** — allow pre-create via `POST /cases` without documents (typical for a case created before its documents arrive). The plan allows it; confirm.
3. **Merge cases** — reassign all docs from case A to B, delete A; defer v1.
4. **Submission batch** — upload N files with one case id (single API batch); may reuse bulk upload + shared `case_id`.
5. **Per-case ACL** — when needed, add `cases.restricted` + acl, without intersection complexity (one case per doc).
6. **Registered case metadata keys** — required vs optional keys per case tag (e.g. tag `claim` requires `claim_date`); JSON Schema per tag deferred.
7. **Knowledge base permission** — separate `knowledge_bases` permission, or covered by `all` only (§5.1).

## 11. Deferred

- Case retention and scheduled deletion (HS Machine Collation settings)
- Document in multiple cases
- Case JSON export (HS "View JSON output")
- **Case-level tag prompts** (LLM on case metadata + aggregated doc context, without replacing document tag pipeline)
- **Automatic case prompt triggers** when all docs complete processing. Needs a per-document "processing finished" event (today's `document.uploaded` fires before OCR), a case trigger node with a readiness rule (quiet period, expected count, or required document types), and one execution per case deduplicated with `trigger.dedupe_key = flow_id:case_id`.
- ImageRight / external system case id import
- Access audit log for case ACL
