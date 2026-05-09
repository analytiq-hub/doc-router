#!/usr/bin/env python3
"""
Read NDJSON from ``tools/dump_credentials.js`` and write DocRouter kind JSON files.

Usage:
  python tools/port_credentials.py tools/credential_dump.jsonl --out schemas/credential-kinds
  python tools/port_credentials.py --stdin < tools/credential_dump.jsonl --dry-run

Requires ``PYTHONPATH`` including ``packages/python`` (or run from a venv where ``analytiq_data`` is installed).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Repo layout: tools/ → parents[1] = workspace root
_REPO_ROOT = Path(__file__).resolve().parents[1]
_PY_PKG = _REPO_ROOT / "packages" / "python"
if _PY_PKG.is_dir() and str(_PY_PKG) not in sys.path:
    sys.path.insert(0, str(_PY_PKG))

from analytiq_data.flows.n8n_credential_port import (  # noqa: E402
    iter_ndjson_lines,
    port_record_to_kind,
)


def main() -> int:
    ap = argparse.ArgumentParser(description="Port n8n credential dump to DocRouter kind JSON.")
    ap.add_argument(
        "input",
        nargs="?",
        help="NDJSON file from dump_credentials.js (omit with --stdin)",
    )
    ap.add_argument(
        "--out",
        default=str(_REPO_ROOT / "schemas" / "credential-kinds"),
        help="Output directory for <key>.json",
    )
    ap.add_argument("--stdin", action="store_true", help="Read NDJSON from stdin")
    ap.add_argument("--dry-run", action="store_true", help="Do not write files")
    ap.add_argument("--overwrite", action="store_true", help="Replace existing JSON files")
    ap.add_argument("--limit", type=int, default=0, help="Max credentials to emit (0 = all)")
    ap.add_argument(
        "--report",
        help="Write JSON summary of skipped/failed keys to this path",
    )
    args = ap.parse_args()

    out_dir = Path(args.out)
    if not args.dry_run:
        out_dir.mkdir(parents=True, exist_ok=True)

    if args.stdin:
        lines = sys.stdin
    else:
        if not args.input:
            ap.error("pass INPUT file or --stdin")
        p = Path(args.input)
        if not p.is_file():
            print(f"error: input not found: {p}", file=sys.stderr)
            return 2
        lines = p.open(encoding="utf-8")

    wrote = 0
    skipped: dict[str, str] = {}
    report_rows: list[dict[str, str]] = []

    for i, record in enumerate(iter_ndjson_lines(lines)):
        if args.limit and i >= args.limit:
            break
        if not isinstance(record, dict):
            continue
        key = record.get("name")
        if not isinstance(key, str):
            continue

        kind, err = port_record_to_kind(record)
        if kind is None:
            skipped[key] = err or "unknown"
            report_rows.append({"key": key, "status": "skip", "detail": skipped[key]})
            continue

        dest = out_dir / f"{key}.json"
        if dest.exists() and not args.overwrite:
            skipped[key] = "exists (pass --overwrite)"
            report_rows.append({"key": key, "status": "exists", "detail": skipped[key]})
            continue

        if args.dry_run:
            wrote += 1
            continue

        dest.write_text(json.dumps(kind, indent=2, sort_keys=False) + "\n", encoding="utf-8")
        wrote += 1

    print(
        f"wrote={wrote} skipped={len(skipped)} out_dir={out_dir}",
        file=sys.stderr,
    )
    if args.report:
        Path(args.report).write_text(json.dumps(report_rows, indent=2), encoding="utf-8")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
