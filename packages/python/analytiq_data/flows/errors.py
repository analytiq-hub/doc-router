"""Execution error envelopes for flow runs (see ``docs/docrouter_fulltrace.md``)."""

from __future__ import annotations

import traceback
from typing import Any

MAX_STACK_CHARS = 32_000


def _truncate(text: str | None, limit: int) -> str | None:
    if text is None:
        return None
    if len(text) <= limit:
        return text
    return text[: limit - 24] + "\n... [stack truncated]"


def http_code_from_exception(exc: BaseException) -> int | None:
    code = getattr(exc, "status_code", None)
    return code if isinstance(code, int) else None


def node_error_envelope(
    exc: BaseException,
    *,
    node_id: str,
    node_name: str,
    include_stack: bool = True,
) -> dict[str, Any]:
    """Build ``run_data[node_id].error`` payload."""

    stack: str | None = None
    if include_stack:
        stack = _truncate(traceback.format_exc(), MAX_STACK_CHARS)
    http_code = http_code_from_exception(exc)
    out: dict[str, Any] = {
        "message": str(exc),
        "node_id": node_id,
        "node_name": node_name,
        "stack": stack,
        "cause": type(exc).__name__,
    }
    if http_code is not None:
        out["http_code"] = http_code
    return out


def latest_node_error_from_run_data(run_data: dict[str, Any] | None) -> dict[str, Any] | None:
    """Return the error envelope from the highest ``execution_index`` failed node."""

    if not run_data:
        return None
    best: dict[str, Any] | None = None
    best_idx = -1
    for raw in run_data.values():
        if not isinstance(raw, dict):
            continue
        err = raw.get("error")
        if not isinstance(err, dict):
            continue
        msg = err.get("message")
        if not isinstance(msg, str) or not msg.strip():
            continue
        idx_raw = raw.get("execution_index")
        idx = idx_raw if isinstance(idx_raw, int) else best_idx + 1
        if idx >= best_idx:
            best_idx = idx
            best = err
    return best


def execution_error_envelope(
    exc: BaseException,
    *,
    run_data: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Top-level ``flow_executions.error`` payload.

    Prefer a node-level error already written to ``run_data`` when the engine stopped mid-run.
    """

    from_node = latest_node_error_from_run_data(run_data)
    if from_node is not None:
        return dict(from_node)

    stack = _truncate(traceback.format_exc(), MAX_STACK_CHARS)
    http_code = http_code_from_exception(exc)
    out: dict[str, Any] = {
        "message": str(exc),
        "node_id": None,
        "node_name": None,
        "stack": stack,
        "cause": type(exc).__name__,
    }
    if http_code is not None:
        out["http_code"] = http_code
    return out
