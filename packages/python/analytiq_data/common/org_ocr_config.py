"""
Organization-level OCR configuration (Textract, Gemini, Vertex AI).

Multiple engines may be enabled; the worker runs them **in parallel** and waits for all to
finish, then picks one Textract-shaped payload to persist (preference: Textract → Gemini →
Vertex). See :mod:`analytiq_data.common.ocr_runners`.
"""
from __future__ import annotations

import logging
from typing import Any, Literal

from bson import ObjectId
from pydantic import BaseModel, Field, field_validator, model_validator

logger = logging.getLogger(__name__)

TEXTRACT_FEATURES = frozenset({"LAYOUT", "TABLES", "FORMS", "SIGNATURES"})
OcrEngineId = Literal["textract", "gemini", "vertex_ai"]

# Order used when running multiple enabled OCR backends.
OCR_ENGINE_RUN_ORDER: tuple[OcrEngineId, ...] = ("textract", "gemini", "vertex_ai")


def textract_spu_cost(feature_types: list[str]) -> int:
    """
    SPUs to charge for a successful Textract AnalyzeDocument run.

    2 SPUs when TABLES or FORMS is requested (higher Textract work); otherwise 1.
    """
    fts = set(feature_types)
    if "TABLES" in fts or "FORMS" in fts:
        return 2
    return 1


# Gemini / Vertex multimodal OCR: one successful run each bills 1 SPU.
GEMINI_OCR_SPU_PER_RUN = 1
VERTEX_OCR_SPU_PER_RUN = 1


class OrgOcrTextractSettings(BaseModel):
    """AWS Textract: AnalyzeDocument feature types (at least one when enabled)."""

    enabled: bool = True
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
    def _require_feature_when_enabled(self) -> OrgOcrTextractSettings:
        if self.enabled and not self.feature_types:
            raise ValueError(
                "When Textract is enabled, at least one feature type is required (e.g. LAYOUT)."
            )
        return self


class OrgOcrGeminiSettings(BaseModel):
    """Gemini multimodal OCR via LiteLLM (PDF in context)."""

    enabled: bool = False
    model: str = "gemini/gemini-2.5-flash"


class OrgOcrVertexSettings(BaseModel):
    """Vertex AI Gemini multimodal OCR via LiteLLM."""

    enabled: bool = False
    model: str = "vertex_ai/gemini-2.5-flash"


class OrgOcrConfig(BaseModel):
    """
    OCR settings: any subset of engines may be enabled; at least one must be on.

    Default: only Textract, with LAYOUT.
    """

    textract: OrgOcrTextractSettings = Field(default_factory=OrgOcrTextractSettings)
    gemini: OrgOcrGeminiSettings = Field(default_factory=OrgOcrGeminiSettings)
    vertex_ai: OrgOcrVertexSettings = Field(default_factory=OrgOcrVertexSettings)

    @model_validator(mode="after")
    def _at_least_one_engine(self) -> OrgOcrConfig:
        if not any(
            [
                self.textract.enabled,
                self.gemini.enabled,
                self.vertex_ai.enabled,
            ]
        ):
            raise ValueError("At least one OCR provider must be enabled.")
        return self


def max_reserved_spu_for_ocr_config(cfg: OrgOcrConfig) -> int:
    """Upper-bound SPUs this OCR job might consume (for credit pre-check)."""
    total = 0
    if cfg.textract.enabled:
        total += textract_spu_cost(cfg.textract.feature_types)
    if cfg.gemini.enabled:
        total += GEMINI_OCR_SPU_PER_RUN
    if cfg.vertex_ai.enabled:
        total += VERTEX_OCR_SPU_PER_RUN
    return total


def _normalize_legacy_ocr_dict(raw: dict[str, Any]) -> dict[str, Any]:
    """Drop deprecated ``primary_provider`` from stored org documents."""
    out = dict(raw)
    out.pop("primary_provider", None)
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
        cfg = OrgOcrConfig.model_validate(merged)
    except Exception as e:
        logger.warning("Invalid ocr_config document, using defaults: %s", e)
        return OrgOcrConfig()
    try:
        validate_gemini_vertex_models(cfg)
    except ValueError as e:
        logger.warning("Invalid ocr_config Gemini/Vertex models, using defaults: %s", e)
        return OrgOcrConfig()
    return cfg


def validate_gemini_vertex_models(cfg: OrgOcrConfig) -> None:
    """Ensure Gemini / Vertex model ids are among provider-available models when enabled."""
    import analytiq_data as ad

    providers = ad.llm.providers.get_llm_providers()
    gemini_avail = set(providers.get("gemini", {}).get("litellm_models_available", []))
    vertex_avail = set(providers.get("vertex_ai", {}).get("litellm_models_available", []))
    if cfg.gemini.enabled and cfg.gemini.model not in gemini_avail:
        raise ValueError(
            f"gemini.model {cfg.gemini.model!r} is not in available Gemini models: {sorted(gemini_avail)}"
        )
    if cfg.vertex_ai.enabled and cfg.vertex_ai.model not in vertex_avail:
        raise ValueError(
            f"vertex_ai.model {cfg.vertex_ai.model!r} is not in available Vertex models: {sorted(vertex_avail)}"
        )


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


def apply_ocr_config_update(
    stored: dict[str, Any] | None, incoming: dict[str, Any]
) -> dict[str, Any]:
    """
    Merge a partial OCR config update into stored settings, validate, and return a full
    document suitable for persisting on the organization.
    """
    base = OrgOcrConfig().model_dump()
    merged_in = _normalize_legacy_ocr_dict(dict(incoming))
    merged_stored = _deep_merge_defaults(stored or {}, merged_in)
    full = _deep_merge_defaults(base, merged_stored)
    cfg = OrgOcrConfig.model_validate(full)
    validate_gemini_vertex_models(cfg)
    return cfg.model_dump()


def ocr_settings_catalog() -> dict[str, Any]:
    """Models available for OCR UI / API discovery (static + from get_llm_providers)."""
    import analytiq_data as ad

    providers = ad.llm.providers.get_llm_providers()
    return {
        "gemini_models_available": list(providers.get("gemini", {}).get("litellm_models_available", [])),
        "vertex_models_available": list(
            providers.get("vertex_ai", {}).get("litellm_models_available", [])
        ),
        "textract_feature_types": sorted(TEXTRACT_FEATURES),
    }
