from __future__ import annotations

"""Generic branching node implementation (`flows.branch`)."""

from typing import Any

import analytiq_data as ad


class FlowsBranchNode:
    """Route each input item to either the `true` or `false` output slot."""

    key = "flows.branch"
    label = "Branch"
    description = "Routes items to true/false outputs based on a condition."
    category = "Generic"
    is_trigger = False
    is_merge = False
    min_inputs = 1
    max_inputs = 1
    outputs = 2
    output_labels = ["true", "false"]
    parameter_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "field": {"type": "string"},
            "equals": {},
        },
        "required": ["field", "equals"],
        "additionalProperties": False,
    }

    def validate_parameters(self, params: dict[str, Any]) -> list[str]:
        """Validate the configured `field` parameter is usable."""

        # Keep v1 simple; JSON Schema handles requiredness.
        if not isinstance(params.get("field"), str) or not params["field"]:
            return ["parameters.field must be a non-empty string"]
        return []

    async def execute(
        self,
        context: "ad.flows.ExecutionContext",
        node: dict[str, Any],
        inputs: list[list["ad.flows.FlowItem"]],
    ) -> list[list["ad.flows.FlowItem"]]:
        """Split items by `json[field] == equals`."""

        field = node.get("parameters", {}).get("field")
        equals = node.get("parameters", {}).get("equals")
        true_items: list["ad.flows.FlowItem"] = []
        false_items: list["ad.flows.FlowItem"] = []
        for it in inputs[0]:
            if it.json.get(field) == equals:
                true_items.append(it)
            else:
                false_items.append(it)
        return [true_items, false_items]

