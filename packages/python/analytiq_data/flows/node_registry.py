from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from .context import ExecutionContext
from .items import FlowItem


@runtime_checkable
class NodeType(Protocol):
    key: str
    label: str
    description: str
    category: str
    is_trigger: bool
    min_inputs: int
    max_inputs: int | None
    outputs: int
    output_labels: list[str]
    parameter_schema: dict[str, Any]

    async def execute(
        self,
        context: ExecutionContext,
        node: dict[str, Any],
        inputs: list[list[FlowItem]],
    ) -> list[list[FlowItem]]: ...

    def validate_parameters(self, params: dict[str, Any]) -> list[str]: ...


_registry: dict[str, NodeType] = {}


def register(node_type: NodeType) -> None:
    _registry[node_type.key] = node_type


def get(key: str) -> NodeType:
    if key not in _registry:
        raise KeyError(f"Unknown node type: {key!r}")
    return _registry[key]


def list_all() -> list[NodeType]:
    return list(_registry.values())

