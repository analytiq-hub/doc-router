from __future__ import annotations

"""
Execution output shapes stored in `flow_executions.run_data`.

These dataclasses mirror the spec's `NodeRunData` and `NodeOutputData` records.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal

import analytiq_data as ad

NodeStatus = Literal["success", "error", "skipped"]


@dataclass
class NodeOutputData:
    """Per-node output data grouped by connection lane (v1 uses `main`)."""

    # Matches spec: { "main": [ [FlowItem...], [FlowItem...] ] }
    main: list[list["ad.flows.FlowItem"]]


@dataclass
class NodeRunData:
    """Per-node execution record: status, timing, outputs, and optional error envelope."""

    status: NodeStatus
    start_time: datetime
    execution_time_ms: int
    data: dict[str, Any] | None = None
    error: dict[str, Any] | None = None

