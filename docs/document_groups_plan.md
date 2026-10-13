# Document Groups — Implementation Plan

## Goal

Let users group documents by metadata value, browse documents group by group on the documents page, run prompts over a whole group, and later restrict access per group.

A **group** is the set of documents in an org that share one value for one metadata key, for example all documents with `claim_number = CLM-123`. This is the DocRouter equivalent of a Hyperscience *case*: a long-lived grouping by business identifier that builds up over many uploads. Each document is still processed on its own when it is uploaded (OCR, tag prompts, flows). Groups add a way to browse, a place to run prompts across documents, and an access-control boundary.

The approach is deliberately small:

- an org-level list of **group keys**, which are the metadata keys allowed to act as groups
- no membership records: a document is in a group because of its metadata
- a `groups` collection that holds a row only for groups that carry state (an ACL or a display name)
- one wildcard index on document metadata that serves every group key in every org
- a group-by aggregation endpoint and a group pane on the documents page
- group prompt runs that send all of a group's documents to the LLM in one call, with the result saved on the group
- per-group access control, where restrictions from several groups combine by intersection

### Decisions

- **Groups come from metadata, not folders.** An earlier draft of this plan proposed a folder tree (`group_id`, `group_path`). That is replaced here. The fixed ImageRight levels (drawer, file, folder) can be declared as group keys and browsed as a nested group-by. Free-form folders are deferred (see 9.2).
- **A document can be in several groups at once**, one for each declared key it has a value for, for example a claim group and a policy group.
- **Group membership is not stored.** Changing a document's metadata moves it between groups. Section 4.4 makes this subject to permission checks once ACLs exist.
- **Tags still drive processing.** Groups do not trigger OCR, LLM or flows in this plan. Automatic group-level triggers are deferred (see 9.2).
- **Prompt-level `peer_match_keys` is retired in phase 2.** Today, prompt revisions can list metadata keys so a single-document LLM run pulls in peer documents and saves one combined result on the source document. Group runs (section 5) replace that behavior. Phase 2 removes the behavior from `_build_prompt_context` and the UI. The prompt API still accepts the field so old clients keep working, but ignores it (5.1). Old prompt settings are not migrated.
- **Deleting a group deletes only its record by default.** Deleting the group's documents too is an explicit `cascade` option (2.6).

## 1. Data model

### 1.1 Group keys (org setting)

A new field on the `organizations` document:

```json
"group_keys": [
  { "key": "claim_number",  "label": "Claim" },
  { "key": "policy_number", "label": "Policy" }
]
```

Rules:

- Only org admins can change `group_keys`. Keys affect access control from phase 3 onward.
- `key` must be a valid metadata key: non-empty, with no `.` and no leading `$`, because it is used in the `metadata.<key>` field path. One validator, `validate_group_key`, enforces this everywhere a key reaches a query, including undeclared keys in admin grouping (2.2).
- At most 10 keys per org. This keeps the group-by picker usable and bounds the number of `$or` terms in access lookups (4.2). Indexes do not limit it, because one wildcard index covers every key (1.5).
- A key cannot be removed while any `groups` row for it is restricted. The API returns `409` and lists the restricted groups. Otherwise, removing a key would silently lift restrictions.
- The order of the list is the order shown in the UI's group-by picker.

### 1.2 Values and normalization

Document metadata stays `Dict[str, str]`, as it is today.

- **Trim on write.** Values for declared keys are trimmed of surrounding whitespace on every write path: upload (JSON and multipart), `PUT /documents/{id}`, and the bulk metadata update.
- **Case.** Values are case-sensitive and are never case-folded. `CLM-123` and `clm-123` are different groups. Callers that need case-insensitive grouping normalize before upload.
- **Empty values.** An empty string after trimming counts as "no value". The server removes the key from metadata instead of storing `""`, so the document belongs to no group for that key.
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
- Deleting a group (`DELETE /groups/item`, 2.6) removes its row, and with it the display name and any restriction. It deletes documents only when `cascade=true` is passed.
- Groups are flat. Nesting in the UI (Claim, then Document type) is a browsing view, not a hierarchy of `groups` rows. That keeps ACLs per `(key, value)`, with no ancestor chain to walk.

### 1.4 New field on `docs`

| Field           | Type                | Notes |
|-----------------|---------------------|-------|
| `group_readers` | `list[str] \| null` | Added in phase 3. The intersection of `readers` across every restricted group the document belongs to. `null` means no restricted group applies, and the document is visible to every org member as today. `[]` means the document sits in at least one restricted group whose ACL has no users (only org admins can see it). See 4.3. |

| `ocr_completed_at` | `datetime \| null` | Added in phase 2. Set when OCR finishes. Used to detect stale group runs (5.2). |
| `metadata_updated_at` | `datetime \| null` | Added in phase 2. Set on every metadata write. Used to detect stale group runs (5.2). |

No other document fields change. Group membership is read from `metadata`.

### 1.5 Indexes

All indexes are static. They go in `EXPECTED_INDEXES` in `analytiq_data/mongodb/index_registry.py` and are applied by the deploy-time `reconcile_indexes()` in `index_reconcile.py`. Do not add a versioned migration class only to create these.

- `docs`: one **compound wildcard index** `(organization_id, metadata.$**)`, named `docs_org_metadata_wildcard`. It serves equality and `$exists` matches on any `metadata.<key>`, for every group key in every org. Declaring or removing a key needs no index work.
  - Compound wildcard indexes need **MongoDB 7.0 or later**. Before phase 1 ships, confirm the minimum MongoDB version supported for on-prem deployments, and pin it in the install docs. Hosted deployments use `mongo:latest`.
  - The index does not cover `upload_date` sorting. Within one group, documents are sorted in memory after the indexed match, which is fine at group sizes. Org-wide listing keeps using the existing `docs` indexes.
  - A wildcard index also adds a little cost to every document write that touches `metadata`, for every metadata key. Metadata is small (`Dict[str, str]` with a handful of keys), so this is acceptable. If an org stores many keys that are never grouped, restrict the index with `wildcardProjection` later.
- `groups`: `(organization_id, key, value)` unique.
- `groups`: `(organization_id, restricted)` — for listing restricted groups and blocking key removal.
- `group_llm_runs`: `(organization_id, key, value, prompt_id, created_at desc)`.
- `queues.group_llm` and `queues.group_delete`: the same worker-queue index template as `queues.llm`. Add both to `WORKER_QUEUE_COLLECTIONS` in `index_registry.py`.

### 1.6 Group filters and query patterns

A **group filter** selects documents by one or more group levels. It is a list, so nested group-by (3.2) can combine levels:

```json
[
  { "key": "claim_number", "value": "CLM-123" },
  { "key": "doc_type", "value": "Police report" }
]
```

Each entry has a `key` and a `value`. Entries combine with AND. One helper, `group_filter_to_match(group_filter)`, turns the list into a MongoDB match, and every endpoint that takes a group filter uses it (2.4). Documents without a value for a key belong to no group for that key, and there is no filter or bucket for them.

- **Documents in a group:** `{"organization_id": org, "metadata.<key>": value}`.
- **Nested:** all levels together, for example `metadata.claim_number = "CLM-123"` and `metadata.doc_type = "Police report"`.
- **Values of a key with counts:** a `$match` (org, the existing filters, and visibility from phase 3), then `$group` on `$metadata.<key>`, then `$sort` and `$skip`/`$limit`. See 2.2.
- **Visibility for a non-admin user (phase 3):** `{"$or": [{"group_readers": null}, {"group_readers": user_id}]}`.

## 2. Backend: grouping and browsing (phase 1)

### 2.1 Data layer: `packages/python/analytiq_data/common/groups.py` (new)

Follow the style of `common/doc.py` and `common/tags.py`. Add an explicit import in `analytiq_data/common/__init__.py`. Per CLAUDE.md, this must be an eager import, with no lazy loading.

- `get_group_keys(analytiq_client, organization_id)` returns the declared keys.
- `set_group_keys(analytiq_client, organization_id, keys)` validates the keys (1.1) and saves them. No index work is needed (1.5).
- `validate_group_key(key)` enforces the key rules in 1.1. Every function that puts a key into a query calls it.
- `group_filter_to_match(group_filter)` validates a group filter (1.6) and returns its MongoDB match.
- `normalize_group_metadata(group_keys, metadata)` applies the rules in 1.2 and returns new metadata (pure function, no I/O).
- `apply_group_metadata_rules(analytiq_client, organization_id, metadata)` loads `group_keys` and returns normalized metadata for write paths (1.2).
- `list_group_values(analytiq_client, organization_id, key, *, match, value_search, skip, limit, sort)` runs the aggregation in 2.2.
- `get_group(analytiq_client, organization_id, key, value)` returns the `groups` row, or a default (unrestricted, no display name) when there is none.
- `upsert_group(...)` manages `groups` rows. Phase 1 uses it only for `display_name`.
- `delete_group(analytiq_client, organization_id, key, value, *, cascade)` is described in 2.6.

### 2.2 Group values aggregation

`list_group_values` takes the same filters as `GET /documents` (name search, tags, metadata search, grid filters), through `build_docs_match_query`. That way the pane and the grid always agree. The pipeline is:

1. `$match` on the document query, plus `metadata.<key>: {$exists: true}` so documents without a value are left out, plus the parent group filter for nested levels (3.2).
2. `$group` by `$metadata.<key>`:
   - `count`
   - `last_upload: {$max: "$upload_date"}`, `first_upload: {$min: "$upload_date"}`
   - state counts, using `$sum` over `$cond` on `state` (the `DOCUMENT_STATE_*` constants in `common/doc.py`):
     - `done`: `llm_completed`, and `ocr_completed` for documents whose tags have no prompts
     - `error`: `ocr_failed`, `llm_failed`
     - `in_progress`: every other state (`uploaded`, `ocr_processing`, `llm_processing`, and `ocr_completed` while prompts are still queued)

     Telling `ocr_completed` apart as done or in progress needs the tag pipeline policy. If that is too costly inside the aggregation, report `ocr_completed` as its own count and let the UI label it.
3. `value_search` adds a case-insensitive regex on the value after `$group`. Escape the user input with `re.escape` before building the regex.
4. Sort by `last_upload desc` (the default), `value asc` or `count desc`. Then `$skip`/`$limit`, with a `$facet` for the total number of values.
5. Join `display_name` and `restricted` from `groups` rows for the values on the page, with one `$in` query.

The `$group` scans every matching document in the org, so its cost grows with the size of the filtered set, not the page size. That is fine at today's volumes. Section 9.3 covers what to do if it becomes slow.

Grouping by an undeclared key is allowed for **org admins only**, and it never applies to ACLs. The key still goes through `validate_group_key`, because it is placed into the `$group` expression and the field path. This is for exploring data before deciding to declare a key.

### 2.3 Routes

New file `packages/python/app/routes/groups.py`, registered in `app/main.py` the same way `tags_router` is. Every endpoint first requires `get_org_user`, as documents and tags do.

Group values can contain `/` and other characters that proxies decode unreliably in path segments, so groups are identified by `key` and `value` **query parameters**, not path segments.

| Method | Path | Purpose |
|--------|------|---------|
| `GET`  | `/v0/orgs/{org}/group-keys` | List the declared keys. |
| `PUT`  | `/v0/orgs/{org}/group-keys` | Replace the list. Admin only. Returns `409` if it would remove a key that has restricted groups. |
| `GET`  | `/v0/orgs/{org}/groups/values?key=&group_filter=&value_search=&skip=&limit=&sort=` plus the document filters | The aggregation in 2.2. `group_filter` holds the parent levels for nested group-by. |
| `GET`  | `/v0/orgs/{org}/groups/item?key=&value=` | One group: counts, `display_name`, `restricted`, and (phase 3) `my_role`. |
| `PUT`  | `/v0/orgs/{org}/groups/item?key=&value=` | Set `display_name`. Org admin only. |
| `DELETE` | `/v0/orgs/{org}/groups/item?key=&value=&cascade=false` | Delete the group record, and with `cascade=true` its documents too (2.6). |
| `GET`  | `/v0/orgs/{org}/groups/results?key=&value=&prompt_id=` | Group results view (section 6). |
| `POST` | `/v0/orgs/{org}/groups/runs` | Start a group prompt run (section 5). |
| `GET`  | `/v0/orgs/{org}/groups/runs?key=&value=&prompt_id=` | Get the latest group runs. |
| `GET`, `PUT` | `/v0/orgs/{org}/groups/access?key=&value=` | Phase 3 (section 4). |

`key` must be a declared key on every endpoint except `groups/values`, where an admin may pass an undeclared key (2.2).

`group_filter` is the group filter list from 1.6, sent as a JSON-encoded query parameter. JSON avoids any ambiguity when values contain `:`, `,` or `=`.

Pydantic models go in `app/routes/groups.py`: `GroupKey`, `GroupValue`, `ListGroupValuesResponse`, `Group`, `GroupRunRequest`, `GroupRun`, `GroupAccess`, `GroupAclEntry`.

### 2.4 Documents API changes (`app/routes/documents.py`, `common/doc.py`)

- `GET /documents` gains a `group_filter` parameter (1.6, 2.3). It maps onto `build_docs_match_query` through `group_filter_to_match`. `metadata_search` could express a single level, but a dedicated parameter makes the group scope explicit in bulk-action code and keeps one parser for nested levels.
- `build_docs_match_query` and `list_all_matching_docs` take the same `group_filter`, so bulk analyze (OCR, LLM, flows) can target one group.
- Every server-side metadata write path calls `apply_group_metadata_rules` (1.2): JSON upload, multipart upload, `PUT /documents/{id}` and the bulk metadata update. The SDKs, the MCP server and the agent write through these routes, so they are covered without changes of their own.
- `PUT /documents/{id}` **replaces** the whole metadata dict today. A client that sends partial metadata drops the keys it left out, which moves the document out of its groups. This stays as it is for compatibility, but in phase 3 such a drop counts as a move and goes through the checks in 4.4.
- **Phase 1 does not add confidentiality.** Until phase 3, any org member can still read and edit metadata on all org documents, including moving them between group values. Do not describe group browsing as access control before phase 3 ships.

### 2.5 Tests: `packages/python/tests/test_groups.py` (new)

- Declaring keys: validation (including keys with `.` or a leading `$`), admin-only, the 10-key limit
- The `docs_org_metadata_wildcard` index exists after reconcile, and a group query uses it (`explain()`)
- Normalization on every write path (upload JSON, multipart, update, bulk update), including trimming and removing empty values. Case is preserved.
- `groups/values`: counts, state counts, documents without the key left out, `value_search` (including regex special characters), paging, each sort, and that results agree with `GET /documents` under the same filters
- **Nested group-by:** with a parent value selected, child-key aggregation and `GET /documents` with a two-level `group_filter` agree
- Undeclared-key grouping is admin-only, and rejects invalid keys
- `GET /documents?group_filter=...` with one and two levels, and a malformed `group_filter` returns `400`
- Bulk OCR, LLM, flows, delete, and metadata update respect `group_filter` on the server (mirror existing tests that assert `metadata_search` on bulk paths)
- Group delete (2.6): without `cascade`, documents and their metadata are untouched and only the row goes. With `cascade=true`, every document in the group is deleted with all its data (`delete_doc_full`), and documents outside the group are untouched. A rerun after a simulated crash finishes the job.
- Cross-org isolation: values from org A never appear in org B

### 2.6 Group delete

`DELETE /groups/item?key=&value=&cascade=false`

- **Default (`cascade=false`):** delete the `groups` row only, which removes the display name and (phase 3) any restriction. Documents keep their metadata and stay in the group, because membership comes from metadata. The group still appears in the values list as long as documents have the value. If there is no row, the call is a no-op that returns `204`.
- **`cascade=true`:** delete the row and every document whose `metadata.<key>` equals the value. The UI shows the document count and requires the user to type the value to confirm.
  - The documents are deleted in the background: the route enqueues a `group_delete` worker message with the key and value and returns `202`. The worker deletes matching documents in batches, re-querying each time, so a crash or retry carries on where it stopped. Documents uploaded with the value while the job runs are deleted too.
  - Each document goes through a new `ad.common.delete_doc_full` helper, which cascade delete makes a **phase 1** requirement. Today the cleanup is split between the `DELETE /documents/{id}` route (original file, PDF rendition, `flow_results`) and `ad.common.delete_doc` (`llm_runs`, OCR, KB index and vectors). Several collections keyed by document are missed altogether, so a deleted document's data survives even now. `delete_doc_full` removes all of it: the files, OCR, `llm_runs`, `flow_results`, flow executions and their blobs, form submissions, KB entries and vectors, agent threads, and webhook deliveries. The single-document delete route and bulk delete switch to it as well.
  - Group runs (`group_llm_runs`) for the group are deleted as well.
- **Permissions:**
  - Phase 1: deleting the row requires org admin, because it holds the display name, which only admins set. Cascade requires org admin.
  - Phase 3: deleting the row of a restricted group requires `manager`, and goes through the widening rule (4.4), because removing the restriction can widen access. Cascade requires org admin, or `manager` on the group **and** visibility of every document in it. If any document is hidden from the caller (because another restricted group covers it), return `403` and tell the user to ask an org admin.

## 3. Frontend: group-by on the documents page (phase 1)

### 3.1 URL and state

- `/orgs/[organizationId]/docs?group_by=claim_number` shows the group pane for that key.
- `&group=CLM-123` selects a value.
- `&group_by2=doc_type&group2=...` adds a second level (3.2).

All group state lives in the URL, so links can be shared and the browser's back button works.

### 3.2 Components

In `packages/typescript/frontend/src/components/groups/`:

- **`GroupBySelect.tsx`** goes in the documents page toolbar. Its options are **None** plus the declared keys by label. Admins also get a "Custom key…" entry (2.2).
- **`GroupValuesPane.tsx`** is a resizable, collapsible left pane. It shows:
  - a search box (`value_search`)
  - a sort menu (recent, A–Z, largest)
  - one row per value: the value, the `display_name` if set, the document count, a small state summary (for example "12 · 2 in progress · 1 error"), and a lock icon when restricted
  - infinite scroll over `groups/values`

  Documents without a value for the key are not listed in the pane. They still show in the grid while no value is selected.

  Selecting a row sets `group` in the URL.
- **Second level.** When `group_by2` is set, the selected value expands to show its sub-values. They come from the same endpoint with the parent level passed as `group_filter`. Selecting a sub-value sends both levels as `group_filter` to `listDocuments`. This is how drawer, then file, then folder browsing works without folders.
- **`GroupHeader.tsx`** sits above the grid when a value is selected. It shows the key label, the value, the `display_name` (editable by org admins only), the counts, and buttons for **Run prompt on group** (phase 2), **Results** (phase 2), **Access…** (phase 3, managers only) and **Delete group…**.
- **`GroupDeleteDialog.tsx`** opens from **Delete group…**. By default it deletes only the group record and says that the documents stay. A "Also delete the N documents in this group" checkbox switches to `cascade=true`, and then the user must type the value to confirm. Shown to org admins in phase 1. In phase 3 it is also shown to group managers, following the permissions in 2.6.

### 3.3 Changes to existing components

- **`DocumentList.tsx`** takes a `groupFilter` (the list from 1.6, with one or two levels) and passes it to `listDocuments`. When grouping is active and no value is selected, the grid shows all matching documents, as it does today.
- **Bulk actions** (`DocumentBulkUpdateTags.tsx`, `DocumentBulkUpdateMetadata.tsx`, `DocumentBulkDelete.tsx`, `DocumentBulkRunOCR.tsx`, `DocumentBulkRunLLM.tsx`, `DocumentBulkRunFlows.tsx`) carry `groupFilter` in their `searchParameters` and pass it on. Without this, "select all in this group, then bulk delete" would act on every matching document in the org. Server-side bulk filter tests (2.5) are the source of truth; the frontend has no test runner today.
- **`DocumentUpload.tsx`**: when a group is selected, the upload form pre-fills `metadata[key] = value`, shows "Uploading to: Claim CLM-123", and lets the user clear it.
- **Document page (`docs/[id]`)**: show the document's groups as chips (`Claim: CLM-123`). Each chip links to the documents page with that group selected.
- **Org settings**: a "Group keys" section for admins, wired to `GET`/`PUT /group-keys` only (not a separate org PATCH field). Columns: key and label; drag-to-reorder; confirmation listing restricted groups when a removal is blocked. Phase 3 adds "restrict a value before upload" here (4.6).

## 4. Access control (phase 3)

### 4.1 Model

- **Unrestricted groups** behave like documents do today: every org member can see and edit their documents. A document in no restricted group is unrestricted.
- A group with **`restricted: true`** limits its documents to the users in its `acl`, plus org admins.
- Each `acl` entry gives one org member a role on the group:

| Role      | Can do |
|-----------|--------|
| `viewer`  | See the group's documents, OCR text, extraction results, group runs and the group results view. Download files. |
| `editor`  | Everything a viewer can. Upload into the group (set the key to this value), rename documents, edit their tags and metadata, edit extraction results, run OCR, LLM, flows and group runs, delete documents, and move documents in or out (subject to 4.4). |
| `manager` | Everything an editor can. Change `restricted` and `acl`, and delete the group record (2.6). |

Setting `display_name` is reserved for org admins on every group, restricted or not.

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
| Change `display_name` | Org admin |
| Change `restricted` or `acl` | `manager` on the group |
| Delete the group record, or delete with cascade | See 2.6 |
| Start a group prompt run | `editor` on the group, and the caller can see every document in the group. Otherwise `403` with "the group includes documents you cannot access", because the caller could not read the result (4.5). |
| Declare or remove group keys | Org admin |

**Widening rule:** if a write would let more people see the document, it also requires `manager` on every restricted group the document is leaving. The test is that the document's new `group_readers` is not a subset of the old one, with `null` counting as everyone. Without this rule, any editor could leak a restricted file by editing its claim number, or by sending a `PUT` with partial metadata that drops the key (2.4).

**Flows and workers** write metadata as the system. They bypass these checks, but they still recompute `group_readers`. Flows are configured by org admins, who already see everything.

### 4.5 Enforcement points

This is most of the work in phase 3. Documents are reached through many routes, not only `documents.py`.

- **One helper for single documents.** Add `ad.common.get_doc_for_user(analytiq_client, organization_id, document_id, user, min_role)` in `common/doc.py`. It loads the document, applies the visibility rule, and checks the role for writes. It returns `404` both when the document does not exist and when the caller cannot see it, so the API does not reveal that restricted documents exist. Every route with `{document_id}` in its path uses it.
- **One filter for lists.** `build_docs_match_query` and `list_docs` get a keyword-only, required `visibility` argument built from the current user (`Visibility.for_user(user, org)` or `Visibility.system()`). Making it required means every existing call site has to be updated, and none can be missed by accident.
- **Group endpoints.** `groups/values` counts include only visible documents. A restricted group that the caller has no ACL entry on is omitted from the values list, including restricted groups with no documents yet. Org admins see every group, so they can manage access and pre-restricted empty groups. Users in a group's ACL see it as usual. `groups/item`, `groups/results` and `groups/runs` return `404` for callers with no access.
- **Group prompt runs** (section 5) store the multi-document LLM output on the group. Reading a run requires `viewer` on the group, **and** the caller must be able to see every document in the run's `document_ids` snapshot. Otherwise the output could reveal content from documents in another restricted group. If any document is hidden from the caller, return the run's metadata with the result withheld and the message "includes documents you cannot access".
- **Routes to audit** (each has `{document_id}` endpoints or document lists): `documents.py`, `ocr.py`, `llm.py` (including bulk analyze and bulk run), `forms.py` (form submissions per document: `GET` and `DELETE /forms/submissions/{document_id}` currently skip the document check entirely), `prompts.py`, `flows.py` (run on document, plus the org-wide executions list, execution detail, blob download and resume, which read `flow_executions` without loading the document even though the trigger holds the file name, tags, metadata and LLM result), `knowledge_bases.py` (KB document lists and counts, search, chat), `webhooks.py` (delivery list, detail and retry, whose stored payloads hold document name, tags, metadata and LLM output), `agent.py` (document chat; agent tools such as `get_ocr_text` and `get_extraction_result` rely on the route-level check), and the new `groups.py`. **Dashboard / home counts** are computed in the frontend from list APIs; once those lists honor `visibility`, dashboard numbers follow without a separate backend audit.
- **Knowledge base search and chat.** Vector hits carry `document_id`. Post-filter hits against the caller's visibility, and over-fetch to make up for dropped hits. KB search is also reached from the KB tool inside extraction (`llm/llm.py`) and the flow agent tool (`flows/agent_loop/dispatch.py`), so the post-filter belongs in `search_knowledge_base` itself.
- **Workers, flows and webhooks** run as the system and are configured by org admins, so they can read every document. That is acceptable, because admins already see everything. User-facing views of their output, such as flow execution lists, must still hide entries for documents the caller cannot see.

### 4.6 Routes and UI for access

- `GET /groups/access?key=&value=` returns `restricted`, `acl` (with user names and emails) and `my_role`.
- `PUT /groups/access?key=&value=` takes `{ "restricted": bool, "acl": [{ "user_id", "role" }] }`. It creates the `groups` row if there is none. Every `acl` user must be a member of the org.
- `PUT` with `restricted: false` lifts the restriction and keeps the ACL entries for later. To remove the group record entirely, use `DELETE /groups/item` (2.6).
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
- Lists, counts, `groups/values`, bulk operations, KB search, group results and group runs exclude restricted documents. A restricted group the caller is not in does not appear in `groups/values`, except for org admins (4.5).
- The widening rule blocks an editor from changing or dropping a restricted key value, including through a `PUT` with partial metadata, and allows a manager.
- Uploading with a restricted group's value requires `editor` on it.
- `group_readers` is correct after an upload, an update, a bulk update, an ACL change, a restrict and unrestrict, and removal of a user from the org.
- Removing a key that has restricted groups returns `409`.
- A group run whose documents include one the caller cannot see has its result withheld, and starting a run on such a group returns `403`.
- Only org admins can set `display_name`, on restricted and unrestricted groups.
- Group delete permissions in phase 3 (2.6): a manager can delete the record, cascade is refused with `403` when the manager cannot see every document, and an org admin can always cascade.
- An org API token gets the same results as its user. Org admins see everything.

## 5. Group prompt runs (phase 2)

These replace the removed prompt-level `peer_match_keys` feature for "run a prompt over a set of related documents". The group is chosen explicitly and the result belongs to the group, not to whichever document triggered a tag prompt.

### 5.1 Retire `peer_match_keys` (same phase)

- **API stays compatible.** `PromptConfig` in `app/routes/prompts.py` keeps the `peer_match_keys` field, so clients that still send it get no `422`. The server ignores the value: it is not stored on new revisions, and responses always return `peer_match_keys: []`. Mark the field deprecated in the model's description and in the OpenAPI docs.
- **Revision equality.** The check that decides whether a `PUT` creates a new prompt revision ([`prompts.py`](../packages/python/app/routes/prompts.py), the comparison of `peer_match_keys` against the latest revision) must drop that comparison. Otherwise an old revision with stored keys never compares equal to a new request, and every save creates a new revision.
- **Stored values are ignored.** Existing prompt revisions that have `peer_match_keys` keep the field in MongoDB. `get_prompt_group_config` (`common/prompts.py`) stops returning it, so nothing reads it.
- **SDKs:** the TypeScript and Python SDK models keep the field as optional and deprecated, for the same compatibility reason.
- **UI:** remove the "Grouped Inputs → Metadata group-by keys" control from `PromptCreate.tsx`. Keep the `include` controls (OCR text, PDF, metadata keys), because single-document runs and group runs both use them.
- **Context building:** remove peer-document lookup from `_build_prompt_context` in `llm/llm.py`. Refactor it to take an explicit ordered list of documents. Single-document runs pass one document, and group runs pass the group's documents. `peer_run`, `match_values` and `match_document_ids` on `llm_runs` go away.
- **Tests:** delete or rewrite the peer-grouping tests in `test_llm_prompt_context.py`, and add a test that a `PUT` with `peer_match_keys` succeeds and the value is ignored.
- **Release notes:** say that prompt-level grouping is retired, and that declared group keys and group runs replace it.

### 5.2 Run lifecycle

- **Start:** `POST /groups/runs` with `{ key, value, prompt_id }`. It checks permissions (4.4 in phase 3), enqueues a message on `queues.group_llm` and returns the run ID.
- **Worker** (`worker/worker.py`, same pattern as LLM queue handlers): load **all** of the group's documents as the system, not filtered by the caller's visibility, sorted by upload date, and build one multi-document prompt via the refactored `_build_prompt_context`. The prompt revision's `include` settings (OCR text, PDF, metadata keys) apply unchanged. Message shape: `{ organization_id, key, value, prompt_id, run_id, ... }` with idempotent handling on `run_id`. Because every run covers the whole group, two users get the same result for the same group, and staleness (below) is well defined. Access is enforced when the run is started (4.4) and when its result is read (4.5).
- **Storage:** `group_llm_runs` collection holding `{organization_id, key, value, prompt_id, prompt_revid, document_ids, result, prompt_used, status, error, created_by, created_at}`. `document_ids` is the snapshot of the group at run time.
- **Staleness:** a run is **stale** when its inputs have changed since it ran:
  - the group's current documents differ from `document_ids`
  - a document's OCR was redone after the run (when `include.ocr_text` is on)
  - a document's metadata changed after the run, for keys listed in `include.metadata_keys` (or any key when it is `["*"]`)
  - the prompt has a newer revision than `prompt_revid`

  Per-document LLM results are not inputs to a group run, so they do not affect staleness. To detect OCR and metadata changes, store `ocr_completed_at` and `metadata_updated_at` on `docs`, set on the OCR and metadata write paths, and compare them with the run's `created_at`. The UI shows a "Re-run" button for stale runs.
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

## 7. SDKs, MCP and agent

The TypeScript SDK covers every new API in the phase that adds it. MCP and the internal DocRouter agent get tools in a later phase (phase 4).

### 7.1 TypeScript SDK (`packages/typescript/sdk/src/docrouter-org.ts`, `types/`)

- Phase 1: `getGroupKeys`, `setGroupKeys`, `listGroupValues`, `getGroup`, `updateGroup`, `deleteGroup` (with `cascade`)
- Phase 2: `getGroupResults`, `runGroupPrompt`, `listGroupRuns`
- Phase 3: `getGroupAccess`, `setGroupAccess`
- `listDocuments` gains `groupFilter` (phase 1).
- Add `GroupKey`, `GroupFilter`, `GroupValue`, `Group`, `GroupRun`, `GroupAccess` and related types.
- Prompt types keep `peer_match_keys` as optional and deprecated (5.1).

The frontend calls the API through this SDK, so each phase's SDK changes land before its UI work.

### 7.2 Python SDK (`packages/python/sdk/src/docrouter_sdk/`)

- New `groups.py` API module that mirrors `tags.py`, and matching models in `models/`
- Add `group_filter` to `documents.py`
- Prompt models keep `peer_match_keys` as optional and deprecated (5.1).

### 7.3 MCP server and internal agent (phase 4)

Neither gets group tools before phase 4. Until then they keep working through their existing document tools, and metadata writes they make go through the routes that apply normalization and (in phase 3) the move checks.

**MCP server** (`packages/typescript/mcp/src/index.ts`):

- New tools: `list_group_keys`, `list_group_values`, `get_group`, `get_group_results`, `run_group_prompt`, `get_group_runs`
- Extend `list_documents` with `group_filter`.
- Tool descriptions explain that groups come from metadata, and that changing a document's metadata moves it between groups.
- The access endpoints, `set_group_keys` and group delete are not exposed, so an agent cannot change who can see a file or delete a group's documents.

**Internal DocRouter agent** (`analytiq_data/agent/tools/`, registered in `agent/tool_registry.py`):

- The same read and run tools as MCP: list group keys and values, get a group, get group results, run a group prompt, get group runs.
- The agent acts as the chatting user, so every tool goes through the same visibility and role checks as the routes (4.5).
- The same exclusions as MCP: no access changes, no key changes, no group delete.

## 8. Delivery phases

| Phase | Scope | Exit criteria |
|-------|-------|---------------|
| **1. Group keys and browsing** | `group_keys` on orgs, the metadata wildcard index and `groups` indexes in `index_registry.py`, normalization on every write path, `common/groups.py`, `groups/values` and `groups/item`, `group_filter` on `GET /documents` and bulk operations, group delete with `cascade` and `delete_doc_full` (2.6), `test_groups.py`, TS and Python SDK changes, the group-by pane, header, delete dialog and upload pre-fill, org settings UI | A user can group documents by claim number, open a claim, upload into it, bulk-act on it, and share a link to it. An admin can delete a group record, or a group with its documents. No confidentiality claim until phase 3. |
| **2. Group runs and results** | Retire `peer_match_keys` (UI, `_build_prompt_context`, revision equality, API accepts and ignores), group runs refactor, `queues.group_llm` worker and indexes, `group_llm_runs`, staleness fields on `docs`, the results endpoint, the Results tab, TS and Python SDK changes | A claim shows one row per document with extracted fields, and a claim-level prompt runs over all its documents with a stale marker. Prompt create/edit has no peer-metadata grouping control, and old clients that send `peer_match_keys` still work. |
| **3. Access control** | `groups` ACL fields, `group_readers`, the access endpoints, `get_doc_for_user`, required `visibility` in list queries, move checks on metadata writes, the audit in 4.5, phase 3 delete and run permissions, `test_group_access.py`, the access editor, TS and Python SDK changes | The route-table test passes, and a restricted document is invisible to non-members in every API |
| **4. MCP and agent tools** | Group tools in the MCP server and the internal DocRouter agent (7.3) | An agent can list a user's groups, read group results and start a group run, and sees only what the user can see |

Phase 3's backend and UI ship together. Groups that look restricted in the UI without enforcement would invite users to rely on protection that isn't there.

## 9. Open questions, deferred work and risks

### 9.1 Open questions

1. **Normalizing existing values:** when a key is declared, should a one-off job trim existing values? This plan leaves existing values alone. A job is cheap, but it rewrites customer data.
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
- **ImageRight import.** A script on the Python SDK that declares `ir_drawer`, `ir_file` and `ir_folder` as group keys, sets them on upload, and maps ImageRight security onto group ACLs.
- **Access audit log.** Who viewed or changed access to a restricted group. Access changes are logged from phase 3, and a queryable audit collection can follow.

### 9.3 Risks

- **Missed enforcement point.** A document route that skips `get_doc_for_user` leaks restricted content. Mitigations: the route-table test in 4.7, the required `visibility` argument, and reviewing every new document route against 4.5.
- **Metadata is now a security attribute (phase 3 onward).** Every server-side path that writes metadata (upload, update and bulk update routes, flow nodes, future importers that write to MongoDB directly) must call `apply_group_metadata_rules` and recompute `group_readers`. The SDKs, MCP and the agent go through those routes. Mitigation: one write helper in `common/groups.py` and a test that seeds a restricted group and writes through each path.
- **Stale `group_readers` after a race.** An upload can compute readers while the group's ACL is changing. Mitigations: re-read restricted groups inside the upload write, apply the stricter readers during long recomputes (4.3), and provide a `repair_group_readers(org_id)` helper that recomputes every document.
- **Aggregation cost on large orgs.** `groups/values` scans every matching document. If it becomes slow, cache per-value counts in `groups` rows, updated with `$inc` on metadata writes. Cached counts would include documents the caller cannot see, so they work only for unrestricted groups.
- **Context limits on group runs.** Large groups can exceed the model's context window. Mitigations: the document cap and the pre-flight token estimate in section 5. A map-reduce run (summarize each document, then combine) is a later option.
- **KB search quality.** Post-filtering restricted hits can return fewer results than requested. Over-fetching covers this in most cases.
