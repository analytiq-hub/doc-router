"""
Run OCR for a document PDF blob using organization OCR settings.

Enabled backends are started **in parallel**; we await all tasks (success, failure, or stub).
The payload persisted downstream is chosen in preference order: Textract → Gemini → Vertex.

Only **AWS Textract** is implemented today; Gemini / Vertex log a warning and complete with
no result until wired in.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any

import analytiq_data as ad

from analytiq_data.aws import textract as textract_mod
from analytiq_data.common.org_ocr_config import (
    GEMINI_OCR_SPU_PER_RUN,
    OCR_ENGINE_RUN_ORDER,
    OrgOcrConfig,
    VERTEX_OCR_SPU_PER_RUN,
    max_reserved_spu_for_ocr_config,
    textract_spu_cost,
)

logger = logging.getLogger(__name__)

# When multiple engines return a Textract-shaped dict, which to store on the document.
_OCR_PERSIST_PREFERENCE: tuple[str, ...] = ("textract", "gemini", "vertex_ai")


async def run_document_ocr(
    analytiq_client,
    pdf_bytes: bytes,
    *,
    org_id: str,
    document_id: str,
    cfg: OrgOcrConfig,
) -> dict[str, Any]:
    """
    Run all enabled OCR backends concurrently; wait for every task to complete.

    Returns one Textract-shaped dict for :func:`analytiq_data.common.ocr.save_ocr_text_from_list`,
    using the first successful result in :data:`_OCR_PERSIST_PREFERENCE` order.
    """
    tasks: list[asyncio.Task] = []
    names: list[str] = []

    for engine in OCR_ENGINE_RUN_ORDER:
        if engine == "textract" and cfg.textract.enabled:

            async def _textract() -> dict[str, Any]:
                return await textract_mod.run_textract(
                    analytiq_client,
                    pdf_bytes,
                    feature_types=list(cfg.textract.feature_types),
                    document_id=document_id,
                    org_id=org_id,
                )

            tasks.append(asyncio.create_task(_textract()))
            names.append("textract")

        elif engine == "gemini" and cfg.gemini.enabled:

            async def _gemini_stub() -> None:
                logger.warning(
                    "Gemini OCR is enabled for org_id=%s document_id=%s but not implemented",
                    org_id,
                    document_id,
                )
                return None

            tasks.append(asyncio.create_task(_gemini_stub()))
            names.append("gemini")

        elif engine == "vertex_ai" and cfg.vertex_ai.enabled:

            async def _vertex_stub() -> None:
                logger.warning(
                    "Vertex AI OCR is enabled for org_id=%s document_id=%s but not implemented",
                    org_id,
                    document_id,
                )
                return None

            tasks.append(asyncio.create_task(_vertex_stub()))
            names.append("vertex_ai")

    if not tasks:
        raise RuntimeError(
            "No OCR engine is enabled. Enable Textract, Gemini, and/or Vertex in organization settings."
        )

    reserved = max_reserved_spu_for_ocr_config(cfg)
    if reserved > 0:
        await ad.payments.check_spu_limits(org_id, reserved)

    results = await asyncio.gather(*tasks, return_exceptions=True)

    by_engine: dict[str, Any] = {}
    for name, res in zip(names, results):
        if isinstance(res, Exception):
            logger.error("OCR engine %s failed for org_id=%s document_id=%s: %s", name, org_id, document_id, res)
            by_engine[name] = None
        elif res is None:
            by_engine[name] = None
        else:
            by_engine[name] = res
            logger.info(
                "OCR engine %s finished successfully for org_id=%s document_id=%s",
                name,
                org_id,
                document_id,
            )

    total_spus = 0
    tr = by_engine.get("textract")
    if cfg.textract.enabled and isinstance(tr, dict) and tr:
        total_spus += textract_spu_cost(cfg.textract.feature_types)
    gm = by_engine.get("gemini")
    if cfg.gemini.enabled and isinstance(gm, dict) and gm:
        total_spus += GEMINI_OCR_SPU_PER_RUN
    vx = by_engine.get("vertex_ai")
    if cfg.vertex_ai.enabled and isinstance(vx, dict) and vx:
        total_spus += VERTEX_OCR_SPU_PER_RUN

    chosen: dict[str, Any] | None = None
    for key in _OCR_PERSIST_PREFERENCE:
        payload = by_engine.get(key)
        if isinstance(payload, dict) and payload:
            chosen = payload
            break

    if not chosen:
        raise RuntimeError(
            "No OCR engine produced usable output. Check logs; enable Textract or wait until other providers are implemented."
        )

    if total_spus > 0:
        await ad.payments.record_spu_usage(
            org_id=org_id,
            spus=total_spus,
            llm_provider="ocr",
            llm_model="ocr",
            operation="ocr",
        )

    return chosen
