"""Tests for `flows.http_request` (see docs/docrouter_http_request.md)."""

from __future__ import annotations

import json
from unittest.mock import patch

import httpx
import pytest

import analytiq_data as ad
from analytiq_data.flows.nodes.http_request import FlowsHttpRequestNode

# Capture real constructor before tests patch `http_request.httpx.AsyncClient`.
_RealAsyncClient = httpx.AsyncClient


@pytest.fixture
def http_node() -> FlowsHttpRequestNode:
    return FlowsHttpRequestNode()


def test_http_request_parameter_schema_display_extensions(http_node: FlowsHttpRequestNode):
    """UI hints are embedded for schema-driven parameter forms (see docs/flow_parameter_schema_ui_plan.md)."""
    schema = http_node.parameter_schema
    props = schema["properties"]
    assert props["query_params"].get("x-ui-widget") == "name_value_list"
    assert props["body_json"].get("x-ui-show-when") == {"field": "body_mode", "in": ["json"]}
    assert props["body_raw"].get("x-ui-show-when") == {"field": "body_mode", "equals": "raw"}
    assert list(props.keys()) == [
        "method",
        "url",
        "query_params",
        "headers",
        "body_mode",
        "body_json",
        "body_params",
        "body_raw",
        "body_content_type",
        "full_response",
        "never_error",
        "follow_redirects",
        "timeout_seconds",
    ]


@pytest.fixture
def minimal_ctx() -> ad.flows.ExecutionContext:
    return ad.flows.ExecutionContext(
        organization_id="org1",
        execution_id="e1",
        flow_id="f1",
        flow_revid="r1",
        mode="manual",
        trigger_data={},
        run_data={},
        analytiq_client=None,
    )


@pytest.mark.asyncio
async def test_get_static_url(http_node: FlowsHttpRequestNode, minimal_ctx: ad.flows.ExecutionContext):
    transport = httpx.MockTransport(
        lambda request: httpx.Response(200, json={"ok": True}, request=request)
    )
    with patch(
        "analytiq_data.flows.nodes.http_request.httpx.AsyncClient",
        side_effect=lambda **kw: _RealAsyncClient(transport=transport, **kw),
    ):
        item = ad.flows.FlowItem(json={"x": 1}, binary={}, meta={}, paired_item=None)
        out = await http_node.execute(
            minimal_ctx,
            {
                "id": "n1",
                "parameters": {
                    "method": "GET",
                    "url": "https://example.com/ping",
                    "headers": [],
                    "query_params": [],
                    "body_mode": "none",
                },
            },
            [[item]],
        )

    assert out[0][0].json["body"] == {"ok": True}


@pytest.mark.asyncio
async def test_post_json_keypair(http_node: FlowsHttpRequestNode, minimal_ctx: ad.flows.ExecutionContext):
    requests_seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests_seen.append(request)
        return httpx.Response(200, json={"saved": True}, request=request)

    transport = httpx.MockTransport(handler)

    with patch(
        "analytiq_data.flows.nodes.http_request.httpx.AsyncClient",
        side_effect=lambda **kw: _RealAsyncClient(transport=transport, **kw),
    ):
        item = ad.flows.FlowItem(json={"a": 1}, binary={}, meta={}, paired_item=None)
        await http_node.execute(
            minimal_ctx,
            {
                "id": "n1",
                "parameters": {
                    "method": "POST",
                    "url": "https://api.example.com/v1/items",
                    "headers": [],
                    "query_params": [],
                    "body_mode": "json_keypair",
                    "body_params": [
                        {"name": "email", "value": "x@y.com"},
                        {"name": "name", "value": "Test"},
                    ],
                },
            },
            [[item]],
        )

    assert len(requests_seen) == 1
    sent = json.loads(requests_seen[0].content.decode())
    assert sent == {"email": "x@y.com", "name": "Test"}
    assert requests_seen[0].headers.get("content-type", "").startswith("application/json")


@pytest.mark.asyncio
async def test_body_json_from_expression(http_node: FlowsHttpRequestNode, minimal_ctx: ad.flows.ExecutionContext):
    requests_seen: list[httpx.Request] = []

    transport = httpx.MockTransport(
        lambda request: (
            requests_seen.append(request) or httpx.Response(200, json={}, request=request)
        )
    )

    with patch(
        "analytiq_data.flows.nodes.http_request.httpx.AsyncClient",
        side_effect=lambda **kw: _RealAsyncClient(transport=transport, **kw),
    ):
        item = ad.flows.FlowItem(
            json={"payload": '{"hello": "world"}'},
            binary={},
            meta={},
            paired_item=None,
        )
        await http_node.execute(
            minimal_ctx,
            {
                "id": "n1",
                "parameters": {
                    "method": "POST",
                    "url": "https://example.com/post",
                    "headers": [],
                    "query_params": [],
                    "body_mode": "json",
                    "body_json": "=$json['payload']",
                },
            },
            [[item]],
        )

    assert json.loads(requests_seen[0].content.decode()) == {"hello": "world"}


@pytest.mark.asyncio
async def test_http_header_auth_slot(
    http_node: FlowsHttpRequestNode,
    minimal_ctx: ad.flows.ExecutionContext,
    monkeypatch: pytest.MonkeyPatch,
):
    async def fake_fetch(org_id: str, cred_id: str) -> dict:
        assert org_id == "org1"
        assert cred_id == "deadbeefdeadbeefdeadbeef"
        return {"name": "Authorization", "value": "Bearer secret"}

    monkeypatch.setattr(
        "analytiq_data.flows.fetch_credential_fields",
        fake_fetch,
    )

    requests_seen: list[httpx.Request] = []
    transport = httpx.MockTransport(
        lambda request: (
            requests_seen.append(request) or httpx.Response(200, json={}, request=request)
        )
    )

    with patch(
        "analytiq_data.flows.nodes.http_request.httpx.AsyncClient",
        side_effect=lambda **kw: _RealAsyncClient(transport=transport, **kw),
    ):
        item = ad.flows.FlowItem(json={}, binary={}, meta={}, paired_item=None)
        await http_node.execute(
            minimal_ctx,
            {
                "id": "n1",
                "credentials": {"httpHeaderAuth": "deadbeefdeadbeefdeadbeef"},
                "parameters": {
                    "method": "GET",
                    "url": "https://example.com/x",
                    "headers": [],
                    "query_params": [],
                    "body_mode": "none",
                },
            },
            [[item]],
        )

    assert requests_seen[0].headers.get("Authorization") == "Bearer secret"


@pytest.mark.asyncio
async def test_http_query_auth_slot(
    http_node: FlowsHttpRequestNode,
    minimal_ctx: ad.flows.ExecutionContext,
    monkeypatch: pytest.MonkeyPatch,
):
    async def fake_fetch(org_id: str, cred_id: str) -> dict:
        return {"name": "api_key", "value": "abc123"}

    monkeypatch.setattr(
        "analytiq_data.flows.fetch_credential_fields",
        fake_fetch,
    )

    requests_seen: list[httpx.Request] = []
    transport = httpx.MockTransport(
        lambda request: (
            requests_seen.append(request) or httpx.Response(200, json={}, request=request)
        )
    )

    with patch(
        "analytiq_data.flows.nodes.http_request.httpx.AsyncClient",
        side_effect=lambda **kw: _RealAsyncClient(transport=transport, **kw),
    ):
        item = ad.flows.FlowItem(json={}, binary={}, meta={}, paired_item=None)
        await http_node.execute(
            minimal_ctx,
            {
                "id": "n1",
                "credentials": {"httpQueryAuth": "deadbeefdeadbeefdeadbeef"},
                "parameters": {
                    "method": "GET",
                    "url": "https://example.com/x",
                    "headers": [],
                    "query_params": [],
                    "body_mode": "none",
                },
            },
            [[item]],
        )

    assert str(requests_seen[0].url).endswith("api_key=abc123")


@pytest.mark.asyncio
async def test_non_2xx_raises_when_not_never_error(
    http_node: FlowsHttpRequestNode,
    minimal_ctx: ad.flows.ExecutionContext,
):
    transport = httpx.MockTransport(
        lambda request: httpx.Response(404, text="missing", request=request)
    )

    with patch(
        "analytiq_data.flows.nodes.http_request.httpx.AsyncClient",
        side_effect=lambda **kw: _RealAsyncClient(transport=transport, **kw),
    ):
        item = ad.flows.FlowItem(json={}, binary={}, meta={}, paired_item=None)
        with pytest.raises(RuntimeError, match="HTTP 404"):
            await http_node.execute(
                minimal_ctx,
                {
                    "id": "n1",
                    "parameters": {
                        "method": "GET",
                        "url": "https://example.com/missing",
                        "headers": [],
                        "query_params": [],
                        "body_mode": "none",
                        "never_error": False,
                    },
                },
                [[item]],
            )


@pytest.mark.asyncio
async def test_non_2xx_never_error_emits_item(
    http_node: FlowsHttpRequestNode,
    minimal_ctx: ad.flows.ExecutionContext,
):
    transport = httpx.MockTransport(
        lambda request: httpx.Response(404, text="gone", request=request)
    )

    with patch(
        "analytiq_data.flows.nodes.http_request.httpx.AsyncClient",
        side_effect=lambda **kw: _RealAsyncClient(transport=transport, **kw),
    ):
        item = ad.flows.FlowItem(json={}, binary={}, meta={}, paired_item=None)
        out = await http_node.execute(
            minimal_ctx,
            {
                "id": "n1",
                "parameters": {
                    "method": "GET",
                    "url": "https://example.com/missing",
                    "headers": [],
                    "query_params": [],
                    "body_mode": "none",
                    "never_error": True,
                    "full_response": True,
                },
            },
            [[item]],
        )

    j = out[0][0].json
    assert j["status_code"] == 404
    assert j["body"] == "gone"


@pytest.mark.asyncio
async def test_full_response_includes_headers(
    http_node: FlowsHttpRequestNode,
    minimal_ctx: ad.flows.ExecutionContext,
):
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            200,
            json={"a": 1},
            headers={"x-test": "1"},
            request=request,
        )
    )

    with patch(
        "analytiq_data.flows.nodes.http_request.httpx.AsyncClient",
        side_effect=lambda **kw: _RealAsyncClient(transport=transport, **kw),
    ):
        item = ad.flows.FlowItem(json={}, binary={}, meta={}, paired_item=None)
        out = await http_node.execute(
            minimal_ctx,
            {
                "id": "n1",
                "parameters": {
                    "method": "GET",
                    "url": "https://example.com/",
                    "headers": [],
                    "query_params": [],
                    "body_mode": "none",
                    "full_response": True,
                },
            },
            [[item]],
        )

    assert out[0][0].json["status_code"] == 200
    assert out[0][0].json["headers"].get("x-test") == "1"


def test_validate_parameters_errors(http_node: FlowsHttpRequestNode):
    assert http_node.validate_parameters({"method": "GET", "url": ""})
    errs = http_node.validate_parameters({"method": "FOO", "url": "http://x"})
    assert errs and "method" in errs[0].lower()


@pytest.mark.asyncio
async def test_connect_error_propagates(http_node: FlowsHttpRequestNode, minimal_ctx: ad.flows.ExecutionContext):
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    transport = httpx.MockTransport(handler)
    with patch(
        "analytiq_data.flows.nodes.http_request.httpx.AsyncClient",
        side_effect=lambda **kw: _RealAsyncClient(transport=transport, **kw),
    ):
        item = ad.flows.FlowItem(json={}, binary={}, meta={}, paired_item=None)
        with pytest.raises(httpx.ConnectError):
            await http_node.execute(
                minimal_ctx,
                {"id": "n1", "parameters": {"method": "GET", "url": "https://unreachable.invalid/"}},
                [[item]],
            )


@pytest.mark.asyncio
async def test_timeout_error_propagates(http_node: FlowsHttpRequestNode, minimal_ctx: ad.flows.ExecutionContext):
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.TimeoutException("timed out", request=request)

    transport = httpx.MockTransport(handler)
    with patch(
        "analytiq_data.flows.nodes.http_request.httpx.AsyncClient",
        side_effect=lambda **kw: _RealAsyncClient(transport=transport, **kw),
    ):
        item = ad.flows.FlowItem(json={}, binary={}, meta={}, paired_item=None)
        with pytest.raises(httpx.TimeoutException):
            await http_node.execute(
                minimal_ctx,
                {
                    "id": "n1",
                    "parameters": {
                        "method": "GET",
                        "url": "https://slow.invalid/",
                        "timeout_seconds": 1,
                    },
                },
                [[item]],
            )
