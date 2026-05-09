# DocRouter HTTP Request Node

Outbound HTTP node (`flows.http_request`), replacing the legacy `flows.webhook` node.

**Related:** [`docrouter_credentials.md`](./docrouter_credentials.md), [`docrouter_nodes.md`](./docrouter_nodes.md), [`docrouter_binary.md`](./docrouter_binary.md).

---

## 1. Roadmap (n8n-parity direction)

The upstream **n8n** HTTP Request node (`../n8n/packages/nodes-base/nodes/HttpRequest/`) is the behavioral reference: versioned node type, explicit **authentication** axis (none / predefined credential type / generic credential type), rich **Options** (redirect policy, proxy, batching, response format), **pagination**, SSL client certs, curl import, etc.

DocRouter intentionally keeps **strong SSRF controls** and **organization-scoped credentials**; parity is about **UX and capability**, not copying unsafe defaults.

| Phase | Goals | Status |
|-------|--------|--------|
| **1** | HTTP methods **HEAD**, **OPTIONS**; optional **query_json** / **headers_json** (JSON objects merged after key/value lists); **max_redirects** when following redirects; tests | **Done** |
| **2** | Authentication UX aligned with n8n: explicit mode (none / generic slots / “service” credential picker); extend credential slots (Digest, Custom JSON, OAuth wiring) per credentials roadmap | Planned |
| **3** | Options: **proxy**, **allow insecure TLS** (if product-approved), **response format** controls closer to n8n (forced json/text/file vs autodetect), **batching** | Planned |
| **4** | **Pagination** (expressions + bounded loops), **SSL client certificate** credential + httpx agent options | Planned |
| **5** | **Node versioning** (`type_version` / schema evolution without breaking saved flows), optional **curl import** in the parameter UI | Planned |

---

## 2. Phase 1 implementation notes

### Methods

`parameter_schema.properties.method.enum` includes **GET**, **HEAD**, **OPTIONS**, **POST**, **PUT**, **PATCH**, **DELETE**.

### Query / headers JSON overlay

- **`query_json`**: optional JSON **object** (string from the UI or dict after expression evaluation). Parsed after **`query_params`** key/value rows; **same keys overwrite** list values (n8n-style “JSON specification” overlay).
- **`headers_json`**: same for **`headers`**, applied **before** credential injection so credential-provided header/query values still apply on top for auth.

Invalid JSON or non-object → validation error on save; at runtime a bad value raises `RuntimeError` with the parse message.

### Redirects

- **`follow_redirects`** (boolean, default `true`).
- **`max_redirects`** (integer ≥ 1, default **20**) passed to **httpx** when `follow_redirects` is enabled (matches httpx’s default cap).

---

## 3. Rename (historical)

| | Old | New |
|---|---|---|
| Node key | `flows.webhook` | `flows.http_request` |
| Class | `FlowsWebhookNode` | `FlowsHttpRequestNode` |
| File | `flows/nodes/webhook.py` | `flows/nodes/http_request.py` |

---

## 4. Implemented features (summary)

| Feature | Notes |
|---------|--------|
| Methods | GET, HEAD, OPTIONS, POST, PUT, PATCH, DELETE |
| URL | Absolute `http(s)` or `=expression` per inbound item |
| Query | Key/value list + optional **`query_json`** overlay |
| Headers | Key/value list + optional **`headers_json`** overlay |
| Credential slots | **httpBearerAuth**, **httpHeaderAuth**, **httpQueryAuth** + inject templates from kind JSON |
| Body modes | `none`, `json`, `json_keypair`, `form_urlencoded`, `raw`, `binary`, `multipart_form` |
| Options | `full_response`, `never_error`, `follow_redirects`, **`max_redirects`**, `timeout_seconds` |
| Binary responses | Content-Type heuristics → `BinaryRef` on output (see `docrouter_binary.md`) |
| SSRF | `validate_http_url_allowed_async` on every request including redirect hops |
| Parameter UI hints | `x-ui-group`, `x-ui-widget`, `x-ui-show-when` on schema |

### Still deferred (later phases)

Predefined integration credentials on the node (n8n “Predefined credential type”), pagination, proxy, batch/rate limits, curl import, SSL client certs.

---

## 5. Credential slots

Kinds live under `schemas/credential-kinds/`. The node resolves each bound slot via `fetch_credential_kind_and_fields`, applies **inject** templates where present, then legacy header/query field pairs.

See §3 of the historical doc in git history for detailed inject examples if needed.

---

## 6. Parameter schema

Extension fields (`x-ui-*`) drive the schema-driven flow editor forms.

---

## 7. `execute()` behavior

- Parameters are **pre-resolved** by the engine (`=expressions` expanded); the node does not call `resolve_parameters` itself.
- **HEAD** / **OPTIONS** use the same body machinery as other methods; callers should leave `body_mode` `none` when inappropriate.
- Errors are logged with `node_name`, `node_id`, `execution_id`, `flow_id`, `organization_id` when `context.logger` is set.

---

## 8. Output shapes

Unchanged from prior documentation:

- Default JSON output: `{ "body": … }`.
- `full_response: true` adds `status_code` and `headers`.
- Binary responses attach bytes under `item.binary["data"]` and put metadata in `item.json`.

---

## 9. Tests

**File:** `packages/python/tests/flows/test_flow_http_request_node.py`

Includes Phase 1 coverage: **HEAD** request method, **query_json** overlay, **max_redirects** forwarded to httpx, validation for **`max_redirects`** and invalid **`query_json`**.

---

## 10. Declarative runtime stub

`schemas/runtimes/http_request_v1.schema.json` allows `HEAD` and `OPTIONS` in the method pattern for ported packages.
