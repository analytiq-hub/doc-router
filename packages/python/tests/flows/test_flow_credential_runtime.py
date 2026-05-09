"""Tests for OAuth/pre-auth credential runtime (``credential_runtime.py``)."""

from __future__ import annotations

import os
import time
from unittest.mock import AsyncMock, patch

import pytest

os.environ.setdefault("NEXTAUTH_SECRET", "test-secret-for-credential-runtime-tests")

import analytiq_data as ad
from analytiq_data.flows.credential_runtime import (
    apply_runtime_credential_updates,
    build_oauth_authorization_url,
    decode_flow_oauth_state,
    encode_flow_oauth_state,
    maybe_refresh_oauth_tokens,
    maybe_run_pre_auth,
)


def test_oauth_state_roundtrip():
    t = encode_flow_oauth_state("orgA", "cid1", "user1", ttl_seconds=60)
    payload = decode_flow_oauth_state(t)
    assert payload["org"] == "orgA"
    assert payload["cid"] == "cid1"
    assert payload["uid"] == "user1"


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
