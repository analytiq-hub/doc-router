# DocRouter Credentials

This document describes the credential system in DocRouter: kind definitions, org-scoped storage, backend API, runtime injection, and frontend UI. It is self-contained and does not depend on n8n credential import tooling.

---

## 1. Architecture

Three concepts:

| Concept | Where | Purpose |
|---|---|---|
| **Credential kind** | `schemas/credential-kinds/<key>.json` — loaded at startup via `lru_cache` | Global type definition: auth mode, field schema, inject rules |
| **Org credential** | `credentials` MongoDB collection | One saved instance per org: kind reference + AES-encrypted field values |
| **Node binding** | `flow_revisions.nodes[*].credentials` field | Maps a node's slot name → a saved org credential id |

Runtime flow: before executing a node, the engine resolves its slot bindings → decrypts the referenced credential → populates `context.credentials` → the node reads `context.credentials` to inject headers or query params.

---

## 2. Credential kind file format

Kind definitions live in `schemas/credential-kinds/<key>.json`. They are loaded automatically at import time (no startup call required).

**Fields:**

| Field | Type | Required | Purpose |
|---|---|---|---|
| `key` | string | yes | Stable identifier; must match the filename stem |
| `display_name` | string | yes | Human-readable label shown in the UI |
| `auth_mode` | enum | yes | `"api_key"`, `"oauth2_authorization_code"`, `"oauth2_client_credentials"`, `"basic_auth"`, `"custom"` |
| `secret_schema` | JSON Schema object | yes | JSON Schema for the fields the org fills in; `"x-secret": true` marks fields whose values are never returned in API responses |
| `inject` | object | no | How to attach decrypted fields to HTTP requests: `inject.headers` and/or `inject.query_params`. Values are Jinja2 templates using `{{ credentials.<field> }}` |
| `test_request` | object | no | `{ "method": "GET", "url": "…" }` — called by the `/test` endpoint to verify a credential |

**Implemented kind files:**

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
      "value": { "type": "string", "title": "Header Value", "x-secret": true, "description": "e.g. Bearer sk-…" }
    }
  },
  "inject": {
    "headers": { "{{ credentials.name }}": "{{ credentials.value }}" }
  }
}
```

`schemas/credential-kinds/httpQueryAuth.json` — injects an arbitrary query parameter:
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
    "query_params": { "{{ credentials.name }}": "{{ credentials.value }}" }
  }
}
```



---

## 3. Python kind registry

**File:** `packages/python/analytiq_data/flows/credential_kind_registry.py`

Loaded lazily at first access via `lru_cache`. Scans `schemas/credential-kinds/*.json` relative to the repo root. No startup call is needed.

**Public API:**

| Function | Purpose |
|---|---|
| `list_credential_kinds() → list[dict]` | All loaded kind documents (mutable copies) |
| `get_credential_kind(key: str) → dict` | One kind by key; raises `KeyError` if unknown |
| `credential_secret_field_names(kind: dict) → set[str]` | Property names marked `x-secret` in `secret_schema` |

Exposed through the `analytiq_data.flows` namespace. Accessible as `ad.flows.list_credential_kinds()`, `ad.flows.get_credential_kind(key)`, `ad.flows.credential_secret_field_names(kind)`.

**Note:** The `extends` field described in early design docs is not implemented. If inheritance across kinds is needed, add `_resolve(key, seen)` merge logic to the registry.

---

## 4. `credentials` MongoDB collection

One document per saved credential instance:

```python
{
    "_id":              ObjectId,          # credential id
    "organization_id":  str,               # org scope
    "kind_key":         str,               # e.g. "httpHeaderAuth"
    "name":             str,               # user-chosen label
    "encrypted_payload": str,             # AES-encrypted JSON blob of all field values
    "created_at":       datetime,
    "created_by":       str,               # user_id
    "updated_at":       datetime,
    "updated_by":       str,
}
```

### Encryption

`encrypted_payload` is `ad.crypto.encrypt_token(json.dumps(fields_dict))` — AES-256-CFB, key derived from `NEXTAUTH_SECRET` (SHA-256 padded to 32 bytes).

**Known limitation:** the IV is fixed — derived deterministically from the key via SHA-256 (`encryption.py`). This means identical plaintext always produces identical ciphertext. For credentials this is partially mitigated by the JSON field ordering varying across writes, but it is still weaker than random-IV encryption. A random-IV variant of `encrypt_token` should be added before storing high-value secrets (OAuth client secrets, etc.).

Decryption returns the full field dict; `x-secret` fields are stripped before any API response.

### Credential field values and expressions

Credential field values are **plain strings** — they are not run through the expression engine (`resolve_parameters`). Storing an expression like `=$env['MY_TOKEN']` in a credential field would store the literal string, not the resolved value. This is intentional: credentials are static secrets managed by admins, not dynamic values computed at flow run time.

**Index:** add a compound index `{ organization_id: 1, kind_key: 1 }` for efficient filtering.

---

## 5. Backend API

**File:** `packages/python/app/routes/flows_credentials.py`

Router registered in `packages/python/app/main.py` as `flow_credentials_router`.

### 5.1 Pydantic models

| Model | Purpose |
|---|---|
| `CredentialKindSummary` | Kind metadata + field list (no secrets) |
| `CreateCredentialRequest` | `{ kind_key, name, fields }` — all field values, encrypted server-side |
| `UpdateCredentialRequest` | `{ name, fields }` — kind_key is immutable after creation |
| `CredentialHeader` | Saved credential metadata + `public_fields` (secret fields omitted) |
| `ListCredentialsResponse` | `{ items, total }` |
| `TestCredentialResponse` | `{ ok, status_code?, error? }` |

### 5.2 Routes

| Method | Path | Description |
|---|---|---|
| `GET` | `/v0/orgs/{orgId}/credential-kinds` | List all available credential kinds |
| `POST` | `/v0/orgs/{orgId}/credentials` | Create a credential instance |
| `GET` | `/v0/orgs/{orgId}/credentials` | List org credentials; optional `?credential_kind=<key>` filter |
| `GET` | `/v0/orgs/{orgId}/credentials/{credId}` | Get one credential (no secrets) |
| `PUT` | `/v0/orgs/{orgId}/credentials/{credId}` | Update name and fields (re-encrypts) |
| `DELETE` | `/v0/orgs/{orgId}/credentials/{credId}` | Delete a credential |
| `POST` | `/v0/orgs/{orgId}/credentials/{credId}/test` | Test a credential against its `test_request` |

The `/test` endpoint:
- Decrypts field values.
- Renders `kind.inject.headers` and `kind.inject.query_params` via Jinja2.
- Makes the `test_request` HTTP call.
- Returns `ok: true` with a message if the kind has no `test_request` defined.
- SSRF protection is not yet applied here — add `assert_http_url_allowed(url)` before the httpx call.

---

## 6. Flow node credential bindings

### 6.1 Node document structure

Nodes are stored in `flow_revisions.nodes` as plain dicts. Each node optionally carries a `credentials` map:

```json
{
  "id": "3",
  "type": "http_request",
  "name": "Call API",
  "parameters": { "method": "GET", "url": "https://example.com/api" },
  "credentials": {
    "httpHeaderAuth": "64f3a1b2c3d4e5f6a7b8c9d0"
  }
}
```

Key = slot name from the node type's `credential_slots`; value = `credentials._id` as a string.

### 6.2 Node type declaration

Node types declare their credential slots via a `credential_slots` class attribute:

```python
# In http_request.py
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
```

`GET /v0/orgs/{orgId}/flows/node-types` includes `credential_slots` in each node type's response so the frontend can render the binding UI.

### 6.3 Validation at execution time

`engine.py` `validate_revision()` checks that `credentials` on each node is either absent or a `dict[str, str]`. It also validates that each slot name in the binding map is a known slot for that node type.

---

## 7. Code nodes and credentials

Code nodes (`flows.code`) execute arbitrary user-supplied Python in a subprocess. Because decrypted credential values passed into that sandbox would be readable by whoever writes the flow — defeating the purpose of keeping secrets from non-admin users — **code nodes do not have credential slots and credentials are never injected into the subprocess context**.

---

## 8. Runtime credential injection

### 7.1 Resolver utility

**File:** `packages/python/analytiq_data/flows/credentials.py`

```python
async def fetch_credential_fields(organization_id: str, credential_id: str) -> dict[str, Any]:
    """Load and decrypt one saved credential by id. Returns {} on failure."""
```

Called directly by nodes that need credentials. Returns the full decrypted field dict (including secret fields) — for use inside the execution engine only, never exposed externally.

### 7.2 Execution context

`ExecutionContext` carries a `credentials` field (plain dict) that the engine clears and repopulates before each node execution:

```python
@dataclass
class ExecutionContext:
    ...
    credentials: dict[str, Any] = field(default_factory=dict)
```

The engine clears `context.credentials` at the start of each node call. Nodes that have credential slots call `fetch_credential_fields` directly from their `execute()` method and use the result immediately.

### 7.3 Usage in `http_request` executor

The HTTP Request node (`packages/python/analytiq_data/flows/nodes/http_request.py`) reads its credential bindings at execution time:

```python
bindings = node.get("credentials") or {}

# Header auth slot
hf = await ad.flows.fetch_credential_fields(org_id, bindings.get("httpHeaderAuth", ""))
if hf:
    headers[hf["name"]] = hf["value"]

# Query auth slot
qf = await ad.flows.fetch_credential_fields(org_id, bindings.get("httpQueryAuth", ""))
if qf:
    params[qf["name"]] = qf["value"]
```

---

## 9. Frontend

### 9.1 Node config panel — credential slot binding (implemented)

**File:** `packages/typescript/frontend/src/components/flows/flowNodeCredentialSlots.tsx`

`<FlowNodeCredentialSlots>` renders per-slot `<select>` dropdowns in the node config panel for any node type that has `credential_slots`. It:

- Fetches `GET /v0/orgs/{orgId}/credentials` once when a node with slots is selected.
- Filters options by `kind_key` using `slot.docrouter_binding` (strips the `organization_credential_kind:` prefix).
- Stores the selected credential id in `node.credentials[slot.slot]` and calls `onChange({ credentials: ... })`.
- Shows a "— None —" option (clears the slot) for optional slots.

The binding is saved as part of the node's data in the next `PUT` save.

### 9.2 Credentials management tab (not yet implemented)

**Route:** `/orgs/[organizationId]/flows?tab=credentials`

#### Flows page layout changes

The flows page (`page.tsx`) currently has two tabs — **Flows** and **Create Flow** — plus no top-level create button. The redesign (modelled on the n8n flows list page) makes three changes:

1. **Replace the "Create Flow" tab with a split button** in the top-right corner: primary action is "Create flow"; a dropdown chevron reveals a secondary option "Create credential". This keeps the tab bar clean and matches the pattern users expect from n8n.

2. **Add a "Credentials" tab** alongside the existing "Flows" tab.

3. **Add an "Executions" tab** for an org-wide view of all flow executions.

The tab bar becomes: **Flows** | **Credentials** | **Executions**.

Concretely in `packages/typescript/frontend/src/app/orgs/[organizationId]/flows/page.tsx`:
- Remove the `flow-create` tab value; replace with a `<Button>` + dropdown (MUI `ButtonGroup` with a `<Menu>` on the chevron, or a single split-button component).
- Clicking "Create flow" navigates directly to the flow editor for a new flow (or opens the existing create dialog inline).
- Clicking "Create credential" switches to `?tab=credentials` with the create dialog pre-opened.
- Add `credentials` as a valid tab value; render `<FlowCredentials>` in its panel.
- Add `executions` as a valid tab value; render `<FlowExecutionsAll>` in its panel.

#### `FlowCredentials` component

**New file:** `packages/typescript/frontend/src/components/flows/FlowCredentials.tsx`

- **List view** (default): fetches `GET /v0/orgs/{orgId}/credentials` and renders a table with columns **Name**, **Kind**, **Created**, **Actions**.
  - Actions per row: **Test** (calls `POST .../test`, shows an inline ok/error chip), **Edit** (opens the field form in a dialog), **Delete** (confirmation dialog, then `DELETE`).
- **Create dialog** (opened by "Create credential" from the split button, or an "Add" button in the tab):
  1. Kind picker — dropdown from `GET .../credential-kinds`.
  2. Field form rendered from `kind.fields`: `is_secret: true` → password input with show/hide toggle; `description` → helper text. Name field always at top.
  3. Submit → `POST .../credentials` → dialog closes, list refreshes.

### 9.3 Org-wide executions tab (not yet implemented)

**Route:** `/orgs/[organizationId]/flows?tab=executions`

#### Backend: new org-wide executions endpoint

The existing endpoint `GET /v0/orgs/{orgId}/flows/{flowId}/executions` filters by a single flow. The global view needs a new endpoint that queries across all flows:

```
GET /v0/orgs/{orgId}/executions?limit=50&offset=0&status=<optional>
```

Implementation in `flows.py`: query `flow_executions` with only `organization_id` in the filter (no `flow_id`), sort by `started_at` descending. To show the flow name alongside each execution, join against the `flows` collection — either with a `$lookup` aggregation (same pattern as `list_flows`) or by fetching a name map up front. The response reuses the existing `ListExecutionsResponse` / `FlowExecution` models; `flow_id` is already present in each `FlowExecution` document.

Add a corresponding SDK method in `docrouter-org.ts`:
```typescript
listAllExecutions(params?: { limit?: number; offset?: number; status?: string }): Promise<ListExecutionsResponse>
```

#### Frontend: `FlowExecutionsAll` component

**New file:** `packages/typescript/frontend/src/components/flows/FlowExecutionsAll.tsx`

Reuse the existing `FlowExecutionsView` component as a reference (`flowNodeCredentialSlots.tsx` → `FlowExecutionsView.tsx`). The org-wide version adds one column — **Flow** — showing the flow name (looked up from `flow_id`). Everything else (status chip, started/finished times, duration, stop button, row click → execution detail) is identical to the per-flow view.

The flow name lookup can be done by fetching `GET /v0/orgs/{orgId}/flows` once and building a `flowId → name` map client-side, since the executions list already contains `flow_id`.

#### SDK client methods

Already partially present in `docrouter-org.ts` — verify these all exist:
- `listFlowCredentialKinds()`
- `listFlowCredentials({ credential_kind? })`
- `createFlowCredential(req)`
- `updateFlowCredential(credId, req)`
- `deleteFlowCredential(credId)`
- `testFlowCredential(credId)`

---

## 10. Porting n8n credential kinds to DocRouter

This section is about converting n8n credential *type definitions* from the n8n source tree (`../n8n/packages/nodes-base/credentials/`) into DocRouter kind JSON files (`schemas/credential-kinds/`). This is analogous to `tools/dump_nodes.js` + `tools/port_nodes.py` for node types.

### 10.1 n8n credential type structure

Each credential type is a TypeScript class in `../n8n/packages/nodes-base/credentials/<Name>.credentials.ts`:

```typescript
export class SlackApi implements ICredentialType {
    name = 'slackApi';                     // → kind key
    displayName = 'Slack API';             // → display_name
    properties: INodeProperties[] = [
        {
            name: 'accessToken',
            displayName: 'Access Token',
            type: 'string',
            typeOptions: { password: true }, // → x-secret: true
            required: true,
            default: '',
        },
    ];
    authenticate: IAuthenticateGeneric = {
        type: 'generic',
        properties: {
            headers: {
                Authorization: '=Bearer {{$credentials.accessToken}}',
                // → inject.headers: { "Authorization": "Bearer {{ credentials.accessToken }}" }
            },
        },
    };
    test: ICredentialTestRequest = {
        request: { baseURL: 'https://slack.com', url: '/api/auth.test' },
        // → test_request: { method: "GET", url: "https://slack.com/api/auth.test" }
    };
}
```

OAuth2 types use `extends = ['oAuth2Api']` and declare `auth_url`, `token_url` etc. as hidden properties.

### 10.2 Conversion pipeline

Follows the same two-step pattern as node porting:

**Step A — `tools/dump_credentials.js`** (to create): Node.js script that `require()`s each `*.credentials.ts` file (compiled) from `../n8n/packages/nodes-base/credentials/`, instantiates the class, and emits one JSONL line per type with the raw shape:

```json
{"name":"slackApi","displayName":"Slack API","extends":null,"properties":[...],"authenticate":{...},"test":{...}}
```

**Step B — `tools/port_credentials.py`** (to create): Python script that reads the JSONL and writes one `schemas/credential-kinds/<key>.json` per type.

**Mapping rules** from n8n → DocRouter kind JSON:

| n8n field | DocRouter field | Notes |
|---|---|---|
| `name` | `key` | Identical |
| `displayName` | `display_name` | |
| `extends[0]` | `extends` | Not yet resolved in registry |
| `properties[].name` | `secret_schema.properties` key | |
| `properties[].displayName` | `title` | |
| `properties[].description` | `description` | |
| `properties[].typeOptions.password` | `x-secret: true` | |
| `properties[].required` | `secret_schema.required[]` | |
| `authenticate.properties.headers` | `inject.headers` | Convert `={{$credentials.x}}` → `{{ credentials.x }}` |
| `authenticate.properties.qs` | `inject.query_params` | Same template conversion |
| `test.request.baseURL` + `test.request.url` | `test_request.url` | Concatenate |
| `test.request.method` | `test_request.method` | Default `GET` |
| OAuth2 `grantType` hidden prop | `auth_mode` | `authorizationCode` → `oauth2_authorization_code` |

Skip `type: 'hidden'` and `type: 'notice'` properties — they are UI-only, not user-filled fields.

### 10.3 Template syntax conversion

n8n uses `={{$credentials.fieldName}}` (n8n expression syntax) in `authenticate` blocks. DocRouter uses Jinja2: `{{ credentials.fieldName }}`. The conversion is a simple string substitution:

```python
import re

def convert_template(n8n_tmpl: str) -> str:
    # "=Bearer {{$credentials.accessToken}}" → "Bearer {{ credentials.accessToken }}"
    s = n8n_tmpl.lstrip("=")
    return re.sub(r"\{\{\s*\$credentials\.(\w+)\s*\}\}", r"{{ credentials.\1 }}", s)
```

### 10.4 Auth mode mapping

| n8n `authenticate.type` / `grantType` | DocRouter `auth_mode` |
|---|---|
| `generic` (no OAuth) | `api_key` or `basic_auth` |
| `authorizationCode` | `oauth2_authorization_code` |
| `clientCredentials` | `oauth2_client_credentials` |

Infer `basic_auth` when the inject block sets an `Authorization: Basic …` header.

---

## 10a. Gaps: what DocRouter needs to port all n8n credential kinds

A survey of all ~370 credential type files in `../n8n/packages/nodes-base/credentials/` reveals the following gaps between what n8n supports and what DocRouter's kind format currently handles.

### Gap 1 — `inject.body` (affects ~5 kinds)

n8n's `authenticate.properties` supports a `body` injection target alongside `headers` and `qs`. A small number of credentials (e.g. Beeminder) POST their auth token in the request body. DocRouter's kind format only has `inject.headers` and `inject.query_params`.

**Fix:** add `inject.body` to the kind format and teach the HTTP Request node executor to merge it into the request body.

### Gap 2 — `extends` inheritance not resolved (affects ~100 kinds)

Over 100 credentials use `extends = ['oAuth2Api']`, `googleOAuth2Api`, `microsoftOAuth2Api`, etc. DocRouter's kind registry declares an `extends` field but the `_resolve()` merge logic is not implemented — get_credential_kind returns the child dict without inheriting the base's `secret_schema`, `inject`, or `oauth2` config.

**Fix:** implement `_resolve(key, seen)` in `credential_kind_registry.py` (the algorithm is already documented in §3).

### Gap 3 — Dynamic test URL (affects ~50 kinds)

Many credentials construct the test URL from a credential field: `baseURL: "={{$credentials.domain}}"`. DocRouter's `test_request.url` is a static string. The `/test` endpoint would silently call a literal `={{$credentials.domain}}/api/test` URL.

**Fix:** apply the same Jinja2 template render to `test_request.url` and `test_request.baseURL` before making the test request (same render already done for inject headers/query_params).

### Gap 4 — `preAuthentication` / expirable session tokens (affects ~7 kinds)

Auth0, CrowdStrike, Cisco Umbrella, Metabase, Wekan, and a few others use a `preAuthentication()` lifecycle method: before the first request, if a `hidden` + `expirable: true` field (e.g. `sessionToken`) is empty or expired, they call a token endpoint to fetch it and store it back. DocRouter has no concept of this.

**Fix:** add a `pre_auth` block to the kind format, similar to OAuth2's token refresh, specifying how to fetch a short-lived session token and which field to store it in. Alternatively, treat these as a subset of the OAuth2 `client_credentials` flow.

### Gap 5 — Custom `authenticate()` method (affects ~24 kinds)

AWS (SigV4), some Cisco endpoints, Datadog, and others implement a custom TypeScript `authenticate()` method that can't be expressed as simple header/query/body templates — they compute HMAC signatures, perform multi-step token fetches, etc.

**Fix:** these cannot be ported as declarative JSON kinds. Each needs a dedicated Python node class (like the HTTP Request node) with custom auth logic. Skip them in the automated port; implement on demand as custom integrations.

### Gap 6 — OAuth1 (affects ~10 kinds)

Twitter, Etsy, Magento1, and others use `oAuth1Api` as the base. DocRouter's `auth_mode` enum does not include `oauth1`. OAuth1 requires request signing (HMAC-SHA1) which is more complex than OAuth2.

**Fix:** add `auth_mode: "oauth1"` to the kind format and implement the signing flow. Defer until specifically needed.

### Gap 7 — `options` field type in `secret_schema` (affects ~20 kinds)

Some credentials expose a dropdown field (e.g. "region", "environment"). n8n uses `type: "options"` with a `values` array. JSON Schema supports this as `enum`. The conversion should map n8n `options` properties to a JSON Schema `enum` field (non-secret, so not `x-secret`).

**Fix:** handle in `port_credentials.py` by mapping `type: "options"` + `options` array → `{ "type": "string", "enum": [...], "title": "..." }`.

### Gap 8 — `hidden` runtime fields in `secret_schema` (affects ~15 kinds)

Fields with `type: "hidden"` are not user-filled — they are populated at runtime (OAuth tokens, session IDs). In DocRouter's kind format these belong in `runtime_fields`, not `secret_schema`. The conversion must filter them out of `secret_schema` and list them in `runtime_fields` instead.

**Fix:** handle in `port_credentials.py`: if `property.type === "hidden"`, emit it in `runtime_fields` rather than `secret_schema.properties`.

### Summary

| Gap | Scope | Effort | Action |
|---|---|---|---|
| `inject.body` | ~5 kinds | Low | Add to kind format + HTTP executor |
| `extends` resolution | ~100 kinds | Medium | Implement `_resolve()` in registry |
| Dynamic test URL | ~50 kinds | Low | Jinja2-render test URL at test time |
| `preAuthentication` / expirable tokens | ~7 kinds | High | New `pre_auth` block in kind format |
| Custom `authenticate()` | ~24 kinds | Very high | Skip; implement as bespoke Python nodes |
| OAuth1 | ~10 kinds | High | Defer |
| `options` → `enum` | ~20 kinds | Low | Handle in conversion script |
| `hidden` → `runtime_fields` | ~15 kinds | Low | Handle in conversion script |

The first three gaps (body injection, `extends` resolution, dynamic test URL) together unlock the large majority of API-key and OAuth2 authorization-code kinds. Custom auth and OAuth1 are the long tail and can be deferred.

---

## 11. OAuth2 credential flow (not yet implemented)

OAuth2 kinds (`auth_mode: "oauth2_authorization_code"`) require a browser redirect to the provider's consent screen and a server-side callback to exchange the code for tokens.

| Step | What to build |
|---|---|
| **Base kind file** | `schemas/credential-kinds/oAuth2Api.json` with `auth_url`, `token_url`, `runtime_fields` (`access_token`, `refresh_token`) |
| **Initiate** | `POST /v0/orgs/{orgId}/credentials/{credId}/oauth/initiate` — build the auth URL, redirect user's browser with `state=<signed JWT encoding orgId+credId>` |
| **Callback** | `GET /v0/callback/oauth` — validate `state`, POST to `token_url` with the code, store `access_token` + `refresh_token` into `encrypted_payload` |
| **Refresh** | Before each execution: check expiry on `access_token`; if expired, POST to `token_url` with `refresh_token`, update `encrypted_payload` |
| **Frontend** | "Connect" button in the create form for OAuth2 kinds; polls for completion after redirect |

Until this is built:
- OAuth2 credential instances can be created by manually supplying an `access_token` as a string field (treating it like an API key for testing).
- Mark OAuth2 kinds with `"status": "manual_token_only"` in the kind file so the UI can show a warning.

---

## 12. What is implemented vs. what remains

### Implemented (on `flows20` branch)

| Component | Status |
|---|---|
| Kind registry (`credential_kind_registry.py`) | Done — auto-discovers from `schemas/credential-kinds/` via `lru_cache` |
| Kind files: `httpHeaderAuth`, `httpQueryAuth` | Done |
| Credentials API (CRUD + test endpoint) | Done — all 7 routes in `flows_credentials.py` |
| `credentials` MongoDB collection | Done — used by API; index not yet created |
| Runtime resolver (`credentials.py` → `fetch_credential_fields`) | Done |
| `ExecutionContext.credentials` field | Done |
| HTTP Request node credential slots | Done — `httpHeaderAuth` and `httpQueryAuth` slots |
| Engine binding validation | Done — validates slot names in `validate_revision()` |
| Frontend: node config credential slot picker | Done — `flowNodeCredentialSlots.tsx` |
| Frontend flows page redesign | Done — split button + Flows / Credentials / Executions tabs in `page.tsx` |
| Frontend credentials management tab | Done — `FlowCredentials.tsx` |
| Frontend org-wide executions tab | Done — `FlowExecutionsAll.tsx` |
| SDK TypeScript types for credentials | Done — `FlowCredentialSlot`, `FlowCredentialHeader`, etc. |
| Tests | Done — `test_flow_credentials.py` |
| MongoDB index on `credentials` | Done — startup check ensures `{ organization_id: 1, kind_key: 1 }` |

### Not yet implemented

| Component | Notes |
|---|---|
| Additional kind files | `slackApi`, `googleOAuth2Api`, etc. — generate via `tools/port_credentials.py` (see §10) |
| `extends` chain resolution in registry | Registry does not merge base + extension kinds |
| SSRF guard in `/test` endpoint | `assert_http_url_allowed()` not called before the test httpx request |
| OAuth2 flow | Initiate / callback / refresh (see §11) |

---

## 13. Build order for remaining work

**Step 1 — Kind files**

Add additional kind JSON files under `schemas/credential-kinds/` as integrations are prioritized. They are picked up automatically without any code changes.

**Step 2 — SSRF guard in test endpoint**

In `test_credential()` in `flows_credentials.py`, call `assert_http_url_allowed(url)` (from `analytiq_data.flows.url_ssrf_guard`) before the `httpx.AsyncClient.request()` call.

**Step 3 — MongoDB index**

Completed: added a startup check to ensure `{ organization_id: 1, kind_key: 1 }` index exists on `credentials` (`app/main.py` calls `ad.flows.ensure_credentials_indexes()`).

**Step 4 — Additional kind files**

Create `tools/dump_credentials.js` and `tools/port_credentials.py` following the node-porting pipeline (see §10). Run against `../n8n/packages/nodes-base/credentials/` to generate kind JSON files for the integrations needed.

**Step 5 — `extends` registry support**

If multi-level kind inheritance is needed (e.g. `googleOAuth2Api` extending `oAuth2Api`), add `_resolve(key, seen)` merge logic to `credential_kind_registry.py`.

**Step 6 — OAuth2 (separate milestone)**

See §11 above.
