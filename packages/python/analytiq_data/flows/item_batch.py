from __future__ import annotations

"""Batch item processing for flow nodes (bounded in-flight work via ``batch_size``)."""

import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import TypeVar

from .node_settings import FLOW_NODE_BATCH_SIZE_DEFAULT

logger = logging.getLogger(__name__)

T = TypeVar("T")


async def map_flow_items_batch(
    count: int,
    fn: Callable[[int], Awaitable[T | None]],
    *,
    batch_size: int = FLOW_NODE_BATCH_SIZE_DEFAULT,
    should_stop: Callable[[], Awaitable[bool]] | None = None,
    execution_id: str | None = None,
    node_id: str | None = None,
    node_type: str | None = None,
) -> list[T | None]:
    """Run ``fn(i)`` for ``i in range(count)``, at most ``batch_size`` in flight at once.

    Results preserve input order (index ``i`` → ``results[i]``). ``None`` means skip.

    When ``should_stop`` returns true after an item finishes, no new items are started;
    in-flight work is allowed to complete first.
    """
    if count <= 0:
        return []

    limit = max(1, int(batch_size))
    if limit > 1 and count > 1:
        context_bits: list[str] = []
        if execution_id:
            context_bits.append(f"execution_id={execution_id}")
        if node_type:
            context_bits.append(f"node_type={node_type}")
        if node_id:
            context_bits.append(f"node_id={node_id}")
        context_suffix = f" ({', '.join(context_bits)})" if context_bits else ""
        logger.info(
            f"Processing {count} items in parallel with batch_size={limit}{context_suffix}"
        )
    results: list[T | None] = [None] * count
    next_index = 0
    stop_launching = False
    lock = asyncio.Lock()

    async def worker() -> None:
        nonlocal next_index, stop_launching
        while True:
            if should_stop is not None and await should_stop():
                async with lock:
                    stop_launching = True
                return
            async with lock:
                if stop_launching or next_index >= count:
                    return
                idx = next_index
                next_index += 1
            results[idx] = await fn(idx)
            if should_stop is not None and await should_stop():
                async with lock:
                    stop_launching = True
                return

    workers = [asyncio.create_task(worker()) for _ in range(min(limit, count))]
    await asyncio.gather(*workers)
    return results
