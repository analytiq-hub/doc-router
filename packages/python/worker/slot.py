"""Lifecycle flags for hot-resizable queue workers."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class WorkerSlot:
    """Pool-managed state for one queue worker task."""

    draining: bool = False
    busy: bool = False

    def should_exit_before_poll(self) -> bool:
        return self.draining

    def should_exit_when_idle(self) -> bool:
        return self.draining
