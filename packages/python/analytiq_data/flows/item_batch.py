from __future__ import annotations

"""Batch item processing for flow nodes (bounded in-flight work via ``batch_size``)."""

import asyncio
from collections.abc import Awaitable, Callable
from typing import TypeVar

from .node_settings import FLOW_NODE_BATCH_SIZE_DEFAULT

T = TypeVar("T")


async def map_flow_items_batch(
    count: int,
    fn: Callable[[int], Awaitable[T | None]],
    *,
    batch_size: int = FLOW_NODE_BATCH_SIZE_DEFAULT,
) -> list[T | None]:
    """Run ``fn(i)`` for ``i in range(count)``, at most ``batch_size`` in flight at once.

    Results preserve input order (index ``i`` → ``results[i]``). ``None`` means skip.
    """
    if count <= 0:
        return []

    limit = max(1, int(batch_size))
    sem = asyncio.Semaphore(limit)
    results: list[T | None] = [None] * count

    async def _run(index: int) -> None:
        async with sem:
            results[index] = await fn(index)

    await asyncio.gather(*(_run(i) for i in range(count)))
    return results
