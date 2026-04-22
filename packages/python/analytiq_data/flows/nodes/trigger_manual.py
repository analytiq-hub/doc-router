from __future__ import annotations

"""Generic manual trigger node implementation (`flows.trigger.manual`)."""

from typing import Any

import analytiq_data as ad


class FlowsManualTriggerNode:
    """Seed a manual execution with the engine-provided `trigger_data` payload."""

    key = "flows.trigger.manual"
    label = "Manual trigger"
    description = "Emits the manual-run seed item."
    category = "Generic"
    is_trigger = True
    is_merge = False
    min_inputs = 0
    max_inputs = 0
    outputs = 1
    output_labels = ["output"]
    parameter_schema: dict[str, Any] = {"type": "object", "properties": {}, "additionalProperties": False}

    def validate_parameters(self, params: dict[str, Any]) -> list[str]:
        """Validate node parameters beyond JSON Schema (none for this node)."""

        return []

    async def execute(
        self,
        context: "ad.flows.ExecutionContext",
        node: dict[str, Any],
        inputs: list[list["ad.flows.FlowItem"]],
    ) -> list[list["ad.flows.FlowItem"]]:
        """Emit a single item containing `trigger_data` under `json.trigger`."""

        item = ad.flows.FlowItem(
            json={"trigger": context.trigger_data},
            binary={},
            meta={"source_node_id": node["id"], "item_index": 0},
            paired_item=None,
        )
        return [[item]]

