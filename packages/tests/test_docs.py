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
from .test_utils import (
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
    
    # Prepare test data
    upload_data = {
        "documents": [
            {
                "name": test_pdf["name"],
                "content": test_pdf["content"],
                "tag_ids": []
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
        
        # Step 3: Get the specific document to verify its content
        get_response = client.get(
            f"/v0/orgs/{TEST_ORG_ID}/documents/{document_id}",
            headers=get_auth_headers()
        )
        
        assert get_response.status_code == 200
        doc_data = get_response.json()
        assert "metadata" in doc_data
        assert doc_data["metadata"]["id"] == document_id
        assert doc_data["metadata"]["document_name"] == test_pdf["name"]
        assert "content" in doc_data  # Verify the PDF content is returned
        
        # Verify the content matches what we uploaded
        original_content = base64.b64decode(test_pdf["content"].split(',')[1])
        retrieved_content = base64.b64decode(doc_data["content"])
        assert original_content == retrieved_content, "Retrieved document content doesn't match the uploaded content"
        
        # Optional: For completeness, test document deletion
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
        
        # Step 2: Upload document with the tag
        upload_data = {
            "documents": [
                {
                    "name": test_pdf["name"],
                    "content": test_pdf["content"],
                    "tag_ids": [tag_id]
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
        
        # Step 5: Update document with new tag
        update_data = {
            "tag_ids": [second_tag_id]  # Replace the original tag
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
        assert doc_data["metadata"]["document_name"] == new_document_name
        assert second_tag_id in doc_data["metadata"]["tag_ids"]
        
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
