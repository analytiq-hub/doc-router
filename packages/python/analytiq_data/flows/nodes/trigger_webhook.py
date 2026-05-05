from __future__ import annotations

"""Webhook trigger node (`flows.trigger.webhook`) — emits an n8n-shaped flat JSON item per inbound HTTP request."""

from typing import Any

import analytiq_data as ad


def _webhook_trigger_item_json(trigger_data: dict[str, Any]) -> dict[str, Any]:
    """
    Public item shape for downstream nodes:

    ``headers``, ``params``, ``query``, ``body``, ``webhookUrl``, ``executionMode`` (``test`` or ``production``).
    When ``body_stashed_as_binary`` is set on the inbound trigger (raw body / binary content-type),
    ``body`` is always ``{}`` — bytes are only on ``FlowItem.binary``.
    Raw trigger metadata remains on ``ExecutionContext.trigger_data`` (execution docs / logs).
    """

    raw_headers = trigger_data.get("headers")
    headers: dict[str, str] = {}
    if isinstance(raw_headers, dict):
        for hk, hv in raw_headers.items():
            if not isinstance(hk, str):
                continue
            headers[hk.lower()] = "" if hv is None else str(hv)

    qraw = trigger_data.get("query")
    query: dict[str, Any] = dict(qraw) if isinstance(qraw, dict) else {}

    body_any = trigger_data.get("body")
    form_any = trigger_data.get("form")
    stashed_binary = bool(trigger_data.get("body_stashed_as_binary"))

    body_out: Any
    if stashed_binary:
        body_out = {}
    elif body_any is None:
        if isinstance(form_any, dict) and form_any:
            body_out = dict(form_any)
        else:
            body_out = {}
    elif isinstance(body_any, dict):
        body_out = dict(body_any)
    else:
        body_out = body_any

    wurl = trigger_data.get("webhook_url")
    webhook_url = str(wurl).strip() if isinstance(wurl, str) else ""

    wm = trigger_data.get("webhook_mode")
    execution_mode = "test" if wm == "test" else "production"

    # Reserved for future path/route params (routing is leaf-based today).
    params_out: dict[str, Any] = {}

    return {
        "headers": headers,
        "params": params_out,
        "query": query,
        "body": body_out,
        "webhookUrl": webhook_url,
        "executionMode": execution_mode,
    }


class FlowsWebhookTriggerNode:
    """
    Emits one item from an inbound webhook HTTP request stored in ``ExecutionContext.trigger_data``.

    ``trigger_data`` is produced by inbound webhook routes (see ``app.routes.flows`` ``_inbound_webhook_common``).
    File uploads are stored under ``binary_properties[].storage_id`` (GridFS ``flow_blobs``) and surfaced
    here as ``FlowItem.binary[property_name]`` with pass-by-reference ``BinaryRef`` objects.

    Tunable inbound behaviour aligns with common Webhook-trigger options (methods, whitelist, bots,
    raw body, synchronous response tweaks). Deferred execution responses (reply after the flow finishes)
    are not implemented yet—the ``respond_to_webhook`` / ``last_node`` modes enqueue runs but keep the
    same immediate acknowledgement as ``on_received``.
    """

    key = "flows.trigger.webhook"
    label = "Webhook"
    description = "Starts the flow when the webhook URL receives an HTTP request (JSON, form, or binary body)."
    category = "Generic"
    is_trigger = True
    is_merge = False
    min_inputs = 0
    max_inputs = 0
    outputs = 1
    output_labels = ["output"]
    icon_key = "webhook_trigger"
    parameter_schema: dict[str, Any] = {
        "type": "object",
        "title": "Webhook",
        "description": (
            "URL path segment routing on this DocRouter webhook is keyed by webhook id "
            "(the production URL `/v0/webhooks/{webhook_id}`). Treat `path` as a human label aligned "
            "with comparable tools; enforced HTTP verbs and security options mirror that pattern."
        ),
        "additionalProperties": True,
        "properties": {
            "webhook_leaf": {
                "title": "Path",
                "type": "string",
                "default": "",
                "description": (
                    "Public URL leaf for both production and test endpoints. "
                    "Should be a UUID; must be unique across the entire system."
                ),
                "x-ui-placeholder": "e.g. 550e8400-e29b-41d4-a716-446655440000",
                "x-ui-regex": r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$",
                "x-ui-regex-message": "Must be a UUID (xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx)",
                "x-ui-group": "Webhook URLs",
            },
            "http_method": {
                "title": "HTTP method",
                "type": "string",
                "enum": ["DELETE", "GET", "HEAD", "PATCH", "POST", "PUT"],
                "default": "GET",
                "description": "Single verb when multiple HTTP methods are off.",
                "x-ui-show-when": {"field": "multiple_methods", "equals": False},
                "x-ui-group": "HTTP",
            },
            "allowed_methods": {
                "title": "Allowed methods",
                "type": "string",
                "default": "",
                "description": (
                    'Comma-separated list (e.g. "GET, POST"). Leave empty while multiple-methods mode is '
                    "on to allow every verb the gateway accepts."
                ),
                "x-ui-widget": "textarea",
                "x-ui-placeholder": "GET, POST",
                "x-ui-show-when": {"field": "multiple_methods", "equals": True},
                "x-ui-group": "HTTP",
            },
            "response_mode": {
                "title": "Respond",
                "type": "string",
                "enum": ["on_received", "last_node", "respond_to_webhook"],
                "default": "on_received",
                "description": (
                    "When DocRouter acknowledges the inbound HTTP request. Deferred responses after the "
                    "flow completes require future engine support—the non-default modes enqueue runs "
                    "identically today."
                ),
                "x-ui-enum-names": [
                    "Immediately",
                    "When last node finishes (planned)",
                    "Using respond node (planned)",
                ],
                "x-ui-group": "Response",
            },
            "response_code": {
                "title": "Response status code",
                "type": "integer",
                "default": 200,
                "minimum": 100,
                "maximum": 599,
                "description": "HTTP status returned with the acknowledgement when responding immediately.",
                "x-ui-show-when": {"field": "response_mode", "equals": "on_received"},
                "x-ui-group": "Response",
            },
            "no_response_body": {
                "title": "No response body",
                "type": "boolean",
                "default": False,
                "description": "Acknowledge without a serialized body.",
                "x-ui-show-when": {"field": "response_mode", "equals": "on_received"},
                "x-ui-group": "Response",
            },
            "response_data": {
                "title": "Response data",
                "type": "string",
                "default": "",
                "description": (
                    'Custom acknowledgement payload (JSON string or plain text). Empty restores the '
                    'default `{ "execution_id": "…" }` JSON envelope.'
                ),
                "x-ui-widget": "textarea",
                "x-ui-show-when": {"field": "response_mode", "equals": "on_received"},
                "x-ui-group": "Response",
            },
            "response_content_type": {
                "title": "Response content type",
                "type": "string",
                "default": "",
                "description": "Optional Content-Type for the acknowledgement (derived when empty).",
                "x-ui-placeholder": "application/xml",
                "x-ui-show-when": {"field": "response_mode", "equals": "on_received"},
                "x-ui-group": "Response",
            },
            "response_headers": {
                "title": "Response headers",
                "type": "array",
                "description": "Optional headers added to the synchronous acknowledgement.",
                "default": [],
                "items": {},
                "x-ui-widget": "name_value_list",
                "x-ui-show-when": {"field": "response_mode", "equals": "on_received"},
                "x-ui-group": "Response",
            },
            "ignore_bots": {
                "title": "Ignore bots",
                "type": "boolean",
                "default": False,
                "description": "Reject heuristic bot / crawler traffic with HTTP 403 before enqueueing a run.",
                "x-ui-group": "Advanced",
            },
            "ip_whitelist": {
                "title": "IP whitelist",
                "type": "string",
                "default": "",
                "description": (
                    'Comma-separated substrings matched against forwarded / client IPs (similar to substring '
                    "checks in comparable tools)."
                ),
                "x-ui-widget": "textarea",
                "x-ui-placeholder": "127.0.0.1, 10.0.0.",
                "x-ui-group": "Advanced",
            },
            "raw_body": {
                "title": "Raw body",
                "type": "boolean",
                "default": False,
                "description": (
                    'For non-multipart requests, stash the uploaded bytes under the webhook binary field '
                    'instead of JSON/text parsing.'
                ),
                "x-ui-group": "Advanced",
            },
            "binary_property_name": {
                "title": "Binary property name",
                "type": "string",
                "default": "data",
                "description": (
                    'Output binary field/prefix used when multipart files or raw body uploads attach to GridFS.'
                ),
                "x-ui-group": "Advanced",
            },
        },
    }

    def validate_parameters(self, params: dict[str, Any]) -> list[str]:
        errs: list[str] = []
        rm = params.get("response_mode")
        if rm is not None and rm not in ("on_received", "last_node", "respond_to_webhook"):
            errs.append("response_mode must be on_received, last_node, or respond_to_webhook")

        rc = params.get("response_code")
        if rc is not None:
            try:
                code = int(rc)
            except (TypeError, ValueError):
                errs.append("response_code must be an integer HTTP status code")
            else:
                if not (100 <= code <= 599):
                    errs.append("response_code must be between 100 and 599")

        mul = params.get("multiple_methods")
        if mul is True or mul == "true":
            csv = params.get("allowed_methods")
            if csv is None or not str(csv).strip():
                return errs
            for seg in str(csv).split(","):
                s = seg.strip().upper()
                if not s:
                    continue
                if s not in {"GET", "HEAD", "POST", "PUT", "PATCH", "DELETE"}:
                    errs.append(f"allowed_methods references unknown verb {s!r}")
        else:
            hm = params.get("http_method")
            if hm and str(hm).strip():
                ss = str(hm).strip().upper()
                if ss not in {"GET", "HEAD", "POST", "PUT", "PATCH", "DELETE"}:
                    errs.append("http_method must be a standard HTTP verb")
        return errs

    async def execute(
        self,
        context: "ad.flows.ExecutionContext",
        node: dict[str, Any],
        inputs: list[list["ad.flows.FlowItem"]],
    ) -> list[list["ad.flows.FlowItem"]]:
        td_any = context.trigger_data or {}
        if not isinstance(td_any, dict):
            raise ValueError("flows.trigger.webhook requires trigger_data to be an object")

        params = node.get("parameters") if isinstance(node.get("parameters"), dict) else {}
        _bp = params.get("binary_property_name")
        binary_fallback = _bp.strip() if isinstance(_bp, str) and _bp.strip() else "data"

        bprops = td_any.get("binary_properties")
        if not isinstance(bprops, list):
            bprops = []

        binary_out: dict[str, ad.flows.BinaryRef] = {}
        for bp in bprops:
            if not isinstance(bp, dict):
                continue
            name = bp.get("name")
            if not isinstance(name, str) or not name.strip():
                name = binary_fallback
            sid = bp.get("storage_id")
            if not isinstance(sid, str) or not sid.strip():
                continue
            mime = bp.get("mime_type")
            if not isinstance(mime, str) or not mime.strip():
                mime = "application/octet-stream"
            fname = bp.get("file_name")
            if fname is not None and not isinstance(fname, str):
                fname = str(fname)
            fsize = bp.get("file_size")
            if fsize is not None and not isinstance(fsize, int):
                fsize = None
            binary_out[name] = ad.flows.BinaryRef(
                mime_type=mime,
                file_name=fname,
                storage_id=sid,
                file_size=fsize,
            )

        item = ad.flows.FlowItem(
            json=_webhook_trigger_item_json(td_any),
            binary=binary_out,
            meta={"source_node_id": node["id"], "item_index": 0},
            paired_item=None,
        )
        return [[item]]
