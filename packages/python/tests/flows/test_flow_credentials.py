"""Tests for `flows.credentials` against a real test database.

These tests exercise the actual MongoDB query so that a wrong collection name
or document shape is caught here rather than silently returning `{}` at runtime.
They also cover credential injection through `FlowsHttpRequestNode.execute()`
end-to-end, using a real credential document and a mocked HTTP transport.
"""

from __future__ import annotations

import json
from unittest.mock import patch

import httpx
import pytest
from bson import ObjectId

import analytiq_data as ad
from analytiq_data.flows.credentials import fetch_org_credential_fields
from analytiq_data.flows.nodes.http_request import FlowsHttpRequestNode

_RealAsyncClient = httpx.AsyncClient

TEST_ORG = "aabbccddeeff001122334455"


def _encrypted(payload: dict) -> str:
    return ad.crypto.encrypt_token(json.dumps(payload))


@pytest.mark.asyncio
async def test_fetch_returns_decrypted_fields(test_db):
    """Happy path: document in `credentials` collection is found and decrypted."""
    cred_id = ObjectId()
    await test_db.credentials.insert_one(
        {
            "_id": cred_id,
            "organization_id": TEST_ORG,
            "encrypted_payload": _encrypted({"name": "Authorization", "value": "Bearer tok"}),
        }
    )

    result = await fetch_org_credential_fields(TEST_ORG, str(cred_id))

    assert result == {"name": "Authorization", "value": "Bearer tok"}


@pytest.mark.asyncio
async def test_fetch_missing_document_returns_empty(test_db):
    """No document with that id → empty dict, not an exception."""
    result = await fetch_org_credential_fields(TEST_ORG, str(ObjectId()))

    assert result == {}


@pytest.mark.asyncio
async def test_fetch_wrong_org_returns_empty(test_db):
    """Document exists but belongs to a different org → empty dict (org isolation)."""
    cred_id = ObjectId()
    await test_db.credentials.insert_one(
        {
            "_id": cred_id,
            "organization_id": "other_org",
            "encrypted_payload": _encrypted({"name": "X-Key", "value": "secret"}),
        }
    )

    result = await fetch_org_credential_fields(TEST_ORG, str(cred_id))

    assert result == {}


@pytest.mark.asyncio
async def test_fetch_invalid_object_id_returns_empty(test_db):
    """Non-hex credential_id → empty dict, not an exception."""
    result = await fetch_org_credential_fields(TEST_ORG, "not-an-objectid")

    assert result == {}


@pytest.mark.asyncio
async def test_fetch_missing_encrypted_payload_returns_empty(test_db):
    """Document exists but has no encrypted_payload field → empty dict."""
    cred_id = ObjectId()
    await test_db.credentials.insert_one(
        {"_id": cred_id, "organization_id": TEST_ORG}
    )

    result = await fetch_org_credential_fields(TEST_ORG, str(cred_id))

    assert result == {}


# ---------------------------------------------------------------------------
# End-to-end: credential fetched from DB and injected into HTTP request node
# ---------------------------------------------------------------------------

def _node(params: dict, credentials: dict | None = None) -> dict:
    n = {"id": "n1", "parameters": params}
    if credentials:
        n["credentials"] = credentials
    return n


def _item() -> "ad.flows.FlowItem":
    return ad.flows.FlowItem(json={}, binary={}, meta={}, paired_item=None)


def _ctx(org_id: str = TEST_ORG) -> "ad.flows.ExecutionContext":
    return ad.flows.ExecutionContext(
        organization_id=org_id,
        execution_id="e1",
        flow_id="f1",
        flow_revid="r1",
        mode="manual",
        trigger_data={},
        run_data={},
        analytiq_client=None,
    )


@pytest.mark.asyncio
async def test_header_auth_credential_injected_from_db(test_db):
    """httpHeaderAuth credential stored in DB is fetched, decrypted, and sent as a request header."""
    cred_id = ObjectId()
    await test_db.credentials.insert_one(
        {
            "_id": cred_id,
            "organization_id": TEST_ORG,
            "encrypted_payload": _encrypted({"name": "Authorization", "value": "Bearer real-token"}),
        }
    )

    requests_seen: list[httpx.Request] = []
    transport = httpx.MockTransport(
        lambda req: (requests_seen.append(req) or httpx.Response(200, json={}, request=req))
    )

    with patch(
        "analytiq_data.flows.nodes.http_request.httpx.AsyncClient",
        side_effect=lambda **kw: _RealAsyncClient(transport=transport, **kw),
    ):
        await FlowsHttpRequestNode().execute(
            _ctx(),
            _node(
                {"method": "GET", "url": "https://example.com/", "body_mode": "none"},
                credentials={"httpHeaderAuth": str(cred_id)},
            ),
            [[_item()]],
        )

    assert requests_seen[0].headers.get("Authorization") == "Bearer real-token"


@pytest.mark.asyncio
async def test_query_auth_credential_injected_from_db(test_db):
    """httpQueryAuth credential stored in DB is fetched, decrypted, and appended as a query param."""
    cred_id = ObjectId()
    await test_db.credentials.insert_one(
        {
            "_id": cred_id,
            "organization_id": TEST_ORG,
            "encrypted_payload": _encrypted({"name": "api_key", "value": "db-secret"}),
        }
    )

    requests_seen: list[httpx.Request] = []
    transport = httpx.MockTransport(
        lambda req: (requests_seen.append(req) or httpx.Response(200, json={}, request=req))
    )

    with patch(
        "analytiq_data.flows.nodes.http_request.httpx.AsyncClient",
        side_effect=lambda **kw: _RealAsyncClient(transport=transport, **kw),
    ):
        await FlowsHttpRequestNode().execute(
            _ctx(),
            _node(
                {"method": "GET", "url": "https://example.com/", "body_mode": "none"},
                credentials={"httpQueryAuth": str(cred_id)},
            ),
            [[_item()]],
        )

    assert "api_key=db-secret" in str(requests_seen[0].url)


@pytest.mark.asyncio
async def test_missing_credential_doc_sends_request_without_auth(test_db):
    """If the credential id has no matching document the request still goes through, just unauthenticated."""
    requests_seen: list[httpx.Request] = []
    transport = httpx.MockTransport(
        lambda req: (requests_seen.append(req) or httpx.Response(200, json={}, request=req))
    )

    with patch(
        "analytiq_data.flows.nodes.http_request.httpx.AsyncClient",
        side_effect=lambda **kw: _RealAsyncClient(transport=transport, **kw),
    ):
        await FlowsHttpRequestNode().execute(
            _ctx(),
            _node(
                {"method": "GET", "url": "https://example.com/", "body_mode": "none"},
                credentials={"httpHeaderAuth": str(ObjectId())},
            ),
            [[_item()]],
        )

    assert "Authorization" not in requests_seen[0].headers
