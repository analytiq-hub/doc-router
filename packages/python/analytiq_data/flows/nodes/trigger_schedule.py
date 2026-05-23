from __future__ import annotations

"""Schedule trigger node (`flows.trigger.schedule`)."""

from datetime import datetime, UTC
from typing import Any

import analytiq_data as ad

from analytiq_data.flows.triggers.cron_exprs import schedule_params_to_specs

_INTERVAL_ITEM_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "field": {
            "type": "string",
            "enum": ["minutes", "hours", "days", "cronExpression"],
            "default": "hours",
        },
        "minutesInterval": {
            "type": "integer",
            "minimum": 1,
            "maximum": 59,
            "default": 5,
        },
        "hoursInterval": {
            "type": "integer",
            "minimum": 1,
            "maximum": 23,
            "default": 1,
        },
        "daysInterval": {
            "type": "integer",
            "minimum": 1,
            "maximum": 31,
            "default": 1,
        },
        "cronExpression": {
            "type": "string",
            "default": "0 * * * *",
            "description": "Cron expression (validated by croniter on save). Usually 5 fields: minute hour day-of-month month day-of-week.",
        },
    },
    "required": ["field"],
}


class FlowsScheduleTriggerNode:
    """Fire the flow on a cron schedule (n8n Schedule Trigger subset)."""

    key = "flows.trigger.schedule"
    label = "Schedule trigger"
    description = "Starts the flow on a recurring schedule (cron or interval rules)."
    category = "Generic"
    palette_group = "trigger"
    is_trigger = True
    polling = False
    min_inputs = 0
    max_inputs = 0
    outputs = 1
    output_labels = ["output"]
    icon_key = "schedule_trigger"
    parameter_schema: dict[str, Any] = {
        "type": "object",
        "title": "Schedule trigger",
        "properties": {
            "rule": {
                "type": "object",
                "title": "Trigger rules",
                "description": "One or more interval rules; each matching tick can start a run.",
                "x-ui-widget": "schedule_trigger_rules",
                "default": {
                    "interval": [{"field": "hours", "hoursInterval": 1}],
                },
                "properties": {
                    "interval": {
                        "type": "array",
                        "minItems": 1,
                        "items": _INTERVAL_ITEM_SCHEMA,
                    },
                },
                "required": ["interval"],
            },
        },
        "required": ["rule"],
    }

    def validate_parameters(self, params: dict[str, Any]) -> list[str]:
        errors: list[str] = []
        try:
            schedule_params_to_specs(params)
        except Exception as e:
            errors.append(str(e))
        return errors

    async def on_schedule_tick(
        self,
        context: "ad.flows.triggers.PollContext",
        node: dict[str, Any],
    ) -> list[list[ad.flows.FlowItem]]:
        rule_index = int(context.tick_meta.get("rule_index") or 0)
        item = ad.flows.FlowItem(
            json={
                "timestamp": datetime.now(UTC).isoformat(),
                "rule_index": rule_index,
            },
            binary={},
            meta={"source_node_id": node["id"], "item_index": 0},
            paired_item=None,
        )
        return [[item]]

    async def execute(
        self,
        context: "ad.flows.ExecutionContext",
        node: dict[str, Any],
        inputs: list[list["ad.flows.FlowItem"]],
    ) -> list[list["ad.flows.FlowItem"]]:
        """
        During a scheduled run, replay items from ``trigger_data``.

        Manual/editor runs emit a single sample item.
        """

        td = context.trigger_data or {}
        if context.mode == "schedule" and td.get("type") == "schedule":
            raw_slots = td.get("items")
            if isinstance(raw_slots, list) and raw_slots:
                out_slot: list[ad.flows.FlowItem] = []
                for lane in raw_slots:
                    if not isinstance(lane, list):
                        continue
                    for raw in lane:
                        if isinstance(raw, dict):
                            out_slot.append(ad.flows.coerce_flow_item(raw))
                if out_slot:
                    return [out_slot]

        sample = ad.flows.FlowItem(
            json={"timestamp": datetime.now(UTC).isoformat(), "rule_index": 0},
            binary={},
            meta={"source_node_id": node["id"], "item_index": 0, "manual_sample": True},
            paired_item=None,
        )
        return [[sample]]
