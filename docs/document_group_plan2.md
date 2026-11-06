# Document slices & group-by (v2) — implementation plan

This plan supersedes the per-group ACL model in [`document_groups_plan.md`](document_groups_plan.md) for new work. Reuse v1 for index registry patterns, `delete_doc_full`, cascade delete workers, and `peer_match_keys` removal (§5.2 here).

## Goal

Let users **group documents by metadata** (like SQL `GROUP BY`), drill into **buckets**, and treat the resulting document set as a **slice** for the grid, bulk actions, and **one prompt over all documents in the slice**. Access control stays **org-wide** (read-only, read-write, admin) in a later phase.

Terminology:

| Term | Meaning |
|------|---------|
| **Slice** | All documents in the org that match a **slice expression** (a boolean filter on metadata). Not stored; computed from `docs.metadata`. |
| **Group-by** | How to split documents (that already match the current slice) into **buckets** in the browse pane. Picking a bucket **narrows** the slice (usually adds an equality on that dimension). |
| **Bucket** | One group-by result row (e.g. value `CLM-123`, or label `claim_number present`). |

Tags still drive OCR, tag prompts, and flows. Slices do not auto-run pipelines.

## Decisions

- **Slice expression is the single contract** for `GET /documents`, bulk operations, slice prompt runs, slice results, and cascade delete. One canonical JSON AST, one compiler to MongoDB.
- **Group-by is separate from the slice.** Group-by only drives the left pane (bucket list + counts). It does not define membership by itself until the user selects buckets (which append constraints to the slice).
- **No per-slice ACL in v2.** Phase 3: workspace roles read-only / read-write / admin only.
- **Optional display names** for a bucket or for a full slice (sparse DB rows); no restriction fields.
- **Remove `peer_match_keys` in phase 2** (v1 §5.1).
- **MongoDB 7+** wildcard index `(organization_id, metadata.$**)` for metadata predicates.

## 1. Slice expression language

### 1.1 AST

Expressions are JSON nodes. Each node has `"op"`.

**Leaves (predicates on one document):**

| `op` | Fields | Meaning |
|------|--------|---------|
| `eq` | `key`, `value` | `metadata[key] == value` (after normalization) |
| `present` | `key` | Key exists in metadata (non-empty after normalization) |
| `absent` | `key` | Key not present |
| `key_eq` | `left`, `right` | Both keys present and string values equal |

**Combinators:**

| `op` | Fields | Meaning |
|------|--------|---------|
| `and` | `args`: expression[] | All true |
| `or` | `args`: expression[] | Any true |
| `not` | `arg`: expression | Negation |

Keys are validated (non-empty, no `.`, no leading `$`). Max depth and max nodes per expression (e.g. depth 10, 50 nodes) to bound query cost.

Examples:

All documents on a claim:

```json
{ "op": "eq", "key": "claim_number", "value": "CLM-123" }
```

Policy files with no claim:

```json
{
  "op": "and",
  "args": [
    { "op": "absent", "key": "claim_number" },
    { "op": "eq", "key": "policy_number", "value": "P-998" }
  ]
}
```

Claim or policy, but not both numbers equal when both present:

```json
{
  "op": "and",
  "args": [
    {
      "op": "or",
      "args": [
        { "op": "present", "key": "claim_number" },
        { "op": "present", "key": "policy_number" }
      ]
    },
    {
      "op": "not",
      "arg": { "op": "key_eq", "left": "claim_number", "right": "policy_number" }
    }
  ]
}
```

Nested drill-down (claim, then doc type) is the **slice** after two bucket picks:

```json
{
  "op": "and",
  "args": [
    { "op": "eq", "key": "claim_number", "value": "CLM-123" },
    { "op": "eq", "key": "doc_type", "value": "Police report" }
  ]
}
```

Helpers in `analytiq_data/common/slices.py` (name TBD):

- `validate_slice_expr(expr)`
- `slice_expr_to_match(expr)` → MongoDB `$match` fragment on `docs`
- `slice_key(expr)` → stable canonical string (for indexes, run dedupe, saved labels)

Wire: JSON query param `slice` (same encoding for POST bodies).

### 1.2 Group-by

Group-by describes **one aggregation dimension** for the browse pane. Documents considered: those matching the **current slice** plus the same grid filters as `GET /documents` (name, tags, etc.).

| `type` | Fields | Buckets |
|--------|--------|---------|
| `value` | `key` | One bucket per distinct `metadata[key]`; docs without the key are omitted from the bucket list (same as classic group-by on a column) |
| `present` | `key` | Two buckets: `present` (key exists) and `absent` (key missing) |
| `key_eq` | `left`, `right` | Two buckets: `equal` (both present and equal) and `not_equal` (otherwise, including one or both missing—define explicitly in tests) |

Phase 1 ships **`value`** and **`present`**; **`key_eq`** as group-by dimension can follow in phase 1 if cheap, else early phase 2.

Selecting a bucket **narrows the slice**:

| Group-by type | User selects | Append to slice |
|---------------|--------------|-----------------|
| `value` | `CLM-123` | `{ "op": "eq", "key", "value": "CLM-123" }` |
| `present` | `present` | `{ "op": "present", "key" }` |
| `present` | `absent` | `{ "op": "absent", "key" }` |

Nested panes: stack group-by dimensions (claim value, then doc type value). The slice is the AND of all bucket constraints; the next pane uses the next group-by spec on that slice.

Org **presets** (optional, admin): named shortcuts for power users, e.g. label `"Policy (no claim)"` with initial slice `{ "op": "absent", "key": "claim_number" }` and group-by `{ "type": "value", "key": "policy_number" }`. Presets are UI defaults only—they expand to slice + group-by in the URL, not a separate server concept.

```json
{
  "id": "policy_no_claim",
  "label": "Policy (no claim)",
  "initial_slice": { "op": "absent", "key": "claim_number" },
  "group_by": { "type": "value", "key": "policy_number" }
}
```

Stored on `organizations` as `slice_browse_presets` (max 10). No `base_scope`; the preset’s `initial_slice` is a normal slice expression.

### 1.3 Normalization

All keys referenced in slice expressions and in `value` group-by should be listed in org **metadata key registry** (same idea as v1 declared keys): trim on write, empty removes key. Registry = union of keys from presets plus keys admins register in org settings. `apply_slice_metadata_rules` on every metadata write path.

### 1.4 Optional labels (display only)

Sparse collection, e.g. `slice_labels`:

- By **full slice:** `slice_key` → `display_name` (for header on a deep link)
- By **bucket:** `(slice_key_at_parent, group_by_key, bucket_id)` → `display_name` (e.g. human title for `CLM-123`)

No ACL fields in v2.

### 1.5 Indexes and doc fields

- `docs`: `(organization_id, metadata.$**)` (MongoDB 7+).
- `slice_llm_runs`: `(organization_id, slice_key, prompt_id, created_at desc)`.
- `queues.slice_llm`, `queues.slice_delete`: worker queue indexes (same template as `queues.llm`).
- Phase 2 on `docs`: `ocr_completed_at`, `metadata_updated_at` (staleness, v1 §5.2).

## 2. Backend — group-by & slices (phase 1)

### 2.1 Data layer

- `get_slice_browse_presets` / `set_slice_browse_presets`
- `validate_slice_expr`, `slice_expr_to_match`, `slice_key`
- `append_bucket_to_slice(parent_slice, group_by, bucket_id)` — pure helper for drill-down
- `list_group_by_buckets(org, slice, group_by, …)` — aggregation pipeline:
  1. `$match` org + `slice_expr_to_match(slice)` + document list filters
  2. Branch on `group_by.type`:
     - `value`: `$group` on `$metadata.<key>` with counts / state summary (v1 §2.2 semantics)
     - `present`: `$group` on `$cond` [$metadata.key exists, "present", "absent"]
  3. Sort, page, optional value regex search (for `value` type only)
  4. Join optional bucket `display_name` from `slice_labels`

### 2.2 Routes

Router `app/routes/slices.py` (or keep `groups.py` with v2 semantics), `get_org_user` on all.

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/v0/orgs/{org}/slice-browse-presets` | List presets |
| `PUT` | `/v0/orgs/{org}/slice-browse-presets` | Replace presets (admin) |
| `POST` | `/v0/orgs/{org}/slices/validate` | Parse + validate expr (optional, for UI builder) |
| `GET` | `/v0/orgs/{org}/slices/buckets?slice=&group_by=&…` | Bucket list for pane |
| `GET` | `/v0/orgs/{org}/slices/label?slice=` | Optional display name for slice |
| `PUT` | `/v0/orgs/{org}/slices/label?slice=` | Set slice display name (admin) |
| `PUT` | `/v0/orgs/{org}/slices/bucket-label?…` | Set bucket display name |
| `DELETE` | `/v0/orgs/{org}/slices/label?slice=&cascade=` | Remove label; `cascade=true` deletes all docs in slice |

Phase 2: `/slices/runs`, `/slices/results`.

**Documents:** `GET /documents` and bulk paths take `slice` (JSON expr). `metadata_search` remains for ad hoc grid filters. **`slice` is the canonical “this bucket / this drill-down” parameter.**

### 2.3 Slice delete

Same as v1 group delete: default drops label row only; `cascade=true` enqueues `slice_delete` and `delete_doc_full` for every document matching the slice. Phase 1: org admin only.

### 2.4 Tests (`test_slices.py`)

- Expression validation; `and`/`or`/`not`; `eq`, `present`, `absent`, `key_eq`; malformed → 400
- Compiler tests: expr → match → known fixture docs in/out
- `slices/buckets` for `value` and `present` group-by agrees with `GET /documents?slice=…` after bucket selection
- Nested drill-down: two `value` group-by levels
- Preset `initial_slice` + group-by matches manual expr
- Bulk paths respect `slice`
- Cascade delete + worker
- Cross-org isolation

## 3. Frontend (phase 1)

### 3.1 URL state

Prefer one shareable param:

- `slice` — JSON expression (widens/narrows with each bucket click)
- `group_by` — current pane dimension (JSON `{ "type", "key" | … }`)
- Optional `preset=policy_no_claim` to seed slice + group_by from org preset

Example after picking claim then type:

`?slice=<encoded-and-of-two-eqs>&group_by={"type":"value","key":"doc_type"}`

All browse state in the URL.

### 3.2 UI

- **Group-by picker** — None; `value` on a metadata key; `present` on a key; optional preset list from org settings
- **Buckets pane** — `list_group_by_buckets`; infinite scroll; show bucket labels
- **Slice header** — human-readable summary of expr (simple formatter or preset name); edit display name; delete slice (cascade); phase 2: Run prompt / Results
- **Grid & bulk** — pass `slice` to SDK
- **Upload** — when slice implies `eq` on a key, pre-fill that metadata field

Org settings: metadata key registry; slice browse presets (label, `initial_slice` expr builder, group-by type + key).

Phase 2+ UI: expression builder for advanced `and` / `or` / `not` (power users); phase 1 can rely on drill-down + presets + simple eq/present/absent chips.

## 4. Slice prompt runs (phase 2)

- **Start:** `POST /v0/orgs/{org}/slices/runs` `{ "slice", "prompt_id" }` → `queues.slice_llm`
- **Worker:** All document IDs matching `slice`, sorted by upload date, cap (default 50); one `_build_prompt_context` call with full document list
- **Storage:** `slice_llm_runs` with `slice`, `slice_key`, `prompt_id`, `document_ids` snapshot, result, staleness fields (v1 §5.2)
- **Readiness / limits / billing:** same as v1 group runs
- Phase 3: read-only org role cannot start runs

Remove `peer_match_keys` (v1 §5.1).

**Slice results:** `GET /slices/results?slice=&prompt_id=` — per-document extraction grid for that prompt across the slice (v1 §6).

## 5. Workspace permissions (phase 3)

| Role | Documents |
|------|-----------|
| **admin** | Unchanged org admin + read-write |
| **read_write** | Today’s member: upload, edit, bulk, slice runs |
| **read_only** | Read/list/download; no writes, no slice run start |

No slice-level ACL. Optional later: per-slice or per-bucket ACL (v1 §4) if customers need claim-level isolation.

Tests: `test_org_document_roles.py`.

## 6. SDK, MCP, agent

- Phase 1: presets, `listGroupByBuckets`, slice labels, `listDocuments({ slice })`, types for `SliceExpr` and `GroupBy`
- Phase 2: `runSlicePrompt`, `listSliceRuns`, `getSliceResults`; drop `peer_match_keys`
- Phase 4 MCP/agent: list buckets, list documents with slice, run prompt on slice (as user)

## 7. Phases

| Phase | Exit criteria |
|-------|----------------|
| **1** | Group-by `value` + `present`; slice expr `eq`/`and`/`or`/`not`/`present`/`absent`/`key_eq`; buckets pane; grid/bulk by slice; presets; SDK; tests |
| **2** | Slice runs + results; remove `peer_match_keys` |
| **3** | Org read-only vs read-write enforcement |
| **4** | MCP/agent slice tools |

## 8. Mapping from v1 and old v2 draft

| v1 / old v2 | This plan |
|-------------|-----------|
| `group_filter` / flat AND list | `slice` expression tree |
| `group_keys` / `group_browse_levels` / `base_scope` | `group_by` + optional `slice_browse_presets` with `initial_slice` |
| “Group” | **Slice** (documents) + **bucket** (pane row) |
| Per-group ACL | Deferred; org roles only in phase 3 |
| `group_llm_runs` | `slice_llm_runs` |

## 9. Open questions

1. **`key_eq` group-by buckets** — exact labels for “one missing” vs “both present unequal” (document in API).
2. **Expression builder scope** — phase 1 presets + drill-down only vs full boolean UI in phase 1.
3. **Saved slices** — user-saved slice expressions (favorites) beyond org presets; defer unless needed.
4. **Per-slice ACL** — revisit v1 if workspace-wide roles are insufficient.

## 10. Deferred

Automatic slice triggers; flow metadata nodes; folders; ImageRight import; access audit for future ACL.
