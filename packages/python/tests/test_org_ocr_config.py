"""Tests for organization OCR configuration merge and validation."""
import pytest
from pydantic import ValidationError
from unittest.mock import AsyncMock, patch

from analytiq_data.ocr.mistral_ocr_provider import provider_and_llm_enabled
from analytiq_data.ocr.ocr_config import (
    OCR_ENGINE_RUN_ORDER,
    OrgOcrTextractSettings,
    apply_ocr_config_update,
    max_reserved_spu_for_ocr_config,
    merge_org_ocr_config,
    ocr_settings_catalog,
    spu_ocr_for_page_count,
    textract_spu_cost,
)
from analytiq_data.ocr.ocr_runners import run_document_ocr
from analytiq_data.ocr.llm_ocr import _parse_llm_ocr_response


def test_provider_and_llm_enabled_requires_both():
    assert provider_and_llm_enabled(None) is False
    assert provider_and_llm_enabled({}) is False
    assert provider_and_llm_enabled({"enabled": True, "litellm_models_enabled": []}) is False
    assert provider_and_llm_enabled({"enabled": False, "litellm_models_enabled": ["m"]}) is False
    assert provider_and_llm_enabled({"enabled": True, "litellm_models_enabled": ["mistral/mistral-tiny"]}) is True


def test_ocr_engine_run_order_starts_with_textract():
    assert OCR_ENGINE_RUN_ORDER[0] == "textract"


def test_merge_defaults_when_missing():
    cfg = merge_org_ocr_config(None)
    assert cfg.textract.feature_types == ["LAYOUT"]
    assert cfg.mode == "textract"


def test_merge_legacy_drops_deprecated_gemini_vertex():
    """Stored Gemini/Vertex-only config falls back to defaults (Textract feature types)."""
    cfg = merge_org_ocr_config(
        {
            "primary_provider": "gemini",
            "gemini": {"enabled": True, "model": "gemini/gemini-2.5-flash"},
            "textract": {"enabled": False},
        }
    )
    assert cfg.textract.feature_types == ["LAYOUT"]
    assert cfg.mode == "textract"


def test_merge_strips_legacy_textract_enabled_key():
    cfg = merge_org_ocr_config(
        {"textract": {"enabled": False, "feature_types": ["TABLES", "LAYOUT"]}}
    )
    assert cfg.textract.feature_types == ["TABLES", "LAYOUT"]


def test_invalid_feature_rejected():
    with pytest.raises(ValueError, match="Invalid Textract feature"):
        OrgOcrTextractSettings(feature_types=["LAYOUT", "NOT_A_FEATURE"])


def test_textract_requires_at_least_one_feature():
    with pytest.raises(ValidationError, match="At least one Textract feature type"):
        OrgOcrTextractSettings(feature_types=[])


@pytest.mark.asyncio
async def test_apply_rejects_empty_feature_types():
    with pytest.raises(ValidationError, match="At least one Textract feature type"):
        await apply_ocr_config_update(
            None,
            {
                "textract": {"feature_types": []},
            },
        )


def test_textract_and_spu_costs_legacy():
    assert textract_spu_cost(["LAYOUT"]) == 1
    assert textract_spu_cost(["TABLES"]) == 2
    assert textract_spu_cost(["FORMS"]) == 4


def test_spu_ocr_for_page_count():
    assert spu_ocr_for_page_count(0) == 0
    assert spu_ocr_for_page_count(1) == 1
    assert spu_ocr_for_page_count(25) == 1
    assert spu_ocr_for_page_count(26) == 2
    assert spu_ocr_for_page_count(50) == 2


def test_max_reserved_without_pdf_uses_fallback():
    base = merge_org_ocr_config(None)
    assert max_reserved_spu_for_ocr_config(base) == spu_ocr_for_page_count(100)


def test_max_reserved_with_pdf_bytes():
    base = merge_org_ocr_config(None)
    # Minimal valid PDF header (one page count may fail — then fallback inside pdf_page_count)
    tiny = b"%PDF-1.4\n1 0 obj<<>>endobj trailer<<>>\n%%EOF"
    r = max_reserved_spu_for_ocr_config(base, pdf_bytes=tiny)
    assert r >= 1


@pytest.mark.asyncio
async def test_ocr_settings_catalog_includes_mistral_flag(monkeypatch):
    async def mistral_on():
        return True

    monkeypatch.setattr(
        "analytiq_data.ocr.mistral_ocr_provider.mistral_ocr_enabled_from_llm_providers",
        mistral_on,
    )
    cat = await ocr_settings_catalog()
    assert cat["modes"] == ["textract", "mistral", "llm"]
    assert cat["mistral_enabled"] is True


@pytest.mark.asyncio
async def test_ocr_settings_catalog_mistral_disabled(monkeypatch):
    async def mistral_off():
        return False

    monkeypatch.setattr(
        "analytiq_data.ocr.mistral_ocr_provider.mistral_ocr_enabled_from_llm_providers",
        mistral_off,
    )
    cat = await ocr_settings_catalog()
    assert cat["mistral_enabled"] is False


@pytest.mark.asyncio
async def test_apply_rejects_mistral_when_mistral_llm_not_configured(monkeypatch):
    async def mistral_off():
        return False

    monkeypatch.setattr(
        "analytiq_data.ocr.mistral_ocr_provider.mistral_ocr_enabled_from_llm_providers",
        mistral_off,
    )
    with pytest.raises(ValueError, match="Mistral OCR is not available"):
        await apply_ocr_config_update(None, {"mode": "mistral"})


@pytest.mark.asyncio
async def test_apply_allows_mistral_when_mistral_llm_configured(monkeypatch):
    async def mistral_on():
        return True

    monkeypatch.setattr(
        "analytiq_data.ocr.mistral_ocr_provider.mistral_ocr_enabled_from_llm_providers",
        mistral_on,
    )
    out = await apply_ocr_config_update(None, {"mode": "mistral"})
    assert out["mode"] == "mistral"


@pytest.mark.asyncio
async def test_apply_update_textract():
    out = await apply_ocr_config_update(
        None,
        {
            "textract": {"feature_types": ["LAYOUT", "TABLES"]},
        },
    )
    assert out["textract"]["feature_types"] == ["LAYOUT", "TABLES"]
    assert "enabled" not in out["textract"]


@pytest.mark.asyncio
async def test_mode_llm_requires_provider_model():
    with pytest.raises(ValidationError):
        await apply_ocr_config_update(None, {"mode": "llm", "llm": {}})


def test_mode_llm_valid():
    cfg = merge_org_ocr_config(
        {
            "mode": "llm",
            "llm": {"provider": "openai", "model": "gpt-4o"},
        }
    )
    assert cfg.mode == "llm"
    assert cfg.llm.provider == "openai"
    assert cfg.llm.model == "gpt-4o"


@pytest.mark.asyncio
async def test_gemini_only_stored_config_resets_to_defaults_then_textract_runs():
    """Legacy gemini-only org config merges to Textract defaults; OCR invokes Textract."""
    cfg = merge_org_ocr_config(
        {
            "textract": {"enabled": False},
            "gemini": {"enabled": True, "model": "gemini/gemini-2.5-flash"},
        }
    )
    assert cfg.textract.feature_types == ["LAYOUT"]

    async def fake_textract(*_a, **_k):
        return {
            "DocumentMetadata": {"Pages": 1},
            "Blocks": [],
        }

    with (
        patch("analytiq_data.ocr.ocr_runners.textract_mod.run_textract", side_effect=fake_textract),
        patch("analytiq_data.ocr.ocr_runners.ad.payments.check_spu_limits"),
        patch("analytiq_data.ocr.ocr_runners.ad.payments.record_spu_usage"),
    ):
        await run_document_ocr(
            None, b"%PDF-1.4", org_id="o", document_id="d", cfg=cfg
        )


def test_parse_llm_ocr_response_plain_json():
    raw = '{"pages":[{"index":0,"markdown":"hello"}]}'
    assert _parse_llm_ocr_response(raw) == [{"index": 0, "markdown": "hello"}]


def test_parse_llm_ocr_response_json_fence():
    raw = '```json\n{"pages":[{"index":0,"markdown":"x"}]}\n```'
    assert _parse_llm_ocr_response(raw) == [{"index": 0, "markdown": "x"}]


def test_parse_llm_ocr_response_invalid_json_falls_back():
    raw = "just markdown text"
    assert _parse_llm_ocr_response(raw) == [{"index": 0, "markdown": "just markdown text"}]


@pytest.mark.asyncio
async def test_run_document_ocr_llm_mode():
    cfg = merge_org_ocr_config(
        {"mode": "llm", "llm": {"provider": "openai", "model": "gpt-4o"}}
    )
    payload = {
        "provider": "openai",
        "model": "gpt-4o",
        "pages": [{"index": 0, "markdown": "a"}, {"index": 1, "markdown": "b"}],
    }
    with (
        patch(
            "analytiq_data.ocr.llm_ocr.run_llm_ocr_pdf",
            new=AsyncMock(return_value=payload),
        ),
        patch("analytiq_data.ocr.ocr_runners.ad.payments.check_spu_limits"),
        patch("analytiq_data.ocr.ocr_runners.ad.payments.record_spu_usage") as rec,
    ):
        out = await run_document_ocr(
            object(), b"%PDF-1.4", org_id="o", document_id="d", cfg=cfg
        )
    assert out == payload
    rec.assert_called_once()
    assert rec.call_args.kwargs["spus"] == 1
