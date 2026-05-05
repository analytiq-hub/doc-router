"""Tests for ported node UI hints mapped to JSON Schema (`x-ui-*`) in `flows/port/schema.py`."""

from __future__ import annotations

from analytiq_data.flows.port.schema import inode_property_to_schema


def test_placeholder_to_x_display_placeholder() -> None:
    sch = inode_property_to_schema({"name": "url", "type": "string", "placeholder": " https:// "})
    assert sch["x-ui-placeholder"] == "https://"


def test_code_type_sets_x_display_ui() -> None:
    sch = inode_property_to_schema({"name": "jsCode", "type": "code"})
    assert sch["type"] == "string"
    assert sch["x-ui-widget"] == "code"


def test_display_options_show_single_field_maps_to_show_when() -> None:
    sch = inode_property_to_schema(
        {
            "name": "text",
            "type": "string",
            "displayOptions": {"show": {"resource": ["message"]}},
        }
    )
    assert sch["x-ui-show-when"] == {"field": "resource", "in": ["message"]}


def test_display_options_multi_field_show_not_mapped() -> None:
    sch = inode_property_to_schema(
        {
            "name": "z",
            "type": "string",
            "displayOptions": {"show": {"resource": ["a"], "operation": ["b"]}},
        }
    )
    assert "x-ui-show-when" not in sch
