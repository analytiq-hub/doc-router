"""Tests for organization OCR configuration merge and validation."""
import pytest
from unittest.mock import patch

from analytiq_data.common.org_ocr_config import (
    GEMINI_OCR_SPU_PER_RUN,
    VERTEX_OCR_SPU_PER_RUN,
    OrgOcrTextractSettings,
    apply_ocr_config_update,
    max_reserved_spu_for_ocr_config,
    merge_org_ocr_config,
    textract_spu_cost,
)
from analytiq_data.common.ocr_runners import run_document_ocr


def test_merge_defaults_when_missing():
    cfg = merge_org_ocr_config(None)
    assert cfg.textract.enabled is True
    assert cfg.textract.feature_types == ["LAYOUT"]
    assert cfg.gemini.enabled is False
    assert cfg.vertex_ai.enabled is False


def test_merge_legacy_drops_primary_provider():
    cfg = merge_org_ocr_config(
        {
            "primary_provider": "gemini",
            "gemini": {"enabled": True, "model": "gemini/gemini-2.5-flash"},
            "textract": {"enabled": False},
        }
    )
    assert cfg.gemini.enabled is True
    assert cfg.textract.enabled is False


def test_invalid_feature_rejected():
    with pytest.raises(ValueError, match="Invalid Textract feature"):
        OrgOcrTextractSettings(feature_types=["LAYOUT", "NOT_A_FEATURE"])


def test_textract_enabled_requires_at_least_one_feature():
    with pytest.raises(ValueError, match="at least one feature"):
        OrgOcrTextractSettings(enabled=True, feature_types=[])


def test_at_least_one_provider_required():
    with pytest.raises(ValueError, match="At least one OCR provider"):
        apply_ocr_config_update(
            None,
            {
                "textract": {"enabled": False},
                "gemini": {"enabled": False},
                "vertex_ai": {"enabled": False},
            },
        )


def test_textract_and_multimodal_spu_costs():
    assert textract_spu_cost(["LAYOUT"]) == 1
    assert textract_spu_cost(["TABLES"]) == 2
    assert textract_spu_cost(["FORMS"]) == 2
    assert GEMINI_OCR_SPU_PER_RUN == 1
    assert VERTEX_OCR_SPU_PER_RUN == 1
    base = merge_org_ocr_config(None)
    assert max_reserved_spu_for_ocr_config(base) == 1
    tables = merge_org_ocr_config({"textract": {"feature_types": ["LAYOUT", "TABLES"]}})
    assert max_reserved_spu_for_ocr_config(tables) == 2
    multi = merge_org_ocr_config(
        {
            "textract": {"feature_types": ["LAYOUT"]},
            "gemini": {"enabled": True, "model": "gemini/gemini-2.5-flash"},
            "vertex_ai": {"enabled": True, "model": "vertex_ai/gemini-2.5-flash"},
        }
    )
    assert max_reserved_spu_for_ocr_config(multi) == 1 + 1 + 1


def test_apply_update_multiple_engines():
    out = apply_ocr_config_update(
        None,
        {
            "textract": {"enabled": True, "feature_types": ["LAYOUT", "TABLES"]},
            "gemini": {"enabled": True, "model": "gemini/gemini-2.5-flash"},
        },
    )
    assert out["textract"]["feature_types"] == ["LAYOUT", "TABLES"]
    assert out["gemini"]["enabled"] is True


@pytest.mark.asyncio
async def test_only_non_textract_enabled_fails():
    cfg = merge_org_ocr_config(
        {
            "textract": {"enabled": False},
            "gemini": {"enabled": True, "model": "gemini/gemini-2.5-flash"},
        }
    )
    with (
        patch("analytiq_data.common.ocr_runners.ad.payments.check_spu_limits"),
        pytest.raises(RuntimeError, match="No OCR engine produced"),
    ):
        await run_document_ocr(
            None, b"%PDF-1.4", org_id="o", document_id="d", cfg=cfg
        )
