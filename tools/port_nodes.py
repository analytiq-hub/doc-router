#!/usr/bin/env python3
"""
Emit DocRouter node packages from a JSONL dump (see repository docs for the pipeline).

  python tools/port_nodes.py tools/flow_node_dump.jsonl --validate
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def main() -> int:
    rr = _repo_root()
    sys.path.insert(0, str(rr / "packages" / "python"))

    from analytiq_data.flows.port.converter import (
        DEFAULT_GENERATED_ROOT,
        convert_jsonl_file,
        validate_packages,
    )

    p = argparse.ArgumentParser(
        description="Generate DocRouter node packages from integration JSONL dump.",
    )
    p.add_argument(
        "jsonl",
        nargs="?",
        type=Path,
        default=rr / "tools" / "flow_node_dump.jsonl",
        help="Path to JSONL dump (default: tools/flow_node_dump.jsonl)",
    )
    p.add_argument(
        "--out",
        type=Path,
        default=DEFAULT_GENERATED_ROOT,
        help=(
            "Output root (default: packages/python/analytiq_data/flows/port/generated_nodes)"
        ),
    )
    p.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Maximum packages to emit (0 = no limit)",
    )
    p.add_argument(
        "--only-prefix",
        default=None,
        metavar="PREFIX",
        help="Only emit nodes whose manifest key starts with PREFIX (e.g. ext.slack)",
    )
    p.add_argument(
        "--validate",
        action="store_true",
        help="Validate against schemas/ (requires jsonschema)",
    )
    args = p.parse_args()

    jp = Path(args.jsonl)
    if not jp.is_file():
        print(f"error: JSONL dump not found: {jp}", file=sys.stderr)
        print(
            "  Run the dump tool with FLOW_DUMP_SUBDIRS and --upstream-root; see repo docs.",
            file=sys.stderr,
        )
        return 2

    out = Path(args.out)
    pkgs = convert_jsonl_file(
        jp,
        out,
        limit=args.limit,
        only_key_prefix=args.only_prefix,
    )
    print(f"Emitted {len(pkgs)} package(s) under {out}")

    if args.validate:
        try:
            validate_packages(pkgs)
        except Exception as e:
            print(f"validation error: {e}", file=sys.stderr)
            return 3
        print("Validated OK.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
