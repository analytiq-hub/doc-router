# Flows Code Node — v3 Plan

Extends the existing `flows.code` Python node with all execution features present
in the n8n Python code node, adapted to DocRouter conventions.

**Reference:** `../n8n/packages/@n8n/task-runner-python/` — reviewed for
patterns, not copied. Key files: `task_executor.py`, `import_validation.py`,
`config/security_config.py`.

---

## Goals

1. **Per-item execution mode** — code runs once per input item, with a single-item view.
2. **Module imports** — allow safe stdlib and optional external packages via allowlist.
3. **Full builtins** — start from Python's complete built-in set and selectively deny dangerous ones (n8n pattern), replacing the current minimal explicit allowlist.
4. **Continue-on-fail** — catch errors per-item or per-batch and emit error items instead of aborting the execution.
5. **Binary data access** — expose binary attachments (base64-encoded) inside the sandbox so user code can read and forward them.
6. **Expression-style interface** — alternative to `def run()`: top-level code with `items`/`item` and `context` globals, returning a value directly.
7. **Static data** — persistent key-value store per (flow, node) accessible from code.
8. **Richer error output** — full stack traces surfaced in node logs.

---

## Non-Goals

- No WebSocket broker / task-runner daemon (our per-execution subprocess model stays).
- No n8n-style naming (`$input`, `$node`, etc.) — we use our own neutral names.
- No LangChain tool mode.
- No change to how other node types work.

---

## Current State (baseline)

| Aspect | Current |
|---|---|
| Interface | `def run(items: list[dict], context: dict) -> list[dict]:` |
| Execution mode | All-items only |
| Imports | None — no `__import__` in builtins |
| Builtins | ~20 explicit safe functions |
| Binary in sandbox | Not exposed — binary is passed through from input but user code cannot read it |
| Continue-on-fail | No — exceptions abort the execution |
| Static data | No |
| Error details | Error message only (no stack trace in logs) |

---

## User-Facing Interface (v3)

### Execution modes

New node parameter `mode` (default: `"all_items"`):

| Value | Behaviour |
|---|---|
| `"all_items"` | Code runs once with all input items (current behaviour). |
| `"per_item"` | Runner loops over items; code runs once per item. |

---

### Code interface — two styles

#### Style A — function style (existing; extended to support `per_item`)

```python
# all_items mode — unchanged from today
def run(items: list[dict], context: dict) -> list[dict]:
    return [{"json": {**it["json"], "extra": 1}} for it in items]

# per_item mode — new; return None to drop the item
def run(item: dict, context: dict) -> dict | None:
    if item["json"].get("skip"):
        return None
    return {"json": item["json"]}
```

#### Style B — expression style (new)

If the user's code does not define a callable `run`, the runner wraps it in
`def _user_fn(): ...` and captures the return value. The globals `items`/`item`
and `context` are injected.

```python
# all_items — 'items' and 'context' are globals
return [{"json": {**it["json"], "doubled": it["json"]["n"] * 2}} for it in items]

# per_item — 'item' and 'context' are globals
if item["json"]["score"] < 0:
    return None
return {"json": item["json"]}
```

---

### Item dict shape (in sandbox)

Every item passed to user code has the same shape in both styles and modes:

```python
{
    "json": { ... },           # JSON payload — same as today
    "binary": {                # named binary attachments
        "pdf": {
            "mime_type": "application/pdf",
            "file_name": "invoice.pdf",
            "data": "<base64-string>",   # None when attachment exceeds 4 MB
            "file_size": 42000,
        },
    },
}
```

`meta` and `paired_item` are engine-internal fields; they are not sent to the sandbox.

---

### Return value shape

```python
# Minimal — json only (both modes)
{"json": {"key": "value"}}

# With binary forwarded
{
    "json": {"key": "value"},
    "binary": {
        "pdf": {
            "mime_type": "application/pdf",
            "file_name": "processed.pdf",
            "data": "<base64-string>",
        }
    }
}

# per_item only: return None to drop this item from the output
None
```

Legacy flat dict without a `"json"` key is still accepted as before:
`{"key": "value"}` is treated as `{"json": {"key": "value"}}`.

---

### Module imports

A custom `__import__` shim validates every import against an allowlist.

**Default stdlib allowlist** (built into the runner; cannot be removed by node config):

```
base64, collections, copy, datetime, decimal, functools,
hashlib, itertools, json, math, operator, random, re,
string, textwrap, time, urllib.parse, uuid
```

**Extra modules** — optional node parameter `allowed_modules` (list of strings):

```python
import pandas   # allowed only if "pandas" is in node's allowed_modules
import os       # always denied (not stdlib-allowlisted, not in external_allow)
```

**Server-side env vars** control the global defaults:

| Variable | Default | Meaning |
|---|---|---|
| `DOCROUTER_RUNNERS_STDLIB_ALLOW` | comma-separated list above | Overrides default stdlib allowlist |
| `DOCROUTER_RUNNERS_EXTERNAL_ALLOW` | *(empty)* | Comma-separated installed packages (or `*`) |
| `DOCROUTER_RUNNERS_BUILTINS_DENY` | *(deny list below)* | Comma-separated builtins to remove |

---

### Full builtins (deny-list approach)

Start from Python's complete `builtins.__dict__` and remove:

```
open, __loader__, __spec__
```

Everything else — `set`, `frozenset`, `isinstance`, `issubclass`, `Exception`,
`bytes`, `bytearray`, `map`, `filter`, `iter`, `next`, `repr`, `round`, `hash`,
`id`, `chr`, `ord`, `bin`, `hex`, `oct`, `format`, `vars`, `dir`, `getattr`,
`hasattr`, `callable`, `staticmethod`, `classmethod`, `property`, `super` —
is available.

`exec`, `eval`, `compile` are kept (they run inside the already-isolated subprocess;
removing them breaks metaprogramming patterns that are harmless in this context).

`__import__` is replaced by the safe import shim.

---

### Context dict

Same keys as today, passed as argument (function style) or global (expression style).
One new key — `static_data` — is added (see §Static data).

```python
{
    "trigger": ...,
    "node_id": "...",
    "mode": "manual" | "trigger" | ...,
    "organization_id": "...",
    "execution_id": "...",
    "flow_id": "...",
    "flow_revid": "...",
    "start_time": ...,
    "execution_time": ...,
    "static_data": { ... },   # NEW — mutable; mutations are persisted
}
```

---

### Static data

A persistent `dict` for this (flow, node) pair. The node loads it before execution
and saves it after if the value changed.

```python
# Expression style — 'context' is a global; 'context["static_data"]' is mutable
sd = context["static_data"]
sd["count"] = sd.get("count", 0) + len(items)
return items

# Function style
def run(items, context):
    sd = context["static_data"]
    sd["seen"] = sd.get("seen", 0) + len(items)
    return items
```

Any mutation the user makes to `context["static_data"]` (or the `static_data` alias
injected as a global in expression style) is serialised from the subprocess response
and saved by `save_node_static_data()`.

---

### Continue-on-fail

New node parameter `continue_on_fail` (bool, default `False`).

- **`all_items` mode**: wraps the whole execution in try/except; on error emits one
  item `{"json": {"error": "<message>", "stack": "<traceback>"}}` and continues.
- **`per_item` mode**: wraps each item's execution individually; failed items become
  error items, successful items are still emitted.

---

## Architecture

### Subprocess protocol (JSON, backward-incompatible with v2 — internal detail)

```jsonc
// request (stdin)
{
    "code": "...",
    "mode": "all_items" | "per_item",
    "items": [
        {"json": {}, "binary": {"pdf": {"mime_type": "...", "data": "...", ...}}},
        ...
    ],
    "context": { ... },                    // excludes static_data
    "static_data": { ... },
    "allowed_modules": ["re", "pandas"],   // merged with server defaults
    "continue_on_fail": false
}

// success (stdout)
{
    "ok": true,
    "items": [{"json": {}, "binary": {}}, ...],
    "logs": ["line 1\n", ...],
    "static_data": { ... }                 // mutated dict returned
}

// error (stdout)
{
    "ok": false,
    "error": {"message": "...", "stack": "..."},
    "logs": ["..."]
}
```

---

### `code_runner.py` — rewrite

Replace the embedded `_RUNNER_CODE` string with a structured runner script (still
injected via `sys.executable -I -S -c <content>`, so subprocess isolation is
unchanged). The content is now generated by a helper rather than written as a raw
string so it is lintable and testable independently.

**Runner responsibilities:**

1. Read JSON payload from stdin.
2. Build safe builtins: `dict(__builtins__)`, remove deny list, replace
   `__import__` with the allowlist shim.
3. Sanitize `sys.modules`: remove modules not in the allowlist.
4. Determine interface style: if code defines `run`, use function style; otherwise
   wrap in `def _user_fn():` and capture `_user_output = _user_fn()`.
5. Dispatch by mode:
   - `all_items`: exec once, inject `items` + `context` globals, call or capture.
   - `per_item`: exec per item, inject `item` + `context` globals, collect results.
6. Normalize output (see §Output normalization).
7. Handle continue-on-fail per mode.
8. Serialize response to stdout.

**Output normalization (per output item):**

| What user returned | Normalized |
|---|---|
| `{"json": {...}}` | kept |
| `{"json": {...}, "binary": {...}}` | kept; `binary` values decoded from base64 by parent |
| flat dict without `"json"` key | wrapped: `{"json": flat_dict}` |
| `None` (per_item only) | item dropped |

**Binary serialization (parent side, before sending to subprocess):**

For each `FlowItem` in `in_items`, encode binary attachments:

```python
{
    "mime_type": ref.mime_type,
    "file_name": ref.file_name,
    "data": base64.b64encode(data).decode() if len(data) <= 4_194_304 else None,
    "file_size": ref.file_size,
}
```

Data comes from `await get_binary_stream(ref, analytiq_client)`. Attachments larger
than 4 MiB are included as metadata-only (`data: null`) — user code can still see
`mime_type`, `file_name`, `file_size`.

**Binary deserialization (parent side, after subprocess returns):**

Output `binary` dicts are decoded from base64 back to `BinaryRef(data=bytes(...))`.
These are attached to the output `FlowItem.binary`.

---

### `run_python_code()` — updated signature

```python
async def run_python_code(
    *,
    code: str,
    items: list[dict[str, Any]],        # already serialized (json + binary as base64)
    context: dict[str, Any],
    static_data: dict[str, Any] | None = None,
    mode: Literal["all_items", "per_item"] = "all_items",
    allowed_modules: list[str] | None = None,
    continue_on_fail: bool = False,
    timeout_seconds: float = 2.0,
) -> tuple[list[dict[str, Any]], list[str], dict[str, Any]]:
    """Returns (out_items_raw, logs, mutated_static_data)."""
```

---

### `nodes/code.py` — changes

1. Add `mode`, `continue_on_fail`, `allowed_modules` to `parameter_schema`.
2. Before calling runner:
   - For each `FlowItem` in `inputs[0]`: fetch binary data via `get_binary_stream`,
     base64-encode, build the sandbox item dict.
   - Load `static_data = await load_node_static_data(db, flow_id, node_id)`.
3. Call `run_python_code(...)` with new params.
4. After runner returns:
   - Decode `binary` dicts (base64 → `BinaryRef`).
   - Reconstruct `FlowItem` list with json + binary.
   - If `static_data` changed: `await save_node_static_data(db, flow_id, node_id, sd)`.
   - Surface `stack` in `node_logs` alongside print lines on error.

---

### Node parameter schema (v3)

```python
parameter_schema = {
    "type": "object",
    "properties": {
        "python_code": {
            "type": "string",
            "minLength": 1,
            "default": "def run(items, context):\n    return items\n",
            "description": (
                "Must define def run(items, context) -> list or "
                "def run(item, context) -> dict|None (per_item), "
                "or use expression style (return directly)."
            ),
            "x-ui-widget": "code",
            "x-ui-group": "Code",
        },
        "mode": {
            "type": "string",
            "enum": ["all_items", "per_item"],
            "default": "all_items",
            "description": "Run code once for all items, or once per item.",
            "x-ui-group": "Options",
        },
        "continue_on_fail": {
            "type": "boolean",
            "default": False,
            "description": "On error, emit an error item instead of aborting.",
            "x-ui-group": "Options",
        },
        "allowed_modules": {
            "type": "array",
            "items": {"type": "string"},
            "default": [],
            "description": (
                "Extra stdlib or installed packages to allow beyond the built-in "
                "safe list. Example: [\"pandas\", \"numpy\"]."
            ),
            "x-ui-group": "Advanced",
        },
        "timeout_seconds": {
            "type": "number",
            "default": 2,
            "minimum": 0.0001,
            "maximum": 30,
            "description": "Subprocess wall-clock limit in seconds (max 30).",
            "x-ui-group": "Options",
        },
    },
    "required": ["python_code"],
    "additionalProperties": False,
}
```

---

## Default code templates (by mode)

### `all_items` — function style (default shown in editor)
```python
def run(items, context):
    return items
```

### `all_items` — expression style
```python
return [{"json": {**it["json"], "extra": True}} for it in items]
```

### `per_item` — function style
```python
def run(item, context):
    return {"json": item["json"]}
```

### `per_item` — expression style
```python
return {"json": item["json"]}
```

---

## Security model summary

| Control | Current | v3 |
|---|---|---|
| Process boundary | subprocess (`-I -S`) | same |
| Imports | none allowed | allowlist via custom `__import__` shim |
| Builtins | ~20 explicit allow | full Python builtins minus deny list |
| File I/O | blocked (no `open`) | blocked (`open` in deny list) |
| Network | blocked | blocked |
| Environment | PATH only | same |
| `sys.modules` | inherited | sanitized to allowlist before exec |
| Timeout | per-node 0–30 s | same |

---

## Implementation order

### Step 1 — Runner rewrite + full builtins + module imports

**Files touched:** `code_runner.py`

- Rewrite `_RUNNER_CODE` as a properly structured multi-section script.
- Replace explicit allow-list with deny-list builtins + safe `__import__` shim.
- Add `sys.modules` sanitization.
- Support `allowed_modules` field in request payload.
- Both dispatch styles (function + expression).
- Update `run_python_code()` signature (`mode`, `allowed_modules`, `continue_on_fail`,
  `static_data` in; `static_data` out).
- Update existing tests; add new tests for imports, builtins, expression style.

### Step 2 — Per-item mode

**Files touched:** `code_runner.py`, `nodes/code.py`

- Add `per_item` loop in runner (`_item` global per iteration, collect results).
- Add `mode` parameter to `FlowsCodeNode`.
- Default code snippet switches to per-item template when mode is `per_item`.
- Tests: per-item normal, `None` filtering, item count, continue-on-fail per-item.

### Step 3 — Binary data access

**Files touched:** `nodes/code.py`, `code_runner.py`

- Parent: fetch binary data (`get_binary_stream`), base64-encode, add to sandbox
  item dict before sending.
- Runner: pass `binary` dict through to user code.
- Parent: decode base64 on output items, build `BinaryRef`.
- Tests: binary round-trip (in → sandbox visible → out), oversized attachment
  (`data: null` but metadata present), binary pass-through unchanged.

### Step 4 — Static data

**Files touched:** `nodes/code.py`, `code_runner.py`

- Node: load via `load_node_static_data` before execution; save after if changed.
- Runner: inject `static_data` into globals and `context["static_data"]`; return
  mutated value in response.
- Tests: counter increments across executions (mock DB), empty initial value.

### Step 5 — Continue-on-fail

**Files touched:** `code_runner.py`, `nodes/code.py`

- Runner: wrap execution in try/except per mode; emit error items on failure.
- Node: add `continue_on_fail` parameter; pass to runner.
- Tests: error in all-items emits one error item; error in per-item leaves other
  items intact.

### Step 6 — Frontend

**Files touched:** `packages/typescript/frontend/src/components/flows/`

- Add `mode` dropdown (`All Items` / `Per Item`) to Code node config panel.
- Add `Continue on fail` toggle.
- Add `Allowed modules` multi-line text field in Advanced section.
- When mode changes, offer to swap default code template.

### Step 7 — Tests + docs

- Extend `tests/flows/test_code_runner_logs.py` (existing — must not regress).
- Add:
  - `test_code_runner_imports.py` — allowed, denied, expression-style
  - `test_code_runner_per_item.py` — normal, None-filter, continue-on-fail
  - `test_code_runner_binary.py` — round-trip, oversized, pass-through
  - `test_code_runner_static_data.py` — persistence, initial empty

---

## Backward compatibility

- Existing flows using `def run(items, context)` in all-items mode continue to work
  unchanged — `mode` defaults to `"all_items"`, function style is detected first.
- The `context` dict gains `static_data` but existing code that ignores unknown keys
  is unaffected.
- Binary that was previously passed through by index copy continues to be passed
  through (no `binary` in user output → parent copies from input by position, same
  as today for equal-length outputs).
