from __future__ import annotations

"""Context passed to poll hooks and schedule tick handlers."""

from dataclasses import dataclass, field
from typing import Any, Literal

PollMode = Literal["manual", "schedule"]


@dataclass
class PollContext:
    """
    Per-tick context for trigger poll/schedule hooks.

    ``static_data`` is loaded from ``flow_static_data`` and persisted when ``data_changed`` is set.
    """

    organization_id: str
    flow_id: str
    flow_revid: str
    node_id: str
    mode: PollMode
    analytiq_client: Any
    tick_meta: dict[str, Any] = field(default_factory=dict)
    static_data: dict[str, Any] = field(default_factory=dict)
    data_changed: bool = False

    def get_static(self, key: str, default: Any = None) -> Any:
        return self.static_data.get(key, default)

    def set_static(self, key: str, value: Any) -> None:
        self.static_data[key] = value
        self.data_changed = True
