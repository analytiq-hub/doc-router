from __future__ import annotations

import pytest

import analytiq_data as ad


def test_normalize_flow_log_level_defaults_to_error() -> None:
    assert ad.flows.normalize_flow_log_level(None) == "ERROR"
    assert ad.flows.normalize_flow_log_level("trace") == "TRACE"
    assert ad.flows.normalize_flow_log_level("bogus") == "ERROR"


def test_flow_log_level_includes_event_levels() -> None:
    assert ad.flows.flow_log_level_includes("ERROR", "error") is True
    assert ad.flows.flow_log_level_includes("ERROR", "info") is False
    assert ad.flows.flow_log_level_includes("INFO", "info") is True
    assert ad.flows.flow_log_level_includes("INFO", "debug") is False
    assert ad.flows.flow_log_level_includes("TRACE", "debug") is True


def test_flow_log_level_includes_none_defaults_to_error_only() -> None:
    """Missing org level (legacy contexts) must still record error-level trace events."""

    assert ad.flows.flow_log_level_includes(None, "error") is True
    assert ad.flows.flow_log_level_includes(None, "info") is False
    assert ad.flows.flow_log_level_includes(None, "debug") is False


def test_append_trace_on_context_without_flow_log_level_records_errors() -> None:
    """``getattr(context, 'flow_log_level', None)`` on pre-field execution contexts."""

    class _LegacyContext:
        active_trace_node_id = "n1"
        node_traces: dict = {}

    ctx = _LegacyContext()
    ad.flows.append_trace(ctx, None, level="error", kind="http", message="upstream failed")
    assert len(ctx.node_traces["n1"]) == 1
    ad.flows.append_trace(ctx, None, level="info", kind="engine", message="step")
    assert len(ctx.node_traces["n1"]) == 1


def test_append_trace_respects_org_flow_log_level() -> None:
    ctx = ad.flows.ExecutionContext(
        organization_id="org",
        execution_id="64f3a1b2c3d4e5f6a7b8c9d0",
        flow_id="f1",
        flow_revid="r1",
        mode="manual",
        trigger_data={},
        run_data={},
        analytiq_client=None,
        flow_log_level="ERROR",
    )
    ctx.active_trace_node_id = "n1"
    ad.flows.append_trace(ctx, None, level="info", kind="http", message="ok")
    assert ctx.node_traces.get("n1") is None

    ctx.flow_log_level = "INFO"
    ad.flows.append_trace(ctx, None, level="info", kind="http", message="ok")
    assert len(ctx.node_traces["n1"]) == 1


@pytest.mark.asyncio
async def test_trace_http_on_success_requires_info_or_trace() -> None:
    ctx = ad.flows.ExecutionContext(
        organization_id="org",
        execution_id="64f3a1b2c3d4e5f6a7b8c9d1",
        flow_id="f1",
        flow_revid="r1",
        mode="manual",
        trigger_data={},
        run_data={},
        analytiq_client=None,
        flow_log_level="ERROR",
    )
    ctx.active_trace_node_id = "n1"
    ad.flows.trace_http_on_success(
        ctx,
        "n1",
        method="GET",
        url="https://example.com",
        status_code=200,
        duration_ms=10,
        response_preview="ok",
    )
    assert not ctx.node_traces

    ctx.flow_log_level = "TRACE"
    ad.flows.trace_http_on_success(
        ctx,
        "n1",
        method="GET",
        url="https://example.com",
        status_code=200,
        duration_ms=10,
        response_preview="ok",
    )
    assert len(ctx.node_traces["n1"]) == 1
    assert ctx.node_traces["n1"][0]["level"] == "debug"
