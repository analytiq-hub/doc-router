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
                "title": "Response mode",
                "description": "Streaming returns NDJSON token events as the agent runs; Last node waits and returns the full reply as JSON.",
                "type": "string",
                "enum": ["streaming", "last_node"],
                "default": "streaming",
                "x-ui-widget": "select",
                "x-ui-enum-names": ["Streaming", "Last node"],
            },
            "title": {
                "title": "Title",
                "description": "Heading shown in the chat panel and future embed UI. Defaults to the flow name when empty.",
                "type": "string",
            },
            "subtitle": {
                "title": "Subtitle",
                "description": "Optional secondary line under the title in the chat UI.",
                "type": "string",
            },
            "input_placeholder": {
                "title": "Input placeholder",
                "description": "Placeholder text in the message input field.",
                "type": "string",
                "default": "Type your message…",
            },
            "initial_messages": {
                "title": "Initial messages",
                "description": "Newline-separated greeting lines shown before the first user turn in Test chat. Also used as fallback chatInput when running the trigger via manual execute.",
                "type": "string",
                "x-ui-widget": "textarea",
            },
            "allow_file_uploads": {
                "title": "Allow file uploads",
                "description": "Accept file attachments with chat messages (not yet implemented).",
                "type": "boolean",
                "default": False,
            },
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
        params = node.get("parameters") or {}
        chat_input = resolve_chat_input(
            context.trigger_data or {},
            params,
            execution_mode=str(context.mode or "manual"),
        )
        td = context.trigger_data or {}
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


def resolve_chat_input(
    trigger_data: dict[str, Any],
    node_params: dict[str, Any],
    *,
    execution_mode: str,
) -> str:
    """Resolve chatInput from trigger payload, with manual-run editor fallback."""

    raw = trigger_data.get("chatInput")
    if isinstance(raw, str) and raw.strip():
        return raw.strip()
    if execution_mode == "manual":
        initial = node_params.get("initial_messages")
        if isinstance(initial, str) and initial.strip():
            return initial.strip()
    if isinstance(raw, str):
        return raw
    return ""
