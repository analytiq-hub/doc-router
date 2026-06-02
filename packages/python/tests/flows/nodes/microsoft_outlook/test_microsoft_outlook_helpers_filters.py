"""Shared OData filter helpers for trigger vs action message list."""

from __future__ import annotations

from analytiq_data.flows.nodes.microsoft_outlook.helpers import (
    prepare_filter_string,
    prepare_trigger_filters,
)


def test_prepare_trigger_filters_has_attachments_string_false() -> None:
    filt = prepare_trigger_filters({"hasAttachments": "false"})
    assert filt is not None
    assert "hasAttachments eq false" in filt
    assert "hasAttachments eq true" not in filt


def test_prepare_filter_string_has_attachments_string_false() -> None:
    filt = prepare_filter_string(
        {
            "values": {
                "filterBy": "filters",
                "filters": {"hasAttachments": "false", "readStatus": "both"},
            }
        }
    )
    assert filt is not None
    assert "hasAttachments eq false" in filt
    assert "hasAttachments eq true" not in filt


def test_trigger_and_action_filters_share_has_attachments_clause() -> None:
    trigger = prepare_trigger_filters({"hasAttachments": "true", "sender": "x@y.z"})
    action = prepare_filter_string(
        {"values": {"filters": {"hasAttachments": "true", "sender": "x@y.z"}}}
    )
    assert trigger is not None and action is not None
    assert "hasAttachments eq true" in trigger
    assert "hasAttachments eq true" in action
    assert trigger.split(" and ")[0] == action.split(" and ")[0]  # sender clause first
