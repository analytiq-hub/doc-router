"""
Unit tests for document prompt construction (_build_prompt_context) in analytiq_data.llm.llm.

Covers peer grouping, metadata include filters, OCR/PDF toggles, and PDF attachment shape
(file block vs embedded base64) for different providers / model capabilities.
"""

import base64
from datetime import datetime, UTC
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from bson import ObjectId

import analytiq_data as ad
from analytiq_data.llm.llm import _build_prompt_context, _prompt_used_from_grouped_user_blocks
from tests.conftest_utils import TEST_ORG_ID


def _user_text_blocks(messages):
    """Flatten user message content to list of text strings (text blocks only)."""
    user = messages[1]
    assert user["role"] == "user"
    content = user["content"]
    assert isinstance(content, list)
    return [b["text"] for b in content if b.get("type") == "text"]


def _user_file_blocks(messages):
    user = messages[1]
    return [b for b in user["content"] if b.get("type") == "file"]


@pytest.mark.asyncio
async def test_build_prompt_context_metadata_keys_filters(test_db, mock_auth, setup_test_models):
    """Only listed metadata_keys appear in document headers; others are omitted."""
    analytiq_client = ad.common.get_analytiq_client()
    doc = {
        "_id": ObjectId(),
        "metadata": {"invoice_id": "INV-1", "internal_only": "secret"},
        "user_file_name": "doc.pdf",
    }
    group_cfg = {
        "peer_match_keys": [],
        "include": {"ocr_text": False, "pdf": False, "metadata_keys": ["invoice_id"]},
    }
    with (
        patch("analytiq_data.llm.llm.ad.common.get_prompt_group_config", new_callable=AsyncMock, return_value=group_cfg),
        patch("analytiq_data.llm.llm.ad.common.get_prompt_content", new_callable=AsyncMock, return_value="Extract fields."),
    ):
        messages, peer_run, prompt_used = await _build_prompt_context(
            analytiq_client,
            doc,
            "dummy_revid",
            TEST_ORG_ID,
            "SYSTEM",
            llm_provider="openai",
            llm_model="gpt-4o",
            api_key="sk-test",
        )
    assert peer_run is None
    texts = "\n".join(_user_text_blocks(messages))
    assert "invoice_id" in texts
    assert '"INV-1"' in texts
    assert "internal_only" not in texts
    assert "secret" not in texts
    assert "ocr_text:" not in prompt_used
    assert f"<{doc['_id']}_pdf>" not in prompt_used


@pytest.mark.asyncio
async def test_build_prompt_context_empty_metadata_keys_omits_metadata_section(
    test_db, mock_auth, setup_test_models
):
    """Empty metadata_keys means no metadata: block even if document has metadata."""
    analytiq_client = ad.common.get_analytiq_client()
    doc = {"_id": ObjectId(), "metadata": {"x": 1}, "user_file_name": "d.pdf"}
    group_cfg = {
        "peer_match_keys": [],
        "include": {"ocr_text": False, "pdf": False, "metadata_keys": []},
    }
    with (
        patch("analytiq_data.llm.llm.ad.common.get_prompt_group_config", new_callable=AsyncMock, return_value=group_cfg),
        patch("analytiq_data.llm.llm.ad.common.get_prompt_content", new_callable=AsyncMock, return_value="Hi."),
    ):
        messages, _, _ = await _build_prompt_context(
            analytiq_client,
            doc,
            "dummy_revid",
            TEST_ORG_ID,
            "SYS",
            "openai",
            "gpt-4o",
            "k",
        )
    doc_header = [t for t in _user_text_blocks(messages) if t.startswith("[Document #1]")][0]
    assert "metadata:" not in doc_header


@pytest.mark.asyncio
async def test_build_prompt_context_metadata_star_includes_all(test_db, mock_auth, setup_test_models):
    """metadata_keys ['*'] includes entire metadata dict."""
    analytiq_client = ad.common.get_analytiq_client()
    doc = {"_id": ObjectId(), "metadata": {"a": 1, "b": 2}, "user_file_name": "d.pdf"}
    group_cfg = {
        "peer_match_keys": [],
        "include": {"ocr_text": False, "pdf": False, "metadata_keys": ["*"]},
    }
    with (
        patch("analytiq_data.llm.llm.ad.common.get_prompt_group_config", new_callable=AsyncMock, return_value=group_cfg),
        patch("analytiq_data.llm.llm.ad.common.get_prompt_content", new_callable=AsyncMock, return_value="Hi."),
    ):
        messages, _, _ = await _build_prompt_context(
            analytiq_client,
            doc,
            "dummy_revid",
            TEST_ORG_ID,
            "SYS",
            "openai",
            "gpt-4o",
            "k",
        )
    blob = "\n".join(_user_text_blocks(messages))
    assert '"a": 1' in blob
    assert '"b": 2' in blob


@pytest.mark.asyncio
async def test_build_prompt_context_ocr_toggle(test_db, mock_auth, setup_test_models):
    """include.ocr_text false skips OCR blocks; true includes get_extracted_text output."""
    analytiq_client = ad.common.get_analytiq_client()
    doc = {"_id": ObjectId(), "metadata": {}, "user_file_name": "scan.pdf"}

    async def _group_off(_client, _revid):
        return {"peer_match_keys": [], "include": {"ocr_text": False, "pdf": False, "metadata_keys": []}}

    async def _group_on(_client, _revid):
        return {"peer_match_keys": [], "include": {"ocr_text": True, "pdf": False, "metadata_keys": []}}

    with patch("analytiq_data.llm.llm.ad.common.get_prompt_content", new_callable=AsyncMock, return_value="X"):
        with patch(
            "analytiq_data.llm.llm.ad.common.get_prompt_group_config",
            new_callable=AsyncMock,
            side_effect=_group_off,
        ):
            messages_off, _, used_off = await _build_prompt_context(
                analytiq_client, doc, "r", TEST_ORG_ID, "SYS", "openai", "gpt-4o", "k"
            )
        assert "ocr_text:" not in "\n".join(_user_text_blocks(messages_off))
        assert "ocr_text:" not in used_off

        with (
            patch(
                "analytiq_data.llm.llm.ad.common.get_prompt_group_config",
                new_callable=AsyncMock,
                side_effect=_group_on,
            ),
            patch(
                "analytiq_data.llm.llm.get_extracted_llm_text",
                new_callable=AsyncMock,
                return_value="LINE 1\nLINE 2",
            ),
        ):
            messages_on, _, used_on = await _build_prompt_context(
                analytiq_client, doc, "r", TEST_ORG_ID, "SYS", "openai", "gpt-4o", "k"
            )
    joined = "\n".join(_user_text_blocks(messages_on))
    assert "ocr_text:\nLINE 1\nLINE 2" in joined
    assert f"ocr_text:\n<{doc['_id']}_ocr_text>" in used_on


@pytest.mark.asyncio
async def test_build_prompt_context_pdf_toggle_off_skips_attachment(test_db, mock_auth, setup_test_models):
    """include.pdf false skips file blocks, embedded pdf text, and get_file_attachment."""
    analytiq_client = ad.common.get_analytiq_client()
    doc = {"_id": ObjectId(), "metadata": {}, "user_file_name": "z.pdf"}
    group_cfg = {
        "peer_match_keys": [],
        "include": {"ocr_text": False, "pdf": False, "metadata_keys": []},
    }
    attach = AsyncMock(return_value=(b"%PDF fake", "z.pdf"))
    with (
        patch("analytiq_data.llm.llm.ad.common.get_prompt_group_config", new_callable=AsyncMock, return_value=group_cfg),
        patch("analytiq_data.llm.llm.ad.common.get_prompt_content", new_callable=AsyncMock, return_value="P"),
        patch("analytiq_data.llm.llm.get_file_attachment", new=attach),
        patch("litellm.utils.supports_pdf_input", return_value=True),
    ):
        messages, _, used = await _build_prompt_context(
            analytiq_client, doc, "r", TEST_ORG_ID, "SYS", "openai", "gpt-4o", "k"
        )
    attach.assert_not_called()
    assert _user_file_blocks(messages) == []
    assert not any(t.startswith("pdf:\n") for t in _user_text_blocks(messages))
    assert f"<{doc['_id']}_pdf>" not in used


@pytest.mark.asyncio
async def test_build_prompt_context_pdf_file_block_non_openai(test_db, mock_auth, setup_test_models):
    """When model supports PDF and provider is not xai, non-OpenAI uses file_data PDF block."""
    analytiq_client = ad.common.get_analytiq_client()
    pdf_bytes = b"%PDF-1.4\n1 0 obj<<>>endobj trailer<<>>\n%%EOF\n"
    doc = {"_id": ObjectId(), "metadata": {}, "user_file_name": "x.pdf"}
    group_cfg = {
        "peer_match_keys": [],
        "include": {"ocr_text": False, "pdf": True, "metadata_keys": []},
    }
    with (
        patch("analytiq_data.llm.llm.ad.common.get_prompt_group_config", new_callable=AsyncMock, return_value=group_cfg),
        patch("analytiq_data.llm.llm.ad.common.get_prompt_content", new_callable=AsyncMock, return_value="Z"),
        patch("analytiq_data.llm.llm.get_file_attachment", new_callable=AsyncMock, return_value=(pdf_bytes, "x.pdf")),
        patch("litellm.utils.supports_pdf_input", return_value=True),
    ):
        messages, _, prompt_used = await _build_prompt_context(
            analytiq_client, doc, "r", TEST_ORG_ID, "SYS", "anthropic", "claude-sonnet-4-20250514", "k"
        )
    files = _user_file_blocks(messages)
    assert len(files) == 1
    assert files[0]["file"]["file_data"].startswith("data:application/pdf;base64,")
    b64 = files[0]["file"]["file_data"].split(",", 1)[1]
    assert base64.b64decode(b64) == pdf_bytes
    assert f"pdf:\n<{doc['_id']}_pdf>" in prompt_used


@pytest.mark.asyncio
async def test_build_prompt_context_pdf_openai_uploads_file(test_db, mock_auth, setup_test_models):
    """OpenAI path uploads bytes and sends file_id block."""
    analytiq_client = ad.common.get_analytiq_client()
    pdf_bytes = b"%PDF-1.4\nfake\n%%EOF\n"
    doc = {"_id": ObjectId(), "metadata": {}, "user_file_name": "q.pdf"}
    group_cfg = {
        "peer_match_keys": [],
        "include": {"ocr_text": False, "pdf": True, "metadata_keys": []},
    }
    mock_create = AsyncMock(return_value=SimpleNamespace(id="file-openai-xyz"))
    with (
        patch("analytiq_data.llm.llm.ad.common.get_prompt_group_config", new_callable=AsyncMock, return_value=group_cfg),
        patch("analytiq_data.llm.llm.ad.common.get_prompt_content", new_callable=AsyncMock, return_value="Z"),
        patch("analytiq_data.llm.llm.get_file_attachment", new_callable=AsyncMock, return_value=(pdf_bytes, "q.pdf")),
        patch("litellm.utils.supports_pdf_input", return_value=True),
        patch("analytiq_data.llm.llm._litellm_acreate_file_with_retry", new=mock_create),
    ):
        messages, _, _ = await _build_prompt_context(
            analytiq_client, doc, "r", TEST_ORG_ID, "SYS", "openai", "gpt-4o", "sk-x"
        )
    mock_create.assert_awaited_once()
    files = _user_file_blocks(messages)
    assert len(files) == 1
    assert files[0]["file"]["file_id"] == "file-openai-xyz"


@pytest.mark.asyncio
async def test_build_prompt_context_pdf_embedded_when_no_vision(test_db, mock_auth, setup_test_models):
    """When supports_pdf_input is false, PDF is embedded as base64 text (pdf:\\n...)."""
    analytiq_client = ad.common.get_analytiq_client()
    pdf_bytes = b"%PDF-1.4\nz\n%%EOF\n"
    doc = {"_id": ObjectId(), "metadata": {}, "user_file_name": "z.pdf"}
    group_cfg = {
        "peer_match_keys": [],
        "include": {"ocr_text": False, "pdf": True, "metadata_keys": []},
    }
    with (
        patch("analytiq_data.llm.llm.ad.common.get_prompt_group_config", new_callable=AsyncMock, return_value=group_cfg),
        patch("analytiq_data.llm.llm.ad.common.get_prompt_content", new_callable=AsyncMock, return_value="Z"),
        patch("analytiq_data.llm.llm.get_file_attachment", new_callable=AsyncMock, return_value=(pdf_bytes, "z.pdf")),
        patch("litellm.utils.supports_pdf_input", return_value=False),
    ):
        messages, _, _ = await _build_prompt_context(
            analytiq_client, doc, "r", TEST_ORG_ID, "SYS", "openai", "some-text-model", "k"
        )
    assert _user_file_blocks(messages) == []
    texts = _user_text_blocks(messages)
    assert any(t.startswith("pdf:\n") and base64.b64decode(t[5:]) == pdf_bytes for t in texts)


@pytest.mark.asyncio
async def test_build_prompt_context_xai_embeds_pdf_even_if_vision_supported(test_db, mock_auth, setup_test_models):
    """xai never uses file blocks; PDF is embedded as text when include.pdf is true."""
    analytiq_client = ad.common.get_analytiq_client()
    pdf_bytes = b"%PDF-1.4\nxai\n%%EOF\n"
    doc = {"_id": ObjectId(), "metadata": {}, "user_file_name": "x.pdf"}
    group_cfg = {
        "peer_match_keys": [],
        "include": {"ocr_text": False, "pdf": True, "metadata_keys": []},
    }
    with (
        patch("analytiq_data.llm.llm.ad.common.get_prompt_group_config", new_callable=AsyncMock, return_value=group_cfg),
        patch("analytiq_data.llm.llm.ad.common.get_prompt_content", new_callable=AsyncMock, return_value="Z"),
        patch("analytiq_data.llm.llm.get_file_attachment", new_callable=AsyncMock, return_value=(pdf_bytes, "x.pdf")),
        patch("litellm.utils.supports_pdf_input", return_value=True),
    ):
        messages, _, _ = await _build_prompt_context(
            analytiq_client, doc, "r", TEST_ORG_ID, "SYS", "xai", "grok-2-latest", "k"
        )
    assert _user_file_blocks(messages) == []
    assert any(t.startswith("pdf:\n") for t in _user_text_blocks(messages))


@pytest.mark.asyncio
async def test_build_prompt_context_peer_group_order_and_match_ids(test_db, mock_auth, setup_test_models):
    """peer_match_keys loads peers from Mongo; source doc first, then others by sort order."""
    analytiq_client = ad.common.get_analytiq_client()
    t0 = datetime(2024, 1, 1, tzinfo=UTC)
    t1 = datetime(2024, 1, 2, tzinfo=UTC)
    t2 = datetime(2024, 1, 3, tzinfo=UTC)
    oid_early = ObjectId()
    oid_src = ObjectId()
    oid_late = ObjectId()
    await test_db.docs.insert_many(
        [
            {
                "_id": oid_early,
                "organization_id": TEST_ORG_ID,
                "metadata": {"batch_id": "batch-99", "slot": "early"},
                "user_file_name": "early.pdf",
                "created_at": t0,
            },
            {
                "_id": oid_src,
                "organization_id": TEST_ORG_ID,
                "metadata": {"batch_id": "batch-99", "slot": "source"},
                "user_file_name": "source.pdf",
                "created_at": t1,
            },
            {
                "_id": oid_late,
                "organization_id": TEST_ORG_ID,
                "metadata": {"batch_id": "batch-99", "slot": "late"},
                "user_file_name": "late.pdf",
                "created_at": t2,
            },
        ]
    )
    source = await test_db.docs.find_one({"_id": oid_src})
    group_cfg = {
        "peer_match_keys": ["batch_id"],
        "include": {"ocr_text": False, "pdf": False, "metadata_keys": ["slot"]},
    }
    with (
        patch("analytiq_data.llm.llm.ad.common.get_prompt_group_config", new_callable=AsyncMock, return_value=group_cfg),
        patch("analytiq_data.llm.llm.ad.common.get_prompt_content", new_callable=AsyncMock, return_value="Group task."),
    ):
        messages, peer_run, _ = await _build_prompt_context(
            analytiq_client,
            source,
            "r",
            TEST_ORG_ID,
            "SYS",
            "openai",
            "gpt-4o",
            "k",
        )
    assert peer_run is not None
    assert peer_run["match_values"] == {"batch_id": "batch-99"}
    peer_ids = set(peer_run["match_document_ids"])
    assert peer_ids == {str(oid_early), str(oid_late)}

    texts = _user_text_blocks(messages)
    group_header = texts[0]
    assert "group of related documents" in group_header

    markers = [t for t in texts if t.startswith("[Document #")]
    assert len(markers) == 3
    # Source document first, then peers in Mongo sort order (created_at, _id).
    assert '"slot": "source"' in markers[0]
    assert '"slot": "early"' in markers[1]
    assert '"slot": "late"' in markers[2]


@pytest.mark.asyncio
async def test_build_prompt_context_peer_missing_metadata_key_raises(test_db, mock_auth, setup_test_models):
    analytiq_client = ad.common.get_analytiq_client()
    doc = {"_id": ObjectId(), "metadata": {}, "user_file_name": "a.pdf"}
    group_cfg = {
        "peer_match_keys": ["batch_id"],
        "include": {"ocr_text": False, "pdf": False, "metadata_keys": []},
    }
    with (
        patch("analytiq_data.llm.llm.ad.common.get_prompt_group_config", new_callable=AsyncMock, return_value=group_cfg),
        patch("analytiq_data.llm.llm.ad.common.get_prompt_content", new_callable=AsyncMock, return_value="x"),
    ):
        with pytest.raises(Exception, match="missing metadata key"):
            await _build_prompt_context(
                analytiq_client, doc, "r", TEST_ORG_ID, "SYS", "openai", "gpt-4o", "k"
            )


def test_prompt_used_from_grouped_user_blocks_placeholders():
    """Sanity check: prompt_used replaces OCR/PDF payloads with stable placeholders."""
    system = "SYS"
    ordered = [{"_id": ObjectId()}, {"_id": ObjectId()}]
    d0, d1 = str(ordered[0]["_id"]), str(ordered[1]["_id"])
    user_blocks = [
        {"type": "text", "text": "HEADER"},
        {"type": "text", "text": f"[Document #1]\nmetadata:\n{{}}"},
        {"type": "text", "text": f"ocr_text:\nOCR-A"},
        {"type": "file", "file": {"file_id": "x"}},
        {"type": "text", "text": f"[Document #2]\nmetadata:\n{{}}"},
        {"type": "text", "text": f"ocr_text:\nOCR-B"},
        {"type": "text", "text": f"pdf:\nBASE64BLOB"},
    ]
    out = _prompt_used_from_grouped_user_blocks(system, user_blocks, ordered, True, True)
    assert out.startswith("SYS")
    assert f"ocr_text:\n<{d0}_ocr_text>" in out
    assert f"ocr_text:\n<{d1}_ocr_text>" in out
    assert f"pdf:\n<{d1}_pdf>" in out
    assert "OCR-A" not in out
    assert "BASE64BLOB" not in out


def test_prompt_used_from_grouped_user_blocks_missing_ocr_raises():
    """When include_ocr=True, OCR placeholder is required for each document."""
    system = "SYS"
    ordered = [{"_id": ObjectId()}, {"_id": ObjectId()}]
    d0, d1 = str(ordered[0]["_id"]), str(ordered[1]["_id"])

    # Missing OCR for doc #1 (Document #1 header followed by Document #2 header).
    user_blocks = [
        {"type": "text", "text": "HEADER"},
        {"type": "text", "text": f"[Document #1]\nmetadata:\n{{}}"},
        {"type": "text", "text": f"[Document #2]\nmetadata:\n{{}}"},
        {"type": "text", "text": f"ocr_text:\nOCR-B"},
    ]
    with pytest.raises(Exception, match=f"missing OCR.*{d0}"):
        _prompt_used_from_grouped_user_blocks(system, user_blocks, ordered, True, False)


def test_prompt_used_from_grouped_user_blocks_missing_pdf_raises():
    """When include_pdf=True, PDF placeholder is required for each document."""
    system = "SYS"
    ordered = [{"_id": ObjectId()}, {"_id": ObjectId()}]
    d0 = str(ordered[0]["_id"])

    # Missing PDF for doc #1.
    user_blocks = [
        {"type": "text", "text": "HEADER"},
        {"type": "text", "text": f"[Document #1]\nmetadata:\n{{}}"},
        {"type": "text", "text": f"[Document #2]\nmetadata:\n{{}}"},
        {"type": "text", "text": f"pdf:\nBASE64-2"},
    ]
    with pytest.raises(Exception, match=f"missing PDF.*{d0}"):
        _prompt_used_from_grouped_user_blocks(system, user_blocks, ordered, False, True)


def test_prompt_used_from_grouped_user_blocks_pdf_file_and_text_forms():
    """Supports both PDF representations in user_blocks."""
    system = "SYS"
    ordered = [{"_id": ObjectId()}, {"_id": ObjectId()}]
    d0, d1 = str(ordered[0]["_id"]), str(ordered[1]["_id"])

    user_blocks = [
        {"type": "text", "text": "HEADER"},
        {"type": "text", "text": f"[Document #1]\nmetadata:\n{{}}"},
        {"type": "file", "file": {"file_id": "openai-file-id-or-sim"}},
        {"type": "text", "text": f"[Document #2]\nmetadata:\n{{}}"},
        {"type": "text", "text": f"pdf:\nBASE64-BLOB"},
    ]
    out = _prompt_used_from_grouped_user_blocks(system, user_blocks, ordered, False, True)
    assert f"pdf:\n<{d0}_pdf>" in out
    assert f"pdf:\n<{d1}_pdf>" in out
    assert "BASE64-BLOB" not in out


def test_prompt_used_from_grouped_user_blocks_extra_text_is_preserved():
    """Order-robust dispatch should preserve unrelated text blocks verbatim."""
    system = "SYS"
    ordered = [{"_id": ObjectId()}, {"_id": ObjectId()}]
    d0, d1 = str(ordered[0]["_id"]), str(ordered[1]["_id"])

    user_blocks = [
        {"type": "text", "text": "HEADER"},
        {"type": "text", "text": f"[Document #1]\nmetadata:\n{{}}"},
        {"type": "text", "text": "SOME EXTRA LABEL"},
        {"type": "text", "text": f"ocr_text:\nOCR-A"},
        {"type": "text", "text": f"[Document #2]\nmetadata:\n{{}}"},
        {"type": "text", "text": f"ocr_text:\nOCR-B"},
    ]
    out = _prompt_used_from_grouped_user_blocks(system, user_blocks, ordered, True, False)
    assert "SOME EXTRA LABEL" in out
    assert f"ocr_text:\n<{d0}_ocr_text>" in out
    assert f"ocr_text:\n<{d1}_ocr_text>" in out
    assert "OCR-A" not in out
    assert "OCR-B" not in out
