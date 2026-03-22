"""
Run OCR for a document PDF blob using organization OCR settings.

**AWS Textract** is always used (feature types from :class:`~analytiq_data.common.org_ocr_config.OrgOcrConfig`).
Additional backends should be wired alongside Textract using :data:`~analytiq_data.common.org_ocr_config.OCR_ENGINE_RUN_ORDER`.
"""
from __future__ import annotations

import logging
from typing import Any

import analytiq_data as ad

from analytiq_data.aws import textract as textract_mod
from analytiq_data.common.org_ocr_config import (
    OrgOcrConfig,
    max_reserved_spu_for_ocr_config,
    textract_spu_cost,
)

logger = logging.getLogger(__name__)


async def run_document_ocr(
    analytiq_client,
    pdf_bytes: bytes,
    *,
    org_id: str,
    document_id: str,
    cfg: OrgOcrConfig,
) -> dict[str, Any]:
    """
    Run OCR (Textract today; extend for optional engines per :data:`~analytiq_data.common.org_ocr_config.OCR_ENGINE_RUN_ORDER`).
    Returns a Textract-shaped dict for :func:`analytiq_data.common.ocr.save_ocr_text_from_json`.
    """
    reserved = max_reserved_spu_for_ocr_config(cfg)
    if reserved > 0:
        await ad.payments.check_spu_limits(org_id, reserved)

    try:
        tr = await textract_mod.run_textract(
            analytiq_client,
            pdf_bytes,
            feature_types=list(cfg.textract.feature_types),
            document_id=document_id,
            org_id=org_id,
        )
    except Exception as e:
        logger.error("OCR engine textract failed for org_id=%s document_id=%s: %s", org_id, document_id, e)
        raise

    logger.info(
        "OCR engine textract finished successfully for org_id=%s document_id=%s",
        org_id,
        document_id,
    )

    total_spus = 0
    if isinstance(tr, dict) and tr:
        total_spus += textract_spu_cost(cfg.textract.feature_types)

    if not isinstance(tr, dict) or not tr:
        raise RuntimeError(
            "Textract did not produce usable output. Check logs and AWS configuration."
        )

    if total_spus > 0:
        await ad.payments.record_spu_usage(
            org_id=org_id,
            spus=total_spus,
            llm_provider="ocr",
            llm_model="ocr",
            operation="ocr",
        )

    return tr
