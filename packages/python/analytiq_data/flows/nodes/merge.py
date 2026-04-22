from __future__ import annotations

from typing import Any

from ..context import ExecutionContext
from ..items import FlowItem


class FlowsMergeNode:
    key = "flows.merge"
    label = "Merge"
    description = "Waits for all inputs, then concatenates them."
    category = "Generic"
    is_trigger = False
    min_inputs = 2
    max_inputs = None
    outputs = 1
    output_labels = ["output"]
    parameter_schema: dict[str, Any] = {"type": "object", "properties": {}, "additionalProperties": False}

    def validate_parameters(self, params: dict[str, Any]) -> list[str]:
        return []

    async def execute(
        self,
        context: ExecutionContext,
        node: dict[str, Any],
        inputs: list[list[FlowItem]],
    ) -> list[list[FlowItem]]:
        merged: list[FlowItem] = []
        for slot_items in inputs:
            merged.extend(slot_items)
        return [merged]

