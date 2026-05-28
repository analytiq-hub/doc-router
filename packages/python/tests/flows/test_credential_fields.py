"""Credential field coercion before JSON Schema validation."""

from __future__ import annotations

import pytest

from analytiq_data.flows.credential_fields import (
    apply_credential_kind_defaults,
    coerce_credential_fields,
    credential_validation_schema,
)
from analytiq_data.flows.credential_kind_registry import (
    _credential_kinds_bundle,
    get_credential_kind,
)


def test_coerce_empty_string_boolean_to_default() -> None:
    schema = {
        "type": "object",
        "properties": {
            "ignoreSSLIssues": {"type": "boolean", "default": False},
        },
    }
    out = coerce_credential_fields(schema, {"ignoreSSLIssues": "", "clientId": "x"})
    assert out["ignoreSSLIssues"] is False
    assert out["clientId"] == "x"


def test_coerce_string_boolean_literals() -> None:
    schema = {
        "type": "object",
        "properties": {"flag": {"type": "boolean"}},
    }
    assert coerce_credential_fields(schema, {"flag": "true"})["flag"] is True
    assert coerce_credential_fields(schema, {"flag": "false"})["flag"] is False


def test_coerce_empty_number_to_default() -> None:
    schema = {
        "type": "object",
        "properties": {"oauthExpiresAt": {"type": "number", "default": 0}},
    }
    out = coerce_credential_fields(schema, {"oauthExpiresAt": ""})
    assert out["oauthExpiresAt"] == 0


def test_merge_keeps_secret_when_incoming_empty() -> None:
    from analytiq_data.flows.credential_fields import merge_credential_fields_update

    existing = {"clientId": "id", "clientSecret": "sekrit", "scope": "read"}
    incoming = {"clientId": "id2", "clientSecret": "", "scope": "read write"}
    merged = merge_credential_fields_update(
        existing, incoming, frozenset({"clientSecret"})
    )
    assert merged["clientSecret"] == "sekrit"
    assert merged["clientId"] == "id2"
    assert merged["scope"] == "read write"


def test_apply_defaults_fills_google_oauth_urls() -> None:
    _credential_kinds_bundle.cache_clear()
    try:
        kind = get_credential_kind("gmailOAuth2")
        fields = apply_credential_kind_defaults(
            kind,
            {
                "clientId": "cid",
                "clientSecret": "sec",
                "ignoreSSLIssues": False,
            },
        )
        assert fields["authUrl"] == "https://accounts.google.com/o/oauth2/v2/auth"
        assert fields["accessTokenUrl"] == "https://oauth2.googleapis.com/token"
        assert fields.get("grantType") == "authorizationCode"
        schema = credential_validation_schema(kind)
        assert schema is not None
        from jsonschema import Draft7Validator

        Draft7Validator(schema).validate(fields)
    finally:
        _credential_kinds_bundle.cache_clear()


def test_raw_kind_schema_rejects_oauth_tokens_validation_schema_allows() -> None:
    """Stored payloads after OAuth: raw schema fails; credential_validation_schema passes."""
    _credential_kinds_bundle.cache_clear()
    try:
        from jsonschema import Draft7Validator

        kind = get_credential_kind("gmailOAuth2")
        raw = kind.get("secret_schema")
        assert raw is not None
        fields = apply_credential_kind_defaults(
            kind,
            {
                "clientId": "c",
                "clientSecret": "s",
                "oauthAccessToken": "tok",
                "oauthRefreshToken": "rt",
            },
        )
        with pytest.raises(Exception):
            Draft7Validator(raw).validate(fields)
        val_schema = credential_validation_schema(kind)
        assert val_schema is not None
        Draft7Validator(val_schema).validate(fields)
    finally:
        _credential_kinds_bundle.cache_clear()


def test_validation_schema_allows_stored_oauth_runtime_fields() -> None:
    _credential_kinds_bundle.cache_clear()
    try:
        kind = get_credential_kind("gmailOAuth2")
        schema = credential_validation_schema(kind)
        assert schema is not None
        from jsonschema import Draft7Validator

        fields = apply_credential_kind_defaults(
            kind,
            {
                "clientId": "cid",
                "clientSecret": "sec",
                "ignoreSSLIssues": False,
                "oauthAccessToken": "access-tok",
                "oauthRefreshToken": "refresh-tok",
                "oauthExpiresAt": 1_700_000_000.0,
            },
        )
        Draft7Validator(schema).validate(fields)
    finally:
        _credential_kinds_bundle.cache_clear()


def test_apply_defaults_fills_microsoft_oauth_urls_and_onedrive_scope() -> None:
    _credential_kinds_bundle.cache_clear()
    try:
        kind = get_credential_kind("microsoftOneDriveOAuth2Api")
        fields = apply_credential_kind_defaults(
            kind,
            {"clientId": "cid", "clientSecret": "sec"},
        )
        assert fields["authUrl"] == (
            "https://login.microsoftonline.com/common/oauth2/v2.0/authorize"
        )
        assert fields["accessTokenUrl"] == (
            "https://login.microsoftonline.com/common/oauth2/v2.0/token"
        )
        assert fields.get("grantType") == "authorizationCode"
        assert "Files.ReadWrite.All" in (fields.get("scope") or "")
    finally:
        _credential_kinds_bundle.cache_clear()


def test_apply_defaults_fills_microsoft_oauth_urls_and_outlook_scope() -> None:
    _credential_kinds_bundle.cache_clear()
    try:
        kind = get_credential_kind("microsoftOutlookOAuth2Api")
        fields = apply_credential_kind_defaults(
            kind,
            {"clientId": "cid", "clientSecret": "sec"},
        )
        assert fields["authUrl"] == (
            "https://login.microsoftonline.com/common/oauth2/v2.0/authorize"
        )
        assert fields["accessTokenUrl"] == (
            "https://login.microsoftonline.com/common/oauth2/v2.0/token"
        )
        assert fields.get("grantType") == "authorizationCode"
        assert fields.get("authQueryParameters") == "response_mode=query"
        assert "Mail.ReadWrite" in (fields.get("scope") or "")
    finally:
        _credential_kinds_bundle.cache_clear()


def test_resolve_credential_scope_substitutes_sharepoint_subdomain() -> None:
    from analytiq_data.flows.credential_runtime import (
        build_oauth_authorization_url,
        require_resolved_oauth_scope,
        resolve_credential_scope,
    )

    _credential_kinds_bundle.cache_clear()
    try:
        kind = get_credential_kind("microsoftSharePointOAuth2Api")
        fields = apply_credential_kind_defaults(
            kind,
            {"clientId": "cid", "clientSecret": "sec", "subdomain": "contoso"},
        )
        scope = resolve_credential_scope(fields)
        assert scope == "openid offline_access https://contoso.sharepoint.com/.default"
        require_resolved_oauth_scope(fields)
        url = build_oauth_authorization_url(fields, "state-xyz")
        assert "scope=" in url
        assert "contoso.sharepoint.com" in url
    finally:
        _credential_kinds_bundle.cache_clear()


def test_resolve_credential_scope_substitutes_dynamics_subdomain_and_region() -> None:
    from analytiq_data.flows.credential_runtime import (
        resolve_credential_scope,
        require_resolved_oauth_scope,
    )

    _credential_kinds_bundle.cache_clear()
    try:
        kind = get_credential_kind("microsoftDynamicsOAuth2Api")
        fields = apply_credential_kind_defaults(
            kind,
            {
                "clientId": "cid",
                "clientSecret": "sec",
                "subdomain": "myorg",
                "region": "crm.dynamics.com",
            },
        )
        scope = resolve_credential_scope(fields)
        assert scope == "openid offline_access https://myorg.crm.dynamics.com/.default"
        require_resolved_oauth_scope(fields)
    finally:
        _credential_kinds_bundle.cache_clear()


def test_require_resolved_oauth_scope_rejects_missing_sharepoint_subdomain() -> None:
    from analytiq_data.flows.credential_runtime import require_resolved_oauth_scope

    _credential_kinds_bundle.cache_clear()
    try:
        kind = get_credential_kind("microsoftSharePointOAuth2Api")
        fields = apply_credential_kind_defaults(
            kind,
            {"clientId": "cid", "clientSecret": "sec"},
        )
        with pytest.raises(RuntimeError, match="subdomain"):
            require_resolved_oauth_scope(fields)
    finally:
        _credential_kinds_bundle.cache_clear()


def test_microsoft_oauth_urls_are_editable_in_form() -> None:
    """Match n8n: Authorization URL and Access Token URL are user-visible, not runtime-hidden."""
    _credential_kinds_bundle.cache_clear()
    try:
        from analytiq_data.flows.credential_kind_registry import credential_runtime_field_names

        kind = get_credential_kind("microsoftOutlookOAuth2Api")
        runtime = credential_runtime_field_names(kind)
        props = (kind.get("secret_schema") or {}).get("properties") or {}
        assert "authUrl" not in runtime
        assert "accessTokenUrl" not in runtime
        assert "grantType" in runtime
        assert props["authUrl"]["default"] == (
            "https://login.microsoftonline.com/common/oauth2/v2.0/authorize"
        )
        assert props["accessTokenUrl"]["default"] == (
            "https://login.microsoftonline.com/common/oauth2/v2.0/token"
        )
    finally:
        _credential_kinds_bundle.cache_clear()


def test_microsoft_single_tenant_urls_used_in_authorize() -> None:
    """User replaces ``common`` with tenant GUID in URL fields (n8n pattern)."""
    _credential_kinds_bundle.cache_clear()
    try:
        from analytiq_data.flows.credential_runtime import build_oauth_authorization_url

        tenant = "982791fc-875f-48eb-ad38-9a868528c19b"
        fields = apply_credential_kind_defaults(
            get_credential_kind("microsoftOutlookOAuth2Api"),
            {
                "clientId": "cid",
                "clientSecret": "sec",
                "authUrl": f"https://login.microsoftonline.com/{tenant}/oauth2/v2.0/authorize",
                "accessTokenUrl": f"https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token",
            },
        )
        url = build_oauth_authorization_url(fields, "state-xyz")
        assert tenant in url
        assert "/common/" not in url
    finally:
        _credential_kinds_bundle.cache_clear()


def test_microsoft_product_kinds_have_test_request_and_experimental() -> None:
    _credential_kinds_bundle.cache_clear()
    try:
        for key in (
            "microsoftOutlookOAuth2Api",
            "microsoftOneDriveOAuth2Api",
            "microsoftTeamsOAuth2Api",
            "microsoftExcelOAuth2Api",
            "microsoftSharePointOAuth2Api",
            "microsoftDynamicsOAuth2Api",
        ):
            kind = get_credential_kind(key)
            assert kind.get("experimental") is True
            assert isinstance(kind.get("test_request"), dict)
            assert kind["test_request"].get("url")
            props = (kind.get("secret_schema") or {}).get("properties") or {}
            assert "scope" in props
            assert props["scope"].get("default")
    finally:
        _credential_kinds_bundle.cache_clear()
