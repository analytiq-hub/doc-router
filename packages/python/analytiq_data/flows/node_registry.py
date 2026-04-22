from __future__ import annotations

"""
Node type registry for the generic flow engine.

This is a simple in-memory registry mapping `NodeType.key` to a concrete node
implementation. The registry is used by validation and runtime execution.
"""

from typing import Any, Protocol, runtime_checkable

import analytiq_data as ad


@runtime_checkable
class NodeType(Protocol):
    """Protocol describing a runnable node type that can be registered in the engine."""

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
        context: "ad.flows.ExecutionContext",
        node: dict[str, Any],
        inputs: list[list["ad.flows.FlowItem"]],
    ) -> list[list["ad.flows.FlowItem"]]: ...

    def validate_parameters(self, params: dict[str, Any]) -> list[str]: ...


_registry: dict[str, NodeType] = {}


def register(node_type: NodeType) -> None:
    """Register (or overwrite) a node type by its `key`."""

    _registry[node_type.key] = node_type


def get(key: str) -> NodeType:
    """Fetch a registered node type by key or raise `KeyError`."""

    if key not in _registry:
        raise KeyError(f"Unknown node type: {key!r}")
    return _registry[key]


def list_all() -> list[NodeType]:
    """List all currently registered node types."""

    return list(_registry.values())

