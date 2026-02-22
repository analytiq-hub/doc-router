"""Tests for OCR blocks endpoint format parameter (plain vs gzip)."""
import gzip
import json
from unittest.mock import AsyncMock, patch

import pytest

from tests.conftest_utils import client, get_token_headers


SAMPLE_OCR_JSON = [
    {"BlockType": "LINE", "Text": "Sample line", "Geometry": {"BoundingBox": {"Width": 0.1, "Height": 0.02}}},
]
SAMPLE_DOC = {"user_file_name": "test.pdf", "organization_id": "org-123"}


@pytest.mark.asyncio
async def test_ocr_blocks_format_plain(org_and_users, test_db):
    """format=plain returns raw JSON with Cache-Control."""
    org_id = org_and_users["org_id"]
    admin = org_and_users["admin"]
    doc_id = "507f1f77bcf86cd799439011"

    with (
        patch("analytiq_data.common.get_doc", new_callable=AsyncMock, return_value=SAMPLE_DOC),
        patch("analytiq_data.common.get_ocr_json", new_callable=AsyncMock, return_value=SAMPLE_OCR_JSON),
    ):
        resp = client.get(
            f"/v0/orgs/{org_id}/ocr/download/blocks/{doc_id}",
            params={"format": "plain"},
            headers=get_token_headers(admin["token"]),
        )
    assert resp.status_code == 200
    assert resp.headers.get("content-type", "").startswith("application/json")
    assert "private" in resp.headers.get("cache-control", "")
    assert "max-age=3600" in resp.headers.get("cache-control", "")
    assert resp.json() == SAMPLE_OCR_JSON


@pytest.mark.asyncio
async def test_ocr_blocks_format_gzip(org_and_users, test_db):
    """format=gzip returns gzip-compressed body with Content-Encoding and decompresses to same JSON."""
    org_id = org_and_users["org_id"]
    admin = org_and_users["admin"]
    doc_id = "507f1f77bcf86cd799439011"

    with (
        patch("app.routes.ocr.ad") as mock_ad,
    ):
        mock_ad.common.get_doc = AsyncMock(return_value=SAMPLE_DOC)
        mock_ad.common.get_ocr_json = AsyncMock(return_value=SAMPLE_OCR_JSON)
        mock_ad.common.get_analytiq_client = lambda: None
        mock_ad.common.doc.ocr_supported = lambda fn: fn.endswith(".pdf")

        resp = client.get(
            f"/v0/orgs/{org_id}/ocr/download/blocks/{doc_id}?format=gzip",
            headers=get_token_headers(admin["token"]),
        )
    assert resp.status_code == 200
    assert resp.headers.get("content-encoding") == "gzip"
    assert resp.headers.get("content-type", "").startswith("application/json")
    assert "private" in resp.headers.get("cache-control", "")
    assert "max-age=3600" in resp.headers.get("cache-control", "")

    # TestClient/httpx may auto-decompress gzip; if so resp.content is already decompressed
    raw = resp.content
    if raw[:2] == b"\x1f\x8b":
        data = json.loads(gzip.decompress(raw).decode("utf-8"))
    else:
        data = resp.json()
    assert data == SAMPLE_OCR_JSON


@pytest.mark.asyncio
async def test_ocr_blocks_format_default_is_plain(org_and_users, test_db):
    """Omitting format defaults to plain (backward compatibility)."""
    org_id = org_and_users["org_id"]
    admin = org_and_users["admin"]
    doc_id = "507f1f77bcf86cd799439011"

    with (
        patch("analytiq_data.common.get_doc", new_callable=AsyncMock, return_value=SAMPLE_DOC),
        patch("analytiq_data.common.get_ocr_json", new_callable=AsyncMock, return_value=SAMPLE_OCR_JSON),
    ):
        resp = client.get(
            f"/v0/orgs/{org_id}/ocr/download/blocks/{doc_id}",
            headers=get_token_headers(admin["token"]),
        )
    assert resp.status_code == 200
    assert "content-encoding" not in resp.headers or resp.headers.get("content-encoding") != "gzip"
    assert resp.json() == SAMPLE_OCR_JSON


@pytest.mark.asyncio
async def test_ocr_blocks_format_invalid(org_and_users, test_db):
    """Invalid format value returns 422."""
    org_id = org_and_users["org_id"]
    admin = org_and_users["admin"]
    doc_id = "507f1f77bcf86cd799439011"

    resp = client.get(
        f"/v0/orgs/{org_id}/ocr/download/blocks/{doc_id}",
        params={"format": "invalid"},
        headers=get_token_headers(admin["token"]),
    )
    assert resp.status_code == 422
