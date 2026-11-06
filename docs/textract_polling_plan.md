# Textract polling: reduce `GetDocumentAnalysis` rate-limit pressure

Plan to fix aggressive async Textract polling that causes `ProvisionedThroughputExceededException` during bulk flow OCR and high-concurrency document OCR.

**Primary file:** `packages/python/analytiq_data/aws/textract.py` (`run_textract`).

**Implementation order:** Phase 1 (quick wins) → Phase 2 (adaptive polling) → Phase 3 (optional hard TPS cap + observability).

---

## Problem

Async Textract uses two API steps per document:

1. `StartDocumentAnalysis` (or `StartDocumentTextDetection`)
2. Repeated `GetDocumentAnalysis` / `GetDocumentTextDetection` until the job completes, then paginated result fetch

We limit **job starts** via `system_settings.textract_max_concurrent` (`_textract_concurrency`), but **poll frequency is fixed per job** and does not scale with fleet load. Under bulk OCR many jobs poll every 1–2 seconds simultaneously, overwhelming the `GetDocumentAnalysis` TPS quota even when job concurrency is capped.

Symptoms observed in production (`log6.txt`, bulk flow OCR ~Jul 2026):

- ~11,800 completed 1-page `start_document_analysis` jobs in one run
- **Median 6 status polls** + **1 duplicate result fetch** = **7 `GetDocumentAnalysis` calls per document**
- **370** `ProvisionedThroughputExceededException` lines (retries add more calls)
- All completions had `next_token: None` (single result page; no pagination needed)

Current poll loop (`run_textract`):

- First poll **immediately** after start
- Sleep `min(2 ** min(idx // 5, 3), 10)` → effectively **1 s** for the first several polls, then 2 s, 4 s, 8 s
- On `SUCCEEDED`, **discards** the response and calls `GetDocumentAnalysis` again in a separate results loop

AWS recommends polling async Textract at roughly **5 s intervals**, not 1 s.

---

## Goals

1. **Cut `GetDocumentAnalysis` TPS** during bulk runs by ~50–70% without materially increasing end-to-end batch time.
2. **Preserve low latency** for single-document / interactive OCR (`priority="high"`).
3. **No behavior change** to OCR output, billing, timeouts, or concurrency gate semantics unless explicitly noted.
4. **Stay per-pod** for Phase 1–2 (no Redis required); document multi-process limits.

---

## Non-goals

- Changing Textract feature types, S3 upload path, or `textract_max_concurrent` defaults (may tune separately).
- Sync (`AnalyzeDocument`) API for PDFs.
- Cross-pod coordinated rate limiting (Phase 3 optional only).

---

## Observed completion pattern (log6 baseline)

Use these numbers to tune intervals and to validate after deploy.

| Metric | Value |
|--------|-------|
| Median time invoke → `SUCCEEDED` | ~8.7 s |
| Median status polls | 6 |
| Median total `GetDocumentAnalysis` calls | 7 |
| Mode (most common poll count) | 6 (~32% of jobs) |
| Fast path (1 poll) | ~8% of jobs |
| Result pagination | 100% single page (`next_token: None`) |

Poll-count distribution (status polls until `SUCCEEDED`):

| Polls | Share |
|-------|-------|
| 1–3 | ~24% |
| 4–5 | ~24% |
| 6–7 | ~46% |
| 8+ | ~6% |

---

## Phase 1 — Quick wins (low risk)

### 1a. Reuse `SUCCEEDED` response for blocks

When the poll call returns `JobStatus == SUCCEEDED`:

- If `Blocks` is present and `NextToken` is absent → **use that response**; skip the second results loop.
- If `NextToken` is present → enter pagination starting from that response (do not re-fetch page 0).

**Expected savings:** 1 API call per job (~15% of total calls). Zero latency cost.

**Edge cases to handle:**

- `SUCCEEDED` with empty `Blocks` and no `NextToken` (treat as failure or fall back to one fetch — verify against AWS behavior in tests).
- Text-detection jobs (`get_document_text_detection`) — same logic applies.

### 1b. Replace fixed 1 s early polling with completion-aligned schedule

Replace the current exponential-on-idx sleep with an **elapsed-time schedule** (same for all jobs initially; Phase 2 makes it adaptive):

| Elapsed since `Start*` | Action |
|------------------------|--------|
| 0 – 4 s | **Do not poll** (initial wait) |
| 4 – 14 s | Poll every **2 s** |
| 14 – 60 s | Poll every **4 s** |
| 60 s+ | Poll every **8 s** until `OCR_TIMEOUT_SECS` |

Rationale: median completion ~9 s; polls before ~4 s are almost always `IN_PROGRESS` (wasted TPS).

**Expected savings:** typical job drops from ~6 polls to ~3–4, plus Phase 1a → **~3 total calls** vs 7 today.

**Tradeoff:** ~8% of jobs that finish in &lt;4 s will wait until the first poll window (~4 s). Acceptable for bulk; mitigated for interactive via Phase 2 priority split.

### 1c. Add small per-job jitter

Randomize first poll time by **±0–1 s** (and optionally ±0.5 s on subsequent sleeps) so N concurrent jobs do not align on the same second.

### Tests (Phase 1)

- Extend `packages/python/tests/test_textract_retry.py`:
  - `SUCCEEDED` on first poll with `Blocks` → no second `get_document_*` call.
  - `SUCCEEDED` with `NextToken` → pagination continues without duplicate page-0 fetch.
- Add poll-schedule unit tests (mock time / `asyncio.sleep`) asserting call timestamps or sleep durations.
- Keep existing timeout and retry tests passing.

---

## Phase 2 — Adaptive polling from outstanding load

Use existing `_textract_in_flight` (jobs holding a Textract slot from upload through completion) as a load signal. Optionally add `_textract_polling` counter (jobs past `Start*`, not yet terminal) for finer control.

### 2a. Load factor

```text
load = _textract_in_flight / max(1, textract_max_concurrent)   # 0.0 – 1.0
```

When `textract_max_concurrent == 0` (gate disabled), treat `load = 1.0` (conservative polling).

### 2b. Scale intervals by load

Multiply Phase 1b sleep durations by a factor `f(load)`:

| Load | Multiplier (example) | Effective first poll (Phase 1b base 4 s) |
|------|----------------------|-------------------------------------------|
| 0 – 0.25 | 0.75× | ~3 s |
| 0.25 – 0.5 | 1.0× | ~4 s |
| 0.5 – 0.75 | 1.5× | ~6 s |
| 0.75 – 1.0 | 2.0× | ~8 s |

At max concurrency (bulk OCR), polls spread toward AWS-style 5–8 s spacing; at low load, stay responsive.

### 2c. Priority-aware floor

| `priority` | Minimum behavior |
|------------|------------------|
| `high` | Never exceed Phase 1b base schedule (document OCR worker, first item in flow batch). |
| `low` | Always apply load multiplier (remaining flow batch items). |

This reuses the existing `TextractPriority` passed into `run_textract`.

### 2d. Reactive backoff on throttle

Track recent `ProvisionedThroughputExceededException` in-process (e.g. sliding 10 s window). When count &gt; 0:

- Temporarily multiply all poll intervals by **2×** for **10–30 s** (shared across jobs on that process).
- Existing `_call_textract_with_retry` (stamina, 5 attempts) remains the last line of defense.

### Tests (Phase 2)

- Mock `_textract_in_flight` / gate: high load → longer sleeps (assert via mock `asyncio.sleep` args).
- `priority="high"` under high load uses shorter schedule than `priority="low"`.
- Throttle signal widens intervals for subsequent polls.

---

## Phase 3 — Optional hard cap + observability

### 3a. Global poll TPS limiter (per process)

Separate asyncio token bucket or semaphore for **`GetDocumentAnalysis` / `GetDocumentTextDetection` only** (not for `Start*`):

- Env / system setting, e.g. `TEXTRACT_POLL_MAX_TPS` default **10** per process.
- Acquire token before each poll/pagination call; block or delay if bucket empty.

Needed when many uvicorn workers each run independent adaptive schedulers (16 processes × adaptive polls can still exceed account quota).

### 3b. Logging and metrics

Add structured log fields (or counters) per job:

- `poll_count`, `total_get_calls`, `wall_secs`, `load_at_start`, `priority`
- Include `JobId` in poll logs (today only org/doc prefix — makes log analysis reliable when many jobs share one flow execution id)

### 3c. Validation script

Small script (or pytest helper) to parse docker logs like `log6.txt` and output poll-count histogram — reuse for before/after deploy comparison.

---

## Files to touch

| File | Changes |
|------|---------|
| `packages/python/analytiq_data/aws/textract.py` | Poll schedule, reuse `SUCCEEDED`, adaptive sleep, optional TPS bucket, logging |
| `packages/python/tests/test_textract_retry.py` | New cases above |
| `packages/python/tests/test_queue_timeout.py` | Adjust if sleep schedule affects timeout test timing |
| `docs/env.md` | Document new env vars if added (`TEXTRACT_POLL_*`) |
| `packages/python/analytiq_data/system/settings.py` | Optional: `textract_poll_max_tps` in system settings (Phase 3) |

---

## Rollout

1. **Deploy Phase 1** to staging; run a bulk flow OCR batch comparable to `log6` (~300+ docs).
2. Compare:
   - Count of `ProvisionedThroughputExceededException`
   - Poll-count histogram from logs (target: median **3–4** total calls vs 7)
   - End-to-end batch duration (expect similar; ±10% acceptable)
3. **Deploy Phase 2** if rate limits persist under full `textract_max_concurrent`.
4. **Phase 3** only if multiple worker processes still aggregate above AWS quota.

### Rollback

All changes isolated to `run_textract` polling; revert single file to restore prior behavior.

---

## Success criteria

| Metric | Before (log6) | Target after Phase 1+2 |
|--------|---------------|-------------------------|
| Median `GetDocumentAnalysis` calls / 1-page job | 7 | ≤ 4 |
| `ProvisionedThroughputExceededException` per 10k jobs | 370 | &lt; 50 |
| Median invoke → `SUCCEEDED` wall time | ~8.7 s | ≤ 11 s |
| OCR failures / timeouts | baseline | no increase |

---

## Open questions

1. **Confirm `SUCCEEDED` poll payload** always includes `Blocks` for our feature-type combinations (TABLES/LAYOUT/etc.) — validate with one live job in staging before relying on 1a.
2. **Account-level TPS quota** from AWS (default vs raised limit) — determines whether Phase 3 is required for 16 uvicorn × 32 concurrent jobs.
3. **Whether to lower default `textract_max_concurrent`** (32) in system settings as a complementary ops knob — out of scope for code plan but note for deploy runbook.

---

## References

- `packages/python/analytiq_data/aws/textract.py` — `run_textract`, `_textract_concurrency`, `_call_textract_with_retry`
- `log6.txt` — Jul 2026 bulk flow OCR poll analysis
- [AWS Textract async API](https://docs.aws.amazon.com/textract/latest/dg/async-analyzing-with-s3.html) — recommends ~5 s poll interval
