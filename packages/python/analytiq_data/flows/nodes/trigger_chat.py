from __future__ import annotations

"""Chat Trigger node (`flows.trigger.chat`) — conversational flow entry point."""

from typing import Any

import analytiq_data as ad


class FlowsChatTriggerNode:
    key = "flows.trigger.chat"
    label = "Chat Trigger"
    description = "Receives user messages over HTTP and starts a flow run."
    category = "Generic"
    palette_group = "trigger"
    is_trigger = True
    is_merge = False
    min_inputs = 0
    max_inputs = 0
    outputs = 1
    output_labels = ["output"]
    icon_key = "chat_trigger"
    type_version = 1
    experimental = True
    parameter_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "response_mode": {
                "type": "string",
                "enum": ["streaming", "last_node"],
                "default": "streaming",
                "x-ui-widget": "select",
            },
            "authentication": {
                "type": "string",
                "enum": ["none", "org_member", "api_key"],
                "default": "org_member",
                "x-ui-widget": "select",
            },
            "title": {"type": "string"},
            "subtitle": {"type": "string"},
            "input_placeholder": {"type": "string", "default": "Type your message…"},
            "initial_messages": {"type": "string", "x-ui-widget": "textarea"},
            "allow_file_uploads": {"type": "boolean", "default": False},
        },
        "additionalProperties": False,
    }

    def validate_parameters(self, params: dict[str, Any]) -> list[str]:
        return []

    async def execute(
        self,
        context: "ad.flows.ExecutionContext",
        node: dict[str, Any],
        inputs: list[list["ad.flows.FlowItem"]],
    ) -> list[list["ad.flows.FlowItem"]]:
        td = context.trigger_data or {}
        chat_input = td.get("chatInput")
        if not isinstance(chat_input, str):
            chat_input = ""
        session_id = td.get("session_id") or td.get("sessionId")
        item = ad.flows.FlowItem(
            json={"chatInput": chat_input, "action": "sendMessage"},
            binary={},
            meta={
                "source_node_id": node["id"],
                "item_index": 0,
                **({"session_id": session_id} if session_id else {}),
            },
            paired_item=None,
        )
        return [[item]]
