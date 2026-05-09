"""
Org-scoped credential lookup for flow nodes (see docs/docrouter_credentials.md).

When ``credentials`` documents exist, decrypted payloads are returned per credential id.
"""

from __future__ import annotations

import json
import logging
from typing import Any

import analytiq_data as ad

logger = logging.getLogger(__name__)


async def ensure_credentials_indexes(analytiq_client) -> None:
    """
    Ensure the `credentials` collection has the indexes needed for common queries.

    Intended to be called during application startup (idempotent).
    """

    db = analytiq_client.mongodb_async[analytiq_client.env]

    # Efficient filtering by org and kind (non-unique).
    try:
        await db.credentials.create_index(
            [("organization_id", 1), ("kind_key", 1)],
            name="credentials_org_kind_key",
            background=True,
        )
        logger.info("Ensured index on credentials (organization_id, kind_key)")
    except Exception as e:
        # Index might already exist or have an equivalent definition.
        s = str(e).lower()
        if "already exists" not in s and "indexoptionsconflict" not in s:
            logger.warning("Could not ensure credentials indexes: %s", e)


async def fetch_credential_fields(organization_id: str, credential_id: str) -> dict[str, Any]:
    """
    Load and decrypt one saved credential by id.

    Returns an empty dict if the document is missing or decryption fails.
    """

    if not credential_id or not organization_id:
        return {}
    try:
        from bson import ObjectId

        oid = ObjectId(credential_id)
    except Exception:
        logger.warning("Invalid credential ObjectId: %s", credential_id)
        return {}

    try:
        db = ad.common.get_async_db()
        doc = await db.credentials.find_one(
            {"_id": oid, "organization_id": organization_id}
        )
        if not doc:
            return {}
        raw = doc.get("encrypted_payload")
        if not raw:
            return {}
        decrypted = ad.crypto.decrypt_token(raw)
        if not decrypted:
            return {}
        data = json.loads(decrypted)
        return data if isinstance(data, dict) else {}
    except Exception as e:
        logger.warning("fetch_credential_fields failed for %s: %s", credential_id, e)
        return {}


async def fetch_credential_kind_and_fields(
    organization_id: str, credential_id: str
) -> tuple[dict[str, Any], dict[str, Any]]:
    """
    Load one credential's kind definition (from ``kind_key``) and decrypted fields.

    Returns ``({}, fields)`` when the document is missing. On unknown ``kind_key``,
    returns ``({}, fields)`` with fields still populated when decryption succeeds.
    """

    fields = await fetch_credential_fields(organization_id, credential_id)
    if not fields:
        return {}, {}

    try:
        from bson import ObjectId

        oid = ObjectId(credential_id)
    except Exception:
        return {}, fields

    try:
        db = ad.common.get_async_db()
        doc = await db.credentials.find_one(
            {"_id": oid, "organization_id": organization_id}
        )
        if not doc:
            return {}, fields
        kind_key = doc.get("kind_key")
        if not kind_key:
            return {}, fields
        try:
            kind = ad.flows.get_credential_kind(str(kind_key))
        except KeyError:
            return {}, fields
        from analytiq_data.flows.credential_runtime import apply_runtime_credential_updates

        updated = await apply_runtime_credential_updates(
            organization_id, credential_id, kind, fields
        )
        return kind, updated
    except Exception as e:
        logger.warning("fetch_credential_kind_and_fields failed for %s: %s", credential_id, e)
        return {}, fields
