"""
Unit tests for KB indexing with different file types.

Each file type has its own dedicated test routine to verify:
- Correct content source (OCR text vs original file)
- Successful indexing or appropriate skipping
- Vector creation and content preservation

Supported file types tested:
- PDF files (.pdf) - OCR supported
- Image files (.jpg, .png) - OCR supported
- Word documents (.docx, .doc) - OCR supported after PDF conversion
- Text files (.txt) - OCR not supported, uses original content
- Markdown files (.md) - OCR not supported, uses original content
- CSV files (.csv) - OCR not supported, should skip
- Excel files (.xls, .xlsx) - OCR not supported, should skip
"""

import pytest
from bson import ObjectId
import os
from datetime import datetime, UTC
from unittest.mock import patch

from .conftest_utils import TEST_ORG_ID
from .kb_test_helpers import create_kb_api, create_mock_embedding_response, create_tag_api
import analytiq_data as ad

assert os.environ["ENV"] == "pytest"


# Test data for different file types
TEST_CONTENT = {
    ".pdf": "This is test PDF content for knowledge base indexing. " * 10,
    ".txt": "This is test text file content for knowledge base indexing.\n\nIt has multiple lines.\nAnd paragraphs.",
    ".md": "# Test Markdown Document\n\nThis is a **markdown** file for testing.\n\n## Section 1\n\n- Item 1\n- Item 2\n\n## Section 2\n\nSome more content here.",
    ".jpg": "This is test image OCR content. " * 10,  # Simulated OCR text
    ".png": "This is test PNG image OCR content. " * 10,  # Simulated OCR text
    ".docx": "This is test Word document OCR content. " * 10,  # Simulated OCR text after PDF conversion
    ".csv": "name,age,city\nJohn,30,NYC\nJane,25,LA",  # CSV content (won't be indexed)
    ".xlsx": "This is test Excel file content. " * 10,  # Simulated content (won't be indexed)
}


# ============================================================================
# Helper Functions
# ============================================================================

async def create_test_kb(tag_id: str, kb_name: str) -> str:
    return create_kb_api(kb_name, [tag_id])


async def create_test_tag(tag_name: str) -> str:
    return create_tag_api(tag_name)


async def setup_ocr_document(
    test_db,
    document_id: str,
    file_name: str,
    tag_id: str,
    ocr_text: str
) -> None:
    """Set up a document that uses OCR text (PDF, images, Word docs)"""
    await test_db.docs.insert_one({
        "_id": ObjectId(document_id),
        "organization_id": TEST_ORG_ID,
        "user_file_name": file_name,
        "mongo_file_name": f"{document_id}{os.path.splitext(file_name)[1]}",
        "pdf_file_name": f"{document_id}.pdf",
        "tag_ids": [tag_id],
        "upload_date": datetime.now(UTC),
        "state": ad.common.doc.DOCUMENT_STATE_OCR_COMPLETED
    })
    
    # Save OCR text
    analytiq_client = ad.common.get_analytiq_client()
    await ad.common.ocr.save_ocr_text(analytiq_client, document_id, ocr_text)


async def setup_text_file_document(
    test_db,
    document_id: str,
    file_name: str,
    tag_id: str,
    file_content: str
) -> None:
    """Set up a document that uses original file content (.txt, .md)"""
    ext = os.path.splitext(file_name)[1]
    await test_db.docs.insert_one({
        "_id": ObjectId(document_id),
        "organization_id": TEST_ORG_ID,
        "user_file_name": file_name,
        "mongo_file_name": f"{document_id}{ext}",
        "pdf_file_name": f"{document_id}.pdf",  # Still has PDF (converted)
        "tag_ids": [tag_id],
        "upload_date": datetime.now(UTC),
        "state": ad.common.doc.DOCUMENT_STATE_OCR_COMPLETED
    })
    
    # Save original file content (not OCR text)
    analytiq_client = ad.common.get_analytiq_client()
    mime_type = ad.common.doc.EXTENSION_TO_MIME.get(ext, "text/plain")
    await ad.common.save_file_async(
        analytiq_client,
        file_name=f"{document_id}{ext}",
        blob=file_content.encode("utf-8"),
        metadata={"document_id": document_id, "type": mime_type}
    )


async def setup_structured_data_document(
    test_db,
    document_id: str,
    file_name: str,
    tag_id: str
) -> None:
    """Set up a document that cannot be indexed (CSV, Excel)"""
    ext = os.path.splitext(file_name)[1]
    await test_db.docs.insert_one({
        "_id": ObjectId(document_id),
        "organization_id": TEST_ORG_ID,
        "user_file_name": file_name,
        "mongo_file_name": f"{document_id}{ext}",
        "pdf_file_name": f"{document_id}.pdf",  # Converted to PDF
        "tag_ids": [tag_id],
        "upload_date": datetime.now(UTC),
        "state": ad.common.doc.DOCUMENT_STATE_OCR_COMPLETED
    })
    # Note: No OCR text and no text extraction - these files are skipped


async def verify_indexing_result(
    analytiq_client,
    kb_id: str,
    document_id: str,
    expected_chunks: int,
    should_be_skipped: bool = False,
    content_check: str = None
) -> None:
    """Verify indexing results"""
    db = analytiq_client.mongodb_async[analytiq_client.env]
    vectors_collection = db[f"kb_vectors_{kb_id}"]
    
    if should_be_skipped:
        vector_count = await vectors_collection.count_documents({"document_id": document_id})
        assert vector_count == 0, f"Expected no vectors for skipped document, got {vector_count}"
    else:
        vector_count = await vectors_collection.count_documents({"document_id": document_id})
        assert vector_count == expected_chunks, f"Expected {expected_chunks} vectors, got {vector_count}"
        
        if content_check:
            vector = await vectors_collection.find_one({"document_id": document_id})
            assert vector is not None, "No vector found"
            assert content_check in vector["chunk_text"], f"Content check failed: '{content_check}' not in chunk text"


_DOC_OCR_BODY = "This is test Word .doc file OCR content. " * 10

_OCR_FILE_CASES = [
    ("pdf", "test_doc.pdf", TEST_CONTENT[".pdf"]),
    ("jpg", "test_image.jpg", TEST_CONTENT[".jpg"]),
    ("png", "test_image.png", TEST_CONTENT[".png"]),
    ("docx", "test_doc.docx", TEST_CONTENT[".docx"]),
    ("doc", "test_doc.doc", _DOC_OCR_BODY),
]


@pytest.mark.asyncio
@pytest.mark.parametrize("name,file_name,body", _OCR_FILE_CASES)
@patch('litellm.get_model_info', return_value={"provider": "openai"})
@patch('litellm.aembedding')
async def test_kb_indexing_ocr_file_types(
    mock_embedding, mock_get_model_info, test_db, mock_auth, setup_test_models,
    name, file_name, body,
):
    """PDF, images, and Word docs use OCR text for indexing."""
    mock_embedding.return_value = create_mock_embedding_response()
    tag_id = await create_test_tag(f"{name.upper()} Test Tag")
    kb_id = await create_test_kb(tag_id, f"{name.upper()} Test KB")
    document_id = str(ObjectId())
    await setup_ocr_document(test_db, document_id, file_name, tag_id, body)
    analytiq_client = ad.common.get_analytiq_client()
    result = await ad.kb.indexing.index_document_in_kb(
        analytiq_client, kb_id, document_id, TEST_ORG_ID
    )
    assert result["chunk_count"] > 0
    assert not result.get("skipped", False)
    await verify_indexing_result(analytiq_client, kb_id, document_id, result["chunk_count"])


_TEXT_FILE_CASES = [
    ("txt", "test_doc.txt", TEST_CONTENT[".txt"], "multiple lines", False),
    ("md", "test_doc.md", TEST_CONTENT[".md"], None, True),
]


@pytest.mark.asyncio
@pytest.mark.parametrize("name,file_name,body,content_check,check_md", _TEXT_FILE_CASES)
@patch('litellm.get_model_info', return_value={"provider": "openai"})
@patch('litellm.aembedding')
async def test_kb_indexing_plaintext_file_types(
    mock_embedding, mock_get_model_info, test_db, mock_auth, setup_test_models,
    name, file_name, body, content_check, check_md,
):
    """.txt and .md use original file content (not OCR)."""
    mock_embedding.return_value = create_mock_embedding_response()
    tag_id = await create_test_tag(f"{name.upper()} Test Tag")
    kb_id = await create_test_kb(tag_id, f"{name.upper()} Test KB")
    document_id = str(ObjectId())
    await setup_text_file_document(test_db, document_id, file_name, tag_id, body)
    analytiq_client = ad.common.get_analytiq_client()
    result = await ad.kb.indexing.index_document_in_kb(
        analytiq_client, kb_id, document_id, TEST_ORG_ID
    )
    assert result["chunk_count"] > 0
    assert not result.get("skipped", False)
    if check_md:
        db = analytiq_client.mongodb_async[analytiq_client.env]
        vector = await db[f"kb_vectors_{kb_id}"].find_one({"document_id": document_id})
        ct = vector["chunk_text"]
        assert "#" in ct or "**" in ct or "-" in ct
    await verify_indexing_result(
        analytiq_client, kb_id, document_id, result["chunk_count"],
        content_check=content_check,
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("filename", ["test_data.csv", "test_data.xlsx", "test_data.xls"])
@patch('litellm.get_model_info', return_value={"provider": "openai"})
@patch('litellm.aembedding')
async def test_kb_indexing_structured_files_skipped(
    mock_embedding, mock_get_model_info, test_db, mock_auth, setup_test_models,
    filename,
):
    """CSV / Excel have no extractable text for KB indexing."""
    mock_embedding.return_value = create_mock_embedding_response()
    ext = filename.rsplit(".", 1)[-1].upper()
    tag_id = await create_test_tag(f"{ext} Skip Tag")
    kb_id = await create_test_kb(tag_id, f"{ext} Skip KB")
    document_id = str(ObjectId())
    await setup_structured_data_document(test_db, document_id, filename, tag_id)
    analytiq_client = ad.common.get_analytiq_client()
    result = await ad.kb.indexing.index_document_in_kb(
        analytiq_client, kb_id, document_id, TEST_ORG_ID
    )
    assert result.get("skipped") is True
    assert result["chunk_count"] == 0
    assert result.get("reason") == "no_text"
    await verify_indexing_result(analytiq_client, kb_id, document_id, 0, should_be_skipped=True)


# ============================================================================
# Integration Tests - Mixed File Types
# ============================================================================

@pytest.mark.asyncio
@patch('litellm.get_model_info', return_value={"provider": "openai"})
@patch('litellm.aembedding')
async def test_kb_indexing_mixed_file_types(mock_embedding, mock_get_model_info, test_db, mock_auth, setup_test_models):
    """PDF, TXT, and MD can coexist in one KB (OCR vs original text sources)."""
    mock_embedding.return_value = create_mock_embedding_response()
    tag_id = await create_test_tag("Mixed Test Tag")
    kb_id = await create_test_kb(tag_id, "Mixed Test KB")
    analytiq_client = ad.common.get_analytiq_client()
    db = analytiq_client.mongodb_async[analytiq_client.env]
    vectors_collection = db[f"kb_vectors_{kb_id}"]

    pdf_doc_id = str(ObjectId())
    await setup_ocr_document(test_db, pdf_doc_id, "test.pdf", tag_id, TEST_CONTENT[".pdf"])
    pdf_result = await ad.kb.indexing.index_document_in_kb(analytiq_client, kb_id, pdf_doc_id, TEST_ORG_ID)
    assert pdf_result["chunk_count"] > 0

    txt_doc_id = str(ObjectId())
    await setup_text_file_document(test_db, txt_doc_id, "test.txt", tag_id, TEST_CONTENT[".txt"])
    txt_result = await ad.kb.indexing.index_document_in_kb(analytiq_client, kb_id, txt_doc_id, TEST_ORG_ID)
    assert txt_result["chunk_count"] > 0

    md_doc_id = str(ObjectId())
    await setup_text_file_document(test_db, md_doc_id, "test.md", tag_id, TEST_CONTENT[".md"])
    md_result = await ad.kb.indexing.index_document_in_kb(analytiq_client, kb_id, md_doc_id, TEST_ORG_ID)
    assert md_result["chunk_count"] > 0

    total_vectors = await vectors_collection.count_documents({})
    expected_total = pdf_result["chunk_count"] + txt_result["chunk_count"] + md_result["chunk_count"]
    assert total_vectors == expected_total
