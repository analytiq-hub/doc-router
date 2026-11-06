# Flow OCR cache plan (reuse prior results on matching config + input)

Plan for **`docrouter.ocr`** in document flows to look up previously computed OCR
before calling Textract / Mistral / PyMuPDF, and reuse the result when **effective
OCR config** and **input PDF bytes** match a prior run.

**Related docs:**

- [DocRouter document ↔ flow integration](./docrouter_doc_flow_integration.md) — flow OCR is execution-scoped today
- [Conditional OCR on upload](./conditional_ocr_upload_plan.md) — document OCR store + `ocr_config_fingerprint`
- [Flow rerun storm](./feature.md) — document flow reruns always start a new execution

**Implementation order:** Phase 1 (lookup + document-store bridge) first, then Phase 2 (dedicated flow cache), then Phase 3 (UX + ops).

---

## Goals

1. **Document flow reruns** (`rerun_flow_for_document`, bulk re-run, re-dispatch on upload) should not re-OCR the same PDF when node settings and bytes are unchanged.
2. **Same semantics as bulk document OCR “outdated”** — config drift invalidates cache; identical config + identical input hits cache.
3. **No change to execute-step / pin-data reuse** — engine-level `run_data` seeding continues to work; this plan adds **cross-execution** reuse.
4. **Correct billing** — cache hits must not record duplicate SPU/Textract charges.
5. **Flow-scoped output unchanged** — each execution still gets its own `flow_blobs` `ocr_json` ref for traceability; cache is a read-through source, not a shared mutable blob between executions.

---

## Current behavior (baseline)

| Layer | Behavior |
|-------|----------|
| **`docrouter.ocr` node** | Always loads PDF bytes → `run_flow_ocr_on_pdf` → provider run → saves `ocr_json` to `flow_blobs:{execution_id}/…` |
| **`run_flow_ocr_on_pdf`** | Builds effective `OrgOcrConfig` from org settings + node `ocr_provider` / `textract_feature_types`; **never** reads document OCR store |
| **Document OCR store** | GridFS `ocr` bucket, key `{document_id}_json`, metadata includes `ocr_config_fingerprint` |
| **Document OCR worker** | Skips provider when `force=False` and JSON exists (`get_ocr_json`) |
| **Flow rerun** | New `execution_id`, empty `run_data`; OCR runs again |
| **Execute-step (editor)** | Reuses prior node output via `initial_run_data` when node not dirty — **same execution lineage only** |

Flow OCR and document OCR are intentionally separate today (`docrouter_doc_flow_integration.md` §3.5). Reruns therefore repeat expensive OCR even when the document already has compatible results.

---

## Target behavior

### Lookup (before provider call)

When `docrouter.ocr` runs (or inside `run_flow_ocr_on_pdf`):

1. Compute **input fingerprint** from the PDF bytes about to be OCR’d.
2. Compute **effective config fingerprint** from org OCR settings **after** node overrides (same merge as today).
3. Search cache tiers (ordered, stop on first hit):
   - **Tier A — document OCR store** (when input is the document’s canonical PDF)
   - **Tier B — flow OCR cache** (org-scoped, content-addressed)
4. On **hit**: deserialize cached `ocr_json`, derive `ocr_pages`, proceed as today (write execution-local `flow_blobs`, emit items). **Do not** call `run_document_ocr`.
5. On **miss**: run provider, **write Tier B** (and optionally backfill Tier A only when explicitly aligned — see below), write execution blob, emit items.

### Invalidation

| Event | Effect |
|-------|--------|
| PDF bytes change (new upload / replaced file) | New input fingerprint → miss |
| Node `ocr_provider` or `textract_feature_types` change | New config fingerprint → miss |
| Org OCR settings change affecting effective config | New config fingerprint → miss |
| User requests force re-run | Bypass cache (see §Force) |
| Document deleted | Delete Tier B entries indexed by `document_id`; Tier A already tied to document lifecycle |

Reuse the existing helper shape:

```python
# packages/python/analytiq_data/ocr/ocr_config.py
current_ocr_config_fingerprint(cfg: OrgOcrConfig) -> str
is_ocr_config_outdated(stored_metadata, cfg) -> bool
```

Apply it to the **effective** config produced inside `run_flow_ocr_on_pdf`, not merely org defaults.

---

## Cache keys

### Input fingerprint

Primary key component: **SHA-256 of raw PDF bytes** (hex, full 64 chars).

```text
input_sha256 = sha256(pdf_bytes).hexdigest()
```

Properties:

- Works for document triggers (`files:{pdf_file_name}`), split single-page PDFs, webhook PDFs, and pinned test PDFs.
- Split pages produce distinct hashes (correct — each page is a different input).
- Stable across reruns and executions.

**Optional secondary index** (performance only, not part of uniqueness):

- `(organization_id, document_id)` when `item.json.document_id` is present and PDF ref is `files:{doc.pdf_file_name}`.
- Lets us find candidate rows without hashing multi-hundred-MB files on every lookup once we store `input_sha256` on first run.

We do **not** rely on `document_id` alone — replacing a document’s PDF must miss cache.

### Effective config fingerprint

Build effective config exactly as `run_flow_ocr_on_pdf` does today:

```python
cfg = await fetch_org_ocr_config(...)
# override mode from node ocr_provider
# override textract.feature_types from node textract_feature_types
config_fp = current_ocr_config_fingerprint(cfg)
```

Include in the canonical JSON everything that changes OCR output:

- `mode` (`textract` | `mistral` | `pymupdf`; flow node enum)
- Full `textract.feature_types` when mode is `textract`
- Mistral / LLM sub-settings if flow OCR ever exposes them per node

Exclude from fingerprint:

- `textract_priority` (`high` / `low`) — scheduling only, not result content

### Composite cache key

```text
cache_key = f"{organization_id}:{input_sha256}:{config_fp}"
```

Org-scoped so tenants never share blobs.

---

## Storage design

### Tier A — document OCR store (read-through bridge)

**When eligible:**

- Input PDF ref is the document’s canonical PDF (`files:{pdf_file_name}` from the trigger item).
- `item.json.document_id` matches that document.
- Effective flow config fingerprint **equals** metadata on stored document OCR JSON.
- `get_ocr_json(document_id)` returns payload.

**Action on hit:** Use document JSON as `ocr_json` payload; still copy into execution `flow_blobs` for trace UI.

**When not eligible:** Node provider differs from stored document OCR (e.g. document ran org Textract+TABLES, flow node requests `pymupdf`) → fall through to Tier B or miss.

Do **not** write Tier A from flow OCR by default (keeps document store semantics unchanged). Optional future: “promote flow OCR to document store” admin action.

### Tier B — `flow_ocr_cache` (new)

Persistent cross-execution cache for all flow OCR inputs.

**Mongo collection** `flow_ocr_cache`:

| Field | Type | Notes |
|-------|------|-------|
| `_id` | string | `{org_id}:{input_sha256}:{config_fp}` |
| `organization_id` | string | |
| `input_sha256` | string | indexed |
| `config_fingerprint` | string | |
| `ocr_provider` | string | denormalized for UI |
| `document_id` | string \| null | secondary index when known |
| `source_storage_id` | string \| null | e.g. `files:…` for debugging |
| `ocr_json_storage_key` | string | GridFS key in dedicated bucket |
| `page_count` | int | |
| `created_at` | datetime | |
| `last_used_at` | datetime | updated on hit |

**GridFS bucket** `flow_ocr_cache` (or reuse `ocr` bucket with prefix `flow_cache/{org}/…`):

- Store UTF-8 JSON blob (same encoding as document OCR).
- Metadata: `ocr_config_fingerprint`, `input_sha256`, `ocr_type`.

**Indexes:**

- Unique: `(organization_id, input_sha256, config_fingerprint)`
- Secondary: `(organization_id, document_id, config_fingerprint)` for document-flow fast path

**Retention:** No TTL in v1; optional org-level cap / LRU in v2. Deleting a document removes rows with matching `document_id`.

---

## Code integration points

| Location | Change |
|----------|--------|
| `analytiq_data/ocr/ocr_config.py` | `build_flow_effective_ocr_config(org_cfg, ocr_provider, textract_feature_types)`; optional `flow_ocr_cache_fingerprint(cfg)` alias |
| `analytiq_data/docrouter_flows/services.py` | `run_flow_ocr_on_pdf`: lookup → run → store; accept optional `*, force: bool = False`, `document_id: str \| None`, `source_storage_id: str \| None` |
| `analytiq_data/docrouter_flows/nodes/ocr_node.py` | Pass `document_id` from item JSON, PDF `storage_id`, `force` from new node param |
| `analytiq_data/ocr/flow_ocr_cache.py` (new) | `lookup_flow_ocr_cache`, `store_flow_ocr_cache`, `invalidate_for_document` |
| `analytiq_data/docrouter_flows/event_dispatch.py` / document delete | Call invalidation hook |
| Tests | `test_flow_ocr_cache.py`, extend `test_docrouter_ocr_node.py` |

Keep public surface through `ad` (`ad.docrouter_flows.services` / `ad.ocr.flow_ocr_cache`).

### Lookup pseudocode

```python
async def run_flow_ocr_on_pdf(..., force=False, document_id=None, source_storage_id=None):
    cfg = build_flow_effective_ocr_config(...)
    config_fp = current_ocr_config_fingerprint(cfg)
    input_sha256 = hashlib.sha256(pdf_bytes).hexdigest()

    if not force:
        if document_id and source_storage_id and _is_canonical_document_pdf(...):
            doc_json = await get_ocr_json(...)
            if doc_json and not is_ocr_config_outdated(doc_metadata, cfg):
                payload = doc_json
                return payload, ocr_pages_plain_text_list(payload)

        cached = await lookup_flow_ocr_cache(org_id, input_sha256, config_fp)
        if cached:
            return cached.payload, cached.pages

    payload = await run_document_ocr(...)
    await store_flow_ocr_cache(...)
    return payload, pages
```

### Execution blob write (unchanged semantics)

On cache hit, `ocr_node` still calls `save_execution_binary_blob` so execution traces, downloads, and delete-GC behavior stay the same. Log cache hit at INFO (`flow OCR cache hit tier=A|B key=…`).

---

## Force re-run

Add optional node parameter:

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `force_ocr` | boolean | `false` | When true, skip cache and always call provider |

Editor execute-step: when OCR node is in `dirty_node_ids` (target node), treat as `force_ocr=true` for that run so “re-run this node” stays intuitive.

Document sidebar **Re-run flow** does not expose force in v1 — cache saves cost; users toggle `force_ocr` on the node or use bulk document OCR for a full refresh.

---

## Edge cases

| Case | Handling |
|------|----------|
| **Document split → per-page OCR** | Each page’s bytes hash separately; full-doc cache does not apply; Tier B still helps across reruns |
| **Same doc, different flow nodes with different providers** | Different `config_fp` → separate cache entries (correct) |
| **Org OCR settings change** | `config_fp` changes → miss; aligns with bulk OCR “outdated” |
| **Pin data / manual test PDF** | Content hash only; no `document_id` index |
| **Empty or corrupt PDF** | No cache write on failure; existing error paths |
| **Concurrent misses** | Two workers may race; unique index on cache key — second writer catches duplicate key and reads winner (same pattern as embedding cache) |
| **SPU / payments** | Cache hit: skip `record_spu_usage` in OCR runners (guard in `run_flow_ocr_on_pdf`, not inside Textract client) |
| **Engine reuse (`initial_run_data`)** | Orthogonal — runs before node execute; cache helps when engine does call `execute` |

---

## Phases

### Phase 1 — Document-store bridge + config/input helpers

- Extract `build_flow_effective_ocr_config`.
- In `run_flow_ocr_on_pdf`, before provider: if canonical document PDF + matching fingerprint → reuse `get_ocr_json`.
- Tests: rerun simulation calls provider once; second call with same bytes/config skips provider mock.
- **Delivers value** for the common case: document flow OCR node matches org Textract settings, document already OCR’d at upload.

### Phase 2 — Tier B `flow_ocr_cache`

- Collection + GridFS bucket + lookup/store helpers.
- Wire into `run_flow_ocr_on_pdf` on miss/hit.
- Index registry entry; migration if needed.
- Tests: cross-execution reuse without document store; config change → miss; input change → miss.

### Phase 3 — Node param + observability

- `force_ocr` on `docrouter.ocr` (`ocr.manifest.json`, UI checkbox “Always re-run OCR”).
- Execution log / node output metadata: `ocr_cache: hit_document | hit_flow | miss | forced`.
- Document delete invalidates Tier B rows.

### Phase 4 (optional) — Performance

- Store `input_sha256` on `docs` at upload time to skip re-hash when ref unchanged.
- Metrics: hit rate, bytes saved, provider calls avoided.

---

## Test plan

| Test | Assert |
|------|--------|
| Cache hit (Tier B) | Two `run_flow_ocr_on_pdf` calls, same bytes/config → provider mocked once |
| Config drift | Change `textract_feature_types` → provider called again |
| Input drift | Different PDF bytes → provider called again |
| Tier A bridge | Document with OCR JSON + matching config → no provider; without matching config → Tier B or provider |
| `force_ocr=true` | Always calls provider |
| SPU | Cache hit does not call `record_spu_usage` |
| `ocr_node` integration | Execution blob still written on hit; `json.ocr_pages` populated |
| Org isolation | Org A cache not visible to org B |

---

## Open questions

1. **Default for `force_ocr`:** `false` (prefer cache) vs `true` (preserve today’s always-fresh behavior until operators opt in). Recommendation: **`false`** for document flows; document sidebar rerun is the main cost saver.
2. **Backfill document store from flow OCR?** Defer — keeps upload pipeline ownership clear.
3. **Cache shared across flows in same org?** Yes — same bytes + config should reuse regardless of flow_id (content-addressed design).
4. **Mistral / LLM OCR in flows:** Not in `OCR_PROVIDER_CHOICES` today; when added, extend effective config fingerprint accordingly.

---

## Summary

Document flow OCR should gain a **two-tier lookup** before calling providers:

1. **Document OCR store** when the input is the document’s PDF and effective config matches stored metadata.
2. **`flow_ocr_cache`** keyed by `(organization_id, sha256(pdf_bytes), effective_config_fingerprint)`.

Reruns with unchanged node settings and unchanged PDF reuse prior results, while config or content changes naturally miss cache. Each execution still materializes its own `flow_blobs` copy for tracing; billing skips on cache hits.
