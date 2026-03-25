"""Tests for organization OCR configuration merge and validation."""
import pytest
from pydantic import ValidationError
from unittest.mock import patch

from analytiq_data.common.org_ocr_config import (
    OCR_ENGINE_RUN_ORDER,
    OrgOcrTextractSettings,
    apply_ocr_config_update,
    max_reserved_spu_for_ocr_config,
    merge_org_ocr_config,
    textract_spu_cost,
)
from analytiq_data.common.ocr_runners import run_document_ocr


def test_ocr_engine_run_order_starts_with_textract():
    assert OCR_ENGINE_RUN_ORDER[0] == "textract"


def test_merge_defaults_when_missing():
    cfg = merge_org_ocr_config(None)
    assert cfg.textract.feature_types == ["LAYOUT"]


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


def test_apply_rejects_empty_feature_types():
    with pytest.raises(ValidationError, match="At least one Textract feature type"):
        apply_ocr_config_update(
            None,
            {
                "textract": {"feature_types": []},
            },
        )


def test_textract_and_spu_costs():
    assert textract_spu_cost(["LAYOUT"]) == 1
    assert textract_spu_cost(["TABLES"]) == 2
    assert textract_spu_cost(["FORMS"]) == 4
    assert textract_spu_cost(["FORMS", "TABLES"]) == 4
    assert textract_spu_cost(["LAYOUT", "FORMS", "TABLES"]) == 4
    base = merge_org_ocr_config(None)
    assert max_reserved_spu_for_ocr_config(base) == 1
    tables = merge_org_ocr_config({"textract": {"feature_types": ["LAYOUT", "TABLES"]}})
    assert max_reserved_spu_for_ocr_config(tables) == 2
    forms = merge_org_ocr_config({"textract": {"feature_types": ["LAYOUT", "FORMS"]}})
    assert max_reserved_spu_for_ocr_config(forms) == 4


def test_apply_update_textract():
    out = apply_ocr_config_update(
        None,
        {
            "textract": {"feature_types": ["LAYOUT", "TABLES"]},
        },
    )
    assert out["textract"]["feature_types"] == ["LAYOUT", "TABLES"]
    assert "enabled" not in out["textract"]


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
        return {"DocumentMetadata": {}, "Blocks": []}

    with (
        patch("analytiq_data.common.ocr_runners.textract_mod.run_textract", side_effect=fake_textract),
        patch("analytiq_data.common.ocr_runners.ad.payments.check_spu_limits"),
        patch("analytiq_data.common.ocr_runners.ad.payments.record_spu_usage"),
    ):
        await run_document_ocr(
            None, b"%PDF-1.4", org_id="o", document_id="d", cfg=cfg
        )
