"""Tests for typed flow connection ports."""

from __future__ import annotations

import pytest

import analytiq_data as ad
from analytiq_data.flows.connections import NodeConnection, coerce_json_connections_to_dataclasses
from analytiq_data.flows.engine import FlowValidationError, validate_revision


def _node(node_id: str, node_type: str, name: str | None = None) -> dict:
    return {
        "id": node_id,
        "name": name or node_id,
        "type": node_type,
        "position": [0, 0],
        "parameters": {},
        "disabled": False,
        "on_error": "stop",
        "retry_on_fail": False,
        "max_tries": 1,
        "wait_between_tries_ms": 1000,
        "notes": None,
        "webhook_id": None,
    }


@pytest.fixture(autouse=True)
def _register_nodes():
    ad.flows.register_builtin_nodes()
    ad.flows.register_docrouter_nodes()


def test_coerce_preserves_connection_type() -> None:
    raw = {
        "ocr": {
            "main": [[{"dest_node_id": "llm", "connection_type": "docrouter.ocr", "index": 1}]],
        }
    }
    conns = coerce_json_connections_to_dataclasses(raw)
    assert conns["ocr"]["main"][0][0].connection_type == "docrouter.ocr"


def _trigger(node_id: str = "t1") -> dict:
    return _node(node_id, "flows.trigger.manual", "Trigger")


def test_validate_rejects_mismatched_connection_type() -> None:
    nodes = [
        _trigger(),
        _node("ocr", "docrouter.ocr"),
        _node("code", "flows.code"),
    ]
    connections = {
        "t1": {"main": [[NodeConnection(dest_node_id="ocr", connection_type="main", index=0)]]},
        "ocr": {
            "main": [
                [NodeConnection(dest_node_id="code", connection_type="main", index=0)],
            ],
        },
    }
    with pytest.raises(FlowValidationError, match="connection_type 'docrouter.ocr'"):
        validate_revision(nodes, connections, {}, None)


def test_validate_accepts_docrouter_ocr_edge() -> None:
    llm = _node("llm", "docrouter.llm_run")
    llm["parameters"] = {"prompt_id": "p1"}
    nodes = [
        _trigger(),
        _node("ocr", "docrouter.ocr"),
        llm,
    ]

    connections = {
        "t1": {"main": [[NodeConnection(dest_node_id="ocr", connection_type="main", index=0)]]},
        "ocr": {
            "main": [
                [NodeConnection(dest_node_id="llm", connection_type="docrouter.ocr", index=1)],
            ],
        },
    }
    validate_revision(nodes, connections, {}, None)
