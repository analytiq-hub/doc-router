"""Gmail flow node."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import analytiq_data as ad

from .operations import execute_gmail_item

_SCHEMA_PATH = Path(__file__).resolve().parent / "parameter.schema.json"


def _load_parameter_schema() -> dict[str, Any]:
    return json.loads(_SCHEMA_PATH.read_text(encoding="utf-8"))


class FlowsGmailNode:
    """Send and fetch Gmail messages via OAuth2 (``gmailOAuth2``)."""

    key = "flows.gmail"
    label = "Gmail"
    description = "Consume the Gmail API (message, label, draft, and thread operations)."
    category = "input"
    palette_group = "app"
    is_trigger = False
    is_merge = False
    min_inputs = 1
    max_inputs = 1
    outputs = 1
    output_labels = ["main"]
    icon_key = "gmail"
    type_version = 2
    parameter_schema = _load_parameter_schema()
    credential_slots = [
        {
            "slot": "gmailOAuth2",
            "label": "Credential to connect with",
            "required": True,
            "docrouter_binding": "organization_credential_kind:gmailOAuth2",
        },
    ]

    def validate_parameters(self, params: dict[str, Any]) -> list[str]:
        return []

    async def execute(
        self,
        context: "ad.flows.ExecutionContext",
        node: dict[str, Any],
        inputs: list[list["ad.flows.FlowItem"]],
    ) -> list[list["ad.flows.FlowItem"]]:
        slot = inputs[0] if inputs else []
        params = node.get("parameters") if isinstance(node.get("parameters"), dict) else {}
        out: list["ad.flows.FlowItem"] = []
        for i, item in enumerate(slot):
            try:
                result = await execute_gmail_item(
                    context, node, params, item, item_index=i
                )
                out.append(result)
            except Exception as e:
                if not node.get("continueOnFail"):
                    raise
                out.append(
                    ad.flows.FlowItem(
                        json={"error": str(e)},
                        binary=dict(item.binary),
                        meta=dict(item.meta),
                    )
                )
        return [out]
