"""Load ``node.manifest.json`` files for builtin flow nodes (Phase C palette metadata)."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from analytiq_data.docrouter_flows.docrouter_builtin_manifest import DOCROUTER_NODES, DOCROUTER_SPEC_BY_KEY
from analytiq_data.flows.builtin_manifest import BUILTIN_NODES, SPEC_BY_KEY, BuiltinNodeSpec

_FLOWS_ROOT = Path(__file__).resolve().parent
_DOCROUTER_ROOT = Path(__file__).resolve().parent.parent / "docrouter_flows"
# Stable identifier for manifest format v1 (not fetched over HTTP).
MANIFEST_SCHEMA_ID = "urn:docrouter:flow-node-manifest:v1"


def manifest_path_for_spec(spec: BuiltinNodeSpec) -> Path:
    if spec.key in DOCROUTER_SPEC_BY_KEY:
        return _DOCROUTER_ROOT / spec.manifest_relpath
    return _FLOWS_ROOT / spec.manifest_relpath


def manifest_dir_for_spec(spec: BuiltinNodeSpec) -> Path:
    return manifest_path_for_spec(spec).parent


@lru_cache(maxsize=None)
def load_node_manifest(spec: BuiltinNodeSpec) -> dict[str, Any]:
    path = manifest_path_for_spec(spec)
    raw = json.loads(path.read_text(encoding="utf-8"))
    if str(raw.get("key")) != spec.key:
        raise ValueError(
            f"manifest key {raw.get('key')!r} does not match builtin index {spec.key!r} ({path})"
        )
    return _resolve_manifest(raw, path.parent)


def load_node_manifest_by_key(key: str) -> dict[str, Any]:
    return load_node_manifest(SPEC_BY_KEY[key])


def reload_node_manifest(spec: BuiltinNodeSpec) -> dict[str, Any]:
    """Reload palette metadata after manifest/schema edits (clears LRU cache)."""

    load_node_manifest.cache_clear()
    return load_node_manifest(spec)


def _resolve_manifest(raw: dict[str, Any], base_dir: Path) -> dict[str, Any]:
    out = dict(raw)
    ref = out.pop("parameter_schema_ref", None)
    if ref:
        schema_path = base_dir / str(ref)
        out["parameter_schema"] = json.loads(schema_path.read_text(encoding="utf-8"))
    if "parameter_schema" not in out:
        raise ValueError(f"manifest at {base_dir} has no parameter_schema or parameter_schema_ref")
    return out


def list_builtin_palette_manifests() -> list[dict[str, Any]]:
    """All builtin palette metadata from JSON manifests (no Python executor import)."""

    return [load_node_manifest(spec) for spec in (*BUILTIN_NODES, *DOCROUTER_NODES)]


def manifest_executor_spec(manifest: dict[str, Any]) -> dict[str, str]:
    """Python class binding from a resolved or raw manifest (``executor`` block)."""

    executor = manifest.get("executor") or {}
    if executor.get("kind") != "python_class":
        raise ValueError(f"unsupported executor kind for {manifest.get('key')!r}")
    return {
        "module": str(executor["import"]),
        "class_name": str(executor["class"]),
    }
