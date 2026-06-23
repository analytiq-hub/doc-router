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
    should_stop: Callable[[], Awaitable[bool]] | None = None,
) -> list[T | None]:
    """Run ``fn(i)`` for ``i in range(count)``, at most ``batch_size`` in flight at once.

    Results preserve input order (index ``i`` → ``results[i]``). ``None`` means skip.

    When ``should_stop`` returns true after an item finishes, no new items are started;
    in-flight work is allowed to complete first.
    """
    if count <= 0:
        return []

    limit = max(1, int(batch_size))
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
