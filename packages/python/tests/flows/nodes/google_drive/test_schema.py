from __future__ import annotations

from typing import Any

from analytiq_data.flows.nodes.google_drive.schema_builder import build_google_drive_parameter_schema


def test_parameter_schema_merges_operations(drive_schema: dict[str, Any]) -> None:
    op = drive_schema["properties"]["operation"]
    assert "x-ui-enum-by" in op
    assert "upload" in op["enum"]
    assert "search" in op["enum"]
    keys = list(drive_schema["properties"].keys())
    assert keys.index("fileId") < keys.index("options")
    assert drive_schema["properties"]["fileId"]["title"] == "File"
    assert "file id" in drive_schema["properties"]["fileId"]["description"].lower()


def test_schema_builder_orders_resource_operation_first() -> None:
    description = {
        "properties": [
            {"name": "options", "type": "collection", "default": {}},
            {
                "name": "resource",
                "type": "options",
                "options": [{"name": "File", "value": "file"}],
                "default": "file",
            },
            {
                "name": "operation",
                "type": "options",
                "displayOptions": {"show": {"resource": ["file"]}},
                "options": [{"name": "Upload", "value": "upload"}],
                "default": "upload",
            },
            {"name": "fileId", "type": "string"},
        ]
    }
    schema = build_google_drive_parameter_schema(description)
    prop_keys = list(schema["properties"].keys())
    assert prop_keys[:2] == ["resource", "operation"]
    assert prop_keys.index("fileId") < prop_keys.index("options")
    assert schema["properties"]["operation"]["default"] == "upload"
