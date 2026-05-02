# DocRouter HTTP Request Node — Implementation Plan

Rename and reimplement `flows.webhook` as a general-purpose outbound HTTP Request node, aligned with n8n's naming convention and significantly expanded in capability.

Related: [`docrouter_credentials.md`](./docrouter_credentials.md) (credential kinds `httpHeaderAuth` and `httpQueryAuth` used here), [`docrouter_nodes.md`](./docrouter_nodes.md).

---

## 1. Rename summary

| | Old | New |
|---|---|---|
| Node key | `flows.webhook` | `flows.http_request` |
| Class | `FlowsWebhookNode` | `FlowsHttpRequestNode` |
| File | `flows/nodes/webhook.py` | `flows/nodes/http_request.py` |
| Label | `Webhook (generic)` | `HTTP Request` |
| Category | `Generic` | `Generic` |

The old `webhook.py` is deleted. No backward compatibility shim — the node key changes and any existing saved flows using `flows.webhook` must be updated.

---

## 2. Scope

### V1 (this plan)

- Methods: `GET`, `POST`, `PUT`, `PATCH`, `DELETE`
- URL: static string or `=expression` evaluated per item
- Authentication: `none`, `httpHeaderAuth`, `httpQueryAuth` — via the credential slot mechanism from `docrouter_credentials.md`
- Query parameters: key-value list; values support `=expression`
- Headers: key-value list; values support `=expression`
- Body content types: `json` (raw JSON string), `json_keypair` (key-value list assembled into a JSON object), `form_urlencoded`, `raw`
- Body values support `=expression`
- Response as FlowItem: `body` (parsed JSON or raw text), `status_code`, `headers` (optional, behind `full_response` flag)
- `never_error`: when true, non-2xx responses produce a normal output item instead of raising
- `follow_redirects`: boolean, default true
- `timeout_seconds`: number, default 30

### Deferred to later

- Basic auth, Digest auth, OAuth1, OAuth2 (requires token refresh loop from credentials plan §10)
- Multipart / binary body
- Pagination
- Batching / rate limiting
- Proxy
- SSL client certificates
- Response format: binary file output

---

## 3. Credential slots

Two credential kinds are used. Both are defined in `schemas/credential-kinds/` per `docrouter_credentials.md §9`.

**`httpHeaderAuth`** — adds a single header to every request:

```json
{
  "key": "httpHeaderAuth",
  "display_name": "Header Auth",
  "auth_mode": "api_key",
  "secret_schema": {
    "type": "object",
    "additionalProperties": false,
    "required": ["name", "value"],
    "properties": {
      "name":  { "type": "string", "title": "Header Name",  "description": "e.g. Authorization" },
      "value": { "type": "string", "title": "Header Value", "x-secret": true, "description": "e.g. Bearer sk-…" }
    }
  },
  "inject": {
    "headers": {
      "{{ credentials.name }}": "{{ credentials.value }}"
    }
  }
}
```

**`httpQueryAuth`** — adds a single query parameter to every request:

```json
{
  "key": "httpQueryAuth",
  "display_name": "Query Auth",
  "auth_mode": "api_key",
  "secret_schema": {
    "type": "object",
    "additionalProperties": false,
    "required": ["name", "value"],
    "properties": {
      "name":  { "type": "string", "title": "Parameter Name",  "description": "e.g. api_key" },
      "value": { "type": "string", "title": "Parameter Value", "x-secret": true }
    }
  },
  "inject": {
    "query_params": {
      "{{ credentials.name }}": "{{ credentials.value }}"
    }
  }
}
```

The node declares both as optional slots so a user picks whichever auth style their API requires:

```python
credential_slots = [
    {"slot": "httpHeaderAuth", "label": "Header Auth",  "required": False,
     "docrouter_binding": "organization_credential_kind:httpHeaderAuth"},
    {"slot": "httpQueryAuth",  "label": "Query Auth",   "required": False,
     "docrouter_binding": "organization_credential_kind:httpQueryAuth"},
]
```

At execution time, if a slot is bound, the resolved `credentials.name` / `credentials.value` pair is merged into the outgoing request headers or query string respectively.

---

## 4. Parameter schema

```python
parameter_schema: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["method", "url"],
    "properties": {
        # ── Core ──────────────────────────────────────────────────────────
        "method": {
            "type": "string",
            "enum": ["GET", "POST", "PUT", "PATCH", "DELETE"],
            "default": "GET",
        },
        "url": {
            "type": "string",
            "description": "Static URL or =expression. Evaluated per item.",
        },
        # ── Query parameters ──────────────────────────────────────────────
        "query_params": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["name", "value"],
                "properties": {
                    "name":  {"type": "string"},
                    "value": {"type": "string"},  # supports =expression
                },
                "additionalProperties": False,
            },
            "default": [],
        },
        # ── Headers ───────────────────────────────────────────────────────
        "headers": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["name", "value"],
                "properties": {
                    "name":  {"type": "string"},
                    "value": {"type": "string"},  # supports =expression
                },
                "additionalProperties": False,
            },
            "default": [],
        },
        # ── Body ──────────────────────────────────────────────────────────
        "body_mode": {
            "type": "string",
            "enum": ["none", "json", "json_keypair", "form_urlencoded", "raw"],
            "default": "none",
        },
        # Used when body_mode == "json": raw JSON string (supports =expression)
        "body_json": {
            "type": "string",
            "default": "",
        },
        # Used when body_mode == "json_keypair" or "form_urlencoded"
        "body_params": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["name", "value"],
                "properties": {
                    "name":  {"type": "string"},
                    "value": {"type": "string"},  # supports =expression
                },
                "additionalProperties": False,
            },
            "default": [],
        },
        # Used when body_mode == "raw"
        "body_raw": {
            "type": "string",
            "default": "",
        },
        "body_content_type": {
            "type": "string",
            "default": "text/plain",
            "description": "Content-Type header for raw body mode.",
        },
        # ── Response options ──────────────────────────────────────────────
        "full_response": {
            "type": "boolean",
            "default": False,
            "description": "Include status_code and headers in the output item.",
        },
        "never_error": {
            "type": "boolean",
            "default": False,
            "description": "Treat non-2xx responses as normal output instead of errors.",
        },
        "follow_redirects": {
            "type": "boolean",
            "default": True,
        },
        "timeout_seconds": {
            "type": "number",
            "default": 30,
        },
    },
}
```

---

## 5. `execute()` implementation

**File:** `packages/python/analytiq_data/flows/nodes/http_request.py`

The node runs once per item (`batch_execute_inputs = False`). Per-item, it:

1. Resolves all `=expression` parameter values against the current item using `ad.flows.resolve_parameters`.
2. Merges credential injections (header auth → headers dict, query auth → query params dict).
3. Builds the request with `httpx`.
4. Emits a `FlowItem` whose `json` field contains the response.

```python
from __future__ import annotations

import json
import urllib.parse
from typing import Any

import httpx

import analytiq_data as ad


class FlowsHttpRequestNode:

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
        {"slot": "httpHeaderAuth", "label": "Header Auth",  "required": False,
         "docrouter_binding": "organization_credential_kind:httpHeaderAuth"},
        {"slot": "httpQueryAuth",  "label": "Query Auth",   "required": False,
         "docrouter_binding": "organization_credential_kind:httpQueryAuth"},
    ]

    parameter_schema: dict[str, Any] = { ... }   # see §4

    def validate_parameters(self, params: dict[str, Any]) -> list[str]:
        errs: list[str] = []
        method = params.get("method")
        if method not in ("GET", "POST", "PUT", "PATCH", "DELETE"):
            errs.append(f"method must be one of GET POST PUT PATCH DELETE, got {method!r}")
        url = params.get("url")
        if not isinstance(url, str) or not url.strip():
            errs.append("url must be a non-empty string")
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
        item = inputs[0][0]   # batch_execute_inputs=False: exactly one item

        # 1. Resolve expressions against the current item
        params = ad.flows.resolve_parameters(
            params_raw,
            item=item,
            run_data=context.run_data,
        )

        method   = params["method"]
        url      = params["url"].strip()
        timeout  = float(params.get("timeout_seconds") or 30)
        follow_redirects = bool(params.get("follow_redirects", True))
        never_error      = bool(params.get("never_error", False))
        full_response    = bool(params.get("full_response", False))

        # 2. Build headers and query params from parameter lists
        headers: dict[str, str] = {}
        for h in (params.get("headers") or []):
            headers[h["name"]] = h["value"]

        query: dict[str, str] = {}
        for q in (params.get("query_params") or []):
            query[q["name"]] = q["value"]

        # 3. Merge credential injections from context.credentials
        #    (set by the engine before execute() — see docrouter_credentials.md §7.2)
        creds = getattr(context, "credentials", {}) or {}
        if "httpHeaderAuth" in (node.get("credentials") or {}):
            h_name  = creds.get("name")
            h_value = creds.get("value")
            if h_name and h_value:
                headers[h_name] = h_value
        if "httpQueryAuth" in (node.get("credentials") or {}):
            q_name  = creds.get("name")
            q_value = creds.get("value")
            if q_name and q_value:
                query[q_name] = q_value

        # 4. Build body
        body_mode = params.get("body_mode") or "none"
        content: bytes | None = None
        content_type: str | None = None

        if body_mode == "json":
            raw = params.get("body_json") or ""
            obj = json.loads(raw) if raw.strip() else {}
            content = json.dumps(obj).encode()
            content_type = "application/json"
            headers.setdefault("Content-Type", content_type)

        elif body_mode == "json_keypair":
            obj = {p["name"]: p["value"] for p in (params.get("body_params") or [])}
            content = json.dumps(obj).encode()
            content_type = "application/json"
            headers.setdefault("Content-Type", content_type)

        elif body_mode == "form_urlencoded":
            pairs = {p["name"]: p["value"] for p in (params.get("body_params") or [])}
            content = urllib.parse.urlencode(pairs).encode()
            content_type = "application/x-www-form-urlencoded"
            headers.setdefault("Content-Type", content_type)

        elif body_mode == "raw":
            content = (params.get("body_raw") or "").encode()
            content_type = params.get("body_content_type") or "text/plain"
            headers.setdefault("Content-Type", content_type)

        # 5. Make the request
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

        # 6. Parse response body
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

        return [[
            ad.flows.FlowItem(
                json=out_json,
                binary={},
                meta={"source_node_id": node["id"], "item_index": 0},
                paired_item=None,
            )
        ]]
```

### Credential injection detail (§3 expansion)

The engine sets `context.credentials` to the merged decrypted fields of all bound slots before calling `execute()`. Both `httpHeaderAuth` and `httpQueryAuth` store their fields as `name` and `value`. Since a node can bind at most one of each kind, there is no field-name collision. If both slots are bound (unusual but valid), the fields are merged; `name`/`value` from `httpQueryAuth` would overwrite `httpHeaderAuth`'s `name`/`value` in the flat dict.

To avoid this collision when both slots are bound simultaneously, resolve each slot independently rather than merging into a single flat dict. The engine's `resolve_node_credentials` (per `docrouter_credentials.md §7.1`) resolves all slots into one flat dict — this is fine for most nodes, but the HTTP Request node should resolve each slot separately:

```python
# Alternative: resolve per-slot to avoid name/value collision
header_cred_id = (node.get("credentials") or {}).get("httpHeaderAuth")
query_cred_id  = (node.get("credentials") or {}).get("httpQueryAuth")
# fetch and decrypt each independently, then use directly
```

This is a minor implementation detail; the simple flat-merge approach works if only one auth slot is bound (the typical case).

---

## 6. Output FlowItem shape

**`full_response: false` (default):**

```json
{
  "body": { "ok": true, "ts": "1234567890.123456" }
}
```

When the response body is not JSON, `body` is a plain string.

**`full_response: true`:**

```json
{
  "body": { "ok": true },
  "status_code": 200,
  "headers": {
    "content-type": "application/json",
    "x-rate-limit-remaining": "98"
  }
}
```

Downstream nodes reference these via `=expression` syntax: `=$json["body"]["ok"]`, `=$json["status_code"]`.

---

## 7. Expression support

All string parameter values starting with `=` are evaluated per item via `ad.flows.resolve_parameters` before the request is built. Examples:

```json
{
  "method": "POST",
  "url": "=`https://api.example.com/users/${$json['user_id']}`",
  "headers": [
    {"name": "X-Request-Id", "value": "=$json['request_id']"}
  ],
  "body_mode": "json_keypair",
  "body_params": [
    {"name": "email", "value": "=$json['email']"},
    {"name": "name",  "value": "=$json['full_name']"}
  ]
}
```

The `url`, `query_params[*].value`, `headers[*].value`, `body_params[*].value`, `body_json`, and `body_raw` fields all support `=expression`. The `name` side of a key-value pair does not (names are static).

---

## 8. Replacing `flows.webhook`

Delete `flows/nodes/webhook.py` and replace with `flows/nodes/http_request.py`. Any saved flows that used `flows.webhook` nodes must be edited in the flow editor to use `flows.http_request` instead — the parameter structure has changed enough that silent migration is not worthwhile.

---

## 9. Registration

Update `packages/python/analytiq_data/flows/nodes/__init__.py`:

```python
from .http_request import FlowsHttpRequestNode
# Remove: from .webhook import FlowsWebhookNode

_BUILTIN_NODES = [
    ...,
    FlowsHttpRequestNode,
]
```

Update `packages/python/analytiq_data/flows/nodes/register.py` (or wherever `register_builtin()` is called) accordingly.

---

## 10. Tests

**File:** `packages/python/tests/test_flow_http_request_node.py`

Key cases to cover:

| Test | What to assert |
|---|---|
| GET with static URL | Response body in `item.json["body"]` |
| POST with `json_keypair` body | Correct JSON body sent; `Content-Type: application/json` |
| POST with `body_json` expression `=$json["payload"]` | Expression resolved from input item |
| `httpHeaderAuth` credential injected | Header present in outgoing request |
| `httpQueryAuth` credential injected | Query param present in outgoing request |
| Non-2xx with `never_error: false` | `RuntimeError` raised |
| Non-2xx with `never_error: true` | Item emitted with `status_code: 404` (when `full_response: true`) |
| `full_response: true` | `status_code` and `headers` in output |
| URL expression | `=$json["endpoint"]` resolved before request |
| `validate_parameters` | Missing `url` → error; invalid method → error |
Use `respx` (httpx mock library) to intercept HTTP calls in tests without network access.

---

## 11. Starter kind files to add

Two new files in `schemas/credential-kinds/` (in addition to those listed in `docrouter_credentials.md §9`):

```
schemas/credential-kinds/
├── httpHeaderAuth.json    (see §3 above)
└── httpQueryAuth.json     (see §3 above)
```

---

## 12. Build order

1. Write `schemas/credential-kinds/httpHeaderAuth.json` and `httpQueryAuth.json`.
2. Delete `packages/python/analytiq_data/flows/nodes/webhook.py`.
3. Write `packages/python/analytiq_data/flows/nodes/http_request.py`.
4. Register `FlowsHttpRequestNode` in `nodes/__init__.py`.
5. Write `test_flow_http_request_node.py` with `respx` mocks; run `pytest`.
6. Wire credential injection: confirm `context.credentials` is set by the engine before `execute()` (depends on `docrouter_credentials.md` Phase 3).
7. Update the frontend node palette icon and label (no schema changes needed; the frontend reads `label` from `GET /v0/orgs/{orgId}/flows/node-types`).
