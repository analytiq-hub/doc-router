"""Register all builtin flow node types on the global registry."""

from __future__ import annotations

from analytiq_data.flows.builtin_loader import (
    ensure_all_builtin_nodes_registered,
    register_builtin_nodes,
    try_register_builtin_key,
)

__all__ = [
    "ensure_all_builtin_nodes_registered",
    "register_builtin_nodes",
    "try_register_builtin_key",
]
