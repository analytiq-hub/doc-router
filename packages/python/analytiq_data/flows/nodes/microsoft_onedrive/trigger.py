"""Microsoft OneDrive poll trigger node (``flows.trigger.microsoft_onedrive``)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import analytiq_data as ad

from analytiq_data.flows.triggers.cron_exprs import poll_times_to_specs
from analytiq_data.flows.triggers.poll_defaults import resolve_poll_times

from analytiq_data.flows.integrations.microsoft import normalize_drive_item_id
from .poll_trigger import poll_microsoft_onedrive_trigger

_SCHEMA_PATH = Path(__file__).resolve().parent / "trigger.parameter.schema.json"


def _load_parameter_schema() -> dict[str, Any]:
    return json.loads(_SCHEMA_PATH.read_text(encoding="utf-8"))


class FlowsMicrosoftOneDriveTriggerNode:
    """Trigger for Microsoft OneDrive API (n8n ``microsoftOneDriveTrigger``)."""

    key = "flows.trigger.microsoft_onedrive"
    label = "Microsoft OneDrive Trigger"
    description = "Trigger for Microsoft OneDrive API."
    category = "input"
    palette_group = "trigger"
    is_trigger = True
    polling = True
    is_merge = False
    min_inputs = 0
    max_inputs = 0
    outputs = 1
    output_labels = ["output"]
    icon_key = "microsoft_onedrive"
    type_version = 1
    experimental = True
    parameter_schema = _load_parameter_schema()
    credential_slots = [
        {
            "slot": "microsoftOneDriveOAuth2Api",
            "label": "Credential to connect with",
            "required": True,
            "docrouter_binding": "organization_credential_kind:microsoftOneDriveOAuth2Api",
        },
    ]

    def validate_parameters(self, params: dict[str, Any]) -> list[str]:
        errors: list[str] = []
        event = str(params.get("event") or "").strip()
        if not event:
            errors.append("event is required")
        watch = str(params.get("watch") or "").strip()
        watch_folder = bool(params.get("watchFolder"))
        if event == "fileUpdated" and watch == "selectedFile":
            if not normalize_drive_item_id(params.get("fileId")):
                errors.append("fileId is required when watching a selected file")
        if watch in ("selectedFolder", "oneSelectedFolder") or watch_folder:
            if not normalize_drive_item_id(params.get("folderId")):
                errors.append("folderId is required for the selected folder watch")
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
        return await poll_microsoft_onedrive_trigger(context, node)

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
