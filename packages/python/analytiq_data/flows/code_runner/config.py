"""Environment settings for Code / Tool Code nodes.

| Variable | Default | Meaning |
|---|---|---|
| ``FLOW_CODE_RUNNER`` | ``wasi`` | ``wasi`` (sandbox), ``local`` (plain subprocess, no sandbox) or ``disabled`` |
| ``FLOW_CODE_ENABLED`` | ``true`` | ``false`` turns Code nodes off everywhere (same as ``FLOW_CODE_RUNNER=disabled``) |
| ``FLOW_CODE_ALLOW_UNSANDBOXED`` | ``false`` | Must be ``true`` for ``FLOW_CODE_RUNNER=local`` (trusted, single-tenant installs and development only) |
| ``FLOW_CODE_STDLIB_ALLOW`` | ``DEFAULT_ALLOWED_MODULES`` | Comma-separated importable modules, or ``*`` |
| ``FLOW_CODE_EXTERNAL_ALLOW`` | (none) | Extra third-party modules; only importable with ``local`` (the WASI sandbox has the standard library only) |
| ``FLOW_CODE_BUILTINS_DENY`` | ``BUILTINS_DENY_DEFAULT`` | Comma-separated built-ins removed from the code's namespace |
| ``FLOW_CODE_MEMORY_MB`` | ``256`` | WASI linear-memory limit per run |
| ``FLOW_CODE_MAX_PAYLOAD_BYTES`` | 48 MiB | Max request size (items, context and input files as base64) |
| ``FLOW_CODE_BINARY_READ_MAX_BYTES`` | 10 MiB | Max size of one input file passed to the code |
| ``FLOW_CODE_WASI_DIR`` | ``<repo>/.cache/python-wasi/<version>`` | Where ``python.wasm`` and its ``lib/`` are installed |

Inside the WASI sandbox the code has the standard library plus the pinned pure-Python
``SANDBOX_PACKAGES`` (``python_wasi.py``; today ``pypdf``) and a pure-Python ``zlib``
(``sandbox_lib/``), all read-only.

The static checks and the restricted namespace are a second layer only: the security boundary is
the WASI sandbox (``wasi.py``).
"""

from __future__ import annotations

import os

DEFAULT_ALLOWED_MODULES: tuple[str, ...] = (
    "json",
    "re",
    "math",
    "datetime",
    "collections",
    "itertools",
    "functools",
    "hashlib",
    "base64",
    "uuid",
    "typing",
    "decimal",
    "statistics",
    "string",
    "textwrap",
    "random",
    "io",
    # Pinned pure-Python packages shipped into the sandbox (python_wasi.SANDBOX_PACKAGES).
    "pypdf",
)

BUILTINS_DENY_DEFAULT: frozenset[str] = frozenset(
    {
        "eval",
        "exec",
        "compile",
        "open",
        "input",
        "breakpoint",
        "getattr",
        "object",
        "type",
        "vars",
        "setattr",
        "delattr",
        "hasattr",
        "dir",
        "memoryview",
        "__build_class__",
        "globals",
        "locals",
        "license",
        "help",
        "credits",
        "copyright",
        "exit",
        "quit",
    }
)

DEFAULT_MEMORY_MB = 256
DEFAULT_MAX_REQUEST_BYTES = 48 << 20
DEFAULT_MAX_INPUT_FILE_BYTES = 10 << 20
MAX_INPUT_TOTAL_BYTES = 32 << 20
MAX_STORE_BYTES = 16 << 20
MAX_PRINT_CALLS = 100

_FALSE = ("0", "false", "no", "off")
_TRUE = ("1", "true", "yes", "on")


def _csv(value: str | None) -> list[str]:
    return [p.strip() for p in (value or "").split(",") if p.strip()]


def _int_env(name: str, default: int) -> int:
    raw = (os.environ.get(name) or "").strip()
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError:
        return default
    return value if value > 0 else default


def allowed_modules() -> list[str]:
    """Importable top-level modules (``["*"]`` = any)."""
    stdlib = _csv(os.environ.get("FLOW_CODE_STDLIB_ALLOW")) or list(DEFAULT_ALLOWED_MODULES)
    external = _csv(os.environ.get("FLOW_CODE_EXTERNAL_ALLOW"))
    for part in (stdlib, external):
        if "*" in part and len(part) > 1:
            raise ValueError("Wildcard '*' cannot be combined with other allowlist entries")
    if "*" in stdlib or "*" in external:
        return ["*"]
    return list(dict.fromkeys(stdlib + external))


def builtins_deny() -> frozenset[str]:
    raw = _csv(os.environ.get("FLOW_CODE_BUILTINS_DENY"))
    return frozenset(raw) if raw else BUILTINS_DENY_DEFAULT


def runner_name() -> str:
    if (os.environ.get("FLOW_CODE_ENABLED") or "true").strip().lower() in _FALSE:
        return "disabled"
    return (os.environ.get("FLOW_CODE_RUNNER") or "wasi").strip().lower()


def unsandboxed_allowed() -> bool:
    return (os.environ.get("FLOW_CODE_ALLOW_UNSANDBOXED") or "").strip().lower() in _TRUE


def memory_mb() -> int:
    return _int_env("FLOW_CODE_MEMORY_MB", DEFAULT_MEMORY_MB)


def max_request_bytes() -> int:
    return _int_env("FLOW_CODE_MAX_PAYLOAD_BYTES", DEFAULT_MAX_REQUEST_BYTES)


def max_input_file_bytes() -> int:
    return _int_env("FLOW_CODE_BINARY_READ_MAX_BYTES", DEFAULT_MAX_INPUT_FILE_BYTES)
