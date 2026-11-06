# `flows.code` v2 — Implementation Plan

This document plans enhancements to the **Code (Python)** flow node
(`flows.code`): full item I/O (`json` + `binary`), parent-side helper RPCs,
and a hardened execution model inspired by n8n’s Python task runner (static
analysis, import allowlists, denied builtins).

**Motivation:** Today `flows.code` passes only `item.json` into the sandbox and
blindly copies binary from `in_items[min(idx, len-1)]` on output. That blocks
patient PDF assembly, pass-through of per-page binaries, and any workflow where
user code must reference blobs by `storage_id`. See prior analysis on surgery-
schedule flows (Code groups pages correctly but Upload receives page 0 only).

**Reference (behavior only — do not copy naming):** n8n
`packages/@n8n/task-runner-python/` (`task_executor.py`, `task_analyzer.py`,
`import_validation.py`, RPC helpers in `packages/@n8n/task-runner/src/`).

---

## 1. Goals

1. **Item-shaped I/O** — `run(items, context)` receives and may return items with
  `json`, `binary`, and optional `meta` / `paired_item`.
2. **Binary by reference** — sandbox sees `storage_id` metadata, not raw bytes;
  parent resolves blobs and attaches `BinaryRef` on output.
3. **Helper RPCs** — safe, audited operations in the parent process (read blob,
  store blob, merge PDFs).
4. **Security hardening** — AST static analysis before execution, allowlisted
  imports, denied builtins, subprocess isolation retained.
5. **Backward compatibility** — existing snippets that return plain dicts (JSON
  payloads) keep working.

### Non-goals (v1 of this plan)

- Long-lived Python task runner process (keep subprocess-per-invocation for now).
- Arbitrary network/filesystem from user code (no `open`, no raw HTTP in sandbox).
- Pyodide / in-browser Python execution.
- Changing `context` shape beyond documenting it (already sufficient for upstream
JSON via `context["nodes"]`).

---

## 2. Current state


| Area                         | Today                                                                    |
| ---------------------------- | ------------------------------------------------------------------------ |
| Input to sandbox             | `[it.json for it in in_items]`                                           |
| Output from sandbox          | `list[dict]` → parent copies `in_items[idx].binary`                      |
| `context`                    | `trigger`, `node_id`, `mode`, `nodes` (JSON-only), execution ids, timing |
| Security                     | `-I -S` subprocess, tiny builtins, **no imports**                        |
| Helpers                      | None                                                                     |
| Binary in `context["nodes"]` | Stripped (`materialize_node_data`)                                       |


**Key files:**

- `packages/python/analytiq_data/flows/nodes/code.py` — executor
- `packages/python/analytiq_data/flows/code_runner.py` — inline subprocess runner
- `packages/python/analytiq_data/flows/expressions.py` — `_materialize_item`,
`_materialize_binary` (reuse for item serialization)

---

## 3. Target contract

### 3.1 `run(items, context) -> list[item]`

Each **input** item (v2):

```python
{
  "json": { ... },
  "binary": {
    "pdf": {
      "mime_type": "application/pdf",
      "file_name": "page_0.pdf",
      "storage_id": "flow_blobs:exec/node/0/pdf",
      "file_size": 2014,
      "data": None,           # always omitted in sandbox payload
    }
  },
  "meta": { ... },            # optional; may be omitted from sandbox if unused
  "paired_item": 0 | [0, 1] | None,
}
```

Each **output** item from `run()` may be:


| Form                                          | Normalized to                                             |
| --------------------------------------------- | --------------------------------------------------------- |
| Plain `dict` (legacy)                         | `{ "json": dict }` + binary from legacy pass-through rule |
| `{ "json": {...} }`                           | item with empty or inherited binary                       |
| `{ "json": {...}, "binary": {...} }`          | full item; binary refs resolved in parent                 |
| `{ "json": {...}, "_binary_actions": {...} }` | parent executes actions, strips key                       |


Reserved keys (stripped before persisting `item.json`):

- `_binary` — declarative binary attachment (see §3.3)
- `_binary_actions` — alias / synonym (pick one in implementation)

### 3.2 Backward compatibility


| Legacy behavior                           | v2 behavior                                                                       |
| ----------------------------------------- | --------------------------------------------------------------------------------- |
| `return items` where items are flat dicts | Treat as `json` only (unchanged)                                                  |
| Output count ≠ input count                | Binary: use `_binary` / helpers, not index copy                                   |
| Output count = input count                | Default pass-through: copy `binary` from same index if output has no `binary` key |


**Deprecation (soft):** index-based binary copy when fan-in changes item count
remains as fallback for one release; log/debug when used.

### 3.3 Declarative binary output (`_binary`)

User code returns JSON-only hints; **parent executes** blob operations:

```python
def run(items, context):
    out = []
    for p in group_patients(items):
        out.append({
            "json": {"mrn": p["mrn"], "page_idx": p["page_idx"]},
            "_binary": {
                "pdf": {
                    "op": "merge_pages",
                    "page_indices": p["page_idx"],
                    # optional: "source_node_id": "..."  — else default param
                }
            },
        })
    return out
```

**Ops (v1):**


| `op`                | Args                                       | Parent behavior                                                 |
| ------------------- | ------------------------------------------ | --------------------------------------------------------------- |
| `copy_input`        | `input_item_index`, `property`             | Copy binary ref from input item                                 |
| `copy_upstream`     | `source_node_id`, `item_index`, `property` | From `run_data` lane 0                                          |
| `merge_pages`       | `page_indices`, optional `source_node_id`  | Load per-page PDFs, PyMuPDF merge, `save_execution_binary_blob` |
| `merge_storage_ids` | `storage_ids: string[]`                    | Merge blobs by id (order preserved)                             |
| `omit`              | —                                          | No binary on this output item                                   |


Node parameter `default_pages_source_node_id` avoids hardcoding UUIDs in snippets.

---

## 4. Helper functions (parent RPC)

Pattern: sandbox calls `helpers.<name>(...)` → JSON-RPC to parent → result
returned to subprocess (same idea as n8n `EXPOSED_RPC_METHODS`).

### 4.1 Exposed helpers (v1)


| Helper                                                         | Purpose                                      |
| -------------------------------------------------------------- | -------------------------------------------- |
| `helpers.get_binary_bytes(storage_id)`                         | Read blob bytes (size cap enforced)          |
| `helpers.prepare_binary(blob_b64, file_name, mime_type)`       | Store new blob, return materialized ref dict |
| `helpers.merge_pdf_storage_ids(storage_ids)`                   | Merge PDFs, return new ref dict              |
| `helpers.merge_pdf_page_indices(source_node_id, page_indices)` | Convenience wrapper                          |


**Not exposed:** raw Mongo/GridFS paths, arbitrary HTTP, `open()`, env secrets.

### 4.2 Implementation sketch

```
packages/python/analytiq_data/flows/
  code_runner/
    __init__.py
    subprocess_runner.py    # protocol, spawn, timeout
    security_config.py      # env → allowlists
    task_analyzer.py        # AST visitor
    import_validation.py
    helpers_rpc.py          # parent-side handlers
    item_codec.py           # FlowItem ↔ sandbox dict
```

Parent process (`FlowsCodeNode.execute`):

1. Serialize input items via `item_codec.materialize_items_for_sandbox(in_items)`.
2. Run `task_analyzer.validate(code)` — fail fast before subprocess.
3. Start subprocess with code + items + context + `execution_id` for RPC correlation.
4. On RPC request from child: dispatch `helpers_rpc.handle(...)` with
  `ExecutionContext` (enforces execution-scoped `storage_id` access).
5. Decode output items → resolve `_binary` / `binary` refs → `FlowItem` list.

**Size limits:**

- Max stdin/stdout payload (configurable, default 32 MiB).
- Max single blob read in helper (default 64 MiB).
- Max merged PDF output (default 128 MiB).

---

## 5. Security model

### 5.1 Layers (defense in depth)

1. **Static analysis** (`task_analyzer`) — reject dangerous AST before run.
2. **Subprocess** — `-I -S`, minimal env (unchanged).
3. **Filtered builtins** — deny list + safe `__import__` shim.
4. **Import allowlists** — stdlib + external package names from env.
5. **RPC-only I/O** — no direct blob/env/network from sandbox.
6. **Execution-scoped blob access** — RPC validates `storage_id` belongs to
  current execution (or allowed pin prefix).

### 5.2 Static analysis (`task_analyzer`)

Port/adapt patterns from n8n `SecurityValidator`:

- Block `import` / `from ... import` of disallowed modules (pre-scan).
- Block access to `__builtins__`, `globals`, `locals`, `__loader__`, etc.
- Block dangerous attributes (`__globals__`, `__subclasses__`, `gi_frame`, …).
- Block dynamic `__import__(...)` except through safe shim.
- Block f-string / format field tricks reaching blocked attrs.
- Cache validation results by code hash (LRU, cap 500).

Run analyzer in **parent** (has config); pass only “validated” code to subprocess.

### 5.3 Environment variables

Document in `docs/env.md` and `.env.example.*`:


| Variable                                | Default                                                                                                                                       | Description                                                     |
| --------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------- |
| `DOCROUTER_RUNNERS_STDLIB_ALLOW`        | `json,base64,hashlib,re,math,datetime,collections,itertools,functools,typing`                                                                 | Comma-separated stdlib top-level names, or `*`                  |
| `DOCROUTER_RUNNERS_EXTERNAL_ALLOW`      | *(empty)*                                                                                                                                     | Comma-separated PyPI top-level names allowed in sandbox, or `*` |
| `DOCROUTER_RUNNERS_BUILTINS_DENY`       | `eval,exec,compile,open,input,breakpoint,getattr,object,type,vars,setattr,delattr,hasattr,dir,memoryview,__build_class__,globals,locals,help` | Denied builtin names                                            |
| `DOCROUTER_RUNNERS_MAX_PAYLOAD_BYTES`   | `33554432`                                                                                                                                    | Max JSON stdin/stdout per invocation                            |
| `DOCROUTER_RUNNERS_MAX_BLOB_READ_BYTES` | `67108864`                                                                                                                                    | Max bytes per helper read                                       |
| `DOCROUTER_CODE_MAX_TIMEOUT_SECONDS`    | `30`                                                                                                                                          | Already on node param; document server cap                      |


Org-level overrides (future): `organizations.flow_code_stdlib_allow` — **out of
scope v1**; env-only first.

### 5.4 Denied builtins (default)

Same spirit as n8n `BUILTINS_DENY_DEFAULT`. Safe subset remains: `len`, `range`,
`str`, `int`, `float`, `bool`, `list`, `dict`, `tuple`, `set`, `enumerate`,
`zip`, `min`, `max`, `sum`, `sorted`, `reversed`, `print`/`log` (captured).

Provide `**__import__`** wrapper that calls `import_validation.validate_module_import`.

---

## 6. `context` (unchanged in v1)

Keep existing keys (see `flows/nodes/code.py`):

`trigger`, `node_id`, `mode`, `nodes`, `organization_id`, `execution_id`,
`flow_id`, `flow_revid`, `start_time`, `execution_time`.

Optional v1.1: add `context["nodes_binary"]` as node-id → lane-0 binary metadata
only (no bytes). Not required if helpers + `_binary.merge_pages` cover assembly.

---

## 7. Implementation phases

### Phase A — Item codec + I/O (2–3 days)


| File                                   | Action                                                                |
| -------------------------------------- | --------------------------------------------------------------------- |
| `flows/code_runner/item_codec.py`      | `materialize_items_for_sandbox`, `normalize_output_items`             |
| `flows/nodes/code.py`                  | Pass full items in; decode outputs to `FlowItem`                      |
| `flows/code_runner.py`                 | Extend protocol: items include `json`/`binary`; validate output shape |
| `tests/flows/test_flows_code_items.py` | Round-trip json+binary metadata; legacy flat dict                     |


Reuse `expressions._materialize_binary` / `_materialize_item` — move to shared
module to avoid coupling sandbox to expression engine.

### Phase B — Binary post-processor (1–2 days)


| File                                                     | Action                                         |
| -------------------------------------------------------- | ---------------------------------------------- |
| `flows/code_runner/binary_actions.py`                    | `_binary` op dispatch                          |
| `common/pdf_pages.py`                                    | `merge_pdf_bytes(parts: list[bytes]) -> bytes` |
| `flows/items.py` or `docrouter_flows/document_binary.py` | `lane0_flow_items_from_run_data`               |
| `flows/nodes/code.py`                                    | Strip `_binary`, resolve to `BinaryRef`        |
| Node param `default_pages_source_node_id`                | manifest + schema                              |
| `tests/flows/test_flows_code_binary.py`                  | merge_pages, copy_input, fan-in 13→3           |


Enables surgery-schedule flow fix without user snippets calling PyMuPDF directly.

### Phase C — Security: analyzer + imports (2–3 days)


| File                                      | Action                                  |
| ----------------------------------------- | --------------------------------------- |
| `flows/code_runner/security_config.py`    | Load env allowlists                     |
| `flows/code_runner/task_analyzer.py`      | AST visitor + cache                     |
| `flows/code_runner/import_validation.py`  | stdlib vs external checks               |
| `flows/code_runner/subprocess_runner.py`  | Safe builtins + import shim in child    |
| `tests/flows/test_flows_code_security.py` | blocked patterns, allowed `import json` |


### Phase D — Helper RPC (2–3 days)


| File                                     | Action                                                              |
| ---------------------------------------- | ------------------------------------------------------------------- |
| `flows/code_runner/helpers_rpc.py`       | Parent handlers                                                     |
| `flows/code_runner/subprocess_runner.py` | RPC line protocol over stdin/stdout side channel **or** second pipe |


**Protocol option (recommended):** newline-delimited JSON messages on stderr for
RPC requests, stdout reserved for final result only — avoids multiplexing
complexity on single stream.


| Message                                                                           | Direction      |
| --------------------------------------------------------------------------------- | -------------- |
| `{"type":"rpc","id":"...","method":"helpers.merge_pdf_storage_ids","args":[...]}` | child → parent |
| `{"type":"rpc_result","id":"...","ok":true,"result":{...}}`                       | parent → child |


Parent reads child stderr asynchronously while waiting on process (or use
long-lived runner in Phase E).

### Phase E — (Optional) Persistent task runner

Defer unless subprocess-per-call latency is problematic. Would mirror n8n
`@n8n/task-runner-python` broker model; larger operational footprint.

### Phase F — Docs + UI (1 day)


| File                                          | Action                                                              |
| --------------------------------------------- | ------------------------------------------------------------------- |
| `docs/flows.md` (or new `docs/flows_code.md`) | Contract, helpers, `_binary`, examples                              |
| `docs/env.md`                                 | Runner env vars                                                     |
| `.env.example.local`                          | Placeholder entries                                                 |
| `code.manifest.json`                          | Update description, default snippet, `default_pages_source_node_id` |
| Frontend code editor                          | Snippets for binary pass-through / merge_pages                      |


---

## 8. Testing strategy


| Suite                         | Covers                                                |
| ----------------------------- | ----------------------------------------------------- |
| `test_flows_code_items.py`    | Item shape, legacy dict returns, meta/paired_item     |
| `test_flows_code_binary.py`   | `_binary` ops, surgery-schedule fan-in fixture        |
| `test_flows_code_security.py` | Analyzer rejects `open`, `__import_`_ bypass, etc.    |
| `test_flows_code_helpers.py`  | RPC merge/read/store with mock blobs                  |
| `test_flows_engine.py`        | Extend existing code node tests — no regressions      |
| E2E                           | Code → Google Drive upload with merged multi-page PDF |


Fixtures: reuse execution JSON from manual surgery-schedule run (13 pages, 3
patients).

---

## 9. Example: surgery-schedule flow after v2

**Option 1 — `_binary` in Code (no PyMuPDF in sandbox):**

```python
def run(items, context):
    grouped = group_patients(items)  # existing logic on llm_result
    out = []
    for p in grouped["patients"]:
        out.append({
            "json": p,
            "_binary": {
                "pdf": {
                    "op": "merge_pages",
                    "page_indices": p["page_idx"],
                }
            },
        })
    return out
```

**Option 2 — helper in Code (explicit):**

```python
def run(items, context):
  # helpers available if external allowlist permits nothing extra
  ids = [items[i]["binary"]["pdf"]["storage_id"] for i in p["page_idx"]]
  ref = helpers.merge_pdf_storage_ids(ids)
  return [{"json": p, "binary": {"pdf": ref}}]
```

**Option 3 — keep Code JSON-only + `docrouter.document_assemble` node** (separate
plan). v2 Code reduces need for dedicated assemble node but both can coexist.

---

## 10. Risks and mitigations


| Risk                                 | Mitigation                                        |
| ------------------------------------ | ------------------------------------------------- |
| Sandbox escape via imports           | Analyzer + allowlists + no raw builtins           |
| Huge PDFs OOM subprocess             | Size caps on read/merge; stream merge in parent   |
| RPC deadlock / protocol bugs         | Timeouts; integration tests; stderr RPC isolation |
| Breaking existing flows              | Legacy flat dict + index binary pass-through      |
| `storage_id` exfiltration            | RPC validates execution scope                     |
| Duplication with `document_assemble` | Shared `merge_pdf_bytes` in `common/pdf_pages.py` |


---

## 11. Acceptance criteria

1. Code node receives `items[i]["binary"]["pdf"]["storage_id"]` when upstream
  attaches PDFs.
2. User can return `{"json": ..., "binary": {"pdf": ref}}` with ref from
  `helpers.prepare_binary` or `_binary` merge.
3. Surgery-schedule test flow uploads **3 patient PDFs** (multi-page), not page 0.
4. `import json` works; `open("/etc/passwd")` fails at analysis or import shim.
5. Existing tests in `test_flows_engine.py` for code node pass unchanged.
6. Env vars documented and honored.

---

## 12. Related work

- `docs/map_reduce_node_plan.md` — `extract_pdf_page_subset`, group emit (can share
PDF helpers).
- `docrouter.document_split` — per-page source for `merge_pages`.
- n8n Code node — binary via `helpers.prepareBinaryData` (JS); we adopt RPC
pattern, not API names.

---

## 13. Suggested PR split

1. **PR1:** `item_codec` + binary metadata in/out (no new ops).
2. **PR2:** `_binary` post-processor + `merge_pdf_bytes`.
3. **PR3:** `task_analyzer` + env allowlists.
4. **PR4:** Helper RPC + docs/env/UI.

