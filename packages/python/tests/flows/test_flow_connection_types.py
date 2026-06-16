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
    llm_like = _node("llm", "flows.code")
    nodes = [
        _trigger(),
        _node("ocr", "docrouter.ocr"),
        llm_like,
    ]
    # Stand-in downstream node with a typed OCR input port (future llm_run shape).
    class _LlmLike:
        key = "docrouter.llm_run"
        label = "LLM"
        description = ""
        category = "DocRouter"
        is_trigger = False
        is_merge = False
        min_inputs = 2
        max_inputs = 2
        outputs = 1
        output_labels = ["output"]
        input_port_types = ["main", "docrouter.ocr"]
        output_port_types = ["main"]
        parameter_schema = {"type": "object", "properties": {}, "additionalProperties": False}
        icon_key = None

        def validate_parameters(self, params):
            return []

        async def execute(self, context, node, inputs):
            return [[]]

    ad.flows.register(_LlmLike())
    llm_like["type"] = "docrouter.llm_run"

    connections = {
        "t1": {"main": [[NodeConnection(dest_node_id="ocr", connection_type="main", index=0)]]},
        "ocr": {
            "main": [
                [NodeConnection(dest_node_id="llm", connection_type="docrouter.ocr", index=1)],
            ],
        },
    }
    validate_revision(nodes, connections, {}, None)
