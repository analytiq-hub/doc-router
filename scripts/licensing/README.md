# Local license tooling

Internal helpers for DocRouter product licenses. Not shipped to customers.

| Script | Purpose |
|--------|---------|
| `generate_keys.py` | Create Ed25519 keypair |
| `issue_license.py` | Sign a claims JSON file → `DRLIC1.…` token |
| `manage_ui.py` | Localhost UI to generate / review licenses + docs |

## License manager UI

```bash
# One-time: put the private key where the UI expects it
python scripts/licensing/generate_keys.py --out-dir /tmp/dr-lic
cp /tmp/dr-lic/license-private.pem ~/.ssh/docrouter-license-private.pem
chmod 600 ~/.ssh/docrouter-license-private.pem
cp /tmp/dr-lic/license-public.pem \
  packages/python/analytiq_data/licensing/keys/license-public.pem

# Run (repo root, venv active)
python scripts/licensing/manage_ui.py
# → http://127.0.0.1:8765
```

Tabs: **Generate**, **Review**, **Documentation**.

Binds to `127.0.0.1` by default. Override key path with `--private-key`.
