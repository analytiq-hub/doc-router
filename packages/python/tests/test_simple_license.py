"""Tests for offline product licensing (simple_license.md)."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

import analytiq_data as ad
from app.licensing_gate import is_path_allowlisted
from tests.conftest_utils import client, get_auth_headers


@pytest.fixture
def license_keypair(tmp_path, monkeypatch):
    private_key = Ed25519PrivateKey.generate()
    public_key = private_key.public_key()
    pub_path = tmp_path / "license-public.pem"
    pub_path.write_bytes(
        public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
    )
    priv_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    monkeypatch.setenv("LICENSE_PUBLIC_KEY_PATH", str(pub_path))
    ad.licensing.verifier.clear_public_key_cache()
    ad.licensing.invalidate_license_cache()
    yield private_key, priv_pem, pub_path
    ad.licensing.verifier.clear_public_key_cache()
    ad.licensing.invalidate_license_cache()


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def make_claims(
    *,
    features: list[str] | None = None,
    expires_in_days: int = 365,
    grace_days: int = 7,
    installation_id: str | None = None,
    product: str = "docrouter",
) -> dict:
    now = datetime.now(timezone.utc)
    claims = {
        "license_id": "lic_test_1",
        "customer_id": "acme",
        "customer_name": "Acme Corp",
        "product": product,
        "issued_at": _iso(now),
        "not_before": _iso(now - timedelta(days=1)),
        "expires_at": _iso(now + timedelta(days=expires_in_days)),
        "grace_days": grace_days,
        "features": features if features is not None else ["documents", "flows"],
        "limits": {},
        "deployment": {},
    }
    if installation_id:
        claims["deployment"] = {"installation_id": installation_id}
    return claims


def issue_token(priv_pem: bytes, claims: dict) -> str:
    return ad.licensing.verifier.issue_license_token(claims, priv_pem)


@pytest.mark.asyncio
async def test_no_key_ungated(test_db, mock_auth, license_keypair):
    status = await ad.licensing.get_cached_status(force=True)
    assert status.mode == "unlicensed"
    assert status.code == "LICENSE_MISSING"

    response = client.get("/v0/account/license/status", headers=get_auth_headers())
    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "unlicensed"
    assert body["features"] == []


@pytest.mark.asyncio
async def test_put_and_get_valid_license(test_db, mock_auth, license_keypair):
    _, priv_pem, _ = license_keypair
    token = issue_token(priv_pem, make_claims())

    response = client.put(
        "/v0/account/license",
        headers=get_auth_headers(),
        json={"license_key": token},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["valid"] is True
    assert body["mode"] == "licensed"
    assert set(body["features"]) == {"documents", "flows"}
    assert body["masked_key"]
    assert "DRLIC1" not in (body.get("license_key") or "")

    status = client.get("/v0/account/license/status", headers=get_auth_headers())
    assert status.status_code == 200
    assert status.json()["valid"] is True
    assert "masked_key" not in status.json() or status.json().get("masked_key") is None


@pytest.mark.asyncio
async def test_put_bad_signature_keeps_previous(test_db, mock_auth, license_keypair):
    _, priv_pem, _ = license_keypair
    good = issue_token(priv_pem, make_claims())
    client.put("/v0/account/license", headers=get_auth_headers(), json={"license_key": good})

    # Different keypair signature
    other = Ed25519PrivateKey.generate()
    other_pem = other.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    bad = issue_token(other_pem, make_claims(features=["documents"]))
    response = client.put(
        "/v0/account/license",
        headers=get_auth_headers(),
        json={"license_key": bad},
    )
    assert response.status_code == 400
    detail = response.json()["detail"]
    assert detail["code"] == "LICENSE_INVALID"

    admin = client.get("/v0/account/license", headers=get_auth_headers())
    assert admin.status_code == 200
    assert set(admin.json()["features"]) == {"documents", "flows"}


@pytest.mark.asyncio
async def test_expired_disables_api(test_db, mock_auth, license_keypair):
    _, priv_pem, _ = license_keypair
    token = issue_token(
        priv_pem,
        make_claims(expires_in_days=-40, grace_days=7),
    )
    put = client.put(
        "/v0/account/license",
        headers=get_auth_headers(),
        json={"license_key": token},
    )
    assert put.status_code == 200
    assert put.json()["mode"] == "expired"
    assert put.json()["state"] == "disabled"

    # License routes still work
    status = client.get("/v0/account/license/status", headers=get_auth_headers())
    assert status.status_code == 200
    assert status.json()["mode"] == "expired"

    # Org list is not allowlisted → 403
    blocked = client.get("/v0/account/organizations", headers=get_auth_headers())
    assert blocked.status_code == 403
    assert blocked.json()["detail"]["code"] == "LICENSE_EXPIRED"


@pytest.mark.asyncio
async def test_feature_gates(test_db, mock_auth, license_keypair):
    from tests.conftest_utils import TEST_ORG_ID

    _, priv_pem, _ = license_keypair
    token = issue_token(priv_pem, make_claims(features=["documents"]))
    client.put("/v0/account/license", headers=get_auth_headers(), json={"license_key": token})

    headers = get_auth_headers()

    docs = client.get(f"/v0/orgs/{TEST_ORG_ID}/documents", headers=headers)
    assert docs.status_code == 200

    flows = client.get(f"/v0/orgs/{TEST_ORG_ID}/flows", headers=headers)
    assert flows.status_code == 403
    assert flows.json()["detail"]["code"] == "FEATURE_NOT_LICENSED"


@pytest.mark.asyncio
async def test_installation_mismatch(test_db, mock_auth, license_keypair):
    _, priv_pem, _ = license_keypair
    await ad.licensing.ensure_installation_id()
    token = issue_token(
        priv_pem,
        make_claims(installation_id="inst_someone_else"),
    )
    response = client.put(
        "/v0/account/license",
        headers=get_auth_headers(),
        json={"license_key": token},
    )
    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "LICENSE_INVALID"


def test_allowlist_paths():
    assert is_path_allowlisted("/v0/account/license")
    assert is_path_allowlisted("/v0/account/license/status")
    assert is_path_allowlisted("/v0/account/auth/token")
    assert not is_path_allowlisted("/v0/account/organizations")
    assert not is_path_allowlisted("/v0/orgs/abc/documents")


@pytest.mark.asyncio
async def test_wrong_product(test_db, mock_auth, license_keypair):
    _, priv_pem, _ = license_keypair
    token = issue_token(priv_pem, make_claims(product="other"))
    response = client.put(
        "/v0/account/license",
        headers=get_auth_headers(),
        json={"license_key": token},
    )
    assert response.status_code == 400
