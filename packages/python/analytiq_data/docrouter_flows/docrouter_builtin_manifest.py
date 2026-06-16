"""DocRouter flow nodes: manifest file paths (executor binding lives in each JSON file)."""

from __future__ import annotations

from pathlib import Path

from analytiq_data.flows.builtin_manifest import BuiltinNodeSpec

_DOCROUTER_ROOT = Path(__file__).resolve().parent

# Paths relative to ``analytiq_data/docrouter_flows/``. Order is stable for tests and palette listing.
DOCROUTER_MANIFEST_RELPATHS: tuple[str, ...] = (
    "nodes/event_trigger.manifest.json",
    "nodes/manual_trigger.manifest.json",
    "nodes/ocr.manifest.json",
    "nodes/llm_extract.manifest.json",
    "nodes/set_tags.manifest.json",
)

DOCROUTER_NODE_KEYS: tuple[str, ...] = (
    "docrouter.trigger",
    "docrouter.trigger.manual",
    "docrouter.ocr",
    "docrouter.llm_extract",
    "docrouter.set_tags",
)


def docrouter_flows_root() -> Path:
    return _DOCROUTER_ROOT


DOCROUTER_NODES: tuple[BuiltinNodeSpec, ...] = tuple(
    BuiltinNodeSpec(key=key, manifest_relpath=relpath)
    for relpath, key in zip(DOCROUTER_MANIFEST_RELPATHS, DOCROUTER_NODE_KEYS, strict=True)
)

DOCROUTER_SPEC_BY_KEY: dict[str, BuiltinNodeSpec] = {spec.key: spec for spec in DOCROUTER_NODES}
