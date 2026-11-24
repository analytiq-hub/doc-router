"""Where Code / Tool Code nodes' user code runs.

One request in, one result out: the nodes do not know which runner they use.

- ``wasi`` (default): CPython compiled to WebAssembly, run by ``wasmtime`` in the worker. No files
  (except the standard library, read-only), network, environment or processes; memory and
  wall-clock limits. This is the security boundary.
- ``local``: a plain subprocess. **Not a sandbox**; refused unless
  ``FLOW_CODE_ALLOW_UNSANDBOXED=true`` (development, or single-tenant installs where every flow
  editor is trusted and needs compiled packages such as ``fitz``).
- ``disabled``: Code nodes fail with a clear error.

The code never gets access to stored files by key: input files are fetched by the node (scoped to
the run's organization) and passed in; files the code creates come back in the result and the node
stores them for the run.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any, Protocol

from . import config

GUEST_SOURCE_PATH = Path(__file__).with_name("guest_runner.py")
RESULT_MARKER = "\x1e@@flow-code-result@@"

DEFAULT_TIMEOUT_SECONDS = 30.0
MAX_TIMEOUT_SECONDS = 120.0


class CodeExecutionError(RuntimeError):
    """The code could not run, failed, or hit a limit; ``stack`` is the user code's traceback."""

    def __init__(self, message: str, *, stack: str | None = None) -> None:
        super().__init__(message)
        self.stack = stack


@dataclass
class CodeTask:
    code: str
    context: dict[str, Any]
    kind: str = "flow_code"  # "flow_code": run(items, context) | "tool_code": run(params, context)
    mode: str = "all_items"
    items: list[dict[str, Any]] = field(default_factory=list)
    params: dict[str, Any] = field(default_factory=dict)
    continue_on_fail: bool = False
    binaries: dict[str, str] = field(default_factory=dict)  # storage_id -> base64
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS
    memory_mb: int = field(default_factory=config.memory_mb)

    def request_json(self, *, sys_path: list[str] | None = None) -> bytes:
        """The guest's request; ``sys_path``: where the runner put ``SANDBOX_PACKAGES``."""
        body = json.dumps(
            {
                "kind": self.kind,
                "sys_path": list(sys_path or []),
                "code": self.code,
                "mode": self.mode,
                "items": self.items,
                "params": self.params,
                "context": self.context,
                "continue_on_fail": self.continue_on_fail,
                "allowed_modules": config.allowed_modules(),
                "builtins_deny": sorted(config.builtins_deny()),
                "binaries": self.binaries,
                "max_print_calls": config.MAX_PRINT_CALLS,
                "max_store_bytes": config.MAX_STORE_BYTES,
            },
            ensure_ascii=False,
            default=str,
        ).encode("utf-8")
        limit = config.max_request_bytes()
        if len(body) > limit:
            raise CodeExecutionError(
                f"The code node's input is too large ({len(body)} bytes; at most {limit})"
            )
        return body


@dataclass
class CodeResult:
    items: list[dict[str, Any]]
    logs: list[str]
    stored: list[dict[str, str]]  # {"mime_type", "file_name", "data_b64"}; index = pending:N
    tool_result: dict[str, Any] | None = None


class CodeRunner(Protocol):
    name: str

    async def run(self, task: CodeTask) -> CodeResult: ...


@lru_cache(maxsize=1)
def guest_source() -> str:
    return GUEST_SOURCE_PATH.read_text(encoding="utf-8")


def parse_result(stdout: str, stderr: str = "", *, kind: str = "flow_code") -> CodeResult:
    """The guest's result (after its marker); a missing or bad one is an error with stderr."""
    _, sep, tail = stdout.rpartition(RESULT_MARKER)
    if not sep:
        detail = stderr.strip()[-2000:] or stdout.strip()[-2000:] or "no output"
        raise CodeExecutionError(f"The code runner ended without a result: {detail}")
    try:
        out = json.loads(tail.strip().splitlines()[0])
    except (ValueError, IndexError) as e:
        raise CodeExecutionError(f"The code runner returned an unreadable result: {e}") from None
    logs = [str(x) for x in out.get("logs") or []]
    if not out.get("ok"):
        err = out.get("error") or {}
        raise CodeExecutionError(
            str(err.get("message") or "The code failed"), stack=err.get("stack")
        )
    stored = list(out.get("stored") or [])
    if kind == "tool_code":
        tool_result = out.get("tool_result")
        if not isinstance(tool_result, dict):
            raise CodeExecutionError("The code runner returned no tool result")
        return CodeResult(items=[], logs=logs, stored=stored, tool_result=tool_result)
    items = out.get("items")
    if not isinstance(items, list):
        raise CodeExecutionError("The code runner returned no items")
    return CodeResult(items=items, logs=logs, stored=stored)


def get_code_runner() -> CodeRunner:
    """The configured runner (``FLOW_CODE_RUNNER``)."""
    name = config.runner_name()
    if name == "disabled":
        raise CodeExecutionError(
            "Code nodes are turned off on this server (FLOW_CODE_RUNNER=disabled or "
            "FLOW_CODE_ENABLED=false)"
        )
    if name == "local":
        if not config.unsandboxed_allowed():
            raise CodeExecutionError(
                "FLOW_CODE_RUNNER=local runs code without a sandbox and also needs "
                "FLOW_CODE_ALLOW_UNSANDBOXED=true (development or trusted single-tenant installs only)"
            )
        from .local import LocalSubprocessRunner

        return LocalSubprocessRunner()
    if name == "wasi":
        from .wasi import WasiRunner

        return WasiRunner.shared()
    raise CodeExecutionError(f"Unknown FLOW_CODE_RUNNER {name!r} (wasi, local or disabled)")


async def run_code_task(task: CodeTask) -> CodeResult:
    """Static checks, then the configured runner."""
    from .checks import CodeCheckError, check_code

    try:
        check_code(task.code)
    except CodeCheckError as e:
        raise CodeExecutionError(f"Code refused: {e}") from None
    return await get_code_runner().run(task)
