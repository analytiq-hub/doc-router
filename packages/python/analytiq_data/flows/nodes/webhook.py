from __future__ import annotations

"""Generic outbound webhook node implementation (`flows.webhook`)."""

import base64
from typing import Any

import analytiq_data as ad


def _serialize_binaries_for_json(binary: dict[str, "ad.flows.BinaryRef"]) -> dict[str, Any]:
    """Turn `FlowItem.binary` into JSON-safe dicts (bytes as base64)."""

    out: dict[str, Any] = {}
    for name, ref in binary.items():
        out[name] = {
            "mime_type": ref.mime_type,
            "file_name": ref.file_name,
            "storage_id": ref.storage_id,
            "data_b64": base64.standard_b64encode(ref.data).decode("ascii") if ref.data else None,
        }
    return out


class FlowsWebhookNode:
    """POST each input item (JSON only, or JSON + serialized binaries) and emit request/response."""

    key = "flows.webhook"
    label = "Webhook (generic)"
    description = "POSTs item JSON to a configured URL."
    category = "Generic"
    is_trigger = False
    is_merge = False
    min_inputs = 1
    max_inputs = 1
    outputs = 1
    output_labels = ["output"]
    parameter_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "url": {"type": "string"},
            "headers": {"type": "object", "additionalProperties": {"type": "string"}},
            "body_format": {
                "type": "string",
                "enum": ["item_json", "json_with_binary"],
                "description": "item_json: POST body is item.json only. json_with_binary: POST "
                '{"json": item.json, "binary": serialized BinaryRef map}.',
            },
        },
        "required": ["url"],
        "additionalProperties": False,
    }

    def validate_parameters(self, params: dict[str, Any]) -> list[str]:
        """Validate the configured URL is present and non-empty."""

        errs: list[str] = []
        if not isinstance(params.get("url"), str) or not params["url"].strip():
            errs.append("parameters.url must be a non-empty string")
        bf = params.get("body_format")
        if bf is not None and bf not in ("item_json", "json_with_binary"):
            errs.append("parameters.body_format must be item_json or json_with_binary")
        return errs

    async def execute(
        self,
        context: "ad.flows.ExecutionContext",
        node: dict[str, Any],
        inputs: list[list["ad.flows.FlowItem"]],
    ) -> list[list["ad.flows.FlowItem"]]:
        """POST each input item to the configured URL and collect responses."""

        url = (node.get("parameters") or {}).get("url")
        headers = (node.get("parameters") or {}).get("headers") or {}
        body_format = (node.get("parameters") or {}).get("body_format") or "item_json"
        import httpx

        out: list["ad.flows.FlowItem"] = []
        async with httpx.AsyncClient(timeout=30) as client:
            for it in inputs[0]:
                if body_format == "json_with_binary":
                    post_json: dict[str, Any] = {
                        "json": it.json,
                        "binary": _serialize_binaries_for_json(it.binary),
                    }
                else:
                    post_json = it.json
                resp = await client.post(url, json=post_json, headers=headers or {})
                out.append(
                    ad.flows.FlowItem(
                        json={
                            "request": post_json,
                            "response": {"status_code": resp.status_code, "body": resp.text},
                        },
                        binary={},
                        meta=it.meta,
                        paired_item=it.paired_item,
                    )
                )
        return [out]

