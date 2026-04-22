from __future__ import annotations

"""
Execution context for flow runs.

The engine is kept DocRouter-independent; DocRouter-specific nodes can call into
`analytiq_data.docrouter_flows.services` using the `analytiq_client` stored on
the context.
"""

from dataclasses import dataclass
from typing import Any, Literal

ExecutionMode = Literal["manual", "trigger", "webhook", "schedule", "error"]


@dataclass
class ExecutionContext:
    """
    Per-execution context passed to every node.

    Contains identifiers, trigger metadata, the accumulated `run_data` map, a
    process-wide `analytiq_client`, and cooperative stop state.
    """

    organization_id: str
    execution_id: str
    flow_id: str
    flow_revid: str
    mode: ExecutionMode
    trigger_data: dict[str, Any]
    run_data: dict[str, Any]
    analytiq_client: Any
    stop_requested: bool = False
    logger: Any | None = None

