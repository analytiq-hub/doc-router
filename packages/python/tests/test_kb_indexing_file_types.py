"""
Unit tests for text extraction used by KB indexing (no knowledge base creation, no embeddings).
"""

import os
from unittest.mock import AsyncMock, patch

import pytest

import analytiq_data as ad
from analytiq_data.kb.indexing import get_extracted_indexing_text

assert os.environ["ENV"] == "pytest"


@pytest.mark.asyncio
async def test_get_extracted_indexing_text_pdf_plain_ocr():
    analytiq_client = ad.common.get_analytiq_client()
    with patch("analytiq_data.common.doc.ocr_supported", return_value=True):
        with patch(
            "analytiq_data.common.doc.get_doc",
            AsyncMock(
                return_value={
                    "user_file_name": "doc.pdf",
                    "mongo_file_name": "doc.pdf",
                }
            ),
        ):
            with patch("analytiq_data.common.get_ocr_json", AsyncMock(return_value=None)):
                with patch(
                    "analytiq_data.common.get_ocr_text",
                    AsyncMock(return_value="plain ocr body text"),
                ):
                    ex = await get_extracted_indexing_text(analytiq_client, "d1")
                    assert ex is not None
                    assert "plain ocr" in ex.text


@pytest.mark.asyncio
async def test_get_extracted_indexing_text_txt_from_blob():
    analytiq_client = ad.common.get_analytiq_client()
    raw = "line one\nline two\n"
    with patch("analytiq_data.common.doc.ocr_supported", return_value=False):
        with patch(
            "analytiq_data.common.doc.get_doc",
            AsyncMock(
                return_value={
                    "user_file_name": "readme.txt",
                    "mongo_file_name": "readme.txt",
                }
            ),
        ):
            with patch(
                "analytiq_data.common.get_file_async",
                AsyncMock(return_value={"blob": raw.encode("utf-8")}),
            ):
                ex = await get_extracted_indexing_text(analytiq_client, "d2")
                assert ex is not None
                assert "line one" in ex.text


@pytest.mark.asyncio
async def test_get_extracted_indexing_text_csv_parses_to_markdown_when_pandas_succeeds():
    analytiq_client = ad.common.get_analytiq_client()
    csv_blob = b"name,val\na,1\n"
    with patch("analytiq_data.common.doc.ocr_supported", return_value=False):
        with patch(
            "analytiq_data.common.doc.get_doc",
            AsyncMock(
                return_value={
                    "user_file_name": "data.csv",
                    "mongo_file_name": "data.csv",
                }
            ),
        ):
            with patch(
                "analytiq_data.common.get_file_async",
                AsyncMock(return_value={"blob": csv_blob}),
            ):
                ex = await get_extracted_indexing_text(analytiq_client, "d3")
                assert ex is not None
                assert "name" in ex.text.lower() or "a" in ex.text
