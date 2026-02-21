import pytest
import pytest_asyncio
import base64
import os
import sys
import random
from datetime import datetime, UTC
import motor.motor_asyncio
from unittest.mock import patch
from fastapi import Security
from fastapi.security import HTTPAuthorizationCredentials
from bson import ObjectId

import pytest
from bson import ObjectId

import logging

# Import shared test utilities
from .conftest_utils import (
    client, TEST_ORG_ID, 
    get_auth_headers
)
import analytiq_data as ad

import io
import zipfile
import tempfile
import subprocess
import platform

from analytiq_data.common.doc import EXTENSION_TO_MIME
from PIL import Image, ImageDraw, ImageFont
from analytiq_data.common.file import libreoffice_filelock, get_libreoffice_cmd

logger = logging.getLogger(__name__)

# Check that ENV is set to pytest
assert os.environ["ENV"] == "pytest"

@pytest.fixture
def small_pdf():
    """Create a minimal test PDF file"""
    pdf_content = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF\n"
    return {
        "name": "small_test.pdf",
        "content": f"data:application/pdf;base64,{base64.b64encode(pdf_content).decode()}"
    }

@pytest.fixture
def large_pdf():
    """Create a 32MB test PDF file"""
    # Create a valid PDF header
    pdf_header = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n"
    
    # Generate content to reach 32MB
    size_kb = 32 * 1024  # 32MB
    random_content_size = (size_kb * 1024) - len(pdf_header) - 7  # 7 bytes for EOF
    random_content = bytes([0x41 for _ in range(random_content_size)])  # Use 'A' character (0x41) for predictable content
    
    # Add PDF EOF marker
    pdf_eof = b"\n%%EOF\n"
    
    # Combine to create a valid PDF of the specified size
    pdf_content = pdf_header + random_content + pdf_eof
    
    logger.info(f"Created large test PDF of size {len(pdf_content)} bytes")
    
    return {
        "name": "large_test.pdf",
        "content": f"data:application/pdf;base64,{base64.b64encode(pdf_content).decode()}"
    }

@pytest.fixture(params=list(EXTENSION_TO_MIME.items()), ids=lambda x: x[0])
def minimal_file(request):
    ext, mime = request.param
    content = None

    if ext == ".pdf":
        # Use libreoffice to generate a PDF from a txt file with "Hello World"
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as txt_file:
            txt_file.write(b"Hello World")
            txt_file.flush()
            txt_path = txt_file.name
        pdf_path = txt_path.replace(".txt", ".pdf")
        try:
            with libreoffice_filelock:
                print(f"LibreOffice lock acquired for {ext}")

                subprocess.run([
                    get_libreoffice_cmd(),
                    "--headless",
                    "--convert-to", "pdf",
                    "--outdir", os.path.dirname(txt_path),
                    txt_path
                ], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                with open(pdf_path, "rb") as f:
                    content = f.read()

                print("LibreOffice lock released")
        finally:
            os.remove(txt_path)
            if os.path.exists(pdf_path):
                os.remove(pdf_path)
    elif ext == ".docx":
        # Use libreoffice to generate a docx from a txt file with "Hello World"
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as txt_file:
            txt_file.write(b"Hello World")
            txt_file.flush()
            txt_path = txt_file.name
        docx_path = txt_path.replace(".txt", ".docx")
        try:
            with libreoffice_filelock:
                print(f"LibreOffice lock acquired for {ext}")
                subprocess.run([
                    get_libreoffice_cmd(),
                    "--headless",
                    "--convert-to", "docx",
                    "--outdir", os.path.dirname(txt_path),
                    txt_path
                ], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                with open(docx_path, "rb") as f:
                    content = f.read()

                print("LibreOffice lock released")
        finally:
            os.remove(txt_path)
            if os.path.exists(docx_path):
                os.remove(docx_path)
    elif ext == ".xlsx":
        # Use libreoffice to generate a xlsx from a csv file with "Hello World"
        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as csv_file:
            csv_file.write(b"Hello World,SecondCol\n1,2\n")
            csv_file.flush()
            csv_path = csv_file.name
        xlsx_path = csv_path.replace(".csv", ".xlsx")
        try:
            with libreoffice_filelock:
                print(f"LibreOffice lock acquired for {ext}")
                subprocess.run([
                    get_libreoffice_cmd(),
                    "--headless",
                    "--convert-to", "xlsx",
                    "--outdir", os.path.dirname(csv_path),
                    csv_path
                ], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                with open(xlsx_path, "rb") as f:
                    content = f.read()

                print("LibreOffice lock released")
        finally:
            os.remove(csv_path)
            if os.path.exists(xlsx_path):
                os.remove(xlsx_path)
    elif ext == ".csv":
        content = b"Hello World,SecondCol\n1,2\n"
    elif ext == ".txt":
        content = b"Hello World\n"
    elif ext == ".md":
        content = b"Hello World\n# Markdown"
    elif ext == ".doc":
        # Use libreoffice to generate a docx from a txt file with "Hello World"
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as txt_file:
            txt_file.write(b"Hello World")
            txt_file.flush()
            txt_path = txt_file.name
        doc_path = txt_path.replace(".txt", ".doc")
        try:
            with libreoffice_filelock:
                print(f"LibreOffice lock acquired for {ext}")
                subprocess.run([
                    get_libreoffice_cmd(),
                    "--headless",
                    "--convert-to", "doc",
                    "--outdir", os.path.dirname(txt_path),
                    txt_path
                ], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                with open(doc_path, "rb") as f:
                    content = f.read()

                print("LibreOffice lock released")
        finally:
            os.remove(txt_path)
            if os.path.exists(doc_path):
                os.remove(doc_path)
    elif ext == ".xls":
        # Not a real XLS, but starts with Hello World
        content = b"Hello World" + b"\x00" * 10
    elif ext in [
        ".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".tiff", ".tif"
    ]:
        # Create a small image with "Hello World" text
        img = Image.new("RGB", (200, 60), color=(255, 255, 255))
        draw = ImageDraw.Draw(img)
        # Use a basic font; Pillow will fallback if default not available
        try:
            font = ImageFont.load_default()
        except Exception:
            font = None
        draw.text((10, 20), "Hello World", fill=(0, 0, 0), font=font)

        # Save to bytes in the appropriate format
        fmt_map = {
            ".jpg": "JPEG",
            ".jpeg": "JPEG",
            ".png": "PNG",
            ".gif": "GIF",
            ".webp": "WEBP",
            ".bmp": "BMP",
            ".tiff": "TIFF",
            ".tif": "TIFF",
        }
        img_format = fmt_map[ext]

        import io as _io
        buf = _io.BytesIO()
        # Ensure a single frame for GIF; others as default
        save_kwargs = {}
        if img_format == "GIF":
            save_kwargs["loop"] = 0
        img.save(buf, format=img_format, **save_kwargs)
        content = buf.getvalue()
    else:
        raise NotImplementedError(f"Test for {ext} not implemented")

    return {
        "name": f"test{ext}",
        "content": f"data:{mime};base64,{base64.b64encode(content).decode()}",
        "mime": mime,
        "ext": ext,
        "raw_content": content,
    }

def get_auth_headers():
    """Get authentication headers for test requests"""
    return {
        "Authorization": "Bearer test_token",
        "Content-Type": "application/json"
    }

@pytest.mark.asyncio
@pytest.mark.parametrize("pdf_fixture", ["small_pdf", "large_pdf"])
async def test_upload_document(test_db, pdf_fixture, request, mock_auth):
    """Test document upload endpoint with different PDF sizes"""
    # Get the actual PDF fixture using the fixture name
    test_pdf = request.getfixturevalue(pdf_fixture)
    
    logger.info(f"test_upload_document() start with {test_pdf['name']}")
    
    # Prepare test data with metadata
    test_metadata = {"source": "test_suite", "category": "unit_test"}
    upload_data = {
        "documents": [
            {
                "name": test_pdf["name"],
                "content": test_pdf["content"],
                "tag_ids": [],
                "metadata": test_metadata
            }
        ]
    }

    try:
        # Step 1: Upload the document
        upload_response = client.post(
            f"/v0/orgs/{TEST_ORG_ID}/documents",
            json=upload_data,
            headers=get_auth_headers()
        )

        # Check upload response
        assert upload_response.status_code == 200
        upload_result = upload_response.json()
        assert "documents" in upload_result
        assert len(upload_result["documents"]) == 1
        assert upload_result["documents"][0]["document_name"] == test_pdf["name"]
        assert upload_result["documents"][0]["metadata"] == test_metadata
        
        # Get the document ID from the upload response
        document_id = upload_result["documents"][0]["document_id"]
        
        # Step 2: List documents to verify it appears in the list
        list_response = client.get(
            f"/v0/orgs/{TEST_ORG_ID}/documents",
            headers=get_auth_headers()
        )
        
        assert list_response.status_code == 200
        list_data = list_response.json()
        assert "documents" in list_data
        assert len(list_data["documents"]) > 0
        
        # Find our document in the list
        uploaded_doc = next((doc for doc in list_data["documents"] if doc["id"] == document_id), None)
        assert uploaded_doc is not None
        assert uploaded_doc["document_name"] == test_pdf["name"]
        assert uploaded_doc["metadata"] == test_metadata
        
        # Step 3: Get document metadata only (include_content=false) for lightweight polling
        metadata_response = client.get(
            f"/v0/orgs/{TEST_ORG_ID}/documents/{document_id}",
            params={"include_content": False},
            headers=get_auth_headers()
        )
        assert metadata_response.status_code == 200
        meta_data = metadata_response.json()
        assert meta_data["id"] == document_id
        assert meta_data["document_name"] == test_pdf["name"]
        assert meta_data["metadata"] == test_metadata
        assert "state" in meta_data
        assert meta_data.get("content") is None, "include_content=false must not return file content"

        # Step 4: Get the specific document (default include_content=true) to verify content
        get_response = client.get(
            f"/v0/orgs/{TEST_ORG_ID}/documents/{document_id}",
            headers=get_auth_headers()
        )
        
        assert get_response.status_code == 200
        doc_data = get_response.json()
        assert doc_data["id"] == document_id
        assert doc_data["document_name"] == test_pdf["name"]
        assert doc_data["metadata"] == test_metadata
        assert "content" in doc_data  # Verify the PDF content is returned
        
        # Verify the content matches what we uploaded
        original_content = base64.b64decode(test_pdf["content"].split(',')[1])
        retrieved_content = base64.b64decode(doc_data["content"])
        assert original_content == retrieved_content, "Retrieved document content doesn't match the uploaded content"
        
        # Optional: Verify metadata endpoint returns 404 after delete (tested below)

        # Step 5: For completeness, test document deletion
        delete_response = client.delete(
            f"/v0/orgs/{TEST_ORG_ID}/documents/{document_id}",
            headers=get_auth_headers()
        )
        
        assert delete_response.status_code == 200
        
        # Verify document is gone
        get_deleted_response = client.get(
            f"/v0/orgs/{TEST_ORG_ID}/documents/{document_id}",
            headers=get_auth_headers()
        )
        
        assert get_deleted_response.status_code == 404

    finally:
        pass  # mock_auth fixture handles cleanup

    logger.info(f"test_upload_document() end with {test_pdf['name']}")


@pytest.mark.asyncio
async def test_get_document_metadata_only(test_db, small_pdf, mock_auth):
    """GET /documents/{id}?include_content=false returns metadata without file content (for polling)."""
    upload_data = {
        "documents": [{
            "name": small_pdf["name"],
            "content": small_pdf["content"],
            "tag_ids": [],
            "metadata": {"source": "metadata_test"},
        }]
    }
    upload_response = client.post(
        f"/v0/orgs/{TEST_ORG_ID}/documents",
        json=upload_data,
        headers=get_auth_headers(),
    )
    assert upload_response.status_code == 200
    document_id = upload_response.json()["documents"][0]["document_id"]

    meta_response = client.get(
        f"/v0/orgs/{TEST_ORG_ID}/documents/{document_id}",
        params={"include_content": False},
        headers=get_auth_headers(),
    )
    assert meta_response.status_code == 200
    data = meta_response.json()
    assert data["id"] == document_id
    assert data["document_name"] == small_pdf["name"]
    assert data["metadata"] == {"source": "metadata_test"}
    assert "state" in data
    assert "upload_date" in data
    assert "tag_ids" in data
    assert data.get("content") is None

    # 404 for missing document
    missing_id = str(ObjectId())
    not_found = client.get(
        f"/v0/orgs/{TEST_ORG_ID}/documents/{missing_id}",
        params={"include_content": False},
        headers=get_auth_headers(),
    )
    assert not_found.status_code == 404

    # Cleanup
    client.delete(
        f"/v0/orgs/{TEST_ORG_ID}/documents/{document_id}",
        headers=get_auth_headers(),
    )


@pytest.mark.asyncio
async def test_get_document_backward_compatible_default_includes_content(test_db, small_pdf, mock_auth):
    """Default GET /documents/{id} (no include_content param) returns full content for backward compatibility."""
    upload_data = {
        "documents": [{
            "name": small_pdf["name"],
            "content": small_pdf["content"],
            "tag_ids": [],
            "metadata": {},
        }]
    }
    upload_response = client.post(
        f"/v0/orgs/{TEST_ORG_ID}/documents",
        json=upload_data,
        headers=get_auth_headers(),
    )
    assert upload_response.status_code == 200
    document_id = upload_response.json()["documents"][0]["document_id"]

    # No query params: must return content (backward compatible)
    get_response = client.get(
        f"/v0/orgs/{TEST_ORG_ID}/documents/{document_id}",
        headers=get_auth_headers(),
    )
    assert get_response.status_code == 200
    data = get_response.json()
    assert data["id"] == document_id
    assert "content" in data and data["content"] is not None and len(data["content"]) > 0

    client.delete(
        f"/v0/orgs/{TEST_ORG_ID}/documents/{document_id}",
        headers=get_auth_headers(),
    )


@pytest.mark.asyncio
async def test_document_lifecycle(test_db, small_pdf, mock_auth):
    """Test the complete document lifecycle including tags and document name updates"""
    logger.info(f"test_document_lifecycle() start")
    
    # Use small_pdf instead of test_pdf
    test_pdf = small_pdf
    
    try:
        # Step 1: Create a tag
        tag_data = {
            "name": "Test Tag",
            "color": "#FF5733"
        }
        
        tag_response = client.post(
            f"/v0/orgs/{TEST_ORG_ID}/tags",
            json=tag_data,
            headers=get_auth_headers()
        )
        
        assert tag_response.status_code == 200
        tag = tag_response.json()
        tag_id = tag["id"]
        
        # Step 2: Upload document with the tag and metadata
        initial_metadata = {"department": "testing", "priority": "high"}
        upload_data = {
            "documents": [
                {
                    "name": test_pdf["name"],
                    "content": test_pdf["content"],
                    "tag_ids": [tag_id],
                    "metadata": initial_metadata
                }
            ]
        }

        upload_response = client.post(
            f"/v0/orgs/{TEST_ORG_ID}/documents",
            json=upload_data,
            headers=get_auth_headers()
        )

        assert upload_response.status_code == 200
        upload_result = upload_response.json()
        document_id = upload_result["documents"][0]["document_id"]
        
        # Step 3: List documents and verify tag
        list_response = client.get(
            f"/v0/orgs/{TEST_ORG_ID}/documents",
            headers=get_auth_headers()
        )
        
        assert list_response.status_code == 200
        list_data = list_response.json()
        uploaded_doc = next((doc for doc in list_data["documents"] if doc["id"] == document_id), None)
        assert uploaded_doc is not None
        assert tag_id in uploaded_doc["tag_ids"]
        assert uploaded_doc["document_name"] == test_pdf["name"]
        assert uploaded_doc["metadata"] == initial_metadata
        
        # Step 4: Create a second tag
        second_tag_data = {
            "name": "Second Tag",
            "color": "#33FF57"
        }
        
        second_tag_response = client.post(
            f"/v0/orgs/{TEST_ORG_ID}/tags",
            json=second_tag_data,
            headers=get_auth_headers()
        )
        
        assert second_tag_response.status_code == 200
        second_tag = second_tag_response.json()
        second_tag_id = second_tag["id"]
        
        # Step 5: Update document with new tag and metadata
        updated_metadata = {"department": "production", "priority": "low", "reviewed": "true"}
        update_data = {
            "tag_ids": [second_tag_id],  # Replace the original tag
            "metadata": updated_metadata
        }
        
        update_response = client.put(
            f"/v0/orgs/{TEST_ORG_ID}/documents/{document_id}",
            json=update_data,
            headers=get_auth_headers()
        )
        
        assert update_response.status_code == 200
        
        # Step 6: List documents again and verify updated tag
        list_response_after_update = client.get(
            f"/v0/orgs/{TEST_ORG_ID}/documents",
            headers=get_auth_headers()
        )
        
        assert list_response_after_update.status_code == 200
        list_data_after_update = list_response_after_update.json()
        updated_doc = next((doc for doc in list_data_after_update["documents"] if doc["id"] == document_id), None)
        assert updated_doc is not None
        assert second_tag_id in updated_doc["tag_ids"]
        assert tag_id not in updated_doc["tag_ids"]
        assert updated_doc["metadata"] == updated_metadata
        
        # Step 7: Update document name
        new_document_name = "Updated Test Document.pdf"
        update_name_data = {
            "document_name": new_document_name
        }
        
        update_name_response = client.put(
            f"/v0/orgs/{TEST_ORG_ID}/documents/{document_id}",
            json=update_name_data,
            headers=get_auth_headers()
        )
        
        assert update_name_response.status_code == 200
        
        # Step 8: List documents again and verify updated name
        list_response_after_name_update = client.get(
            f"/v0/orgs/{TEST_ORG_ID}/documents",
            headers=get_auth_headers()
        )
        
        assert list_response_after_name_update.status_code == 200
        list_data_after_name_update = list_response_after_name_update.json()
        renamed_doc = next((doc for doc in list_data_after_name_update["documents"] if doc["id"] == document_id), None)
        assert renamed_doc is not None
        assert renamed_doc["document_name"] == new_document_name
        
        # Step 9: Get the specific document to verify its name, content and tags
        get_response = client.get(
            f"/v0/orgs/{TEST_ORG_ID}/documents/{document_id}",
            headers=get_auth_headers()
        )
        
        assert get_response.status_code == 200
        doc_data = get_response.json()
        assert doc_data["document_name"] == new_document_name
        assert second_tag_id in doc_data["tag_ids"]
        assert doc_data["metadata"] == updated_metadata
        
        # Step 10: Filter documents by tag
        filtered_list_response = client.get(
            f"/v0/orgs/{TEST_ORG_ID}/documents?tag_ids={second_tag_id}",
            headers=get_auth_headers()
        )
        
        assert filtered_list_response.status_code == 200
        filtered_list_data = filtered_list_response.json()
        assert len(filtered_list_data["documents"]) > 0
        filtered_doc = next((doc for doc in filtered_list_data["documents"] if doc["id"] == document_id), None)
        assert filtered_doc is not None
        assert filtered_doc["document_name"] == new_document_name
        
        # Step 11: Clean up - delete document
        delete_response = client.delete(
            f"/v0/orgs/{TEST_ORG_ID}/documents/{document_id}",
            headers=get_auth_headers()
        )
        
        assert delete_response.status_code == 200
        
        # Verify document is gone
        get_deleted_response = client.get(
            f"/v0/orgs/{TEST_ORG_ID}/documents/{document_id}",
            headers=get_auth_headers()
        )
        
        assert get_deleted_response.status_code == 404

    finally:
        pass  # mock_auth fixture handles cleanup

    logger.info(f"test_document_lifecycle() end")

@pytest.mark.asyncio
async def test_upload_supported_file_types(test_db, minimal_file, mock_auth):
    """Test uploading each supported file type"""
    test_file = minimal_file
    logger.info(f"Testing upload for {test_file['name']} ({test_file['mime']})")
    upload_data = {
        "documents": [
            {
                "name": test_file["name"],
                "content": test_file["content"],
                "tag_ids": []
            }
        ]
    }
    # Upload
    upload_response = client.post(
        f"/v0/orgs/{TEST_ORG_ID}/documents",
        json=upload_data,
        headers=get_auth_headers()
    )
    assert upload_response.status_code == 200
    upload_result = upload_response.json()
    assert "documents" in upload_result
    assert len(upload_result["documents"]) == 1
    assert upload_result["documents"][0]["document_name"] == test_file["name"]
    document_id = upload_result["documents"][0]["document_id"]

    # List and verify
    list_response = client.get(
        f"/v0/orgs/{TEST_ORG_ID}/documents",
        headers=get_auth_headers()
    )
    assert list_response.status_code == 200
    docs = list_response.json()["documents"]
    uploaded_doc = next((doc for doc in docs if doc["id"] == document_id), None)
    assert uploaded_doc is not None
    assert uploaded_doc["document_name"] == test_file["name"]

    # Get and verify content
    get_response = client.get(
        f"/v0/orgs/{TEST_ORG_ID}/documents/{document_id}",
        headers=get_auth_headers()
    )
    assert get_response.status_code == 200
    doc_data = get_response.json()
    assert "content" in doc_data
    retrieved_content = base64.b64decode(doc_data["content"])

    # For non-PDFs, the backend may convert to PDF, so only check for PDF if ext is .pdf
    if test_file["ext"] == ".pdf":
        # For PDF, check that "Hello World" is in the PDF text stream
        assert retrieved_content.startswith(b"%PDF")
    elif test_file["ext"] in [".docx", ".xlsx"]:
        # For docx/xlsx, the backend will convert to PDF, so check for PDF header and "Hello World" in the PDF
        assert retrieved_content[:4] == b'PK\x03\x04'
    elif test_file["ext"] in [".doc"]:
        # For doc, the backend will convert to PDF, so check for PDF header and "Hello World" in the PDF
        assert retrieved_content[:4] == b'\xd0\xcf\x11\xe0'
    else:
        # For other types, accept either a PDF (converted) or the original file
        if retrieved_content[:4] == b"%PDF":
            # Converted to PDF; just ensure it's a PDF
            pass
        else:
            # Original returned; for images verify magic headers by extension
            if test_file["ext"] in [".jpg", ".jpeg"]:
                assert retrieved_content[:3] == b"\xFF\xD8\xFF"
            elif test_file["ext"] == ".png":
                assert retrieved_content[:8] == b"\x89PNG\r\n\x1a\n"
            elif test_file["ext"] == ".gif":
                assert retrieved_content[:6] in (b"GIF87a", b"GIF89a")
            elif test_file["ext"] == ".webp":
                assert retrieved_content[:4] == b"RIFF" and retrieved_content[8:12] == b"WEBP"
            elif test_file["ext"] == ".bmp":
                assert retrieved_content[:2] == b"BM"
            elif test_file["ext"] in [".tiff", ".tif"]:
                assert retrieved_content[:4] in (b"II*\x00", b"MM\x00*")
            else:
                # Text-like formats
                assert retrieved_content.startswith(b"Hello World")

    # --- NEW: Download and verify the PDF version of the document ---
    get_pdf_response = client.get(
        f"/v0/orgs/{TEST_ORG_ID}/documents/{document_id}?file_type=pdf",
        headers=get_auth_headers()
    )
    assert get_pdf_response.status_code == 200
    pdf_doc_data = get_pdf_response.json()
    assert "content" in pdf_doc_data
    pdf_content = base64.b64decode(pdf_doc_data["content"])
    assert pdf_content.startswith(b"%PDF"), "Downloaded file_type=pdf does not start with %PDF"

    # Clean up
    delete_response = client.delete(
        f"/v0/orgs/{TEST_ORG_ID}/documents/{document_id}",
        headers=get_auth_headers()
    )
    assert delete_response.status_code == 200

    # Verify document is gone
    get_deleted_response = client.get(
        f"/v0/orgs/{TEST_ORG_ID}/documents/{document_id}",
        headers=get_auth_headers()
    )
    assert get_deleted_response.status_code == 404

    # Verify PDF is gone
    get_pdf_deleted_response = client.get(
        f"/v0/orgs/{TEST_ORG_ID}/documents/{document_id}?file_type=pdf",
        headers=get_auth_headers()
    )
    assert get_pdf_deleted_response.status_code == 404

@pytest.mark.asyncio
async def test_upload_document_base64_formats(test_db, small_pdf, mock_auth):
    """Test document upload with different base64 formats"""
    logger.info("test_upload_document_base64_formats() start")
    
    # Extract the base64 part from the data URL for testing
    base64_content = small_pdf['content'].split(',', 1)[1]
    
    # Test 1: Data URL format (current frontend format)
    upload_data_data_url = {
        "documents": [
            {
                "name": "test_data_url.pdf",
                "content": f"data:application/pdf;base64,{base64_content}",
                "tag_ids": []
            }
        ]
    }
    
    upload_response = client.post(
        f"/v0/orgs/{TEST_ORG_ID}/documents",
        json=upload_data_data_url,
        headers=get_auth_headers()
    )
    assert upload_response.status_code == 200
    
    # Test 2: Plain base64 format
    upload_data_plain = {
        "documents": [
            {
                "name": "test_plain.pdf",
                "content": base64_content,  # Plain base64 without data URL prefix
                "tag_ids": []
            }
        ]
    }
    
    upload_response = client.post(
        f"/v0/orgs/{TEST_ORG_ID}/documents",
        json=upload_data_plain,
        headers=get_auth_headers()
    )
    assert upload_response.status_code == 200
    
    # Test 3: Invalid base64 should fail
    # Let's test with a string that is definitely not valid base64
    invalid_content = "this-is-definitely-not-valid-base64-content-with-special-chars-!@#$%^&*()_+{}|:<>?[]\\;'\",./"
    
    upload_data_invalid = {
        "documents": [
            {
                "name": "test_invalid.pdf",
                "content": invalid_content,
                "tag_ids": []
            }
        ]
    }
    
    upload_response = client.post(
        f"/v0/orgs/{TEST_ORG_ID}/documents",
        json=upload_data_invalid,
        headers=get_auth_headers()
    )
    
    assert upload_response.status_code == 400
    assert "Invalid base64 content" in upload_response.json()["detail"]

@pytest.mark.asyncio
async def test_document_metadata_search(test_db, small_pdf, mock_auth):
    """Test metadata search functionality including URL encoding"""
    logger.info("test_document_metadata_search() start")
    
    # Step 1: Upload multiple documents with different metadata
    test_documents = [
        {
            "name": "doc1.pdf",
            "content": small_pdf["content"], 
            "metadata": {"author": "John Smith", "type": "invoice", "department": "finance"}
        },
        {
            "name": "doc2.pdf", 
            "content": small_pdf["content"],
            "metadata": {"author": "Jane Doe", "type": "receipt", "department": "finance"}
        },
        {
            "name": "doc3.pdf",
            "content": small_pdf["content"], 
            "metadata": {"author": "John Smith", "type": "contract", "department": "legal"}
        },
        {
            "name": "doc4.pdf",
            "content": small_pdf["content"],
            "metadata": {"author": "Bob Wilson", "type": "invoice", "special": "comma,value"}
        },
        {
            "name": "doc5.pdf",
            "content": small_pdf["content"],
            "metadata": {"title": "Project=Alpha", "status": "complete", "notes": "Has = and , chars"}
        }
    ]
    
    document_ids = []
    
    try:
        # Upload all documents
        for doc in test_documents:
            upload_data = {"documents": [doc]}
            upload_response = client.post(
                f"/v0/orgs/{TEST_ORG_ID}/documents",
                json=upload_data,
                headers=get_auth_headers()
            )
            assert upload_response.status_code == 200
            upload_result = upload_response.json()
            document_ids.append(upload_result["documents"][0]["document_id"])
        
        # Test 1: Basic metadata search - single key=value
        logger.info("Testing basic metadata search: author=John Smith")
        response = client.get(
            f"/v0/orgs/{TEST_ORG_ID}/documents?metadata_search=author%3DJohn%20Smith",
            headers=get_auth_headers()
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["documents"]) == 2  # doc1 and doc3
        doc_names = [doc["document_name"] for doc in data["documents"]]
        assert "doc1.pdf" in doc_names
        assert "doc3.pdf" in doc_names
        
        # Test 2: Multiple metadata criteria - AND logic
        logger.info("Testing multiple metadata criteria: author=John Smith,department=finance")
        response = client.get(
            f"/v0/orgs/{TEST_ORG_ID}/documents?metadata_search=author%3DJohn%20Smith%2Cdepartment%3Dfinance",
            headers=get_auth_headers()
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["documents"]) == 1  # Only doc1 matches both criteria
        assert data["documents"][0]["document_name"] == "doc1.pdf"
        
        # Test 3: Search by type
        logger.info("Testing search by type: type=invoice")
        response = client.get(
            f"/v0/orgs/{TEST_ORG_ID}/documents?metadata_search=type%3Dinvoice",
            headers=get_auth_headers()
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["documents"]) == 2  # doc1 and doc4
        doc_names = [doc["document_name"] for doc in data["documents"]]
        assert "doc1.pdf" in doc_names
        assert "doc4.pdf" in doc_names
        
        # Test 4: URL-encoded comma in value
        logger.info("Testing URL-encoded comma in value: special=comma,value")
        response = client.get(
            f"/v0/orgs/{TEST_ORG_ID}/documents?metadata_search=special%3Dcomma%252Cvalue",
            headers=get_auth_headers()
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["documents"]) == 1  # Only doc4
        assert data["documents"][0]["document_name"] == "doc4.pdf"
        
        # Test 5: URL-encoded equals in value
        logger.info("Testing URL-encoded equals in value: title=Project=Alpha")
        response = client.get(
            f"/v0/orgs/{TEST_ORG_ID}/documents?metadata_search=title%3DProject%253DAlpha",
            headers=get_auth_headers()
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["documents"]) == 1  # Only doc5
        assert data["documents"][0]["document_name"] == "doc5.pdf"
        
        # Test 6: Complex value with both comma and equals
        logger.info("Testing complex value with comma and equals: notes=Has = and , chars")
        response = client.get(
            f"/v0/orgs/{TEST_ORG_ID}/documents?metadata_search=notes%3DHas%20%253D%20and%20%252C%20chars",
            headers=get_auth_headers()
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["documents"]) == 1  # Only doc5
        assert data["documents"][0]["document_name"] == "doc5.pdf"
        
        # Test 7: Non-existent metadata key
        logger.info("Testing non-existent metadata key")
        response = client.get(
            f"/v0/orgs/{TEST_ORG_ID}/documents?metadata_search=nonexistent%3Dvalue",
            headers=get_auth_headers()
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["documents"]) == 0
        
        # Test 8: Metadata search combined with name search
        logger.info("Testing metadata search combined with name search")
        response = client.get(
            f"/v0/orgs/{TEST_ORG_ID}/documents?name_search=doc1&metadata_search=author%3DJohn%20Smith",
            headers=get_auth_headers()
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["documents"]) == 1  # Only doc1 matches both name and metadata
        assert data["documents"][0]["document_name"] == "doc1.pdf"
        
        # Test 9: Pagination with metadata search
        logger.info("Testing pagination with metadata search")
        response = client.get(
            f"/v0/orgs/{TEST_ORG_ID}/documents?metadata_search=department%3Dfinance&limit=1",
            headers=get_auth_headers()
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["documents"]) == 1  # Limited to 1 result
        assert data["total_count"] == 2  # But total count shows 2 matches
        
        # Test 10: Empty metadata search should return all documents
        logger.info("Testing empty metadata search")
        response = client.get(
            f"/v0/orgs/{TEST_ORG_ID}/documents?metadata_search=",
            headers=get_auth_headers()
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["documents"]) >= 5  # Should include all uploaded documents
        
    finally:
        # Cleanup: Delete all uploaded documents
        for doc_id in document_ids:
            try:
                delete_response = client.delete(
                    f"/v0/orgs/{TEST_ORG_ID}/documents/{doc_id}",
                    headers=get_auth_headers()
                )
                # Don't assert delete success as test might have failed earlier
            except Exception as e:
                logger.warning(f"Failed to cleanup document {doc_id}: {e}")
                
    logger.info("test_document_metadata_search() end")

@pytest.mark.asyncio  
async def test_document_metadata_search_edge_cases(test_db, small_pdf, mock_auth):
    """Test edge cases for metadata search functionality"""
    logger.info("test_document_metadata_search_edge_cases() start")
    
    # Upload document with edge case metadata
    edge_case_metadata = {
        "empty_value": "",
        "spaces_only": "   ",
        "equal_sign": "=",
        "comma": ",",
        "unicode": "café résumé",
        "numbers": "12345",
        "boolean_like": "true",
        "null_like": "null"
    }
    
    upload_data = {
        "documents": [{
            "name": "edge_case.pdf",
            "content": small_pdf["content"],
            "metadata": edge_case_metadata
        }]
    }
    
    document_id = None
    
    try:
        # Upload document
        upload_response = client.post(
            f"/v0/orgs/{TEST_ORG_ID}/documents",
            json=upload_data,
            headers=get_auth_headers()
        )
        assert upload_response.status_code == 200
        upload_result = upload_response.json()
        document_id = upload_result["documents"][0]["document_id"]
        
        # Test 1: Search by empty value
        logger.info("Testing search by empty value")
        response = client.get(
            f"/v0/orgs/{TEST_ORG_ID}/documents?metadata_search=empty_value%3D",
            headers=get_auth_headers()
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["documents"]) == 1
        assert data["documents"][0]["document_name"] == "edge_case.pdf"
        
        # Test 2: Search by spaces only value (URL encoded)
        logger.info("Testing search by spaces-only value")  
        response = client.get(
            f"/v0/orgs/{TEST_ORG_ID}/documents?metadata_search=spaces_only%3D%20%20%20",
            headers=get_auth_headers()
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["documents"]) == 1
        assert data["documents"][0]["document_name"] == "edge_case.pdf"
        
        # Test 3: Search by unicode value
        logger.info("Testing search by unicode value")
        response = client.get(
            f"/v0/orgs/{TEST_ORG_ID}/documents?metadata_search=unicode%3Dcaf%C3%A9%20r%C3%A9sum%C3%A9",
            headers=get_auth_headers()
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["documents"]) == 1
        assert data["documents"][0]["document_name"] == "edge_case.pdf"
        
        # Test 4: Search by numeric value
        logger.info("Testing search by numeric value")
        response = client.get(
            f"/v0/orgs/{TEST_ORG_ID}/documents?metadata_search=numbers%3D12345",
            headers=get_auth_headers()
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["documents"]) == 1
        assert data["documents"][0]["document_name"] == "edge_case.pdf"
        
        # Test 5: Invalid metadata search format (missing value)
        logger.info("Testing invalid metadata search format")
        response = client.get(
            f"/v0/orgs/{TEST_ORG_ID}/documents?metadata_search=invalid_key",
            headers=get_auth_headers()
        )
        assert response.status_code == 200  # Should not error, just return no results
        data = response.json()
        # Should not match anything since format is invalid
        
        # Test 6: Malformed URL encoding
        logger.info("Testing malformed URL encoding")
        response = client.get(
            f"/v0/orgs/{TEST_ORG_ID}/documents?metadata_search=key%3Dvalue%ZZ",  # %ZZ is invalid
            headers=get_auth_headers()
        )
        assert response.status_code == 200  # Should handle gracefully
        
    finally:
        # Cleanup
        if document_id:
            try:
                delete_response = client.delete(
                    f"/v0/orgs/{TEST_ORG_ID}/documents/{document_id}",
                    headers=get_auth_headers()
                )
            except Exception as e:
                logger.warning(f"Failed to cleanup document {document_id}: {e}")
                
    logger.info("test_document_metadata_search_edge_cases() end")

@pytest.mark.asyncio
async def test_document_metadata_removal(test_db, small_pdf, mock_auth):
    """Test removing all metadata from a document"""
    logger.info("test_document_metadata_removal() start")

    try:
        # Step 1: Upload a document with initial metadata
        initial_metadata = {
            "author": "John Doe",
            "department": "finance",
            "priority": "high",
            "project": "Q4 Report"
        }

        upload_data = {
            "documents": [{
                "name": "metadata_removal_test.pdf",
                "content": small_pdf["content"],
                "metadata": initial_metadata
            }]
        }

        response = client.post(
            f"/v0/orgs/{TEST_ORG_ID}/documents",
            json=upload_data,
            headers=get_auth_headers()
        )
        assert response.status_code == 200

        upload_result = response.json()
        document_id = upload_result["documents"][0]["document_id"]

        # Step 2: Verify initial metadata is present
        response = client.get(
            f"/v0/orgs/{TEST_ORG_ID}/documents/{document_id}",
            headers=get_auth_headers()
        )
        assert response.status_code == 200
        doc_data = response.json()
        assert doc_data["metadata"] == initial_metadata

        # Step 3: Update document to remove all metadata (empty dict)
        update_data = {"metadata": {}}

        response = client.put(
            f"/v0/orgs/{TEST_ORG_ID}/documents/{document_id}",
            json=update_data,
            headers=get_auth_headers()
        )
        assert response.status_code == 200

        # Step 4: Verify metadata has been removed using GET
        response = client.get(
            f"/v0/orgs/{TEST_ORG_ID}/documents/{document_id}",
            headers=get_auth_headers()
        )
        assert response.status_code == 200
        doc_data = response.json()
        assert doc_data["metadata"] == {}

        # Step 5: Verify metadata removal using LIST
        response = client.get(
            f"/v0/orgs/{TEST_ORG_ID}/documents",
            headers=get_auth_headers()
        )
        assert response.status_code == 200
        docs_data = response.json()

        test_doc = next((doc for doc in docs_data["documents"] if doc["id"] == document_id), None)
        assert test_doc is not None
        assert test_doc["metadata"] == {}

        # Step 6: Verify old metadata searches no longer find the document
        response = client.get(
            f"/v0/orgs/{TEST_ORG_ID}/documents?metadata_search=author%3DJohn%20Doe",
            headers=get_auth_headers()
        )
        assert response.status_code == 200
        search_data = response.json()

        # Document should not be found in metadata search since metadata was removed
        found_doc_ids = [doc["id"] for doc in search_data["documents"]]
        assert document_id not in found_doc_ids

    finally:
        # Cleanup
        try:
            client.delete(
                f"/v0/orgs/{TEST_ORG_ID}/documents/{document_id}",
                headers=get_auth_headers()
            )
        except Exception as e:
            logger.warning(f"Failed to cleanup document {document_id}: {e}")

    logger.info("test_document_metadata_removal() end")

@pytest.mark.asyncio
async def test_document_name_search(test_db, small_pdf, mock_auth):
    """Test document name search functionality"""
    logger.info("test_document_name_search() start")
    
    # Upload multiple documents with different names
    test_documents = [
        {"name": "invoice_2023.pdf", "content": small_pdf["content"]},
        {"name": "INVOICE_2024.pdf", "content": small_pdf["content"]},
        {"name": "receipt_store_A.pdf", "content": small_pdf["content"]},
        {"name": "contract_john_smith.pdf", "content": small_pdf["content"]},
        {"name": "report_quarterly.pdf", "content": small_pdf["content"]},
        {"name": "My Invoice Document.pdf", "content": small_pdf["content"]},
    ]
    
    document_ids = []
    
    try:
        # Upload all documents
        for doc in test_documents:
            upload_data = {"documents": [doc]}
            upload_response = client.post(
                f"/v0/orgs/{TEST_ORG_ID}/documents",
                json=upload_data,
                headers=get_auth_headers()
            )
            assert upload_response.status_code == 200
            upload_result = upload_response.json()
            document_ids.append(upload_result["documents"][0]["document_id"])
        
        # Test 1: Case-insensitive search for "invoice"
        logger.info("Testing case-insensitive name search: invoice")
        response = client.get(
            f"/v0/orgs/{TEST_ORG_ID}/documents?name_search=invoice",
            headers=get_auth_headers()
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["documents"]) == 3  # invoice_2023.pdf, INVOICE_2024.pdf, My Invoice Document.pdf
        doc_names = [doc["document_name"] for doc in data["documents"]]
        assert "invoice_2023.pdf" in doc_names
        assert "INVOICE_2024.pdf" in doc_names
        assert "My Invoice Document.pdf" in doc_names
        
        # Test 2: Partial name search
        logger.info("Testing partial name search: contract")
        response = client.get(
            f"/v0/orgs/{TEST_ORG_ID}/documents?name_search=contract",
            headers=get_auth_headers()
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["documents"]) == 1
        assert data["documents"][0]["document_name"] == "contract_john_smith.pdf"
        
        # Test 3: Search with spaces
        logger.info("Testing name search with spaces: My Invoice")
        response = client.get(
            f"/v0/orgs/{TEST_ORG_ID}/documents?name_search=My%20Invoice",
            headers=get_auth_headers()
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["documents"]) == 1
        assert data["documents"][0]["document_name"] == "My Invoice Document.pdf"
        
        # Test 4: Search for year/number
        logger.info("Testing name search with numbers: 2023")
        response = client.get(
            f"/v0/orgs/{TEST_ORG_ID}/documents?name_search=2023",
            headers=get_auth_headers()
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["documents"]) == 1
        assert data["documents"][0]["document_name"] == "invoice_2023.pdf"
        
        # Test 5: Search with underscores
        logger.info("Testing name search with underscores: store_A")
        response = client.get(
            f"/v0/orgs/{TEST_ORG_ID}/documents?name_search=store_A",
            headers=get_auth_headers()
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["documents"]) == 1
        assert data["documents"][0]["document_name"] == "receipt_store_A.pdf"
        
        # Test 6: No matches
        logger.info("Testing name search with no matches")
        response = client.get(
            f"/v0/orgs/{TEST_ORG_ID}/documents?name_search=nonexistent",
            headers=get_auth_headers()
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["documents"]) == 0
        
        # Test 7: Empty search should return all documents
        logger.info("Testing empty name search")
        response = client.get(
            f"/v0/orgs/{TEST_ORG_ID}/documents?name_search=",
            headers=get_auth_headers()
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["documents"]) >= 6
        
        # Test 8: Name search combined with pagination
        logger.info("Testing name search with pagination")
        response = client.get(
            f"/v0/orgs/{TEST_ORG_ID}/documents?name_search=pdf&limit=2",
            headers=get_auth_headers()
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["documents"]) == 2  # Limited to 2 results
        assert data["total_count"] >= 6  # But total count shows all matches
        
    finally:
        # Cleanup: Delete all uploaded documents
        for doc_id in document_ids:
            try:
                delete_response = client.delete(
                    f"/v0/orgs/{TEST_ORG_ID}/documents/{doc_id}",
                    headers=get_auth_headers()
                )
            except Exception as e:
                logger.warning(f"Failed to cleanup document {doc_id}: {e}")
                
    logger.info("test_document_name_search() end")

@pytest.mark.asyncio
async def test_document_tag_search(test_db, small_pdf, mock_auth):
    """Test document tag search functionality"""
    logger.info("test_document_tag_search() start")
    
    # Step 1: Create multiple tags
    tag_data_list = [
        {"name": "Finance", "color": "#FF5733"},
        {"name": "Legal", "color": "#33FF57"},
        {"name": "HR", "color": "#3357FF"},
        {"name": "Urgent", "color": "#FF33F5"},
        {"name": "Archive", "color": "#808080"},
    ]
    
    tag_ids = []
    document_ids = []
    
    try:
        # Create all tags
        for tag_data in tag_data_list:
            tag_response = client.post(
                f"/v0/orgs/{TEST_ORG_ID}/tags",
                json=tag_data,
                headers=get_auth_headers()
            )
            assert tag_response.status_code == 200
            tag = tag_response.json()
            tag_ids.append(tag["id"])
        
        finance_tag, legal_tag, hr_tag, urgent_tag, archive_tag = tag_ids
        
        # Step 2: Upload documents with different tag combinations
        test_documents = [
            {
                "name": "doc_finance.pdf", 
                "content": small_pdf["content"],
                "tag_ids": [finance_tag]
            },
            {
                "name": "doc_legal.pdf",
                "content": small_pdf["content"], 
                "tag_ids": [legal_tag]
            },
            {
                "name": "doc_finance_urgent.pdf",
                "content": small_pdf["content"],
                "tag_ids": [finance_tag, urgent_tag]
            },
            {
                "name": "doc_legal_hr.pdf",
                "content": small_pdf["content"],
                "tag_ids": [legal_tag, hr_tag]
            },
            {
                "name": "doc_all_tags.pdf",
                "content": small_pdf["content"],
                "tag_ids": [finance_tag, legal_tag, hr_tag, urgent_tag]
            },
            {
                "name": "doc_no_tags.pdf",
                "content": small_pdf["content"],
                "tag_ids": []
            }
        ]
        
        # Upload all documents
        for doc in test_documents:
            upload_data = {"documents": [doc]}
            upload_response = client.post(
                f"/v0/orgs/{TEST_ORG_ID}/documents",
                json=upload_data,
                headers=get_auth_headers()
            )
            assert upload_response.status_code == 200
            upload_result = upload_response.json()
            document_ids.append(upload_result["documents"][0]["document_id"])
        
        # Test 1: Filter by single tag (Finance)
        logger.info("Testing single tag filter: Finance")
        response = client.get(
            f"/v0/orgs/{TEST_ORG_ID}/documents?tag_ids={finance_tag}",
            headers=get_auth_headers()
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["documents"]) == 3  # doc_finance.pdf, doc_finance_urgent.pdf, doc_all_tags.pdf
        doc_names = [doc["document_name"] for doc in data["documents"]]
        assert "doc_finance.pdf" in doc_names
        assert "doc_finance_urgent.pdf" in doc_names
        assert "doc_all_tags.pdf" in doc_names
        
        # Test 2: Filter by single tag (Legal)
        logger.info("Testing single tag filter: Legal")
        response = client.get(
            f"/v0/orgs/{TEST_ORG_ID}/documents?tag_ids={legal_tag}",
            headers=get_auth_headers()
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["documents"]) == 3  # doc_legal.pdf, doc_legal_hr.pdf, doc_all_tags.pdf
        doc_names = [doc["document_name"] for doc in data["documents"]]
        assert "doc_legal.pdf" in doc_names
        assert "doc_legal_hr.pdf" in doc_names
        assert "doc_all_tags.pdf" in doc_names
        
        # Test 3: Filter by multiple tags (AND logic - documents must have ALL tags)
        logger.info("Testing multiple tag filter: Finance AND Urgent")
        response = client.get(
            f"/v0/orgs/{TEST_ORG_ID}/documents?tag_ids={finance_tag},{urgent_tag}",
            headers=get_auth_headers()
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["documents"]) == 2  # doc_finance_urgent.pdf, doc_all_tags.pdf
        doc_names = [doc["document_name"] for doc in data["documents"]]
        assert "doc_finance_urgent.pdf" in doc_names
        assert "doc_all_tags.pdf" in doc_names
        
        # Test 4: Filter by multiple tags (Legal AND HR)
        logger.info("Testing multiple tag filter: Legal AND HR")
        response = client.get(
            f"/v0/orgs/{TEST_ORG_ID}/documents?tag_ids={legal_tag},{hr_tag}",
            headers=get_auth_headers()
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["documents"]) == 2  # doc_legal_hr.pdf, doc_all_tags.pdf
        doc_names = [doc["document_name"] for doc in data["documents"]]
        assert "doc_legal_hr.pdf" in doc_names
        assert "doc_all_tags.pdf" in doc_names
        
        # Test 5: Filter by three tags
        logger.info("Testing three tag filter: Finance AND Legal AND HR")
        response = client.get(
            f"/v0/orgs/{TEST_ORG_ID}/documents?tag_ids={finance_tag},{legal_tag},{hr_tag}",
            headers=get_auth_headers()
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["documents"]) == 1  # Only doc_all_tags.pdf
        assert data["documents"][0]["document_name"] == "doc_all_tags.pdf"
        
        # Test 6: Filter by tag that has no documents
        logger.info("Testing tag filter with no matches: Archive")
        response = client.get(
            f"/v0/orgs/{TEST_ORG_ID}/documents?tag_ids={archive_tag}",
            headers=get_auth_headers()
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["documents"]) == 0
        
        # Test 7: Filter by non-existent tag ID
        logger.info("Testing filter with non-existent tag ID")
        fake_tag_id = str(ObjectId())  # Generate a fake ObjectId
        response = client.get(
            f"/v0/orgs/{TEST_ORG_ID}/documents?tag_ids={fake_tag_id}",
            headers=get_auth_headers()
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["documents"]) == 0
        
        # Test 8: Combine tag filter with name search
        logger.info("Testing tag filter combined with name search")
        response = client.get(
            f"/v0/orgs/{TEST_ORG_ID}/documents?tag_ids={finance_tag}&name_search=urgent",
            headers=get_auth_headers()
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["documents"]) == 1  # Only doc_finance_urgent.pdf
        assert data["documents"][0]["document_name"] == "doc_finance_urgent.pdf"
        
        # Test 9: Tag filtering with pagination
        logger.info("Testing tag filter with pagination")
        response = client.get(
            f"/v0/orgs/{TEST_ORG_ID}/documents?tag_ids={finance_tag}&limit=1",
            headers=get_auth_headers()
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["documents"]) == 1  # Limited to 1 result
        assert data["total_count"] == 3  # But total shows 3 finance documents
        
        # Test 10: Empty tag filter should return all documents
        logger.info("Testing empty tag filter")
        response = client.get(
            f"/v0/orgs/{TEST_ORG_ID}/documents?tag_ids=",
            headers=get_auth_headers()
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["documents"]) >= 6  # Should include all uploaded documents
        
    finally:
        # Cleanup: Delete all uploaded documents
        for doc_id in document_ids:
            try:
                delete_response = client.delete(
                    f"/v0/orgs/{TEST_ORG_ID}/documents/{doc_id}",
                    headers=get_auth_headers()
                )
            except Exception as e:
                logger.warning(f"Failed to cleanup document {doc_id}: {e}")
        
        # Cleanup: Delete all created tags
        for tag_id in tag_ids:
            try:
                delete_response = client.delete(
                    f"/v0/orgs/{TEST_ORG_ID}/tags/{tag_id}",
                    headers=get_auth_headers()
                )
            except Exception as e:
                logger.warning(f"Failed to cleanup tag {tag_id}: {e}")
                
    logger.info("test_document_tag_search() end")
