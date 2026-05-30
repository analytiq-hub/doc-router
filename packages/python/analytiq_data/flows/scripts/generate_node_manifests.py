#!/usr/bin/env python3
"""Generate ``node.manifest.json`` for each builtin from current Python node classes."""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[3]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from analytiq_data.flows.manifest_generate import generate_builtin_manifests  # noqa: E402


def main() -> None:
    flows_root = Path(__file__).resolve().parents[1]
    for path in generate_builtin_manifests(flows_root=flows_root):
        print(f"wrote {path.relative_to(flows_root)}")


if __name__ == "__main__":
    main()
