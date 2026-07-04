from __future__ import annotations

"""Batch item processing for flow nodes (bounded in-flight work via ``batch_size``)."""

import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import TypeVar

from .node_settings import FLOW_NODE_BATCH_SIZE_DEFAULT

logger = logging.getLogger(__name__)

T = TypeVar("T")


class FlowBatchItemErrors(Exception):
    """One or more batch items failed (see ``errors`` and ``results``)."""

    def __init__(
        self,
        errors: list[tuple[int, BaseException]],
        results: list[object | None],
    ) -> None:
        self.errors = errors
        self.results = results
        first = errors[0][1] if errors else None
        super().__init__(str(first) if first else "batch item errors")

    @property
    def first(self) -> BaseException:
        if not self.errors:
            raise RuntimeError("FlowBatchItemErrors has no errors")
        return self.errors[0][1]


async def map_flow_items_batch(
    count: int,
    fn: Callable[[int], Awaitable[T | None]],
    *,
    batch_size: int = FLOW_NODE_BATCH_SIZE_DEFAULT,
    should_stop: Callable[[], Awaitable[bool]] | None = None,
    on_items_checkpoint: Callable[[int, int, list[T | None]], Awaitable[None]] | None = None,
    on_fatal_item_error: Callable[[int, int, list[T | None], BaseException], Awaitable[None]] | None = None,
    continue_on_item_error: bool = False,
    execution_id: str | None = None,
    node_id: str | None = None,
    node_type: str | None = None,
) -> list[T | None]:
    """Run ``fn(i)`` for ``i in range(count)``, at most ``batch_size`` in flight at once.

    Results preserve input order (index ``i`` → ``results[i]``). ``None`` means skip.

    When ``should_stop`` returns true after an item finishes, no new items are started;
    in-flight work is allowed to complete first.

    When ``on_items_checkpoint`` is set, it is invoked after every ``batch_size`` completions
    and when all items finish. On cooperative stop, a final checkpoint runs if the last
    completion count is not already on a wave boundary.

    When ``continue_on_item_error`` is true, per-item exceptions are recorded and processing
    continues; ``FlowBatchItemErrors`` is raised after all in-flight work finishes if any
    item failed.

    When ``continue_on_item_error`` is false, the first item error stops launching new work,
    waits for in-flight items, invokes ``on_fatal_item_error`` with completed results, then
    re-raises the first error.
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
    finished_count = 0
    item_errors: list[tuple[int, BaseException]] = []
    fatal_error: BaseException | None = None
    lock = asyncio.Lock()

    async def maybe_checkpoint(completed: int) -> None:
        if on_items_checkpoint is None:
            return
        if completed <= 0:
            return
        if completed % limit != 0 and completed != count:
            return
        await on_items_checkpoint(completed, count, results)

    async def worker() -> None:
        nonlocal next_index, stop_launching, finished_count, fatal_error
        while True:
            if should_stop is not None and await should_stop():
                async with lock:
                    stop_launching = True
                return
            async with lock:
                if fatal_error is not None:
                    return
                if stop_launching or next_index >= count:
                    return
                idx = next_index
                next_index += 1
            try:
                results[idx] = await fn(idx)
            except Exception as e:
                if continue_on_item_error:
                    async with lock:
                        item_errors.append((idx, e))
                    results[idx] = None
                else:
                    async with lock:
                        if fatal_error is None:
                            fatal_error = e
                            stop_launching = True
                    results[idx] = None
                    async with lock:
                        finished_count += 1
                        completed = finished_count
                    if on_fatal_item_error is not None:
                        await on_fatal_item_error(completed, count, results, e)
                    continue
            async with lock:
                finished_count += 1
                completed = finished_count
            await maybe_checkpoint(completed)
            if should_stop is not None and await should_stop():
                async with lock:
                    stop_launching = True
                return

    workers = [asyncio.create_task(worker()) for _ in range(min(limit, count))]
    await asyncio.gather(*workers)

    if (
        on_items_checkpoint is not None
        and stop_launching
        and not fatal_error
        and finished_count > 0
        and finished_count < count
        and finished_count % limit != 0
    ):
        await on_items_checkpoint(finished_count, count, results)

    if fatal_error is not None:
        raise fatal_error

    if item_errors:
        raise FlowBatchItemErrors(item_errors, results)

    return results
