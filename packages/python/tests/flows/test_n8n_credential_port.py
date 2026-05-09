"""Tests for ``analytiq_data.flows.n8n_credential_port``."""

from __future__ import annotations

import json

import pytest

import analytiq_data as ad
from analytiq_data.flows.n8n_credential_port import (
    convert_n8n_template,
    map_authenticate_generic,
    map_test_request,
    port_record_to_kind,
)


def test_convert_n8n_template_header_style() -> None:
    assert convert_n8n_template("={{$credentials.name}}") == "{{ credentials.name }}"


def test_convert_n8n_template_bearer_slack() -> None:
    assert convert_n8n_template("=Bearer {{$credentials.accessToken}}") == "Bearer {{ credentials.accessToken }}"


def test_map_authenticate_headers() -> None:
    auth = {
        "type": "generic",
        "properties": {
            "headers": {
                "Authorization": "=Bearer {{$credentials.accessToken}}",
            }
        },
    }
    inj = map_authenticate_generic(auth)
    assert inj is not None
    assert inj["headers"]["Authorization"] == "=Bearer {{$credentials.accessToken}}"
    # templating applied by caller
    from analytiq_data.flows.n8n_credential_port import _template_mapping

    m = _template_mapping(inj)
    assert "Bearer {{ credentials.accessToken }}" in m["headers"]["Authorization"]


def test_map_test_request_concat() -> None:
    tr = map_test_request(
        {"request": {"baseURL": "https://slack.com", "url": "/api/users.profile.get", "method": "get"}}
    )
    assert tr == {"method": "GET", "url": "https://slack.com/api/users.profile.get"}


def test_port_http_header_style_record() -> None:
    record = {
        "name": "httpHeaderAuth",
        "displayName": "Header Auth",
        "properties": [
            {"displayName": "Name", "name": "name", "type": "string", "default": ""},
            {
                "displayName": "Value",
                "name": "value",
                "type": "string",
                "typeOptions": {"password": True},
                "default": "",
            },
        ],
        "authenticate": {
            "type": "generic",
            "properties": {
                "headers": {"={{$credentials.name}}": "={{$credentials.value}}"},
            },
        },
    }
    kind, err = port_record_to_kind(record)
    assert err is None
    assert kind is not None
    assert kind["key"] == "httpHeaderAuth"
    assert kind["inject"]["headers"]["{{ credentials.name }}"] == "{{ credentials.value }}"


def test_options_enum_gap7() -> None:
    record = {
        "name": "grantProbe",
        "displayName": "Grant Probe",
        "properties": [
            {
                "displayName": "Mode",
                "name": "mode",
                "type": "options",
                "options": [{"name": "A", "value": "a"}, {"name": "B", "value": "b"}],
                "default": "a",
            }
        ],
    }
    kind, err = port_record_to_kind(record)
    assert err is None
    assert kind is not None
    props = kind["secret_schema"]["properties"]["mode"]
    assert props.get("enum") == ["a", "b"]


def test_hidden_runtime_fields_gap8() -> None:
    record = {
        "name": "hiddenProbe",
        "displayName": "Hidden Probe",
        "properties": [
            {"displayName": "Secret", "name": "secretField", "type": "hidden", "default": "x"},
        ],
    }
    kind, err = port_record_to_kind(record)
    assert err is None
    assert kind is not None
    assert "secretField" in kind.get("runtime_fields", [])
    assert "secretField" not in kind["secret_schema"]["properties"]


def test_kind_registry_extends_merge_slack_oauth(tmp_path) -> None:
    """Resolve Slack OAuth2 child merged with parent OAuth2Api (minimal fixtures)."""

    import analytiq_data.flows.credential_kind_registry as reg

    root = tmp_path / "schemas" / "credential-kinds"
    root.mkdir(parents=True)

    parent = {
        "key": "oAuth2Api",
        "display_name": "OAuth2 API",
        "auth_mode": "oauth2_authorization_code",
        "secret_schema": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "clientId": {"type": "string", "title": "Client ID"},
                "clientSecret": {"type": "string", "title": "Secret", "x-secret": True},
            },
            "required": ["clientId", "clientSecret"],
        },
    }
    child = {
        "key": "slackOAuth2Api",
        "display_name": "Slack OAuth2 API",
        "extends": ["oAuth2Api"],
        "auth_mode": "oauth2_authorization_code",
        "secret_schema": {
            "type": "object",
            "additionalProperties": False,
            "properties": {},
            "required": [],
        },
        "runtime_fields": ["grantType", "authUrl"],
    }
    (root / "oAuth2Api.json").write_text(json.dumps(parent), encoding="utf-8")
    (root / "slackOAuth2Api.json").write_text(json.dumps(child), encoding="utf-8")

    orig_repo_root = reg._repo_root
    reg._repo_root = lambda: tmp_path  # type: ignore[method-assign, assignment]
    reg._loaded_kinds.cache_clear()
    try:
        merged = ad.flows.get_credential_kind("slackOAuth2Api")
        assert merged["display_name"] == "Slack OAuth2 API"
        props = merged["secret_schema"]["properties"]
        assert "clientId" in props and "clientSecret" in props
        assert merged.get("runtime_fields") == ["grantType", "authUrl"]
        assert "extends" not in merged
    finally:
        reg._repo_root = orig_repo_root  # type: ignore[method-assign, assignment]
        reg._loaded_kinds.cache_clear()
