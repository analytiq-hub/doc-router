"""``flows.trigger.webhook`` trigger node and parsing helpers."""

from __future__ import annotations

import pytest
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route
from starlette.testclient import TestClient

import analytiq_data as ad


@pytest.mark.asyncio
async def test_webhook_trigger_maps_binary_properties_to_flowitem() -> None:
    n = ad.flows.FlowsWebhookTriggerNode()
    ctx = ad.flows.ExecutionContext(
        organization_id="o",
        execution_id="64f3a1b2c3d4e5f6a7b8c9d1",
        flow_id="f",
        flow_revid="r",
        mode="webhook",
        trigger_data={
            "type": "webhook",
            "webhook_id": "wh",
            "method": "POST",
            "headers": {},
            "query": {},
            "body": {"x": 1},
            "binary_properties": [
                {
                    "name": "data",
                    "mime_type": "application/pdf",
                    "file_name": "doc.pdf",
                    "storage_id": "flow_blobs:64f3/a.pdf",
                },
                {
                    "name": "attachment",
                    "mime_type": "image/png",
                    "file_name": None,
                    "storage_id": "flow_blobs:64f3/b.png",
                },
            ],
        },
        run_data={},
        analytiq_client=None,
        stop_requested=False,
        logger=None,
    )
    out = await n.execute(ctx, {"id": "t1"}, [[]])
    item = out[0][0]
    assert item.json["trigger"]["type"] == "webhook"
    assert item.binary["data"].storage_id == "flow_blobs:64f3/a.pdf"
    assert item.binary["data"].mime_type == "application/pdf"
    assert item.binary["attachment"].mime_type == "image/png"


def test_parse_webhook_json_body() -> None:
    async def endpoint(request: Request) -> JSONResponse:
        p = await ad.flows.webhook_parse.parse_webhook_request(request)
        return JSONResponse(
            {
                "query": p.query,
                "body": p.body,
                "form": p.form,
                "pending": len(p.pending_binaries),
            }
        )

    app = Starlette(routes=[Route("/t", endpoint, methods=["POST"])])
    client = TestClient(app)
    res = client.post("/t?foo=bar", json={"a": 2})
    assert res.status_code == 200
    data = res.json()
    assert data["query"] == {"foo": "bar"}
    assert data["body"] == {"a": 2}
    assert data["pending"] == 0


def test_parse_webhook_multipart_via_testclient() -> None:
    async def endpoint(request: Request) -> JSONResponse:
        p = await ad.flows.webhook_parse.parse_webhook_request(request)
        return JSONResponse(
            {
                "body": p.body,
                "form": p.form,
                "pending": [(k, len(b), m, f) for k, b, m, f in p.pending_binaries],
            }
        )

    app = Starlette(routes=[Route("/t", endpoint, methods=["POST"])])
    client = TestClient(app)
    res = client.post(
        "/t",
        data={"title": "hello"},
        files={"upload": ("one.png", b"\x89PNG\r\n\xff", "image/png")},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["form"] == {"title": "hello"}
    assert len(data["pending"]) == 1
    assert data["pending"][0][0] == "upload"
    assert data["pending"][0][1] == 7
    assert data["pending"][0][2] == "image/png"
    assert data["pending"][0][3] == "one.png"


@pytest.mark.asyncio
async def test_parse_webhook_raw_body_stashes_bytes() -> None:
    async def endpoint(request: Request) -> JSONResponse:
        p = await ad.flows.webhook_parse.parse_webhook_request(request, raw_body=True, binary_property_name="payload")
        return JSONResponse(
            {
                "body": p.body,
                "form": p.form,
                "pending": [(k, len(b), m, f) for k, b, m, f in p.pending_binaries],
            }
        )

    app = Starlette(routes=[Route("/t", endpoint, methods=["POST"])])
    client = TestClient(app)
    raw = b'{"looks":"json"}'
    res = client.post("/t", content=raw, headers={"Content-Type": "application/json"})
    assert res.status_code == 200
    data = res.json()
    assert data["body"] is None
    assert data["pending"] == [["payload", len(raw), "application/json", None]]


def test_webhook_params_allowed_methods_snapshot() -> None:
    wp = ad.flows.webhook_params

    assert wp.allowed_http_methods_snapshot({}) is None
    assert wp.allowed_http_methods_snapshot({"http_method": "POST"}) == frozenset({"POST"})
    assert wp.allowed_http_methods_snapshot({"multiple_methods": True, "allowed_methods": "GET, PATCH"}) == frozenset(
        {"GET", "PATCH"}
    )
    hops, dip = wp.request_ip_candidates(
        Request(
            scope={
                "type": "http",
                "headers": [(b"x-forwarded-for", b" 10.0.0.1 , 172.31.9.99 ")],
                "client": ("192.168.0.2", 0),
                "server": ("test", 80),
                "method": "GET",
                "path": "/",
                "query_string": b"",
                "http_version": "1.1",
                "scheme": "http",
                "extensions": {},
            }
        )
    )
    assert hops[0] == "10.0.0.1"
    assert wp.is_ip_whitelisted(None, hops, dip) is True
    assert wp.is_ip_whitelisted("10.0.", hops, dip) is True
    assert wp.is_ip_whitelisted("8.8.8.", hops, dip) is False


def test_webhook_sync_response_shapes() -> None:
    wp = ad.flows.webhook_params

    status, hdr, body = wp.synchronous_http_response("exec1", {})
    assert status == 200
    assert "application/json" in (hdr.get("Content-Type") or "").lower()
    assert body is not None and b"exec1" in body

    st2, _hdr2, body2 = wp.synchronous_http_response(
        "e2",
        {"response_mode": "on_received", "no_response_body": True},
    )
    assert st2 == 200
    assert body2 is None
