"""The program that runs Code / Tool Code nodes' user code.

It runs **inside the sandbox** (CPython on WASI; a plain subprocess only with the unsandboxed
``local`` runner), standard library only, and must not import anything from ``analytiq_data``. It
reads one JSON request on stdin and writes one JSON result on stdout after ``RESULT_MARKER``.

- ``kind="flow_code"``: ``def run(items, context) -> list[dict]``, ``all_items`` / ``per_item``
  modes, continue-on-fail error items, output normalization and checks.
- ``kind="tool_code"``: ``def run(params, context) -> dict`` (an LLM tool call).

``print`` / ``log`` are captured as logs. ``read_binary(storage_id)`` only returns files passed in
with the request (the input items' own); ``store_binary`` hands the bytes back to the worker, which
stores them for the run. There is no access to stored files by key.

Request: ``{"kind", "sys_path", "code", "mode", "items", "params", "context", "continue_on_fail",
"allowed_modules", "builtins_deny", "binaries": {storage_id: base64}, "max_print_calls",
"max_store_bytes"}``.
Result: ``{"ok": true, "items" | "tool_result", "logs", "stored": [{"mime_type", "file_name",
"data_b64"}]}`` or ``{"ok": false, "error": {"message", "stack"}, "logs"}``.
"""

import base64
import builtins
import importlib
import json
import sys
import traceback

RESULT_MARKER = "\x1e@@flow-code-result@@"

_write = sys.stdout.write
_flush = sys.stdout.flush

RESERVED_TOP_LEVEL_KEYS = frozenset({"json", "binary", "meta", "paired_item"})
BINARY_META_KEYS = frozenset({"mime_type", "file_name", "storage_id", "file_size"})
PENDING_PREFIX = "pending:"

# Modules the runner itself keeps loaded (removed from sys.modules otherwise, as in doc-router).
_RUNNER_KEEP = frozenset(
    {
        "sys",
        "builtins",
        "importlib",
        "importlib.machinery",
        "importlib._bootstrap",
        "importlib._bootstrap_external",
        "importlib.util",
        "encodings",
        "codecs",
        "abc",
        "json",
        "json.decoder",
        "json.encoder",
        "json.scanner",
        "traceback",
        "types",
        "linecache",
        "posix",
        "posixpath",
        "errno",
        "os",
        "io",
        "warnings",
        "weakref",
        "collections",
        "collections.abc",
        "functools",
        "operator",
        "itertools",
        "keyword",
        "base64",
        "binascii",
        "struct",
        "re",
        "enum",
        "textwrap",
        "contextlib",
        "reprlib",
    }
)


class ExecutionFailure(Exception):
    def __init__(self, message, stack=None):
        super().__init__(message)
        self.message = message
        self.stack = stack


class CodeValidationError(ValueError):
    pass


# ---- Output checks (doc-router's validation.py) -------------------------------------------------


def _has_reserved_key(item):
    return any(k in RESERVED_TOP_LEVEL_KEYS for k in item)


def _normalize(items, batch_has_explicit):
    out = []
    for idx, raw in enumerate(items):
        if not isinstance(raw, dict):
            raise CodeValidationError(
                f"run() output items must be dicts; got {type(raw).__name__} at index {idx}"
            )
        if _has_reserved_key(raw):
            item = dict(raw)
            item.setdefault("json", {})
            out.append(item)
        elif batch_has_explicit:
            unknown = [k for k in raw if k not in RESERVED_TOP_LEVEL_KEYS]
            raise CodeValidationError(
                f"Unknown top-level key '{unknown[0] if unknown else '?'}' at index {idx}. "
                'Put fields under json: return {"json": {...}} on every item.'
            )
        else:
            out.append({"json": dict(raw)})
    return out


def _check_item(item, idx):
    keys = set(item)
    reserved, unknown = keys & RESERVED_TOP_LEVEL_KEYS, keys - RESERVED_TOP_LEVEL_KEYS
    if reserved and unknown:
        raise CodeValidationError(
            f"Output item at index {idx} mixes reserved key '{sorted(reserved)[0]}' with "
            f"'{sorted(unknown)[0]}'. Put custom fields under json."
        )
    if not isinstance(item.get("json"), dict):
        raise CodeValidationError(f"'json' must be a dict at index {idx}")
    if "binary" in item:
        binary = item["binary"]
        if not isinstance(binary, dict):
            raise CodeValidationError(f"'binary' must be a dict at index {idx}")
        for name, ref in binary.items():
            if not isinstance(ref, dict):
                raise CodeValidationError(f"binary['{name}'] must be a dict at index {idx}")
            if ref.get("data") is not None:
                raise CodeValidationError(
                    f"binary['{name}'] must not include raw data at index {idx}: use store_binary()"
                )
            sid = ref.get("storage_id")
            if not isinstance(sid, str) or not sid.strip():
                raise CodeValidationError(
                    f"binary['{name}'] has no storage_id at index {idx}: call store_binary() first"
                )
            extra = set(ref) - BINARY_META_KEYS
            if extra:
                raise CodeValidationError(
                    f"binary['{name}'] has unknown key '{sorted(extra)[0]}' at index {idx}"
                )
    if "meta" in item and not isinstance(item["meta"], dict):
        raise CodeValidationError(f"'meta' must be a dict at index {idx}")
    paired = item.get("paired_item")
    if paired is not None and not (
        isinstance(paired, int)
        or (isinstance(paired, list) and paired and all(isinstance(x, int) for x in paired))
    ):
        raise CodeValidationError(f"Invalid paired_item at index {idx}")


def validate_code_output(items):
    if not isinstance(items, list):
        raise CodeValidationError("run() must return a list")
    explicit = any(isinstance(x, dict) and _has_reserved_key(x) for x in items)
    normalized = _normalize(items, explicit)
    for idx, item in enumerate(normalized):
        _check_item(item, idx)
    return normalized


# ---- The restricted namespace -------------------------------------------------------------------


def _safe_import_factory(allowed):
    allowed = set(allowed)

    def safe_import(name, globals=None, locals=None, fromlist=(), level=0):
        if level != 0:
            raise ImportError("Relative imports are not allowed")
        top = name.split(".")[0]
        if "*" not in allowed and top not in allowed:
            raise ImportError(f"Import of module '{top}' is not allowed")
        return importlib.__import__(name, globals, locals, fromlist or (), 0)

    return safe_import


def _filtered_builtins(deny, allowed):
    out = {k: v for k, v in builtins.__dict__.items() if k not in deny}
    out["__import__"] = _safe_import_factory(allowed)
    return out


def _sanitize_modules(allowed):
    if "*" in allowed:
        return
    for name in list(sys.modules):
        if name in _RUNNER_KEEP or name.split(".")[0] in allowed:
            continue
        del sys.modules[name]


def _print_factory(logs, max_calls):
    state = {"n": 0}

    def _show(value):
        if isinstance(value, str):
            return value
        try:
            return json.dumps(value, ensure_ascii=False, default=lambda o: f"[{type(o).__name__}]")
        except (TypeError, ValueError):
            return repr(value)

    def log(*args, sep=" ", **_kwargs):
        state["n"] += 1
        if state["n"] > max_calls:
            if state["n"] == max_calls + 1:
                logs.append(f"[more than {max_calls} print calls: the rest is not shown]")
            return
        logs.append(sep.join(_show(a) for a in args))

    return log


def _binary_functions(binaries, stored, max_store_bytes, can_store=True):
    state = {"bytes": 0}

    def read_binary(storage_id):
        if not isinstance(storage_id, str) or storage_id not in binaries:
            raise ValueError(
                f"read_binary: {storage_id!r} is not a file of this node's input items "
                "(or it is larger than the Code node's file limit)"
            )
        return binaries[storage_id]

    def store_binary(mime_type, file_name, data_b64):
        if not can_store:
            raise ValueError("store_binary is not available in tool code")
        try:
            data = base64.b64decode(data_b64, validate=True)
        except Exception as e:
            raise ValueError(f"store_binary: invalid base64 ({e})") from None
        state["bytes"] += len(data)
        if state["bytes"] > max_store_bytes:
            raise ValueError(f"store_binary: more than {max_store_bytes} bytes stored by this run")
        stored.append(
            {
                "mime_type": str(mime_type or "application/octet-stream"),
                "file_name": str(file_name or ""),
                "data_b64": data_b64,
            }
        )
        return f"{PENDING_PREFIX}{len(stored) - 1}"

    return read_binary, store_binary


def _error_item(message, context, paired_item=None):
    item = {
        "json": {
            "_error": {
                "message": message,
                "node_id": context.get("node_id"),
                "node_name": context.get("node_name") or context.get("node_id"),
            }
        }
    }
    if paired_item is not None:
        item["paired_item"] = paired_item
    return item


def _namespace(req, stored, logs, can_store=True):
    allowed = list(req.get("allowed_modules") or [])
    read_binary, store_binary = _binary_functions(
        dict(req.get("binaries") or {}),
        stored,
        int(req.get("max_store_bytes") or 16 << 20),
        can_store=can_store,
    )
    log = _print_factory(logs, int(req.get("max_print_calls") or 100))
    ns = {
        "__builtins__": _filtered_builtins(set(req.get("builtins_deny") or []), allowed),
        "read_binary": read_binary,
        "store_binary": store_binary,
        "print": log,
        "log": log,
    }
    _sanitize_modules(set(allowed))
    return ns


def _load_run(req, ns, signature):
    try:
        exec(compile(req["code"], "<code>", "exec"), ns, ns)
    except Exception:
        stack = traceback.format_exc()
        raise ExecutionFailure(f"Code compile/exec failed:\n{stack}", stack) from None
    run_fn = ns.get("run")
    if not callable(run_fn):
        raise ExecutionFailure(f"Code must define a callable `run({signature})`")
    return run_fn


def execute_tool(req, logs, stored):
    params, context = req.get("params"), req.get("context")
    if not isinstance(params, dict) or not isinstance(context, dict):
        raise ExecutionFailure("params and context must be dicts")
    run_fn = _load_run(req, _namespace(req, stored, logs, can_store=False), "params, context")
    try:
        raw = run_fn(params, context)
    except Exception:
        stack = traceback.format_exc()
        raise ExecutionFailure(f"Tool code execution failed:\n{stack}", stack) from None
    if not isinstance(raw, dict):
        raise ExecutionFailure(f"run() must return a dict, got {type(raw).__name__}")
    return raw


def execute(req, logs, stored):
    mode = req.get("mode") or "all_items"
    if mode not in ("all_items", "per_item"):
        raise ExecutionFailure(f"Invalid mode: {mode}")
    items, context = req.get("items"), req.get("context")
    if not isinstance(items, list) or not isinstance(context, dict):
        raise ExecutionFailure("items must be a list and context a dict")
    run_fn = _load_run(req, _namespace(req, stored, logs), "items, context")
    continue_on_fail = bool(req.get("continue_on_fail"))

    def call(batch, idx=None):
        try:
            return validate_code_output(run_fn(batch, context))
        except CodeValidationError as e:
            raise ExecutionFailure(str(e), traceback.format_exc()) from None
        except Exception as e:
            if continue_on_fail:
                return [_error_item(str(e), context, idx)]
            where = "" if idx is None else f" at item {idx}"
            stack = traceback.format_exc()
            raise ExecutionFailure(f"Code execution failed{where}:\n{stack}", stack) from None

    if mode == "all_items":
        return call(items)
    out = []
    for idx, item in enumerate(items):
        for row in call([item], idx):
            if row.get("paired_item") is None:
                row = {**row, "paired_item": idx}
            out.append(row)
    return out


def main():
    logs, stored = [], []
    try:
        req = json.loads(sys.stdin.buffer.read().decode("utf-8"))
        for entry in req.get("sys_path") or []:
            if isinstance(entry, str) and entry not in sys.path:
                sys.path.append(entry)
        if req.get("kind") == "tool_code":
            out = {"ok": True, "tool_result": execute_tool(req, logs, stored), "logs": logs}
        else:
            out = {"ok": True, "items": execute(req, logs, stored), "logs": logs, "stored": stored}
    except ExecutionFailure as e:
        out = {"ok": False, "error": {"message": e.message, "stack": e.stack}, "logs": logs}
    except Exception as e:
        out = {
            "ok": False,
            "error": {"message": str(e), "stack": traceback.format_exc()},
            "logs": logs,
        }
    try:
        text = json.dumps(out, ensure_ascii=False)
    except (TypeError, ValueError) as e:
        text = json.dumps(
            {
                "ok": False,
                "error": {
                    "message": f"run() returned values that are not JSON: {e}",
                    "stack": None,
                },
                "logs": logs,
            }
        )
    _write(RESULT_MARKER + text + "\n")
    _flush()


main()
