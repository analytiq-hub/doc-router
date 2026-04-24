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
    parameter_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "payload": {
                "type": "object",
                "description": "Optional extra keys merged into the emitted item JSON (after trigger metadata).",
            },
        },
        "additionalProperties": False,
    }

    def validate_parameters(self, params: dict[str, Any]) -> list[str]:
        pl = params.get("payload")
        if pl is not None and not isinstance(pl, dict):
            return ["parameters.payload must be an object when set"]
        return []

    async def execute(
        self,
        context: "ad.flows.ExecutionContext",
        node: dict[str, Any],
        inputs: list[list["ad.flows.FlowItem"]],
    ) -> list[list["ad.flows.FlowItem"]]:
        """Emit a single item containing `trigger_data` under `json.trigger`."""

        params = node.get("parameters") or {}
        extra = params.get("payload")
        if isinstance(extra, dict) and extra:
            out_json: dict[str, Any] = {**extra, "trigger": context.trigger_data}
        else:
            out_json = {"trigger": context.trigger_data}
        item = ad.flows.FlowItem(
            json=out_json,
            binary={},
            meta={"source_node_id": node["id"], "item_index": 0},
            paired_item=None,
        )
        return [[item]]

