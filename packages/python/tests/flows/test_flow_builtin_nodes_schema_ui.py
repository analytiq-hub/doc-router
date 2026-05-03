"""UI-oriented keys on built-in node parameter schemas (`x-ui-*`, groups, etc.)."""

from __future__ import annotations

from analytiq_data.flows.nodes.branch import FlowsBranchNode
from analytiq_data.flows.nodes.code import FlowsCodeNode
from analytiq_data.flows.nodes.merge import FlowsMergeNode
from analytiq_data.flows.nodes.trigger_manual import FlowsManualTriggerNode


def test_code_node_parameter_schema_ui_hints() -> None:
    props = FlowsCodeNode().parameter_schema["properties"]
    assert props["python_code"].get("x-ui-widget") == "code"
    assert props["python_code"].get("x-ui-group") == "Code"
    assert props["timeout_seconds"].get("x-ui-group") == "Options"
    assert props["timeout_seconds"].get("maximum") == 30


def test_branch_node_parameter_schema_ui_hints() -> None:
    props = FlowsBranchNode().parameter_schema["properties"]
    assert props["field"].get("x-ui-group") == "Condition"
    assert props["equals"].get("x-ui-group") == "Condition"
    assert "x-ui-placeholder" in props["field"]


def test_merge_node_parameter_schema_has_description() -> None:
    schema = FlowsMergeNode().parameter_schema
    assert schema.get("title") == "Merge"
    assert "concatenated" in (schema.get("description") or "").lower()


def test_trigger_node_parameter_schema_has_title() -> None:
    schema = FlowsManualTriggerNode().parameter_schema
    assert schema.get("title") == "Manual trigger"
    assert schema.get("properties") == {}
