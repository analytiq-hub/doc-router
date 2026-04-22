from __future__ import annotations

"""
Isolated Python runner for `flows.code`.

This uses a separate Python interpreter process (subprocess) to execute user
code with a narrow JSON-in/JSON-out contract. The subprocess is started in
Python isolated mode (`-I -S`) and with a minimal environment to avoid
inheriting the parent environment variables.

This is not a full security sandbox, but it provides a process boundary and a
constrained builtins set (no imports) for v1.
"""

import asyncio
import json
import os
import sys
from typing import Any


class CodeExecutionError(RuntimeError):
    """Raised when a code snippet fails or returns invalid output."""


_RUNNER_CODE = r"""
import json
import sys
import traceback

def _safe_builtins():
    # Intentionally small. No __import__ => no imports.
    allowed = {
        "abs": abs,
        "all": all,
        "any": any,
        "bool": bool,
        "dict": dict,
        "enumerate": enumerate,
        "float": float,
        "int": int,
        "len": len,
        "list": list,
        "max": max,
        "min": min,
        "range": range,
        "reversed": reversed,
        "sorted": sorted,
        "str": str,
        "sum": sum,
        "tuple": tuple,
        "zip": zip,
    }
    return allowed

def _fail(message: str):
    sys.stdout.write(json.dumps({"ok": False, "error": {"message": message}}))
    sys.stdout.flush()
    raise SystemExit(0)

payload = sys.stdin.read()
if not payload:
    _fail("Missing payload")

try:
    req = json.loads(payload)
except Exception as e:
    _fail(f"Invalid JSON payload: {e}")

code = req.get("code")
items = req.get("items")
context = req.get("context")

if not isinstance(code, str):
    _fail("code must be a string")
if not isinstance(items, list):
    _fail("items must be a list")
if not isinstance(context, dict):
    _fail("context must be a dict")

globs = {"__builtins__": _safe_builtins()}
locs = {}

try:
    exec(code, globs, locs)
except Exception:
    _fail("Code compile/exec failed:\n" + traceback.format_exc())

fn = locs.get("run") or globs.get("run")
if not callable(fn):
    _fail("Code must define a callable `run(items, context)`")

try:
    out = fn(items, context)
except Exception:
    _fail("Code execution failed:\n" + traceback.format_exc())

if not isinstance(out, list):
    _fail("run() must return a list")
for i, v in enumerate(out):
    if not isinstance(v, dict):
        _fail(f"run() output items must be dicts; got {type(v).__name__} at index {i}")

sys.stdout.write(json.dumps({"ok": True, "items": out}))
sys.stdout.flush()
"""


def _minimal_env() -> dict[str, str]:
    """
    Return a minimal environment for the child interpreter.

    We keep PATH so the interpreter can start normally on some systems, but we
    scrub most other variables (including secrets). `-I` also ignores PYTHON* env.
    """

    env: dict[str, str] = {}
    if "PATH" in os.environ:
        env["PATH"] = os.environ["PATH"]
    env["LANG"] = os.environ.get("LANG", "C.UTF-8")
    env["LC_ALL"] = os.environ.get("LC_ALL", env["LANG"])
    return env


async def run_python_code(
    *,
    code: str,
    items: list[dict[str, Any]],
    context: dict[str, Any],
    timeout_seconds: float = 2.0,
) -> list[dict[str, Any]]:
    """
    Execute `code` in an isolated Python subprocess.

    Contract:
    - `code` must define `run(items, context)` and return `list[dict]`.
    - `items` are JSON dicts (typically item.json).
    - `context` is a small JSON dict (execution metadata).
    """

    req = {"code": code, "items": items, "context": context}
    inp = json.dumps(req).encode("utf-8")

    proc = await asyncio.create_subprocess_exec(
        sys.executable,
        "-I",
        "-S",
        "-c",
        _RUNNER_CODE,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env=_minimal_env(),
    )

    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(inp), timeout=timeout_seconds)
    except asyncio.TimeoutError:
        proc.kill()
        raise CodeExecutionError("Code execution timed out") from None

    try:
        resp = json.loads(stdout.decode("utf-8") if stdout else "{}")
    except Exception as e:
        stderr_text = stderr.decode("utf-8", errors="replace") if stderr else ""
        raise CodeExecutionError(
            f"Runner returned invalid JSON: {e}" + (f"\nstderr: {stderr_text}" if stderr_text else "")
        ) from e

    if not resp.get("ok"):
        msg = ((resp.get("error") or {}) or {}).get("message") or "Unknown error"
        raise CodeExecutionError(msg)

    out_items = resp.get("items")
    if not isinstance(out_items, list):
        raise CodeExecutionError("Runner returned invalid items")
    return out_items

