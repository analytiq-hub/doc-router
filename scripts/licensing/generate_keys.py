#!/usr/bin/env python3
"""Generate an Ed25519 keypair for DocRouter product licenses."""

from __future__ import annotations

import argparse
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=Path("."),
        help="Directory for license-private.pem and license-public.pem",
    )
    parser.add_argument(
        "--password",
        default=None,
        help="Optional passphrase to encrypt the private key PEM",
    )
    args = parser.parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)

    private_key = Ed25519PrivateKey.generate()
    public_key = private_key.public_key()

    encryption: serialization.KeySerializationEncryption
    if args.password:
        encryption = serialization.BestAvailableEncryption(args.password.encode("utf-8"))
    else:
        encryption = serialization.NoEncryption()

    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=encryption,
    )
    public_pem = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )

    priv_path = args.out_dir / "license-private.pem"
    pub_path = args.out_dir / "license-public.pem"
    priv_path.write_bytes(private_pem)
    pub_path.write_bytes(public_pem)
    print(f"Wrote {priv_path}")
    print(f"Wrote {pub_path}")
    print("Keep the private key out of git and customer artifacts.")


if __name__ == "__main__":
    main()
