"""``flows.trigger.webhook`` trigger node and parsing helpers."""

from __future__ import annotations

import uuid

import pytest
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route
from starlette.testclient import TestClient

import analytiq_data as ad


def test_filename_from_content_disposition_quoted() -> None:
    assert ad.flows.webhook_parse.filename_from_content_disposition('attachment; filename="report.csv"') == "report.csv"


def test_filename_from_content_disposition_rfc5987() -> None:
    assert (
        ad.flows.webhook_parse.filename_from_content_disposition("attachment; filename*=UTF-8''rep%20ort.csv")
        == "rep ort.csv"
    )


def test_filename_from_content_disposition_strips_path() -> None:
    assert (
        ad.flows.webhook_parse.filename_from_content_disposition('inline; filename="../../../tmp/x.csv"')
        == "x.csv"
    )


def test_filename_from_content_disposition_bare_filename_prefix() -> None:
    """Bare ``filename="…"`` without ``attachment`` / ``inline`` is accepted after normalization."""
    assert ad.flows.webhook_parse.filename_from_content_disposition('filename="bare.csv"') == "bare.csv"


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
    out = await n.execute(ctx, {"id": "t1", "parameters": {}}, [[]])
    item = out[0][0]
    assert item.json["body"] == {"x": 1}
    assert item.json["executionMode"] == "production"
    assert "headers" in item.json
    assert item.binary["data"].storage_id == "flow_blobs:64f3/a.pdf"
    assert item.binary["data"].mime_type == "application/pdf"
    assert item.binary["attachment"].mime_type == "image/png"


@pytest.mark.asyncio
async def test_webhook_trigger_flat_json_test_mode_form_body_and_url() -> None:
    n = ad.flows.FlowsWebhookTriggerNode()
    ctx = ad.flows.ExecutionContext(
        organization_id="o",
        execution_id="64f3a1b2c3d4e5f6a7b8c9d1",
        flow_id="f",
        flow_revid="r",
        mode="webhook",
        trigger_data={
            "type": "webhook",
            "webhook_mode": "test",
            "webhook_url": "https://tools.example/webhook-test/e95569a5-245a-4426-a87c-a447b38f8d3b",
            "headers": {"Content-Type": "text/csv", "Host": "tools.example"},
            "query": {},
            "body": None,
            "form": {"row": "1"},
            "binary_properties": [],
        },
        run_data={},
        analytiq_client=None,
        stop_requested=False,
        logger=None,
    )
    out = await n.execute(ctx, {"id": "t1", "parameters": {}}, [[]])
    j = out[0][0].json
    assert j["executionMode"] == "test"
    assert j["webhookUrl"] == "https://tools.example/webhook-test/e95569a5-245a-4426-a87c-a447b38f8d3b"
    assert j["headers"]["content-type"] == "text/csv"
    assert j["headers"]["host"] == "tools.example"
    assert j["body"] == {"row": "1"}
    assert j["params"] == {}
    assert j["query"] == {}


@pytest.mark.asyncio
async def test_parse_webhook_text_csv_stashes_binary() -> None:
    async def endpoint(request: Request) -> JSONResponse:
        p = await ad.flows.webhook_parse.parse_webhook_request(request, binary_property_name="data")
        return JSONResponse(
            {
                "body": p.body,
                "stashed": p.body_stashed_as_binary,
                "pending": [(k, bytes(b).decode(), m, f) for k, b, m, f in p.pending_binaries],
            }
        )

    app = Starlette(routes=[Route("/t", endpoint, methods=["POST"])])
    client = TestClient(app)
    csv_bytes = (
        "Respiratory - Nebulizers, \nBathroom Aids, \nCHERRY,\n".encode("utf-8")
    )
    res = client.post("/t", content=csv_bytes, headers={"Content-Type": "text/csv"})
    assert res.status_code == 200
    data = res.json()
    assert data["body"] is None
    assert data["stashed"] is True
    assert len(data["pending"]) == 1
    _, text, mime, fname = data["pending"][0]
    assert mime == "text/csv"
    uuid.UUID(fname)
    assert "." not in fname
    assert text == csv_bytes.decode("utf-8")


@pytest.mark.asyncio
async def test_parse_webhook_text_csv_uses_content_disposition_filename() -> None:
    async def endpoint(request: Request) -> JSONResponse:
        p = await ad.flows.webhook_parse.parse_webhook_request(request, binary_property_name="data")
        return JSONResponse(
            {
                "pending": [(k, len(b), m, f) for k, b, m, f in p.pending_binaries],
            }
        )

    app = Starlette(routes=[Route("/t", endpoint, methods=["POST"])])
    client = TestClient(app)
    csv_bytes = b"a,b\n1,2\n"
    res = client.post(
        "/t",
        content=csv_bytes,
        headers={
            "Content-Type": "text/csv",
            "Content-Disposition": 'attachment; filename="categories.csv"',
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert data["pending"] == [["data", len(csv_bytes), "text/csv", "categories.csv"]]


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
async def test_webhook_trigger_body_stashed_keeps_json_body_empty() -> None:
    """When ``body_stashed_as_binary``, do not duplicate payload under ``json.body``."""
    n = ad.flows.FlowsWebhookTriggerNode()
    ctx = ad.flows.ExecutionContext(
        organization_id="o",
        execution_id="64f3a1b2c3d4e5f6a7b8c9d1",
        flow_id="f",
        flow_revid="r",
        mode="webhook",
        trigger_data={
            "type": "webhook",
            "webhook_mode": "test",
            "webhook_url": "https://host/webhook-test/u",
            "headers": {"content-type": "application/pdf"},
            "query": {},
            "body": None,
            "form": None,
            "body_stashed_as_binary": True,
            "binary_properties": [
                {
                    "name": "data",
                    "mime_type": "application/pdf",
                    "file_name": "x.pdf",
                    "storage_id": "flow_blobs:fake/key",
                },
            ],
        },
        run_data={},
        analytiq_client=None,
        stop_requested=False,
        logger=None,
    )
    out = await n.execute(ctx, {"id": "t1", "parameters": {"binary_property_name": "data"}}, [[]])
    assert out[0][0].json["body"] == {}
    assert out[0][0].binary["data"].storage_id == "flow_blobs:fake/key"


@pytest.mark.asyncio
async def test_parse_webhook_raw_body_sets_stashed_flag() -> None:
    async def endpoint(request: Request) -> JSONResponse:
        p = await ad.flows.webhook_parse.parse_webhook_request(request, raw_body=True, binary_property_name="payload")
        return JSONResponse(
            {
                "body": p.body,
                "pending_len": len(p.pending_binaries),
                "stashed": p.body_stashed_as_binary,
            }
        )

    app = Starlette(routes=[Route("/t", endpoint, methods=["POST"])])
    client = TestClient(app)
    res = client.post("/t", content=b"\x00\x01\xff", headers={"Content-Type": "application/octet-stream"})
    assert res.status_code == 200
    data = res.json()
    assert data["body"] is None
    assert data["pending_len"] == 1
    assert data["stashed"] is True


@pytest.mark.asyncio
async def test_parse_webhook_octet_stream_sets_stashed_flag() -> None:
    async def endpoint(request: Request) -> JSONResponse:
        p = await ad.flows.webhook_parse.parse_webhook_request(request)
        return JSONResponse(
            {
                "body": p.body,
                "pending": [(k, len(b), m, f) for k, b, m, f in p.pending_binaries],
                "stashed": p.body_stashed_as_binary,
            }
        )

    app = Starlette(routes=[Route("/t", endpoint, methods=["POST"])])
    client = TestClient(app)
    res = client.post("/t", content=b"abc", headers={"Content-Type": "application/octet-stream"})
    assert res.status_code == 200
    data = res.json()
    assert data["body"] is None
    assert data["stashed"] is True
    k, ln, m, f = data["pending"][0]
    assert [k, ln, m] == ["data", 3, "application/octet-stream"]
    uuid.UUID(f)


@pytest.mark.asyncio
async def test_parse_webhook_opendocument_content_type_stashes_binary() -> None:
    async def endpoint(request: Request) -> JSONResponse:
        p = await ad.flows.webhook_parse.parse_webhook_request(request, binary_property_name="data")
        return JSONResponse(
            {
                "body": p.body,
                "stashed": p.body_stashed_as_binary,
                "pending_fields": [k for k, _b, _m, _f in p.pending_binaries],
                "pending_len": [len(_b) for _k, _b, _m, _f in p.pending_binaries],
            }
        )

    app = Starlette(routes=[Route("/t", endpoint, methods=["POST"])])
    client = TestClient(app)
    raw = b"PK\x03\x04" + b"\x00" * 80
    res = client.post(
        "/t",
        content=raw,
        headers={"Content-Type": "application/vnd.oasis.opendocument.spreadsheet"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["body"] is None
    assert data["stashed"] is True
    assert data["pending_fields"] == ["data"]
    assert data["pending_len"] == [len(raw)]


@pytest.mark.asyncio
async def test_parse_webhook_vnd_plus_json_is_not_forced_binary() -> None:
    async def endpoint(request: Request) -> JSONResponse:
        p = await ad.flows.webhook_parse.parse_webhook_request(request)
        return JSONResponse(
            {
                "body": p.body,
                "stashed": p.body_stashed_as_binary,
                "pending_len": len(p.pending_binaries),
            }
        )

    app = Starlette(routes=[Route("/t", endpoint, methods=["POST"])])
    client = TestClient(app)
    res = client.post(
        "/t",
        content=b'{"catalog":true}',
        headers={"Content-Type": "application/vnd.docrouter+json"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["body"] == {"catalog": True}
    assert data["stashed"] is False
    assert data["pending_len"] == 0


@pytest.mark.asyncio
async def test_parse_webhook_zip_magic_sniff_without_known_mime() -> None:
    """ODS/OOXML are ZIP-shaped; sniff catches wrong or missing MIME."""

    async def endpoint(request: Request) -> JSONResponse:
        p = await ad.flows.webhook_parse.parse_webhook_request(request)
        return JSONResponse(
            {
                "body": p.body,
                "stashed": p.body_stashed_as_binary,
                "mime": [m for _k, _b, m, _f in p.pending_binaries],
            }
        )

    app = Starlette(routes=[Route("/t", endpoint, methods=["POST"])])
    client = TestClient(app)
    raw = b"PK\x03\x04" + bytes(range(120))
    res = client.post("/t", content=raw, headers={"Content-Type": "application/binary"})
    assert res.status_code == 200
    data = res.json()
    assert data["body"] is None
    assert data["stashed"] is True
    assert data["mime"] == ["application/binary"]


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
    k, ln, m, f = data["pending"][0]
    assert [k, ln, m] == ["payload", len(raw), "application/json"]
    uuid.UUID(f)


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

    # Fallback / synthetic ack path used outside full ``on_received`` UI (including respond / last-node fallbacks).
    for mode in ("last_node", "respond_to_webhook"):
        sm, _, bod = wp.synchronous_http_response("ex-sync", {"response_mode": mode})
        assert sm == 200
        assert bod is not None and b"ex-sync" in bod and b"execution_id" in bod


def test_webhook_trigger_response_mode_schema_labels_match_enum() -> None:
    n = ad.flows.FlowsWebhookTriggerNode()
    prop = n.parameter_schema["properties"]["response_mode"]
    assert prop["enum"] == ["on_received", "last_node", "respond_to_webhook"]
    names = prop["x-ui-enum-names"]
    assert names == [
        "Respond immediately",
        "When last node finishes",
        "Using Respond to Webhook",
    ]
    assert len(names) == len(prop["enum"])
    assert not any("(planned)" in str(label) for label in names)


def test_webhook_trigger_validate_accepts_each_response_mode() -> None:
    n = ad.flows.FlowsWebhookTriggerNode()
    for mode in ("on_received", "last_node", "respond_to_webhook"):
        assert n.validate_parameters({"response_mode": mode}) == [], repr(mode)


def test_respond_to_webhook_validate_accepts_missing_body_mode() -> None:
    """``execute`` defaults missing ``body_mode`` to json; validation must match."""
    n = ad.flows.FlowsRespondToWebhookNode()
    assert n.validate_parameters({}) == []
    assert n.validate_parameters({"status_code": 200}) == []
    assert n.validate_parameters({"body_mode": None}) == []
    assert n.validate_parameters({"body_mode": ""}) == []


@pytest.mark.asyncio
async def test_respond_to_webhook_node_sets_context_response() -> None:
    n = ad.flows.FlowsRespondToWebhookNode()
    ctx = ad.flows.ExecutionContext(
        organization_id="o",
        execution_id="64f3a1b2c3d4e5f6a7b8c9d1",
        flow_id="f",
        flow_revid="r",
        mode="webhook",
        trigger_data={"type": "webhook"},
        run_data={},
        analytiq_client=None,
        stop_requested=False,
        logger=None,
    )
    node = {
        "id": "n1",
        "type": "flows.respond_to_webhook",
        "parameters": {
            "status_code": 201,
            "headers": [{"name": "X-Test", "value": "1"}],
            "body_mode": "text",
            "body_text": "hello",
        },
    }
    out = await n.execute(ctx, node, [[ad.flows.FlowItem(json={"a": 1}, binary={}, meta={}, paired_item=None)]])
    assert out and out[0]  # pass-through
    resp = ctx.trigger_data.get("_webhook_response")
    assert isinstance(resp, dict)
    assert resp["status_code"] == 201
    assert resp["headers"]["X-Test"] == "1"
