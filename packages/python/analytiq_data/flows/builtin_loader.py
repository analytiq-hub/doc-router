"""Register builtin flow nodes from JSON manifests; load executors on demand."""

from __future__ import annotations

import importlib
from collections.abc import Iterable
from typing import TYPE_CHECKING, Any

from analytiq_data.flows.builtin_manifest import (
    BUILTIN_NODES,
    BuiltinNodeSpec,
    SPEC_BY_KEY,
)
from analytiq_data.flows.lazy_builtin_node import LazyBuiltinNode
from analytiq_data.flows.node_manifest_io import (
    load_node_manifest,
    manifest_executor_spec,
)
from analytiq_data.flows.node_registry import get, is_registered, register

if TYPE_CHECKING:
    from analytiq_data.flows.node_registry import NodeType

_all_builtins_registered = False


def load_builtin_node_class(spec: BuiltinNodeSpec) -> type:
    manifest = load_node_manifest(spec)
    binding = manifest_executor_spec(manifest)
    module = importlib.import_module(binding["module"])
    return getattr(module, binding["class_name"])


def instantiate_builtin(spec: BuiltinNodeSpec) -> "NodeType":
    return load_builtin_node_class(spec)()


def register_builtin_palette_node(spec: BuiltinNodeSpec) -> LazyBuiltinNode:
    if is_registered(spec.key):
        existing = get(spec.key)
        assert isinstance(existing, LazyBuiltinNode), (
            f"registry entry for {spec.key!r} must be a LazyBuiltinNode, got {type(existing)!r}"
        )
        return existing
    manifest = load_node_manifest(spec)
    node_type = LazyBuiltinNode(spec, manifest)
    register(node_type)
    return node_type


def node_type_keys_in_revision(
    revision: dict[str, Any] | None = None,
    *,
    nodes: list[dict[str, Any]] | None = None,
) -> frozenset[str]:
    """Distinct ``nodes[].type`` values from a revision document or node list."""

    node_list = nodes if nodes is not None else (revision or {}).get("nodes") or []
    keys: set[str] = set()
    if isinstance(node_list, list):
        for node in node_list:
            if not isinstance(node, dict):
                continue
            raw = node.get("type")
            if isinstance(raw, str):
                key = raw.strip()
                if key:
                    keys.add(key)
    return frozenset(keys)


def register_builtin_keys(keys: Iterable[str]) -> None:
    """Register lazy builtins for each key (no-op for unknown or already registered)."""

    for key in keys:
        try_register_builtin_key(key)


def ensure_builtin_keys_for_revision(
    revision: dict[str, Any] | None = None,
    *,
    nodes: list[dict[str, Any]] | None = None,
) -> frozenset[str]:
    """Register palette entries for all node types in a revision (Phase D)."""

    keys = node_type_keys_in_revision(revision, nodes=nodes)
    register_builtin_keys(keys)
    return keys


def try_register_builtin_key(key: str) -> bool:
    """Register a lazy builtin palette entry by key. Returns False if not builtin."""

    spec = SPEC_BY_KEY.get(key)
    if spec is None:
        return False
    if not is_registered(key):
        register_builtin_palette_node(spec)
    return True


def register_builtin_nodes() -> None:
    """Register every builtin from ``node.manifest.json`` (no executor import)."""

    global _all_builtins_registered
    for spec in BUILTIN_NODES:
        if not is_registered(spec.key):
            register_builtin_palette_node(spec)
    _all_builtins_registered = True


def ensure_all_builtin_nodes_registered() -> None:
    if not _all_builtins_registered:
        register_builtin_nodes()


def palette_entry_dict(manifest: dict[str, Any]) -> dict[str, Any]:
    """Shape for ``GET …/flows/node-types`` from a resolved manifest."""

    from types import SimpleNamespace

    from analytiq_data.flows.palette_groups import resolve_palette_group

    subject = SimpleNamespace(
        key=manifest["key"],
        is_trigger=manifest["is_trigger"],
        palette_group=manifest.get("palette_group"),
    )
    slots = manifest.get("credential_slots")
    return {
        "key": manifest["key"],
        "label": manifest["label"],
        "description": manifest["description"],
        "category": manifest["category"],
        "palette_group": resolve_palette_group(subject),
        "is_trigger": manifest["is_trigger"],
        "min_inputs": manifest["min_inputs"],
        "max_inputs": manifest.get("max_inputs"),
        "outputs": manifest["outputs"],
        "output_labels": manifest.get("output_labels") or [],
        "parameter_schema": manifest["parameter_schema"],
        "icon_key": manifest.get("icon_key"),
        "credential_slots": slots if isinstance(slots, list) else [],
        "experimental": bool(manifest.get("experimental", False)),
        "polling": bool(manifest.get("polling", False)),
    }


def list_builtin_palette_entries() -> list[dict[str, Any]]:
    """Palette rows from JSON manifests only (Phase C)."""

    from analytiq_data.flows.node_manifest_io import list_builtin_palette_manifests

    return [palette_entry_dict(m) for m in list_builtin_palette_manifests()]
