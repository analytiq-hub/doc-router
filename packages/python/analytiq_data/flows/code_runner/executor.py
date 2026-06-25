from __future__ import annotations

import traceback
from typing import Any

from .builtins import (
    build_filtered_builtins,
    clear_environment_if_blocked,
    make_print_fn,
    sanitize_sys_modules,
)
from .config import MAX_PRINT_CALLS, SecurityConfig
from .rpc import ChildRpcClient, make_child_rpc_functions
from .validation import CodeValidationError, validate_code_output


class ExecutionFailure(RuntimeError):
    def __init__(self, message: str, *, stack: str | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.stack = stack


def _error_item(
    message: str,
    *,
    context: dict[str, Any],
    paired_item: int | None = None,
) -> dict[str, Any]:
    node_id = context.get("node_id")
    node_name = context.get("node_name") or node_id
    item: dict[str, Any] = {
        "json": {
            "_error": {
                "message": message,
                "node_id": node_id,
                "node_name": node_name,
            }
        }
    }
    if paired_item is not None:
        item["paired_item"] = paired_item
    return item


def execute_task(
    *,
    code: str,
    mode: str,
    items: list[dict[str, Any]],
    context: dict[str, Any],
    config: SecurityConfig,
    continue_on_fail: bool,
    max_payload_bytes: int,
) -> tuple[list[dict[str, Any]], list[str]]:
    if mode not in ("all_items", "per_item"):
        raise ExecutionFailure(f"Invalid mode: {mode}")

    logs: list[str] = []
    clear_environment_if_blocked(config)
    rpc_client = ChildRpcClient(max_payload_bytes=max_payload_bytes)
    read_binary, store_binary = make_child_rpc_functions(rpc_client)

    print_fn = make_print_fn(logs, max_calls=MAX_PRINT_CALLS)

    ns: dict[str, Any] = {
        "__builtins__": build_filtered_builtins(config),
        "read_binary": read_binary,
        "store_binary": store_binary,
        "print": print_fn,
        "log": print_fn,
    }

    sanitize_sys_modules(config)

    try:
        exec(code, ns, ns)
    except Exception as e:
        raise ExecutionFailure(
            f"Code compile/exec failed:\n{traceback.format_exc()}",
            stack=traceback.format_exc(),
        ) from e

    run_fn = ns.get("run")
    if not callable(run_fn):
        raise ExecutionFailure("Code must define a callable `run(items, context)`")

    try:
        if mode == "all_items":
            try:
                raw = run_fn(items, context)
            except Exception as e:
                if continue_on_fail:
                    return [_error_item(str(e), context=context)], logs
                raise ExecutionFailure(
                    f"Code execution failed:\n{traceback.format_exc()}",
                    stack=traceback.format_exc(),
                ) from e
            try:
                return validate_code_output(raw), logs
            except CodeValidationError as e:
                raise ExecutionFailure(e.message, stack=traceback.format_exc()) from e

        out: list[dict[str, Any]] = []
        for idx, item in enumerate(items):
            try:
                raw = run_fn([item], context)
            except Exception as e:
                if continue_on_fail:
                    out.append(_error_item(str(e), context=context, paired_item=idx))
                    continue
                raise ExecutionFailure(
                    f"Code execution failed at item {idx}:\n{traceback.format_exc()}",
                    stack=traceback.format_exc(),
                ) from e
            try:
                validated = validate_code_output(raw)
            except CodeValidationError as e:
                raise ExecutionFailure(e.message, stack=traceback.format_exc()) from e
            for row in validated:
                if row.get("paired_item") is None:
                    row = dict(row)
                    row["paired_item"] = idx
                out.append(row)
        return out, logs
    except ExecutionFailure:
        raise
    except Exception as e:
        if continue_on_fail:
            return [_error_item(str(e), context=context)], logs
        raise ExecutionFailure(
            f"Code execution failed:\n{traceback.format_exc()}",
            stack=traceback.format_exc(),
        ) from e
