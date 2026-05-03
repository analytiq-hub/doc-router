from __future__ import annotations

"""Generic branching node implementation (`flows.branch`)."""

from typing import Any

import analytiq_data as ad


def _branch_field_equals(actual: Any, expected: Any) -> bool:
    """Loose equality for branch conditions (handles JSON numeric vs string from UIs/API)."""

    if actual == expected:
        return True
    try:
        if isinstance(actual, (int, float)) and isinstance(expected, str):
            return float(actual) == float(expected)
        if isinstance(actual, str) and isinstance(expected, (int, float)):
            return float(actual) == float(expected)
    except (TypeError, ValueError):
        return False
    return False


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
    icon_key = "branch"
    parameter_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "field": {
                "type": "string",
                "minLength": 1,
                "default": "",
                "description": "Key on each item's `json` object to read (e.g. `status`, `ok`).",
                "x-ui-group": "Condition",
                "x-ui-placeholder": "Field name in each item's JSON",
            },
            "equals": {
                "description": "Compared to `json[field]` (loose equality for number vs string). Use a literal or expression.",
                "x-ui-group": "Condition",
                "x-ui-placeholder": "Value to match, or =expression",
            },
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
            actual = it.json.get(field)
            if _branch_field_equals(actual, equals):
                true_items.append(it)
            else:
                false_items.append(it)
        return [true_items, false_items]

