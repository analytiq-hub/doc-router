"""SPU billing helpers for the flow agent loop."""

from __future__ import annotations

import logging
from typing import Any

import litellm

import analytiq_data as ad

logger = logging.getLogger(__name__)


async def check_spu_limits(organization_id: str, model: str) -> None:
    spu_check = await ad.payments.get_spu_cost(model)
    await ad.payments.check_spu_limits(organization_id, spu_check)


async def record_spu(response: Any, organization_id: str, model: str) -> None:
    usage = getattr(response, "usage", None)
    await record_spu_from_usage(usage, organization_id, model, completion_response=response)


async def record_spu_from_usage(
    usage: Any,
    organization_id: str,
    model: str,
    *,
    completion_response: Any | None = None,
) -> None:
    try:
        try:
            actual_cost = (
                litellm.completion_cost(completion_response=completion_response)
                if completion_response is not None and usage
                else 0.0
            )
        except Exception as e:
            logger.warning(f"Could not compute LLM cost for model {model}: {e}")
            actual_cost = 0.0

        prompt_tokens = getattr(usage, "prompt_tokens", None) or 0
        completion_tokens = getattr(usage, "completion_tokens", None) or 0
        total_tokens = getattr(usage, "total_tokens", None) or (prompt_tokens + completion_tokens)
        provider = (model.split("/", 1)[0] if "/" in model else model) or "unknown"

        spus_to_charge = ad.payments.compute_spu_to_charge(actual_cost)
        await ad.payments.record_spu_usage(
            organization_id,
            spus_to_charge,
            llm_provider=provider,
            llm_model=model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            actual_cost=actual_cost,
            operation="flow_agent_llm",
        )
    except Exception as e:
        logger.error(f"Error recording flow agent SPU (model={model}): {e}")
