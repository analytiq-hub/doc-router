# JavaScript / TypeScript Code Nodes — Design Guide

This document covers the design for `flows.js` and `flows.ts` node types that
run user-supplied JavaScript or TypeScript snippets inside a flow, side by side
with the existing `flows.code` Python node.

---

## 1. Why add JS/TS code nodes

`flows.code` (Python) covers the common case. JS/TS nodes add two things:

- **TypeScript** is the language many frontend and full-stack developers reach
for when writing data-transformation logic. Offering a TS node lowers the
barrier for those teams.
- **Ecosystem parity with n8n.** n8n's code node supports JavaScript and Python.
Flows that are migrated from or compared against n8n workflows benefit from
having the same two-language choice.

The nodes are additive: Python, JS, and TS nodes coexist in the same flow with
the same `FlowItem` contract between them.

---

## 2. Execution options

Three approaches exist for sandboxed JS/TS execution from a Python host.

### 2.1 Node.js subprocess

Fork a `node` child process per call. Send input JSON on stdin; read output JSON
from stdout. The contract is identical to the current `flows.code` Python runner.

- **TypeScript support**: not native. Requires a transpilation step (e.g.
`esbuild` or `ts-node`) bundled into the runner script.
- **Startup cost**: ~50–150 ms per invocation (Node.js process startup).
- **Isolation**: OS process boundary — equivalent to the Python runner.
- **Complexity**: low. Mirrors `code_runner.py` exactly.

### 2.2 Deno subprocess (recommended)

Fork a `deno run` child process per call, or keep a long-lived Deno process and
send tasks over a pipe. Deno executes TypeScript natively without any
compilation configuration.

- **TypeScript support**: native. The runner file itself can be TypeScript.
- **Startup cost**: first call per snippet ~300–500 ms while Deno's module cache
is cold; subsequent calls ~50–150 ms (cache warm). Eliminated entirely with a
persistent worker (see §4).
- **Isolation**: OS process boundary **plus** Deno's permission model. A runner
launched with `--no-allow-read --no-allow-write --no-allow-net` cannot touch
the filesystem or make outbound requests regardless of what the user snippet
does.
- **Complexity**: medium. Deno must be installed alongside Python. The runner
protocol is the same JSON stdin/stdout contract.

### 2.3 In-process JavaScript engine

Embed a JavaScript engine inside the Python process. No subprocess fork;
context creation is fast and contexts are reusable across calls. Two options
exist and they make different trade-offs.

#### PyMiniRacer (V8)

Embeds Google's V8 engine via a C extension (`mini-racer` on PyPI).

- **TypeScript support**: none. JavaScript only.
- **Startup cost**: context creation ~1–10 ms; reusable across calls.
- **Performance**: full JIT compiler — significantly faster than QuickJS for
CPU-intensive snippets (tight loops, heavy computation).
- **Binary size**: ~30 MB (V8 is large).
- **Isolation**: V8 heap isolation per context; memory is otherwise shared with
the host process.
- **Packaging**: V8 is frozen at build time. The `mini-racer` package has had
maintenance gaps and binary packaging issues on ARM and Alpine Linux.

#### QuickJS (`quickjs` on PyPI)

Embeds Fabrice Bellard's QuickJS engine via a C extension.

- **TypeScript support**: none. JavaScript only.
- **Startup cost**: context creation in microseconds.
- **Performance**: interpreter, no JIT. Slower than V8 for CPU-heavy code, but
adequate for JSON transformation work (maps, filters, string operations) where
serialisation dominates over computation.
- **Binary size**: ~1 MB.
- **Isolation**: interpreter-level; memory shared with the host process.
- **Packaging**: small, pure C, portable across platforms including ARM and
Alpine. Actively maintained by Bellard.

#### Which to use

For document-processing snippets — `items.map(...)`, field extraction, string
manipulation — the JIT advantage of V8 does not materialise in practice: the
bottleneck is JSON serialisation and `FlowItem` construction, not computation.
QuickJS wins on deployment simplicity, binary size, and startup cost. MiniRacer
would only be preferable if users routinely write computationally intensive
algorithms in their snippets, which is not the target use case.

**QuickJS is the chosen in-process fallback.** MiniRacer is not planned.

Both options share the same limitation: no TypeScript support, and weaker
isolation than the Deno subprocess path. The in-process engine is strictly a
fallback for deployments where Deno is not available.

### 2.4 Comparison


|                      | Node.js subprocess    | Deno subprocess            | PyMiniRacer (V8)          | QuickJS                    |
| -------------------- | --------------------- | -------------------------- | ------------------------- | -------------------------- |
| TypeScript native    | No (needs transpiler) | **Yes**                    | No                        | No                         |
| Per-call startup     | ~100 ms               | ~100 ms (warm)             | ~5 ms                     | <1 ms                      |
| CPU-intensive perf   | Good (JIT)            | Good (JIT)                 | **Best** (V8 JIT)         | Adequate (interpreter)     |
| Security sandbox     | Process boundary      | Process + permission flags | Heap isolation only       | Interpreter isolation only |
| Long-lived worker    | Yes (see §4)          | **Yes**                    | N/A (in-process)          | N/A (in-process)           |
| Binary size          | Node.js install       | Deno install               | ~30 MB                    | ~1 MB                      |
| Platform portability | Good                  | Good                       | Problematic on ARM/Alpine | **Excellent**              |
| Extra dependency     | `node`                | `deno`                     | `mini-racer`              | `quickjs`                  |


---

## 3. Recommended approach: Deno with a persistent task runner

Use Deno for both `flows.js` and `flows.ts` node types, run as a **persistent
task runner process**: a single long-lived Deno process started alongside the
worker, receiving tasks over a pipe, executing each snippet in an isolated
context, and returning results. This amortizes Deno startup to near zero per
call.

The permission flags passed at launch time define a fixed security boundary:

```
deno run \
  --no-allow-read \
  --no-allow-write \
  --no-allow-net \
  --no-allow-env \
  --no-allow-run \
  packages/deno/js_runner/runner.ts
```

User snippets cannot reach outside those boundaries regardless of their content.

This mirrors the architecture n8n uses for its task runner (see `docs/n8n.md`
§20–21): a long-running subprocess per language that receives jobs over IPC,
runs them in isolated `vm` / V8 contexts, and relays results back to the main
process.

---

## 4. Task runner protocol

The persistent Deno runner uses a newline-delimited JSON protocol over stdin /
stdout, identical to the Python runner except for the language field.

### Request (Python worker → Deno runner, one line)

```json
{
  "call_id":  "uuid-per-call",
  "code":     "function run(items, context) { ... }",
  "items":    [ { "amount": 100 } ],
  "context": {
    "parameters":     { "currency": "USD" },
    "trigger":        {},
    "node_id":        "n1",
    "mode":           "manual",
    "nodes":          {},
    "organization_id": "org",
    "execution_id":   "exec",
    "flow_id":        "flow",
    "flow_revid":     "rev"
  },
  "timeout_ms": 5000
}
```

### Response (Deno runner → Python worker, one line)

Success:

```json
{ "call_id": "uuid-per-call", "ok": true,  "items": [ { "amount": 110 } ] }
```

Error:

```json
{ "call_id": "uuid-per-call", "ok": false, "error": "ReferenceError: x is not defined" }
```

`call_id` is echoed back so the Python side can match responses to waiting
coroutines when multiple calls are in flight.

---

## 5. Snippet contract

The snippet must export or define a top-level `run` function:

```typescript
// flows.ts node — TypeScript
function run(
  items:   Record<string, unknown>[],
  context: Record<string, unknown>,
): Record<string, unknown>[] {
  const currency = (context["parameters"] as any).currency ?? "USD";
  return items.map(item => ({ ...item, currency }));
}
```

```javascript
// flows.js node — plain JavaScript
function run(items, context) {
  const currency = context.parameters?.currency ?? "USD";
  return items.map(item => ({ ...item, currency }));
}
```

- `items` — array of the current input slot's item `json` payloads.
- `context` — same shape as the Python runner context, with `parameters`
populated from the resolved node parameters.
- Return — array of output JSON objects. Each becomes one `FlowItem` on
output slot 0.

The runner evaluates the snippet in strict mode and calls `run(items, context)`
with a 5-second default timeout (configurable via `timeout_seconds` in node
parameters, capped at 30).

---

## 6. Node type definitions

Two new built-in node types are registered in `register_builtin.py`.

### `flows.js`

```python
class FlowsJSNode:
    key           = "flows.js"
    label         = "Code (JavaScript)"
    description   = "Runs a JavaScript snippet to transform items."
    category      = "Generic"
    is_trigger    = False
    is_merge      = False
    min_inputs    = 1
    max_inputs    = 1
    outputs       = 1
    output_labels = ["output"]
    parameter_schema = {
        "type": "object",
        "properties": {
            "js_code":          { "type": "string" },
            "timeout_seconds":  { "type": "number" },
        },
        "required": ["js_code"],
        "additionalProperties": False,
    }
```

### `flows.ts`

Identical to `flows.js` except:

```python
    key         = "flows.ts"
    label       = "Code (TypeScript)"
    parameter_schema = {
        ...
        "properties": {
            "ts_code":         { "type": "string" },
            "timeout_seconds": { "type": "number" },
        },
        "required": ["ts_code"],
        ...
    }
```

Both node types delegate execution to a shared `run_js_code` / `run_ts_code`
helper (or a single `run_deno_code(code, *, language, ...)` helper) in a new
`analytiq_data/flows/js_runner.py` module.

---

## 7. `js_runner.py` module

Analogous to `code_runner.py`. Manages the lifecycle of the persistent Deno
process and exposes one async function:

```python
async def run_deno_code(
    code: str,
    *,
    language: Literal["js", "ts"],
    items: list[dict[str, Any]],
    context: dict[str, Any],
    timeout_seconds: float = 5.0,
) -> list[dict[str, Any]]:
    ...
```

### Process lifecycle

- **Startup**: the Deno runner process is started lazily on first call and kept
alive for the lifetime of the worker. If the process exits unexpectedly it is
restarted on the next call.
- **Concurrency**: each call sends one request line and awaits the matching
response line, identified by `call_id`. Multiple coroutines may call
`run_deno_code` concurrently; the module maintains a `dict[call_id, Future]`
and a single reader task that dispatches response lines to the right future.
- **Timeout**: enforced both client-side (`asyncio.wait_for`) and inside the
Deno runner (via `setTimeout` abort).
- **Failure isolation**: a snippet that throws an unhandled error returns an
error response; it does not kill the runner process. A snippet that blocks
past `timeout_ms` is aborted by the runner's internal timer.

### Deno runner source

The Deno runner (`packages/deno/js_runner/runner.ts`) reads request lines from
`stdin` in a loop, evaluates each snippet in a fresh `Function` scope or
`eval`-with-sandbox, and writes response lines to `stdout`.

TypeScript snippets are handled transparently by Deno (no explicit compile
step needed in the runner).

---

## 8. Security notes


| Threat                                    | Mitigation                                                                                    |
| ----------------------------------------- | --------------------------------------------------------------------------------------------- |
| File system access                        | `--no-allow-read --no-allow-write` at Deno launch                                             |
| Outbound network calls                    | `--no-allow-net` at Deno launch                                                               |
| Environment variable leakage              | `--no-allow-env` at Deno launch                                                               |
| Infinite loops / CPU exhaustion           | `timeout_ms` enforced inside runner; `asyncio.wait_for` on Python side                        |
| Memory exhaustion                         | Deno V8 heap limit (set via `--v8-flags=--max-heap-size=128`)                                 |
| Prototype pollution / `__proto__` attacks | Runner passes items as JSON-parsed plain objects; snippet cannot reach the runner's own scope |


These mitigations are stronger than the Python runner's current posture
(`sys.executable -I -S` plus restricted builtins) because the permission flags
are enforced by the OS-level seccomp filter Deno applies, not just by Python
`eval` restrictions.

---

## 9. Module layout

```
analytiq_data/flows/
  js_runner.py                  run_deno_code(); Deno process lifecycle
  nodes/
    js.py                       FlowsJSNode
    ts.py                       FlowsTSNode
  register_builtin.py           register FlowsJSNode, FlowsTSNode

packages/deno/
  js_runner/
    runner.ts                   Long-lived Deno task runner (reads stdin, writes stdout)

tests_flow/
  test_js_node.py               Unit tests using a mock Deno runner
tests/
  test_flows_e2e.py             Integration tests (require Deno installed)
```

---

## 10. Availability and fallback

### Primary path: Deno

`js_runner.py` checks for the `deno` binary at import time:

```python
DENO_AVAILABLE: bool  # True if `deno` is on PATH
```

`FlowsJSNode` and `FlowsTSNode` are always registered regardless of this flag,
so validation and the node-type list remain functional. If `DENO_AVAILABLE` is
`False` and no fallback is available, execution raises a clear runtime error:

```
flows.js requires Deno. Install from https://deno.land and ensure it is on PATH.
```

### Fallback path: QuickJS

When Deno is unavailable, `flows.js` falls back to in-process execution via the
`quickjs` Python package. The fallback is JavaScript only — `flows.ts` has no
fallback and raises the error above when Deno is absent.

```python
QUICKJS_AVAILABLE: bool  # True if `quickjs` package is importable
```

Execution path selection at call time:

```python
if DENO_AVAILABLE:
    return await _run_via_deno(code, language=language, ...)
elif language == "js" and QUICKJS_AVAILABLE:
    return _run_via_quickjs(code, ...)
else:
    raise RuntimeError(...)
```

QuickJS runs synchronously in the calling thread. There is no subprocess
overhead, but isolation is weaker (interpreter-level, no process boundary) and
TypeScript is unsupported. It is suitable for simple JSON transformation
snippets; for anything CPU-intensive or security-sensitive, Deno is strongly
preferred.

The `quickjs` package is an optional dependency. Deployments that always have
Deno do not need it.

---

## 11. Roadmap


| Item                                          | Notes                                                                                                                                                                                                                                                                                              |
| --------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Multi-output return (`list[list[dict]]`)      | Allows JS/TS nodes to feed branch-style flows; same gap as Python dynamic node types                                                                                                                                                                                                               |
| `flows.js` / `flows.ts` as dynamic node types | Combine §6 with `docs/dynamic_node_types.md`: store JS/TS code in `flow_node_type_definitions`                                                                                                                                                                                                     |
| npm / Deno module imports inside snippets     | Requires allow-listing specific modules; significant security surface expansion                                                                                                                                                                                                                    |
| Persistent runner pool                        | Multiple Deno workers for high-concurrency deployments                                                                                                                                                                                                                                             |
| QuickJS fallback                              | In-process JS-only fallback when Deno is unavailable (see §10). Chosen over PyMiniRacer: smaller binary (~1 MB vs ~30 MB), microsecond context creation, better portability on ARM/Alpine. V8/MiniRacer's JIT advantage does not apply to the JSON-transformation workloads typical in flow nodes. |


