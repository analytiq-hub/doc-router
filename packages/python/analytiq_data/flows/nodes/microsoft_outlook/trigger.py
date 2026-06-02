"""Microsoft Outlook poll trigger node (``flows.trigger.microsoft_outlook``)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import analytiq_data as ad

from analytiq_data.flows.triggers.cron_exprs import poll_times_to_specs
from analytiq_data.flows.triggers.poll_defaults import resolve_poll_times
from analytiq_data.flows.triggers.static_data import load_node_static_data, save_node_static_data

from .poll_trigger import poll_microsoft_outlook_trigger

_SCHEMA_PATH = Path(__file__).resolve().parent / "trigger.parameter.schema.json"


def _load_parameter_schema() -> dict[str, Any]:
    return json.loads(_SCHEMA_PATH.read_text(encoding="utf-8"))


class FlowsMicrosoftOutlookTriggerNode:
    """Starts the flow when new Microsoft Outlook messages arrive (poll trigger)."""

    key = "flows.trigger.microsoft_outlook"
    label = "Microsoft Outlook Trigger"
    description = (
        "Starts the flow when Outlook messages match your filters. "
        "Uses receivedDateTime since the last poll (or the latest message in manual test)."
    )
    category = "input"
    palette_group = "trigger"
    is_trigger = True
    polling = True
    is_merge = False
    min_inputs = 0
    max_inputs = 0
    outputs = 1
    output_labels = ["output"]
    icon_key = "microsoft_outlook"
    type_version = 1
    experimental = True
    parameter_schema = _load_parameter_schema()
    credential_slots = [
        {
            "slot": "microsoftOutlookOAuth2Api",
            "label": "Credential to connect with",
            "required": True,
            "docrouter_binding": "organization_credential_kind:microsoftOutlookOAuth2Api",
        },
    ]

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
        return await poll_microsoft_outlook_trigger(context, node)

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

        if context.mode == "manual":
            node_id = str(node.get("id") or "")
            static_data: dict[str, Any] = {}
            if context.analytiq_client and node_id:
                db = ad.common.get_async_db(context.analytiq_client)
                static_data = await load_node_static_data(db, context.flow_id, node_id)

            poll_ctx = ad.flows.PollContext(
                organization_id=context.organization_id,
                flow_id=context.flow_id,
                flow_revid=context.flow_revid,
                node_id=node_id,
                mode="manual",
                analytiq_client=context.analytiq_client,
                static_data=static_data,
            )
            items = await poll_microsoft_outlook_trigger(
                poll_ctx, node, execution=context
            )
            if poll_ctx.data_changed and context.analytiq_client and node_id:
                db = ad.common.get_async_db(context.analytiq_client)
                await save_node_static_data(db, context.flow_id, node_id, poll_ctx.static_data)
            if items and items[0]:
                return items
            raise ad.flows.FlowValidationError(
                "No data with the current filter could be found"
            )

        sample = ad.flows.FlowItem(
            json={"manual_sample": True},
            binary={},
            meta={"source_node_id": node["id"], "item_index": 0, "manual_sample": True},
            paired_item=None,
        )
        return [[sample]]
