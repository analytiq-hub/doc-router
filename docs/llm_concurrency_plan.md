# LLM concurrency: per-model in-flight limits (per pod)

Plan to add **per-model concurrency gates** for LLM API calls, mirroring the Textract
`_textract_concurrency` pattern but **without priority tiers** — a single FIFO-style
slot pool per litellm model string.

**Primary files:**

- `packages/python/analytiq_data/llm/concurrency.py` (new)
- `packages/python/analytiq_data/llm/llm.py` (`_litellm_acompletion_with_retry`, `agent_completion_stream`, `run_llm_chat`)
- `packages/python/analytiq_data/llm/embedding.py` (`aembedding`)
- `packages/python/analytiq_data/system/settings.py`

**Related docs:**

- [Flow rerun storm](./feature.md) — bulk flow + document workers share one process pool
- [Textract polling plan](./textract_polling_plan.md) — reference concurrency gate design (`_textract_concurrency`)

**Implementation order:** Phase 1 (gate + settings + tests) → Phase 2 (admin UI) → Phase 3 (observability, optional).

---

## Problem

Today LLM throughput is controlled only indirectly:

| Knob | What it does | Gap |
|------|--------------|-----|
| `n_llm_workers` | Number of `llm` queue consumers per pod | Does not cap in-flight calls to a **specific model** |
| Stamina retries on 429/503 | Reactive backoff after provider rejects | Does not prevent self-inflicted overload |
| `n_flow_run_workers` | Concurrent flow executions | Flow LLM nodes can fan out many parallel calls to the same model |

All LLM entry points ultimately call `litellm.acompletion` / `litellm.aembedding` with
**no preventive gate**. Under bulk document LLM, bulk flow `docrouter.llm_run`, KB chat,
and agent loops, many coroutines on one worker process can hammer the same model until
the provider rate-limits.

Unlike Textract (one shared AWS job pool), **each litellm model has different provider
capacity** — `gpt-4o-mini`, `vertex_ai/gemini-2.5-flash`, and Bedrock Claude IDs need
independent limits.

Textract already solves the analogous problem with a per-process `asyncio.Condition` gate
(`packages/python/analytiq_data/aws/textract.py`). This plan applies the same mechanism
per model, without high/low priority.

---

## Default policy

**All LLM models default to limit `0` (unlimited — gate disabled).**

- Fresh installs, seeded `system_settings`, and models not listed in config: **no concurrency cap**.
- A model is gated **only** when an admin explicitly sets a **positive** limit for that
  litellm model string in `llm_max_concurrent_by_model`.
- Setting a model's limit back to `0` (or removing it from the map) restores unlimited behavior.
- There is no global default above zero — unlike Textract (`textract_max_concurrent: 32`), LLM
  limits are entirely opt-in per model.

Deploying Phase 1 with an empty map therefore changes **nothing** in production until an
admin configures specific models.

---

## Goals

1. **Cap in-flight LLM calls per model per process** — opt-in only; default unlimited (`0`).
2. **Single priority** — no high/low tiers; callers wait FIFO when at capacity.
3. **Slot covers the full call** — acquire before the litellm request, release after
   response (including streaming completion).
4. **Deployment-wide config** in `system_settings` (same ops model as `textract_max_concurrent`).
5. **No behavior change** on deploy — all models stay at `0` until explicitly configured.
6. **Stay per-pod** — no Redis or cross-process coordination in v1.

---

## Non-goals

- High/low priority scheduling (unlike Textract).
- Cross-pod coordinated rate limiting.
- Token-per-minute (TPM) or requests-per-minute (RPM) token buckets — in-flight job count only.
- Per-organization limits (deployment-wide only).
- Provider-level shared pools (e.g. all Bedrock models share one counter) — per litellm model string only.
- Changing `n_llm_workers` defaults or stamina retry policy.

---

## Current behavior (baseline)

### Call paths (no gate today)

| Path | Entry | litellm call |
|------|-------|--------------|
| Document LLM worker | `run_llm` | `_litellm_acompletion_with_retry` |
| Flow `docrouter.llm_run` | `agent_completion` | `_litellm_acompletion_with_retry` |
| Flow / docrouter agent loop | `agent_completion` / `agent_completion_stream` | `_litellm_acompletion_with_retry` or direct `litellm.acompletion` |
| KB chat | `_litellm_acompletion_with_retry` | same |
| LLM OCR | `_litellm_acompletion_with_retry` | same |
| Interactive chat API | `run_llm_chat` | **direct** `litellm.acompletion` (bypasses wrapper) |
| Embeddings (KB index, search) | `aembedding` | direct `litellm.aembedding` |

### Existing overload handling

`llm.py` retries 429/503/overloaded errors via stamina (`_LLM_OVERLOADED_RETRY_PATTERNS`).
This is reactive; a concurrency gate is preventive.

### Model configuration today

- **Enable/disable:** `llm_providers.litellm_models_enabled` (per provider document).
- **Prompt model choice:** `prompt_revisions.model`.
- **No concurrency fields** anywhere in Mongo.

---

## Target behavior

### Gate semantics

For each litellm model string (e.g. `gpt-4o-mini`, `vertex_ai/gemini-2.5-flash`):

1. Look up `max_concurrent` from `system_settings`.
2. If `max_concurrent <= 0` → **gate disabled** for that model (unlimited).
3. Otherwise → acquire a slot on a model-specific `asyncio.Condition`:
   - Wait while `in_flight >= max_concurrent`.
   - Increment `in_flight`, run the litellm call, decrement in `finally`, `notify_all`.

**Scope:** per Python process (worker pod, each uvicorn worker). Independent pools across pods.

**Slot duration:** from gate acquire through litellm response completion. For streaming,
hold the slot until the stream finishes (same as Textract holding through polling).

### Configuration

Store in the existing `system_settings` singleton (`_id: "deployment"`):

```json
{
  "_id": "deployment",
  "textract_max_concurrent": 32,
  "llm_max_concurrent_by_model": {}
}
```

After an admin opts in for specific models:

```json
{
  "llm_max_concurrent_by_model": {
    "gpt-4o-mini": 16,
    "vertex_ai/gemini-2.5-flash": 8
  }
}
```

| Field | Type | Meaning |
|-------|------|---------|
| `llm_max_concurrent_by_model` | `dict[str, int]` | Per-model limit. Key = litellm model string. Omitted models = `0`. |

**Lookup:** `limit = map.get(model, 0)` — missing key or explicit `0` → unlimited.

**Clamp:** `0` – `1024` (same range as Textract). Values `<= 0` disable the gate.

**Bootstrap / seed:** `llm_max_concurrent_by_model: {}` (empty dict). No env var overrides
for v1 — do not introduce a global LLM default above zero.

**Cache:** mirror Textract — load from Mongo every 25 gate acquisitions; invalidate on PATCH.

---

## Phase 1 — Core gate + settings + tests

### 1a. New module `llm/concurrency.py`

```python
@asynccontextmanager
async def llm_concurrency(model: str) -> AsyncIterator[None]:
    """Acquire an in-flight slot for ``model``; no-op when limit <= 0."""
```

Implementation sketch (mirror `_textract_concurrency` without priority):

- Module-level `_gates: dict[str, _ModelGate]` (lazy-created per model string).
- Each `_ModelGate` holds `_in_flight: int` and `_gate: asyncio.Condition`.
- `get_llm_max_concurrent_for_model(model)` from `system.settings`.

### 1b. Settings (`system/settings.py`)

Add:

- `LLM_MAX_CONCURRENT_MIN = 0`, `LLM_MAX_CONCURRENT_MAX = 1024`
- `LLM_MAX_CONCURRENT_REFRESH_EVERY = 25`
- `clamp_llm_max_concurrent(value: int) -> int`
- `load_llm_max_concurrent_map_from_db() -> dict[str, int]`
- `get_llm_max_concurrent_for_model(model: str) -> int`
- `invalidate_llm_max_concurrent_cache()` (called from `update_system_settings`)
- Include `llm_max_concurrent_by_model: {}` in `default_system_settings()`, `get_system_settings_document()`, `update_system_settings()`

Validate map keys: non-empty strings. Validate values: clamped ints.

### 1c. Wrap litellm entry points

| Function | Change |
|----------|--------|
| `_litellm_acompletion_with_retry` | `async with llm_concurrency(model):` around `litellm.acompletion` |
| `agent_completion_stream` | `async with llm_concurrency(model):` around entire stream loop |
| `aembedding` | `async with llm_concurrency(model):` around `litellm.aembedding` |
| `run_llm_chat` | `async with llm_concurrency(request.model):` around each `litellm.acompletion` call |

`agent_completion` and `run_llm` are covered transitively via `_litellm_acompletion_with_retry`.

**Do not** gate non-LLM code paths. Embeddings use the same model-keyed gate (same provider quota).

### 1d. API (`app/routes/system_settings.py`)

Extend `SystemSettingsResponse` / `SystemSettingsUpdate`:

```python
llm_max_concurrent_by_model: dict[str, int] = {}  # default empty — all models unlimited
```

PATCH: optional `llm_max_concurrent_by_model` key replaces the stored map (full replace from
UI; API may support per-key merge — see open questions). Omitting the field on PATCH leaves
the map unchanged.

### 1e. Tests

New `packages/python/tests/test_llm_concurrency.py` (mirror `test_textract_retry.py` concurrency tests):

- Limit 1 on model A: two concurrent calls to A serialize; max in-flight = 1.
- Model A limit 1, model B limit 1: A and B run in parallel (independent gates).
- Limit 0: gate bypassed, no waiting.
- Map refresh: PATCH `system_settings` → new limit picked up within refresh window.
- `clamp_llm_max_concurrent` bounds.

Extend `test_system_settings.py` for new fields on GET/PATCH/seed (seeded doc has `{}` map).

---

## Phase 2 — Admin UI

### 2a. System Settings page

No global LLM concurrency field (all models default to `0`). Optional link/note pointing
admins to the LLM Models page for per-model limits.

### 2b. LLM Models table (`LLMModelsConfig.tsx`)

Add column **Max concurrent** per chat model row:

- Default display: empty or `0` (unlimited) for every model.
- Positive integer → set `llm_max_concurrent_by_model[litellm_model]`.
- Clear / `0` → remove key from map on save (back to unlimited).
- On blur/save → `PATCH /v0/account/system_settings` with updated map.
- Show only **enabled** models (same rows as today).

### 2c. SDK types

Extend `SystemSettings` / `SystemSettingsUpdate` in `packages/typescript/sdk/src/types/index.ts`.

---

## Phase 3 — Observability (optional)

- Structured log on gate acquire when wait > 0: `model`, `wait_secs`, `in_flight`, `limit`.
- Optional counter metrics per model: `llm_gate_waits`, `llm_in_flight` (if metrics infra exists).

No Phase 3 required for initial ship.

---

## Suggested limits when opting in (ops tuning guide)

Only set a positive limit on models that are actually hitting 429s or overloading a pod.
All others stay at `0`.

| Tier | Examples | Suggested per-pod limit (if needed) |
|------|----------|-------------------------------------|
| Fast / economy | `gpt-4o-mini`, `gemini-*-flash*`, haiku | 8–16 |
| Mid | `gpt-4o`, sonnet | 4–8 |
| Flagship | opus, `gpt-5*`, pro | 2–4 |
| Embeddings | `text-embedding-3-small` | 4–8 |
| Everything else | not in map | **0 (leave unlimited)** |

Tune from 429 rate and p95 queue wait. Gate prevents storms; stamina retries remain the last line of defense.

---

## Rollout

1. **Deploy Phase 1** with empty map (all unlimited) — no behavior change.
2. Set limits for the 2–3 models under heaviest bulk load (from logs / prompts).
3. **Deploy Phase 2** UI for ongoing ops tuning.
4. Monitor 429 count and end-to-end batch time; adjust per model.

### Validation

- Run bulk flow `docrouter.llm_run` on 50+ items with `llm_max_concurrent_by_model[model]=2`:
  verify at most 2 in-flight litellm calls per process (mock or log assertion).
- Confirm document LLM worker and flow LLM share the same gate for the same model string.
- Confirm streaming chat holds slot until stream ends.

---

## Success criteria

| Metric | Target |
|--------|--------|
| Self-inflicted 429s under bulk LLM | Meaningful reduction when limits are set |
| Interactive single-doc LLM latency | No regression when model is not at capacity |
| Bulk flow end-to-end time | Slight increase acceptable; no timeout storms |
| Config change propagation | New limit effective within 25 gate calls or immediately after cache invalidation |

---

## File checklist

| File | Change |
|------|--------|
| `analytiq_data/llm/concurrency.py` | **New** — gate implementation |
| `analytiq_data/llm/__init__.py` | Export if needed for tests |
| `analytiq_data/system/settings.py` | Map + default fields, cache, clamp |
| `analytiq_data/llm/llm.py` | Wrap completion + stream + chat paths |
| `analytiq_data/llm/embedding.py` | Wrap `aembedding` |
| `app/routes/system_settings.py` | API schema |
| `tests/test_llm_concurrency.py` | **New** |
| `tests/test_system_settings.py` | Extend |
| `sdk/src/types/index.ts` | Types |
| `frontend/.../SystemSettingsManager.tsx` | Optional link to LLM Models limits (Phase 2) |
| `frontend/.../LLMModelsConfig.tsx` | Per-model column (Phase 2) |

---

## Open questions (defaults for v1)

| Question | Decision |
|----------|----------|
| Default limit for every model | **`0` (unlimited)** — fixed; no global override field |
| Unlisted / missing map entry | `0` (unlimited) |
| Embeddings share chat gate for same model string? | Yes |
| PATCH replaces entire `llm_max_concurrent_by_model` dict? | **Full replace** from UI; API PATCH may merge keys if partial body sent |
| Gate key normalization | Use litellm model string exactly as passed to `litellm.acompletion` (no alias resolution) |
