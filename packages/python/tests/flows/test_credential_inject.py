"""Unit tests for credential inject helpers exposed via ``ad.flows``."""

from __future__ import annotations

import pytest

import analytiq_data as ad


def test_render_skips_empty_bearer_header() -> None:
    kind = {
        "inject": {
            "headers": {
                "Authorization": "Bearer {{ credentials.oauthAccessToken }}",
            }
        }
    }
    out = ad.flows.render_credential_inject(kind, {"oauthAccessToken": ""})
    assert out["headers"] == {}


def test_render_dynamic_header_keys() -> None:
    kind = {
        "inject": {
            "headers": {
                "{{ credentials.name }}": "{{ credentials.value }}",
            }
        }
    }
    out = ad.flows.render_credential_inject(
        kind, {"name": "Authorization", "value": "Bearer x"}
    )
    assert out["headers"]["Authorization"] == "Bearer x"


def test_render_inject_body() -> None:
    kind = {
        "inject": {
            "body": {"access_token": "{{ credentials.access_token }}"}
        }
    }
    rend = ad.flows.render_credential_inject(kind, {"access_token": "abc"})
    assert ad.flows.inject_body_as_json(rend["body"]) == {"access_token": "abc"}


@pytest.mark.parametrize(
    "raw,expect",
    [
        ('{"a": 1}', {"a": 1}),
        ("42", 42),
        ("plain", "plain"),
        ("", ""),
    ],
)
def test_coerce_template_json_value(raw: str, expect: object) -> None:
    assert ad.flows.coerce_template_json_value(raw) == expect
