# License public key

This directory ships **only** the Ed25519 public key used to verify product
license tokens (`DRLIC1.…`).

The corresponding private key is **not** in this repository. Issue licenses with
`scripts/licensing/issue_license.py` using a private key held in an internal
secrets manager.

Override the public key path for tests via `LICENSE_PUBLIC_KEY_PATH`.
