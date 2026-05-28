from __future__ import annotations

from analytiq_data.flows.builtin_loader import load_builtin_node_class
from analytiq_data.flows.builtin_manifest import SPEC_BY_KEY
from analytiq_data.flows.node_manifest_io import load_node_manifest, manifest_executor_spec


def test_load_builtin_node_class_uses_manifest_executor() -> None:
    spec = SPEC_BY_KEY["flows.gmail"]
    manifest = load_node_manifest(spec)
    binding = manifest_executor_spec(manifest)
    cls = load_builtin_node_class(spec)
    assert cls.__module__ == binding["module"]
    assert cls.__name__ == binding["class_name"]
    assert cls.key == "flows.gmail"
