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
