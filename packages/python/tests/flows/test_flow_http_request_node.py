"""Tests for `flows.http_request` (see docs/docrouter_http_request.md)."""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import patch

import httpx
import pytest
from jsonschema import Draft7Validator

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
    assert "allOf" not in schema
    assert props["query_params"].get("x-ui-widget") == "name_value_list"
    assert props["body_json"].get("x-ui-widget") == "json"
    assert props["body_json"].get("x-ui-show-when") == {"field": "body_mode", "in": ["json"]}
    assert props["body_params"].get("x-ui-show-when") == {"field": "body_mode", "in": ["json_keypair", "form_urlencoded"]}
    assert props["body_raw"].get("x-ui-show-when") == {"field": "body_mode", "equals": "raw"}
    assert props["body_content_type"].get("x-ui-show-when") == {"field": "body_mode", "equals": "raw"}
    assert list(props.keys()) == [
        "method",
        "url",
        "query_params",
        "query_json",
        "headers",
        "headers_json",
        "body_mode",
        "body_json",
        "body_params",
        "body_raw",
        "body_content_type",
        "binary_property_name",
        "multipart_file_field_name",
        "multipart_fields",
        "full_response",
        "never_error",
        "follow_redirects",
        "max_redirects",
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
async def test_execute_forwards_incoming_binary_and_meta(http_node: FlowsHttpRequestNode, minimal_ctx: ad.flows.ExecutionContext):
    """Downstream HTTP output must not drop upstream ``FlowItem.binary`` (pass-by-reference)."""

    transport = httpx.MockTransport(
        lambda request: httpx.Response(200, json={"ok": True}, request=request)
    )
    with patch(
        "analytiq_data.flows.nodes.http_request.httpx.AsyncClient",
        side_effect=lambda **kw: _RealAsyncClient(transport=transport, **kw),
    ):
        pref = ad.flows.BinaryRef(mime_type="application/pdf", storage_id="files:x.pdf")
        item = ad.flows.FlowItem(
            json={"u": "https://example.com/api"},
            binary={"pdf": pref},
            meta={"item_index": 3, "trace": "a"},
            paired_item=1,
        )
        out = await http_node.execute(
            minimal_ctx,
            {
                "id": "http1",
                "parameters": {
                    "method": "GET",
                    "url": "https://example.com/api",
                    "body_mode": "none",
                },
            },
            [[item]],
        )
    row = out[0][0]
    assert row.binary["pdf"] is pref
    assert row.meta.get("trace") == "a"
    assert row.meta.get("item_index") == 3
    assert row.meta.get("source_node_id") == "http1"
    assert row.paired_item == 1


@pytest.mark.asyncio
async def test_execute_head_method(
    http_node: FlowsHttpRequestNode,
    minimal_ctx: ad.flows.ExecutionContext,
):
    seen_method: str | None = None

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal seen_method
        seen_method = request.method
        return httpx.Response(200, request=request)

    transport = httpx.MockTransport(handler)
    with patch(
        "analytiq_data.flows.nodes.http_request.httpx.AsyncClient",
        side_effect=lambda **kw: _RealAsyncClient(transport=transport, **kw),
    ):
        item = ad.flows.FlowItem(json={}, binary={}, meta={}, paired_item=None)
        await http_node.execute(
            minimal_ctx,
            {
                "id": "h1",
                "parameters": {"method": "HEAD", "url": "https://example.com/x", "body_mode": "none"},
            },
            [[item]],
        )
    assert seen_method == "HEAD"


@pytest.mark.asyncio
async def test_query_json_overwrites_query_params(
    http_node: FlowsHttpRequestNode,
    minimal_ctx: ad.flows.ExecutionContext,
):
    seen_qs: str | None = None

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal seen_qs
        seen_qs = str(request.url)
        return httpx.Response(200, json={"ok": True}, request=request)

    transport = httpx.MockTransport(handler)
    with patch(
        "analytiq_data.flows.nodes.http_request.httpx.AsyncClient",
        side_effect=lambda **kw: _RealAsyncClient(transport=transport, **kw),
    ):
        item = ad.flows.FlowItem(json={}, binary={}, meta={}, paired_item=None)
        await http_node.execute(
            minimal_ctx,
            {
                "id": "h1",
                "parameters": {
                    "method": "GET",
                    "url": "https://example.com/api",
                    "body_mode": "none",
                    "query_params": [{"name": "a", "value": "1"}, {"name": "b", "value": "2"}],
                    "query_json": '{"a": "9", "c": "3"}',
                },
            },
            [[item]],
        )
    assert seen_qs is not None
    assert "a=9" in seen_qs
    assert "c=3" in seen_qs
    assert "b=2" in seen_qs


@pytest.mark.asyncio
async def test_max_redirects_passed_to_httpx_client(
    http_node: FlowsHttpRequestNode,
    minimal_ctx: ad.flows.ExecutionContext,
):
    captured: dict[str, Any] = {}

    def capture_client(**kw: Any) -> httpx.AsyncClient:
        captured.clear()
        captured.update(kw)
        return _RealAsyncClient(
            transport=httpx.MockTransport(lambda r: httpx.Response(200, json={}, request=r)),
            **kw,
        )

    with patch(
        "analytiq_data.flows.nodes.http_request.httpx.AsyncClient",
        side_effect=capture_client,
    ):
        item = ad.flows.FlowItem(json={}, binary={}, meta={}, paired_item=None)
        await http_node.execute(
            minimal_ctx,
            {
                "id": "h1",
                "parameters": {
                    "method": "GET",
                    "url": "https://example.com/",
                    "body_mode": "none",
                    "follow_redirects": True,
                    "max_redirects": 7,
                },
            },
            [[item]],
        )
    assert captured.get("follow_redirects") is True
    assert captured.get("max_redirects") == 7


@pytest.mark.asyncio
async def test_execute_uploads_binary_as_raw_body(
    http_node: FlowsHttpRequestNode,
    minimal_ctx: ad.flows.ExecutionContext,
):
    """Binary body mode uploads item.binary[prop] as request body bytes."""

    seen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["content_type"] = request.headers.get("content-type")
        seen["body"] = request.read()
        return httpx.Response(200, json={"ok": True}, request=request)

    transport = httpx.MockTransport(handler)
    with patch(
        "analytiq_data.flows.nodes.http_request.httpx.AsyncClient",
        side_effect=lambda **kw: _RealAsyncClient(transport=transport, **kw),
    ):
        minimal_ctx.analytiq_client = object()
        blob = b"\x00\x01hello"
        item = ad.flows.FlowItem(
            json={},
            binary={"data": ad.flows.BinaryRef(mime_type="application/octet-stream", file_name="a.bin", data=blob)},
            meta={},
            paired_item=None,
        )
        await http_node.execute(
            minimal_ctx,
            {
                "id": "http1",
                "parameters": {
                    "method": "POST",
                    "url": "https://example.com/upload",
                    "body_mode": "binary",
                    "binary_property_name": "data",
                },
            },
            [[item]],
        )

    assert seen["content_type"] == "application/octet-stream"
    assert seen["body"] == blob


@pytest.mark.asyncio
async def test_execute_uploads_binary_as_multipart_form(
    http_node: FlowsHttpRequestNode,
    minimal_ctx: ad.flows.ExecutionContext,
):
    """multipart_form mode uploads item.binary[prop] as a multipart file field."""

    seen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        ct = request.headers.get("content-type") or ""
        seen["content_type"] = ct
        body = request.read()
        seen["body"] = body
        return httpx.Response(200, json={"ok": True}, request=request)

    transport = httpx.MockTransport(handler)
    with patch(
        "analytiq_data.flows.nodes.http_request.httpx.AsyncClient",
        side_effect=lambda **kw: _RealAsyncClient(transport=transport, **kw),
    ):
        minimal_ctx.analytiq_client = object()
        blob = b"PDFBYTES"
        item = ad.flows.FlowItem(
            json={},
            binary={
                "pdf": ad.flows.BinaryRef(
                    mime_type="application/pdf",
                    file_name="invoice.pdf",
                    data=blob,
                )
            },
            meta={},
            paired_item=None,
        )
        await http_node.execute(
            minimal_ctx,
            {
                "id": "http1",
                "parameters": {
                    "method": "POST",
                    "url": "https://example.com/upload",
                    "body_mode": "multipart_form",
                    "binary_property_name": "pdf",
                    "multipart_file_field_name": "file",
                    "multipart_fields": [{"name": "a", "value": "b"}],
                },
            },
            [[item]],
        )

    assert isinstance(seen["content_type"], str)
    assert "multipart/form-data" in str(seen["content_type"])
    body = seen["body"]
    assert isinstance(body, (bytes, bytearray))
    # Minimal invariants: form field name, filename, and payload are present.
    assert b'name="a"' in body
    assert b"\r\nb\r\n" in body
    assert b'name="file"' in body
    assert b'filename="invoice.pdf"' in body
    assert blob in body


@pytest.mark.asyncio
async def test_execute_binary_pdf_response_attachs_binaryref_under_data(
    http_node: FlowsHttpRequestNode,
    minimal_ctx: ad.flows.ExecutionContext,
):
    pdf_bytes = b"%PDF-1.7 hello"

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            content=pdf_bytes,
            headers={
                "content-type": 'application/pdf; charset=latin1',
                'Content-Disposition': 'attachment; filename="download-me.pdf"',
            },
            request=request,
        )

    transport = httpx.MockTransport(handler)
    with patch(
        "analytiq_data.flows.nodes.http_request.httpx.AsyncClient",
        side_effect=lambda **kw: _RealAsyncClient(transport=transport, **kw),
    ):
        item = ad.flows.FlowItem(json={"u": "https://example.com/file"}, binary={}, meta={}, paired_item=None)
        out = await http_node.execute(
            minimal_ctx,
            {
                "id": "n1",
                "parameters": {"method": "GET", "url": "https://example.com/file", "body_mode": "none"},
            },
            [[item]],
        )

    row = out[0][0]
    assert row.json["status_code"] == 200
    hdrs = row.json["headers"]
    assert hdrs.get("content-type") == "application/pdf; charset=latin1"
    assert hdrs.get("content-disposition") == 'attachment; filename="download-me.pdf"'
    assert "body" not in row.json
    ref = row.binary["data"]
    assert ref.mime_type == "application/pdf"
    assert ref.file_name == "download-me.pdf"
    assert ref.data == pdf_bytes


@pytest.mark.asyncio
async def test_execute_binary_response_merges_upstream_binary(
    http_node: FlowsHttpRequestNode,
    minimal_ctx: ad.flows.ExecutionContext,
):
    """New ``binary[\"data\"]`` from the HTTP response coexists with forwarded refs."""

    png = b"\x89PNG\r\n"

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            content=png,
            headers={"content-type": "image/png"},
            request=request,
        )

    transport = httpx.MockTransport(handler)
    with patch(
        "analytiq_data.flows.nodes.http_request.httpx.AsyncClient",
        side_effect=lambda **kw: _RealAsyncClient(transport=transport, **kw),
    ):
        pref = ad.flows.BinaryRef(mime_type="application/pdf", storage_id="files:upstream.pdf")
        item = ad.flows.FlowItem(json={"u": "https://example.com/i"}, binary={"pdf": pref}, meta={}, paired_item=None)
        out = await http_node.execute(
            minimal_ctx,
            {
                "id": "n1",
                "parameters": {"method": "GET", "url": "https://example.com/i", "body_mode": "none"},
            },
            [[item]],
        )

    row = out[0][0]
    assert row.binary["pdf"] is pref
    assert row.binary["data"].mime_type == "image/png"
    assert row.binary["data"].data == png


@pytest.mark.asyncio
async def test_execute_rejects_ssrf_loopback_before_http(http_node: FlowsHttpRequestNode, minimal_ctx: ad.flows.ExecutionContext):
    """SSRF guard blocks 127.0.0.1 before httpx runs (no network)."""

    item = ad.flows.FlowItem(json={"x": 1}, binary={}, meta={}, paired_item=None)
    with pytest.raises(RuntimeError, match="blocked"):
        await http_node.execute(
            minimal_ctx,
            {
                "id": "n1",
                "parameters": {
                    "method": "GET",
                    "url": "http://127.0.0.1/",
                    "headers": [],
                    "query_params": [],
                    "body_mode": "none",
                },
            },
            [[item]],
        )


@pytest.mark.asyncio
async def test_follow_redirect_rejected_when_location_is_blocked(
    http_node: FlowsHttpRequestNode, minimal_ctx: ad.flows.ExecutionContext,
):
    """Each redirect target is validated (blocks SSRF via Location to loopback)."""

    def handler(request: httpx.Request) -> httpx.Response:
        u = str(request.url)
        if u.startswith("http://8.8.8.8"):
            return httpx.Response(302, headers={"location": "http://127.0.0.1/evil"}, request=request)
        return httpx.Response(200, json={"ok": True}, request=request)

    transport = httpx.MockTransport(handler)
    with patch(
        "analytiq_data.flows.nodes.http_request.httpx.AsyncClient",
        side_effect=lambda **kw: _RealAsyncClient(transport=transport, **kw),
    ):
        item = ad.flows.FlowItem(json={"x": 1}, binary={}, meta={}, paired_item=None)
        with pytest.raises(RuntimeError, match="blocked"):
            await http_node.execute(
                minimal_ctx,
                {
                    "id": "n1",
                    "parameters": {
                        "method": "GET",
                        "url": "http://8.8.8.8/start",
                        "headers": [],
                        "query_params": [],
                        "body_mode": "none",
                        "follow_redirects": True,
                    },
                },
                [[item]],
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
                    # Resolved by the engine in production; execute() receives literals only.
                    "body_json": '{"hello": "world"}',
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
    async def fake_kind_fields(org_id: str, cred_id: str):
        assert org_id == "org1"
        assert cred_id == "deadbeefdeadbeefdeadbeef"
        return {}, {"name": "Authorization", "value": "Bearer secret"}

    monkeypatch.setattr(
        "analytiq_data.flows.fetch_credential_kind_and_fields",
        fake_kind_fields,
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
    async def fake_kind_fields(org_id: str, cred_id: str):
        return {}, {"name": "api_key", "value": "abc123"}

    monkeypatch.setattr(
        "analytiq_data.flows.fetch_credential_kind_and_fields",
        fake_kind_fields,
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
    assert not http_node.validate_parameters({"method": "GET", "url": "https://x"})
    errs = http_node.validate_parameters({"method": "FOO", "url": "http://x"})
    assert errs and "method" in errs[0].lower()
    errs_mr = http_node.validate_parameters({"method": "GET", "url": "https://x", "max_redirects": 0})
    assert any("max_redirects" in e for e in errs_mr)
    errs_qj = http_node.validate_parameters(
        {"method": "GET", "url": "https://x", "query_json": "["}
    )
    assert any("query_json" in e for e in errs_qj)


def test_http_request_url_json_schema_minlength(http_node: FlowsHttpRequestNode):
    v = Draft7Validator(http_node.parameter_schema)
    v.validate({"method": "GET", "url": "https://example.com/x"})
    v.validate({"method": "GET", "url": "=_json['url']"})
    with pytest.raises(Exception):
        v.validate({"method": "GET", "url": ""})


def test_validate_parameters_body_json_required(http_node: FlowsHttpRequestNode):
    ok = {"method": "POST", "url": "https://x", "body_mode": "json", "body_json": '{"x":1}'}
    assert not http_node.validate_parameters(ok)
    errs = http_node.validate_parameters({**ok, "body_json": ""})
    assert any("body_json" in e for e in errs)
    errs = http_node.validate_parameters({**ok, "body_json": "   "})
    assert any("body_json" in e for e in errs)


def test_validate_parameters_body_raw_required(http_node: FlowsHttpRequestNode):
    ok = {"method": "POST", "url": "https://x", "body_mode": "raw", "body_raw": "data", "body_content_type": "text/plain"}
    assert not http_node.validate_parameters(ok)
    errs = http_node.validate_parameters({**ok, "body_raw": ""})
    assert any("body_raw" in e for e in errs)
    errs = http_node.validate_parameters({**ok, "body_content_type": ""})
    assert any("body_content_type" in e for e in errs)


@pytest.mark.asyncio
async def test_rejects_empty_url_after_parameters(http_node: FlowsHttpRequestNode, minimal_ctx: ad.flows.ExecutionContext):
    item = ad.flows.FlowItem(json={}, binary={}, meta={}, paired_item=None)
    with pytest.raises(RuntimeError, match="empty"):
        await http_node.execute(
            minimal_ctx,
            {"id": "n1", "parameters": {"method": "GET", "url": "", "body_mode": "none"}},
            [[item]],
        )


@pytest.mark.asyncio
async def test_invalid_url_error_includes_upstream_row_hint(http_node: FlowsHttpRequestNode, minimal_ctx: ad.flows.ExecutionContext):
    transport = httpx.MockTransport(
        lambda request: httpx.Response(200, json={"ok": True}, request=request)
    )
    with patch(
        "analytiq_data.flows.nodes.http_request.httpx.AsyncClient",
        side_effect=lambda **kw: _RealAsyncClient(transport=transport, **kw),
    ):
        item = ad.flows.FlowItem(
            json={"name": "not-a-url"},
            binary={},
            meta={"source_node_id": "c1", "item_index": 2},
            paired_item=None,
        )
        with pytest.raises(RuntimeError, match="upstream output row index 2"):
            await http_node.execute(
                minimal_ctx,
                {
                    "id": "n1",
                    "parameters": {
                        "method": "GET",
                        # Resolved expression value (non-URL) triggers invalid-url path + hint.
                        "url": "not-a-url",
                        "body_mode": "none",
                    },
                },
                [[item]],
            )


@pytest.mark.asyncio
async def test_rejects_schemeless_url(http_node: FlowsHttpRequestNode, minimal_ctx: ad.flows.ExecutionContext):
    transport = httpx.MockTransport(
        lambda request: httpx.Response(200, json={"ok": True}, request=request)
    )
    with patch(
        "analytiq_data.flows.nodes.http_request.httpx.AsyncClient",
        side_effect=lambda **kw: _RealAsyncClient(transport=transport, **kw),
    ):
        item = ad.flows.FlowItem(json={"host": "example.com"}, binary={}, meta={}, paired_item=None)
        with pytest.raises(RuntimeError, match="http:// or https://"):
            await http_node.execute(
                minimal_ctx,
                {
                    "id": "n1",
                    "parameters": {
                        "method": "GET",
                        # Resolved: upstream string without scheme.
                        "url": "example.com",
                        "body_mode": "none",
                    },
                },
                [[item]],
            )


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
                {"id": "n1", "parameters": {"method": "GET", "url": "http://8.8.8.8/"}},
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
                        "url": "http://8.8.8.8/",
                        "timeout_seconds": 1,
                    },
                },
                [[item]],
            )
