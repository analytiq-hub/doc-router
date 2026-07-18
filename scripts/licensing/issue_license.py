#!/usr/bin/env python3
"""Issue a DocRouter DRLIC1 license token from a claims JSON file."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Allow running from repo root without installing the package
REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "packages" / "python"))

from analytiq_data.licensing.verifier import issue_license_token  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--claims", type=Path, required=True, help="Path to claims JSON")
    parser.add_argument(
        "--private-key",
        type=Path,
        required=True,
        help="Path to Ed25519 private key PEM",
    )
    parser.add_argument("--password", default=None, help="Private key passphrase if encrypted")
    args = parser.parse_args()

    claims = json.loads(args.claims.read_text(encoding="utf-8"))
    private_pem = args.private_key.read_bytes()
    password = args.password.encode("utf-8") if args.password else None
    token = issue_license_token(claims, private_pem, password=password)
    print(token)


if __name__ == "__main__":
    main()
