"""Flow node implementations (lazy class exports; see ``flows.builtin_manifest``)."""

from __future__ import annotations

from typing import Any

from analytiq_data.flows.builtin_manifest import BUILTIN_CLASS_NAMES, SPEC_BY_CLASS_NAME
from analytiq_data.flows.builtin_loader import load_builtin_node_class

__all__ = sorted(BUILTIN_CLASS_NAMES)


def __getattr__(name: str) -> Any:
    spec = SPEC_BY_CLASS_NAME.get(name)
    if spec is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    return load_builtin_node_class(spec)


def __dir__() -> list[str]:
    return sorted(__all__)
