"""Credential kind fields exposed to the UI (runtime fields hidden)."""

from __future__ import annotations

from analytiq_data.flows.credential_kind_registry import (
    _credential_kinds_bundle,
    credential_runtime_field_names,
    get_credential_kind,
)


def test_gmail_scope_is_runtime_hidden_but_schema_default() -> None:
    """Gmail scope: in properties for defaults (like google grantType), hidden from UI via runtime_fields."""
    _credential_kinds_bundle.cache_clear()
    try:
        kind = get_credential_kind("gmailOAuth2")
        runtime = credential_runtime_field_names(kind)
        props = (kind.get("secret_schema") or {}).get("properties") or {}
        assert "scope" in runtime
        assert "scope" in props
        assert props["scope"].get("default")
    finally:
        _credential_kinds_bundle.cache_clear()


def test_google_oauth_kinds_hide_ignore_ssl_issues() -> None:
    """Google stack: ignoreSSLIssues stays false via schema default, not shown in UI."""
    _credential_kinds_bundle.cache_clear()
    try:
        for key in ("googleOAuth2Api", "gmailOAuth2"):
            kind = get_credential_kind(key)
            props = (kind.get("secret_schema") or {}).get("properties") or {}
            assert props["ignoreSSLIssues"].get("default") is False
            assert props["ignoreSSLIssues"].get("x-ui-hidden") is True
    finally:
        _credential_kinds_bundle.cache_clear()


def test_oauth_kinds_include_http_domain_restriction_fields() -> None:
    _credential_kinds_bundle.cache_clear()
    try:
        for key in ("oAuth2Api", "gmailOAuth2"):
            kind = get_credential_kind(key)
            props = (kind.get("secret_schema") or {}).get("properties") or {}
            assert props["allowedHttpRequestDomains"]["enum"] == ["all", "domains", "none"]
            assert props["allowedDomains"]["x-ui-show-when"] == {
                "field": "allowedHttpRequestDomains",
                "equals": "domains",
            }
    finally:
        _credential_kinds_bundle.cache_clear()


def test_gmail_oauth_tokens_are_runtime_not_form_fields() -> None:
    _credential_kinds_bundle.cache_clear()
    try:
        kind = get_credential_kind("gmailOAuth2")
        runtime = credential_runtime_field_names(kind)
        assert "oauthAccessToken" in runtime
        assert "oauthRefreshToken" in runtime
        assert "oauthExpiresAt" in runtime
        props = (kind.get("secret_schema") or {}).get("properties") or {}
        assert "oauthAccessToken" not in props
        assert "oauthRefreshToken" not in props
        assert "oauthExpiresAt" not in props
        assert "clientId" in props
        assert "clientSecret" in props
    finally:
        _credential_kinds_bundle.cache_clear()
