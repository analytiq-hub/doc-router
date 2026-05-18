"""Credential field coercion before JSON Schema validation."""

from __future__ import annotations

from analytiq_data.flows.credential_fields import coerce_credential_fields


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
