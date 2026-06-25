from __future__ import annotations

import sys

import pytest

import analytiq_data as ad
from analytiq_data.flows.builtin_loader import (
    list_builtin_palette_entries,
    register_builtin_nodes,
)
from analytiq_data.flows.builtin_manifest import BUILTIN_NODES
from analytiq_data.docrouter_flows.docrouter_builtin_manifest import DOCROUTER_NODES
from analytiq_data.flows.lazy_builtin_node import LazyBuiltinNode
from analytiq_data.flows.node_registry import _registry, get, is_registered


def _pop_executor_modules(*, include_node: bool = False) -> None:
    for name in list(sys.modules):
        if "flows.nodes" not in name:
            continue
        if name.endswith(".operations") or (include_node and name.endswith(".node")):
            sys.modules.pop(name, None)


@pytest.fixture(autouse=True)
def _clear_registry() -> None:
    _registry.clear()
    import analytiq_data.flows.builtin_loader as loader

    loader._all_builtins_registered = False
    yield
    _registry.clear()
    loader._all_builtins_registered = False


def test_list_palette_entries_without_operations_modules() -> None:
    for name in list(sys.modules):
        if name.endswith(".operations") and "flows.nodes" in name:
            sys.modules.pop(name, None)

    entries = list_builtin_palette_entries()
    assert len(entries) == len(BUILTIN_NODES) + len(DOCROUTER_NODES)
    assert entries[0]["key"]
    assert "parameter_schema" in entries[0]
    assert "analytiq_data.flows.nodes.gmail.operations" not in sys.modules


def test_register_builtin_nodes_registers_lazy_wrappers_only() -> None:
    _pop_executor_modules()
    sys.modules.pop("analytiq_data.flows.nodes.gmail.node", None)
    register_builtin_nodes()
    assert len(_registry) == len(BUILTIN_NODES)
    nt = get("flows.gmail")
    assert isinstance(nt, LazyBuiltinNode)
    assert "analytiq_data.flows.nodes.gmail.operations" not in sys.modules


def test_executor_loads_on_first_delegate_access() -> None:
    _pop_executor_modules(include_node=True)
    register_builtin_nodes()
    nt = get("flows.gmail")
    assert isinstance(nt, LazyBuiltinNode)
    nt.validate_parameters({})
    assert "analytiq_data.flows.nodes.gmail.node" in sys.modules
    assert "analytiq_data.flows.nodes.gmail.operations" in sys.modules


def test_list_palette_entries_matches_manifest_keys() -> None:
    keys = {e["key"] for e in ad.flows.list_palette_entries()}
    assert keys == {s.key for s in BUILTIN_NODES} | {s.key for s in DOCROUTER_NODES}


def test_list_palette_entries_includes_docrouter_event_trigger() -> None:
    keys = {e["key"] for e in ad.flows.list_palette_entries()}
    assert "docrouter.trigger" in keys


def test_batch_execute_inputs_enabled_for_code_ocr_and_llm() -> None:
    by_key = {e["key"]: bool(e.get("batch_execute_inputs")) for e in ad.flows.list_palette_entries()}
    assert by_key["flows.code"] is True
    assert by_key["docrouter.ocr"] is True
    assert by_key["docrouter.llm_run"] is True


def test_supports_batch_size_enabled_only_for_ocr_and_llm() -> None:
    by_key = {e["key"]: bool(e.get("supports_batch_size")) for e in ad.flows.list_palette_entries()}
    assert by_key["docrouter.ocr"] is True
    assert by_key["docrouter.llm_run"] is True
    for key, enabled in by_key.items():
        if key in ("docrouter.ocr", "docrouter.llm_run"):
            continue
        assert enabled is False, key


def test_get_registers_lazy_without_executor() -> None:
    sys.modules.pop("analytiq_data.flows.nodes.microsoft_onedrive.node", None)
    sys.modules.pop("analytiq_data.flows.nodes.microsoft_onedrive.operations", None)
    assert not is_registered("flows.microsoft_onedrive")
    nt = get("flows.microsoft_onedrive")
    assert isinstance(nt, LazyBuiltinNode)
    assert "analytiq_data.flows.nodes.microsoft_onedrive.operations" not in sys.modules
