# DocRouter HTTP Request Node — Implementation

Outbound HTTP Request node (`flows.http_request`), replacing the old `flows.webhook` node.

Related: [`docrouter_credentials.md`](./docrouter_credentials.md) (credential kinds `httpHeaderAuth` and `httpQueryAuth` used here), [`docrouter_nodes.md`](./docrouter_nodes.md), [`docrouter_binary.md`](./docrouter_binary.md) (binary response handling).

---

## 1. Rename — Done

| | Old | New |
|---|---|---|
| Node key | `flows.webhook` | `flows.http_request` |
| Class | `FlowsWebhookNode` | `FlowsHttpRequestNode` |
| File | `flows/nodes/webhook.py` | `flows/nodes/http_request.py` |
| Label | `Webhook (generic)` | `HTTP Request` |
| Category | `Generic` | `Generic` |

`webhook.py` is deleted. No backward compatibility shim.

---

## 2. Scope — V1 implemented

| Feature | Status |
|---|---|
| Methods: `GET`, `POST`, `PUT`, `PATCH`, `DELETE` | Done |
| Static URL or `=expression` evaluated per item | Done (engine pre-resolves) |
| `httpHeaderAuth` and `httpQueryAuth` credential slots | Done |
| Query parameters (key-value list, values support `=expression`) | Done |
| Headers (key-value list, values support `=expression`) | Done |
| Body modes: `none`, `json`, `json_keypair`, `form_urlencoded`, `raw` | Done |
| `full_response` flag (status_code + headers in output) | Done |
| `never_error` flag | Done |
| `follow_redirects`, `timeout_seconds` | Done |
| Binary response detection and `BinaryRef` output | Done |
| SSRF guard (blocks loopback, RFC-1918, redirect chains) | Done — not in original plan |
| Structured error logging per execution/node/org | Done — not in original plan |
| Parameter schema UI hints (`x-ui-group`, `x-ui-widget`, `x-ui-show-when`) | Done — not in original plan |
| Incoming binary pass-through (§8 of binary plan) | Done |

### Deferred to later

- Basic auth, Digest auth, OAuth1, OAuth2
- Multipart / binary body (binary response is done; binary request body is not)
- Pagination, batching / rate limiting
- Proxy, SSL client certificates

---

## 3. Credential kinds — Done

Both files exist in `schemas/credential-kinds/`:

**`httpHeaderAuth.json`** — adds a single header to every request.

**`httpQueryAuth.json`** — adds a single query parameter to every request.

The node fetches each slot independently via `ad.flows.fetch_credential_fields(org_id, cred_id)` — one call per bound slot, not a flat-merged context dict. This avoids `name`/`value` field collisions when both slots are bound simultaneously.

```python
if bindings.get("httpHeaderAuth"):
    hf = await ad.flows.fetch_credential_fields(org_id, str(bindings["httpHeaderAuth"]))
    hn, hv = hf.get("name"), hf.get("value")
    if hn and hv is not None:
        headers[str(hn)] = str(hv)
if bindings.get("httpQueryAuth"):
    qf = await ad.flows.fetch_credential_fields(org_id, str(bindings["httpQueryAuth"]))
    qn, qv = qf.get("name"), qf.get("value")
    if qn and qv is not None:
        query[str(qn)] = str(qv)
```

---

## 4. Parameter schema

The schema includes UI extension fields (`x-ui-group`, `x-ui-widget`, `x-ui-show-when`, `x-ui-placeholder`, `x-ui-regex`) that drive the schema-driven parameter form in the frontend.

Notable differences from the plan:
- `value` fields in `query_params`, `headers`, `body_params` items use `{}` (no type constraint) to allow expression-resolved non-string values from upstream items.
- `url` has `minLength: 1` enforced at the JSON Schema level in addition to `validate_parameters`.
- `x-ui-show-when` controls conditional display of `body_json`, `body_params`, `body_raw`, `body_content_type` based on `body_mode`.

---

## 5. `execute()` implementation notes

**File:** `packages/python/analytiq_data/flows/nodes/http_request.py`

### Parameter resolution

The engine pre-resolves all `=expression` values against the current item before calling `execute()`. The node receives already-resolved literals in `node["parameters"]` — it does **not** call `ad.flows.resolve_parameters` internally.

### Binary response (see `docrouter_binary.md` §9)

When `Content-Type` matches a binary marker, the response is attached as `BinaryRef(data=resp.content)` under `binary["data"]`. The output `item.json` contains `status_code` and `headers` (always, for binary responses — no `full_response` flag check). Inline bytes are offloaded to `flow_blobs` by the engine before `run_data` is persisted.

Markers checked (lowercased):
```python
("application/pdf", "image/", "audio/", "video/",
 "application/zip", "application/x-zip-compressed",
 "application/gzip", "application/x-gzip", "application/octet-stream")
```

### Binary pass-through (see `docrouter_binary.md` §8)

Both code paths (text and binary response) copy the incoming `item.binary` dict into the output `FlowItem`. Incoming binary refs from upstream nodes are not dropped — the output item merges them with any newly produced `BinaryRef`.

### SSRF guard

`assert_http_url_allowed()` from `analytiq_data.flows.url_ssrf_guard` is called:
1. Statically, after URL validation, before the httpx client is created.
2. Via `event_hooks={"request": [_ssrf_guard_each_request]}` — on every outbound request including each redirect hop.

This blocks loopback (`127.x`, `::1`), RFC-1918 ranges, and redirect chains that resolve to internal addresses.

### Error handling

- Empty or schemeless URL after parameter resolution → `RuntimeError` with an `_inbound_row_hint` explaining which upstream row was in use.
- `httpx.UnsupportedProtocol` → normalized `RuntimeError`.
- `httpx.RequestError` (connect errors, timeouts) → re-raised as-is after structured logging.
- HTTP 4xx/5xx with `never_error=False` → `RuntimeError` with status and first 200 chars of body.

All errors log `node_name`, `node_id`, `execution_id`, `flow_id`, `organization_id` via `context.logger` (falls back to module logger if not attached).

---

## 6. Output FlowItem shapes

**Text/JSON response (`full_response: false`):**
```json
{ "body": { "ok": true } }
```

**Text/JSON response (`full_response: true`):**
```json
{ "body": { "ok": true }, "status_code": 200, "headers": { "content-type": "application/json" } }
```

**Binary response (regardless of `full_response`):**
```json
// item.json:
{ "status_code": 200, "headers": { "content-type": "application/pdf" } }
// item.binary:
{ "data": BinaryRef(mime_type="application/pdf", file_name="invoice.pdf", data=<bytes>) }
```

Upstream binary refs are merged into `item.binary` alongside the new `"data"` key.

---

## 7. Expression support

All `=expression` parameter values are resolved by the engine before `execute()` is called. The node receives plain string/object values. The `url`, `query_params[*].value`, `headers[*].value`, `body_params[*].value`, `body_json`, and `body_raw` fields all support expressions. The `name` side of key-value pairs is always static.

---

## 8. `flows.webhook` removal — Done

`flows/nodes/webhook.py` is deleted. `FlowsHttpRequestNode` is registered in `nodes/__init__.py`. Any saved flows using `flows.webhook` must be updated in the flow editor.

---

## 9. Tests — Done

**File:** `packages/python/tests/flows/test_flow_http_request_node.py`

Tests use `httpx.MockTransport` (not `respx` as originally planned). Cases covered:

| Test | What it asserts |
|---|---|
| GET with static URL | Response body in `item.json["body"]` |
| POST `json_keypair` body | Correct JSON body; `Content-Type: application/json` |
| POST `body_json` (literal resolved by engine) | Correct JSON body sent |
| `httpHeaderAuth` credential slot | Header present in outgoing request |
| `httpQueryAuth` credential slot | Query param present in outgoing request |
| Non-2xx, `never_error: false` | `RuntimeError` raised |
| Non-2xx, `never_error: true`, `full_response: true` | Item emitted with `status_code: 404` |
| `full_response: true` | `status_code` and `headers` in output |
| `validate_parameters` | Invalid method → error; empty `body_json` → error; empty `body_raw` → error |
| Empty URL after parameters | `RuntimeError` with "empty" |
| Schemeless URL | `RuntimeError` with "http:// or https://" |
| SSRF loopback blocked | `RuntimeError` with "blocked" (no network call) |
| Redirect to loopback blocked | `RuntimeError` with "blocked" |
| Connect error | `httpx.ConnectError` propagates |
| Timeout error | `httpx.TimeoutException` propagates |
| Binary PDF response | `BinaryRef` under `binary["data"]`; `status_code` and headers in `item.json` |
| Binary response merges upstream binary | Upstream `binary["pdf"]` preserved alongside new `binary["data"]` |
| Incoming binary/meta pass-through | Upstream `item.binary` and `item.meta` forwarded in text response path |

---

## 10. What remains

| Item | Notes |
|---|---|
| Frontend palette icon | `icon_key = "http_request"` set; frontend must map the key to an SVG |
| Multipart / binary request body | Sending a `BinaryRef` as the request body (depends on `docrouter_binary.md` §8) |
| Additional auth kinds | Basic auth, OAuth1/2 (depends on credentials plan) |
| Pagination | Not started |
