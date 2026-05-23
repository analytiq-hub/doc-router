"""Tests for flow-level settings (timezone)."""

from __future__ import annotations

import pytest

import analytiq_data as ad


def test_resolve_flow_timezone_default_and_missing() -> None:
    assert ad.flows.resolve_flow_timezone({}) == ad.flows.INSTANCE_DEFAULT_TIMEZONE
    assert ad.flows.resolve_flow_timezone({"timezone": "DEFAULT"}) == ad.flows.INSTANCE_DEFAULT_TIMEZONE
    assert ad.flows.resolve_flow_timezone({"timezone": ""}) == ad.flows.INSTANCE_DEFAULT_TIMEZONE


def test_resolve_flow_timezone_iana() -> None:
    assert ad.flows.resolve_flow_timezone({"timezone": "America/New_York"}) == "America/New_York"


def test_validate_flow_settings_rejects_unknown_timezone() -> None:
    errs = ad.flows.validate_flow_settings({"timezone": "Not/A/Zone"})
    assert len(errs) == 1
    assert "Invalid flow timezone" in errs[0]


def test_validate_flow_settings_accepts_default_and_iana() -> None:
    assert ad.flows.validate_flow_settings({}) == []
    assert ad.flows.validate_flow_settings({"timezone": "DEFAULT"}) == []
    assert ad.flows.validate_flow_settings({"timezone": "Europe/Berlin"}) == []


@pytest.fixture(autouse=True)
def _register_nodes() -> None:
    ad.flows.register_builtin_nodes()


def test_validate_revision_rejects_invalid_flow_timezone() -> None:
    nodes = [
        {
            "id": "t1",
            "name": "Schedule",
            "type": "flows.trigger.schedule",
            "position": [0, 0],
            "parameters": {"rule": {"interval": [{"field": "hours", "hoursInterval": 1}]}},
            "webhook_id": None,
            "disabled": False,
            "on_error": "stop",
            "retry_on_fail": False,
            "max_tries": 1,
            "wait_between_tries_ms": 1000,
            "notes": None,
        },
    ]
    with pytest.raises(ad.flows.FlowValidationError, match="Invalid flow timezone"):
        ad.flows.validate_revision(nodes, {}, {"timezone": "Bad/Zone"}, None)
