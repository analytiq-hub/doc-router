from __future__ import annotations

"""
Execution context for flow runs.

The engine is kept DocRouter-independent; DocRouter-specific nodes can call into
`analytiq_data.docrouter_flows.services` using the `analytiq_client` stored on
the context.
"""

from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Literal

ExecutionMode = Literal[
    "manual",
    "event",
    "trigger",
    "webhook",
    "schedule",
    "error",
    "sub_flow",
    "sub_flow_tool",
    "chat",
]


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
    #: Org setting ``organizations.flow_log_level`` (``ERROR`` | ``INFO`` | ``TRACE``).
    flow_log_level: str = "ERROR"
    #: Node ids with confirmed persisted checkpoints (resume skips these).
    completed_nodes: frozenset[str] = field(default_factory=frozenset)
    #: Source execution id when this run resumes from a checkpoint.
    resumed_from: str | None = None
    #: Precomputed tool wiring for tool_consumer nodes (node_id -> WiredTool list).
    tool_consumer_wiring: dict[str, list[Any]] | None = None
    #: Nested flow_tool stack for recursion/cycle detection.
    flow_id_stack: list[str] = field(default_factory=list)
    #: Chat streaming: when true, agent may stream LLM tokens via stream_sink.
    is_streaming: bool = False
    stream_sink: Callable[[dict[str, Any]], Awaitable[None]] | None = None

