# DocRouter Credentials

Credential kinds, org-scoped storage, backend API, runtime injection, OAuth2 browser connect, and frontend UI.

**Related:** [`docrouter_http_request.md`](./docrouter_http_request.md)

---

## 1. Architecture overview

```
schemas/credential-kinds/<key>.json   ← global kind definitions (lru_cache on load)
credentials (MongoDB collection)      ← one saved instance per org, AES-encrypted fields
flow nodes: { credentials: { slot → credentialId } }  ← binding
```

At node execution time:

1. Slot binding is resolved → `fetch_credential_kind_and_fields(org_id, cred_id)`
2. `apply_runtime_credential_updates` runs optional token refresh / pre_auth
3. `render_credential_inject(kind, fields)` expands Jinja2 templates → headers / query / body dicts
4. The node merges the result into the outbound HTTP request

---

## 2. Credential kind file format

Kind definitions live in `schemas/credential-kinds/<key>.json`. Auto-discovered at startup; no registration call needed. The key must match the filename stem.

| Field | Type | Required | Purpose |
|-------|------|----------|---------|
| `key` | string | yes | Stable identifier; must match filename stem |
| `display_name` | string | yes | Human-readable label shown in UI |
| `auth_mode` | string | yes | `api_key`, `oauth2_authorization_code`, `oauth2_client_credentials`, `basic_auth`, `custom` |
| `secret_schema` | JSON Schema object | yes | Fields the org fills in; `"x-secret": true` marks values stripped from API responses |
| `inject` | object | no | `inject.headers`, `inject.query_params`, `inject.body` — Jinja2 templates using `{{ credentials.<field> }}` |
| `test_request` | object | no | `{ "method": "GET", "url": "…" }` for the `/test` endpoint; URL may contain `{{ credentials.<field> }}` |
| `extends` | string or array | no | Inherits and merges from named parent kind(s); see §3 |
| `runtime_fields` | array of strings | no | Field names computed at runtime (e.g. OAuth tokens); excluded from `secret_schema` |
| `experimental` | boolean | no | When `true`, kind is hidden unless the org has `experimental_features: true` |

### Minimal example — API key via header

```json
{
  "key": "acmeApi",
  "display_name": "Acme API",
  "auth_mode": "api_key",
  "secret_schema": {
    "type": "object",
    "additionalProperties": false,
    "required": ["apiKey"],
    "properties": {
      "apiKey": { "type": "string", "title": "API Key", "x-secret": true }
    }
  },
  "inject": {
    "headers": { "Authorization": "Bearer {{ credentials.apiKey }}" }
  },
  "test_request": { "method": "GET", "url": "https://api.acme.com/v1/me" }
}
```

### OAuth2 authorization-code example (extends)

```json
{
  "key": "slackOAuth2Api",
  "display_name": "Slack OAuth2 API",
  "auth_mode": "oauth2_authorization_code",
  "extends": ["oAuth2Api"],
  "experimental": true,
  "secret_schema": {
    "type": "object",
    "additionalProperties": false,
    "properties": {},
    "required": []
  },
  "runtime_fields": ["grantType", "authUrl", "accessTokenUrl", "oauthAccessToken", "oauthRefreshToken", "oauthExpiresAt"]
}
```

---

## 3. `extends` — kind inheritance

A kind may inherit from one or more parents via `extends`. The registry resolves the chain at startup and caches the merged result. Overlay rules:

- `secret_schema.properties`: overlay properties are merged on top of base; both `required` lists are unioned and intersected with the merged property set.
- `inject.headers / query_params / body`: merged (overlay wins on key conflicts).
- `test_request`: overlay wins if present; base is kept if overlay is absent.
- `runtime_fields`: concatenated, deduplicated.
- `pre_auth`: overlay wins if present.
- `experimental`: sticky — if either base or overlay is experimental, the merged kind is experimental.

Circular extends are detected at load time; broken kinds are skipped with a warning and excluded from `list_credential_kinds()`.

**Base `oAuth2Api` security fields** (inherited by `googleOAuth2Api`, `gmailOAuth2`, and other OAuth kinds):

| Field | UI | Purpose |
|-------|-----|---------|
| `ignoreSSLIssues` | Toggle | Skip TLS certificate verification on outbound HTTP (insecure) |
| `allowedHttpRequestDomains` | Select (`all` / `domains` / `none`) | Restrict which hosts HTTP Request nodes may call with this credential |
| `allowedDomains` | Text (shown when mode is `domains`) | Comma-separated allowlist; supports `*` wildcards |

The credential editor uses `x-ui-show-when` on `allowedDomains` (same mechanism as flow node parameters).

---

## 4. `credentials` MongoDB collection

```python
{
    "_id":               ObjectId,
    "organization_id":   str,
    "kind_key":          str,        # e.g. "httpHeaderAuth"
    "name":              str,        # user-chosen label, unique per org (case-insensitive)
    "encrypted_payload": str,        # AES-256-CFB encrypted JSON of all field values
    "created_at":        datetime,
    "created_by":        str,
    "updated_at":        datetime,
    "updated_by":        str,
}
```

**Encryption:** AES-256-CFB via `ad.crypto.encrypt_secret`; key derived from `NEXTAUTH_SECRET`. Single uniform scheme — every encrypted field in the database is written this way (credential payloads, access tokens, LLM provider keys, AWS/Azure/GCP secrets, webhook auth values, …).

**Payload format:** `v2:<urlsafe_b64(iv || ciphertext)>` with a fresh 16-byte IV from `os.urandom` per call, so identical plaintexts produce distinct ciphertexts. `ad.crypto.decrypt_secret` auto-detects the `v2:` prefix and falls back to the pre-fingerprint legacy format (bare urlsafe-base64, fixed IV from `sha256(key)[:16]`) so existing rows remain readable indefinitely. Application code paths re-encrypt as v2 on the next write to a given row; there is no scheduled re-encryption pass.

**Equality lookups (`access_tokens`).** Because the ciphertext is randomized, rows that need to be queried by their plaintext (currently only `access_tokens`) carry an extra indexed `fingerprint` column: `ad.crypto.fingerprint_secret(plaintext)` returns `HMAC-SHA256(NEXTAUTH_SECRET, plaintext)` as hex, deterministic and brute-force resistant for the high-entropy `secrets.token_urlsafe(32)` plaintexts the server issues. Authentication does `find_one({"fingerprint": fingerprint_secret(presented_token)})` and never decrypts the stored ciphertext on the hot path. Migrated in by `AddAccessTokenFingerprint`, which also swaps the unique index from `token` to `fingerprint` and **deletes** any `access_tokens` row whose stored ciphertext cannot be decrypted with the current secret (e.g. after `NEXTAUTH_SECRET` rotation) or decrypts to empty plaintext.

**Index:** `{ organization_id: 1, kind_key: 1 }` — created at startup.

---

## 5. Python kind registry

**File:** `packages/python/analytiq_data/flows/credential_kind_registry.py`

The raw JSON store and the resolved kind documents are both cached in a single `@lru_cache(maxsize=1)` bundle (`_credential_kinds_bundle`). The cache is populated once per process at first access. Tests that swap the schema directory must call `_credential_kinds_bundle.cache_clear()` before and after.

| Function | Purpose |
|----------|---------|
| `list_credential_kinds()` | All resolved kind documents, sorted by key |
| `get_credential_kind(key)` | One kind by key; raises `KeyError` if not found |
| `credential_secret_field_names(kind)` | Property names marked `x-secret` |

All three are exported as `ad.flows.*`.

---

## 6. Backend API

**File:** `packages/python/app/routes/flows_credentials.py`

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/v0/orgs/{orgId}/credential-kinds` | List available kinds; filters experimental unless org has `experimental_features: true` |
| `POST` | `/v0/orgs/{orgId}/credentials` | Create a credential; validates `secret_schema`; blocks experimental if org flag is off |
| `GET` | `/v0/orgs/{orgId}/credentials` | List org credentials (`?credential_kind=<key>` filter, pagination) |
| `GET` | `/v0/orgs/{orgId}/credentials/{credId}` | Get one credential (no secret fields) |
| `PUT` | `/v0/orgs/{orgId}/credentials/{credId}` | Update name and/or fields |
| `DELETE` | `/v0/orgs/{orgId}/credentials/{credId}` | Delete |
| `POST` | `/v0/orgs/{orgId}/credentials/{credId}/test` | Run runtime refresh, then call `test_request` URL via httpx |
| `POST` | `/v0/orgs/{orgId}/credentials/{credId}/oauth/initiate` | Begin OAuth2 browser flow; returns `{ authorization_url }` |
| `GET` | `/v0/callback/flow-oauth` | OAuth2 callback; exchanges code, persists tokens, redirects browser to frontend |

**`GET /credential-kinds`** response shape (per item):

```python
class CredentialKindSummary(BaseModel):
    key: str
    display_name: str
    auth_mode: str
    fields: list[dict]               # schema field metadata for the create form
    has_test_request: bool
    supports_oauth_browser_flow: bool
    oauth_redirect_uri: str | None   # when browser OAuth is supported
    has_pre_auth: bool
    experimental: bool
```

**`GET /credentials`** list response includes `public_fields` (non-secret fields decrypted from `encrypted_payload`) so the frontend can display current values without a separate fetch.

### Experimental gating

Kinds with `"experimental": true` are only visible and creatable when the org document has `experimental_features: true`. This is set via `PUT /v0/orgs/{orgId}` and toggled in the Org Settings UI. Once a credential is created it remains usable even if the flag is later disabled.

---

## 7. Runtime credential updates

**File:** `packages/python/analytiq_data/flows/credential_runtime.py`

`apply_runtime_credential_updates(org_id, cred_id, kind, fields)` is called before every credential use (node execution and `/test`). It:

1. Runs **`maybe_run_pre_auth`** if the kind has a `pre_auth` block (see §8).
2. Runs **`maybe_refresh_oauth_tokens`** for OAuth2 kinds (client-credentials re-grant; authorization-code refresh).
3. Persists updated fields back to MongoDB if anything changed.

Returns the (possibly refreshed) fields dict for use in injection.

### OAuth2 token refresh logic

`maybe_refresh_oauth_tokens` checks `fields["grantType"]`:

- **`clientCredentials`**: if `oauthAccessToken` is missing or `oauthExpiresAt` is within 120 seconds, posts `grant_type=client_credentials` to `accessTokenUrl` and stores the new token.
- **`authorizationCode`**: if `oauthRefreshToken` is set and `oauthExpiresAt` is within 120 seconds, posts `grant_type=refresh_token` and updates `oauthAccessToken` (and `oauthRefreshToken` if the provider rotates it).

For authorization-code flows, the initial tokens come from the browser OAuth flow (§9). Refresh happens automatically at runtime with no user interaction.

---

## 8. `pre_auth` block (session / expirable token credentials)

Some APIs require a login request to obtain a short-lived session token before every operation. This is modelled by adding a `pre_auth` block to the kind JSON:

```json
{
  "pre_auth": {
    "method": "POST",
    "url": "https://api.example.com/auth/login",
    "headers": { "Content-Type": "application/json" },
    "body": {
      "username": "{{ credentials.username }}",
      "password": "{{ credentials.password }}"
    },
    "token_json_path": "data.token",
    "expires_in_json_path": "data.expires_in",
    "access_token_field": "oauthAccessToken",
    "expires_at_field": "oauthExpiresAt"
  }
}
```

`maybe_run_pre_auth` fires when `fields[access_token_field]` is empty or `fields[expires_at_field]` is within 120 seconds of `time.time()`. The response is parsed with `token_json_path` (dot-separated) and stored back to `fields`.

**Current status:** the `pre_auth` runtime is fully implemented. No shipped kind schemas currently use it (0 of 371). It is ready to use in custom kind JSON files or future ported kinds.

---

## 9. OAuth2 browser connect flow

For `oauth2_authorization_code` kinds where `secret_schema` includes `grantType` (with `authorizationCode` or `pkce` in enum) and `authUrl`:

1. **User fills in** Client ID, Client Secret, Authorization URL, Token URL in the credential edit form (some kinds expose Grant Type **PKCE** for public/confidential apps that require RFC 7636).
2. **User clicks "Connect with provider"** → frontend calls `POST /oauth/initiate`.
3. **`oauth_initiate_flow_credential`** inserts a short-lived row in MongoDB collection `flow_oauth_states` (org, credential id, user id, **`grant_type`** as selected at initiate time, optional PKCE `code_verifier`, `expires_at`) and uses a random **opaque** `state` nonce in the authorize URL (no secrets in the query string). For grant type **pkce** it adds `code_challenge` and `code_challenge_method=S256` to the authorize URL.
4. **Frontend sets `window.location.href`** to the provider's authorization page.
5. **Provider redirects back** to `GET /v0/callback/flow-oauth?code=…&state=…`.
6. **`flow_oauth_callback`** loads and **deletes** that row by `state` (single-use, must be unexpired). Whether PKCE applies is decided **only** from `grant_type` on that row (not from the live credential), so changing `grantType` on the credential between redirect and callback cannot bypass PKCE or break a valid flow. It then exchanges the code via `_oauth_token_post` (`exchange_authorization_code`). For PKCE it sends `code_verifier` from the **server** row only. If the JSON response omits `access_token` (including HTTP 200 with an OAuth error body), a `RuntimeError` is raised and the browser is redirected with `flow_oauth=error`. Otherwise `oauthAccessToken`, `oauthRefreshToken`, and `oauthExpiresAt` are persisted on the credential.
7. **Redirect** to `{NEXTAUTH_URL}/orgs/{orgId}/flows?tab=credentials&flow_oauth=success`. The frontend detects `flow_oauth` in the URL, shows a toast, and cleans the query string.

### Configuration

| Env var | Purpose |
|---------|---------|
| `NEXTAUTH_SECRET` | Used elsewhere (e.g. session); **not** used to encode browser `state` for Connect — state is an opaque nonce keyed in MongoDB |
| `FLOW_OAUTH_PUBLIC_ORIGIN` | Base URL for the redirect URI registered with the OAuth provider (falls back to `PUBLIC_API_URL`, `DOCROUTER_API_PUBLIC_ORIGIN`, `http://127.0.0.1:8000`) |
| `NEXTAUTH_URL` | Base URL for the success/error redirect back to the frontend |

Redirect URI registered with the provider: `{FLOW_OAUTH_PUBLIC_ORIGIN}/v0/callback/flow-oauth`

### Security

- `authQueryParameters` in credential fields may add extra query parameters to the authorization URL, but cannot override `state`, `redirect_uri`, `response_type`, `client_id`, `code_challenge`, or `code_challenge_method` (locked).
- Pending OAuth context (including the PKCE **code_verifier**) lives only in **`flow_oauth_states`** until callback; the browser sees only the opaque `state` nonce. Rows expire after 15 minutes (TTL index on `expires_at`). **Single-use:** the row is removed when consumed.

---

## 10. Credential injection

**File:** `packages/python/analytiq_data/flows/credential_inject.py`

```python
render_credential_inject(kind, fields) → { "headers": {…}, "query_params": {…}, "body": {…} }
inject_body_as_json(inject_body) → { key: coerced_value, … }
coerce_template_json_value(val) → parsed JSON or original string
```

Templates use `{{ credentials.<field> }}` (Jinja2). Missing variables render as empty string (`Undefined`, not `StrictUndefined`) — a typo in a template key silently produces a blank value.

`render_credential_inject` is exported as `ad.flows.render_credential_inject`.

---

## 11. Frontend

### Credentials management tab (`FlowCredentials.tsx`)

- **Kind picker wizard**: step 1 is a searchable list of all available kinds; step 2 is the name + field form. Double-clicking a kind advances immediately to step 2.
- **OAuth "Connect" button**: shown in the edit form for `oauth2_authorization_code` kinds that support the browser flow. Disabled until Client ID, Secret, and URLs are saved. Clicking initiates the flow described in §9.
- **Test button**: calls `/test`; shows status code.
- **Experimental kinds**: hidden from the kind picker unless the org has `experimental_features` enabled.

### Node config credential widget (`FlowCredentialAuthenticationField.tsx`)

When a node's parameter schema has `x-ui-widget: credential_authentication`, the default per-slot credential panel is suppressed and this composite widget renders instead. It offers three modes:

- **None**: no credential bound.
- **Generic**: user picks an auth style (Bearer, Basic, …) then a saved credential of that kind.
- **Predefined**: user picks any saved credential compatible with this node; correct slot is chosen automatically.

Companion parameter `generic_auth_slot` (marked `x-ui-companion-of: authentication`) is rendered inside this widget, not as a standalone row.

### Organization settings (`OrganizationEdit.tsx`)

Checkbox "Show experimental features" toggles `experimental_features` on the org document. This is the only way to unlock experimental credential kinds.

---

## 12. Porting n8n credentials

### Current state (371 kinds in `schemas/credential-kinds/`)

| auth_mode | Count | Experimental |
|-----------|-------|-------------|
| `custom` | 170 | 170 |
| `api_key` | 105 | 102 |
| `oauth2_authorization_code` | 96 | 96 |
| **Total** | **371** | **368** |

Non-experimental (production-ready): `httpHeaderAuth`, `httpQueryAuth`, `httpBearerAuth`.

### Porting pipeline

**Step A — `tools/dump_credentials.js`**: Node.js script. Requires each compiled `.credentials.js` from `../n8n/packages/nodes-base/credentials/dist/`, instantiates the class, and emits one NDJSON line per type.

**Step B — `tools/port_credentials.py`**: Reads the NDJSON and writes one `schemas/credential-kinds/<key>.json` per successfully ported kind. Skips kinds with unsupported `authenticate` types or unresolvable property types (logs reasons).

Run via:
```
make credential-dump    # runs dump_credentials.js → /tmp/credentials.ndjson
make credential-port    # runs port_credentials.py reading that file
```

### Field mapping (n8n → DocRouter)

| n8n field | DocRouter field |
|-----------|----------------|
| `name` | `key` |
| `displayName` | `display_name` |
| `extends[]` | `extends` |
| `properties[].name` | `secret_schema.properties` key |
| `properties[].displayName` | `title` |
| `properties[].typeOptions.password` | `x-secret: true` |
| `properties[].required` | `secret_schema.required[]` |
| `properties[].type == "options"` | `enum` |
| `properties[].type == "hidden"` | `runtime_fields[]` (excluded from schema) |
| `authenticate.properties.headers` | `inject.headers` |
| `authenticate.properties.qs` | `inject.query_params` |
| `authenticate.properties.body` | `inject.body` |
| `test.request.baseURL + url` | `test_request.url` |

**Template conversion** — n8n uses `={{$credentials.field}}`; DocRouter uses Jinja2:
```python
re.sub(r"\{\{\s*\$credentials\.(\w+)\s*\}\}", r"{{ credentials.\1 }}", s.lstrip("="))
```

### What the ported kinds need before production use

Most of the 368 experimental kinds were auto-ported and have not been manually reviewed. Before marking a kind non-experimental:

1. Verify `secret_schema` fields and `required` list are correct.
2. Confirm `inject` templates render the right header/query/body.
3. Confirm `test_request.url` works (Jinja2-rendered) and returns 2xx with a valid credential.
4. Check that `extends` resolution produces the expected merged schema.
5. Remove `"experimental": true`.

Track per-kind sign-off in `schemas/credential-kinds/PORTING_STATUS.md`.

---

## 13. What is not yet implemented

### 13.1 `pre_auth` kind schemas

The `pre_auth` runtime is implemented but no shipped kind uses it. The ~7 n8n `preAuthentication` credentials (e.g. ERPNext, some CRMs) need kind JSON files with a `pre_auth` block. These are the ones the automated porter skips as unsupported.

### 13.2 OAuth1

~2 n8n credential kinds use OAuth1 (Twitter v1, some others). Defer unless a specific integration requires it. Would need a new `auth_mode: "oauth1"` and HMAC-SHA1 request signing in `credential_runtime`.

### 13.3 Custom `authenticate()` kinds

~24 n8n kinds use a custom TypeScript `authenticate()` function (AWS SigV4, HMAC, Digest with custom parameters, etc.). These cannot be ported as declarative JSON. Implement each as a dedicated Python credential module, similar to the existing AWS integration. Track in `PORTING_STATUS.md`.

### 13.4 Predefined credential integration on the HTTP Request node

The `predefined` mode in the authentication widget currently picks any org credential whose kind matches a slot. True n8n-style "predefined credential type" would let a node declare it natively targets a specific third-party service (e.g. `slackOAuth2Api`), and the UI would filter to only that kind. This requires node-type metadata changes and new UI filtering.
