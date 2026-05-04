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

`encrypted_payload` is `ad.crypto.encrypt_token(json.dumps(fields_dict))`. Decryption returns the full dict; secret fields are stripped before any API response.

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

## 7. Runtime credential injection

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

## 8. Frontend

### 8.1 Node config panel — credential slot binding (implemented)

**File:** `packages/typescript/frontend/src/components/flows/flowNodeCredentialSlots.tsx`

`<FlowNodeCredentialSlots>` renders per-slot `<select>` dropdowns in the node config panel for any node type that has `credential_slots`. It:

- Fetches `GET /v0/orgs/{orgId}/credentials` once when a node with slots is selected.
- Filters options by `kind_key` using `slot.docrouter_binding` (strips the `organization_credential_kind:` prefix).
- Stores the selected credential id in `node.credentials[slot.slot]` and calls `onChange({ credentials: ... })`.
- Shows a "— None —" option (clears the slot) for optional slots.

The binding is saved as part of the node's data in the next `PUT` save.

### 8.2 Credentials management tab (not yet implemented)

**Route:** `/orgs/[organizationId]/flows?tab=credentials`

The flows page (`page.tsx`) currently has two tabs: `flows` and `flow-create`. A "Credentials" tab needs to be added.

**To implement:**

1. Add a "Credentials" tab button to `packages/typescript/frontend/src/app/orgs/[organizationId]/flows/page.tsx`.
2. Create `packages/typescript/frontend/src/components/flows/FlowCredentials.tsx` with:
   - **List view:** table with columns **Name**, **Kind**, **Created**, **Actions** (Test / Edit / Delete).
   - **"Add credential" button:** two-step dialog:
     1. Kind picker from `GET .../credential-kinds`, grouped by `auth_mode`.
     2. Field form rendered from `kind.fields`: `is_secret: true` → password input with show/hide; `description` → `helperText`. Name field always at top.
   - Submit → `POST .../credentials` → dialog closes, list refreshes.
3. Add SDK client methods (already partially in `docrouter-org.ts` — verify completeness):
   - `listFlowCredentialKinds()`
   - `listFlowCredentials({ credential_kind? })`
   - `createFlowCredential(req)`
   - `updateFlowCredential(credId, req)`
   - `deleteFlowCredential(credId)`
   - `testFlowCredential(credId)`

---

## 9. OAuth2 credential flow (not yet implemented)

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

## 10. What is implemented vs. what remains

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
| SDK TypeScript types for credentials | Done — `FlowCredentialSlot`, `FlowCredentialHeader`, etc. |
| Tests | Done — `test_flow_credentials.py` |

### Not yet implemented

| Component | Notes |
|---|---|
| Frontend credentials management tab | `FlowCredentials.tsx` and "Credentials" tab in `page.tsx` not created |
| Additional kind files | `slackApi`, `openAiApi`, `googleOAuth2Api`, etc. |
| `extends` chain resolution in registry | Registry does not merge base + extension kinds |
| SSRF guard in `/test` endpoint | `assert_http_url_allowed()` not called before the test httpx request |
| MongoDB index on `credentials` | Compound `{ organization_id: 1, kind_key: 1 }` not yet created |
| OAuth2 flow | Initiate / callback / refresh (see §9) |

---

## 11. Build order for remaining work

**Step 1 — Kind files**

Add additional kind JSON files under `schemas/credential-kinds/` as integrations are prioritized. They are picked up automatically without any code changes.

**Step 2 — SSRF guard in test endpoint**

In `test_credential()` in `flows_credentials.py`, call `assert_http_url_allowed(url)` (from `analytiq_data.flows.url_ssrf_guard`) before the `httpx.AsyncClient.request()` call.

**Step 3 — MongoDB index**

Add a migration or startup check to ensure `{ organization_id: 1, kind_key: 1 }` index exists on `credentials`.

**Step 4 — Frontend credentials tab**

See §8.2 above. Implement `FlowCredentials.tsx` and wire it into the flows page.

**Step 5 — `extends` registry support**

If multi-level kind inheritance is needed (e.g. `googleOAuth2Api` extending `oAuth2Api`), add `_resolve(key, seen)` merge logic to `credential_kind_registry.py`.

**Step 6 — OAuth2 (separate milestone)**

See §9 above.
