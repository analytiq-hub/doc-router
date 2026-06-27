from __future__ import annotations

"""Respond to tool node — sets tool_result for parent flow_tool dispatch."""

from typing import Any

import analytiq_data as ad


class FlowsRespondToToolNode:
    key = "flows.respond_to_tool"
    label = "Respond to tool"
    description = "Sets json.tool_result for parent flow_tool dispatch."
    category = "AI"
    palette_group = "ai"
    is_trigger = False
    is_merge = False
    min_inputs = 1
    max_inputs = 1
    outputs = 0
    output_labels = []
    icon_key = "respond_to_tool"
    type_version = 1
    experimental = True
    parameter_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "result_source": {
                "type": "string",
                "enum": ["from_input", "input_field", "fixed"],
                "default": "from_input",
                "x-ui-widget": "select",
            },
            "result_field": {"type": "string", "default": "tool_result"},
            "result_value": {"type": "object", "x-ui-widget": "json"},
        },
        "additionalProperties": False,
    }

    def validate_parameters(self, params: dict[str, Any]) -> list[str]:
        return []

    def _resolve_result(self, params: dict[str, Any], item: "ad.flows.FlowItem") -> Any:
        src = params.get("result_source") or "from_input"
        if src == "fixed":
            return params.get("result_value")
        if src == "input_field":
            field = str(params.get("result_field") or "tool_result")
            return (item.json or {}).get(field)
        return dict(item.json or {})

    async def execute(
        self,
        context: "ad.flows.ExecutionContext",
        node: dict[str, Any],
        inputs: list[list["ad.flows.FlowItem"]],
    ) -> list[list["ad.flows.FlowItem"]]:
        in_items = inputs[0] if inputs else []
        item = in_items[0] if in_items else ad.flows.FlowItem(json={}, binary={}, meta={})
        context.sub_flow_tool_result = self._resolve_result(node.get("parameters") or {}, item)
        return []
