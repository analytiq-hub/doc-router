from __future__ import annotations

import builtins
import importlib
import json
import sys
from typing import Any, Callable

from .config import SecurityConfig
from .import_validation import ImportValidationError
from .security import RUNNER_MODULES_KEEP, RUNNER_MODULE_PREFIXES


def build_filtered_builtins(config: SecurityConfig) -> dict[str, Any]:
    filtered: dict[str, Any] = {}
    for name, value in builtins.__dict__.items():
        if name in config.builtins_deny:
            continue
        filtered[name] = value
    filtered["__import__"] = _make_safe_import(config)
    return filtered


def _make_safe_import(config: SecurityConfig) -> Callable[..., Any]:
    def safe_import(
        name: str,
        globals: dict[str, Any] | None = None,
        locals: dict[str, Any] | None = None,
        fromlist: tuple[str, ...] = (),
        level: int = 0,
    ) -> Any:
        if level != 0:
            raise ImportValidationError("Relative imports are not allowed")
        top = name.split(".")[0]
        if not config.is_module_allowed(top):
            raise ImportValidationError(f"Import of module '{top}' is not allowed")
        entries = fromlist or ()
        for entry in entries:
            if entry != "*":
                sub_top = f"{name}.{entry}".split(".")[0]
                if not config.is_module_allowed(sub_top):
                    raise ImportValidationError(f"Import of module '{sub_top}' is not allowed")
        return importlib.__import__(name, globals, locals, entries, level)

    return safe_import


def sanitize_sys_modules(config: SecurityConfig) -> None:
    if "*" in config.stdlib_allow or "*" in config.external_allow:
        return

    allowed = set(config.stdlib_allow) | set(config.external_allow)
    for module_name in list(sys.modules):
        if module_name in RUNNER_MODULES_KEEP:
            continue
        if any(module_name.startswith(prefix) for prefix in RUNNER_MODULE_PREFIXES):
            continue
        top = module_name.split(".")[0]
        if top in allowed:
            continue
        del sys.modules[module_name]


def make_print_fn(logs: list[str], *, max_calls: int) -> Callable[..., None]:
    state = {"count": 0}

    def _serialize(value: Any) -> str:
        try:
            return json.dumps(value, ensure_ascii=False, default=_json_default)
        except TypeError:
            return repr(value)

    def _json_default(value: Any) -> str:
        return f"[Circular {type(value).__name__}]"

    def print_fn(*args: Any, **kwargs: Any) -> None:
        if state["count"] >= max_calls:
            return
        sep = kwargs.get("sep", " ")
        end = kwargs.get("end", "\n")
        rendered = sep.join(_serialize(a) for a in args) + str(end)
        if len(rendered) > 10_000:
            rendered = rendered[:10_000] + "…\n"
        logs.append(rendered)
        state["count"] += 1

    return print_fn


def clear_environment_if_blocked(config: SecurityConfig) -> None:
    if not config.block_env_access:
        return
    import os

    os.environ.clear()
