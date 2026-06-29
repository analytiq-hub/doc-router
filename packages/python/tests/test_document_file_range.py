"""Pure and HTTP tests for document file byte-range handling."""

import base64
import uuid
from datetime import datetime, UTC

import pytest
from bson import ObjectId

import analytiq_data as ad
from analytiq_data.mongodb.blob import (
    align_byte_range_to_gridfs_chunks,
    DEFAULT_GRIDFS_CHUNK_BYTES,
)
from app.routes.documents import _parse_single_byte_range

from .conftest_utils import client, TEST_ORG_ID, get_auth_headers


def _auth_headers_multipart() -> dict[str, str]:
    return {"Authorization": "Bearer test_token"}


@pytest.fixture
def small_pdf():
    pdf_content = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF\n"
    return {
        "name": "small_test.pdf",
        "content": f"data:application/pdf;base64,{base64.b64encode(pdf_content).decode()}",
    }


class TestParseSingleByteRange:
    def test_closed_range(self):
        assert _parse_single_byte_range("bytes=0-9", 100) == (0, 9)

    def test_open_ended_from_start(self):
        assert _parse_single_byte_range("bytes=50-", 100) == (50, 99)

    def test_suffix_range(self):
        assert _parse_single_byte_range("bytes=-20", 100) == (80, 99)

    def test_uses_first_range_when_multiple(self):
        assert _parse_single_byte_range("bytes=0-9, 20-29", 100) == (0, 9)

    def test_strips_whitespace_and_case(self):
        assert _parse_single_byte_range("  Bytes= 10 - 20  ", 100) == (10, 20)

    def test_clamps_end_to_file_size(self):
        assert _parse_single_byte_range("bytes=90-200", 100) == (90, 99)

    def test_rejects_invalid_inputs(self):
        assert _parse_single_byte_range("", 100) is None
        assert _parse_single_byte_range("bytes=", 100) is None
        assert _parse_single_byte_range("items=0-1", 100) is None
        assert _parse_single_byte_range("bytes=0", 100) is None
        assert _parse_single_byte_range("bytes=-0", 100) is None
        assert _parse_single_byte_range("bytes=100-101", 100) is None
        assert _parse_single_byte_range("bytes=50-40", 100) is None
        assert _parse_single_byte_range("bytes=0-1", 0) is None


class TestAlignByteRangeToGridfsChunks:
    def test_single_chunk_range(self):
        start, end = align_byte_range_to_gridfs_chunks(10, 50, 512, 256)
        assert (start, end) == (0, 255)

    def test_spans_two_chunks(self):
        start, end = align_byte_range_to_gridfs_chunks(200, 300, 512, 256)
        assert (start, end) == (0, 511)

    def test_last_chunk_clamped_to_file_length(self):
        start, end = align_byte_range_to_gridfs_chunks(400, 500, 450, 256)
        assert (start, end) == (256, 449)

    def test_chunk_boundary_start(self):
        start, end = align_byte_range_to_gridfs_chunks(256, 256, 512, 256)
        assert (start, end) == (256, 511)

    def test_uses_default_when_chunk_size_invalid(self):
        start, end = align_byte_range_to_gridfs_chunks(0, 10, 100, 0)
        aligned_end = min(DEFAULT_GRIDFS_CHUNK_BYTES - 1, 99)
        assert (start, end) == (0, aligned_end)


@pytest.mark.asyncio
async def test_get_document_file_invalid_range_returns_416(test_db, mock_auth, small_pdf):
    """Unsatisfiable Range headers return 416 without changing full-file behavior."""
    raw = base64.b64decode(small_pdf["content"].split(",", 1)[1])
    upload_resp = client.post(
        f"/v0/orgs/{TEST_ORG_ID}/documents/multipart",
        files=[("file", ("range_416.pdf", raw, "application/pdf"))],
        headers=_auth_headers_multipart(),
    )
    assert upload_resp.status_code == 200, upload_resp.text
    document_id = upload_resp.json()["document"]["document_id"]

    try:
        invalid_resp = client.get(
            f"/v0/orgs/{TEST_ORG_ID}/documents/{document_id}/file",
            params={"file_type": "pdf"},
            headers={**get_auth_headers(), "Range": "bytes=99999-100000"},
        )
        assert invalid_resp.status_code == 416, invalid_resp.text
        assert invalid_resp.headers.get("content-range") == f"bytes */{len(raw)}"

        suffix_resp = client.get(
            f"/v0/orgs/{TEST_ORG_ID}/documents/{document_id}/file",
            params={"file_type": "pdf"},
            headers={**get_auth_headers(), "Range": "bytes=-20"},
        )
        assert suffix_resp.status_code == 206, suffix_resp.text
        assert suffix_resp.content == raw[-20:]
        assert suffix_resp.headers.get("content-range") == f"bytes {len(raw) - 20}-{len(raw) - 1}/{len(raw)}"
    finally:
        client.delete(
            f"/v0/orgs/{TEST_ORG_ID}/documents/{document_id}",
            headers=get_auth_headers(),
        )


@pytest.mark.asyncio
async def test_uploaded_document_uses_default_gridfs_chunk_size(test_db, mock_auth, small_pdf):
    """Multipart uploads store files with the default 8MB GridFS chunk size."""
    raw = base64.b64decode(small_pdf["content"].split(",", 1)[1])
    upload_resp = client.post(
        f"/v0/orgs/{TEST_ORG_ID}/documents/multipart",
        files=[("file", ("chunk_default.pdf", raw, "application/pdf"))],
        headers=_auth_headers_multipart(),
    )
    assert upload_resp.status_code == 200, upload_resp.text
    document_id = upload_resp.json()["document"]["document_id"]

    aq_client = ad.common.get_analytiq_client()
    try:
        doc = await ad.common.get_async_db(aq_client).docs.find_one({"_id": ObjectId(document_id)})
        file_name = doc["pdf_file_name"]
        info = await ad.mongodb.get_blob_info_async(aq_client, "files", file_name)
        assert info is not None
        assert info["chunk_size"] == DEFAULT_GRIDFS_CHUNK_BYTES
        assert info["length"] == len(raw)
    finally:
        client.delete(
            f"/v0/orgs/{TEST_ORG_ID}/documents/{document_id}",
            headers=get_auth_headers(),
        )


@pytest.mark.asyncio
async def test_read_blob_range_across_gridfs_chunks(test_db, mock_auth):
    """GridFS range reads fetch whole chunks and slice to the requested byte span."""
    aq_client = ad.common.get_analytiq_client()
    key = f"gridfs_range_test_{uuid.uuid4().hex}"
    chunk_size = 256
    raw = b"A" * 200 + b"B" * 312  # 512 bytes across two GridFS chunks

    await ad.mongodb.save_blob_async(
        aq_client,
        "files",
        key,
        raw,
        {"type": "application/octet-stream"},
        chunk_size_bytes=chunk_size,
    )
    try:
        info = await ad.mongodb.get_blob_info_async(aq_client, "files", key)
        assert info["chunk_size"] == chunk_size
        assert info["length"] == len(raw)

        aligned_start, aligned_end = align_byte_range_to_gridfs_chunks(
            200, 300, len(raw), chunk_size,
        )
        assert aligned_start == 0
        assert aligned_end == 511

        data = await ad.mongodb.read_blob_range_async(aq_client, "files", key, 200, 300)
        assert data == raw[200:301]

        aligned = await ad.mongodb.read_blob_range_async(
            aq_client, "files", key, aligned_start, aligned_end,
        )
        assert aligned == raw
    finally:
        await ad.mongodb.delete_blob_async(aq_client, "files", key)


@pytest.mark.asyncio
async def test_read_blob_range_missing_chunk_returns_none(test_db, mock_auth):
    """Corrupt GridFS data (missing chunk doc) surfaces as None, not partial bytes."""
    aq_client = ad.common.get_analytiq_client()
    key = f"gridfs_missing_chunk_{uuid.uuid4().hex}"
    chunk_size = 256
    raw = bytes(i % 256 for i in range(512))

    await ad.mongodb.save_blob_async(
        aq_client,
        "files",
        key,
        raw,
        {"type": "application/octet-stream"},
        chunk_size_bytes=chunk_size,
    )
    mongo = aq_client.mongodb_async
    db = mongo[aq_client.env]
    file_doc = await db["files.files"].find_one({"filename": key})
    await db["files.chunks"].delete_one({"files_id": file_doc["_id"], "n": 1})

    try:
        data = await ad.mongodb.read_blob_range_async(aq_client, "files", key, 300, 400)
        assert data is None
    finally:
        await ad.mongodb.delete_blob_async(aq_client, "files", key)


@pytest.mark.asyncio
async def test_get_document_file_range_exact_span(test_db, mock_auth):
    """HTTP Range on /file returns exactly the requested byte span."""
    aq_client = ad.common.get_analytiq_client()
    key = f"chunk_range_http_{uuid.uuid4().hex}"
    chunk_size = 256
    raw = bytes(i % 256 for i in range(512))

    await ad.mongodb.save_blob_async(
        aq_client,
        "files",
        key,
        raw,
        {"type": "application/pdf"},
        chunk_size_bytes=chunk_size,
    )
    document_id = str(ObjectId())
    db = ad.common.get_async_db(aq_client)
    await db.docs.insert_one({
        "_id": ObjectId(document_id),
        "organization_id": TEST_ORG_ID,
        "user_file_name": "chunked.pdf",
        "pdf_file_name": key,
        "mongo_file_name": key,
        "state": "ocr_completed",
        "upload_date": datetime.now(UTC),
    })
    try:
        file_resp = client.get(
            f"/v0/orgs/{TEST_ORG_ID}/documents/{document_id}/file",
            params={"file_type": "pdf"},
            headers={**get_auth_headers(), "Range": "bytes=200-300"},
        )
        assert file_resp.status_code == 206, file_resp.text
        assert file_resp.content == raw[200:301]
        assert file_resp.headers.get("content-range") == f"bytes 200-300/{len(raw)}"

        aligned_resp = client.get(
            f"/v0/orgs/{TEST_ORG_ID}/documents/{document_id}/file",
            params={"file_type": "pdf"},
            headers={**get_auth_headers(), "Range": "bytes=0-255"},
        )
        assert aligned_resp.status_code == 206, aligned_resp.text
        assert aligned_resp.content == raw[:256]
        assert aligned_resp.headers.get("content-range") == f"bytes 0-255/{len(raw)}"
    finally:
        client.delete(
            f"/v0/orgs/{TEST_ORG_ID}/documents/{document_id}",
            headers=get_auth_headers(),
        )
        await ad.mongodb.delete_blob_async(aq_client, "files", key)


@pytest.mark.asyncio
async def test_get_document_metadata_includes_file_size(test_db, mock_auth, small_pdf):
    """include_content=false returns file_size without downloading bytes."""
    raw = base64.b64decode(small_pdf["content"].split(",", 1)[1])
    upload_resp = client.post(
        f"/v0/orgs/{TEST_ORG_ID}/documents/multipart",
        files=[("file", ("meta_size.pdf", raw, "application/pdf"))],
        headers=_auth_headers_multipart(),
    )
    assert upload_resp.status_code == 200, upload_resp.text
    document_id = upload_resp.json()["document"]["document_id"]

    try:
        meta_resp = client.get(
            f"/v0/orgs/{TEST_ORG_ID}/documents/{document_id}",
            params={"file_type": "pdf", "include_content": "false"},
            headers=get_auth_headers(),
        )
        assert meta_resp.status_code == 200, meta_resp.text
        body = meta_resp.json()
        assert body["content"] is None
        assert body["file_size"] == len(raw)
    finally:
        client.delete(
            f"/v0/orgs/{TEST_ORG_ID}/documents/{document_id}",
            headers=get_auth_headers(),
        )


@pytest.mark.asyncio
async def test_get_document_metadata_skips_file_size_when_disabled(test_db, mock_auth, small_pdf):
    """include_file_size=false avoids GridFS lookup (e.g. poll ticks)."""
    raw = base64.b64decode(small_pdf["content"].split(",", 1)[1])
    upload_resp = client.post(
        f"/v0/orgs/{TEST_ORG_ID}/documents/multipart",
        files=[("file", ("no_size_meta.pdf", raw, "application/pdf"))],
        headers=_auth_headers_multipart(),
    )
    assert upload_resp.status_code == 200, upload_resp.text
    document_id = upload_resp.json()["document"]["document_id"]

    try:
        meta_resp = client.get(
            f"/v0/orgs/{TEST_ORG_ID}/documents/{document_id}",
            params={"file_type": "pdf", "include_content": "false", "include_file_size": "false"},
            headers=get_auth_headers(),
        )
        assert meta_resp.status_code == 200, meta_resp.text
        body = meta_resp.json()
        assert body.get("file_size") is None
    finally:
        client.delete(
            f"/v0/orgs/{TEST_ORG_ID}/documents/{document_id}",
            headers=get_auth_headers(),
        )
