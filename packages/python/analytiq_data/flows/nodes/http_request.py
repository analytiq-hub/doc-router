from __future__ import annotations

"""Outbound HTTP Request node (`flows.http_request`)."""

import json
import urllib.parse
from typing import Any

import httpx

import analytiq_data as ad


def _json_keypair_value(value: Any) -> Any:
    """Keep JSON-serializable values from expressions; stringify everything else."""
    if value is None or isinstance(value, (dict, list, bool, int, float)):
        return value
    return str(value)


class FlowsHttpRequestNode:
    """Perform an HTTP request with optional header/query credential slots."""

    key = "flows.http_request"
    label = "HTTP Request"
    description = "Make an HTTP request to any URL."
    category = "Generic"
    is_trigger = False
    is_merge = False
    min_inputs = 1
    max_inputs = 1
    outputs = 1
    output_labels = ["output"]
    icon_key = "http_request"
    batch_execute_inputs = False

    credential_slots = [
        {
            "slot": "httpHeaderAuth",
            "label": "Header Auth",
            "required": False,
            "docrouter_binding": "organization_credential_kind:httpHeaderAuth",
        },
        {
            "slot": "httpQueryAuth",
            "label": "Query Auth",
            "required": False,
            "docrouter_binding": "organization_credential_kind:httpQueryAuth",
        },
    ]

    parameter_schema: dict[str, Any] = {
        "type": "object",
        "additionalProperties": False,
        "required": ["method", "url"],
        "properties": {
            "method": {
                "type": "string",
                "enum": ["GET", "POST", "PUT", "PATCH", "DELETE"],
                "default": "GET",
                "x-ui-group": "Request",
            },
            "url": {
                "type": "string",
                "minLength": 1,
                "description": "Absolute http(s) URL or =expression. Evaluated per item.",
                "default": "",
                "x-ui-group": "Request",
                "x-ui-placeholder": "https://… or =expression",
                "x-ui-regex": "^https?://\\S+$",
                "x-ui-regex-message": "Must be a valid HTTP/S URL",
            },
            "query_params": {
                "type": "array",
                "x-ui-widget": "name_value_list",
                "x-ui-group": "Request",
                "items": {
                    "type": "object",
                    "required": ["name", "value"],
                    "properties": {
                        "name": {"type": "string"},
                        "value": {"type": "string"},
                    },
                    "additionalProperties": False,
                },
                "default": [],
            },
            "headers": {
                "type": "array",
                "x-ui-widget": "name_value_list",
                "x-ui-group": "Request",
                "items": {
                    "type": "object",
                    "required": ["name", "value"],
                    "properties": {
                        "name": {"type": "string"},
                        "value": {"type": "string"},
                    },
                    "additionalProperties": False,
                },
                "default": [],
            },
            "body_mode": {
                "type": "string",
                "enum": ["none", "json", "json_keypair", "form_urlencoded", "raw"],
                "default": "none",
                "x-ui-group": "Body",
            },
            "body_json": {
                "type": "string",
                "default": "",
                "x-ui-widget": "textarea",
                "x-ui-group": "Body",
                "x-ui-show-when": {"field": "body_mode", "in": ["json"]},
                "x-ui-require-when": {"field": "body_mode", "in": ["json"]},
                "x-ui-require-message": "JSON body cannot be empty for this mode",
            },
            "body_params": {
                "type": "array",
                "x-ui-widget": "name_value_list",
                "x-ui-group": "Body",
                "x-ui-show-when": {"field": "body_mode", "in": ["json_keypair", "form_urlencoded"]},
                "items": {
                    "type": "object",
                    "required": ["name", "value"],
                    "properties": {
                        "name": {"type": "string"},
                        "value": {"type": "string"},
                    },
                    "additionalProperties": False,
                },
                "default": [],
            },
            "body_raw": {
                "type": "string",
                "default": "",
                "x-ui-widget": "textarea",
                "x-ui-group": "Body",
                "x-ui-show-when": {"field": "body_mode", "equals": "raw"},
                "x-ui-require-when": {"field": "body_mode", "equals": "raw"},
                "x-ui-require-message": "Raw body cannot be empty for this mode",
            },
            "body_content_type": {
                "type": "string",
                "default": "text/plain",
                "description": "Content-Type header for raw body mode.",
                "x-ui-group": "Body",
                "x-ui-show-when": {"field": "body_mode", "equals": "raw"},
            },
            "full_response": {
                "type": "boolean",
                "default": False,
                "description": "Include status_code and headers in the output item.",
                "x-ui-group": "Options",
            },
            "never_error": {
                "type": "boolean",
                "default": False,
                "description": "Treat non-2xx responses as normal output instead of errors.",
                "x-ui-group": "Options",
            },
            "follow_redirects": {
                "type": "boolean",
                "default": True,
                "x-ui-group": "Options",
            },
            "timeout_seconds": {
                "type": "number",
                "default": 30,
                "minimum": 1,
                "x-ui-group": "Options",
            },
        },
    }

    def validate_parameters(self, params: dict[str, Any]) -> list[str]:
        errs: list[str] = []
        method = params.get("method") or "GET"
        if method not in ("GET", "POST", "PUT", "PATCH", "DELETE"):
            errs.append(f"method must be one of GET POST PUT PATCH DELETE, got {method!r}")
        ts = params.get("timeout_seconds")
        if ts is not None and (not isinstance(ts, (int, float)) or ts <= 0):
            errs.append("timeout_seconds must be a positive number")
        return errs

    async def execute(
        self,
        context: "ad.flows.ExecutionContext",
        node: dict[str, Any],
        inputs: list[list["ad.flows.FlowItem"]],
    ) -> list[list["ad.flows.FlowItem"]]:
        params_raw = node.get("parameters") or {}
        slot0 = inputs[0] if inputs else []
        if not slot0:
            return [[]]
        item = slot0[0]

        params = ad.flows.resolve_parameters(
            params_raw,
            item=item,
            run_data=context.run_data,
            input_context=ad.flows.materialize_input_context(
                inputs, input_index=0, item_index=0
            ),
            execution_refs={
                "execution_id": context.execution_id,
                "flow_id": context.flow_id,
                "flow_revid": context.flow_revid,
            },
        )

        method = str(params.get("method") or "GET").upper()
        url = str(params.get("url") or "").strip()
        timeout = float(params.get("timeout_seconds") or 30)
        follow_redirects = bool(params.get("follow_redirects", True))
        never_error = bool(params.get("never_error", False))
        full_response = bool(params.get("full_response", False))

        headers: dict[str, str] = {}
        for h in params.get("headers") or []:
            if isinstance(h, dict) and h.get("name"):
                headers[str(h["name"])] = str(h.get("value", ""))

        query: dict[str, str] = {}
        for q in params.get("query_params") or []:
            if isinstance(q, dict) and q.get("name"):
                query[str(q["name"])] = str(q.get("value", ""))

        bindings = node.get("credentials") or {}
        org_id = context.organization_id
        if bindings.get("httpHeaderAuth"):
            hf = await ad.flows.fetch_credential_fields(
                org_id, str(bindings["httpHeaderAuth"])
            )
            hn, hv = hf.get("name"), hf.get("value")
            if hn and hv is not None:
                headers[str(hn)] = str(hv)
        if bindings.get("httpQueryAuth"):
            qf = await ad.flows.fetch_credential_fields(
                org_id, str(bindings["httpQueryAuth"])
            )
            qn, qv = qf.get("name"), qf.get("value")
            if qn and qv is not None:
                query[str(qn)] = str(qv)

        body_mode = params.get("body_mode") or "none"
        content: bytes | None = None
        content_type: str | None = None

        if body_mode == "json":
            raw = params.get("body_json")
            body_obj = _coerce_json_body(raw)
            content = json.dumps(body_obj).encode()
            content_type = "application/json"
            headers.setdefault("Content-Type", content_type)
        elif body_mode == "json_keypair":
            obj = {
                str(p["name"]): _json_keypair_value(p.get("value", ""))
                for p in (params.get("body_params") or [])
                if isinstance(p, dict) and p.get("name") is not None
            }
            content = json.dumps(obj).encode()
            content_type = "application/json"
            headers.setdefault("Content-Type", content_type)
        elif body_mode == "form_urlencoded":
            pairs = {
                str(p["name"]): str(p.get("value", ""))
                for p in (params.get("body_params") or [])
                if isinstance(p, dict) and p.get("name") is not None
            }
            content = urllib.parse.urlencode(pairs).encode()
            content_type = "application/x-www-form-urlencoded"
            headers.setdefault("Content-Type", content_type)
        elif body_mode == "raw":
            content = str(params.get("body_raw") or "").encode()
            content_type = str(params.get("body_content_type") or "text/plain")
            headers.setdefault("Content-Type", content_type)

        async with httpx.AsyncClient(
            timeout=timeout,
            follow_redirects=follow_redirects,
        ) as client:
            resp = await client.request(
                method=method,
                url=url,
                params=query or None,
                headers=headers or None,
                content=content,
            )

        if not never_error and resp.status_code >= 400:
            raise RuntimeError(
                f"HTTP {resp.status_code} from {method} {url}: {resp.text[:200]}"
            )

        resp_body: Any
        ct = resp.headers.get("content-type", "")
        if "application/json" in ct:
            try:
                resp_body = resp.json()
            except Exception:
                resp_body = resp.text
        else:
            resp_body = resp.text

        out_json: dict[str, Any] = {"body": resp_body}
        if full_response:
            out_json["status_code"] = resp.status_code
            out_json["headers"] = dict(resp.headers)

        return [
            [
                ad.flows.FlowItem(
                    json=out_json,
                    binary={},
                    meta={"source_node_id": node["id"], "item_index": 0},
                    paired_item=None,
                )
            ]
        ]


def _coerce_json_body(raw: Any) -> Any:
    """Turn body_json parameter into a JSON-serializable value."""

    if raw is None or raw == "":
        return {}
    if isinstance(raw, (dict, list)):
        return raw
    if isinstance(raw, str):
        s = raw.strip()
        if not s:
            return {}
        try:
            return json.loads(s)
        except json.JSONDecodeError:
            return raw
    return raw
