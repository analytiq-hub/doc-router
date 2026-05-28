"""Tests for OAuth/pre-auth credential runtime (``credential_runtime.py``)."""

from __future__ import annotations

import os
import time
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest

os.environ.setdefault("NEXTAUTH_SECRET", "test-secret-for-credential-runtime-tests")

import analytiq_data as ad
from analytiq_data.flows.credential_runtime import (
    FLOW_OAUTH_STATE_COLLECTION,
    apply_runtime_credential_updates,
    build_oauth_authorization_url,
    consume_flow_oauth_authorization_state,
    flow_oauth_redirect_uri,
    flow_oauth_redirect_uri_for_fields,
    flow_oauth_redirect_uri_for_kind,
    oauth_callback_redirect_success,
    decode_flow_oauth_state,
    encode_flow_oauth_state,
    exchange_authorization_code,
    generate_pkce_code_verifier,
    maybe_refresh_oauth_tokens,
    maybe_run_pre_auth,
    pkce_code_challenge_s256,
    require_oauth_client_configured,
    store_flow_oauth_authorization_state,
)
from urllib.parse import parse_qs, urlparse


def test_flow_oauth_redirect_uri_keeps_127_for_non_microsoft(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "analytiq_data.flows.credential_runtime._FLOW_OAUTH_PUBLIC_ORIGIN",
        "http://127.0.0.1:8000",
    )
    assert (
        flow_oauth_redirect_uri()
        == "http://127.0.0.1:8000/v0/callback/flow-oauth"
    )


def test_flow_oauth_redirect_uri_microsoft_maps_127_to_localhost(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "analytiq_data.flows.credential_runtime._FLOW_OAUTH_PUBLIC_ORIGIN",
        "http://127.0.0.1:8000",
    )
    fields = {
        "authUrl": "https://login.microsoftonline.com/common/oauth2/v2.0/authorize",
        "clientId": "cid",
    }
    assert (
        flow_oauth_redirect_uri_for_fields(fields)
        == "http://localhost:8000/v0/callback/flow-oauth"
    )
    kind = {"key": "microsoftOutlookOAuth2Api"}
    assert (
        flow_oauth_redirect_uri_for_kind(kind)
        == "http://localhost:8000/v0/callback/flow-oauth"
    )


def test_build_oauth_authorization_url_microsoft_uses_localhost_redirect(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "analytiq_data.flows.credential_runtime._FLOW_OAUTH_PUBLIC_ORIGIN",
        "http://127.0.0.1:8000",
    )
    fields = {
        "authUrl": "https://login.microsoftonline.com/common/oauth2/v2.0/authorize",
        "clientId": "cid",
    }
    url = build_oauth_authorization_url(fields, "state-xyz")
    redirect = parse_qs(urlparse(url).query)["redirect_uri"][0]
    assert redirect == "http://localhost:8000/v0/callback/flow-oauth"


def test_oauth_state_roundtrip():
    t = encode_flow_oauth_state("orgA", "cid1", "user1", ttl_seconds=60)
    payload = decode_flow_oauth_state(t)
    assert payload["org"] == "orgA"
    assert payload["cid"] == "cid1"
    assert payload["uid"] == "user1"


@pytest.mark.asyncio
async def test_flow_oauth_server_state_store_and_consume(test_db, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        "analytiq_data.flows.credential_runtime.ad.common.get_async_db",
        lambda: test_db,
    )

    nonce = await store_flow_oauth_authorization_state(
        organization_id="orgA",
        credential_id="cid1",
        user_id="u1",
        oauth_grant_type="pkce",
        pkce_verifier="pv-secret",
        ttl_seconds=60,
    )
    assert len(nonce) > 20

    row = await consume_flow_oauth_authorization_state(nonce)
    assert row is not None
    assert row["organization_id"] == "orgA"
    assert row["credential_id"] == "cid1"
    assert row["user_id"] == "u1"
    assert row["grant_type"] == "pkce"
    assert row["pkce_verifier"] == "pv-secret"

    assert await consume_flow_oauth_authorization_state(nonce) is None


@pytest.mark.asyncio
async def test_flow_oauth_server_state_rejects_expired(test_db, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        "analytiq_data.flows.credential_runtime.ad.common.get_async_db",
        lambda: test_db,
    )

    await test_db[FLOW_OAUTH_STATE_COLLECTION].insert_one(
        {
            "_id": "stale-nonce",
            "organization_id": "o",
            "credential_id": "c",
            "user_id": "u",
            "grant_type": "authorizationCode",
            "pkce_verifier": None,
            "expires_at": datetime.now(UTC) - timedelta(minutes=1),
        }
    )
    assert await consume_flow_oauth_authorization_state("stale-nonce") is None


def test_pkce_code_challenge_s256_rfc7636_appendix_b():
    v = "dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk"
    assert pkce_code_challenge_s256(v) == "E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM"


def test_generate_pkce_code_verifier_length_and_charset():
    v = generate_pkce_code_verifier()
    assert 43 <= len(v) <= 128
    assert all(c.isascii() for c in v)


def test_require_oauth_client_configured_rejects_missing_secret():
    with pytest.raises(RuntimeError, match="Client secret is missing"):
        require_oauth_client_configured({"clientId": "abc"})
    require_oauth_client_configured(
        {"clientId": "abc", "clientSecret": "sec"}, require_secret=False
    )


def test_build_oauth_authorization_url_rejects_empty_client_id():
    with pytest.raises(RuntimeError, match="Client ID is missing"):
        build_oauth_authorization_url({"authUrl": "https://example.com/a", "clientId": ""}, "st")


def test_build_oauth_authorization_url():
    fields = {
        "authUrl": "https://example.com/oauth/authorize",
        "clientId": "cid",
        "scope": "a b",
        "grantType": "authorizationCode",
    }
    url = build_oauth_authorization_url(fields, "state-xyz")
    assert url.startswith("https://example.com/oauth/authorize?")
    assert "state=state-xyz" in url.replace("+", " ")
    assert "client_id=cid" in url
    assert url.count("response_type=") == 1


def test_oauth_callback_redirect_success_includes_credential_id():
    url = oauth_callback_redirect_success("org1", "6a0b802bb023c1430b14a216")
    assert "flow_oauth=success" in url
    assert "flow_oauth_credential_id=6a0b802bb023c1430b14a216" in url


def test_build_oauth_authorization_url_preserves_static_query_and_custom_json():
    fields = {
        "authUrl": "https://example.com/oauth/authorize?audience=api",
        "clientId": "cid",
        "authQueryParameters": '{"prompt":"login","resource":"x"}',
        "grantType": "authorizationCode",
    }
    url = build_oauth_authorization_url(fields, "st")
    assert "audience=api" in url
    assert "prompt=login" in url
    assert "resource=x" in url
    assert url.count("client_id=") == 1


def test_build_oauth_authorization_url_parses_n8n_style_query_auth_params():
    fields = {
        "authUrl": "https://example.com/oauth/authorize",
        "clientId": "cid",
        "authQueryParameters": "access_type=offline&prompt=consent",
        "grantType": "authorizationCode",
    }
    url = build_oauth_authorization_url(fields, "st")
    assert "access_type=offline" in url
    assert "prompt=consent" in url


def test_build_oauth_authorization_url_adds_pkce_challenge():
    fields = {
        "authUrl": "https://example.com/oauth/authorize",
        "clientId": "cid",
        "grantType": "authorizationCode",
    }
    url = build_oauth_authorization_url(
        fields, "st", pkce_code_challenge="E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM"
    )
    assert "code_challenge=" in url
    assert "code_challenge_method=S256" in url.replace("+", " ")


def test_build_oauth_authorization_url_ignores_auth_query_override_of_pkce_challenge():
    fields = {
        "authUrl": "https://example.com/oauth/authorize",
        "clientId": "cid",
        "authQueryParameters": '{"code_challenge":"evil","code_challenge_method":"plain"}',
    }
    ch = "E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM"
    url = build_oauth_authorization_url(fields, "st", pkce_code_challenge=ch)
    assert ch in url
    assert "evil" not in url
    assert "code_challenge_method=S256" in url.replace("+", " ")


def test_build_oauth_authorization_url_ignores_reserved_keys_in_auth_query_parameters():
    evil = (
        '{"redirect_uri":"https://evil.example/cb","state":"hijack","response_type":"token",'
        '"client_id":"bad","audience":"keep"}'
    )
    fields = {
        "authUrl": "https://example.com/oauth/authorize",
        "clientId": "good-client",
        "authQueryParameters": evil,
    }
    url = build_oauth_authorization_url(fields, "legit-state")
    assert "client_id=good-client" in url
    assert "state=legit-state" in url
    assert "response_type=code" in url
    assert "evil.example" not in url
    assert "audience=keep" in url


@pytest.mark.asyncio
async def test_maybe_refresh_client_credentials(monkeypatch: pytest.MonkeyPatch):
    kind = {"key": "x", "auth_mode": "oauth2_client_credentials"}
    fields = {
        "grantType": "clientCredentials",
        "accessTokenUrl": "https://example.com/token",
        "clientId": "a",
        "clientSecret": "b",
    }

    async def fake_post(url, body, **kw):
        assert body["grant_type"] == "client_credentials"
        assert body["client_id"] == "a"
        assert body["client_secret"] == "b"
        assert kw.get("auth_basic") is None
        return {"access_token": "tok", "expires_in": 3600}

    monkeypatch.setattr(
        "analytiq_data.flows.credential_runtime._oauth_token_post",
        fake_post,
    )

    out, changed = await maybe_refresh_oauth_tokens(kind, fields)
    assert changed is True
    assert out["oauthAccessToken"] == "tok"
    assert out["oauthExpiresAt"] > time.time()


@pytest.mark.asyncio
async def test_maybe_run_pre_auth(monkeypatch: pytest.MonkeyPatch):
    kind = {
        "key": "pa",
        "pre_auth": {
            "method": "POST",
            "url": "https://example.com/login",
            "headers": {"Content-Type": "application/json"},
            "body": {"u": "x"},
            "token_json_path": "token",
            "expires_in_json_path": "ttl",
            "access_token_field": "oauthAccessToken",
            "expires_at_field": "oauthExpiresAt",
        },
    }
    fields = {"oauthAccessToken": "", "oauthExpiresAt": 0.0}

    async def fake_http(method, url, headers, body):
        return {"token": "sess", "ttl": 120}

    monkeypatch.setattr(
        "analytiq_data.flows.credential_runtime._http_pre_auth_request",
        fake_http,
    )
    monkeypatch.setattr(
        "analytiq_data.flows.url_ssrf_guard.validate_http_url_allowed_async",
        AsyncMock(return_value=None),
    )

    out, changed = await maybe_run_pre_auth(kind, fields)
    assert changed is True
    assert out["oauthAccessToken"] == "sess"


@pytest.mark.asyncio
async def test_apply_runtime_skips_persist_when_unchanged(monkeypatch: pytest.MonkeyPatch):
    kind = {"key": "plain", "auth_mode": "api_key"}
    fields = {"name": "Authorization", "value": "x"}

    persist = AsyncMock()
    monkeypatch.setattr(
        "analytiq_data.flows.credential_runtime.persist_credential_fields",
        persist,
    )

    out = await apply_runtime_credential_updates("org", "507f1f77bcf86cd799439011", kind, fields)
    assert out == fields
    persist.assert_not_called()


@pytest.mark.asyncio
async def test_exchange_authorization_code_uses_basic_auth_when_authentication_header(
    monkeypatch: pytest.MonkeyPatch,
):
    captured: dict = {}

    async def fake_post(url, body, **kw):
        captured["body"] = body
        captured["auth_basic"] = kw.get("auth_basic")
        return {"access_token": "tok", "expires_in": 3600}

    monkeypatch.setattr(
        "analytiq_data.flows.credential_runtime._oauth_token_post",
        fake_post,
    )
    monkeypatch.setattr(
        "analytiq_data.flows.credential_runtime.persist_credential_fields",
        AsyncMock(),
    )

    fields = {
        "accessTokenUrl": "https://example.com/token",
        "clientId": " id ",
        "clientSecret": " secret ",
        "authentication": "header",
    }
    await exchange_authorization_code("org", "507f1f77bcf86cd799439011", fields, "code")
    assert "client_id" not in captured["body"]
    assert "client_secret" not in captured["body"]
    assert captured["auth_basic"] == ("id", "secret")


@pytest.mark.asyncio
async def test_exchange_authorization_code_raises_when_access_token_missing(monkeypatch: pytest.MonkeyPatch):
    async def fake_post(url, body, **kw):
        return {"error": "invalid_grant", "error_description": "Code expired"}

    monkeypatch.setattr(
        "analytiq_data.flows.credential_runtime._oauth_token_post",
        fake_post,
    )
    persist = AsyncMock()
    monkeypatch.setattr(
        "analytiq_data.flows.credential_runtime.persist_credential_fields",
        persist,
    )

    fields = {
        "accessTokenUrl": "https://example.com/token",
        "clientId": "a",
        "clientSecret": "b",
        "authentication": "body",
    }
    with pytest.raises(RuntimeError, match="missing access_token"):
        await exchange_authorization_code(
            "org", "507f1f77bcf86cd799439011", fields, "auth-code"
        )
    persist.assert_not_called()


@pytest.mark.asyncio
async def test_exchange_authorization_code_persists_when_access_token_present(
    monkeypatch: pytest.MonkeyPatch,
):
    async def fake_post(url, body, **kw):
        return {"access_token": "atok", "refresh_token": "rtok", "expires_in": 120}

    monkeypatch.setattr(
        "analytiq_data.flows.credential_runtime._oauth_token_post",
        fake_post,
    )
    persist = AsyncMock()
    monkeypatch.setattr(
        "analytiq_data.flows.credential_runtime.persist_credential_fields",
        persist,
    )

    fields = {
        "accessTokenUrl": "https://example.com/token",
        "clientId": "a",
        "clientSecret": "b",
        "authentication": "body",
    }
    out = await exchange_authorization_code(
        "org", "507f1f77bcf86cd799439011", fields, "auth-code"
    )
    assert out["oauthAccessToken"] == "atok"
    assert out["oauthRefreshToken"] == "rtok"
    persist.assert_called_once()


@pytest.mark.asyncio
async def test_exchange_authorization_code_includes_pkce_verifier(monkeypatch: pytest.MonkeyPatch):
    captured: dict[str, dict[str, str]] = {}

    async def fake_post(url, body, **kw):
        captured["body"] = dict(body)
        return {"access_token": "atok"}

    monkeypatch.setattr(
        "analytiq_data.flows.credential_runtime._oauth_token_post",
        fake_post,
    )
    monkeypatch.setattr(
        "analytiq_data.flows.credential_runtime.persist_credential_fields",
        AsyncMock(),
    )

    fields = {
        "accessTokenUrl": "https://example.com/token",
        "clientId": "a",
        "clientSecret": "b",
    }
    await exchange_authorization_code(
        "org",
        "507f1f77bcf86cd799439011",
        fields,
        "auth-code",
        pkce_verifier="pkce-verifier-value",
    )
    assert captured["body"].get("code_verifier") == "pkce-verifier-value"


@pytest.mark.asyncio
async def test_exchange_authorization_code_omits_pkce_when_not_used(monkeypatch: pytest.MonkeyPatch):
    captured: dict[str, dict[str, str]] = {}

    async def fake_post(url, body, **kw):
        captured["body"] = dict(body)
        return {"access_token": "atok"}

    monkeypatch.setattr(
        "analytiq_data.flows.credential_runtime._oauth_token_post",
        fake_post,
    )
    monkeypatch.setattr(
        "analytiq_data.flows.credential_runtime.persist_credential_fields",
        AsyncMock(),
    )

    fields = {
        "accessTokenUrl": "https://example.com/token",
        "clientId": "a",
        "clientSecret": "b",
    }
    await exchange_authorization_code(
        "org", "507f1f77bcf86cd799439011", fields, "auth-code"
    )
    assert "code_verifier" not in captured["body"]
