"""
Organization-level OCR configuration.

**AWS Textract is always used** for OCR (feature types are configurable). Additional
engines can be added later by extending :data:`OCR_ENGINE_RUN_ORDER`, this module’s
settings models, and :func:`analytiq_data.common.ocr_runners.run_document_ocr`.

See :mod:`analytiq_data.common.ocr_runners`.
"""
from __future__ import annotations

import logging
from typing import Any, Literal

from bson import ObjectId
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

logger = logging.getLogger(__name__)

TEXTRACT_FEATURES = frozenset({"LAYOUT", "TABLES", "FORMS", "SIGNATURES"})

# Registered backends; extend when implementing optional engines alongside Textract.
OcrEngineId = Literal["textract"]
OCR_ENGINE_RUN_ORDER: tuple[OcrEngineId, ...] = ("textract",)


def textract_spu_cost(feature_types: list[str]) -> int:
    """
    SPUs to charge for a successful Textract AnalyzeDocument run.

    4 SPUs when FORMS is requested (highest Textract cost, applies whether or not
    TABLES is also enabled); 2 SPUs when TABLES only is requested; otherwise 1.
    """
    fts = set(feature_types)
    if "FORMS" in fts:
        return 4
    if "TABLES" in fts:
        return 2
    return 1


class OrgOcrTextractSettings(BaseModel):
    """AWS Textract: always-on; only AnalyzeDocument feature types are configurable."""

    model_config = ConfigDict(extra="ignore")

    feature_types: list[str] = Field(default_factory=lambda: ["LAYOUT"])

    @field_validator("feature_types")
    @classmethod
    def _validate_features(cls, v: list[str]) -> list[str]:
        for ft in v:
            if ft not in TEXTRACT_FEATURES:
                raise ValueError(
                    f"Invalid Textract feature {ft!r}; allowed: {sorted(TEXTRACT_FEATURES)}"
                )
        seen: set[str] = set()
        out: list[str] = []
        for ft in v:
            if ft not in seen:
                seen.add(ft)
                out.append(ft)
        return out

    @model_validator(mode="after")
    def _require_at_least_one_feature(self) -> OrgOcrTextractSettings:
        if not self.feature_types:
            raise ValueError("At least one Textract feature type is required (e.g. LAYOUT).")
        return self


class OrgOcrConfig(BaseModel):
    """
    Per-organization OCR settings.

    Textract is always the OCR engine; ``textract.feature_types`` selects AnalyzeDocument
    features. Optional backends can be added under this model in the future.
    """

    textract: OrgOcrTextractSettings = Field(default_factory=OrgOcrTextractSettings)


def max_reserved_spu_for_ocr_config(cfg: OrgOcrConfig) -> int:
    """Upper-bound SPUs this OCR job might consume (for credit pre-check)."""
    return textract_spu_cost(cfg.textract.feature_types)


def _normalize_legacy_ocr_dict(raw: dict[str, Any]) -> dict[str, Any]:
    """Drop deprecated keys from stored org documents."""
    out = dict(raw)
    out.pop("primary_provider", None)
    out.pop("gemini", None)
    out.pop("vertex_ai", None)
    tx = out.get("textract")
    if isinstance(tx, dict) and "enabled" in tx:
        tx = dict(tx)
        tx.pop("enabled", None)
        out["textract"] = tx
    return out


def _deep_merge_defaults(defaults: dict[str, Any], overrides: dict[str, Any]) -> dict[str, Any]:
    out = dict(defaults)
    for k, v in overrides.items():
        if (
            k in out
            and isinstance(out[k], dict)
            and isinstance(v, dict)
            and not isinstance(v, list)
        ):
            out[k] = _deep_merge_defaults(out[k], v)
        else:
            out[k] = v
    return out


def merge_org_ocr_config(raw: dict[str, Any] | None) -> OrgOcrConfig:
    """Merge stored partial Mongo document with defaults."""
    base = OrgOcrConfig().model_dump()
    if not raw:
        return OrgOcrConfig.model_validate(base)
    raw = _normalize_legacy_ocr_dict(raw)
    merged = _deep_merge_defaults(base, raw)
    try:
        return OrgOcrConfig.model_validate(merged)
    except Exception as e:
        logger.warning("Invalid ocr_config document, using defaults: %s", e)
        return OrgOcrConfig()


def apply_ocr_config_update(
    stored: dict[str, Any] | None, incoming: dict[str, Any]
) -> dict[str, Any]:
    """
    Merge a partial OCR config update into stored settings, validate, and return a full
    document suitable for persisting on the organization.
    """
    base = OrgOcrConfig().model_dump()
    merged_in = _normalize_legacy_ocr_dict(dict(incoming))
    merged_stored = _deep_merge_defaults(_normalize_legacy_ocr_dict(stored or {}), merged_in)
    full = _deep_merge_defaults(base, merged_stored)
    cfg = OrgOcrConfig.model_validate(full)
    return cfg.model_dump()


def ocr_settings_catalog() -> dict[str, Any]:
    """Textract features for OCR UI / API discovery."""
    return {
        "textract_feature_types": sorted(TEXTRACT_FEATURES),
    }


async def fetch_org_ocr_config(analytiq_client, org_id: str) -> OrgOcrConfig:
    """Load organization OCR config from MongoDB and merge with defaults."""
    import analytiq_data as ad

    db = ad.common.get_async_db()
    try:
        oid = ObjectId(org_id)
    except Exception:
        logger.warning("Invalid org_id for OCR config: %s", org_id)
        return OrgOcrConfig()
    org = await db.organizations.find_one({"_id": oid})
    raw = (org or {}).get("ocr_config")
    return merge_org_ocr_config(raw if isinstance(raw, dict) else None)
