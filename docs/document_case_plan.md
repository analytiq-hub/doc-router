# Document cases — implementation plan

Hyperscience groups work under a persisted **Case ID** created by **case collation** (flows attach files and documents to a case over time). See [Hyperscience Cases](https://help.hyperscience.ai/v43/docs/case-collation).

This plan is the DocRouter version of that model. It is an alternative to metadata-only **groups** ([`document_groups_plan.md`](document_groups_plan.md)) and **slices / group-by** ([`document_group_plan2.md`](document_group_plan2.md)). Pick one browse-and-batch story for the product; cases can still **mirror** business IDs in metadata (claim number, policy number) without replacing them.

## Goal

Give each org **cases**: stable IDs that **explicitly** group documents for browse, review, bulk actions, and **one prompt over all documents in the case**. Uploads and flows **assign** documents to a case (create case if needed). Removing a document from a case does **not** delete the document.

Access control is **org-wide roles** (read-only, read-write, admin) enforced on **all org-scoped REST operations** in a later phase—not cases only. Per-case ACL is deferred.

**Document** tags still drive OCR, tag prompts, and flows. **Case** tags and metadata classify and link cases (claim vs policy, dates, related case ids); they do not run document pipelines unless a flow explicitly reads case fields (phase 3+). Case collation assigns documents; it does not copy case metadata onto documents automatically.

## Decisions

- **Case is a first-class record**, not a computed metadata filter. Membership is stored on the document (`case_id`) and maintained by assign/remove APIs and flow nodes.
- **One primary case per document** in v1 (`docs.case_id` nullable). A document with no case behaves as today. Many-to-many (document in multiple cases) is deferred; HS can attach pages/docs flexibly, but insurance UX usually assumes one business case per file.
- **Case ID** is a string, unique per org, chosen by the client or auto-generated (e.g. `DR-{ulid}`) when omitted on create/assign. Do not require a specific prefix; customers may use `CLM-123` as the case id.
- **Cases have tags and metadata like documents.** Same org **tags** collection (`tag_ids` on the case). Case **`metadata`** is `Dict[str, str]` with the same normalization rules as document metadata (trim, empty removes key). Example: a case tagged `claim` with metadata `claim_date`, `policy_id`, `policy_effective_date`, where `policy_id` holds another case’s `case_id` (e.g. a case tagged `policy`).
- **Case links are metadata conventions, not a graph DB.** The server treats `policy_id` (and similar keys) as strings. Optional **validate on write** when an org declares **case link keys** (see §1.5): value must match an existing `cases.case_id` in the same org. Invalid or missing targets return `400` or a soft warning (pick strict for v1).
- **Document metadata stays separate.** Files keep their own tags/metadata for extraction. Flows or UI may copy fields from case → document or document → case; that is explicit, not implicit on assign.
- **Deleting a case** removes the case row and clears `case_id` on member documents by default. **Cascade delete documents** is an explicit admin option (same spirit as group delete in v1 §2.6). Other cases that reference this `case_id` in metadata may hold stale ids unless delete is blocked (§2.3) or links are cleared.
- **Remove `peer_match_keys` in phase 2** when case prompt runs land (v1 §5.1).
- **Indexes:** `(organization_id, case_id)` on `docs`; `(organization_id, case_id)` unique on `cases`; `(organization_id, tag_ids)` on `cases` for tag filter; optional `(organization_id, metadata.$**)` wildcard on `cases` if case list metadata search is hot (MongoDB 7+, same pattern as v1 docs index).

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
    "policy_id": "POL-998",
    "policy_effective_date": "2025-01-01"
  },
  "created_by": "<user id>",
  "created_at": "...",
  "updated_at": "..."
}
```

Example **policy** case (linked target):

```json
{
  "case_id": "POL-998",
  "tag_ids": ["<tag id for policy>"],
  "metadata": {
    "policy_effective_date": "2025-01-01",
    "line_of_business": "auto"
  }
}
```

The claim case’s `metadata.policy_id` equals `POL-998`, the policy case’s `case_id`. UI renders `policy_id` as a link to `/cases/POL-998` when that case exists.

- Unique index `(organization_id, case_id)`.
- Index `(organization_id, updated_at desc)` for the cases table (sort by case row changes).
- **Document count** for list/detail UI is computed at read time (`countDocuments` / `$match` on `docs.case_id`), not stored on the case row.
- Optional later: `scheduled_deletion_at`, retention (HS Machine Collation `retention_period`) — §11.

### 1.2 `docs` field

| Field | Type | Notes |
|-------|------|-------|
| `case_id` | `str \| null` | Org-scoped logical id matching `cases.case_id`, not ObjectId |

Index: `(organization_id, case_id, upload_date desc)` for case document lists.

Phase 2 staleness (case runs): reuse `ocr_completed_at`, `metadata_updated_at` from v1 §5.2 on `docs`.

### 1.3 Case ID rules

- Non-empty string, max length 256; trim on write.
- Validator `validate_case_id` shared by API and flows.
- **Create case** explicitly (`POST /cases`) or **implicitly** on first assign when `case_id` is unknown (upsert case row).
- Org admin may **rename display_name**; changing `case_id` itself is **move merge** (advanced, deferred)—v1: case id immutable.

### 1.4 Case tags

- Reuse the org **`tags`** collection and tag IDs exactly as documents do (`app/routes/documents.py` validation: tags must exist in the org).
- Tags distinguish case **kind** (e.g. tag slug `claim`, tag slug `policy`) and drive list filters (`GET /cases?tag_ids=`). They do **not** by themselves run LLM on member documents.
- Case tag prompts / case-level flows (run prompt on case record, not only on case documents) are **deferred** (§11).

### 1.5 Case metadata and links

- **Shape:** `Dict[str, str]`, same as document metadata.
- **Normalization:** `apply_case_metadata_rules(org, metadata)` — trim values; remove empty keys; optional org **registered metadata keys** for cases (admin settings) mirroring group-key registry patterns in v1.
- **List/search:** `GET /cases` accepts `metadata_search` with the same `key=value` comma encoding as `GET /documents`.
- **Case link keys (optional org setting):** e.g. `case_link_keys: ["policy_id", "parent_case_id"]`. On create/update case, each listed key’s value, if present, must equal some `cases.case_id` in the org (excluding self). Enables reliable claim → policy navigation without a separate foreign-key collection.
- **Inverse lookup (phase 1 nice-to-have):** `GET /cases?metadata_search=policy_id=POL-998` finds claim cases pointing at a policy; optional dedicated `GET /cases/{case_id}/referrers?metadata_key=policy_id` for “cases that link here.”

Documents inside a claim case keep **document-level** metadata (page type, extracted fields). Case metadata holds **case-level** facts (loss date, policy pointer).

### 1.6 Document vs case fields

| Layer | Tags | Metadata examples |
|-------|------|-------------------|
| **Case** | `claim`, `policy` | `claim_date`, `policy_id` → other case, `policy_effective_date` |
| **Document** | processing tags | `doc_type`, extracted vendor fields |

Assigning a document to a case does not merge case metadata onto the document. Upload may default document metadata from case metadata only when the client or a flow sets it.

## 2. Backend — cases and assignment (phase 1)

### 2.1 Data layer (`analytiq_data/common/cases.py`)

- `get_case`, `list_cases` (search by `case_id`, `tag_ids`, `metadata_search`, date range, sort, paging)
- `create_case`, `update_case` (display_name, tag_ids, metadata — validate tags and optional case link keys)
- `normalize_case_metadata`, `apply_case_metadata_rules`
- `delete_case(org, case_id, *, cascade_documents)` 
- `assign_document_to_case(doc_id, case_id, *, create_if_missing)`
- `remove_document_from_case(doc_id)` — sets `case_id` null
- `list_documents_in_case` — wraps `list_docs` with `case_id` filter
- `count_documents_in_case(case_id)` — for list/detail responses

Assign/remove must call the same path from upload, PUT document, bulk update, and flows (phase 3).

### 2.2 Routes (`app/routes/cases.py`)

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/v0/orgs/{org}/cases` | List cases (search by case_id, filter updated/created range, sort) |
| `POST` | `/v0/orgs/{org}/cases` | Create `{ case_id?, display_name?, tag_ids?, metadata? }` |
| `GET` | `/v0/orgs/{org}/cases/{case_id}` | Detail; optional `document_count` in response (computed); resolved **linked cases** for link keys |
| `PUT` | `/v0/orgs/{org}/cases/{case_id}` | Update display_name, tag_ids, metadata (full metadata replace same as document PUT) |
| `PATCH` | `/v0/orgs/{org}/cases/{case_id}/tags` | Optional: bulk tag update mirroring document patterns |
| `DELETE` | `/v0/orgs/{org}/cases/{case_id}?cascade=false` | Delete case row; clear `case_id` on docs; or cascade delete docs |
| `GET` | `/v0/orgs/{org}/cases/{case_id}/documents` | Documents in case (same filters as main list) |
| `POST` | `/v0/orgs/{org}/cases/{case_id}/documents` | Assign `{ document_ids: [] }` |
| `DELETE` | `/v0/orgs/{org}/cases/{case_id}/documents/{document_id}` | Remove from case (not delete doc) |

Phase 2: `/cases/{case_id}/runs`, `/cases/{case_id}/results`.

**Documents API:** `GET /documents` and bulk bodies accept optional `case_id`. Upload (JSON/multipart) accepts optional `case_id` (assign after insert).

### 2.3 Delete semantics

- **Delete case (default):** delete `cases` row; set `case_id = null` on all member documents; delete `case_llm_runs` for that case (phase 2).
- **Referential check:** if org uses `case_link_keys`, **delete case** returns `409` when any other case’s metadata still references this `case_id` (list referrers in error body). Admin may force delete with `?unlink=true` to clear those metadata keys in referrers (batch update) then delete.
- **Delete case `cascade=true`:** enqueue worker to `delete_doc_full` every member document, then delete case row (admin only; confirm in UI).
- **Delete document:** unchanged.

### 2.4 Tests (`test_cases.py`)

- Case id validation; unique per org; cross-org isolation
- Create, list, search, sort
- Assign on upload and POST assign; remove; computed document count matches direct query
- `GET /documents?case_id=` and bulk respect `case_id`
- Delete case vs cascade; document survives remove-from-case
- Implicit case create on assign
- Case tags: invalid tag id → 400; list filter by tag
- Case metadata normalization; link key validates target case exists
- Delete policy case with referring claim → 409; unlink then succeeds

## 3. Frontend (phase 1)

### 3.1 Navigation

- **Cases** under org (parallel to Documents): table — Case ID, display name, tags, key metadata columns (org-configurable), document count (from API aggregate), `updated_at`; filters by tag and metadata search (same UX patterns as document list).
- **Case detail** page: summary, **tags** editor, **metadata** editor (registered keys + free keys), **linked cases** panel (e.g. policy from `policy_id`), documents table, remove from case, link to document viewer.

### 3.2 Documents page integration

- Optional filter **Case** (picker or case id from URL `/docs?case_id=CLM-123`).
- Upload: **Assign to case** (existing case autocomplete or new id).
- Document detail: show case chip linking to case detail.
- Bulk: assign to case / remove from case.

URL: `/orgs/{orgId}/cases`, `/orgs/{orgId}/cases/{caseId}`, documents deep link with `case_id`.

## 4. Case prompt runs (phase 2)

Replace peer-metadata grouping (v1 §5.1) and align with HS “review all case documents together.”

- **Start:** `POST /v0/orgs/{org}/cases/{case_id}/runs` `{ prompt_id }` → queue `queues.case_llm`.
- **Worker:** Load documents with `case_id`, sorted by `upload_date`, cap (default 50), single `_build_prompt_context` over all ids.
- **Storage:** `case_llm_runs`: `{ organization_id, case_id, prompt_id, prompt_revid, document_ids, result, status, error, created_by, created_at }`.
- Index: `(organization_id, case_id, prompt_id, created_at desc)`.
- **Staleness / readiness / limits / billing:** v1 §5.2 applied to case membership (document set changes if assign/remove; OCR/metadata timestamps).
- **Results:** `GET /cases/{case_id}/results?prompt_id=` — per-document extraction grid (v1 §6).
- **Permissions (phase 2):** same as today (any org member); phase 3 requires **read_write** to start runs (§5).

UI: Case detail **Run prompt**, **Results** tab, stale/re-run markers.

## 5. Workspace permissions (phase 3)

Org membership gains a **document access role** (name TBD, e.g. on each org `members[]` entry): **`read_write`**, **`read_only`**, or **`admin`**. Today’s non-admin member becomes **`read_write`**. **Admin** keeps org administration (settings, invites, billing, tag/prompt/flow config, etc.) and always has read-write on content.

This plan adds cases in phases 1–2 **without** new confidentiality; phase 3 turns on **write gating for the whole org API**, not only `/cases`.

### 5.1 Role matrix (org content API)

| Role | Read (GET, list, download, export) | Write (POST, PUT, PATCH, DELETE) |
|------|--------------------------------------|-------------------------------------|
| **admin** | All org content the app exposes today | All content writes + admin-only routes |
| **read_write** | Same as today’s member | Same as today’s member (documents, cases, bulk, OCR/LLM/flows, uploads, metadata, tags on docs/cases, case runs, …) |
| **read_only** | Documents, cases, extractions, case results, KB read/search where allowed today | **Denied** — `403` on any mutating org-scoped route |

**Admin-only** routes stay unchanged (org settings, user invites, tag/prompt/flow **definition** CRUD, payments, etc.). Phase 3 does not demote admin; it adds **read_only** as a third **non-admin** tier.

### 5.2 Enforcement

- **Central dependencies** in FastAPI (extend `get_org_user`): e.g. `require_org_read`, `require_org_write`, `require_org_admin`. Every org router handler declares the minimum role.
- **Coverage:** all user-facing org REST under `app/routes/` — at minimum documents (including upload and bulk), cases, tags, prompts, LLM runs, flows (execute/start mutations), knowledge bases (mutations), schemas, forms, webhooks config, and parallel SDK/MCP paths that hit those routes. Workers, flow **execution** internals, and system callbacks run as system; **user-triggered** enqueue endpoints still require **read_write**.
- **API tokens** use the owning user’s org document access role.
- **Frontend:** hide/disable create, edit, delete, upload, bulk, and run actions for **read_only** across the app, not only on case pages. Server remains source of truth (`403`).
- **Regression:** `test_org_document_roles.py` plus a **route-table test** (same idea as v1 `test_group_access` §4.7): every mutating org route rejects **read_only** unless explicitly listed as admin-only (admin-only should reject read_write too where applicable).

No per-case or per-document ACL in this plan. Deferred: restrict by case id, HS-style flow visibility, break-glass.

## 6. Flows — case collation (phase 3)

HS **Machine Collation** equivalent: a flow node **Assign to case**.

- Inputs: `case_id` (expression from trigger/metadata) or empty → generate id; `document_id` from trigger; optional `create_case`, `display_name`, `tag_ids`, `metadata` (set or merge on case).
- Runs as system; updates `docs.case_id` (no end-user write role check; flow authored by admin).
- Optional: copy selected case metadata fields onto the document metadata on assign.

Bulk collation (array of assignments) can follow for submission-style uploads.

## 7. SDK, MCP, agent

**TypeScript SDK (by phase):**

- Phase 1: case CRUD with `tagIds` and `metadata`; `listCases({ tagIds, metadataSearch })`; `listCaseDocuments`, `assignToCase`, `removeFromCase`, `listDocuments({ caseId })`; types mirror document tag/metadata patterns
- Phase 2: `runCasePrompt`, `listCaseRuns`, `getCaseResults`; remove `peer_match_keys`
- Phase 3: org member `documentAccessRole` (or equivalent) on types; no special case-only client

**Python SDK:** `cases.py` module mirroring routes.

**Phase 4 MCP/agent:** same org role as the user on every tool; read-only users get read tools only.

## 8. Delivery phases

| Phase | Exit criteria |
|-------|----------------|
| **1** | Cases CRUD with tags/metadata and link validation, assign/remove, case + document list filters, cases UI + doc integration, SDK, `test_cases.py` |
| **2** | Case prompt runs + results; `case_llm_runs`; remove `peer_match_keys` |
| **3** | Org **read_only** / **read_write** enforced on **all** org content REST; route-table tests; app-wide read-only UI; flow **Assign to case** node |
| **4** | MCP/agent case read/run tools (subject to user’s org role) |

Ship phase 3 backend and UI together so **read_only** is never case-only or UI-only.

## 9. Comparison to other plans

| Topic | Cases (this plan) | Groups v1 | Slices plan2 |
|-------|-------------------|-----------|--------------|
| Identity | Persisted `case_id` | Metadata `(key, value)` | Computed slice expr |
| Membership | `docs.case_id` | Metadata only | Filter match |
| HS analogue | Case collation | Case-like bucket | Ad hoc query |
| Overlap | One case per doc (v1) | Many metadata groups | Any filter |
| ACL story | Deferred per-case | Per-group intersection | Org roles only |

**Coexistence:** Cases are the workflow handle; **case** tags/metadata describe the business object; **document** tags/metadata describe files and extraction. `policy_id` on a claim case points at a policy **case**, not merely a string in document metadata.

## 10. Open questions

1. **Auto case id format** — `DR-{ulid}` vs sequential; customer-facing ids only when supplied.
2. **Empty cases** — allow pre-create (restrict-before-upload HS pattern) via `POST /cases` without documents (typical for policy case before claim arrives).
3. **Merge cases** — reassign all docs from case A to B, rewrite referrers’ link metadata, delete A; defer v1.
4. **Submission batch** — upload N files one case id (single API batch); may reuse bulk upload + shared `case_id`.
5. **Per-case ACL** — when needed, add `cases.restricted` + acl similar to v1 §4 without intersection complexity (one case per doc).
6. **Registered case metadata keys** — required vs optional keys per case tag (e.g. tag `claim` requires `claim_date`); JSON Schema per tag deferred.
7. **Strict vs soft link validation** — `400` on bad `policy_id` vs save with warning badge in UI.

## 11. Deferred

- Case retention and scheduled deletion (HS Machine Collation settings)
- Document in multiple cases
- Case JSON export (HS “View JSON output”)
- **Case-level tag prompts** (LLM on case metadata + aggregated doc context, without replacing document tag pipeline)
- Automatic case prompt triggers when all docs complete processing (v1 §9.2)
- ImageRight / external system case id import
- Access audit log for case ACL
- Graph queries beyond metadata link keys (multi-hop policy → account)
