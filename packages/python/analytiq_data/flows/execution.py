from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal

from .items import FlowItem

NodeStatus = Literal["success", "error", "skipped"]


@dataclass
class NodeOutputData:
    # Matches spec: { "main": [ [FlowItem...], [FlowItem...] ] }
    main: list[list[FlowItem]]


@dataclass
class NodeRunData:
    status: NodeStatus
    start_time: datetime
    execution_time_ms: int
    data: dict[str, Any] | None = None
    error: dict[str, Any] | None = None

