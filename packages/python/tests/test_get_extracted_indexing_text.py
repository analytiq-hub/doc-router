"""
Unit tests for analytiq_data.kb.indexing.get_extracted_indexing_text.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from analytiq_data.kb.indexing import get_extracted_indexing_text


@pytest.mark.asyncio
@patch("analytiq_data.kb.indexing.ad.common.doc.get_doc", new_callable=AsyncMock)
async def test_returns_none_when_document_missing(mock_get_doc):
    mock_get_doc.return_value = None
    client = object()
    out = await get_extracted_indexing_text(client, "doc-1")
    assert out is None


@pytest.mark.asyncio
@patch("analytiq_data.kb.indexing.ad.ocr.get_ocr_text", new_callable=AsyncMock)
@patch("analytiq_data.kb.indexing.ad.ocr.get_ocr_json", new_callable=AsyncMock)
@patch("analytiq_data.kb.indexing.ad.common.doc.get_doc", new_callable=AsyncMock)
async def test_ocr_returns_none_when_no_ocr_json(
    mock_get_doc, mock_get_ocr_json, mock_get_ocr_text
):
    mock_get_doc.return_value = {"user_file_name": "scan.pdf", "mongo_file_name": "blob-key"}
    mock_get_ocr_json.return_value = None
    mock_get_ocr_text.return_value = None
    client = object()
    out = await get_extracted_indexing_text(client, "doc-1")
    assert out is None


@pytest.mark.asyncio
@patch("analytiq_data.kb.indexing.ad.ocr.get_ocr_text", new_callable=AsyncMock)
@patch("analytiq_data.kb.indexing.ad.aws.textract.open_textract_document_from_ocr_json")
@patch("analytiq_data.kb.indexing.ad.ocr.get_ocr_json", new_callable=AsyncMock)
@patch("analytiq_data.kb.indexing.ad.common.doc.get_doc", new_callable=AsyncMock)
async def test_ocr_returns_none_when_no_pages(
    mock_get_doc, mock_get_ocr_json, mock_open_doc, mock_get_ocr_text
):
    mock_get_doc.return_value = {"user_file_name": "scan.pdf", "mongo_file_name": "blob-key"}
    mock_get_ocr_json.return_value = {"Blocks": []}
    textract_doc = MagicMock()
    textract_doc.pages = []
    mock_open_doc.return_value = textract_doc
    mock_get_ocr_text.return_value = None
    client = object()
    out = await get_extracted_indexing_text(client, "doc-1")
    assert out is None


@pytest.mark.asyncio
@patch("analytiq_data.kb.indexing.ad.aws.textract.open_textract_document_from_ocr_json")
@patch("analytiq_data.kb.indexing.ad.ocr.get_ocr_json", new_callable=AsyncMock)
@patch("analytiq_data.kb.indexing.ad.common.doc.get_doc", new_callable=AsyncMock)
async def test_ocr_returns_plain_text_when_no_tables(
    mock_get_doc, mock_get_ocr_json, mock_open_doc
):
    mock_get_doc.return_value = {"user_file_name": "scan.pdf", "mongo_file_name": "blob-key"}
    mock_get_ocr_json.return_value = {
        "Blocks": [{"BlockType": "LINE", "Text": "hi", "Page": 1}]
    }
    textract_doc = MagicMock()
    textract_doc.pages = [MagicMock()]
    textract_doc.get_text.return_value = "linearized text"
    mock_open_doc.return_value = textract_doc
    client = object()
    out = await get_extracted_indexing_text(client, "doc-1")
    assert out is not None
    assert out.text == "linearized text"
    assert out.page_offsets == []
    textract_doc.get_text.assert_called_once()


@pytest.mark.asyncio
@patch("analytiq_data.kb.indexing.ad.aws.textract.open_textract_document_from_ocr_json")
@patch("analytiq_data.kb.indexing.ad.ocr.get_ocr_json", new_callable=AsyncMock)
@patch("analytiq_data.kb.indexing.ad.common.doc.get_doc", new_callable=AsyncMock)
async def test_ocr_returns_markdown_when_tables(
    mock_get_doc, mock_get_ocr_json, mock_open_doc
):
    mock_get_doc.return_value = {"user_file_name": "scan.pdf", "mongo_file_name": "blob-key"}
    ocr_json = {
        "Blocks": [
            {"BlockType": "TABLE", "Id": "t1"},
        ]
    }
    mock_get_ocr_json.return_value = ocr_json
    textract_doc = MagicMock()
    textract_doc.pages = [MagicMock()]
    textract_doc.to_markdown.return_value = "| h |\n| - |"
    mock_open_doc.return_value = textract_doc
    client = object()
    out = await get_extracted_indexing_text(client, "doc-42")
    assert out is not None
    assert out.text == "| h |\n| - |"
    assert out.page_offsets == []
    textract_doc.to_markdown.assert_called_once()


@pytest.mark.asyncio
@patch("analytiq_data.kb.indexing.ad.common.get_file_async", new_callable=AsyncMock)
@patch("analytiq_data.kb.indexing.ad.common.doc.get_doc", new_callable=AsyncMock)
async def test_txt_returns_utf8_decoded_content(mock_get_doc, mock_get_file):
    mock_get_doc.return_value = {
        "user_file_name": "notes.txt",
        "mongo_file_name": "files/notes.txt",
    }
    mock_get_file.return_value = {"blob": b"hello \xc3\xbcber"}
    client = object()
    out = await get_extracted_indexing_text(client, "doc-1")
    assert out is not None
    assert out.text == "hello über"
    assert out.page_offsets == []


@pytest.mark.asyncio
@patch("analytiq_data.kb.indexing.ad.common.get_file_async", new_callable=AsyncMock)
@patch("analytiq_data.kb.indexing.ad.common.doc.get_doc", new_callable=AsyncMock)
async def test_txt_falls_back_to_latin1(mock_get_doc, mock_get_file):
    mock_get_doc.return_value = {
        "user_file_name": "notes.txt",
        "mongo_file_name": "files/notes.txt",
    }
    mock_get_file.return_value = {"blob": b"\xe9cole"}
    client = object()
    out = await get_extracted_indexing_text(client, "doc-1")
    assert out is not None
    assert out.text == "école"


@pytest.mark.asyncio
@patch("analytiq_data.kb.indexing.ad.common.get_file_async", new_callable=AsyncMock)
@patch("analytiq_data.kb.indexing.ad.common.doc.get_doc", new_callable=AsyncMock)
async def test_csv_returns_markdown_table(mock_get_doc, mock_get_file):
    mock_get_doc.return_value = {
        "user_file_name": "data.csv",
        "mongo_file_name": "files/data.csv",
    }
    mock_get_file.return_value = {"blob": b"name,score\nalice,90\nbob,85"}
    client = object()
    out = await get_extracted_indexing_text(client, "doc-1")
    assert out is not None
    assert "name" in out.text
    assert "alice" in out.text
    assert out.page_offsets == []


@pytest.mark.asyncio
@patch("analytiq_data.kb.indexing.ad.common.get_file_async", new_callable=AsyncMock)
@patch("analytiq_data.kb.indexing.ad.common.doc.get_doc", new_callable=AsyncMock)
async def test_csv_returns_none_when_blob_missing(mock_get_doc, mock_get_file):
    mock_get_doc.return_value = {
        "user_file_name": "data.csv",
        "mongo_file_name": "files/data.csv",
    }
    mock_get_file.return_value = None
    client = object()
    out = await get_extracted_indexing_text(client, "doc-1")
    assert out is None


@pytest.mark.asyncio
@patch("analytiq_data.kb.indexing.ad.common.get_file_async", new_callable=AsyncMock)
@patch("analytiq_data.kb.indexing.ad.common.doc.get_doc", new_callable=AsyncMock)
async def test_txt_returns_none_when_blob_empty(mock_get_doc, mock_get_file):
    mock_get_doc.return_value = {
        "user_file_name": "empty.txt",
        "mongo_file_name": "files/empty.txt",
    }
    mock_get_file.return_value = {"blob": b""}
    client = object()
    out = await get_extracted_indexing_text(client, "doc-1")
    assert out is None
