"""CI guard: committed ``node.manifest.json`` files match the generator output."""

from __future__ import annotations

import shutil
from pathlib import Path

from analytiq_data.flows.builtin_manifest import BUILTIN_MANIFEST_RELPATHS
from analytiq_data.flows.manifest_generate import generate_builtin_manifests

_FLOWS_PKG = Path(__file__).resolve().parents[2] / "analytiq_data" / "flows"

_REGENERATE_CMD = (
    "PYTHONPATH=packages/python python "
    "packages/python/analytiq_data/flows/scripts/generate_node_manifests.py"
)


def test_committed_node_manifests_match_generator(tmp_path: Path) -> None:
    staging = tmp_path / "flows"
    for relpath in BUILTIN_MANIFEST_RELPATHS:
        src = _FLOWS_PKG / relpath
        dst = staging / relpath
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)

    generate_builtin_manifests(flows_root=staging)

    stale: list[str] = []
    for relpath in BUILTIN_MANIFEST_RELPATHS:
        committed = (_FLOWS_PKG / relpath).read_text(encoding="utf-8")
        generated = (staging / relpath).read_text(encoding="utf-8")
        if committed != generated:
            stale.append(relpath)

    assert not stale, (
        "Committed node.manifest.json file(s) are out of date. Regenerate with:\n"
        f"  {_REGENERATE_CMD}\n"
        f"Stale ({len(stale)}): " + ", ".join(stale)
    )
