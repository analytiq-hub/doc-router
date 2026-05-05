from __future__ import annotations

"""Generic manual trigger node implementation (`flows.trigger.manual`)."""

from typing import Any

import analytiq_data as ad


class FlowsManualTriggerNode:
    """Seed a manual execution with a single empty JSON item (same idea as n8n Manual Trigger)."""

    key = "flows.trigger.manual"
    label = "Manual trigger"
    description = "Emits one item with empty JSON `{}`. Use a Code node or pin_data for test payloads; `trigger_data` is only in Code context."
    category = "Generic"
    is_trigger = True
    is_merge = False
    min_inputs = 0
    max_inputs = 0
    outputs = 1
    output_labels = ["output"]
    icon_key = "manual_trigger"
    # Triggers have no user-editable parameters; tolerate legacy keys in stored revisions.
    parameter_schema: dict[str, Any] = {
        "type": "object",
        "title": "Manual trigger",
        "description": "No editable parameters. Downstream nodes or pin_data supply JSON fields.",
        "properties": {},
        "additionalProperties": True,
    }

    def validate_parameters(self, params: dict[str, Any]) -> list[str]:
        return []

    async def execute(
        self,
        context: "ad.flows.ExecutionContext",
        node: dict[str, Any],
        inputs: list[list["ad.flows.FlowItem"]],
    ) -> list[list["ad.flows.FlowItem"]]:
        """Emit one item whose JSON is `{}` (trigger metadata lives on the execution / Code `context`)."""

        item = ad.flows.FlowItem(
            json={},
            binary={},
            meta={"source_node_id": node["id"], "item_index": 0},
            paired_item=None,
        )
        return [[item]]
