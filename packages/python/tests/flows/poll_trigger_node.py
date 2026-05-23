from __future__ import annotations

"""Test-only poll trigger node for poll framework tests."""

from typing import Any

import analytiq_data as ad

from analytiq_data.flows.triggers.poll_defaults import POLL_TIMES_PROPERTY, resolve_poll_times
from analytiq_data.flows.triggers.cron_exprs import poll_times_to_specs


class TestsPollTriggerNode:
    """Dummy poll trigger: emits items until ``items_per_poll`` based on a static cursor."""

    key = "tests.poll_trigger"
    label = "Test poll trigger"
    description = "Test-only poll trigger for poll framework tests."
    category = "Test"
    palette_group = "trigger"
    is_trigger = True
    polling = True
    is_merge = False
    min_inputs = 0
    max_inputs = 0
    outputs = 1
    output_labels = ["output"]
    icon_key = None
    parameter_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "items_per_poll": {
                "type": "integer",
                "minimum": 0,
                "default": 1,
                "description": "How many poll ticks emit an item before going idle.",
            },
            "fail_activation": {
                "type": "boolean",
                "default": False,
                "description": "When true, activation test raises.",
            },
            **POLL_TIMES_PROPERTY,
        },
    }

    def validate_parameters(self, params: dict[str, Any]) -> list[str]:
        errors: list[str] = []
        try:
            poll_times_to_specs(resolve_poll_times(params))
        except Exception as e:
            errors.append(str(e))
        return errors

    async def poll(
        self,
        context: "ad.flows.PollContext",
        node: dict[str, Any],
    ) -> list[list[ad.flows.FlowItem]] | None:
        params = node.get("parameters") or {}
        if params.get("fail_activation") and context.tick_meta.get("testing"):
            raise RuntimeError("poll activation test failure")

        limit = int(params.get("items_per_poll") or 0)
        if limit <= 0:
            return None

        cursor = int(context.get_static("cursor") or 0)
        if cursor >= limit:
            return None

        context.set_static("cursor", cursor + 1)
        item = ad.flows.FlowItem(
            json={
                "seq": cursor + 1,
                "testing": bool(context.tick_meta.get("testing")),
                "mode": context.mode,
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
    ) -> list[list[ad.flows.FlowItem]]:
        td = context.trigger_data or {}
        if context.mode == "schedule" and td.get("type") == "poll":
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
            json={"seq": 0, "manual_sample": True},
            binary={},
            meta={"source_node_id": node["id"], "item_index": 0, "manual_sample": True},
            paired_item=None,
        )
        return [[sample]]
