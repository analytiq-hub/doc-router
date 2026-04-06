"""
Run OCR for a document PDF blob using organization OCR settings.

``OrgOcrConfig.mode`` selects Textract, native Mistral OCR, or LLM OCR (future).
"""
from __future__ import annotations

import logging
from typing import Any

import analytiq_data as ad

from analytiq_data.aws import textract as textract_mod
from analytiq_data.ocr.ocr_config import (
    OrgOcrConfig,
    max_reserved_spu_for_ocr_config,
    spu_ocr_for_page_count,
)

logger = logging.getLogger(__name__)


def _textract_page_count(tr: dict[str, Any]) -> int:
    dm = tr.get("DocumentMetadata") or {}
    p = dm.get("Pages")
    if isinstance(p, int) and p > 0:
        return p
    blocks = tr.get("Blocks") or []
    page_blocks = [
        b for b in blocks if isinstance(b, dict) and b.get("BlockType") == "PAGE"
    ]
    if page_blocks:
        return len(page_blocks)
    return 1


def _mistral_page_count(payload: dict[str, Any]) -> int:
    pages = payload.get("pages")
    if isinstance(pages, list) and pages:
        return len(pages)
    return 1


async def run_document_ocr(
    analytiq_client,
    pdf_bytes: bytes,
    *,
    org_id: str,
    document_id: str,
    cfg: OrgOcrConfig,
) -> dict[str, Any]:
    """
    Run OCR and return a payload suitable for :func:`analytiq_data.ocr.ocr.save_ocr_json`.

    For ``textract``, the return value is Textract-shaped dict with ``Blocks``.
    For ``mistral``, the return value is Mistral ``OCRResponse`` JSON.
    """
    reserved = max_reserved_spu_for_ocr_config(cfg, pdf_bytes=pdf_bytes)
    if reserved > 0:
        await ad.payments.check_spu_limits(org_id, reserved)

    if cfg.mode == "textract":
        try:
            tr = await textract_mod.run_textract(
                analytiq_client,
                pdf_bytes,
                feature_types=list(cfg.textract.feature_types),
                document_id=document_id,
                org_id=org_id,
            )
        except Exception as e:
            logger.error(
                "OCR engine textract failed for org_id=%s document_id=%s: %s",
                org_id,
                document_id,
                e,
            )
            raise
        if not isinstance(tr, dict) or not tr:
            raise RuntimeError(
                "Textract did not produce usable output. Check logs and AWS configuration."
            )
        n_pages = _textract_page_count(tr)
        spus = spu_ocr_for_page_count(n_pages)
        if spus > 0:
            await ad.payments.record_spu_usage(
                org_id=org_id,
                spus=spus,
                llm_provider="ocr",
                llm_model="ocr",
                operation="ocr",
            )
        logger.info(
            "OCR textract finished org_id=%s document_id=%s pages=%s spus=%s",
            org_id,
            document_id,
            n_pages,
            spus,
        )
        return tr

    if cfg.mode == "mistral":
        from analytiq_data.ocr.mistral_ocr_provider import get_mistral_api_key_for_ocr
        from analytiq_data.ocr.mistral_ocr import mistral_ocr_pdf

        try:
            api_key = await get_mistral_api_key_for_ocr()
            payload = await mistral_ocr_pdf(pdf_bytes, api_key=api_key)
        except Exception as e:
            logger.error(
                "OCR engine mistral failed for org_id=%s document_id=%s: %s",
                org_id,
                document_id,
                e,
            )
            raise
        n_pages = _mistral_page_count(payload)
        spus = spu_ocr_for_page_count(n_pages)
        if spus > 0:
            await ad.payments.record_spu_usage(
                org_id=org_id,
                spus=spus,
                llm_provider="ocr",
                llm_model="mistral-ocr",
                operation="ocr",
            )
        logger.info(
            "OCR mistral finished org_id=%s document_id=%s pages=%s spus=%s",
            org_id,
            document_id,
            n_pages,
            spus,
        )
        return payload

    if cfg.mode == "llm":
        raise NotImplementedError(
            "LLM OCR is not implemented yet; set organizations.ocr_config.mode to "
            "'textract' or 'mistral'"
        )

    raise RuntimeError(f"Unknown OCR mode: {cfg.mode!r}")
