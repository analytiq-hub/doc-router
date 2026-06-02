"""Builtin flow nodes: manifest file paths (executor binding lives in each JSON file)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import NamedTuple

_FLOWS_ROOT = Path(__file__).resolve().parent

# Paths relative to ``analytiq_data/flows/``. Order is stable for tests and palette listing.
BUILTIN_MANIFEST_RELPATHS: tuple[str, ...] = (
    "nodes/trigger_manual.manifest.json",
    "nodes/trigger_schedule.manifest.json",
    "nodes/trigger_webhook.manifest.json",
    "nodes/respond_to_webhook.manifest.json",
    "nodes/http_request.manifest.json",
    "nodes/branch.manifest.json",
    "nodes/merge.manifest.json",
    "nodes/code.manifest.json",
    "nodes/google_drive/node.manifest.json",
    "nodes/google_drive/trigger.manifest.json",
    "nodes/gmail/node.manifest.json",
    "nodes/gmail/trigger.manifest.json",
    "nodes/microsoft_onedrive/node.manifest.json",
    "nodes/microsoft_onedrive/trigger.manifest.json",
    "nodes/microsoft_outlook/node.manifest.json",
    "nodes/microsoft_outlook/trigger.manifest.json",
)


class BuiltinNodeSpec(NamedTuple):
    key: str
    manifest_relpath: str


def _peek_manifest_raw(relpath: str) -> dict:
    return json.loads((_FLOWS_ROOT / relpath).read_text(encoding="utf-8"))


def _spec_from_relpath(relpath: str) -> tuple[BuiltinNodeSpec, str]:
    raw = _peek_manifest_raw(relpath)
    spec = BuiltinNodeSpec(key=str(raw["key"]), manifest_relpath=relpath)
    class_name = str(raw["executor"]["class"])
    return spec, class_name


_specs_and_classes = [_spec_from_relpath(relpath) for relpath in BUILTIN_MANIFEST_RELPATHS]
BUILTIN_NODES: tuple[BuiltinNodeSpec, ...] = tuple(spec for spec, _ in _specs_and_classes)

SPEC_BY_KEY: dict[str, BuiltinNodeSpec] = {s.key: s for s in BUILTIN_NODES}

SPEC_BY_CLASS_NAME: dict[str, BuiltinNodeSpec] = {
    class_name: spec for spec, class_name in _specs_and_classes
}

BUILTIN_CLASS_NAMES: frozenset[str] = frozenset(SPEC_BY_CLASS_NAME)
