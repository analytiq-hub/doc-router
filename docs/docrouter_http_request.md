# DocRouter HTTP Request Node

Outbound HTTP node (`flows.http_request`). Replaces the legacy `flows.webhook` node.

**Related:** [`docrouter_credentials.md`](./docrouter_credentials.md), [`docrouter_nodes.md`](./docrouter_nodes.md), [`docrouter_binary.md`](./docrouter_binary.md).

---

## 1. What is implemented

| Feature | Detail |
|---------|--------|
| **Methods** | GET, HEAD, OPTIONS, POST, PUT, PATCH, DELETE |
| **URL** | Absolute `http(s)://…` or `=expression` per inbound item |
| **Query params** | Key/value list (`query_params`) + optional `query_json` overlay |
| **Headers** | Key/value list (`headers`) + optional `headers_json` overlay |
| **Body modes** | `none`, `json`, `json_keypair`, `form_urlencoded`, `raw`, `binary`, `multipart_form` |
| **Credential slots** | `httpBearerAuth`, `httpBasicAuth`, `httpDigestAuth`, `httpHeaderAuth`, `httpQueryAuth`, `httpJsonBodyAuth` |
| **Credential injection** | `inject.headers`, `inject.query_params`, `inject.body` via Jinja2 templates from kind JSON |
| **Body + credential body** | `inject.body` merges into `json` / `json_keypair` / `form_urlencoded` bodies; `body_mode: none` with credential body sends JSON |
| **Authentication widget** | `credential_authentication` schema widget in node config panel (none / generic / predefined UI) |
| **Redirects** | `follow_redirects` (default true) + `max_redirects` (default 20) |
| **Proxy** | `proxy` URL, SSRF-checked before connecting |
| **TLS** | `verify_tls` (default true) |
| **Response format** | `response_format`: auto (Content-Type heuristics), json, text, binary |
| **Full response** | `full_response` adds `status_code` and `headers` to output |
| **Never error** | `never_error` emits non-2xx as items instead of raising |
| **Timeout** | `timeout_seconds` (default 30) |
| **SSRF** | `validate_http_url_allowed_async` on every hop including redirects |
| **Environment proxy** | `trust_env=False` — ignores `HTTP_PROXY`/`HTTPS_PROXY` env vars |
| **Binary responses** | Content-Type heuristics + `response_format: binary` → `BinaryRef` on output |

---

## 2. Authentication

Authentication is set per-node via the `authentication` parameter (schema widget `x-ui-widget: credential_authentication`).

| Mode | Behaviour |
|------|-----------|
| `none` | No credential bound |
| `generic` | User picks a credential slot type (Bearer, Basic, etc.) then a saved credential of that kind |
| `predefined` | User picks any compatible saved credential; the correct slot is auto-selected by kind |

The companion parameter `generic_auth_slot` records which slot is active in `generic` mode. Both are hidden from the default field renderer (marked `x-ui-companion-of: authentication`) — the `FlowCredentialAuthenticationField` component renders the full UI block.

### Credential slots and how they inject

Each bound slot is processed in order during `execute`. If the kind has an `inject` section, Jinja2 templates are rendered and results merged into `headers`, `query`, or `credential_body`. Otherwise the legacy field pair falls back:

| Slot | Kind | Injection |
|------|------|-----------|
| `httpBearerAuth` | `inject.headers` | `Authorization: Bearer <token>` |
| `httpBasicAuth` | fallback | `httpx.BasicAuth(user, password)` |
| `httpDigestAuth` | fallback | `httpx.DigestAuth(user, password)` |
| `httpHeaderAuth` | `inject.headers` | Arbitrary header name/value |
| `httpQueryAuth` | `inject.query_params` | Arbitrary query name/value |
| `httpJsonBodyAuth` | `inject.body` | Merges `access_token` into request body |

`httpBasicAuth` and `httpDigestAuth` cannot be bound simultaneously — `execute` raises immediately.

### `inject.body` + body mode rules

| `body_mode` | Credential body present | Behaviour |
|-------------|------------------------|-----------|
| `json` | yes | Merges into parsed body; **raises `RuntimeError`** if body root is not a JSON object |
| `json_keypair` | yes | Merges into key/value object |
| `form_urlencoded` | yes | Merges into form pairs |
| `none` | yes | Sends credential body as `application/json` |
| `raw`, `binary`, `multipart_form` | yes | `credential_body` silently ignored (not applicable) |

---

## 3. Parameter reference

### Request group

| Parameter | Type | Default | Notes |
|-----------|------|---------|-------|
| `method` | enum | `GET` | GET HEAD OPTIONS POST PUT PATCH DELETE |
| `url` | string | — | `minLength: 1`; must be `http(s)` |
| `authentication` | enum | `none` | `none` / `generic` / `predefined`; drives credential widget |
| `generic_auth_slot` | enum | `httpBearerAuth` | Visible only when `authentication == generic` |
| `query_params` | array of `{name, value}` | `[]` | Applied first |
| `query_json` | string (JSON object) | `""` | Merged after `query_params`; same keys overwrite |
| `headers` | array of `{name, value}` | `[]` | Applied first; credential headers apply last |
| `headers_json` | string (JSON object) | `""` | Merged after `headers`, before credential injection |

### Body group

| Parameter | Type | Default | Notes |
|-----------|------|---------|-------|
| `body_mode` | enum | `none` | none / json / json_keypair / form_urlencoded / raw / binary / multipart_form |
| `body_json` | string | `""` | Required when `body_mode == json` |
| `body_params` | array of `{name, value}` | `[]` | Used by json_keypair and form_urlencoded |
| `body_raw` | string | `""` | Used by raw |
| `body_content_type` | string | `text/plain` | Content-Type for raw mode |
| `binary_property_name` | string | `data` | `item.binary` key for binary / multipart |
| `multipart_fields` | array of `{name, value}` | `[]` | Extra form fields for multipart |
| `multipart_file_field_name` | string | `file` | Part name for the binary file in multipart |

### Options group

| Parameter | Type | Default | Notes |
|-----------|------|---------|-------|
| `follow_redirects` | boolean | `true` | |
| `max_redirects` | integer ≥ 1 | `20` | Only effective when `follow_redirects` is true |
| `proxy` | string | `""` | `http(s)://host:port`; SSRF-checked |
| `verify_tls` | boolean | `true` | Set false only for trusted debug endpoints |
| `response_format` | enum | `auto` | auto / json / text / binary |
| `full_response` | boolean | `false` | Adds `status_code` and `headers` to `item.json` |
| `never_error` | boolean | `false` | Emits non-2xx as items instead of raising |
| `timeout_seconds` | number > 0 | `30` | |

---

## 4. Output shapes

Default output (`full_response: false`):
```json
{ "body": <parsed or raw response> }
```

With `full_response: true`:
```json
{ "body": …, "status_code": 200, "headers": { "Content-Type": "…" } }
```

Binary response (`response_format: binary` or detected from Content-Type):
- `item.binary["data"]` → `BinaryRef` with `mime_type` and `file_name`
- `item.json` → `{ "url": …, "mime_type": …, "file_name": … }`

---

## 5. SSRF protection

`validate_http_url_allowed_async` blocks private/link-local ranges. It runs:
1. Before the initial request (URL parameter)
2. On every redirect hop (via httpx `event_hooks`)
3. On the `proxy` URL before connecting

`trust_env=False` prevents the process environment's `HTTP_PROXY`/`HTTPS_PROXY` from leaking into flow execution.

---

## 6. Tests

`packages/python/tests/flows/test_flow_http_request_node.py`

Notable coverage added in this phase:
- HEAD method
- query_json overlay
- headers_json overlay
- max_redirects forwarded to httpx
- verify_tls=false forwarded
- proxy URL forwarded and SSRF-blocked
- Basic auth (Authorization header produced)
- httpJsonBodyAuth with body_mode=none → JSON body sent
- httpJsonBodyAuth + non-dict body_json → RuntimeError raised
- httpBasicAuth + httpDigestAuth simultaneously → RuntimeError raised
- response_format=text returns raw string for broken JSON
- validate_parameters: max_redirects, query_json, proxy, authentication, generic_auth_slot

---

## 7. What is not yet implemented

These are the known gaps in priority order.

### 7.1 Predefined credential integration (n8n "service" picker)

n8n allows a node to declare it natively supports a specific third-party service (e.g. Slack, GitHub). The user picks one credential from only that service's kind. DocRouter has credential_slots + the generic/predefined authentication widget, but the "predefined" path currently just picks any compatible org credential. True service integrations require the node to declare a `service_credential_kind` and the UI to surface it distinctly.

### 7.2 Batching / rate-limiting

n8n's HTTP Request node supports batching (send N items per second, N items per batch). DocRouter's engine processes items one at a time per node call. Batching would require changes to the engine loop, not just the node.

### 7.3 Pagination

n8n supports cursor-based, offset-based, and link-header pagination loops inside the HTTP Request node. Requires an internal loop with bounded iteration, new parameters (`pagination_mode`, `max_pages`, etc.), and carry-over state across iterations.

### 7.4 SSL client certificates

Add an `httpSslAuth` credential slot. The kind would store PEM-encoded `cert` and `key`; the node would load them into `httpx.AsyncClient(cert=...)`.

### 7.5 Node versioning (`type_version`)

Schema changes (new parameters, renamed options) currently have no migration path. Adding `type_version` to the node type and a migration table would let old saved flows keep working after parameter-schema changes.

### 7.6 Curl import

A UI affordance to paste a `curl` command and auto-populate method, URL, headers, and body. Frontend-only feature; no backend changes needed.
