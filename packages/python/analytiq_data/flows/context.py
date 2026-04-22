from __future__ import annotations

"""
Execution context and service interface for flow runs.

The engine is kept DocRouter-independent by accessing integrations only through
the `FlowServices` protocol.
"""

from dataclasses import dataclass
from typing import Any, Literal, Protocol

ExecutionMode = Literal["manual", "trigger", "webhook", "schedule", "error"]


class FlowServices(Protocol):
    """Services required by DocRouter-aware nodes during execution."""

    async def get_document(self, org_id: str, doc_id: str) -> dict: ...

    async def run_ocr(self, org_id: str, doc_id: str) -> dict: ...

    async def run_llm_extract(
        self, org_id: str, doc_id: str, prompt_id: str, schema_id: str
    ) -> dict: ...

    async def set_tags(self, org_id: str, doc_id: str, tags: list[str]) -> None: ...

    async def send_webhook(self, url: str, payload: dict, headers: dict) -> dict: ...

    async def get_runtime_state(self, flow_id: str, node_id: str) -> dict: ...

    async def set_runtime_state(self, flow_id: str, node_id: str, data: dict) -> None: ...


@dataclass
class ExecutionContext:
    """
    Per-execution context passed to every node.

    Contains identifiers, trigger metadata, the accumulated `run_data` map, a
    `FlowServices` implementation, and cooperative stop state.
    """

    organization_id: str
    execution_id: str
    flow_id: str
    flow_revid: str
    mode: ExecutionMode
    trigger_data: dict[str, Any]
    run_data: dict[str, Any]
    services: FlowServices
    stop_requested: bool = False
    logger: Any | None = None

