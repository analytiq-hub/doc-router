"""Import and register builtin flow node types from ``builtin_manifest``."""

from __future__ import annotations

import importlib
from typing import TYPE_CHECKING

from analytiq_data.flows.builtin_manifest import (
    BUILTIN_NODES,
    BuiltinNodeSpec,
    SPEC_BY_KEY,
)
from analytiq_data.flows.node_registry import is_registered, register

if TYPE_CHECKING:
    from analytiq_data.flows.node_registry import NodeType

_all_builtins_registered = False


def load_builtin_node_class(spec: BuiltinNodeSpec) -> type:
    module = importlib.import_module(spec.module)
    return getattr(module, spec.class_name)


def instantiate_builtin(spec: BuiltinNodeSpec) -> "NodeType":
    return load_builtin_node_class(spec)()


def register_builtin_spec(spec: BuiltinNodeSpec) -> "NodeType":
    if is_registered(spec.key):
        from analytiq_data.flows.node_registry import get

        return get(spec.key)
    node_type = instantiate_builtin(spec)
    register(node_type)
    return node_type


def try_register_builtin_key(key: str) -> bool:
    """Load and register a manifest entry by key. Returns False if key is not builtin."""

    spec = SPEC_BY_KEY.get(key)
    if spec is None:
        return False
    if not is_registered(key):
        register_builtin_spec(spec)
    return True


def register_builtin_nodes() -> None:
    """Register every builtin node type (imports each implementation module once)."""

    global _all_builtins_registered
    for spec in BUILTIN_NODES:
        if not is_registered(spec.key):
            register_builtin_spec(spec)
    _all_builtins_registered = True


def ensure_all_builtin_nodes_registered() -> None:
    if not _all_builtins_registered:
        register_builtin_nodes()
