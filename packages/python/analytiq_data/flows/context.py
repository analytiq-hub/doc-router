from __future__ import annotations

"""
Execution context for flow runs.

The engine is kept DocRouter-independent; DocRouter-specific nodes can call into
`analytiq_data.docrouter_flows.services` using the `analytiq_client` stored on
the context.
"""

from dataclasses import dataclass, field
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
    #: Node id → captured `flows.code` print/log lines (manual UI console).
    node_logs: dict[str, list[str]] = field(default_factory=dict)
    #: Per-node credential fields for integration nodes + HTTP Request (see docs/docrouter_credentials.md).
    credentials: dict[str, Any] = field(default_factory=dict)
    #: Revision ``nodes`` for name-keyed ``_node`` in parameter expressions (see ``expressions.materialize_node_outputs_by_name``).
    revision_nodes: list[dict[str, Any]] | None = None
    #: Monotonic step counter incremented before each node executes (``execution_index`` on run records).
    execution_index: int = 0
    #: Node id → structured trace events flushed into ``run_data[node_id].trace``.
    node_traces: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    #: Node currently executing; used by integration helpers when ``node_id`` is omitted.
    active_trace_node_id: str | None = None

