"""Gmail parameter schema UI ordering and visibility."""

from __future__ import annotations

from analytiq_data.flows.nodes.gmail.node import FlowsGmailNode


def test_message_id_field_precedes_options_in_schema_order() -> None:
    keys = list(FlowsGmailNode.parameter_schema["properties"].keys())
    assert keys.index("messageId") == 2
    assert keys.index("messageId") < keys.index("options")
    assert keys[-1] == "options"


def test_get_controls_precede_options_in_schema_order() -> None:
    keys = list(FlowsGmailNode.parameter_schema["properties"].keys())
    options_idx = keys.index("options")
    for key in ("simple", "returnAll", "limit", "filters"):
        assert keys.index(key) < options_idx


def test_message_resource_includes_get_all_operation() -> None:
    op = FlowsGmailNode.parameter_schema["properties"]["operation"]
    message_ops = op["x-ui-enum-by"]["variants"]["message"]["enum"]
    assert "get" in message_ops
    assert "getAll" in message_ops
