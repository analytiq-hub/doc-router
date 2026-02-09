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
import logging
from unittest.mock import patch, AsyncMock, Mock
from typing import Dict, Any, Tuple

# Import shared test utilities
from .conftest_utils import (
    client, TEST_ORG_ID, 
    get_auth_headers
)
import analytiq_data as ad

logger = logging.getLogger(__name__)

# Check that ENV is set to pytest
assert os.environ["ENV"] == "pytest"

# Mock embedding response for dimension detection
MOCK_EMBEDDING_DIMENSIONS = 1536

def create_mock_embedding_response(num_embeddings=1):
    """Create a mock embedding response with non-zero vectors (required for cosine similarity).
    Uses Mock() not AsyncMock() so get_embedding_cost() does not trigger unawaited coroutines."""
    mock_response = Mock()
    # Generate non-zero embeddings (simple pattern that's not all zeros)
    # Use a small non-zero value to avoid zero vector issues with MongoDB cosine similarity
    embeddings = []
    for i in range(num_embeddings):
        # Create a simple non-zero vector: [0.1, 0.2, 0.3, ...] pattern
        embedding = [0.001 * (j % 100 + 1) for j in range(MOCK_EMBEDDING_DIMENSIONS)]
        embeddings.append({"embedding": embedding})
    mock_response.data = embeddings
    return mock_response


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
    """Create a test knowledge base and return its ID"""
    kb_data = {
        "name": kb_name,
        "tag_ids": [tag_id],
        "chunker_type": "recursive",
        "chunk_size": 100,
        "chunk_overlap": 20
    }
    create_response = client.post(
        f"/v0/orgs/{TEST_ORG_ID}/knowledge-bases",
        json=kb_data,
        headers=get_auth_headers()
    )
    assert create_response.status_code == 200
    return create_response.json()["kb_id"]


async def create_test_tag(tag_name: str) -> str:
    """Create a test tag and return its ID"""
    tag_data = {"name": tag_name, "color": "#FF5733"}
    tag_response = client.post(
        f"/v0/orgs/{TEST_ORG_ID}/tags",
        json=tag_data,
        headers=get_auth_headers()
    )
    assert tag_response.status_code == 200
    return tag_response.json()["id"]


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


# ============================================================================
# PDF File Type Tests
# ============================================================================


@pytest.mark.asyncio
@patch('litellm.get_model_info', return_value={"provider": "openai"})
@patch('litellm.aembedding')
async def test_kb_indexing_pdf_file(mock_embedding, mock_get_model_info, test_db, mock_auth, setup_test_models):
    """
    Test KB indexing for PDF files.
    
    PDF files are OCR-supported, so they use OCR text for indexing.
    """
    logger.info(f"test_kb_indexing_pdf_file() start")
    
    mock_embedding.return_value = create_mock_embedding_response()
    
    try:
        tag_id = await create_test_tag("PDF Test Tag")
        kb_id = await create_test_kb(tag_id, "PDF Test KB")
        
        document_id = str(ObjectId())
        test_text = TEST_CONTENT[".pdf"]
        
        await setup_ocr_document(test_db, document_id, "test_doc.pdf", tag_id, test_text)
        
        analytiq_client = ad.common.get_analytiq_client()
        result = await ad.kb.indexing.index_document_in_kb(
            analytiq_client, kb_id, document_id, TEST_ORG_ID
        )
        
        assert result["chunk_count"] > 0
        assert not result.get("skipped", False)
        
        await verify_indexing_result(analytiq_client, kb_id, document_id, result["chunk_count"])
        
        logger.info(f"test_kb_indexing_pdf_file() completed: {result['chunk_count']} chunks")
        
    except Exception as e:
        logger.error(f"test_kb_indexing_pdf_file() failed: {e}")
        raise


# ============================================================================
# Text File Type Tests
# ============================================================================

@pytest.mark.asyncio
@patch('litellm.get_model_info', return_value={"provider": "openai"})
@patch('litellm.aembedding')
async def test_kb_indexing_txt_file(mock_embedding, mock_get_model_info, test_db, mock_auth, setup_test_models):
    """
    Test KB indexing for .txt files.
    
    Text files are NOT OCR-supported, so they should use original file content for indexing.
    """
    logger.info(f"test_kb_indexing_txt_file() start")
    
    mock_embedding.return_value = create_mock_embedding_response()
    
    try:
        tag_id = await create_test_tag("TXT Test Tag")
        kb_id = await create_test_kb(tag_id, "TXT Test KB")
        
        document_id = str(ObjectId())
        test_text = TEST_CONTENT[".txt"]
        
        await setup_text_file_document(test_db, document_id, "test_doc.txt", tag_id, test_text)
        
        analytiq_client = ad.common.get_analytiq_client()
        result = await ad.kb.indexing.index_document_in_kb(
            analytiq_client, kb_id, document_id, TEST_ORG_ID
        )
        
        assert result["chunk_count"] > 0
        assert not result.get("skipped", False)
        
        await verify_indexing_result(
            analytiq_client, kb_id, document_id, result["chunk_count"],
            content_check="multiple lines"  # Verify original content is used
        )
        
        logger.info(f"test_kb_indexing_txt_file() completed: {result['chunk_count']} chunks")
        
    except Exception as e:
        logger.error(f"test_kb_indexing_txt_file() failed: {e}")
        raise


@pytest.mark.asyncio
@patch('litellm.get_model_info', return_value={"provider": "openai"})
@patch('litellm.aembedding')
async def test_kb_indexing_md_file(mock_embedding, mock_get_model_info, test_db, mock_auth, setup_test_models):
    """
    Test KB indexing for .md files.
    
    Markdown files are NOT OCR-supported, so they should use original markdown content for indexing.
    Markdown structure (headers, lists, formatting) should be preserved.
    """
    logger.info(f"test_kb_indexing_md_file() start")
    
    mock_embedding.return_value = create_mock_embedding_response()
    
    try:
        tag_id = await create_test_tag("MD Test Tag")
        kb_id = await create_test_kb(tag_id, "MD Test KB")
        
        document_id = str(ObjectId())
        test_text = TEST_CONTENT[".md"]
        
        await setup_text_file_document(test_db, document_id, "test_doc.md", tag_id, test_text)
        
        analytiq_client = ad.common.get_analytiq_client()
        result = await ad.kb.indexing.index_document_in_kb(
            analytiq_client, kb_id, document_id, TEST_ORG_ID
        )
        
        assert result["chunk_count"] > 0
        assert not result.get("skipped", False)
        
        # Verify markdown structure is preserved
        db = analytiq_client.mongodb_async[analytiq_client.env]
        vectors_collection = db[f"kb_vectors_{kb_id}"]
        vector = await vectors_collection.find_one({"document_id": document_id})
        assert vector is not None
        chunk_text = vector["chunk_text"]
        # Check that markdown syntax is preserved
        assert ("#" in chunk_text or "**" in chunk_text or "-" in chunk_text), \
            "Markdown structure not preserved in chunk"
        
        await verify_indexing_result(analytiq_client, kb_id, document_id, result["chunk_count"])
        
        logger.info(f"test_kb_indexing_md_file() completed: {result['chunk_count']} chunks")
        
    except Exception as e:
        logger.error(f"test_kb_indexing_md_file() failed: {e}")
        raise


# ============================================================================
# Image File Type Tests
# ============================================================================

@pytest.mark.asyncio
@patch('litellm.get_model_info', return_value={"provider": "openai"})
@patch('litellm.aembedding')
async def test_kb_indexing_jpg_file(mock_embedding, mock_get_model_info, test_db, mock_auth, setup_test_models):
    """
    Test KB indexing for .jpg image files.
    
    Image files are OCR-supported, so they use OCR text for indexing.
    """
    logger.info(f"test_kb_indexing_jpg_file() start")
    
    mock_embedding.return_value = create_mock_embedding_response()
    
    try:
        tag_id = await create_test_tag("JPG Test Tag")
        kb_id = await create_test_kb(tag_id, "JPG Test KB")
        
        document_id = str(ObjectId())
        test_text = TEST_CONTENT[".jpg"]
        
        await setup_ocr_document(test_db, document_id, "test_image.jpg", tag_id, test_text)
        
        analytiq_client = ad.common.get_analytiq_client()
        result = await ad.kb.indexing.index_document_in_kb(
            analytiq_client, kb_id, document_id, TEST_ORG_ID
        )
        
        assert result["chunk_count"] > 0
        assert not result.get("skipped", False)
        
        await verify_indexing_result(analytiq_client, kb_id, document_id, result["chunk_count"])
        
        logger.info(f"test_kb_indexing_jpg_file() completed: {result['chunk_count']} chunks")
        
    except Exception as e:
        logger.error(f"test_kb_indexing_jpg_file() failed: {e}")
        raise


@pytest.mark.asyncio
@patch('litellm.get_model_info', return_value={"provider": "openai"})
@patch('litellm.aembedding')
async def test_kb_indexing_png_file(mock_embedding, mock_get_model_info, test_db, mock_auth, setup_test_models):
    """
    Test KB indexing for .png image files.
    
    Image files are OCR-supported, so they use OCR text for indexing.
    """
    logger.info(f"test_kb_indexing_png_file() start")
    
    mock_embedding.return_value = create_mock_embedding_response()
    
    try:
        tag_id = await create_test_tag("PNG Test Tag")
        kb_id = await create_test_kb(tag_id, "PNG Test KB")
        
        document_id = str(ObjectId())
        test_text = TEST_CONTENT[".png"]
        
        await setup_ocr_document(test_db, document_id, "test_image.png", tag_id, test_text)
        
        analytiq_client = ad.common.get_analytiq_client()
        result = await ad.kb.indexing.index_document_in_kb(
            analytiq_client, kb_id, document_id, TEST_ORG_ID
        )
        
        assert result["chunk_count"] > 0
        assert not result.get("skipped", False)
        
        await verify_indexing_result(analytiq_client, kb_id, document_id, result["chunk_count"])
        
        logger.info(f"test_kb_indexing_png_file() completed: {result['chunk_count']} chunks")
        
    except Exception as e:
        logger.error(f"test_kb_indexing_png_file() failed: {e}")
        raise


# ============================================================================
# Word Document File Type Tests
# ============================================================================

@pytest.mark.asyncio
@patch('litellm.get_model_info', return_value={"provider": "openai"})
@patch('litellm.aembedding')
async def test_kb_indexing_docx_file(mock_embedding, mock_get_model_info, test_db, mock_auth, setup_test_models):
    """
    Test KB indexing for .docx Word documents.
    
    Word documents are converted to PDF, then OCR'd, so they use OCR text for indexing.
    """
    logger.info(f"test_kb_indexing_docx_file() start")
    
    mock_embedding.return_value = create_mock_embedding_response()
    
    try:
        tag_id = await create_test_tag("DOCX Test Tag")
        kb_id = await create_test_kb(tag_id, "DOCX Test KB")
        
        document_id = str(ObjectId())
        test_text = TEST_CONTENT[".docx"]
        
        await setup_ocr_document(test_db, document_id, "test_doc.docx", tag_id, test_text)
        
        analytiq_client = ad.common.get_analytiq_client()
        result = await ad.kb.indexing.index_document_in_kb(
            analytiq_client, kb_id, document_id, TEST_ORG_ID
        )
        
        assert result["chunk_count"] > 0
        assert not result.get("skipped", False)
        
        await verify_indexing_result(analytiq_client, kb_id, document_id, result["chunk_count"])
        
        logger.info(f"test_kb_indexing_docx_file() completed: {result['chunk_count']} chunks")
        
    except Exception as e:
        logger.error(f"test_kb_indexing_docx_file() failed: {e}")
        raise


@pytest.mark.asyncio
@patch('litellm.get_model_info', return_value={"provider": "openai"})
@patch('litellm.aembedding')
async def test_kb_indexing_doc_file(mock_embedding, mock_get_model_info, test_db, mock_auth, setup_test_models):
    """
    Test KB indexing for .doc Word documents.
    
    Word documents are converted to PDF, then OCR'd, so they use OCR text for indexing.
    """
    logger.info(f"test_kb_indexing_doc_file() start")
    
    mock_embedding.return_value = create_mock_embedding_response()
    
    try:
        tag_id = await create_test_tag("DOC Test Tag")
        kb_id = await create_test_kb(tag_id, "DOC Test KB")
        
        document_id = str(ObjectId())
        test_text = "This is test Word .doc file OCR content. " * 10
        
        await setup_ocr_document(test_db, document_id, "test_doc.doc", tag_id, test_text)
        
        analytiq_client = ad.common.get_analytiq_client()
        result = await ad.kb.indexing.index_document_in_kb(
            analytiq_client, kb_id, document_id, TEST_ORG_ID
        )
        
        assert result["chunk_count"] > 0
        assert not result.get("skipped", False)
        
        await verify_indexing_result(analytiq_client, kb_id, document_id, result["chunk_count"])
        
        logger.info(f"test_kb_indexing_doc_file() completed: {result['chunk_count']} chunks")
        
    except Exception as e:
        logger.error(f"test_kb_indexing_doc_file() failed: {e}")
        raise


# ============================================================================
# Structured Data File Type Tests (Should Skip Indexing)
# ============================================================================

@pytest.mark.asyncio
@patch('litellm.get_model_info', return_value={"provider": "openai"})
@patch('litellm.aembedding')
async def test_kb_indexing_csv_file_skipped(mock_embedding, mock_get_model_info, test_db, mock_auth, setup_test_models):
    """
    Test that CSV files are skipped for KB indexing.
    
    CSV files are NOT OCR-supported and have no text extraction.
    They should be skipped with reason "no_text".
    """
    logger.info(f"test_kb_indexing_csv_file_skipped() start")
    
    mock_embedding.return_value = create_mock_embedding_response()
    
    try:
        tag_id = await create_test_tag("CSV Test Tag")
        kb_id = await create_test_kb(tag_id, "CSV Test KB")
        
        document_id = str(ObjectId())
        await setup_structured_data_document(test_db, document_id, "test_data.csv", tag_id)
        
        analytiq_client = ad.common.get_analytiq_client()
        result = await ad.kb.indexing.index_document_in_kb(
            analytiq_client, kb_id, document_id, TEST_ORG_ID
        )
        
        assert result.get("skipped", False) is True
        assert result["chunk_count"] == 0
        assert result.get("reason") == "no_text"
        
        await verify_indexing_result(analytiq_client, kb_id, document_id, 0, should_be_skipped=True)
        
        logger.info(f"test_kb_indexing_csv_file_skipped() completed: correctly skipped")
        
    except Exception as e:
        logger.error(f"test_kb_indexing_csv_file_skipped() failed: {e}")
        raise


@pytest.mark.asyncio
@patch('litellm.get_model_info', return_value={"provider": "openai"})
@patch('litellm.aembedding')
async def test_kb_indexing_xlsx_file_skipped(mock_embedding, mock_get_model_info, test_db, mock_auth, setup_test_models):
    """
    Test that .xlsx Excel files are skipped for KB indexing.
    
    Excel files are NOT OCR-supported and have no text extraction.
    They should be skipped with reason "no_text".
    """
    logger.info(f"test_kb_indexing_xlsx_file_skipped() start")
    
    mock_embedding.return_value = create_mock_embedding_response()
    
    try:
        tag_id = await create_test_tag("XLSX Test Tag")
        kb_id = await create_test_kb(tag_id, "XLSX Test KB")
        
        document_id = str(ObjectId())
        await setup_structured_data_document(test_db, document_id, "test_data.xlsx", tag_id)
        
        analytiq_client = ad.common.get_analytiq_client()
        result = await ad.kb.indexing.index_document_in_kb(
            analytiq_client, kb_id, document_id, TEST_ORG_ID
        )
        
        assert result.get("skipped", False) is True
        assert result["chunk_count"] == 0
        assert result.get("reason") == "no_text"
        
        await verify_indexing_result(analytiq_client, kb_id, document_id, 0, should_be_skipped=True)
        
        logger.info(f"test_kb_indexing_xlsx_file_skipped() completed: correctly skipped")
        
    except Exception as e:
        logger.error(f"test_kb_indexing_xlsx_file_skipped() failed: {e}")
        raise


@pytest.mark.asyncio
@patch('litellm.get_model_info', return_value={"provider": "openai"})
@patch('litellm.aembedding')
async def test_kb_indexing_xls_file_skipped(mock_embedding, mock_get_model_info, test_db, mock_auth, setup_test_models):
    """
    Test that .xls Excel files are skipped for KB indexing.
    
    Excel files are NOT OCR-supported and have no text extraction.
    They should be skipped with reason "no_text".
    """
    logger.info(f"test_kb_indexing_xls_file_skipped() start")
    
    mock_embedding.return_value = create_mock_embedding_response()
    
    try:
        tag_id = await create_test_tag("XLS Test Tag")
        kb_id = await create_test_kb(tag_id, "XLS Test KB")
        
        document_id = str(ObjectId())
        await setup_structured_data_document(test_db, document_id, "test_data.xls", tag_id)
        
        analytiq_client = ad.common.get_analytiq_client()
        result = await ad.kb.indexing.index_document_in_kb(
            analytiq_client, kb_id, document_id, TEST_ORG_ID
        )
        
        assert result.get("skipped", False) is True
        assert result["chunk_count"] == 0
        assert result.get("reason") == "no_text"
        
        await verify_indexing_result(analytiq_client, kb_id, document_id, 0, should_be_skipped=True)
        
        logger.info(f"test_kb_indexing_xls_file_skipped() completed: correctly skipped")
        
    except Exception as e:
        logger.error(f"test_kb_indexing_xls_file_skipped() failed: {e}")
        raise


# ============================================================================
# Integration Tests - Mixed File Types
# ============================================================================

@pytest.mark.asyncio
@patch('litellm.get_model_info', return_value={"provider": "openai"})
@patch('litellm.aembedding')
async def test_kb_indexing_mixed_file_types(mock_embedding, mock_get_model_info, test_db, mock_auth, setup_test_models):
    """
    Test KB indexing with multiple file types in the same KB.
    
    Verifies that different file types (PDF, TXT, MD) can coexist in the same KB
    and each uses the correct content source (OCR text vs original file).
    """
    logger.info(f"test_kb_indexing_mixed_file_types() start")
    
    mock_embedding.return_value = create_mock_embedding_response()
    
    try:
        tag_id = await create_test_tag("Mixed Test Tag")
        kb_id = await create_test_kb(tag_id, "Mixed Test KB")
        
        analytiq_client = ad.common.get_analytiq_client()
        db = analytiq_client.mongodb_async[analytiq_client.env]
        vectors_collection = db[f"kb_vectors_{kb_id}"]
        
        # Test 1: PDF file (OCR text)
        pdf_doc_id = str(ObjectId())
        await setup_ocr_document(test_db, pdf_doc_id, "test.pdf", tag_id, TEST_CONTENT[".pdf"])
        pdf_result = await ad.kb.indexing.index_document_in_kb(analytiq_client, kb_id, pdf_doc_id, TEST_ORG_ID)
        assert pdf_result["chunk_count"] > 0
        
        # Test 2: Text file (original content)
        txt_doc_id = str(ObjectId())
        await setup_text_file_document(test_db, txt_doc_id, "test.txt", tag_id, TEST_CONTENT[".txt"])
        txt_result = await ad.kb.indexing.index_document_in_kb(analytiq_client, kb_id, txt_doc_id, TEST_ORG_ID)
        assert txt_result["chunk_count"] > 0
        
        # Test 3: Markdown file (original content)
        md_doc_id = str(ObjectId())
        await setup_text_file_document(test_db, md_doc_id, "test.md", tag_id, TEST_CONTENT[".md"])
        md_result = await ad.kb.indexing.index_document_in_kb(analytiq_client, kb_id, md_doc_id, TEST_ORG_ID)
        assert md_result["chunk_count"] > 0
        
        # Verify all documents are indexed in the same KB
        total_vectors = await vectors_collection.count_documents({})
        expected_total = pdf_result["chunk_count"] + txt_result["chunk_count"] + md_result["chunk_count"]
        assert total_vectors == expected_total, \
            f"Expected {expected_total} vectors, got {total_vectors}"
        
        logger.info(f"test_kb_indexing_mixed_file_types() completed: PDF={pdf_result['chunk_count']}, TXT={txt_result['chunk_count']}, MD={md_result['chunk_count']}")
        
    except Exception as e:
        logger.error(f"test_kb_indexing_mixed_file_types() failed: {e}")
        raise
