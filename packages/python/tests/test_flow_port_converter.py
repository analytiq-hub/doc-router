from __future__ import annotations

import json
from pathlib import Path

import pytest

from analytiq_data.flows.port.converter import emit_node_package, manifest_key


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
