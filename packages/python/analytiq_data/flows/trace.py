"""Structured trace events for flow node runs (see ``docs/docrouter_fulltrace.md``)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from .org_log_level import flow_log_level_includes, normalize_flow_log_level

if TYPE_CHECKING:
    from .context import ExecutionContext

MAX_TRACE_EVENTS_PER_NODE = 200
MAX_PREVIEW_LEN = 2048
TRACE_OVERFLOW_KIND = "trace_overflow"

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


def _record_trace_overflow(buf: list[dict[str, Any]]) -> None:
    """Append or update a single overflow sentinel (newest events are dropped)."""

    for ev in buf:
        if ev.get("kind") == TRACE_OVERFLOW_KIND:
            detail = ev.setdefault("detail", {})
            dropped = int(detail.get("dropped_count") or 0) + 1
            detail["dropped_count"] = dropped
            detail["cap"] = MAX_TRACE_EVENTS_PER_NODE
            ev["message"] = (
                f"Trace buffer full ({MAX_TRACE_EVENTS_PER_NODE} events); "
                f"{dropped} newer event(s) dropped"
            )
            ev["ts"] = datetime.now(UTC).isoformat()
            return

    buf.append(
        {
            "ts": datetime.now(UTC).isoformat(),
            "level": "warn",
            "kind": TRACE_OVERFLOW_KIND,
            "message": (
                f"Trace buffer full ({MAX_TRACE_EVENTS_PER_NODE} events); "
                "1 newer event(s) dropped"
            ),
            "detail": {"dropped_count": 1, "cap": MAX_TRACE_EVENTS_PER_NODE},
        }
    )


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
    if not flow_log_level_includes(getattr(context, "flow_log_level", None), level):
        return
    buf = _trace_buffer(context, nid)
    content_count = sum(1 for ev in buf if ev.get("kind") != TRACE_OVERFLOW_KIND)
    if content_count >= MAX_TRACE_EVENTS_PER_NODE:
        _record_trace_overflow(buf)
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


def trace_http_on_success(
    context: ExecutionContext,
    node_id: str | None,
    *,
    method: str,
    url: str,
    status_code: int,
    duration_ms: int,
    response_preview: str | None = None,
) -> None:
    """Emit a successful HTTP trace when the org ``flow_log_level`` is INFO or TRACE."""

    org = normalize_flow_log_level(getattr(context, "flow_log_level", None))
    if flow_log_level_includes(org, "debug"):
        level: TraceLevel = "debug"
    elif flow_log_level_includes(org, "info"):
        level = "info"
    else:
        return
    trace_http(
        context,
        node_id,
        method=method,
        url=url,
        status_code=status_code,
        duration_ms=duration_ms,
        response_preview=response_preview,
        level=level,
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
    """Emit a successful HTTP trace only when the org ``flow_log_level`` is TRACE."""

    if not flow_log_level_includes(getattr(context, "flow_log_level", None), "debug"):
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
