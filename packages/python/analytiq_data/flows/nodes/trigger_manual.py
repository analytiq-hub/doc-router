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
        "required": ["payload"],
        "properties": {
            "payload": {
                "type": "array",
                "items": {"type": "object"},
                "description": "List of items to emit. Each object is merged into the item JSON (after trigger metadata).",
            },
        },
        "additionalProperties": False,
    }

    def validate_parameters(self, params: dict[str, Any]) -> list[str]:
        pl = params.get("payload")
        if not isinstance(pl, list):
            return ["parameters.payload must be an array of objects"]
        if not all(isinstance(x, dict) for x in pl):
            return ["parameters.payload must be an array of objects"]
        return []

    async def execute(
        self,
        context: "ad.flows.ExecutionContext",
        node: dict[str, Any],
        inputs: list[list["ad.flows.FlowItem"]],
    ) -> list[list["ad.flows.FlowItem"]]:
        """Emit one or more items containing `trigger_data` under `json.trigger`."""

        params = node.get("parameters") or {}
        payload = params.get("payload")
        items: list[ad.flows.FlowItem] = []

        def _make_item(extra_obj: dict[str, Any] | None, idx: int) -> ad.flows.FlowItem:
            out_json: dict[str, Any]
            if extra_obj:
                out_json = {**extra_obj, "trigger": context.trigger_data}
            else:
                out_json = {"trigger": context.trigger_data}
            return ad.flows.FlowItem(
                json=out_json,
                binary={},
                meta={"source_node_id": node["id"], "item_index": idx},
                paired_item=None,
            )

        if isinstance(payload, list) and len(payload) > 0:
            for idx, obj in enumerate(payload):
                # validate_parameters ensures each is a dict; be defensive anyway.
                if isinstance(obj, dict):
                    items.append(_make_item(obj, idx))
        else:
            # If empty (or missing), still emit a single seed item with trigger metadata.
            items.append(_make_item(None, 0))

        return [items]

