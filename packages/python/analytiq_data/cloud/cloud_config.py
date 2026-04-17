"""
Unified cloud credentials in ``cloud_config`` with ``type`` discriminator.

- ``type: "aws"`` — same fields as legacy ``aws_config`` (encrypted keys, bucket, ``user_id``).
- ``type: "gcp"`` — encrypted ``service_account_json`` (Vertex), ``user_id``.
- ``type: "azure"`` — encrypted Microsoft Entra service principal (tenant, client id, client secret), ``user_id``.
"""

import json
import logging
import os
from typing import Optional

import analytiq_data as ad

logger = logging.getLogger(__name__)

TYPE_AWS = "aws"
TYPE_GCP = "gcp"
TYPE_AZURE = "azure"


async def get_aws_config_dict(analytiq_client) -> dict:
    """
    Return AWS keys and bucket for Textract, S3, Bedrock, etc.

    Prefers ``cloud_config`` with ``type`` aws; falls back to legacy ``aws_config``.
    """
    db = analytiq_client.mongodb_async[analytiq_client.env]

    doc = await db.cloud_config.find_one({"type": TYPE_AWS})
    if not doc:
        doc = await db.aws_config.find_one()

    access_key_id = ""
    secret_access_key = ""
    if doc:
        access_key_id = ad.crypto.decrypt_token(doc.get("access_key_id", "") or "")
        secret_access_key = ad.crypto.decrypt_token(doc.get("secret_access_key", "") or "")

    return {
        "aws_access_key_id": access_key_id,
        "aws_secret_access_key": secret_access_key,
        "s3_bucket_name": doc.get("s3_bucket_name") if doc else None,
    }


async def get_gcp_service_account_json(analytiq_client) -> str:
    """
    Decrypted service account JSON for Vertex AI, or empty string.

    Prefers ``cloud_config`` with ``type`` gcp; falls back to legacy ``llm_providers`` vertex_ai token.
    """
    db = analytiq_client.mongodb_async[analytiq_client.env]

    doc = await db.cloud_config.find_one({"type": TYPE_GCP})
    if doc and doc.get("service_account_json"):
        try:
            return ad.crypto.decrypt_token(doc["service_account_json"])
        except Exception as e:
            logger.warning("Failed to decrypt GCP service_account_json: %s", e)
            return ""

    provider = await db.llm_providers.find_one({"litellm_provider": "vertex_ai"})
    if provider and provider.get("token"):
        try:
            return ad.crypto.decrypt_token(provider["token"])
        except Exception as e:
            logger.warning("Failed to decrypt legacy vertex_ai llm_providers token: %s", e)
            return ""

    return ""


async def gcp_credentials_configured(db) -> bool:
    """True if a non-empty GCP Vertex credential exists (cloud_config or legacy llm_providers)."""
    doc = await db.cloud_config.find_one({"type": TYPE_GCP})
    if doc and doc.get("service_account_json"):
        return True
    provider = await db.llm_providers.find_one({"litellm_provider": "vertex_ai"})
    return bool(provider and provider.get("token"))


async def get_vertex_project_and_location(analytiq_client) -> tuple[str, str]:
    """(vertex_project, vertex_location) from stored GCP JSON."""
    vertex_location = os.getenv("VERTEX_AI_LOCATION", "global")
    raw = await get_gcp_service_account_json(analytiq_client)
    if not raw:
        return "", vertex_location
    try:
        credentials = json.loads(raw)
        vertex_project = credentials.get("project_id", "") or ""
    except Exception:
        vertex_project = ""
    return vertex_project, vertex_location


async def get_azure_service_principal_dict(analytiq_client) -> dict:
    """
    Decrypted Microsoft Entra (Azure AD) service principal fields for Foundry / Azure AI, or empty strings.

    Keys: ``tenant_id``, ``client_id``, ``client_secret``.
    """
    db = analytiq_client.mongodb_async[analytiq_client.env]
    doc = await db.cloud_config.find_one({"type": TYPE_AZURE})
    if not doc:
        return {"tenant_id": "", "client_id": "", "client_secret": ""}

    def _dec(field: str) -> str:
        raw = doc.get(field) or ""
        if not raw:
            return ""
        try:
            return ad.crypto.decrypt_token(raw)
        except Exception as e:
            logger.warning("Failed to decrypt Azure cloud_config field %s: %s", field, e)
            return ""

    return {
        "tenant_id": _dec("tenant_id"),
        "client_id": _dec("client_id"),
        "client_secret": _dec("client_secret"),
    }


async def azure_service_principal_configured(db) -> bool:
    """True if non-empty Azure service principal credentials exist in ``cloud_config``."""
    doc = await db.cloud_config.find_one({"type": TYPE_AZURE})
    if not doc:
        return False
    for key in ("tenant_id", "client_id", "client_secret"):
        if not doc.get(key):
            return False
    return True
