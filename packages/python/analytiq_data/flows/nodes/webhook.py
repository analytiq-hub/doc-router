from __future__ import annotations

"""Generic outbound webhook node implementation (`flows.webhook`)."""

from typing import Any

import analytiq_data as ad


class FlowsWebhookNode:
    """POST each input item JSON to a configured URL and emit request/response."""

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
        """Validate the configured URL is present and non-empty."""

        if not isinstance(params.get("url"), str) or not params["url"].strip():
            return ["parameters.url must be a non-empty string"]
        return []

    async def execute(
        self,
        context: "ad.flows.ExecutionContext",
        node: dict[str, Any],
        inputs: list[list["ad.flows.FlowItem"]],
    ) -> list[list["ad.flows.FlowItem"]]:
        """POST each input item to the configured URL and collect responses."""

        url = (node.get("parameters") or {}).get("url")
        headers = (node.get("parameters") or {}).get("headers") or {}
        import httpx

        out: list["ad.flows.FlowItem"] = []
        async with httpx.AsyncClient(timeout=30) as client:
            for it in inputs[0]:
                resp = await client.post(url, json=it.json, headers=headers or {})
                out.append(
                    ad.flows.FlowItem(
                        json={
                            "request": it.json,
                            "response": {"status_code": resp.status_code, "body": resp.text},
                        },
                        binary={},
                        meta=it.meta,
                        paired_item=it.paired_item,
                    )
                )
        return [out]

