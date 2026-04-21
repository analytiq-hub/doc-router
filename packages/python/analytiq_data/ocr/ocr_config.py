"""
Organization-level OCR configuration.

``mode`` selects exactly one engine: Textract, native Mistral OCR, LLM OCR, or PyMuPDF
embedded text. See :mod:`analytiq_data.ocr.ocr_runners`.
"""
from __future__ import annotations

import logging
import math
from typing import Any, Literal

from bson import ObjectId
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

logger = logging.getLogger(__name__)

TEXTRACT_FEATURES = frozenset({"LAYOUT", "TABLES", "FORMS", "SIGNATURES"})

OcrMode = Literal["textract", "mistral", "mistral_vertex", "llm", "pymupdf"]

# Legacy export (tests); single-mode config replaces multi-engine order.
OcrEngineId = Literal["textract"]
OCR_ENGINE_RUN_ORDER: tuple[OcrEngineId, ...] = ("textract",)


def textract_spu_cost(feature_types: list[str]) -> int:
    """
    Legacy Textract SPU cost by feature types (pre-unified billing).

    Kept for migrations/tests referencing old behavior.
    """
    fts = set(feature_types)
    if "FORMS" in fts:
        return 4
    if "TABLES" in fts:
        return 2
    return 1


def spu_ocr_for_page_count(n_pages: int) -> int:
    """
    SPUs to charge for a successful OCR run: 1 SPU per 25 pages (rounded up).

    Minimum 1 SPU when n_pages >= 1; 0 pages -> 0 SPUs.
    """
    if n_pages <= 0:
        return 0
    return max(1, math.ceil(n_pages / 25))


class OrgOcrTextractSettings(BaseModel):
    """AWS Textract: AnalyzeDocument feature types."""

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


class OrgOcrMistralSettings(BaseModel):
    """Optional native Mistral OCR flags (model is fixed in code: mistral-ocr-latest)."""

    model_config = ConfigDict(extra="ignore")


class OrgOcrMistralVertexSettings(BaseModel):
    """Mistral OCR via Vertex AI (region hardcoded to us-central1, model mistral-ocr-2505).
    Credentials come from the GCP cloud_config service account JSON."""

    model_config = ConfigDict(extra="ignore")


class OrgOcrPymupdfSettings(BaseModel):
    """Optional PyMuPDF OCR flags (extraction is local embedded text only)."""

    model_config = ConfigDict(extra="ignore")


class OrgOcrLlmSettings(BaseModel):
    """LLM OCR provider + model when ``mode == \"llm\"``."""

    model_config = ConfigDict(extra="ignore")

    provider: str | None = None
    model: str | None = None


class OrgOcrConfig(BaseModel):
    """Per-organization OCR settings."""

    model_config = ConfigDict(extra="ignore")

    mode: OcrMode = "textract"
    textract: OrgOcrTextractSettings = Field(default_factory=OrgOcrTextractSettings)
    mistral: OrgOcrMistralSettings = Field(default_factory=OrgOcrMistralSettings)
    mistral_vertex: OrgOcrMistralVertexSettings = Field(default_factory=OrgOcrMistralVertexSettings)
    pymupdf: OrgOcrPymupdfSettings = Field(default_factory=OrgOcrPymupdfSettings)
    llm: OrgOcrLlmSettings = Field(default_factory=OrgOcrLlmSettings)

    @model_validator(mode="after")
    def _llm_required_when_mode_llm(self) -> OrgOcrConfig:
        if self.mode == "llm":
            if not (self.llm.provider and str(self.llm.provider).strip()):
                raise ValueError('ocr_config: when mode is "llm", llm.provider is required')
            if not (self.llm.model and str(self.llm.model).strip()):
                raise ValueError('ocr_config: when mode is "llm", llm.model is required')
        return self


def max_reserved_spu_for_ocr_config(
    cfg: OrgOcrConfig,
    *,
    pdf_bytes: bytes | None = None,
) -> int:
    """
    Upper-bound SPUs to reserve before an OCR job (credit pre-check).

    Uses PDF page count when ``pdf_bytes`` is provided; otherwise a conservative default.

    ``pymupdf`` mode bills **0** SPU — no reservation.
    """
    if cfg.mode == "pymupdf":
        return 0
    if pdf_bytes:
        from analytiq_data.common.pdf_pages import pdf_page_count

        n = pdf_page_count(pdf_bytes)
        if n is not None and n > 0:
            return max(1, spu_ocr_for_page_count(n))
    # Unknown page count: reserve as if 100 pages (4 SPUs) to avoid blocking large jobs.
    return max(1, spu_ocr_for_page_count(100))


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
    if "mode" not in out:
        out["mode"] = "textract"
    if "mistral" not in out or not isinstance(out.get("mistral"), dict):
        out["mistral"] = {}
    if "mistral_vertex" not in out or not isinstance(out.get("mistral_vertex"), dict):
        out["mistral_vertex"] = {}
    if "llm" not in out or not isinstance(out.get("llm"), dict):
        out["llm"] = {"provider": None, "model": None}
    if "pymupdf" not in out or not isinstance(out.get("pymupdf"), dict):
        out["pymupdf"] = {}
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
        logger.warning(f"Invalid ocr_config document, using defaults: {e}")
        return OrgOcrConfig()


async def apply_ocr_config_update(
    stored: dict[str, Any] | None, incoming: dict[str, Any]
) -> dict[str, Any]:
    """
    Merge a partial OCR config update into stored settings, validate, and return a full
    document suitable for persisting on the organization.

    Mistral mode requires the Mistral LLM provider to be enabled with an API key in
    ``llm_providers`` (not a standalone env var).
    Mistral Vertex mode requires GCP credentials in cloud_config.
    """
    from analytiq_data.ocr.mistral_ocr_provider import mistral_ocr_enabled_from_llm_providers
    from analytiq_data.cloud.cloud_config import gcp_credentials_configured

    base = OrgOcrConfig().model_dump()
    merged_in = _normalize_legacy_ocr_dict(dict(incoming))
    merged_stored = _deep_merge_defaults(_normalize_legacy_ocr_dict(stored or {}), merged_in)
    full = _deep_merge_defaults(base, merged_stored)
    cfg = OrgOcrConfig.model_validate(full)
    if cfg.mode == "mistral" and not await mistral_ocr_enabled_from_llm_providers():
        raise ValueError(
            "Mistral OCR is not available: enable the Mistral LLM provider and at least one model "
            "in account LLM settings"
        )
    if cfg.mode == "mistral_vertex":
        import analytiq_data as ad
        db = ad.common.get_async_db()
        if not await gcp_credentials_configured(db):
            raise ValueError(
                "Mistral Vertex OCR is not available: configure GCP credentials in account settings"
            )
    return cfg.model_dump()


async def ocr_settings_catalog() -> dict[str, Any]:
    """OCR UI / API discovery."""
    from analytiq_data.ocr.mistral_ocr_provider import mistral_ocr_enabled_from_llm_providers
    from analytiq_data.cloud.cloud_config import gcp_credentials_configured
    import analytiq_data as ad

    db = ad.common.get_async_db()
    return {
        "textract_feature_types": sorted(TEXTRACT_FEATURES),
        "modes": ["textract", "mistral", "mistral_vertex", "llm", "pymupdf"],
        "mistral_enabled": await mistral_ocr_enabled_from_llm_providers(),
        "mistral_vertex_enabled": await gcp_credentials_configured(db),
    }


async def fetch_org_ocr_config(analytiq_client, org_id: str) -> OrgOcrConfig:
    """Load organization OCR config from MongoDB and merge with defaults."""
    import analytiq_data as ad

    db = ad.common.get_async_db()
    try:
        oid = ObjectId(org_id)
    except Exception:
        logger.warning(f"Invalid org_id for OCR config: {org_id}")
        return OrgOcrConfig()
    org = await db.organizations.find_one({"_id": oid})
    raw = (org or {}).get("ocr_config")
    return merge_org_ocr_config(raw if isinstance(raw, dict) else None)
