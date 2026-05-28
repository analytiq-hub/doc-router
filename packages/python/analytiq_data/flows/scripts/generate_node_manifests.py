#!/usr/bin/env python3
"""Generate ``node.manifest.json`` for each builtin from current Python node classes."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

# Repo: packages/python on path
_ROOT = Path(__file__).resolve().parents[3]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from analytiq_data.flows.builtin_loader import instantiate_builtin  # noqa: E402
from analytiq_data.flows.builtin_manifest import BUILTIN_NODES  # noqa: E402
from analytiq_data.flows.node_manifest_io import (  # noqa: E402
    _MANIFEST_SCHEMA_URI,
    manifest_dir_for_spec,
    manifest_path_for_spec,
)

_SCHEMA_REF_BY_SPEC: dict[str, str | None] = {
    "flows.google_drive": "parameter.schema.json",
    "flows.trigger.google_drive": "trigger.parameter.schema.json",
    "flows.gmail": "parameter.schema.json",
    "flows.trigger.gmail": "trigger.parameter.schema.json",
    "flows.microsoft_onedrive": "parameter.schema.json",
    "flows.trigger.microsoft_onedrive": "trigger.parameter.schema.json",
}


def _manifest_body(spec, nt: Any) -> dict[str, Any]:
    schema_ref = _SCHEMA_REF_BY_SPEC.get(spec.key)
    body: dict[str, Any] = {
        "schema": _MANIFEST_SCHEMA_URI,
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
            "import": spec.module,
            "class": spec.class_name,
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
    slots = getattr(nt, "credential_slots", None)
    if isinstance(slots, list) and slots:
        body["credential_slots"] = slots
    if schema_ref:
        body["parameter_schema_ref"] = schema_ref
    else:
        body["parameter_schema"] = nt.parameter_schema
    return body


def main() -> None:
    for spec in BUILTIN_NODES:
        nt = instantiate_builtin(spec)
        path = manifest_path_for_spec(spec)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(_manifest_body(spec, nt), indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        print(f"wrote {path.relative_to(manifest_dir_for_spec(spec).parents[1])}")


if __name__ == "__main__":
    main()
