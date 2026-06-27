from __future__ import annotations

"""Sub-flow entry trigger for flows invoked by another flow or Flow Tool (`flows.trigger.tool`)."""

from typing import Any

import analytiq_data as ad


class FlowsToolTriggerNode:
    key = "flows.trigger.tool"
    label = "Sub-flow entry"
    description = (
        "Starts when another flow runs this flow (Execute Flow or Flow Tool); "
        "emits one item from tool arguments or sub-flow input."
    )
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
        trigger = context.trigger_data or {}
        if "subflow_input" in trigger:
            payload = trigger["subflow_input"]
            args = dict(payload) if isinstance(payload, dict) else {"value": payload}
        else:
            args = trigger.get("tool_arguments")
            if not isinstance(args, dict):
                args = {}
        item = ad.flows.FlowItem(
            json=dict(args),
            binary={},
            meta={"source_node_id": node["id"], "item_index": 0},
            paired_item=None,
        )
        return [[item]]
