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
                "x-ui-group": "Chat UI",
            },
            "subtitle": {
                "title": "Subtitle",
                "description": "Optional secondary line under the title in the chat UI.",
                "type": "string",
                "x-ui-group": "Chat UI",
            },
            "initial_messages": {
                "title": "Initial messages",
                "description": "Newline-separated greeting lines shown before the first user turn in Test chat.",
                "type": "string",
                "x-ui-widget": "textarea",
                "x-ui-group": "Chat UI",
            },
            "input_placeholder": {
                "title": "Input placeholder",
                "description": "Placeholder text in the message input field.",
                "type": "string",
                "default": "Type your message…",
                "x-ui-group": "Chat UI",
            },
            "manual_chat_input": {
                "title": "Manual run prompt",
                "description": (
                    "Default chatInput when executing the flow manually (Execute flow) with no chatInput. "
                    "Not used by Test chat or the chat HTTP API."
                ),
                "type": "string",
                "x-ui-widget": "textarea",
                "x-ui-group": "Manual run",
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
        manual = node_params.get("manual_chat_input")
        if isinstance(manual, str) and manual.strip():
            return manual.strip()
    if isinstance(raw, str):
        return raw
    return ""
