"""Register all builtin flow node types on the global registry."""

from __future__ import annotations

from analytiq_data.flows.builtin_loader import (
    ensure_all_builtin_nodes_registered,
    ensure_builtin_keys_for_revision,
    list_builtin_palette_entries,
    node_type_keys_in_revision,
    register_builtin_keys,
    register_builtin_nodes,
    try_register_builtin_key,
)

__all__ = [
    "ensure_all_builtin_nodes_registered",
    "ensure_builtin_keys_for_revision",
    "list_builtin_palette_entries",
    "node_type_keys_in_revision",
    "register_builtin_keys",
    "register_builtin_nodes",
    "try_register_builtin_key",
]
