# Document Groups — Implementation Plan

## Goal

Let users group documents by metadata value, browse documents group by group on the documents page, run prompts over a whole group, and later restrict access per group.

A **group** is the set of documents in an org that share one value for one metadata key, for example all documents with `claim_number = CLM-123`. This is the DocRouter equivalent of a Hyperscience *case*: a long-lived grouping by business identifier that builds up over many uploads. Each document is still processed on its own when it is uploaded (OCR, tag prompts, flows). Groups add a way to browse, a place to run prompts across documents, and an access-control boundary.

The approach is deliberately small:

- an org-level list of **group keys**, which are the metadata keys allowed to act as groups
- no membership records: a document is in a group because of its metadata
- a `groups` collection that holds a row only for groups that carry state (an ACL or a display name)
- a group-by aggregation endpoint and a group pane on the documents page
- group prompt runs that send all of a group's documents to the LLM in one call, with the result saved on the group
- per-group access control, where restrictions from several groups combine by intersection

### Decisions

- **Groups come from metadata, not folders.** An earlier draft of this plan proposed a folder tree (`group_id`, `group_path`). That is replaced here. The fixed ImageRight levels (drawer, file, folder) can be declared as group keys and browsed as a nested group-by. Free-form folders are deferred (see 9.2).
- **A document can be in several groups at once**, one for each declared key it has a value for, for example a claim group and a policy group.
- **Group membership is not stored.** Changing a document's metadata moves it between groups. Section 4.4 makes this subject to permission checks once ACLs exist.
- **Tags still drive processing.** Groups do not trigger OCR, LLM or flows in this plan. Automatic group-level triggers are deferred (see 9.2).
- **Prompt-level `peer_match_keys` is removed in phase 2.** Today, prompt revisions can list metadata keys so a single-document LLM run pulls in peer documents and saves one combined result on the source document. Group runs (section 5) replace that behavior. Phase 2 removes `peer_match_keys` from the API, SDKs, UI, and `_build_prompt_context` with no backward compatibility or migration of old prompt settings.

## 1. Data model

### 1.1 Group keys (org setting)

A new field on the `organizations` document:

```json
"group_keys": [
  { "key": "claim_number",  "label": "Claim",  "case_insensitive": false },
  { "key": "policy_number", "label": "Policy", "case_insensitive": false }
]
```

Rules:

- Only org admins can change `group_keys`. Keys affect access control from phase 3 onward.
- `key` must be a valid metadata key: non-empty, with no `.` and no leading `$`, because it is used in the `metadata.<key>` field path.
- At most 10 keys per org. Each key gets an index (1.3), and MongoDB allows 64 indexes per collection.
- A key cannot be removed while any `groups` row for it is restricted. The API returns `409` and lists the restricted groups. Otherwise, removing a key would silently lift restrictions.
- The order of the list is the order shown in the UI's group-by picker.

### 1.2 Values and normalization

Document metadata stays `Dict[str, str]`, as it is today.

- **Trim on write.** Values for declared keys are trimmed of surrounding whitespace on every write path: upload (JSON and multipart), `PUT /documents/{id}`, and the bulk metadata update.
- **Case.** When `case_insensitive` is true, values are also lowercased on write. The default is false, because claim and policy numbers are usually case-significant, and lowercasing changes what users see.
- **Empty values.** An empty string after trimming counts as "no value". The server removes the key from metadata instead of storing `""`. This keeps the "(none)" bucket simple.
- **Existing documents.** Declaring a key does not rewrite existing values. If old documents carry untrimmed values, they appear as separate groups until they are edited. Section 9.1 has the open question about a one-off normalization job.

All writes go through `ad.common.groups.apply_group_metadata_rules(analytiq_client, organization_id, metadata)`, which loads `group_keys` for the org and calls the pure helper `normalize_group_metadata(group_keys, metadata)` so every path applies the same rules.

### 1.3 `groups` collection

A row exists only when a group needs state. Most groups never get one.

```json
{
  "_id": ObjectId("..."),
  "organization_id": "org1",
  "key": "claim_number",
  "value": "CLM-123",
  "display_name": "Smith — auto, 2026-09-14",   // optional
  "restricted": true,                            // see section 4
  "acl": [ { "user_id": "<user id>", "role": "manager" } ],
  "readers": ["<user id>", "..."],               // acl user ids when restricted, else null
  "created_by": "<user id>",
  "created_at": "...",
  "updated_at": "..."
}
```

- A unique index on `(organization_id, key, value)`. `value` is stored normalized (1.2).
- A row can exist before any document has that value. This lets an admin restrict a claim before its first document arrives.
- Deleting a row (`DELETE` on the group's access) removes its restrictions and display name. It does not delete documents.
- Groups are flat. Nesting in the UI (Claim, then Document type) is a browsing view, not a hierarchy of `groups` rows. That keeps ACLs per `(key, value)`, with no ancestor chain to walk.

### 1.4 New field on `docs`

| Field           | Type                | Notes |
|-----------------|---------------------|-------|
| `group_readers` | `list[str] \| null` | Added in phase 3. The intersection of `readers` across every restricted group the document belongs to. `null` means no restricted group applies, and the document is visible to every org member as today. `[]` means the document sits in at least one restricted group whose ACL has no users (only org admins can see it). See 4.3. |

No other document fields change. Group membership is read from `metadata`.

### 1.5 Indexes

Per repo policy ([`docs/indexes.md`](indexes.md)), **static** indexes belong in `EXPECTED_INDEXES` in `analytiq_data/mongodb/index_registry.py` and are applied by deploy-time `reconcile_indexes()`. Do not add a versioned migration class only to create these.

- `docs`: `(organization_id, metadata.<key>, upload_date desc)` for each declared key. Created when the key is declared and dropped when the key is removed. `set_group_keys` (2.1) creates and drops them; `reconcile_org_group_key_indexes` (2.1) re-creates any missing ones on startup reconcile. Name them `docs_group_<key>` so reconcile can tell them apart from other indexes.
- `groups`: `(organization_id, key, value)` unique — `IndexSpec` on collection `groups`.
- `groups`: `(organization_id, restricted)` — for listing restricted groups and blocking key removal.
- `group_llm_runs`: `(organization_id, key, value, prompt_id, created_at desc)`.
- `queues.group_llm`: same worker-queue index template as `queues.llm` (add `queues.group_llm` to `WORKER_QUEUE_COLLECTIONS` in `index_registry.py`).

The per-key `docs` indexes are **dynamic** (key names vary by org) and stay out of the static registry except through `reconcile_org_group_key_indexes`.

### 1.6 Query patterns

- **Documents in a group:** `{"organization_id": org, "metadata.<key>": value}`. This is what `metadata_search` already builds in `build_docs_match_query` (`common/doc.py`).
- **Documents with no value for a key:** `{"organization_id": org, "metadata.<key>": {"$exists": false}}`.
- **Values of a key with counts:** a `$match` (org, the existing filters, and visibility from phase 3), then `$group` on `$metadata.<key>`, then `$sort` and `$skip`/`$limit`. See 2.2.
- **Visibility for a non-admin user (phase 3):** `{"$or": [{"group_readers": null}, {"group_readers": user_id}]}`.

## 2. Backend: grouping and browsing (phase 1)

### 2.1 Data layer: `packages/python/analytiq_data/common/groups.py` (new)

Follow the style of `common/doc.py` and `common/tags.py`. Add an explicit import in `analytiq_data/common/__init__.py`. Per CLAUDE.md, this must be an eager import, with no lazy loading.

- `get_group_keys(analytiq_client, organization_id)` returns the declared keys.
- `set_group_keys(analytiq_client, organization_id, keys)` validates the keys (1.1), saves them, and creates or drops the per-key `docs` indexes.
- `reconcile_org_group_key_indexes(analytiq_client, organization_id)` ensures every declared key has a `docs_group_<key>` index (called from `set_group_keys` and from org-wide reconcile on deploy).
- `normalize_group_metadata(group_keys, metadata)` applies the rules in 1.2 and returns new metadata (pure function, no I/O).
- `apply_group_metadata_rules(analytiq_client, organization_id, metadata)` loads `group_keys` and returns normalized metadata for write paths (1.2).
- `list_group_values(analytiq_client, organization_id, key, *, match, value_search, skip, limit, sort)` runs the aggregation in 2.2.
- `get_group(analytiq_client, organization_id, key, value)` returns the `groups` row, or a default (unrestricted, no display name) when there is none.
- `upsert_group(...)` and `delete_group(...)` manage `groups` rows. Phase 1 uses them only for `display_name`.

### 2.2 Group values aggregation

`list_group_values` takes the same filters as `GET /documents` (name search, tags, metadata search, grid filters), through `build_docs_match_query`. That way the pane and the grid always agree. The pipeline is:

1. `$match` on the document query.
2. `$group` by `$metadata.<key>`:
   - `count`
   - `last_upload: {$max: "$upload_date"}`, `first_upload: {$min: "$upload_date"}`
   - state counts, using `$sum` over `$cond` on `state`: `processed` (the document's terminal success state), `in_progress` (uploaded and still processing), `error`
3. Documents without the key group under `null`, which is returned as the "(none)" bucket.
4. `value_search` adds a case-insensitive regex on the value after `$group`.
5. Sort by `last_upload desc` (the default), `value asc` or `count desc`. Then `$skip`/`$limit`, with a `$facet` for the total number of values.
6. Join `display_name` and `restricted` from `groups` rows for the values on the page, with one `$in` query.

The `$group` scans every matching document in the org, so its cost grows with the size of the filtered set, not the page size. That is fine at today's volumes. Section 9.3 covers what to do if it becomes slow.

Grouping by an undeclared key is allowed for **org admins only**. It has no index, and it never applies to ACLs. This is for exploring data before deciding to declare a key.

### 2.3 Routes

New file `packages/python/app/routes/groups.py`, registered in `app/main.py` the same way `tags_router` is. Every endpoint first requires `get_org_user`, as documents and tags do.

Group values can contain `/` and other characters that proxies decode unreliably in path segments, so groups are identified by `key` and `value` **query parameters**, not path segments.

| Method | Path | Purpose |
|--------|------|---------|
| `GET`  | `/v0/orgs/{org}/group-keys` | List the declared keys. |
| `PUT`  | `/v0/orgs/{org}/group-keys` | Replace the list. Admin only. Returns `409` if it would remove a key that has restricted groups. |
| `GET`  | `/v0/orgs/{org}/groups/values?key=&value_search=&skip=&limit=&sort=` plus the document filters | The aggregation in 2.2. |
| `GET`  | `/v0/orgs/{org}/groups/item?key=&value=` | One group: counts, `display_name`, `restricted`, and (phase 3) `my_role`. |
| `PUT`  | `/v0/orgs/{org}/groups/item?key=&value=` | Set `display_name`. |
| `GET`  | `/v0/orgs/{org}/groups/results?key=&value=&prompt_id=` | Group results view (section 6). |
| `POST` | `/v0/orgs/{org}/groups/runs` | Start a group prompt run (section 5). |
| `GET`  | `/v0/orgs/{org}/groups/runs?key=&value=&prompt_id=` | Get the latest group runs. |
| `GET`, `PUT`, `DELETE` | `/v0/orgs/{org}/groups/access?key=&value=` | Phase 3 (section 4). |

`key` must be a declared key on every endpoint except `groups/values`, where an admin may pass an undeclared key (2.2).

Pydantic models go in `app/routes/groups.py`: `GroupKey`, `GroupValue`, `ListGroupValuesResponse`, `Group`, `GroupRunRequest`, `GroupRun`, `GroupAccess`, `GroupAclEntry`.

### 2.4 Documents API changes (`app/routes/documents.py`, `common/doc.py`)

- `GET /documents` gains `group_key` and `group_value` parameters, plus `group_missing=true` for the "(none)" bucket. They map onto `build_docs_match_query`. `metadata_search` could already express a group value, but not "key is missing", and explicit parameters make the scope clear in bulk-action code.
- `build_docs_match_query` and `list_all_matching_docs` get the same parameters, so bulk analyze (OCR, LLM, flows) can target one group.
- Every metadata write path calls `apply_group_metadata_rules` (1.2): JSON upload, multipart upload, `PUT /documents/{id}`, bulk metadata update, Python SDK upload/update, and MCP upload/update.
- `PUT /documents/{id}` **replaces** the whole metadata dict today. A client that sends partial metadata drops the keys it left out, which moves the document out of its groups. This stays as it is for compatibility, but in phase 3 such a drop counts as a move and goes through the checks in 4.4.
- **Phase 1 does not add confidentiality.** Until phase 3, any org member can still read and edit metadata on all org documents, including moving them between group values. Do not describe group browsing as access control before phase 3 ships.

### 2.5 Tests: `packages/python/tests/test_groups.py` (new)

- Declaring keys: validation, admin-only, index created and dropped, the 10-key limit
- Normalization on every write path (upload JSON, multipart, update, bulk update), including trimming, optional lowercasing, and removing empty values
- `groups/values`: counts, state counts, the "(none)" bucket, `value_search`, paging, each sort, and that results agree with `GET /documents` under the same filters
- **Nested group-by:** with a parent value selected (including parent `group_missing=true` / `(none)`), child-key aggregation and `GET /documents` with `group_by2` filters agree
- Undeclared-key grouping is admin-only
- `GET /documents?group_key&group_value` and `group_missing=true`
- Bulk OCR, LLM, flows, delete, and metadata update respect `group_*` filters on the server (mirror existing tests that assert `metadata_search` on bulk paths)
- Cross-org isolation: values from org A never appear in org B

## 3. Frontend: group-by on the documents page (phase 1)

### 3.1 URL and state

- `/orgs/[organizationId]/docs?group_by=claim_number` shows the group pane for that key.
- `&group=CLM-123` selects a value, and `&group=__none__` selects the "(none)" bucket.
- `&group_by2=doc_type&group2=...` adds a second level (3.2).

All group state lives in the URL, so links can be shared and the browser's back button works.

### 3.2 Components

In `packages/typescript/frontend/src/components/groups/`:

- **`GroupBySelect.tsx`** goes in the documents page toolbar. Its options are **None** plus the declared keys by label. Admins also get a "Custom key…" entry (2.2).
- **`GroupValuesPane.tsx`** is a resizable, collapsible left pane. It shows:
  - a search box (`value_search`)
  - a sort menu (recent, A–Z, largest)
  - one row per value: the value, the `display_name` if set, the document count, a small state summary (for example "12 · 2 in progress · 1 error"), and a lock icon when restricted
  - the "(none)" bucket at the end
  - infinite scroll over `groups/values`

  Selecting a row sets `group` in the URL.
- **Second level.** When `group_by2` is set, the selected value expands to show its sub-values. They come from the same endpoint with the parent group added to the filters (`group_key` / `group_value`, or `group_missing=true` when the parent is `__none__`). This is how drawer, then file, then folder browsing works without folders.
- **`GroupHeader.tsx`** sits above the grid when a value is selected. It shows the key label, the value, an editable `display_name`, the counts, and buttons for **Run prompt on group** (phase 2), **Results** (phase 2) and **Access…** (phase 3, managers only).

### 3.3 Changes to existing components

- **`DocumentList.tsx`** takes `groupKey`, `groupValue` and `groupMissing`, and passes them to `listDocuments`. When grouping is active and no value is selected, the grid shows all matching documents, as it does today.
- **Bulk actions** (`DocumentBulkUpdateTags.tsx`, `DocumentBulkUpdateMetadata.tsx`, `DocumentBulkDelete.tsx`, `DocumentBulkRunOCR.tsx`, `DocumentBulkRunLLM.tsx`, `DocumentBulkRunFlows.tsx`) carry the group parameters in their `searchParameters` and pass them on. Without this, "select all in this group, then bulk delete" would act on every matching document in the org. Server-side bulk filter tests (2.5) are the source of truth; the frontend has no test runner today.
- **`DocumentUpload.tsx`**: when a group is selected, the upload form pre-fills `metadata[key] = value`, shows "Uploading to: Claim CLM-123", and lets the user clear it.
- **Document page (`docs/[id]`)**: show the document's groups as chips (`Claim: CLM-123`). Each chip links to the documents page with that group selected.
- **Org settings**: a "Group keys" section for admins, wired to `GET`/`PUT /group-keys` only (not a separate org PATCH field). Columns: key, label, case-insensitive; drag-to-reorder; confirmation listing restricted groups when a removal is blocked. Phase 3 adds "restrict a value before upload" here (4.6).

## 4. Access control (phase 3)

### 4.1 Model

- **Unrestricted groups** behave like documents do today: every org member can see and edit their documents. A document in no restricted group is unrestricted.
- A group with **`restricted: true`** limits its documents to the users in its `acl`, plus org admins.
- Each `acl` entry gives one org member a role on the group:

| Role      | Can do |
|-----------|--------|
| `viewer`  | See the group's documents, OCR text, extraction results, group runs and the group results view. Download files. |
| `editor`  | Everything a viewer can. Upload into the group (set the key to this value), rename documents, edit their tags and metadata, edit extraction results, run OCR, LLM, flows and group runs, delete documents, and move documents in or out (subject to 4.4). |
| `manager` | Everything an editor can. Set `display_name`, and change `restricted` and `acl`. |

- **Org admins** always have `manager` on every group. This keeps them able to recover a group whose managers have all left.
- **Org members** have `editor` on unrestricted groups, which matches today's behavior.
- **API tokens** are tied to a user (`access_tokens.user_id`), so a token has exactly that user's permissions. This also covers the MCP server and the SDKs.
- Principals are users only in the first version. The `acl` entry shape leaves room for a team principal type later.

### 4.2 Several groups per document: restrictions only narrow

A document can belong to several restricted groups, for example a restricted claim and a restricted policy. A user's effective role on a document is:

1. Find every restricted group the document belongs to: one `groups` lookup with `$or` over its declared `(key, value)` pairs.
2. If there are none, the role is the org default: `manager` for org admins and `editor` for members.
3. Otherwise, the user needs an `acl` entry on **every** one of those groups. Their role is the lowest of those entries. If any entry is missing, the user has no access.

Restrictions combine by intersection. Adding a restricted key value to a document can only narrow who sees it. This is easy to reason about for sensitive insurance files.

The cost is that giving someone access to a claim does not by itself give them access to that claim's documents that also sit in a restricted policy group. Section 9.1 lists the alternative model.

When a user restricts a group, the server adds them as `manager` if they are not already in the `acl`. This stops users from locking themselves out.

### 4.3 Denormalized readers

Listing is the hot path, so visibility must be a cheap filter, not a per-document group lookup.

- `groups.readers` is the user IDs in `acl` when `restricted`, and `null` otherwise. Org admins are not stored, because they bypass the filter.
- `docs.group_readers` is the intersection of `readers` across the document's restricted groups, or `null` when there are none. If any restricted group has `readers: []`, the intersection is `[]`.
- When a group is unrestricted or its `groups` row is deleted, it no longer contributes; recompute must restore `group_readers` to `null` when no restricted groups remain.
- For non-admin users, the visibility filter is `{"$or": [{"group_readers": null}, {"group_readers": user_id}]}`. Org admins get no filter.
- **`compute_doc_readers(group_keys, metadata, restricted_groups)`** is the single function that computes the value for one document.
- Recompute `group_readers`:
  - **on every metadata write** to a declared key (upload, update, bulk update), inside the same write. The upload computes it before inserting the document.
  - **on an ACL or `restricted` change** of group `(k, v)`: process the documents matching `metadata.k = v` in batches. Each document's value depends on its other groups too, so compute per document, caching the org's restricted groups for the duration of the job.
  - **when a user is removed from the org**: remove the user from every `acl` in the org with `$pull`, then recompute the affected groups. Org membership is already checked on every request, so this is cleanup, not the security boundary. It stops a re-invited user from silently regaining old access.
  - **when a key is removed from `group_keys`**: this is only allowed when the key has no restricted groups (1.1), so no recompute is needed.
- Access changes finish before the API responds. If a group holds more than about 10,000 documents, run the recompute as a worker job and show the group as "access change in progress" until it finishes. In the meantime, apply the **stricter** of the old and new readers, so the change never briefly widens access.
- Write checks (`editor` and `manager`) do not use `readers`. They resolve the role from the document's restricted groups when the request arrives (4.2).
- Do not add a `group_readers` index at first. The `$or` runs as a residual filter on the existing org-scoped index scans. Add `(organization_id, group_readers, upload_date desc)` only if measurements show a need.

### 4.4 Metadata edits are moves

Changing a declared key's value, or removing it, moves the document out of one group and into another. Every metadata write path applies these checks:

| Action | Requires |
|--------|----------|
| Upload with a value for a declared key | `editor` on that group if it is restricted |
| Change a declared key from `a` to `b` | `editor` on group `a` and on group `b` |
| Remove a declared key's value | `editor` on the old group |
| Change `display_name` | `manager` on the group |
| Change `restricted` or `acl` | `manager` on the group |
| Run a group prompt | `editor` on the group |
| Declare or remove group keys | Org admin |

**Widening rule:** if a write would let more people see the document, it also requires `manager` on every restricted group the document is leaving. The test is that the document's new `group_readers` is not a subset of the old one, with `null` counting as everyone. Without this rule, any editor could leak a restricted file by editing its claim number, or by sending a `PUT` with partial metadata that drops the key (2.4).

**Flows and workers** write metadata as the system. They bypass these checks, but they still recompute `group_readers`. Flows are configured by org admins, who already see everything.

### 4.5 Enforcement points

This is most of the work in phase 3. Documents are reached through many routes, not only `documents.py`.

- **One helper for single documents.** Add `ad.common.get_doc_for_user(analytiq_client, organization_id, document_id, user, min_role)` in `common/doc.py`. It loads the document, applies the visibility rule, and checks the role for writes. It returns `404` both when the document does not exist and when the caller cannot see it, so the API does not reveal that restricted documents exist. Every route with `{document_id}` in its path uses it.
- **One filter for lists.** `build_docs_match_query` and `list_docs` get a keyword-only, required `visibility` argument built from the current user (`Visibility.for_user(user, org)` or `Visibility.system()`). Making it required means every existing call site has to be updated, and none can be missed by accident.
- **Group endpoints.** `groups/values` counts include only visible documents. A restricted group that the caller has no ACL entry on is omitted from the values list (including zero-document groups), except org admins and users with `manager` on that group, who still see the row so they can manage access and pre-restricted empty groups. `groups/item`, `groups/results` and `groups/runs` return `404` for callers with no access.
- **Group prompt runs** (section 5) store the multi-document LLM output on the group. Reading a run requires `viewer` on the group, **and** the caller must be able to see every document in the run's `document_ids` snapshot. Otherwise the output could reveal content from documents in another restricted group. If any document is hidden from the caller, return the run's metadata with the result withheld and the message "includes documents you cannot access".
- **Routes to audit** (each has `{document_id}` endpoints or document lists): `documents.py`, `ocr.py`, `llm.py` (including bulk analyze and bulk run), `forms.py` (form submissions per document: `GET` and `DELETE /forms/submissions/{document_id}` currently skip the document check entirely), `prompts.py`, `flows.py` (run on document, plus the org-wide executions list, execution detail, blob download and resume, which read `flow_executions` without loading the document even though the trigger holds the file name, tags, metadata and LLM result), `knowledge_bases.py` (KB document lists and counts, search, chat), `webhooks.py` (delivery list, detail and retry, whose stored payloads hold document name, tags, metadata and LLM output), `agent.py` (document chat; agent tools such as `get_ocr_text` and `get_extraction_result` rely on the route-level check), and the new `groups.py`. **Dashboard / home counts** are computed in the frontend from list APIs; once those lists honor `visibility`, dashboard numbers follow without a separate backend audit.
- **Knowledge base search and chat.** Vector hits carry `document_id`. Post-filter hits against the caller's visibility, and over-fetch to make up for dropped hits. KB search is also reached from the KB tool inside extraction (`llm/llm.py`) and the flow agent tool (`flows/agent_loop/dispatch.py`), so the post-filter belongs in `search_knowledge_base` itself.
- **Workers, flows and webhooks** run as the system and are configured by org admins, so they can read every document. That is acceptable, because admins already see everything. User-facing views of their output, such as flow execution lists, must still hide entries for documents the caller cannot see.

### 4.6 Routes and UI for access

- `GET /groups/access?key=&value=` returns `restricted`, `acl` (with user names and emails) and `my_role`.
- `PUT /groups/access?key=&value=` takes `{ "restricted": bool, "acl": [{ "user_id", "role" }] }`. It creates the `groups` row if there is none. Every `acl` user must be a member of the org.
- `DELETE /groups/access?key=&value=` removes the row's restriction and ACL, after a check that the caller is `manager`.
- **`GroupAccessEditor.tsx`**, opened from **Access…** in `GroupHeader`, has:
  - a "Restricted" toggle
  - the ACL as a table of users with role pickers, and an "Add member" picker over org members
  - a read-only note when some of the group's documents are also limited by other restricted groups ("12 documents are also limited by Policy P-998")
  - before saving, a preview of how many users gain or lose access
- Admins can restrict a group with no documents from the org settings page, by entering the key and value. This covers "restrict this claim before anything is uploaded".
- Actions in the header and the bulk toolbar are disabled according to `my_role`. The server still enforces every check.

### 4.7 Tests: `packages/python/tests/test_group_access.py` (new)

- Viewer, editor and manager can each do exactly what the table in 4.1 says.
- Restrictions intersect across a document's groups, and the lowest role wins.
- A user without access gets `404` on the document and every document sub-resource. Write this as a **route-table test**: enumerate every registered route whose path contains `{document_id}` and assert `404` for a restricted document, so new routes cannot skip the check.
- Lists, counts, `groups/values`, bulk operations, KB search, group results and group runs exclude restricted documents. A restricted group the caller is not in does not appear in `groups/values`, except for org admins and group managers (4.5).
- The widening rule blocks an editor from changing or dropping a restricted key value, including through a `PUT` with partial metadata, and allows a manager.
- Uploading with a restricted group's value requires `editor` on it.
- `group_readers` is correct after an upload, an update, a bulk update, an ACL change, a restrict and unrestrict, and removal of a user from the org.
- Removing a key that has restricted groups returns `409`.
- A group run whose documents include one the caller cannot see has its result withheld.
- An org API token gets the same results as its user. Org admins see everything.

## 5. Group prompt runs (phase 2)

These replace the removed prompt-level `peer_match_keys` feature for "run a prompt over a set of related documents". The group is chosen explicitly and the result belongs to the group, not to whichever document triggered a tag prompt.

### 5.1 Remove `peer_match_keys` (same phase, no backward compatibility)

- Drop `peer_match_keys` from prompt revision storage, `GET`/`PUT` prompt APIs, Python and TypeScript SDK models, and `PromptCreate.tsx` (including the metadata "group by" UI).
- Remove peer-document lookup from `_build_prompt_context` in `llm/llm.py`. Refactor it to take an explicit ordered list of documents (used only by group runs and ordinary single-document runs).
- Delete or rewrite tests in `test_llm_prompt_context.py` that cover peer grouping. Document in release notes that customers must use declared group keys and group runs instead.

### 5.2 Run lifecycle

- **Start:** `POST /groups/runs` with `{ key, value, prompt_id }`. It enqueues a message on `queues.group_llm` and returns the run ID.
- **Worker** (`worker/worker.py`, same pattern as LLM queue handlers): load the group's documents (visibility-aware when phase 3 exists; phase 2 uses org-wide membership), sorted by upload date, and build one multi-document prompt via the refactored `_build_prompt_context`. The prompt revision's `include` settings (OCR text, PDF, metadata keys) apply unchanged. Message shape: `{ organization_id, key, value, prompt_id, run_id, ... }` with idempotent handling on `run_id`.
- **Storage:** `group_llm_runs` collection holding `{organization_id, key, value, prompt_id, prompt_revid, document_ids, result, prompt_used, status, error, created_by, created_at}`. `document_ids` is the snapshot of the group at run time.
- **Staleness:** a run is **stale** when the group's current documents differ from `document_ids`, or when one of them has a newer OCR or LLM result than the run. The UI shows a "Re-run" button for stale runs.
- **Readiness:** the run does not wait for document processing. If any document has not finished OCR while `include.ocr_text` is on, the run fails with a message listing those documents. The group header's state counts tell the user when the group is ready.
- **Limits:** cap a run at a configurable number of documents (default 50) and check the estimated token count against the model's context window before calling the LLM (PDF `include` is the usual driver of oversize). Fail with a clear message rather than truncating.
- **Billing:** charge SPUs as the per-document LLM path does, using the total page count.
- **No automatic trigger in this plan.** Runs are started by a user or through the API. Section 9.2 describes the automatic case trigger.

## 6. Group results view (phase 2)

This is a table of each document's extracted fields across a whole group.

**Endpoint:** `GET /v0/orgs/{org}/groups/results?key=&value=&prompt_id=&skip&limit`

- Lists the group's documents with the same match query as `GET /documents`, including the visibility filter. For each one, it fetches the latest `llm_runs` result for `prompt_id`, using the existing lookup logic in `ad.llm.get_llm_result`. Batch this with one `$in` and `$sort`/`$group` aggregation instead of N lookups. `llm/bulk_analyze.py` already uses a similar aggregation that can serve as a model.
- Columns come from the prompt's response JSON Schema (top-level properties, with nested objects flattened to dotted keys). This fixes the column order and holds even for documents without results.
- Each row has `document_id`, `document_name`, `upload_date`, `state`, `has_result`, `is_edited` (when a human has updated the result), and `fields: {key: value}`.
- If `prompt_id` is omitted, the endpoint returns the prompts that have results in the group, so the UI can offer a picker.

**UI:** a **Results** tab next to Documents and Upload when a group is selected.

- A prompt picker, which defaults to the prompt with the most results in the group
- An MUI DataGrid with one row per document and one column per field, plus a status column (no result, pending, done, edited). Clicking a row opens the document with the extraction sidebar.
- A **Group runs** section above the grid that shows the latest group run per prompt, with stale markers and Run and Re-run buttons
- CSV export, built client-side from the loaded rows
- A "Run missing" button, shown to editors, that calls the existing bulk-run LLM path scoped to the group (2.4)

## 7. SDKs and MCP

### 7.1 TypeScript SDK (`packages/typescript/sdk/src/docrouter-org.ts`, `types/`)

- `getGroupKeys`, `setGroupKeys`, `listGroupValues`, `getGroup`, `updateGroup`, `getGroupResults`, `runGroupPrompt`, `listGroupRuns`, `getGroupAccess`, `setGroupAccess`, `deleteGroupAccess`
- `listDocuments` gains `groupKey`, `groupValue` and `groupMissing`.
- Add `GroupKey`, `GroupValue`, `Group`, `GroupRun`, `GroupAccess` and related types.

The frontend calls the API through this SDK, so each phase's SDK changes land before its UI work.

### 7.2 Python SDK (`packages/python/sdk/src/docrouter_sdk/`)

- New `groups.py` API module that mirrors `tags.py`, and matching models in `models/`
- Add the group parameters to `documents.py`

### 7.3 MCP server (`packages/typescript/mcp/src/index.ts`)

- New tools: `list_group_keys`, `list_group_values`, `get_group`, `get_group_results`, `run_group_prompt`, `get_group_runs`
- Extend `list_documents` with `group_key`, `group_value` and `group_missing`.
- Tool descriptions explain that groups come from metadata, and that changing a document's metadata moves it between groups.
- The access endpoints and `set_group_keys` are not exposed through MCP, so an agent cannot change who can see a file.

## 8. Delivery phases

| Phase | Scope | Exit criteria |
|-------|-------|---------------|
| **1. Group keys and browsing** | `group_keys` on orgs, static indexes in `index_registry.py`, dynamic `docs_group_*` indexes, normalization on every write path, `common/groups.py`, `groups/values` and `groups/item`, group parameters on `GET /documents` and bulk operations, `test_groups.py`, SDK changes, the group-by pane, header and upload pre-fill, org settings UI | A user can group documents by claim number, open a claim, upload into it and bulk-act on it, and share a link to it. No confidentiality claim until phase 3. |
| **2. Group runs and results** | Remove `peer_match_keys` (API, UI, SDKs, `_build_prompt_context`), group runs refactor, `queues.group_llm` worker and indexes, `group_llm_runs`, staleness, the results endpoint, the Results tab, MCP tools | A claim shows one row per document with extracted fields, and a claim-level prompt runs over all its documents with a stale marker. Prompt create/edit has no peer-metadata grouping control. |
| **3. Access control** | `groups` ACL fields, `group_readers`, the access endpoints, `get_doc_for_user`, required `visibility` in list queries, move checks on metadata writes, the audit in 4.5, `test_group_access.py`, the access editor | The route-table test passes, and a restricted document is invisible to non-members in every API |

Phase 3's backend and UI ship together. Groups that look restricted in the UI without enforcement would invite users to rely on protection that isn't there.

## 9. Open questions, deferred work and risks

### 9.1 Open questions

1. **Normalizing existing values:** when a key is declared, should a one-off job trim (and, for case-insensitive keys, lowercase) existing values? This plan leaves existing values alone. A job is cheap, but it rewrites customer data.
2. **Intersection vs. union across groups:** the plan uses intersection (4.2), so a document in a restricted claim and a restricted policy is visible only to users in both ACLs. The alternative is union (users in either ACL can see it), which suits "the claim team and the underwriting team both need it". Intersection is recommended because adding a restriction can then never widen access.
3. **Org admin bypass:** org admins see every group. Do compliance requirements need some groups hidden even from org admins? If so, that needs a separate break-glass design, and is not in this plan.
4. **Team principals:** is user-level ACL enough at first, or do we need teams (for example "Claims adjusters, Northeast") from the start? Teams would be a new collection, plus a `team_id` principal in `acl` entries, plus a recompute when team membership changes.
5. **Restricted-by-default keys:** should a declared key be able to make every new value restricted automatically, with the uploader as manager? This would suit claim files where nothing should be open by default.

### 9.2 Deferred

- **Automatic group triggers.** Fire a group run without a user action. This needs:
  - a per-document "processing finished" event (after OCR and all tag prompts), since today's `document.uploaded` fires before OCR
  - a group trigger node in flows, configured with a key and a readiness rule: a quiet period of N minutes after the last document finishes, an expected document count, or required document types present
  - one execution per group, deduplicated with `trigger.dedupe_key = flow_id:key:value`, which already has a unique index

  The group runs in section 5 are the target for this trigger.
- **Setting group keys from extracted data.** A flow node, "Set document metadata", that writes a group key from an LLM result. For example, it would file a scanned page into a claim by the claim number it contains. It goes through the same normalization and `group_readers` recompute (4.4).
- **Submissions.** An upload batch as a unit of processing (one flow run over N documents). This is independent of groups.
- **Free-form folders.** A user-made folder tree with drag and drop, as in the earlier draft of this plan. If it is needed, a folder becomes one more source of group membership and shares the `groups` ACL machinery.
- **Default tags per group.** A group could carry tags that are added to documents when they join it, so that filing into a claim starts the right processing. This needs care, because joining happens through metadata edits.
- **Complete document deletion.** Today the delete route and `ad.common.delete_doc` miss several collections keyed by document (flow executions and blobs, form submissions, agent threads, webhook deliveries). Bulk delete by group makes this more visible. Add a `delete_doc_full` helper that removes everything. Consider doing this in phase 1 or 2 if bulk delete-by-group ships there; otherwise document orphans accumulate faster once grouping is in use.
- **ImageRight import.** A script on the Python SDK that declares `ir_drawer`, `ir_file` and `ir_folder` as group keys, sets them on upload, and maps ImageRight security onto group ACLs.
- **Access audit log.** Who viewed or changed access to a restricted group. Access changes are logged from phase 3, and a queryable audit collection can follow.

### 9.3 Risks

- **Missed enforcement point.** A document route that skips `get_doc_for_user` leaks restricted content. Mitigations: the route-table test in 4.7, the required `visibility` argument, and reviewing every new document route against 4.5.
- **Metadata is now a security attribute (phase 3 onward).** Every path that writes metadata (routes, bulk update, SDKs, MCP, flows, future importers) must call `apply_group_metadata_rules` and recompute `group_readers`. Mitigation: one write helper in `common/groups.py` and a test that seeds a restricted group and writes through each path.
- **Stale `group_readers` after a race.** An upload can compute readers while the group's ACL is changing. Mitigations: re-read restricted groups inside the upload write, apply the stricter readers during long recomputes (4.3), and provide a `repair_group_readers(org_id)` helper that recomputes every document.
- **Aggregation cost on large orgs.** `groups/values` scans every matching document. If it becomes slow, cache per-value counts in `groups` rows, updated with `$inc` on metadata writes. Cached counts would include documents the caller cannot see, so they work only for unrestricted groups.
- **Context limits on group runs.** Large groups can exceed the model's context window. Mitigations: the document cap and the pre-flight token estimate in section 5. A map-reduce run (summarize each document, then combine) is a later option.
- **KB search quality.** Post-filtering restricted hits can return fewer results than requested. Over-fetching covers this in most cases.
