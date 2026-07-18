"""Ed25519 license token verification."""

from __future__ import annotations

import base64
import json
import logging
import os
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Optional

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from .claims import PRODUCT_NAME, LicenseClaims

logger = logging.getLogger(__name__)

TOKEN_PREFIX = "DRLIC1"
DEFAULT_PUBLIC_KEY_PATH = Path(__file__).parent / "keys" / "license-public.pem"


class LicenseVerifyError(Exception):
    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(message)


def _b64url_decode(data: str) -> bytes:
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + padding)


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def canonical_json_bytes(payload: dict) -> bytes:
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


@lru_cache(maxsize=4)
def load_public_key(path: Optional[str] = None) -> Ed25519PublicKey:
    key_path = Path(path or os.getenv("LICENSE_PUBLIC_KEY_PATH") or DEFAULT_PUBLIC_KEY_PATH)
    pem = key_path.read_bytes()
    key = serialization.load_pem_public_key(pem)
    if not isinstance(key, Ed25519PublicKey):
        raise LicenseVerifyError("LICENSE_INVALID", "Public key is not Ed25519")
    return key


def clear_public_key_cache() -> None:
    load_public_key.cache_clear()


def verify_license_token(
    token: str,
    *,
    installation_id: Optional[str] = None,
    now: Optional[datetime] = None,
    public_key: Optional[Ed25519PublicKey] = None,
    check_temporal: bool = True,
) -> LicenseClaims:
    """Verify signature and structural claims. Optionally check not_before.

    Does not apply expiry / grace — callers use evaluate helpers for that.
    """
    if not token or not isinstance(token, str):
        raise LicenseVerifyError("LICENSE_INVALID", "License key is empty")

    parts = token.strip().split(".")
    if len(parts) != 3 or parts[0] != TOKEN_PREFIX:
        raise LicenseVerifyError(
            "LICENSE_INVALID",
            "License key must be DRLIC1.<payload>.<signature>",
        )

    payload_b64, sig_b64 = parts[1], parts[2]
    try:
        payload_bytes = _b64url_decode(payload_b64)
        signature = _b64url_decode(sig_b64)
    except Exception as e:
        raise LicenseVerifyError("LICENSE_INVALID", f"Invalid base64url encoding: {e}") from e

    key = public_key or load_public_key()
    try:
        key.verify(signature, payload_bytes)
    except InvalidSignature as e:
        raise LicenseVerifyError("LICENSE_INVALID", "Invalid license signature") from e

    try:
        payload = json.loads(payload_bytes.decode("utf-8"))
    except Exception as e:
        raise LicenseVerifyError("LICENSE_INVALID", f"Invalid license payload JSON: {e}") from e

    if not isinstance(payload, dict):
        raise LicenseVerifyError("LICENSE_INVALID", "License payload must be an object")

    # Re-canonicalization check: signature was over exact middle-segment bytes
    # (already verified). Parse into model.
    try:
        claims = LicenseClaims.model_validate(payload)
    except Exception as e:
        raise LicenseVerifyError("LICENSE_INVALID", f"Invalid license claims: {e}") from e

    if claims.product != PRODUCT_NAME:
        raise LicenseVerifyError(
            "LICENSE_INVALID",
            f"License product must be '{PRODUCT_NAME}'",
        )

    bound = claims.deployment.installation_id
    if bound and installation_id and bound != installation_id:
        raise LicenseVerifyError(
            "LICENSE_INVALID",
            "License installation_id does not match this deployment",
        )

    if check_temporal:
        current = now or datetime.now(timezone.utc)
        if current.tzinfo is None:
            current = current.replace(tzinfo=timezone.utc)
        nbf = claims.not_before
        if nbf.tzinfo is None:
            nbf = nbf.replace(tzinfo=timezone.utc)
        if current < nbf:
            raise LicenseVerifyError(
                "LICENSE_INVALID",
                "License is not yet valid (not_before)",
            )

    return claims


def issue_license_token(payload: dict, private_key_pem: bytes, password: Optional[bytes] = None) -> str:
    """Internal helper for scripts/tests: sign a claims dict."""
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    key = serialization.load_pem_private_key(private_key_pem, password=password)
    if not isinstance(key, Ed25519PrivateKey):
        raise ValueError("Private key is not Ed25519")
    payload_bytes = canonical_json_bytes(payload)
    signature = key.sign(payload_bytes)
    return f"{TOKEN_PREFIX}.{_b64url_encode(payload_bytes)}.{_b64url_encode(signature)}"
