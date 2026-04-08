"""
Run OCR for a document PDF blob using organization OCR settings.

``OrgOcrConfig.mode`` selects Textract, native Mistral OCR, LLM OCR, or PyMuPDF.
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


def _llm_page_count(payload: dict[str, Any], pdf_bytes: bytes) -> int:
    pages = payload.get("pages")
    if isinstance(pages, list) and pages:
        return len(pages)
    from analytiq_data.common.pdf_pages import pdf_page_count

    n = pdf_page_count(pdf_bytes)
    return n if n is not None and n > 0 else 1


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
    For ``llm``, the return value is ``{ provider, model, pages: [{ index, markdown }] }`` JSON.
    For ``pymupdf``, the return value is ``{ ocr_engine: \"pymupdf\", pages: [...] }`` (0 SPU).
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
        from analytiq_data.ocr.llm_ocr import run_llm_ocr_pdf

        try:
            payload = await run_llm_ocr_pdf(
                analytiq_client,
                pdf_bytes,
                provider_name=cfg.llm.provider or "",
                model=cfg.llm.model or "",
            )
        except Exception as e:
            logger.error(
                "OCR engine llm failed for org_id=%s document_id=%s: %s",
                org_id,
                document_id,
                e,
            )
            raise
        n_pages = _llm_page_count(payload, pdf_bytes)
        spus = spu_ocr_for_page_count(n_pages)
        if spus > 0:
            await ad.payments.record_spu_usage(
                org_id=org_id,
                spus=spus,
                llm_provider="ocr",
                llm_model=cfg.llm.model or "llm-ocr",
                operation="ocr",
            )
        logger.info(
            "OCR llm finished org_id=%s document_id=%s pages=%s spus=%s",
            org_id,
            document_id,
            n_pages,
            spus,
        )
        return payload

    if cfg.mode == "pymupdf":
        from analytiq_data.ocr.pymupdf_ocr import extract_pymupdf_pdf

        try:
            payload = extract_pymupdf_pdf(pdf_bytes)
        except Exception as e:
            logger.error(
                "OCR engine pymupdf failed for org_id=%s document_id=%s: %s",
                org_id,
                document_id,
                e,
            )
            raise
        n_pages = _mistral_page_count(payload)
        logger.info(
            "OCR pymupdf finished org_id=%s document_id=%s pages=%s spus=0",
            org_id,
            document_id,
            n_pages,
        )
        return payload

    raise RuntimeError(f"Unknown OCR mode: {cfg.mode!r}")
