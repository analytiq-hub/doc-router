"""Structured trace events for flow node runs (see ``docs/docrouter_fulltrace.md``)."""

from __future__ import annotations

import os
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .context import ExecutionContext

MAX_TRACE_EVENTS_PER_NODE = 200
MAX_PREVIEW_LEN = 2048

TraceLevel = str
TraceKind = str


def _truncate_preview(text: str | None) -> str | None:
    if text is None:
        return None
    if len(text) <= MAX_PREVIEW_LEN:
        return text
    return text[: MAX_PREVIEW_LEN - 24] + "\n... [response truncated]"


def _trace_buffer(context: ExecutionContext, node_id: str) -> list[dict[str, Any]]:
    buf = context.node_traces.get(node_id)
    if buf is None:
        buf = []
        context.node_traces[node_id] = buf
    return buf


def append_trace(
    context: ExecutionContext,
    node_id: str | None,
    *,
    level: TraceLevel,
    kind: TraceKind,
    message: str,
    detail: dict[str, Any] | None = None,
) -> None:
    """Append a trace event for ``node_id`` (defaults to ``context.active_trace_node_id``)."""

    nid = node_id or context.active_trace_node_id
    if not nid:
        return
    buf = _trace_buffer(context, nid)
    if len(buf) >= MAX_TRACE_EVENTS_PER_NODE:
        return
    event: dict[str, Any] = {
        "ts": datetime.now(UTC).isoformat(),
        "level": level,
        "kind": kind,
        "message": message,
    }
    if detail:
        event["detail"] = detail
    buf.append(event)


def pop_node_trace(context: ExecutionContext, node_id: str) -> list[dict[str, Any]] | None:
    """Remove and return buffered trace events for a node (mirrors ``node_logs.pop``)."""

    if not hasattr(context, "node_traces"):
        return None
    events = context.node_traces.pop(node_id, None)
    if not events:
        return None
    return events


def trace_http(
    context: ExecutionContext,
    node_id: str | None,
    *,
    method: str,
    url: str,
    status_code: int | None = None,
    duration_ms: int | None = None,
    response_preview: str | None = None,
    level: TraceLevel | None = None,
) -> None:
    """Record an HTTP request/response trace event."""

    if status_code is not None and status_code >= 400:
        resolved_level: TraceLevel = level or "error"
    elif status_code is not None:
        resolved_level = level or "info"
    else:
        resolved_level = level or "error"

    preview = _truncate_preview(response_preview)
    if status_code is not None:
        msg = f"{method.upper()} {url} → {status_code}"
    else:
        msg = f"{method.upper()} {url} failed"

    detail: dict[str, Any] = {
        "method": method.upper(),
        "url": url,
    }
    if status_code is not None:
        detail["status_code"] = status_code
    if duration_ms is not None:
        detail["duration_ms"] = duration_ms
    if preview is not None:
        detail["response_preview"] = preview

    append_trace(
        context,
        node_id,
        level=resolved_level,
        kind="http",
        message=msg,
        detail=detail,
    )


def trace_http_on_debug(
    context: ExecutionContext,
    node_id: str | None,
    *,
    method: str,
    url: str,
    status_code: int,
    duration_ms: int,
    response_preview: str | None = None,
) -> None:
    """Emit a success HTTP trace when ``LOG_LEVEL=DEBUG``."""

    if os.getenv("LOG_LEVEL", "INFO").upper() != "DEBUG":
        return
    trace_http(
        context,
        node_id,
        method=method,
        url=url,
        status_code=status_code,
        duration_ms=duration_ms,
        response_preview=response_preview,
        level="debug",
    )
