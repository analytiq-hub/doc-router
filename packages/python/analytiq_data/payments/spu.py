import asyncio
import math
import analytiq_data as ad
import logging
from typing import Dict, Any, Callable

logger = logging.getLogger(__name__)

# Max SPUs we might charge for a single LLM call (cap in compute_spu_to_charge).
# Formula: ceil(200% * actual_cost / price_per_credit); this caps the result.
MAX_SPU_PER_LLM_CALL = 50

# Page-scaled SPU floor: one SPU unit per this many document pages (rounded up).
SPU_PAGES_PER_UNIT = 25

check_payment_limits = None
record_payment_usage = None
get_price_per_credit = None  # Hook: () -> float, set by app.routes.payments


def set_get_price_per_credit_hook(fn: Callable[[], float]) -> None:
    """Set the function to get price per SPU credit (from Stripe config).
    Note: fn is synchronous; if this ever becomes async, compute_spu_to_charge would need to change.
    """
    global get_price_per_credit
    get_price_per_credit = fn


def compute_spu_to_charge(actual_cost: float, min_spu: int = 1, cost_multiplier: float = 2.0) -> int:
    """
    Compute SPUs to charge such that we cover at least cost_multiplier (default 200%) of actual_cost.
    Returns max(min_spu, ceil(cost_multiplier * actual_cost / price_per_credit)), capped at MAX_SPU_PER_LLM_CALL.
    When price_per_credit is 0 or unavailable, returns min_spu.
    """
    if actual_cost is None or actual_cost <= 0:
        return min_spu
    price = get_price_per_credit() if get_price_per_credit else 0
    if not price or price <= 0:
        return min_spu
    spus_from_cost = math.ceil(cost_multiplier * actual_cost / price)
    return min(max(min_spu, spus_from_cost), MAX_SPU_PER_LLM_CALL)


def spu_page_floor(n_pages: int, *, when_empty: int) -> int:
    """
    Minimum SPUs from page count alone: ``ceil(n_pages / SPU_PAGES_PER_UNIT)``.

    ``when_empty`` is returned when ``n_pages <= 0`` (OCR uses 0; LLM uses 1).
    """

    if n_pages <= 0:
        return when_empty
    return max(1, math.ceil(n_pages / SPU_PAGES_PER_UNIT))


def spu_ocr_min_for_page_count(n_pages: int) -> int:
    """Page-based SPU floor for OCR jobs (0 when there are no pages)."""

    return spu_page_floor(n_pages, when_empty=0)


def spu_llm_min_for_page_count(n_pages: int) -> int:
    """
    Minimum SPU floor for a document or flow LLM run, scaled by page count.

    Used for ``check_spu_limits`` pre-check and as ``min_spu`` in ``compute_spu_to_charge``.
    """

    return spu_page_floor(n_pages, when_empty=1)


async def get_spu_cost(llm_model: str) -> int:
    """Conservative pre-check floor: 1 SPU per agent step regardless of model."""
    return 1

async def check_spu_limits(org_id: str, spus: int) -> bool:
    """Check if organization has hit usage limits and needs to upgrade"""

    # If a hook is set, use it to check payment limits
    if check_payment_limits:
        return await check_payment_limits(org_id, spus)

    # Otherwise, payments are not enabled
    return True

async def record_spu_usage(org_id: str, spus: int, 
                          llm_provider: str = None,
                          llm_model: str = None,
                          prompt_tokens: int = None, 
                          completion_tokens: int = None, 
                          total_tokens: int = None, 
                          actual_cost: float = None,
                          operation: str = "document_llm") -> bool:
    """Record SPU usage with LLM metrics"""

    logger.info(f"Recording {spus} spu usage for org_id: {org_id}, operation: {operation}, provider: {llm_provider}, model: {llm_model}")

    # If a hook is set, use it to record payment usage
    if record_payment_usage:
        await record_payment_usage(
            org_id,
            spus,
            llm_provider,
            llm_model,
            prompt_tokens,
            completion_tokens,
            total_tokens,
            actual_cost,
            operation,
        )

    # Otherwise, payments are not enabled
    return True

def set_check_payment_limits_hook(check_payment_limits_func: Callable) -> None:
    """Set the function to check payment limits"""
    global check_payment_limits
    check_payment_limits = check_payment_limits_func

def set_record_payment_usage_hook(record_payment_usage_func: Callable) -> None:
    """Set the function to record payment usage"""
    global record_payment_usage
    record_payment_usage = record_payment_usage_func
