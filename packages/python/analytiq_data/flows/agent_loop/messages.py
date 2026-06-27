"""Build user/system messages for the flow agent loop."""

from __future__ import annotations

import json

from analytiq_data.flows.agent_loop.constants import ALL_ITEMS_PROMPT_MAX_BYTES
from analytiq_data.flows.errors import FlowValidationError

DEFAULT_SYSTEM_MESSAGE = (
    "You are an AI agent in a DocRouter flow. Use the provided tools when they help "
    "answer the user request. Reply concisely when no tools are needed."
)


def build_user_message(
    item_json: dict,
    *,
    prompt_source: str,
    prompt_field: str,
    prompt_text: str,
) -> str:
    if prompt_source == "fixed":
        return prompt_text
    if prompt_source == "chat_trigger":
        value = item_json.get("chatInput")
        if not isinstance(value, str) or not value.strip():
            raise FlowValidationError("chatInput is required from Chat Trigger")
        return value
    return str(item_json.get(prompt_field, ""))


def build_all_items_user_message(items_json: list[dict]) -> str:
    payload = json.dumps(items_json, ensure_ascii=False)
    if len(payload.encode("utf-8")) > ALL_ITEMS_PROMPT_MAX_BYTES:
        raise FlowValidationError("all_items prompt exceeds maximum size")
    return (
        "Process the following items as a batch. Each element is one input item's json payload.\n\n"
        f"<items>\n{payload}\n</items>"
    )
