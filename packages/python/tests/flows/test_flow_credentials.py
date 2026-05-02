"""Tests for `flows.credentials.fetch_org_credential_fields` against a real test database.

These tests exercise the actual MongoDB query so that a wrong collection name
or document shape is caught here rather than silently returning `{}` at runtime.
"""

from __future__ import annotations

import json

import pytest
from bson import ObjectId

import analytiq_data as ad
from analytiq_data.flows.credentials import fetch_org_credential_fields

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
