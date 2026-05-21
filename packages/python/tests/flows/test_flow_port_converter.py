from __future__ import annotations

import json
from pathlib import Path

import pytest

from analytiq_data.flows.port.converter import emit_node_package, iter_flow_node_dump_rows, manifest_key
from analytiq_data.flows.port.schema import build_top_level_parameter_schema


def test_iter_flow_node_dump_rows_legacy_one_object_per_line() -> None:
    text = '{"x": 1}\n{"x": 2}\n'
    assert list(iter_flow_node_dump_rows(text)) == [{"x": 1}, {"x": 2}]


def test_iter_flow_node_dump_rows_pretty_printed_blocks() -> None:
    text = '{\n  "x": 1\n}\n\n{\n  "x": 2\n}\n\n'
    assert list(iter_flow_node_dump_rows(text)) == [{"x": 1}, {"x": 2}]


def test_display_options_multi_field_show_maps_to_all() -> None:
    desc = {
        "properties": [
            {
                "name": "inputDataFieldName",
                "type": "string",
                "displayOptions": {
                    "show": {
                        "resource": ["file"],
                        "operation": ["upload"],
                    }
                },
            }
        ]
    }
    schema = build_top_level_parameter_schema(desc)
    sw = schema["properties"]["inputDataFieldName"]["x-ui-show-when"]
    assert sw == {
        "all": [
            {"field": "resource", "equals": "file"},
            {"field": "operation", "equals": "upload"},
        ]
    }


def test_merge_duplicate_operation_options_by_resource() -> None:
    desc = {
        "properties": [
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
            {
                "name": "operation",
                "type": "options",
                "displayOptions": {"show": {"resource": ["folder"]}},
                "options": [{"name": "Create", "value": "create"}],
                "default": "create",
            },
        ]
    }
    schema = build_top_level_parameter_schema(desc)
    op = schema["properties"]["operation"]
    assert "upload" in op["enum"]
    assert "create" in op["enum"]
    assert op["x-ui-enum-by"]["variants"]["file"]["enum"] == ["upload"]
    assert op["x-ui-enum-by"]["variants"]["folder"]["enum"] == ["create"]


def test_manifest_key_slug() -> None:
    d = {"name": "slack", "displayName": "Slack"}
    assert manifest_key(d) == "ext.slack"


def test_declarative_emits_http_spec(tmp_path: Path) -> None:
    row = {
        "source": "packages/nodes-base/dist/nodes/Slack/Slack.node.js",
        "description": {
            "name": "slack",
            "displayName": "Slack",
            "description": "Slack API",
            "group": ["output"],
            "version": 1,
            "inputs": ["main"],
            "outputs": ["main"],
            "requestDefaults": {
                "baseURL": "https://slack.com/api/",
                "headers": {},
            },
            "properties": [
                {
                    "name": "resource",
                    "type": "string",
                    "default": "message",
                },
                {
                    "name": "text",
                    "type": "string",
                    "routing": {
                        "request": {
                            "method": "POST",
                            "url": "chat.postMessage",
                        },
                        "output": {},
                    },
                },
            ],
        },
    }
    warnings: list[str] = []
    pkg = emit_node_package(row, tmp_path, warnings, {})
    mf = json.loads((pkg / "node.manifest.json").read_text(encoding="utf-8"))
    assert mf["executor"]["kind"] == "declarative"
    assert mf["executor"]["runtime"] == "http_request_v1"
    assert (pkg / "http.spec.json").is_file()
    http = json.loads((pkg / "http.spec.json").read_text(encoding="utf-8"))
    assert http["method"] == "POST"
    assert "slack.com" in http["url"] and "chat.postMessage" in http["url"]
    assert not (pkg / "node_impl.py").is_file()


def test_python_class_stub(tmp_path: Path) -> None:
    row = {
        "source": "packages/nodes-base/dist/nodes/Postgres/Postgres.node.js",
        "description": {
            "name": "postgres",
            "displayName": "Postgres",
            "description": "PostgreSQL",
            "group": ["input"],
            "inputs": ["main"],
            "outputs": ["main"],
            "properties": [{"name": "query", "type": "string"}],
        },
    }
    pkg = emit_node_package(row, tmp_path, [], {})
    mf = json.loads((pkg / "node.manifest.json").read_text(encoding="utf-8"))
    assert mf["executor"]["kind"] == "python_class"
    stub = (pkg / "node_impl.py").read_text(encoding="utf-8")
    assert "class ExtPostgresNode" in stub
    assert "key = 'ext.postgres'" in stub or 'key = "ext.postgres"' in stub


@pytest.mark.skipif(
    not Path(__file__).resolve().parents[3].joinpath(
        "schemas", "flow-node-manifest-v1.json"
    ).is_file(),
    reason="schemas/ not at repo root",
)
def test_validate_generated_against_manifest_schema(tmp_path: Path) -> None:
    from analytiq_data.flows.port.converter import validate_packages

    row = {
        "source": "x/Minimal.node.js",
        "description": {
            "name": "minimal",
            "displayName": "Minimal",
            "description": "Test",
            "group": ["transform"],
            "inputs": ["main"],
            "outputs": ["main"],
            "requestDefaults": {"baseURL": "https://example.com/", "headers": {}},
            "properties": [
                {
                    "name": "trigger",
                    "type": "string",
                    "routing": {
                        "request": {"method": "GET", "url": "ping"},
                    },
                }
            ],
        },
    }
    pkg = emit_node_package(row, tmp_path, [], {})
    validate_packages([pkg])
