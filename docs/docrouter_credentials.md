# DocRouter Credentials

Credential kinds, org-scoped storage, backend API, runtime injection, and frontend UI. Self-contained; does not depend on n8n credential import tooling.

---

## 1. Architecture

| Concept | Where | Purpose |
|---|---|---|
| **Credential kind** | `schemas/credential-kinds/<key>.json` — loaded at startup via `lru_cache` | Global type definition: auth mode, field schema, inject rules |
| **Org credential** | `credentials` MongoDB collection | One saved instance per org: kind reference + AES-encrypted field values |
| **Node binding** | `flow_revisions.nodes[*].credentials` | Maps a node's slot name → a saved org credential id |

Runtime: before executing a node, the engine resolves slot bindings → decrypts the credential → populates `context.credentials` → the node reads it to inject headers or query params.

---

## 2. Credential kind file format

Kind definitions live in `schemas/credential-kinds/<key>.json`. Auto-discovered at startup; no registration call needed.

| Field | Type | Required | Purpose |
|---|---|---|---|
| `key` | string | yes | Stable identifier; must match the filename stem |
| `display_name` | string | yes | Human-readable label |
| `auth_mode` | enum | yes | `api_key`, `oauth2_authorization_code`, `oauth2_client_credentials`, `basic_auth`, `custom` |
| `secret_schema` | JSON Schema object | yes | Fields the org fills in; `"x-secret": true` marks values never returned in API responses |
| `inject` | object | no | `inject.headers` and/or `inject.query_params` — Jinja2 templates using `{{ credentials.<field> }}` |
| `test_request` | object | no | `{ "method": "GET", "url": "…" }` — called by the `/test` endpoint |

**Implemented kinds:**

`schemas/credential-kinds/httpHeaderAuth.json` — injects an arbitrary header:
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
      "value": { "type": "string", "title": "Header Value", "x-secret": true }
    }
  },
  "inject": { "headers": { "{{ credentials.name }}": "{{ credentials.value }}" } }
}
```

`schemas/credential-kinds/httpQueryAuth.json` — injects an arbitrary query parameter (same shape; `inject.query_params` instead of `inject.headers`).

---

## 3. Python kind registry

**File:** `packages/python/analytiq_data/flows/credential_kind_registry.py`

Loaded lazily at first access via `lru_cache`. Scans `schemas/credential-kinds/*.json` at repo root.

| Function | Purpose |
|---|---|
| `list_credential_kinds() → list[dict]` | All loaded kind documents |
| `get_credential_kind(key: str) → dict` | One kind by key; raises `KeyError` if unknown |
| `credential_secret_field_names(kind: dict) → set[str]` | Property names marked `x-secret` |

Exposed as `ad.flows.list_credential_kinds()` etc.

`extends` inheritance is declared in the kind format but the `_resolve()` merge logic is not yet implemented (see §6 Porting, Gap 2).

---

## 4. `credentials` MongoDB collection

```python
{
    "_id":               ObjectId,
    "organization_id":   str,
    "kind_key":          str,        # e.g. "httpHeaderAuth"
    "name":              str,        # user-chosen label
    "encrypted_payload": str,        # AES-encrypted JSON of all field values
    "created_at":        datetime,
    "created_by":        str,
    "updated_at":        datetime,
    "updated_by":        str,
}
```

**Encryption:** AES-256-CFB via `ad.crypto.encrypt_token`; key derived from `NEXTAUTH_SECRET`. Known limitation: the IV is fixed (derived deterministically from the key), so identical plaintext always produces identical ciphertext. A random-IV variant should be added before storing high-value secrets (OAuth client secrets, etc.).

Decryption returns the full field dict; `x-secret` fields are stripped from all API responses.

**Index:** `{ organization_id: 1, kind_key: 1 }` — created at startup. ✓

---

## 5. Backend API

**File:** `packages/python/app/routes/flows_credentials.py`

| Method | Path | Description |
|---|---|---|
| `GET` | `/v0/orgs/{orgId}/credential-kinds` | List all available kinds |
| `POST` | `/v0/orgs/{orgId}/credentials` | Create a credential instance |
| `GET` | `/v0/orgs/{orgId}/credentials` | List org credentials; `?credential_kind=<key>` filter |
| `GET` | `/v0/orgs/{orgId}/credentials/{credId}` | Get one credential (no secrets) |
| `PUT` | `/v0/orgs/{orgId}/credentials/{credId}` | Update name and fields (re-encrypts) |
| `DELETE` | `/v0/orgs/{orgId}/credentials/{credId}` | Delete |
| `POST` | `/v0/orgs/{orgId}/credentials/{credId}/test` | Test against `test_request` |

The `/test` endpoint decrypts fields, renders `inject` templates via Jinja2, and calls the `test_request` URL via `httpx`. `validate_http_url_allowed_async()` runs before the request (same SSRF rules as the HTTP Request node). ✓

---

## 6. Flow node credential bindings

### Node document structure

```json
{
  "id": "3",
  "type": "http_request",
  "credentials": { "httpHeaderAuth": "64f3a1b2c3d4e5f6a7b8c9d0" }
}
```

Key = slot name from the node type's `credential_slots`; value = `credentials._id` as a string.

### Node type declaration

```python
credential_slots = [
    { "slot": "httpHeaderAuth", "label": "Header Auth", "required": False,
      "docrouter_binding": "organization_credential_kind:httpHeaderAuth" },
    { "slot": "httpQueryAuth",  "label": "Query Auth",  "required": False,
      "docrouter_binding": "organization_credential_kind:httpQueryAuth" },
]
```

`GET /v0/orgs/{orgId}/flows/node-types` includes `credential_slots` so the frontend can render the binding UI.

`validate_revision()` checks that `credentials` on each node is a `dict[str, str]` and that each slot name is known for that node type. ✓

---

## 7. Code nodes and credentials

Code nodes (`flows.code`) execute arbitrary user-supplied Python in a subprocess. Credentials are never injected into that sandbox — decrypted secrets passed to user code would be readable by anyone who writes the flow.

---

## 8. Runtime credential injection

**File:** `packages/python/analytiq_data/flows/credentials.py`

```python
async def fetch_credential_fields(organization_id: str, credential_id: str) -> dict[str, Any]:
    """Load and decrypt one saved credential. Returns {} on failure."""
```

Called directly by nodes. Returns the full decrypted field dict (including secrets) — for engine use only, never exposed externally.

`ExecutionContext.credentials` is cleared before each node call. The HTTP Request node reads its bindings and calls `fetch_credential_fields` at execution time:

```python
bindings = node.get("credentials") or {}
hf = await ad.flows.fetch_credential_fields(org_id, bindings.get("httpHeaderAuth", ""))
if hf:
    headers[hf["name"]] = hf["value"]
```

---

## 9. Frontend

**Node config panel** (`flowNodeCredentialSlots.tsx`): renders per-slot `<select>` dropdowns for any node type with `credential_slots`. Fetches `GET /credentials` once when a node is selected; filters by `kind_key`; stores the selected id in `node.credentials[slot.slot]`; saved on the next PUT. ✓

**Credentials management tab** (`FlowCredentials.tsx`): list view with Test / Edit / Delete per row; create dialog with kind picker and field form (password inputs for `x-secret` fields). Accessible at `/orgs/[orgId]/flows?tab=credentials`. ✓

**Org-wide executions tab** (`FlowExecutionsAll.tsx`): reuses `FlowExecutionsView` with an added **Flow** column. Backed by `GET /v0/orgs/{orgId}/executions` (queries `flow_executions` without `flow_id` filter). ✓

---

## 10. Porting n8n credentials to DocRouter

### 10.1 Scope

The n8n tree (`../n8n/packages/nodes-base/credentials/`) has **369** credential files. DocRouter currently has 2 (`httpHeaderAuth`, `httpQueryAuth`).

Breakdown by category:

| Category | Count | DocRouter path |
|---|---|---|
| Generic API-key / header / query (no OAuth) | ~240 | Declarative JSON kind — automated port |
| OAuth2 extensions of `oAuth2Api` etc. | ~92 | Declarative after `extends` resolution (Gap 2) + OAuth2 flow (§11) |
| Dynamic test URL (`$credentials.domain`) | ~50 | Gap 3 — Jinja2-render test URL |
| Custom `authenticate()` (SigV4, HMAC, etc.) | ~24 | Not portable as JSON; implement as dedicated Python nodes |
| `preAuthentication` / expirable session tokens | ~7 | Gap 4 — `pre_auth` block or OAuth2 client-credentials |
| OAuth1 | ~2 | Defer; add `auth_mode: "oauth1"` only if required |

These overlap (e.g. an OAuth2 kind may also have a dynamic test URL), so counts are approximate.

### 10.2 Conversion pipeline

**Step A — `tools/dump_credentials.js`** (to create): Node.js script that requires each compiled `*.credentials.ts` from `../n8n/packages/nodes-base/credentials/`, instantiates the class, and emits one JSONL line per type:

```json
{"name":"slackApi","displayName":"Slack API","extends":null,"properties":[...],"authenticate":{...},"test":{...}}
```

**Step B — `tools/port_credentials.py`** (to create): reads the JSONL and writes one `schemas/credential-kinds/<key>.json` per type.

**Field mapping:**

| n8n field | DocRouter field | Notes |
|---|---|---|
| `name` | `key` | identical |
| `displayName` | `display_name` | |
| `extends[0]` | `extends` | registry merge not yet implemented |
| `properties[].name` | `secret_schema.properties` key | |
| `properties[].displayName` | `title` | |
| `properties[].typeOptions.password` | `x-secret: true` | |
| `properties[].required` | `secret_schema.required[]` | |
| `properties[].type === "options"` | `enum` | map `options` array to JSON Schema `enum` |
| `properties[].type === "hidden"` | `runtime_fields` | skip in `secret_schema` |
| `authenticate.properties.headers` | `inject.headers` | convert template (see below) |
| `authenticate.properties.qs` | `inject.query_params` | |
| `authenticate.properties.body` | `inject.body` | Gap 1 |
| `test.request.baseURL` + `url` | `test_request.url` | concatenate; Jinja2-render at test time (Gap 3) |
| OAuth2 `grantType` | `auth_mode` | `authorizationCode` → `oauth2_authorization_code` |

**Template conversion** — n8n uses `={{$credentials.field}}`; DocRouter uses Jinja2:

```python
import re

def convert_template(n8n_tmpl: str) -> str:
    s = n8n_tmpl.lstrip("=")
    return re.sub(r"\{\{\s*\$credentials\.(\w+)\s*\}\}", r"{{ credentials.\1 }}", s)
```

### 10.3 Infrastructure gaps

Close these before running the automated port:

| Gap | Affects | Effort | Fix |
|---|---|---|---|
| **Gap 1** — `inject.body` | ~5 kinds | Low | Add to kind format; teach HTTP executor to merge into request body |
| **Gap 2** — `extends` not resolved | ~92 kinds | Medium | Implement `_resolve(key, seen)` merge in `credential_kind_registry.py` |
| **Gap 3** — Dynamic `test_request` URL | ~50 kinds | Low | Jinja2-render `test_request.url` before calling `httpx` in `/test` |
| **Gap 4** — `preAuthentication` / expirable tokens | ~7 kinds | High | `pre_auth` block in kind format, or treat as OAuth2 client-credentials |
| **Gap 5** — Custom `authenticate()` | ~24 kinds | N/A — skip | Implement per-integration as dedicated Python nodes; do not fake in JSON |
| **Gap 6** — OAuth1 | ~2 kinds | High | Defer; add `auth_mode: "oauth1"` only if needed |
| **Gap 7** — `options` → `enum` | ~20 kinds | Low | Handle in `port_credentials.py` |
| **Gap 8** — `hidden` → `runtime_fields` | ~15 kinds | Low | Handle in `port_credentials.py` |

Gaps 1, 3, 7, 8 are script-level fixes (low effort, unlock most API-key kinds).
Gap 2 unlocks the OAuth2 majority once §11 is implemented.
Gaps 4, 5, 6 are the long tail — defer.

### 10.4 Phased plan

| Phase | Goal | Prerequisite |
|---|---|---|
| **P0** | Close Gaps 1, 3, 7, 8 (all low-effort) | none |
| **P1** | Build `dump_credentials.js` + `port_credentials.py`; run against n8n tree; commit API-key kinds in vendor batches | P0 |
| **P2** | Close Gap 2 (`extends` resolution); re-run port for OAuth2 kinds; implement OAuth2 flow (§11) | P1 |
| **P3** | Close Gap 4 (`pre_auth`) for expirable-token kinds | P2 |
| **P4** | Implement custom-auth kinds as dedicated Python nodes (AWS SigV4 etc.) — on demand, not bulk | P1 |
| **P5** | OAuth1 — only if product requires those nodes | P4 |

**Done criteria:** every n8n kind is either (a) in `schemas/credential-kinds/` with a passing `/test`, (b) listed as handler-backed with a Python module path, or (c) explicitly out of scope in `schemas/credential-kinds/PORTING_STATUS.md`.

**Maintenance:** re-run `dump_credentials.js` when upgrading the `../n8n` pin; diff output against `schemas/credential-kinds/` to catch new or removed upstream kinds.

---

## 11. OAuth2 credential flow (not yet implemented)

OAuth2 authorization-code kinds require a browser redirect and server-side token exchange.

| Step | What to build |
|---|---|
| **Base kind** | `schemas/credential-kinds/oAuth2Api.json` with `auth_url`, `token_url`, `runtime_fields` (`access_token`, `refresh_token`) |
| **Initiate** | `POST /v0/orgs/{orgId}/credentials/{credId}/oauth/initiate` — build auth URL; redirect with `state=<signed JWT encoding orgId+credId>` |
| **Callback** | `GET /v0/callback/oauth` — validate state; POST to `token_url` with code; store tokens in `encrypted_payload` |
| **Refresh** | Before each execution: check `access_token` expiry; if expired, POST to `token_url` with `refresh_token`; update `encrypted_payload` |
| **Frontend** | "Connect" button in create form for OAuth2 kinds; poll for completion after redirect |

Until this is built, OAuth2 credential instances can be created by manually supplying an `access_token` as a string field. Mark OAuth2 kinds with `"status": "manual_token_only"` so the UI shows a warning.

---

## 12. Implementation status

| Component | Status |
|---|---|
| Kind registry (`credential_kind_registry.py`) | ✓ Done |
| Kind files: `httpHeaderAuth`, `httpQueryAuth` | ✓ Done |
| Credentials API — CRUD + `/test` | ✓ Done |
| `credentials` MongoDB collection + index | ✓ Done |
| Runtime resolver (`fetch_credential_fields`) | ✓ Done |
| HTTP Request node credential slots | ✓ Done |
| Engine binding validation in `validate_revision` | ✓ Done |
| Frontend: node config credential slot picker | ✓ Done |
| Frontend: credentials management tab | ✓ Done |
| Frontend: org-wide executions tab | ✓ Done |
| SDK TypeScript types for credentials | ✓ Done |
| Tests (`test_flow_credentials.py`) | ✓ Done |
| Porting pipeline (`dump_credentials.js`, `port_credentials.py`) | ✗ Not started |
| `extends` resolution in registry | ✗ Not started |
| OAuth2 initiate / callback / refresh | ✗ Not started |
| `inject.body` (Gap 1) | ✗ Not started |
| Dynamic `test_request` URL render (Gap 3) | ✗ Not started |
