from __future__ import annotations

from typing import Any

from ..context import ExecutionContext
from ..items import FlowItem


class FlowsWebhookNode:
    key = "flows.webhook"
    label = "Webhook (generic)"
    description = "POSTs item JSON to a configured URL."
    category = "Generic"
    is_trigger = False
    min_inputs = 1
    max_inputs = 1
    outputs = 1
    output_labels = ["output"]
    parameter_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "url": {"type": "string"},
            "headers": {"type": "object", "additionalProperties": {"type": "string"}},
        },
        "required": ["url"],
        "additionalProperties": False,
    }

    def validate_parameters(self, params: dict[str, Any]) -> list[str]:
        if not isinstance(params.get("url"), str) or not params["url"].strip():
            return ["parameters.url must be a non-empty string"]
        return []

    async def execute(
        self,
        context: ExecutionContext,
        node: dict[str, Any],
        inputs: list[list[FlowItem]],
    ) -> list[list[FlowItem]]:
        url = (node.get("parameters") or {}).get("url")
        headers = (node.get("parameters") or {}).get("headers") or {}
        out: list[FlowItem] = []
        for it in inputs[0]:
            resp = await context.services.send_webhook(url=url, payload=it.json, headers=headers)
            out.append(
                FlowItem(
                    json={"request": it.json, "response": resp},
                    binary={},
                    meta=it.meta,
                    paired_item=it.paired_item,
                )
            )
        return [out]

