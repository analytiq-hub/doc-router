"""Generate committed ``node.manifest.json`` files from live node classes."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from analytiq_data.flows.builtin_loader import instantiate_builtin
from analytiq_data.flows.builtin_manifest import BUILTIN_MANIFEST_RELPATHS, BUILTIN_NODES, BuiltinNodeSpec
from analytiq_data.flows.node_manifest_io import MANIFEST_SCHEMA_ID

_FLOWS_ROOT = Path(__file__).resolve().parent


def manifest_path_for_flows_root(spec: BuiltinNodeSpec, flows_root: Path) -> Path:
    return flows_root / spec.manifest_relpath


def manifest_body_for_node(
    nt: Any,
    *,
    existing: dict[str, Any] | None = None,
) -> dict[str, Any]:
    cls = type(nt)
    body: dict[str, Any] = {
        "schema": MANIFEST_SCHEMA_ID,
        "manifest_version": 1,
        "key": nt.key,
        "type_version": int(getattr(nt, "type_version", 1)),
        "label": nt.label,
        "description": nt.description,
        "category": nt.category,
        "is_trigger": bool(getattr(nt, "is_trigger", False)),
        "is_merge": bool(getattr(nt, "is_merge", False)),
        "min_inputs": nt.min_inputs,
        "max_inputs": nt.max_inputs,
        "outputs": nt.outputs,
        "output_labels": list(nt.output_labels),
        "icon_key": getattr(nt, "icon_key", None),
        "executor": {
            "kind": "python_class",
            "import": cls.__module__,
            "class": cls.__name__,
        },
    }
    palette_group = getattr(nt, "palette_group", None)
    if palette_group:
        body["palette_group"] = palette_group
    if getattr(nt, "polling", False):
        body["polling"] = True
    if getattr(nt, "experimental", False):
        body["experimental"] = True
    if hasattr(nt, "batch_execute_inputs"):
        body["batch_execute_inputs"] = bool(nt.batch_execute_inputs)
    if hasattr(nt, "supports_batch_size"):
        body["supports_batch_size"] = bool(nt.supports_batch_size)
    slots = getattr(nt, "credential_slots", None)
    if isinstance(slots, list) and slots:
        body["credential_slots"] = slots
    prior = existing or {}
    if "parameter_schema_ref" in prior:
        body["parameter_schema_ref"] = prior["parameter_schema_ref"]
    else:
        body["parameter_schema"] = nt.parameter_schema
    return body


def format_manifest_json(body: dict[str, Any]) -> str:
    return json.dumps(body, indent=2, ensure_ascii=False) + "\n"


def generate_builtin_manifests(*, flows_root: Path | None = None) -> list[Path]:
    """Write all builtin manifests under *flows_root* (default: this package)."""

    root = flows_root if flows_root is not None else _FLOWS_ROOT
    written: list[Path] = []
    for spec in BUILTIN_NODES:
        path = manifest_path_for_flows_root(spec, root)
        path.parent.mkdir(parents=True, exist_ok=True)
        existing: dict[str, Any] = {}
        if path.exists():
            existing = json.loads(path.read_text(encoding="utf-8"))
        nt = instantiate_builtin(spec)
        path.write_text(
            format_manifest_json(manifest_body_for_node(nt, existing=existing)),
            encoding="utf-8",
        )
        written.append(path)
    return written
