from __future__ import annotations

import sys

import pytest

from analytiq_data.flows.builtin_loader import (
    ensure_builtin_keys_for_revision,
    register_builtin_nodes,
)
from analytiq_data.flows.lazy_builtin_node import LazyBuiltinNode
from analytiq_data.flows.node_registry import _registry, get, is_registered


@pytest.fixture(autouse=True)
def _clear_registry() -> None:
    _registry.clear()
    import analytiq_data.flows.builtin_loader as loader

    loader._all_builtins_registered = False
    yield
    _registry.clear()
    loader._all_builtins_registered = False


def _pop_gmail_modules() -> None:
    for name in (
        "analytiq_data.flows.nodes.gmail.node",
        "analytiq_data.flows.nodes.gmail.operations",
        "analytiq_data.flows.nodes.microsoft_onedrive.node",
        "analytiq_data.flows.nodes.microsoft_onedrive.operations",
    ):
        sys.modules.pop(name, None)


def test_ensure_builtin_keys_registers_only_revision_types() -> None:
    _pop_gmail_modules()
    revision = {
        "nodes": [
            {"id": "t1", "type": "flows.trigger.manual", "name": "Manual"},
            {"id": "g1", "type": "flows.gmail", "name": "Gmail"},
        ]
    }
    keys = ensure_builtin_keys_for_revision(revision)
    assert keys == frozenset({"flows.trigger.manual", "flows.gmail"})
    assert is_registered("flows.gmail")
    assert is_registered("flows.trigger.manual")
    assert not is_registered("flows.microsoft_onedrive")
    assert "analytiq_data.flows.nodes.gmail.operations" not in sys.modules

    nt = get("flows.gmail")
    assert isinstance(nt, LazyBuiltinNode)


def test_validate_revision_registers_types_without_register_builtin_nodes() -> None:
    import analytiq_data as ad

    _pop_gmail_modules()
    nodes = [
        {"id": "t1", "type": "flows.trigger.manual", "name": "Manual", "parameters": {}},
        {"id": "c1", "type": "flows.code", "name": "Code", "parameters": {}},
    ]
    connections = {
        "t1": {
            "main": [
                [ad.flows.NodeConnection(dest_node_id="c1", connection_type="main", index=0)]
            ]
        }
    }
    ad.flows.validate_revision(nodes, connections, {}, None)
    assert is_registered("flows.trigger.manual")
    assert is_registered("flows.code")
    assert not is_registered("flows.gmail")


def test_register_builtin_nodes_still_registers_all() -> None:
    register_builtin_nodes()
    assert is_registered("flows.gmail")
    assert is_registered("flows.microsoft_onedrive")
