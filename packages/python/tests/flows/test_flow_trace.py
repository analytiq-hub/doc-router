from __future__ import annotations

import pytest

import analytiq_data as ad


def test_append_trace_buffers_by_node() -> None:
    ctx = ad.flows.ExecutionContext(
        organization_id="org",
        execution_id="e1",
        flow_id="f1",
        flow_revid="r1",
        mode="manual",
        trigger_data={},
        run_data={},
        analytiq_client=None,
        flow_log_level="INFO",
    )
    ctx.active_trace_node_id = "n1"
    ad.flows.append_trace(ctx, None, level="info", kind="engine", message="step")
    ad.flows.trace_http(
        ctx,
        "n1",
        method="GET",
        url="https://example.com",
        status_code=404,
        duration_ms=12,
        response_preview="not found",
    )
    assert len(ctx.node_traces["n1"]) == 2
    assert ctx.node_traces["n1"][1]["kind"] == "http"
    assert ctx.node_traces["n1"][1]["detail"]["status_code"] == 404


def test_pop_node_trace_returns_and_clears() -> None:
    ctx = ad.flows.ExecutionContext(
        organization_id="org",
        execution_id="e1",
        flow_id="f1",
        flow_revid="r1",
        mode="manual",
        trigger_data={},
        run_data={},
        analytiq_client=None,
        flow_log_level="INFO",
    )
    ad.flows.append_trace(ctx, "n2", level="warn", kind="validation", message="bad")
    popped = ad.flows.pop_node_trace(ctx, "n2")
    assert popped is not None
    assert popped[0]["message"] == "bad"
    assert ad.flows.pop_node_trace(ctx, "n2") is None


def test_trace_event_cap() -> None:
    ctx = ad.flows.ExecutionContext(
        organization_id="org",
        execution_id="e1",
        flow_id="f1",
        flow_revid="r1",
        mode="manual",
        trigger_data={},
        run_data={},
        analytiq_client=None,
        flow_log_level="TRACE",
    )
    from analytiq_data.flows.trace import MAX_TRACE_EVENTS_PER_NODE

    cap = MAX_TRACE_EVENTS_PER_NODE
    for i in range(cap + 5):
        ad.flows.append_trace(ctx, "n1", level="debug", kind="engine", message=str(i))
    assert len(ctx.node_traces["n1"]) == cap


@pytest.mark.asyncio
async def test_engine_persists_http_trace_on_failure() -> None:
    ad.flows.register_builtin_nodes()

    class _HttpFailNode:
        key = "tests.http_fail"
        label = "HTTP Fail"
        description = "Test HTTP trace node."
        category = "Test"
        is_trigger = False
        is_merge = False
        min_inputs = 1
        max_inputs = 1
        outputs = 1
        output_labels = ["main"]
        icon_key = None
        parameter_schema = {"type": "object", "properties": {}, "additionalProperties": False}

        def validate_parameters(self, params):
            return []

        async def execute(self, context, node, inputs):
            ad.flows.trace_http(
                context,
                node["id"],
                method="GET",
                url="https://api.example.com/missing",
                status_code=404,
                duration_ms=50,
                response_preview='{"error":"missing"}',
            )
            raise RuntimeError("upstream 404")

    ad.flows.register(_HttpFailNode())
    nodes = [
        {
            "id": "t1",
            "name": "Start",
            "type": "flows.trigger.manual",
            "position": [0, 0],
            "parameters": {},
            "disabled": False,
            "on_error": "stop",
        },
        {
            "id": "h1",
            "name": "HTTP Fail",
            "type": "tests.http_fail",
            "position": [200, 0],
            "parameters": {},
            "disabled": False,
            "on_error": "stop",
        },
    ]
    connections = {"t1": {"main": [[{"dest_node_id": "h1", "connection_type": "main", "index": 0}]]}}
    rev = {"nodes": nodes, "connections": connections, "settings": {}, "pin_data": None}
    ctx = ad.flows.ExecutionContext(
        organization_id="org",
        execution_id="e1",
        flow_id="f1",
        flow_revid="r1",
        mode="manual",
        trigger_data={},
        run_data={},
        analytiq_client=None,
    )
    with pytest.raises(RuntimeError, match="upstream 404"):
        await ad.flows.run_flow(context=ctx, revision=rev)

    entry = ctx.run_data["h1"]
    trace = entry.get("trace")
    assert isinstance(trace, list)
    assert len(trace) == 1
    assert trace[0]["kind"] == "http"
    assert trace[0]["detail"]["status_code"] == 404


@pytest.mark.asyncio
async def test_persist_run_data_sets_last_node_executed(monkeypatch) -> None:
    import analytiq_data as ad

    saved: dict = {}

    class _FakeFlowExecutions:
        async def update_one(self, _filter, update):
            saved["update"] = update

    class _FakeDb:
        flow_executions = _FakeFlowExecutions()

    monkeypatch.setattr(ad.common, "get_async_db", lambda _c: _FakeDb())

    ctx = ad.flows.ExecutionContext(
        organization_id="org",
        execution_id="64f3a1b2c3d4e5f6a7b8c9d0",
        flow_id="f1",
        flow_revid="r1",
        mode="manual",
        trigger_data={},
        run_data={"n1": {"status": "success", "data": {"main": [[]]}}},
        analytiq_client=object(),
    )
    await ad.flows.persist_run_data(ctx, ctx.run_data, last_node_executed="n1")
    assert saved["update"]["$set"]["last_node_executed"] == "n1"
