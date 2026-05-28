"""Google Drive poll trigger node (`flows.trigger.google_drive`)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import analytiq_data as ad

from analytiq_data.flows.triggers.cron_exprs import poll_times_to_specs
from analytiq_data.flows.triggers.poll_defaults import resolve_poll_times

from .helpers import normalize_drive_watch_id
from .poll_trigger import poll_google_drive_trigger

_SCHEMA_PATH = Path(__file__).resolve().parent / "trigger.parameter.schema.json"


def _load_parameter_schema() -> dict[str, Any]:
    return json.loads(_SCHEMA_PATH.read_text(encoding="utf-8"))


class FlowsGoogleDriveTriggerNode:
    """Starts the flow when Google Drive files or folders change (poll trigger)."""

    key = "flows.trigger.google_drive"
    label = "Google Drive trigger"
    description = "Starts the flow when Google Drive events occur."
    category = "input"
    palette_group = "trigger"
    is_trigger = True
    polling = True
    is_merge = False
    min_inputs = 0
    max_inputs = 0
    outputs = 1
    output_labels = ["output"]
    icon_key = "google_drive"
    parameter_schema = _load_parameter_schema()
    credential_slots = [
        {
            "slot": "googleDriveOAuth2Api",
            "label": "Credential to connect with",
            "required": True,
            "docrouter_binding": "organization_credential_kind:googleDriveOAuth2Api",
        },
    ]

    def validate_parameters(self, params: dict[str, Any]) -> list[str]:
        errors: list[str] = []
        trigger_on = str(params.get("triggerOn") or "").strip()
        event = str(params.get("event") or "").strip()
        if trigger_on not in ("specificFile", "specificFolder"):
            errors.append("triggerOn must be specificFile or specificFolder")
        if trigger_on == "specificFile":
            if not event:
                errors.append("event is required for specific file trigger")
            elif event != "fileUpdated":
                errors.append("specific file trigger only supports fileUpdated")
            if not normalize_drive_watch_id(params.get("fileToWatch")):
                errors.append("fileToWatch is required (Google Drive file ID or share URL)")
        if trigger_on == "specificFolder":
            if not event:
                errors.append("event is required for specific folder trigger")
            if not normalize_drive_watch_id(params.get("folderToWatch")):
                errors.append("folderToWatch is required (Google Drive folder ID or share URL)")
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
        return await poll_google_drive_trigger(context, node)

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
            json={"manual_sample": True},
            binary={},
            meta={"source_node_id": node["id"], "item_index": 0, "manual_sample": True},
            paired_item=None,
        )
        return [[sample]]
