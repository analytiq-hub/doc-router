from __future__ import annotations

"""Outbound HTTP Request node (`flows.http_request`)."""

import json
import logging
import re
import urllib.parse
from typing import Any

import httpx

import analytiq_data as ad

logger = logging.getLogger(__name__)


def _exec_log(ctx: "ad.flows.ExecutionContext") -> logging.Logger:
    """Prefer the flow worker logger when attached so errors land with other flow_run lines."""

    return ctx.logger if ctx.logger is not None else logger


def _inbound_row_hint(item: "ad.flows.FlowItem") -> str:
    """Explain which upstream row this invocation uses (engine runs HTTP once per inbound item)."""

    meta = item.meta if isinstance(item.meta, dict) else {}
    ix = meta.get("item_index")
    if isinstance(ix, int):
        return f" This invocation is for upstream output row index {ix} (HTTP Request runs once per inbound item; each row must yield a valid http(s) URL)."
    return " This node runs once per inbound item; ensure the URL resolves to http(s) for every row or filter upstream."


def _json_keypair_value(value: Any) -> Any:
    """Keep JSON-serializable values from expressions; stringify everything else."""
    if value is None or isinstance(value, (dict, list, bool, int, float)):
        return value
    return str(value)


_ALLOWED_HTTP_METHODS = frozenset(
    {"GET", "HEAD", "OPTIONS", "POST", "PUT", "PATCH", "DELETE"}
)


def _parse_json_object_param(raw: Any, *, field_label: str) -> dict[str, Any]:
    """Resolve optional JSON object parameter (string from UI or dict from expressions)."""

    if raw is None or raw == "":
        return {}
    if isinstance(raw, dict):
        return dict(raw)
    if isinstance(raw, str):
        s = raw.strip()
        if not s:
            return {}
        try:
            parsed = json.loads(s)
        except json.JSONDecodeError as e:
            raise ValueError(f"{field_label} must be valid JSON object text: {e}") from e
        if not isinstance(parsed, dict):
            raise ValueError(f"{field_label} must be a JSON object, got {type(parsed).__name__}")
        return parsed
    raise ValueError(f"{field_label} must be a JSON object or string, got {type(raw).__name__}")


def _merge_flat_json_into_str_dict(parsed: dict[str, Any], dest: dict[str, str]) -> None:
    """Merge JSON object keys into a string-only header/query map (n8n-style JSON overlay)."""

    for k, v in parsed.items():
        dest[str(k)] = "" if v is None else str(v)


def _proxy_parameter_syntax_ok(proxy: str) -> bool:
    """Lightweight check for validate_parameters (full SSRF check runs in execute)."""

    p = urllib.parse.urlparse(proxy.strip())
    return p.scheme in ("http", "https") and bool(p.hostname)


# Substrings matched against ``Content-Type`` (lowercased) — see ``docs/docrouter_binary.md`` §9.
_BINARY_RESPONSE_CONTENT_TYPE_MARKERS = (
    "application/pdf",
    "image/",
    "audio/",
    "video/",
    "application/zip",
    "application/x-zip-compressed",
    "application/gzip",
    "application/x-gzip",
    "application/octet-stream",
)


def _response_content_type_is_binary(content_type_header: str) -> bool:
    h = (content_type_header or "").lower()
    return any(marker in h for marker in _BINARY_RESPONSE_CONTENT_TYPE_MARKERS)


def _extract_filename_from_content_disposition(headers: httpx.Headers) -> str | None:
    """Best-effort ``filename`` / ``filename*`` from ``Content-Disposition``."""

    cd = headers.get("content-disposition") or ""
    if not cd:
        return None
    m = re.search(r"filename\*=(?:UTF-8''|utf-8'')([^;]+)", cd, re.IGNORECASE)
    if m:
        raw = m.group(1).strip().strip('"').strip()
        decoded = urllib.parse.unquote(raw)
        return decoded or None
    m = re.search(r'filename\s*=\s*"((?:\\.|[^"\\])*)"', cd, re.IGNORECASE)
    if m:
        return m.group(1).replace('\\"', '"').strip() or None
    m = re.search(r"filename\s*=\s*([^;\s]+)", cd, re.IGNORECASE)
    if m:
        raw = m.group(1).strip().strip('"')
        return urllib.parse.unquote(raw) or None
    return None


class FlowsHttpRequestNode:
    """Perform an HTTP request with optional header/query credential slots."""

    key = "flows.http_request"
    label = "HTTP Request"
    description = "Make an HTTP request to any URL."
    category = "Generic"
    palette_group = "core"
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
            "slot": "httpBearerAuth",
            "label": "Bearer Auth",
            "required": False,
            "docrouter_binding": "organization_credential_kind:httpBearerAuth",
        },
        {
            "slot": "httpBasicAuth",
            "label": "Basic Auth",
            "required": False,
            "docrouter_binding": "organization_credential_kind:httpBasicAuth",
        },
        {
            "slot": "httpDigestAuth",
            "label": "Digest Auth",
            "required": False,
            "docrouter_binding": "organization_credential_kind:httpDigestAuth",
        },
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
                "enum": ["GET", "HEAD", "OPTIONS", "POST", "PUT", "PATCH", "DELETE"],
                "default": "GET",
                "x-ui-group": "Request",
            },
            "url": {
                "type": "string",
                "minLength": 1,
                "description": "Absolute http(s) URL or =expression (_json, etc.). Evaluated once per inbound item: if the upstream node emits N rows, this node issues up to N requests using each row's JSON.",
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
                        "value": {},
                    },
                    "additionalProperties": False,
                },
                "default": [],
            },
            "query_json": {
                "type": "string",
                "default": "",
                "description": "Optional JSON object merged after query_params (same keys overwrite). Use for dynamic query objects or =expression.",
                "x-ui-widget": "json",
                "x-ui-group": "Request",
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
                        "value": {},
                    },
                    "additionalProperties": False,
                },
                "default": [],
            },
            "headers_json": {
                "type": "string",
                "default": "",
                "description": "Optional JSON object merged after headers (same keys overwrite). Credential headers apply after this.",
                "x-ui-widget": "json",
                "x-ui-group": "Request",
            },
            "body_mode": {
                "type": "string",
                "enum": [
                    "none",
                    "json",
                    "json_keypair",
                    "form_urlencoded",
                    "raw",
                    "binary",
                    "multipart_form",
                ],
                "default": "none",
                "x-ui-group": "Body",
            },
            "body_json": {
                "type": "string",
                "default": "",
                "description": "JSON text when body mode is JSON. Required (non-empty) in that mode; use =expression for dynamic values.",
                "x-ui-widget": "json",
                "x-ui-group": "Body",
                "x-ui-show-when": {"field": "body_mode", "in": ["json"]},
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
                        "value": {},
                    },
                    "additionalProperties": False,
                },
                "default": [],
            },
            "body_raw": {
                "type": "string",
                "default": "",
                "description": "Raw body bytes when body mode is raw. Required (non-empty) in that mode.",
                "x-ui-widget": "textarea",
                "x-ui-group": "Body",
                "x-ui-show-when": {"field": "body_mode", "equals": "raw"},
            },
            "body_content_type": {
                "type": "string",
                "default": "text/plain",
                "description": "Content-Type header for raw body mode.",
                "x-ui-group": "Body",
                "x-ui-show-when": {"field": "body_mode", "equals": "raw"},
            },
            "binary_property_name": {
                "type": "string",
                "default": "data",
                "description": "Name of the incoming `item.binary` property to upload.",
                "x-ui-group": "Body",
                "x-ui-show-when": {"field": "body_mode", "in": ["binary", "multipart_form"]},
            },
            "multipart_file_field_name": {
                "type": "string",
                "default": "file",
                "description": "Multipart form field name to use for the uploaded binary.",
                "x-ui-group": "Body",
                "x-ui-show-when": {"field": "body_mode", "equals": "multipart_form"},
            },
            "multipart_fields": {
                "type": "array",
                "x-ui-widget": "name_value_list",
                "x-ui-group": "Body",
                "x-ui-show-when": {"field": "body_mode", "equals": "multipart_form"},
                "items": {
                    "type": "object",
                    "required": ["name", "value"],
                    "properties": {
                        "name": {"type": "string"},
                        "value": {},
                    },
                    "additionalProperties": False,
                },
                "default": [],
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
            "max_redirects": {
                "type": "integer",
                "default": 20,
                "minimum": 1,
                "description": "Maximum redirect hops when follow_redirects is enabled (matches httpx default).",
                "x-ui-group": "Options",
            },
            "proxy": {
                "type": "string",
                "default": "",
                "description": "Optional HTTP(S) proxy URL (e.g. http://proxy:8080). Validated against the same SSRF rules as the request URL.",
                "x-ui-group": "Options",
            },
            "verify_tls": {
                "type": "boolean",
                "default": True,
                "description": "Verify TLS certificates. Disable only for trusted debug endpoints.",
                "x-ui-group": "Options",
            },
            "response_format": {
                "type": "string",
                "enum": ["auto", "json", "text", "binary"],
                "default": "auto",
                "description": "How to interpret the response body: auto (Content-Type heuristics), json, text, or always store raw bytes as BinaryRef.",
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
        method = str(params.get("method") or "GET").upper()
        if method not in _ALLOWED_HTTP_METHODS:
            errs.append(
                f"method must be one of {' '.join(sorted(_ALLOWED_HTTP_METHODS))}, got {method!r}"
            )
        ts = params.get("timeout_seconds")
        if ts is not None and (not isinstance(ts, (int, float)) or ts <= 0):
            errs.append("timeout_seconds must be a positive number")
        mr = params.get("max_redirects")
        if mr is not None and (
            not isinstance(mr, int) or isinstance(mr, bool) or mr < 1
        ):
            errs.append("max_redirects must be an integer >= 1")
        for jname in ("query_json", "headers_json"):
            raw = params.get(jname)
            if raw is None or raw == "":
                continue
            try:
                _parse_json_object_param(raw, field_label=jname)
            except ValueError as e:
                errs.append(str(e))
        body_mode = params.get("body_mode", "none")
        if body_mode == "json" and not str(params.get("body_json") or "").strip():
            errs.append("body_json must not be empty when body mode is json")
        if body_mode == "raw":
            if not str(params.get("body_raw") or "").strip():
                errs.append("body_raw must not be empty when body mode is raw")
            if not str(params.get("body_content_type") or "").strip():
                errs.append("body_content_type must not be empty when body mode is raw")
        if body_mode in ("binary", "multipart_form"):
            if not str(params.get("binary_property_name") or "").strip():
                errs.append("binary_property_name must not be empty when body mode uploads binary")
        if body_mode == "multipart_form":
            if not str(params.get("multipart_file_field_name") or "").strip():
                errs.append("multipart_file_field_name must not be empty when body mode is multipart_form")
        px = str(params.get("proxy") or "").strip()
        if px and not _proxy_parameter_syntax_ok(px):
            errs.append("proxy must be a valid http(s) URL with a hostname")
        return errs

    async def execute(
        self,
        context: "ad.flows.ExecutionContext",
        node: dict[str, Any],
        inputs: list[list["ad.flows.FlowItem"]],
    ) -> list[list["ad.flows.FlowItem"]]:
        # Parameters are already resolved by the engine (per-item ``resolve_parameters``).
        params = node.get("parameters") or {}
        slot0 = inputs[0] if inputs else []
        if not slot0:
            return [[]]
        item = slot0[0]

        method = str(params.get("method") or "GET").upper()
        url = str(params.get("url") or "").strip()
        exec_log = _exec_log(context)
        nid = node.get("id", "?")
        n_disp = ad.flows.node_name(node)

        if not url:
            msg = "HTTP Request url is empty after evaluating parameters." + _inbound_row_hint(item)
            exec_log.error(
                f"flows.http_request invalid url node_name={n_disp!r} node_id={nid} execution_id={context.execution_id} "
                f"flow_id={context.flow_id} organization_id={context.organization_id}: {msg}"
            )
            raise RuntimeError(msg)
        url_lc = url.lower()
        if not (url_lc.startswith("http://") or url_lc.startswith("https://")):
            msg = (
                "HTTP Request url must be an absolute URL with http:// or https:// "
                f"(after evaluation: {url[:500]!r})."
            ) + _inbound_row_hint(item)
            exec_log.error(
                f"flows.http_request invalid url node_name={n_disp!r} node_id={nid} execution_id={context.execution_id} "
                f"flow_id={context.flow_id} organization_id={context.organization_id}: {msg}"
            )
            raise RuntimeError(msg)

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

        try:
            qj = _parse_json_object_param(params.get("query_json"), field_label="query_json")
        except ValueError as e:
            raise RuntimeError(str(e)) from None
        _merge_flat_json_into_str_dict(qj, query)

        try:
            hj = _parse_json_object_param(params.get("headers_json"), field_label="headers_json")
        except ValueError as e:
            raise RuntimeError(str(e)) from None
        _merge_flat_json_into_str_dict(hj, headers)

        bindings = node.get("credentials") or {}
        org_id = context.organization_id
        credential_body: dict[str, str] = {}
        auth_basic: tuple[str, str] | None = None
        auth_digest: tuple[str, str] | None = None
        for slot_spec in FlowsHttpRequestNode.credential_slots:
            slot = slot_spec.get("slot")
            if not slot or not isinstance(slot, str):
                continue
            cred_id = bindings.get(slot)
            if not cred_id:
                continue
            kind, cfields = await ad.flows.fetch_credential_kind_and_fields(
                org_id, str(cred_id)
            )
            inj = kind.get("inject") if isinstance(kind.get("inject"), dict) else None
            if inj and (
                inj.get("headers") or inj.get("query_params") or inj.get("body")
            ):
                rinj = ad.flows.render_credential_inject(kind, cfields)
                headers.update(rinj["headers"])
                query.update(rinj["query_params"])
                credential_body.update(rinj["body"])
                continue
            if slot == "httpHeaderAuth":
                hn, hv = cfields.get("name"), cfields.get("value")
                if hn and hv is not None:
                    headers[str(hn)] = str(hv)
            elif slot == "httpQueryAuth":
                qn, qv = cfields.get("name"), cfields.get("value")
                if qn and qv is not None:
                    query[str(qn)] = str(qv)
            elif slot == "httpBasicAuth":
                bu, bp = cfields.get("user"), cfields.get("password")
                if bu is not None and bp is not None:
                    auth_basic = (str(bu), str(bp))
            elif slot == "httpDigestAuth":
                du, dp = cfields.get("user"), cfields.get("password")
                if du is not None and dp is not None:
                    auth_digest = (str(du), str(dp))

        if auth_basic is not None and auth_digest is not None:
            raise RuntimeError(
                "HTTP Request cannot bind both httpBasicAuth and httpDigestAuth credentials."
            )
        req_auth: httpx.Auth | None = None
        if auth_basic is not None:
            req_auth = httpx.BasicAuth(auth_basic[0], auth_basic[1])
        elif auth_digest is not None:
            req_auth = httpx.DigestAuth(auth_digest[0], auth_digest[1])

        body_mode = params.get("body_mode") or "none"
        content: bytes | None = None
        content_type: str | None = None
        data: dict[str, str] | None = None
        files: dict[str, tuple[str, bytes, str]] | None = None

        if body_mode == "json":
            raw = params.get("body_json")
            body_obj = _coerce_json_body(raw)
            if credential_body:
                if not isinstance(body_obj, dict):
                    body_obj = {}
                for bk, bv in credential_body.items():
                    body_obj[bk] = ad.flows.coerce_template_json_value(bv)
            content = json.dumps(body_obj).encode()
            content_type = "application/json"
            headers.setdefault("Content-Type", content_type)
        elif body_mode == "json_keypair":
            obj = {
                str(p["name"]): _json_keypair_value(p.get("value", ""))
                for p in (params.get("body_params") or [])
                if isinstance(p, dict) and p.get("name") is not None
            }
            for bk, bv in credential_body.items():
                obj[bk] = ad.flows.coerce_template_json_value(bv)
            content = json.dumps(obj).encode()
            content_type = "application/json"
            headers.setdefault("Content-Type", content_type)
        elif body_mode == "form_urlencoded":
            pairs = {
                str(p["name"]): str(p.get("value", ""))
                for p in (params.get("body_params") or [])
                if isinstance(p, dict) and p.get("name") is not None
            }
            for bk, bv in credential_body.items():
                pairs[bk] = str(ad.flows.coerce_template_json_value(bv))
            content = urllib.parse.urlencode(pairs).encode()
            content_type = "application/x-www-form-urlencoded"
            headers.setdefault("Content-Type", content_type)
        elif body_mode == "raw":
            content = str(params.get("body_raw") or "").encode()
            content_type = str(params.get("body_content_type") or "text/plain")
            headers.setdefault("Content-Type", content_type)
        elif body_mode in ("binary", "multipart_form"):
            if context.analytiq_client is None:
                raise RuntimeError("HTTP Request binary upload requires analytiq_client on the execution context")
            prop = str(params.get("binary_property_name") or "data").strip() or "data"
            ref = item.binary.get(prop)
            if ref is None:
                raise RuntimeError(f"HTTP Request expected item.binary[{prop!r}] for binary upload, but it was missing")
            blob = await ad.flows.get_binary_stream(ref, context.analytiq_client)
            mime = (ref.mime_type or "application/octet-stream") if hasattr(ref, "mime_type") else "application/octet-stream"
            filename = (ref.file_name or "upload") if hasattr(ref, "file_name") else "upload"

            if body_mode == "binary":
                content = blob
                headers.setdefault("Content-Type", mime)
            else:
                # multipart_form
                data = {}
                for p in params.get("multipart_fields") or []:
                    if isinstance(p, dict) and p.get("name") is not None:
                        data[str(p["name"])] = str(p.get("value", ""))
                field_name = str(params.get("multipart_file_field_name") or "file").strip() or "file"
                files = {field_name: (filename, blob, mime)}

        async def _ssrf_guard_each_request(request: httpx.Request) -> None:
            """Run SSRF blocklist on every outbound URL, including each redirect hop."""

            await ad.flows.validate_http_url_allowed_async(
                str(request.url), purpose="HTTP Request"
            )

        max_redirs = int(params.get("max_redirects") or 20)
        if max_redirs < 1:
            max_redirs = 20

        client_kw: dict[str, Any] = {
            "timeout": timeout,
            "event_hooks": {"request": [_ssrf_guard_each_request]},
            # Ignore HTTP(S)_PROXY from the environment so flow URLs and MockTransport tests are authoritative.
            "trust_env": False,
        }
        if follow_redirects:
            client_kw["follow_redirects"] = True
            client_kw["max_redirects"] = max_redirs
        else:
            client_kw["follow_redirects"] = False

        if params.get("verify_tls") is False:
            client_kw["verify"] = False

        proxy_raw = str(params.get("proxy") or "").strip()
        if proxy_raw:
            await ad.flows.validate_http_url_allowed_async(
                proxy_raw, purpose="HTTP Request proxy"
            )
            client_kw["proxy"] = proxy_raw

        try:
            async with httpx.AsyncClient(**client_kw) as client:
                resp = await client.request(
                    method=method,
                    url=url,
                    params=query or None,
                    headers=headers or None,
                    content=content,
                    data=data,
                    files=files,
                    auth=req_auth,
                )
        except httpx.UnsupportedProtocol as e:
            # Should be rare after preflight validation; normalize message for callers.
            msg = (
                "HTTP Request url must use http:// or https:// "
                f"(request used {url!r}: {e})"
            )
            exec_log.error(
                f"flows.http_request unsupported protocol node_name={n_disp!r} node_id={nid} execution_id={context.execution_id} "
                f"flow_id={context.flow_id} organization_id={context.organization_id}: {msg}",
                exc_info=True,
            )
            raise RuntimeError(msg) from None
        except httpx.RequestError as e:
            exec_log.error(
                f"flows.http_request transport error node_name={n_disp!r} node_id={nid} execution_id={context.execution_id} "
                f"flow_id={context.flow_id} organization_id={context.organization_id} "
                f"method={method} url={url!r}: {e}",
                exc_info=True,
            )
            raise

        if not never_error and resp.status_code >= 400:
            detail = resp.text[:200]
            msg = f"HTTP {resp.status_code} from {method} {url}: {detail}"
            exec_log.error(
                f"flows.http_request HTTP error node_name={n_disp!r} node_id={nid} execution_id={context.execution_id} "
                f"flow_id={context.flow_id} organization_id={context.organization_id} "
                f"status={resp.status_code} method={method} url={url!r} body_snippet={detail!r}"
            )
            raise RuntimeError(msg)

        ct_header = resp.headers.get("content-type") or ""

        out_meta = dict(item.meta) if isinstance(item.meta, dict) else {}
        out_meta["source_node_id"] = node["id"]

        rf_raw = str(params.get("response_format") or "auto").lower()
        response_format = rf_raw if rf_raw in ("auto", "json", "text", "binary") else "auto"

        treat_as_binary = response_format == "binary" or (
            response_format == "auto" and _response_content_type_is_binary(ct_header)
        )
        if treat_as_binary:
            mime = (ct_header.split(";")[0].strip() or "application/octet-stream")
            fname = _extract_filename_from_content_disposition(resp.headers)
            out_binary = dict(item.binary)
            out_binary["data"] = ad.flows.BinaryRef(
                mime_type=mime,
                file_name=fname,
                data=resp.content,
            )
            out_json_bin: dict[str, Any] = {
                "status_code": resp.status_code,
                "headers": dict(resp.headers),
            }
            return [
                [
                    ad.flows.FlowItem(
                        json=out_json_bin,
                        binary=out_binary,
                        meta=out_meta,
                        paired_item=item.paired_item,
                    )
                ]
            ]

        resp_body: Any
        ct = ct_header
        if response_format == "json":
            try:
                resp_body = resp.json()
            except Exception:
                resp_body = resp.text
        elif response_format == "text":
            resp_body = resp.text
        else:
            # auto
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
                    binary=dict(item.binary),
                    meta=out_meta,
                    paired_item=item.paired_item,
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
