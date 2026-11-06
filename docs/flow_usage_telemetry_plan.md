# Flow usage metrics via SPUs (pages, steps, items)

**Goal:** Answer “how many pages / flow steps / items / LLM·OCR calls (and retries)
today?” by **extending the existing SPU usage path** — same Mongo collection,
same `/payments/usage/range` API, same subscription usage chart — not a parallel
telemetry stack.

**Related:** [Flow OCR cache](./flow_ocr_cache_plan.md) (cache hits: pages yes,
SPUs no), [LLM concurrency](./llm_concurrency_plan.md) (retries).

**Order:** Phase 1 (pages on existing records + API/UI) → Phase 2 (flow step/item
rows) → Phase 3 (retries, optional).

---

## Verdict from `log4.txt` (2026-07-19)

Rough ops snapshot (UTC ~11:37–19:11). Full caveats in the appendix.

| Metric | Estimate |
|--------|----------|
| Pages OCR’d in flows | **~90,584** (all `pages=1`) |
| Flow executions | **~2,597** / **~2,594** finished |
| Flow steps (OCR+LLM nodes) | **~4,104** |
| Items | **~90k** OCR / **~91k** LLM |
| OCR / LLM billable calls | **~90.6k** / **~91.1k** |
| LLM retries (429) | **~7.3k** |
| OCR retries | **~0** |

Today’s SPU rows already approximate **successful OCR/LLM calls** (`operation`
+ record count) and **credits** (`spus`). They do **not** store `pages`, steps,
items, or retries — so we could not answer “pages today” from the DB alone.

---

## Principle: reuse SPUs, don’t fork

What already works:

| Piece | Role |
|-------|------|
| `record_spu_usage` → `payments_usage_records` | Single write path |
| `GET …/payments/usage/range` | Day × `operation` aggregates |
| `SubscriptionSPUUsageChart` | Org UI over that API |

**Do not** add `usage_events`, daily rollup jobs, or a second chart stack unless
Phase 1–2 prove insufficient.

Keep a hard split inside the **same** collection:

- **`spus > 0`** → billable (existing credit consumption unchanged).
- **Extra fields / `spus = 0` metric rows** → observability only; never decrement
  credits.

---

## Phase 1 — Pages on billable records (simplest win)

Almost every OCR/LLM charge already knows page count at write time. Persist it.

### Record shape (additive)

Extend `save_complete_usage_record` / `record_spu_usage` with optional:

```python
pages: int | None = None           # pages in this charge
execution_id: str | None = None  # when from a flow
document_id: str | None = None   # real doc id when known
```

Call sites that already have pages:

- `ocr_runners.run_document_ocr` — `n_pages`
- `docrouter_flows.services` flow LLM — `len(ocr_pages)` or 1
- document LLM path — existing `num_pages`

Billing math unchanged. Missing `pages` on old rows → treat as unknown (do not
assume 0 in “total pages” UI without a note).

### API

Extend usage/range aggregation:

```javascript
{
  $group: {
    _id: { year, month, day, operation },
    total_spus: { $sum: "$spus" },
    total_pages: { $sum: { $ifNull: ["$pages", 0] } },
    calls: { $sum: 1 },   // record count ≈ successful calls
    ...
  }
}
```

Extend `UsageDataPoint`:

```text
spus, pages, calls, operation, source, date
```

`UsageRangeResponse` adds `total_pages`, `total_calls` (optional; easy).

### UI

Same chart component:

- Keep stacked SPUs by operation (current behavior).
- Add a second total / toggle: **Pages** (and optionally **Calls**).
- Colors: add `flow_llm` alongside existing `ocr` / `document_llm` / `agent_llm`
  (today `flow_llm` falls through to gray).

**After Phase 1 you can answer:** pages today, SPUs today, successful OCR/LLM
calls today (by operation) — for anything that already records SPUs.

---

## Phase 2 — Flow steps & items (same collection)

Billable OCR/LLM rows are **per item** (or per provider call), not per graph
node. To get steps/items without a new system, write **metric-only** rows through
the same API:

```python
await record_spu_usage(
    org_id,
    spus=0,                          # no credit impact
    operation="flow_step",
    pages=None,
    items=N,                         # new optional field
    execution_id=...,
    node_id=...,
    # store node_type on the record
)
```

### Rules for `spus=0`

Today `record_payment_usage` bails out when `spus <= 0`. Change to:

1. Still **insert** the usage record (with `pages` / `items` / ids).
2. **Skip** credit balance updates and paid-overage side records when `spus == 0`.

One code path, one collection, one range query.

### When to emit

| Event | `operation` | `spus` | Fields |
|-------|-------------|--------|--------|
| Flow node finished processing its item list | `flow_step` | 0 | `items`, `execution_id`, `node_id`, `node_type` |
| Existing OCR charge | `ocr` | >0 | `pages`, ids |
| Existing flow LLM charge | `flow_llm` | >0 | `pages`, ids |

Emit `flow_step` once per node run from `map_flow_items_batch` completion (or
OCR/LLM node wrappers) — same place that already logs
`Processing N items … node_type=…`.

### Aggregates

| Question | Query |
|----------|--------|
| Flow steps today | `count` where `operation=flow_step` |
| Items today | `sum(items)` where `operation=flow_step` |
| Items for OCR steps only | filter `node_type=docrouter.ocr` (store on record) |
| Pages today | `sum(pages)` on billable ops (Phase 1) |

Chart: either a third metric toggle (**Steps** / **Items**) or a small summary
row under the existing chart (`Steps: … · Items: … · Pages: …`).

---

## Phase 3 — Retries (optional, still same path)

Retries are not billable. Same `spus=0` pattern:

```text
operation=llm_retry  (or ocr_retry), spus=0, attempt=k, model=...
```

Emit from `_litellm_acompletion_with_retry` on each Stamina retry (one line per
retry, not per success).

Skip if Phase 1–2 are enough; Jul 19 showed retries matter under rate limits but
are secondary to pages/steps/items.

---

## What we explicitly are not doing

- New `usage_events` collection or parallel telemetry service
- Nightly rollup jobs (range aggregation on `payments_usage_records` is enough)
- Per-item metric rows beyond what billing already writes
- Changing SPU pricing formulas
- Backfilling historical pages (forward-only)

---

## Implementation checklist

### Phase 1

1. Add `pages`, `execution_id`, `document_id` to `record_spu_usage` →
   `save_complete_usage_record`.
2. Pass `pages` from OCR runners + flow/document LLM call sites.
3. Extend usage/range `$group` + Pydantic/TS types (`pages`, `calls`).
4. Chart: show pages (and calls); color `flow_llm`.
5. Tests: OCR/LLM record includes `pages`; range sums pages; `spus` billing
   unchanged.

### Phase 2

1. Allow `spus=0` inserts without credit mutation.
2. Add `items`, `node_id`, `node_type` optional fields.
3. Emit `flow_step` from item-batch / node completion.
4. Range API: sum `items`, count `flow_step`; chart summary or toggle.
5. Tests: step row does not change customer balances; sums match batch `N`.

### Phase 3 (optional)

1. Emit `llm_retry` with `spus=0` from litellm retry wrapper.
2. Surface retry count in range summary.

---

## Success criteria

1. Usage chart (or its totals) answers **pages / SPUs / calls** for a date range
   without log scraping.
2. After Phase 2, same UI/API answers **flow steps** and **items**.
3. `spus=0` rows never reduce subscription/purchased/granted credits.
4. Cache hits (future): may record `pages` via `spus=0` + `operation=ocr_cache`
   or omit; must not double-charge OCR SPUs.

---

## Appendix — log caveats (2026-07-19)

1. Log lines `step N: SUCCEEDED` are **Textract polling**, not flow graph steps.
2. Flow OCR currently passes `document_id=execution_id` into runners — fine for
   correlation if we also store `execution_id` explicitly; prefer real
   `document_id` from item meta when present.
3. Pages ≈ SPUs ≈ calls only because that day was all 1-page items at 1 SPU;
   not a general invariant (`SPU_PAGES_PER_UNIT = 25`, cost multiplier).
4. Retries do not create SPU rows today — hence Phase 3 if we care.
