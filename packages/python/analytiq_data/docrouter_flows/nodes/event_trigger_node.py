from __future__ import annotations

"""DocRouter document lifecycle event trigger node."""

from datetime import UTC, datetime
from typing import Any

import analytiq_data as ad

from ..event_dispatch import DOCROUTER_EVENT_TRIGGER_KIND, DOCROUTER_TRIGGER_TYPE
from ..event_types import DOCROUTER_EVENT_TYPES, DOCROUTER_LLM_EVENT_TYPES


class DocRouterEventTriggerNode:
    """Fires when a configured document lifecycle event occurs."""

    key = DOCROUTER_TRIGGER_TYPE
    label = "Document event trigger"
    description = "Starts the flow when a document is uploaded, errors, or completes LLM processing."
    category = "DocRouter"
    palette_group = "trigger"
    is_trigger = True
    is_merge = False
    min_inputs = 0
    max_inputs = 0
    outputs = 1
    output_labels = ["output"]
    icon_key = "document_event_trigger"
    parameter_schema: dict[str, Any] = {
        "type": "object",
        "title": "Document event trigger",
        "properties": {
            "event_type": {
                "type": "string",
                "enum": list(DOCROUTER_EVENT_TYPES),
                "default": "document.uploaded",
                "description": "Document lifecycle event that starts this flow.",
            },
            "tag_ids": {
                "type": "array",
                "items": {"type": "string"},
                "title": "Tag filter",
                "description": "Tags — fires when the document has any of these tags.",
                "x-ui-widget": "org_tag_picker",
            },
            "prompt_id": {
                "type": "string",
                "title": "Prompt filter",
                "description": "Optional prompt filter for LLM events.",
                "x-ui-widget": "org_prompt_picker",
                "x-ui-show-when-any": [
                    {"field": "event_type", "equals": "llm.completed"},
                    {"field": "event_type", "equals": "llm.error"},
                ],
            },
            "report_result": {
                "type": "boolean",
                "title": "Report result to document",
                "default": True,
                "description": (
                    "When enabled, the last node's output is saved on the document "
                    "Flows tab after each run."
                ),
            },
        },
        "required": ["event_type"],
        "additionalProperties": False,
    }

    def validate_parameters(self, params: dict[str, Any]) -> list[str]:
        errs: list[str] = []
        event_type = params.get("event_type")
        if not isinstance(event_type, str) or event_type not in DOCROUTER_EVENT_TYPES:
            errs.append("parameters.event_type is required")
        tag_ids = params.get("tag_ids")
        if tag_ids is not None and not isinstance(tag_ids, list):
            errs.append("parameters.tag_ids must be a list of strings")
        prompt_id = params.get("prompt_id")
        if isinstance(prompt_id, str) and prompt_id.strip() and event_type not in DOCROUTER_LLM_EVENT_TYPES:
            errs.append("parameters.prompt_id applies only to llm.completed / llm.error")
        return errs

    async def execute(
        self,
        context: "ad.flows.ExecutionContext",
        node: dict[str, Any],
        inputs: list[list["ad.flows.FlowItem"]],
    ):
        td = context.trigger_data or {}
        if context.mode == "event" and td.get("type") == DOCROUTER_EVENT_TRIGGER_KIND:
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

        params = node.get("parameters") or {}
        event_type = params.get("event_type") if isinstance(params.get("event_type"), str) else "document.uploaded"
        sample = ad.flows.FlowItem(
            json={
                "event_type": event_type,
                "document_id": "",
                "file_name": "",
                "mime_type": "application/octet-stream",
                "upload_date": datetime.now(UTC).isoformat(),
                "tag_ids": [],
                "tag_names": [],
                "metadata": {},
            },
            binary={},
            meta={"source_node_id": node["id"], "item_index": 0, "manual_sample": True},
            paired_item=None,
        )
        return [[sample]]
