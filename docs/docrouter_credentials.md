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

## 10. Porting n8n credentials to DocRouter

### 10.1 Export from n8n

n8n's CLI can export all credentials in decrypted form:

```bash
n8n export:credentials --all --decrypted --output=tools/n8n_credentials_decrypted.json
```

Each item in the output JSON array has this shape:

```json
{
  "id": "5",
  "name": "My Slack bot",
  "type": "slackApi",
  "data": { "accessToken": "xoxb-…" },
  "createdAt": "2024-01-18T12:00:00.000Z",
  "updatedAt": "2024-01-18T12:00:00.000Z"
}
```

`type` is the n8n credential type name. `data` is the fully decrypted field dict.

> **Security:** the decrypted export file contains all secret values in plain text. Delete it immediately after the import is complete.

### 10.2 Import script

A conversion script lives at (or should be created at) `tools/port_credentials.py`. It follows the same pattern as `tools/port_nodes.py`.

**Algorithm:**

1. Load the decrypted n8n export JSON.
2. For each credential entry:
   a. Map n8n `type` → DocRouter `kind_key`. For most built-in kinds the name is identical (e.g. `slackApi` → `slackApi`). Maintain a small override dict for diverging names.
   b. Skip the entry if the `kind_key` is not registered in DocRouter's kind registry (i.e. the kind file does not exist under `schemas/credential-kinds/`).
   c. POST to `POST /v0/orgs/{orgId}/credentials` with `{ kind_key, name, fields: data }`.
3. Print a summary: imported / skipped / failed.

**Minimal implementation sketch:**

```python
#!/usr/bin/env python3
"""Import n8n decrypted credentials into DocRouter.

Usage:
    python tools/port_credentials.py \
        --input tools/n8n_credentials_decrypted.json \
        --org <organization_id> \
        --api-url http://localhost:8000 \
        --token <bearer_token>
"""
import argparse, json, sys
import httpx

KIND_REMAP: dict[str, str] = {
    # n8n type name → DocRouter kind key (add overrides as needed)
}

def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--input",   required=True)
    p.add_argument("--org",     required=True)
    p.add_argument("--api-url", default="http://localhost:8000")
    p.add_argument("--token",   required=True)
    args = p.parse_args()

    with open(args.input) as f:
        items = json.load(f)

    headers = {"Authorization": f"Bearer {args.token}"}
    base = args.api_url.rstrip("/")
    url = f"{base}/v0/orgs/{args.org}/credentials"

    imported = skipped = failed = 0
    for item in items:
        kind_key = KIND_REMAP.get(item["type"], item["type"])
        payload = {"kind_key": kind_key, "name": item["name"], "fields": item.get("data") or {}}
        r = httpx.post(url, json=payload, headers=headers)
        if r.status_code == 400 and "Unknown credential kind" in r.text:
            print(f"  skip  {item['name']!r} (kind {kind_key!r} not registered)")
            skipped += 1
        elif r.is_success:
            print(f"  ok    {item['name']!r} → {kind_key}")
            imported += 1
        else:
            print(f"  FAIL  {item['name']!r}: {r.status_code} {r.text[:120]}")
            failed += 1

    print(f"\nDone: {imported} imported, {skipped} skipped, {failed} failed.")
    if failed:
        sys.exit(1)

if __name__ == "__main__":
    main()
```

### 10.3 Kind coverage

Before running the import, check which n8n credential types appear in the export and ensure the corresponding kind files exist under `schemas/credential-kinds/`. Any kind without a matching file will be skipped. Add the missing kind files first (§2), then re-run.

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
| SDK TypeScript types for credentials | Done — `FlowCredentialSlot`, `FlowCredentialHeader`, etc. |
| Tests | Done — `test_flow_credentials.py` |

### Not yet implemented

| Component | Notes |
|---|---|
| Frontend flows page redesign | Split button + "Credentials" and "Executions" tabs not yet added to `page.tsx` |
| Frontend credentials management tab | `FlowCredentials.tsx` not yet created |
| Frontend org-wide executions tab | `FlowExecutionsAll.tsx` and `GET /v0/orgs/{orgId}/executions` endpoint not yet created |
| Additional kind files | `slackApi`, `openAiApi`, `googleOAuth2Api`, etc. |
| `extends` chain resolution in registry | Registry does not merge base + extension kinds |
| SSRF guard in `/test` endpoint | `assert_http_url_allowed()` not called before the test httpx request |
| MongoDB index on `credentials` | Compound `{ organization_id: 1, kind_key: 1 }` not yet created |
| OAuth2 flow | Initiate / callback / refresh (see §11) |

---

## 13. Build order for remaining work

**Step 1 — Kind files**

Add additional kind JSON files under `schemas/credential-kinds/` as integrations are prioritized. They are picked up automatically without any code changes.

**Step 2 — SSRF guard in test endpoint**

In `test_credential()` in `flows_credentials.py`, call `assert_http_url_allowed(url)` (from `analytiq_data.flows.url_ssrf_guard`) before the `httpx.AsyncClient.request()` call.

**Step 3 — MongoDB index**

Add a migration or startup check to ensure `{ organization_id: 1, kind_key: 1 }` index exists on `credentials`.

**Step 4 — Frontend flows page redesign + Credentials tab**

See §9.2 above. Replace the "Create Flow" tab with a split button, add the "Credentials" and "Executions" tabs to `page.tsx`, and implement `FlowCredentials.tsx`.

**Step 4b — Org-wide executions tab**

See §9.3 above. Add `GET /v0/orgs/{orgId}/executions` endpoint in `flows.py`, add SDK method, and implement `FlowExecutionsAll.tsx` reusing the per-flow executions view with an added Flow name column.

**Step 5 — `extends` registry support**

If multi-level kind inheritance is needed (e.g. `googleOAuth2Api` extending `oAuth2Api`), add `_resolve(key, seen)` merge logic to `credential_kind_registry.py`.

**Step 6 — OAuth2 (separate milestone)**

See §11 above.
