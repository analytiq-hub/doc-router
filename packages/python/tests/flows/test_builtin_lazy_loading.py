from __future__ import annotations

import importlib
import sys

import pytest

import analytiq_data as ad
from analytiq_data.flows.builtin_manifest import BUILTIN_NODES, SPEC_BY_KEY
from analytiq_data.flows.builtin_loader import (
    load_builtin_node_class,
    register_builtin_nodes,
    try_register_builtin_key,
)
from analytiq_data.flows.node_registry import _registry, get, is_registered


@pytest.fixture(autouse=True)
def _clear_registry() -> None:
    _registry.clear()
    import analytiq_data.flows.builtin_loader as loader

    loader._all_builtins_registered = False
    yield
    _registry.clear()
    loader._all_builtins_registered = False


def test_importing_flows_does_not_load_integration_node_modules() -> None:
    for name in (
        "analytiq_data.flows.nodes.gmail.operations",
        "analytiq_data.flows.nodes.google_drive.operations",
        "analytiq_data.flows.nodes.microsoft_onedrive.operations",
    ):
        sys.modules.pop(name, None)

    importlib.reload(ad.flows)

    assert "analytiq_data.flows.nodes.gmail.operations" not in sys.modules
    assert "analytiq_data.flows.nodes.google_drive.operations" not in sys.modules
    assert "analytiq_data.flows.nodes.microsoft_onedrive.operations" not in sys.modules


def test_get_lazy_registers_single_builtin() -> None:
    from analytiq_data.flows.lazy_builtin_node import LazyBuiltinNode

    spec = SPEC_BY_KEY["flows.gmail"]
    for name in (
        "analytiq_data.flows.nodes.gmail.node",
        "analytiq_data.flows.nodes.gmail.operations",
    ):
        sys.modules.pop(name, None)
    assert not is_registered(spec.key)

    nt = get(spec.key)

    assert nt.key == spec.key
    assert isinstance(nt, LazyBuiltinNode)
    assert is_registered(spec.key)
    assert "analytiq_data.flows.nodes.gmail.operations" not in sys.modules
    assert len(_registry) == 1


def test_register_builtin_nodes_registers_all_manifest_entries() -> None:
    register_builtin_nodes()
    assert len(_registry) == len(BUILTIN_NODES)
    for spec in BUILTIN_NODES:
        assert is_registered(spec.key)


def test_try_register_builtin_key_unknown_returns_false() -> None:
    assert try_register_builtin_key("flows.not.real") is False
    assert len(_registry) == 0


def test_flows_getattr_loads_one_node_class() -> None:
    sys.modules.pop("analytiq_data.flows.nodes.code", None)
    cls = ad.flows.FlowsCodeNode
    assert cls.key == "flows.code"
    assert "analytiq_data.flows.nodes.code" in sys.modules
    assert not is_registered("flows.gmail")
    # Avoid leaking the module into later tests that assert lazy get() did not import executors.
    sys.modules.pop("analytiq_data.flows.nodes.code", None)


def test_manifest_module_paths_resolve() -> None:
    before = set(sys.modules)
    for spec in BUILTIN_NODES:
        cls = load_builtin_node_class(spec)
        assert cls.key == spec.key
    # Do not leak node packages into lazy-registration tests (pytest-xdist ordering).
    for name in list(sys.modules):
        if name.startswith("analytiq_data.flows.nodes.") and name not in before:
            sys.modules.pop(name, None)
