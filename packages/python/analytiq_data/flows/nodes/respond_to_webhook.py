from __future__ import annotations

"""
Respond-to-webhook node (`flows.respond_to_webhook`).

When a webhook trigger is configured with `response_mode = respond_to_webhook`,
the inbound HTTP handler runs the flow synchronously and returns the response
payload captured by this node.
"""

from typing import Any

import analytiq_data as ad


class FlowsRespondToWebhookNode:
    key = "flows.respond_to_webhook"
    label = "Respond to Webhook"
    description = "Define the HTTP response for a synchronous webhook execution."
    category = "Generic"
    is_trigger = False
    is_merge = False
    min_inputs = 1
    max_inputs = 1
    outputs = 1
    output_labels = ["output"]
    icon_key = "respond_to_webhook"

    parameter_schema: dict[str, Any] = {
        "type": "object",
        "title": "Respond to Webhook",
        "additionalProperties": True,
        "properties": {
            "status_code": {
                "title": "Status code",
                "type": "integer",
                "minimum": 100,
                "maximum": 599,
                "default": 200,
                "x-ui-group": "Response",
            },
            "headers": {
                "title": "Headers",
                "type": "array",
                "default": [],
                "items": {},
                "x-ui-widget": "name_value_list",
                "x-ui-group": "Response",
            },
            "body_mode": {
                "title": "Body",
                "type": "string",
                "enum": ["json", "text", "none"],
                "default": "json",
                "x-ui-enum-names": ["JSON", "Text", "No body"],
                "x-ui-group": "Body",
            },
            "body_json": {
                "title": "JSON body",
                "type": "string",
                "default": "{\n  \"ok\": true\n}\n",
                "x-ui-widget": "json",
                "x-ui-show-when": {"field": "body_mode", "equals": "json"},
                "x-ui-group": "Body",
            },
            "body_text": {
                "title": "Text body",
                "type": "string",
                "default": "ok",
                "x-ui-widget": "textarea",
                "x-ui-show-when": {"field": "body_mode", "equals": "text"},
                "x-ui-group": "Body",
            },
            "content_type": {
                "title": "Content-Type",
                "type": "string",
                "default": "",
                "x-ui-placeholder": "application/json",
                "x-ui-group": "Body",
            },
        },
    }

    def validate_parameters(self, params: dict[str, Any]) -> list[str]:
        errs: list[str] = []
        sc = params.get("status_code")
        if sc is not None:
            try:
                c = int(sc)
            except (TypeError, ValueError):
                errs.append("status_code must be an integer")
            else:
                if not (100 <= c <= 599):
                    errs.append("status_code must be between 100 and 599")
        bm = params.get("body_mode")
        if bm not in ("json", "text", "none"):
            errs.append("body_mode must be json, text, or none")
        return errs

    async def execute(
        self,
        context: "ad.flows.ExecutionContext",
        node: dict[str, Any],
        inputs: list[list["ad.flows.FlowItem"]],
    ) -> list[list["ad.flows.FlowItem"]]:
        params = node.get("parameters") or {}
        if not isinstance(params, dict):
            params = {}

        status_code = int(params.get("status_code") or 200)
        headers_raw = params.get("headers") or []
        headers: dict[str, str] = {}
        if isinstance(headers_raw, list):
            for row in headers_raw:
                if not isinstance(row, dict):
                    continue
                n = row.get("name")
                if not isinstance(n, str) or not n.strip():
                    continue
                v = row.get("value")
                headers[n.strip()] = "" if v is None else str(v)

        mode = params.get("body_mode") or "json"
        content_type_any = params.get("content_type")
        content_type = content_type_any.strip() if isinstance(content_type_any, str) else ""

        body_bytes: bytes | None
        if mode == "none":
            body_bytes = None
        elif mode == "text":
            txt = params.get("body_text")
            body_bytes = (txt if isinstance(txt, str) else str(txt)).encode("utf-8")
            headers.setdefault("Content-Type", content_type or "text/plain; charset=utf-8")
        else:
            js = params.get("body_json")
            body_bytes = (js if isinstance(js, str) else str(js)).encode("utf-8")
            headers.setdefault("Content-Type", content_type or "application/json")

        # Store response envelope on the execution context so the inbound handler can return it.
        context.trigger_data["_webhook_response"] = {
            "status_code": status_code,
            "headers": headers,
            "body_bytes_utf8": None if body_bytes is None else body_bytes.decode("utf-8", errors="replace"),
            "body_is_none": body_bytes is None,
        }

        # Pass-through (no-op) output so the flow can continue if desired.
        return [inputs[0] if inputs else []]

