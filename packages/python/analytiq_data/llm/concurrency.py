"""Per-model in-flight concurrency gates for litellm calls (per worker process)."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import AsyncIterator

from analytiq_data.system import settings as system_settings


@dataclass
class _ModelGate:
    in_flight: int = 0
    condition: asyncio.Condition = field(default_factory=asyncio.Condition)


_gates: dict[str, _ModelGate] = {}


def _get_model_gate(model: str) -> _ModelGate:
    gate = _gates.get(model)
    if gate is None:
        gate = _ModelGate()
        _gates[model] = gate
    return gate


def reset_llm_concurrency_gates() -> None:
    """Clear per-model gate state (tests)."""
    _gates.clear()


@asynccontextmanager
async def llm_concurrency(model: str) -> AsyncIterator[None]:
    """Acquire an in-flight slot for ``model``; no-op when limit <= 0."""
    limit = await system_settings.get_llm_max_concurrent_for_model(model)
    if limit <= 0:
        yield
        return

    model_gate = _get_model_gate(model)
    async with model_gate.condition:
        while model_gate.in_flight >= limit:
            await model_gate.condition.wait()
        model_gate.in_flight += 1

    try:
        yield
    finally:
        async with model_gate.condition:
            model_gate.in_flight -= 1
            model_gate.condition.notify_all()
