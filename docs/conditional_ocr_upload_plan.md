# Conditional OCR on upload + bulk OCR actions

Plan for skipping automatic whole-document OCR when it is not needed, and adding a **Bulk Run OCR** action so operators can run (or re-run) OCR on demand. LLM and KB indexing **do not** auto-trigger OCR; they fail with a clear error when OCR text is required but missing.

**Implementation order:** Phase 1 (bulk OCR) first, then Phase 2 (skip on upload), then Phase 3 (errors).

---

## Goals

1. **Flow-only / large-document customers** can upload multi-hundred-page PDFs without enqueueing Textract on every upload.
2. **Classic customers** (tags + prompts + KB) can still get OCR when they need it—via **manual** single-doc OCR or **bulk** OCR from Actions.
3. **No auto-OCR-on-demand** in LLM/KB workers (no queue coordination, dedupe, or polling in those paths).
4. **Parallel bulk OCR** with the same UX patterns as **Bulk Run LLM** (`DocumentBulkRunLLM.tsx`).

---

## Current behavior (baseline)

| Step | What happens |
|------|----------------|
| Upload | Always `send_msg("ocr", …)` in `documents.py` |
| OCR worker | Full-doc Textract → saves OCR JSON → enqueues LLM + KB |
| No prompts / no KB | OCR still runs; LLM no-ops; wasted work on large PDFs |
| LLM API | 404 if OCR metadata missing |
| LLM worker | Does not ensure OCR; may fail on missing text |
| Manual OCR | `POST /ocr/run/{document_id}` (`force`, `ocr_only`) exists |

---

## Target behavior

### Upload

- If **whole-document OCR is not needed** at upload time → **do not enqueue OCR**; leave `state = uploaded`.
- If **needed** → keep today’s path (enqueue OCR → LLM → KB).

**“Needed”** means at least one of:

- Organization `default_prompt_enabled` is true **and** the default prompt uses OCR text (`include.ocr_text`, default true).
- Document upload tags map to at least one prompt revision that uses OCR text.
- Document would be indexed into at least one KB that requires OCR/plain text (tag rules on KBs).

Non-OCR files (`.txt`, `.md`, csv, etc.) keep existing shortcuts in `process_ocr_msg`.

### LLM / KB when OCR is required but missing

- **Fail** with an explicit error (API + worker), e.g. `OCR required but not run for this document`.
- User fixes via **Run OCR** on the document or **Bulk Run OCR** in Actions.
- No automatic enqueue from LLM/KB handlers.

### Flows

- Unchanged: `document.uploaded` fires at upload; per-page OCR in `docrouter.ocr` does not use the document OCR store.

---

## Phase 1 — Bulk Run OCR (ship first)

Mirror **Bulk Run LLM** (`DocumentBulkRunLLM`, `bulk_analyze_executions`, `POST …/llm/bulk-analyze`).

### UX (Actions modal)

Add operation under a new **OCR** group in `DocumentBulkUpdate.tsx`:

- **Run OCR** — same document filter as other bulk actions (grid search, tag filters, metadata).

**Execution modes** (same labels as Bulk Run LLM; OCR-specific semantics below):

| Mode | Label (UI) | OCR behavior |
|------|------------|--------------|
| `outdated` | Run when missing or outdated | Queue OCR if no result **or** stored OCR config fingerprint ≠ current org OCR settings |
| `missing` | Run only when completely missing | Queue OCR only if `get_ocr_json()` is absent |
| `all` | Run on all matching documents | Queue OCR for every OCR-supported match with `force=true` |

**Outdated** for OCR means **org OCR settings changed** since the stored run (provider/mode, Textract feature types, etc.)—not prompt version. Prompt version remains the concern of **Bulk Run LLM**.

**Parallel runs:** reuse `runWithConcurrency` + session-stored concurrency limit (same pattern as `DocumentBulkRunLLM`).

**Progress UI:** per-document rows with `pending | running | completed | error | cancelled`; cancel support.

### Backend

#### `bulk_analyze_ocr` (new)

Location: `packages/python/analytiq_data/ocr/bulk_analyze.py` (parallel to `llm/bulk_analyze.py`).

```text
POST /v0/orgs/{organization_id}/ocr/bulk-analyze
Body: {
  tag_id?: str,              // optional anchor tag (include in doc tag filter if set)
  mode: "all" | "missing" | "outdated",
  document_filters: { tag_ids, name_search, metadata_search, filters }
}
Response: {
  total_executions: int,
  executions: [{ document_id, document_name, reason? }]
}
```

Logic:

1. `list_all_matching_docs(...)` — reuse `analytiq_data.common.doc.list_all_matching_docs`.
2. Filter to `ocr_supported(user_file_name)`.
3. Batch-load OCR presence + stored metadata (`get_ocr_json` / `get_ocr_metadata` or one aggregation on blob keys).
4. For `outdated`, compare **OCR config fingerprint** (see below) with current `fetch_org_ocr_config(org_id)`.
5. Return flat `executions` list (no prompt groups—OCR is per document).

#### OCR config fingerprint

When saving OCR JSON/text, persist in blob metadata:

```text
ocr_config_fingerprint: stable hash of OrgOcrConfig
  (mode, textract.feature_types, mistral/llm/pymupdf settings as applicable)
```

Helper: `current_ocr_config_fingerprint(cfg) -> str` and `is_ocr_outdated(stored_meta, current_cfg) -> bool`.

Documents with `ocr_failed` count as needing run in `outdated` and `missing`.

#### Bulk execute (frontend-driven)

No new “bulk execute” API required for v1: frontend calls existing per-doc endpoint in parallel:

```text
POST /v0/orgs/{organization_id}/ocr/run/{document_id}?force={mode==all}&ocr_only=true
```

Use `ocr_only=true` so completion does **not** auto-enqueue LLM/KB (operator may run Bulk LLM separately).

Optional later: `POST /ocr/bulk-run` that enqueues all IDs server-side (fewer HTTP round-trips).

### Frontend files

| File | Change |
|------|--------|
| `DocumentBulkRunOCR.tsx` | New; clone structure from `DocumentBulkRunLLM.tsx` |
| `DocumentBulkUpdate.tsx` | Add `runOCROperations` to Actions menu |
| `docrouter-org.ts` / SDK types | `bulkAnalyzeOCR`, types for mode + response |
| Tests | `test_bulk_analyze_ocr.py`; frontend smoke optional |

### Tests (Phase 1)

- `missing`: docs without OCR JSON included; with OCR excluded.
- `outdated`: doc with old fingerprint included; current fingerprint excluded.
- `all`: all OCR-supported matches included; passes `force=true` to run endpoint.
- Non-PDF / non-OCR types excluded.
- Respect document grid filters (tag, name, metadata).

---

## Phase 2 — Skip OCR on upload when not needed

### Upload path (`documents.py`)

Replace unconditional OCR enqueue:

```python
if await document_needs_upload_ocr(analytiq_client, org_id, tag_ids):
    await ad.queue.send_msg(analytiq_client, "ocr", msg={"document_id": document_id})
else:
    # state stays uploaded; still fire webhooks + docrouter events
    pass
```

Do **not** enqueue LLM/KB when OCR is skipped and nothing else requires them (see `document_needs_upload_pipeline` below).

### Helpers (new module e.g. `analytiq_data/ocr/upload_policy.py`)

```python
async def document_needs_upload_ocr(...) -> bool:
    """True if any configured prompt on upload tags (or default) needs ocr_text."""

async def document_needs_upload_llm(...) -> bool:
    """True if default prompt enabled or tag-linked prompts exist."""

async def document_needs_upload_kb_index(...) -> bool:
    """True if doc tags match any KB indexing rules."""
```

`document_needs_upload_ocr` implementation sketch:

- If file not `ocr_supported` → False.
- Load org `default_prompt_enabled`; if true, default prompt uses `include.ocr_text` (true by default) → True.
- If any active KB tag-overlaps upload `tag_ids` and file is OCR-supported → True (`find_one` / `limit 1`).
- Else ask **one efficient prompt query** (below): True if any latest revision for those tags needs OCR text.

Do **not** call `get_prompt_revision_ids_by_tag_ids` — it loads all matching revisions and dedupes in Python (fine for the LLM worker, too heavy on the upload path). See **Performance**.

### Performance

Upload policy runs on **every** document save. Keep it to a boolean “does anything need OCR?” — not “list all prompts.”

**Short-circuit order** (cheapest checks first):

1. `ocr_supported(file_name)` → False.
2. No `tag_ids` and `default_prompt_enabled` is false → False for prompts/KB (no tag overlap).
3. `default_prompt_enabled` → True (no prompt DB read).
4. KB existence: `knowledge_bases.find_one({ organization_id, status ∈ active, tag_ids: { $in: tag_ids } })`.
5. Prompt existence (efficient aggregation below).

**Batch uploads:** cache policy per `(org_id, frozenset(tag_ids))` for the lifetime of the request so N files in one `POST …/documents` body share one org + KB + prompt lookup.

#### Efficient prompt query

Goal: return whether **any** latest revision linked to upload `tag_ids` has `include.ocr_text` true (missing field counts as true, same as `get_prompt_group_config`).

Use a single aggregation on `prompt_revisions` with `$limit: 1` — stop as soon as one match is found:

```python
async def any_tagged_prompt_needs_ocr_text(db, tag_ids: list[str]) -> bool:
    if not tag_ids:
        return False
    pipeline = [
        {"$match": {"tag_ids": {"$in": tag_ids}}},
        {"$sort": {"prompt_version": -1, "_id": -1}},
        {"$group": {"_id": "$prompt_id", "doc": {"$first": "$$ROOT"}}},
        {"$replaceRoot": {"newRoot": "$doc"}},
        {
            "$match": {
                "$or": [
                    {"include.ocr_text": True},
                    {"include.ocr_text": {"$exists": False}},
                    {"include": {"$exists": False}},
                ]
            }
        },
        {"$limit": 1},
        {"$project": {"_id": 1}},
    ]
    row = await db.prompt_revisions.aggregate(pipeline).to_list(1)
    return bool(row)
```

Notes:

- **Latest revision only:** `$sort` + `$group` with `$first` — same semantics as `get_prompt_revision_ids_by_tag_ids(..., latest_version=True)` without loading every historical revision.
- **Existence, not enumeration:** `$limit 1` after the `include.ocr_text` filter; we never need the full prompt list on upload.
- **Index:** existing `prompt_id_tag_ids_idx` on `(prompt_id, tag_ids)` helps; optional later: multikey index on `tag_ids` if explain plans show collection scans on large orgs.
- **Shared helper:** `document_needs_upload_llm` can use the same aggregation without the `include.ocr_text` `$match` (any latest revision for tags ⇒ LLM needed).

When skip:

- `state` remains `uploaded` (do not set `ocr_completed`).
- Still send `document.uploaded` webhook / flow event.

When not skip:

- Unchanged: OCR → LLM → KB chain.

### OCR worker

When processing a queued job, keep existing behavior. Optional guard: if `not force` and `not document_needs_upload_ocr` at process time, skip Textract (safety for stale queue messages)—delete msg, leave `uploaded`.

---

## Phase 3 — Clear errors when OCR required but missing

### LLM

| Location | Change |
|----------|--------|
| `app/routes/llm.py` `run_llm_analysis` | Keep 404; message: `OCR required but not run` |
| `msg_handlers/llm.py` | Before prompts: if any selected prompt needs `ocr_text` and no OCR → set `llm_failed`, webhook error, delete msg with log |
| `llm.run_llm` / `_build_prompt_context` | Raise clear exception (already raises on missing text) |

### KB indexing

| Location | Change |
|----------|--------|
| `msg_handlers/kb_index.py` / `indexing.py` | If OCR-supported doc and `get_extracted_indexing_text` returns None → set KB doc status error / log; do not silently skip |

### UI

- Document detail: show **Run OCR** when `state=uploaded` and prompts/KB need OCR.
- Bulk LLM analyze can surface “N documents missing OCR” before execution.

---

## Rollout notes (customer install)

1. Ship **Phase 1** first so operators can bulk-OCR after prompt/KB setup.
2. Ship **Phase 2**; set expectations: new uploads stay `uploaded` until OCR is needed or manually/bulk run.
3. Reduce `N_DOCROUTER_WORKERS` on constrained installs (separate ops note); bulk OCR should use modest parallelism (e.g. 2–4) for large PDFs.
4. Clear stuck `queues.ocr` backlog (50+ jobs at `attempts=3`) before enabling Phase 2.

---

## Out of scope (v1)

- Auto-OCR from LLM/KB when missing (queue + poll + dedupe).
- S3 multipart / longer timeouts (orthogonal; bulk OCR on large docs still needs ops tuning).
- Prompt-change backfill (configuring a new prompt does not auto-OCR existing docs).
- Org flag `disable_ocr_on_upload` (automatic skip replaces explicit flag unless we want an override later).

---

## File checklist

### Phase 1

- [x] `analytiq_data/ocr/bulk_analyze.py`
- [x] `analytiq_data/ocr/ocr_config.py` — fingerprint helper
- [x] `analytiq_data/ocr/ocr.py` — persist fingerprint in metadata on save
- [x] `app/routes/ocr.py` — `bulk-analyze` route
- [x] `DocumentBulkRunOCR.tsx`
- [x] `DocumentBulkUpdate.tsx`
- [x] SDK: `bulkAnalyzeOCR`, types
- [x] `tests/test_bulk_analyze_ocr.py`

### Phase 2

- [x] `analytiq_data/ocr/upload_policy.py`
- [x] `app/routes/documents.py` — conditional enqueue
- [x] Tests: upload with/without tags, default prompt, KB tags

### Phase 3

- [x] `msg_handlers/llm.py`, `msg_handlers/kb_index.py` / `indexing.py`
- [x] Error copy in API responses
- [x] Tests for fail-fast paths
- [ ] UI: document detail Run OCR hint; bulk LLM missing-OCR warning

---

## Reference

- Bulk LLM: `DocumentBulkRunLLM.tsx`, `analytiq_data/llm/bulk_analyze.py`, `POST …/llm/bulk-analyze`
- Single OCR: `POST …/ocr/run/{document_id}`, `process_ocr_msg`
- Upload enqueue: `packages/python/app/routes/documents.py` (~line 209)
