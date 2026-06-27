from __future__ import annotations

"""Flow Tool node — invoke another callable flow as an LLM tool."""

import re
from typing import Any

import analytiq_data as ad

_TOOL_NAME_RE = re.compile(r"^[a-z][a-z0-9_]{0,63}$")


class FlowsFlowToolNode:
    key = "flows.flow_tool"
    label = "Flow Tool"
    description = "Invokes another flow's active revision as a single tool call."
    category = "AI"
    palette_group = "ai"
    tool_provider = True
    is_trigger = False
    is_merge = False
    min_inputs = 0
    max_inputs = 0
    outputs = 1
    output_labels = ["tool"]
    output_port_types = ["flows.tool"]
    icon_key = "flow_tool"
    type_version = 1
    experimental = True
    parameter_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "tool_name": {"type": "string", "x-ui-group": "Tool"},
            "tool_description": {"type": "string", "x-ui-widget": "textarea", "x-ui-group": "Tool"},
            "target_flow_id": {
                "type": "string",
                "x-ui-widget": "flow_picker",
                "x-ui-flow-picker-mode": "callable",
                "x-ui-group": "Flow",
            },
            "parameters_schema": {
                "type": "object",
                "x-ui-widget": "json",
                "x-ui-group": "Tool",
            },
        },
        "required": ["tool_name", "tool_description", "target_flow_id"],
        "additionalProperties": False,
    }

    def validate_parameters(self, params: dict[str, Any]) -> list[str]:
        errs: list[str] = []
        name = str(params.get("tool_name") or "").strip()
        if not name or not _TOOL_NAME_RE.match(name):
            errs.append("parameters.tool_name must match ^[a-z][a-z0-9_]{0,63}$")
        if not str(params.get("tool_description") or "").strip():
            errs.append("parameters.tool_description is required")
        if not str(params.get("target_flow_id") or "").strip():
            errs.append("parameters.target_flow_id is required")
        return errs

    async def execute(
        self,
        context: "ad.flows.ExecutionContext",
        node: dict[str, Any],
        inputs: list[list["ad.flows.FlowItem"]],
    ) -> list[list["ad.flows.FlowItem"]]:
        return [[]]
