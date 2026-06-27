from __future__ import annotations

"""Tool entry trigger for callable sub-flows (`flows.trigger.tool`)."""

from typing import Any

import analytiq_data as ad


class FlowsToolTriggerNode:
    key = "flows.trigger.tool"
    label = "Tool entry"
    description = "Starts a callable sub-flow; emits one item whose json is the tool arguments object."
    category = "Generic"
    palette_group = "trigger"
    is_trigger = True
    is_merge = False
    min_inputs = 0
    max_inputs = 0
    outputs = 1
    output_labels = ["output"]
    icon_key = "tool_trigger"
    type_version = 1
    parameter_schema: dict[str, Any] = {
        "type": "object",
        "properties": {},
        "additionalProperties": False,
    }

    def validate_parameters(self, params: dict[str, Any]) -> list[str]:
        return []

    async def execute(
        self,
        context: "ad.flows.ExecutionContext",
        node: dict[str, Any],
        inputs: list[list["ad.flows.FlowItem"]],
    ) -> list[list["ad.flows.FlowItem"]]:
        args = context.trigger_data.get("tool_arguments")
        if not isinstance(args, dict):
            args = {}
        item = ad.flows.FlowItem(
            json=dict(args),
            binary={},
            meta={"source_node_id": node["id"], "item_index": 0},
            paired_item=None,
        )
        return [[item]]
