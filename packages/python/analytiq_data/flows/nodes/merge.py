from __future__ import annotations

"""Generic merge node implementation (`flows.merge`)."""

from typing import Any

import analytiq_data as ad


class FlowsMergeNode:
    """Concatenate items from multiple input slots into a single output list."""

    key = "flows.merge"
    label = "Merge"
    description = "Waits for all inputs, then concatenates them."
    category = "Generic"
    is_trigger = False
    is_merge = True
    min_inputs = 2
    max_inputs = None
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
        """Concatenate inputs in ascending input-slot order."""

        merged: list["ad.flows.FlowItem"] = []
        for slot_items in inputs:
            merged.extend(slot_items)
        return [merged]

