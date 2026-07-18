#!/usr/bin/env python3
"""Local DocRouter license management UI (localhost only).

Assumes the Ed25519 private key lives at:
  ~/.ssh/docrouter-license-private.pem

Usage (from repo root, venv active):
  python scripts/licensing/manage_ui.py
  # open http://127.0.0.1:8765
"""

from __future__ import annotations

import argparse
import base64
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel, Field

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "packages" / "python"))

from cryptography.hazmat.primitives import serialization  # noqa: E402
from cryptography.hazmat.primitives.asymmetric.ed25519 import (  # noqa: E402
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

from dateutil import parser as date_parser

from analytiq_data.licensing.claims import (  # noqa: E402
    DEFAULT_GRACE_DAYS,
    FEATURE_DOCUMENTS,
    FEATURE_FLOWS,
    PRODUCT_NAME,
)
from analytiq_data.licensing.service import evaluate_claims  # noqa: E402
from analytiq_data.licensing.verifier import (  # noqa: E402
    LicenseVerifyError,
    issue_license_token,
    verify_license_token,
)

DEFAULT_PRIVATE_KEY = Path.home() / ".ssh" / "docrouter-license-private.pem"
UI_DIR = Path(__file__).resolve().parent / "ui"
DEFAULT_PORT = 8765

_private_key_path: Path = DEFAULT_PRIVATE_KEY
_private_key_password: Optional[bytes] = None


def _load_private_key() -> Ed25519PrivateKey:
    if not _private_key_path.is_file():
        raise HTTPException(
            status_code=503,
            detail=(
                f"Private key not found at {_private_key_path}. "
                "Generate one with scripts/licensing/generate_keys.py and place "
                "license-private.pem there (or pass --private-key)."
            ),
        )
    pem = _private_key_path.read_bytes()
    try:
        key = serialization.load_pem_private_key(pem, password=_private_key_password)
    except TypeError as e:
        raise HTTPException(
            status_code=503,
            detail="Private key is encrypted; restart with --password.",
        ) from e
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Failed to load private key: {e}") from e
    if not isinstance(key, Ed25519PrivateKey):
        raise HTTPException(status_code=503, detail="Key is not Ed25519")
    return key


def _public_key_from_private() -> Ed25519PublicKey:
    return _load_private_key().public_key()


def _public_pem() -> str:
    return (
        _public_key_from_private()
        .public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        .decode("ascii")
    )


app = FastAPI(title="DocRouter License Manager", docs_url=None, redoc_url=None)


class GenerateRequest(BaseModel):
    license_id: str = Field(..., min_length=1)
    customer_id: str = Field(..., min_length=1)
    customer_name: str = Field(..., min_length=1)
    product: str = PRODUCT_NAME
    start_date: str = Field(
        ...,
        min_length=1,
        description="License start (not_before). Accepts common date formats.",
    )
    expires_at: Optional[str] = None
    expires_in_days: int = Field(default=365, ge=1, le=3650)
    grace_days: int = Field(default=DEFAULT_GRACE_DAYS, ge=0, le=365)
    features: list[str] = Field(default_factory=lambda: [FEATURE_DOCUMENTS, FEATURE_FLOWS])
    limits_users: Optional[int] = Field(default=None, ge=1)
    limits_workspaces: Optional[int] = Field(default=None, ge=1)
    installation_id: Optional[str] = None


class ReviewRequest(BaseModel):
    license_key: str = Field(..., min_length=1)
    installation_id: Optional[str] = None


def _parse_flexible_date(value: str, *, end_of_day: bool = False) -> datetime:
    """Parse a human date string into an aware UTC datetime.

    Ambiguous numeric dates (e.g. 7/1/2024) are interpreted as MM/DD/YYYY
    (month first), matching US-style entry.

    Date-only inputs become midnight UTC on that calendar day (not "now"'s
    clock time — dateutil would otherwise fill hour/minute from the present).
    """
    raw = (value or "").strip()
    if not raw:
        raise HTTPException(status_code=400, detail="Start date is required")
    # default=… forces missing time fields to 00:00:00 instead of datetime.now().
    default = datetime(2000, 1, 1, 0, 0, 0)
    try:
        dt = date_parser.parse(raw, dayfirst=False, yearfirst=False, default=default)
    except (ValueError, OverflowError, TypeError) as e:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Could not parse date {value!r}. "
                "Try MM/DD/YYYY (e.g. 7/1/2024) or YYYY-MM-DD (e.g. 2024-07-01)."
            ),
        ) from e
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)
    if end_of_day and dt.hour == 0 and dt.minute == 0 and dt.second == 0 and dt.microsecond == 0:
        dt = dt.replace(hour=23, minute=59, second=59)
    return dt


def _iso_z(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


@app.get("/")
async def index() -> FileResponse:
    index_path = UI_DIR / "index.html"
    if not index_path.is_file():
        return HTMLResponse("<h1>Missing ui/index.html</h1>", status_code=500)
    return FileResponse(index_path)


@app.get("/api/status")
async def status() -> dict[str, Any]:
    exists = _private_key_path.is_file()
    pub: Optional[str] = None
    error: Optional[str] = None
    if exists:
        try:
            pub = _public_pem()
        except HTTPException as e:
            error = str(e.detail)
    return {
        "private_key_path": str(_private_key_path),
        "private_key_present": exists,
        "public_key_pem": pub,
        "error": error,
        "known_features": [FEATURE_DOCUMENTS, FEATURE_FLOWS],
        "product": PRODUCT_NAME,
    }


@app.post("/api/generate")
async def generate(body: GenerateRequest) -> dict[str, Any]:
    key = _load_private_key()
    now = datetime.now(timezone.utc)
    start = _parse_flexible_date(body.start_date)
    not_before = start
    issued = now
    if body.expires_at:
        expires = _parse_flexible_date(body.expires_at, end_of_day=True)
    else:
        expires = start + timedelta(days=body.expires_in_days)

    if expires <= not_before:
        raise HTTPException(
            status_code=400,
            detail="Expiry must be after the start date.",
        )

    features = [f for f in body.features if f]
    limits: dict[str, Any] = {}
    if body.limits_users is not None:
        limits["users"] = body.limits_users
    if body.limits_workspaces is not None:
        limits["workspaces"] = body.limits_workspaces

    deployment: dict[str, Any] = {}
    if body.installation_id and body.installation_id.strip():
        deployment["installation_id"] = body.installation_id.strip()

    claims = {
        "license_id": body.license_id.strip(),
        "customer_id": body.customer_id.strip(),
        "customer_name": body.customer_name.strip(),
        "product": body.product.strip() or PRODUCT_NAME,
        "issued_at": _iso_z(issued),
        "not_before": _iso_z(not_before),
        "expires_at": _iso_z(expires),
        "grace_days": body.grace_days,
        "features": features,
        "limits": limits,
        "deployment": deployment,
    }

    pem = key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    # If the on-disk key is encrypted we already decrypted into `key`; re-export
    # unencrypted bytes only in memory for signing helper.
    token = issue_license_token(claims, pem)
    return {"license_key": token, "claims": claims}


@app.post("/api/review")
async def review(body: ReviewRequest) -> dict[str, Any]:
    token = body.license_key.strip()
    try:
        claims = verify_license_token(
            token,
            installation_id=body.installation_id.strip() if body.installation_id else None,
            public_key=_public_key_from_private(),
            check_temporal=True,
        )
    except LicenseVerifyError as e:
        # Still try to decode payload for display
        payload = _try_decode_payload(token)
        return {
            "ok": False,
            "code": e.code,
            "message": e.message,
            "claims": payload,
            "status": None,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    status = evaluate_claims(
        claims,
        installation_id=body.installation_id or claims.deployment.installation_id or "local",
    )
    return {
        "ok": status.valid or status.mode in ("grace", "expired"),
        "code": status.code,
        "message": status.message,
        "claims": json.loads(claims.model_dump_json()),
        "status": status.model_dump(mode="json"),
    }


def _try_decode_payload(token: str) -> Optional[dict[str, Any]]:
    parts = token.split(".")
    if len(parts) != 3:
        return None
    try:
        pad = "=" * (-len(parts[1]) % 4)
        raw = base64.urlsafe_b64decode(parts[1] + pad)
        data = json.loads(raw.decode("utf-8"))
        return data if isinstance(data, dict) else None
    except Exception:
        return None


def main() -> None:
    global _private_key_path, _private_key_password

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--private-key",
        type=Path,
        default=DEFAULT_PRIVATE_KEY,
        help=f"Ed25519 private key PEM (default: {DEFAULT_PRIVATE_KEY})",
    )
    parser.add_argument("--password", default=None, help="Private key passphrase if encrypted")
    parser.add_argument("--host", default="127.0.0.1", help="Bind address (localhost only recommended)")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    args = parser.parse_args()

    _private_key_path = args.private_key.expanduser()
    _private_key_password = args.password.encode("utf-8") if args.password else None

    if args.host not in ("127.0.0.1", "localhost", "::1"):
        print(
            f"WARNING: binding to {args.host} exposes license signing on the network.",
            file=sys.stderr,
        )

    if not _private_key_path.is_file():
        print(
            f"Private key not found at {_private_key_path}\n"
            f"  python scripts/licensing/generate_keys.py --out-dir /tmp/dr-lic\n"
            f"  cp /tmp/dr-lic/license-private.pem {_private_key_path}\n"
            f"  cp /tmp/dr-lic/license-public.pem "
            f"packages/python/analytiq_data/licensing/keys/license-public.pem\n"
            f"The UI will still start; Generate/Review need the key.",
            file=sys.stderr,
        )

    import uvicorn

    print(f"DocRouter license manager → http://{args.host}:{args.port}")
    print(f"Private key: {_private_key_path}")
    uvicorn.run(app, host=args.host, port=args.port, log_level="info")


if __name__ == "__main__":
    main()
