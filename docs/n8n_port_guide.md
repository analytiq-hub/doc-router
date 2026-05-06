# Porting n8n nodes to DocRouter

This guide describes the **programmatic pipeline** for converting n8n node types (from the sibling `../n8n` clone) into DocRouter node packages — the `node.manifest.json` + `parameter.schema.json` + optional executor spec layout described in [`docrouter_nodes.md`](./docrouter_nodes.md) (declarative **`executor.kind`** + **`http_request_v1`** etc.: §6.2 there).

Goal: quickly bootstrap the DocRouter node ecosystem by translating the large n8n integration library rather than hand-authoring each node from scratch.

Related references: [`n8n_nodes.md`](./n8n_nodes.md) (n8n node inventory and type contracts), [`flows_workflow_interop.md`](./flows_workflow_interop.md) (broader interop goals).

---

## 1. Core observation: two tracks

Most n8n SaaS connectors are not really TypeScript programs — they are **declarative HTTP specs dressed in TypeScript**. They use `requestDefaults` plus `routing` on `INodeProperties` entries to describe HTTP calls. These map cleanly to DocRouter's `http_request_v1` declarative executor and can be ported fully automatically.

A smaller set have real imperative `execute()` logic (transforms, code nodes, database drivers). These get a **stub manifest** with a `python_class` executor; the Python behavior must be ported by hand.

```
../n8n  *.node.ts
         │
         ├─ uses requestDefaults / routing? ──→  declarative executor (http_request_v1)
         │                                        fully automatable
         │
         └─ has custom execute()? ────────────→  python_class stub (NotImplementedError)
                                                  metadata automatable, behavior manual
```

---

## 2. Input source

Do not parse TypeScript AST — it is fragile across upstream releases. Instead **require() the compiled `*.node.js` modules** from the built repo. Implemented as **`tools/dump_nodes.js`**: mandatory **`--upstream-root`**, discovery via repeatable **`--subdir REL`** paths *or* the **`FLOW_DUMP_SUBDIRS`** environment variable (**`:`**-separated relative paths under the upstream root).

Example (paths depend on how the sibling monorepo lays out packages):

```bash
FLOW_DUMP_SUBDIRS='packages/nodes-base/dist/nodes:packages/other-vendor-ai/dist/nodes' \
  node tools/dump_nodes.js --upstream-root ../upstream_nodes > tools/flow_node_dump.jsonl
```

`make flow-node-dump` passes **`FLOW_DUMP_SUBDIRS`** to **`dump_nodes.js`**. **`UPSTREAM_NODES_ROOT`** defaults to **`../n8n`** relative to the DocRouter makefile directory (`abspath` in the makefile), so the checkout can sit beside a sibling **`n8n`** tree without exporting env vars. **`make flow-node-port`** errors if zero packages are emitted unless **`tools/port_nodes.py --allow-empty`**. **`tools/flow_node_dump.jsonl`** updates only after a successful dump (write to temp file, then **`mv`**).

### Upstream toolchain and build (required)

The sibling monorepo is **pnpm-based**. If `pnpm` is missing, install it (for example `corepack enable && corepack prepare pnpm@latest --activate`, or `npm install -g pnpm`, or an OS package). From the **upstream repository root**, run **`pnpm install`**, then **`pnpm build`** so compiled artifacts exist (including **`packages/nodes-base/dist/nodes/**/*.node.js`** and any other trees you list in **`FLOW_DUMP_SUBDIRS`**). Without that, **`make flow-node-dump`** fails (**`dump_nodes.js`** exits nonzero: missing upstream directory, zero `*.node.js` matches, etc.) and **`tools/flow_node_dump.jsonl`** is left unchanged (atomic rename from a temp file).

### Verifying the JSONL before `flow-node-port`

Open **`tools/flow_node_dump.jsonl`** and spot-check important integrations (e.g. Slack, Airtable). A **healthy** row includes a full **`description.properties`** array (dozens of fields for large SaaS nodes). A **degraded** row often has only metadata such as **`displayName`**, **`name`**, **`defaultVersion`**, **`icon`**, **`group`** — and **no** (or empty) **`properties`**.

**Why this happens — versioned nodes:** many upstream nodes use a **thin base** `description` on the class and move the real UI and routing into **`nodeVersions`**: a map of version keys to **sub-constructors**, each with a complete `description`. **`tools/dump_nodes.js`** tries **`new SubCtor()`** for each entry. If instantiation **throws** (missing context, side effects, or environment), **no** version line is emitted for that sub-class; the tool then falls back to a single JSONL record using the **base** `description` only. **`tools/port_nodes.py`** correctly turns that into **schema-valid** packages with **empty `parameter.schema.json`**, missing **`credential_slots`**, and a **`python_class`** stub — which is **not** a faithful port.

**What to do:** fix or extend **`tools/dump_nodes.js`** (more robust construction, alternative extraction from compiled metadata, logging of `tryInstantiate` failures) and **re-dump**; optionally hand-merge rows for critical nodes; then re-run **`make flow-node-port`**.

**Declarative HTTP count:** even with full descriptions, **`http.spec.json`** is emitted only when the converter can extract a usable **`routing.request`**. Expect **most** packages to remain **`python_class`** until heuristics improve or nodes are ported by hand.

**`--validate`:** `python tools/port_nodes.py … --validate` checks **JSON Schema** shape for manifests (and **`http.spec.json`** when present). It does **not** prove behavioral parity with upstream or that the dump contained full **`properties`**.

---

## 3. Executor classification

Heuristic only: n8n can combine **`routing`** / **`requestDefaults`** with imperative **`execute()`** logic that ignores or extends the declarative path.

```python
def classify(description: dict, has_body_execute: bool) -> str:
    """Return 'declarative' or 'python_class'."""

    if has_body_execute:
        # Instantiating the version-specific class and inspecting whether
        # `execute` is the generic routing helper vs overridden is ideal; if unknown, err on python_class.
        return "python_class"

    if description.get("requestDefaults"):
        return "declarative"
    for prop in iter_properties(description):
        if prop.get("routing"):
            return "declarative"
    return "python_class"
```

When you only have the dump of **`.description`** (no class), treat nodes that **also** ship non-trivial **`execute`** as **`python_class`** after sampling the compiled module. If you cannot detect `execute` reliably, prefer **`python_class`** stubs for anything that is not a **pure routing** HTTP connector.

`iter_properties` flattens all nested `INodeProperties` entries including those inside `options[].values` and versioned node slices.

---

## 4. Metadata mapping

Manifest top-level fields derived from `INodeTypeDescription`:

| n8n field | DocRouter manifest field | Notes |
|---|---|---|
| `displayName` | `label` | |
| `name` | `key` | Prefix with integration namespace (`ext.` in generated output, e.g. `ext.slack`) |
| `description` | `description` | |
| `group[0]` | `category` | e.g. `"output"`, `"transform"` |
| `defaultVersion` \| `version` | `type_version` | Use `defaultVersion` when present; for arrays take the max |
| `inputs` | `min_inputs`, `max_inputs` | Count `Main` entries; `0` inputs → `is_trigger: true` |
| `outputs` | `outputs`, `output_labels` | Count `Main` outputs; use `outputNames` for labels if present |
| `trigger`/`poll`/`webhook` present | `is_trigger: true` | |
| `credentials[*]` | `credential_slots` | See §7 |
| `icon` | `icon_key` | Strip `file:` prefix; store path relative to package root |
| `usableAsTool` | (future) | Skip for now |

**`key` convention:** `ext.<integration>` (generated); adjust if you rename the namespace during import wiring.

---

## 5. Parameter mapping: `INodeProperties[]` → JSON Schema

Build a single `parameter.schema.json` `object` whose `properties` are the top-level parameters. Recurse into `collection` and `fixedCollection` types.

| n8n `type` | JSON Schema | Notes |
|---|---|---|
| `string` | `{"type": "string"}` | |
| `number` | `{"type": "number"}` | |
| `boolean` | `{"type": "boolean"}` | |
| `options` | `{"type": "string", "enum": [...]}` | `options[].value` → enum values; `options[].name` → **`x-ui-enum-names`** (UI hint array, same order as `enum`) |
| `multiOptions` | `{"type": "array", "items": {"type": "string", "enum": [...]}}` | |
| `collection` | `{"type": "object", "properties": {...}}` | Recurse into `options` |
| `fixedCollection` | `{"type": "object", "properties": {...}}` | Flatten `values` arrays into properties |
| `json` | `{"type": ["object", "string"]}` | n8n accepts either |
| `code` | `{"type": "string"}` | Add `$content_ref` if `default` is non-empty (write default to sidecar) |
| `color` | `{"type": "string", "pattern": "^#[0-9a-fA-F]{6}$"}` | |
| `dateTime` | `{"type": "string", "format": "date-time"}` | |
| `resourceLocator` | `{"type": "string"}` | Loses resource-picker UI; acceptable for first pass |
| `notice` | drop | UI-only display element, carries no data |
| `hidden` | include as optional | Often carries `default` values used by routing |

**`default` values:** carry through as JSON Schema `default` on the property.

**UI extensions (`x-ui-*`):** `analytiq_data/flows/port/schema.py` (`inode_property_to_schema`) attaches DocRouter UI hints alongside validation shape (see `docs/flow_parameter_schema_ui_plan.md`):

| n8n source | Schema extension |
|---|---|
| `placeholder` | **`x-ui-placeholder`** |
| `type: "code"` | **`x-ui-widget": "code"`** (Monaco code path in the flows editor) |
| `displayOptions.show` with **exactly one** key | **`x-ui-show-when`**: `{ "field": "<that key>", "in": [<allowed values>] }` |

If `show` lists multiple keys (conjunctive n8n visibility) or uses **`hide`**, nothing is emitted yet — those fields stay visible until the mapper is extended.

**`required` fields:** a parameter is required in the schema if `required: true` is set on the `INodeProperty` and it has no `default`.

---

## 6. Declarative executor: assembling `http.spec.json`

For nodes classified as `declarative`, assemble an `http_request_v1` spec from:

| n8n source | `http.spec.json` field |
|---|---|
| `requestDefaults.baseURL` | prepended to per-operation `url` |
| `requestDefaults.headers` | merged into `headers` |
| `routing.request.method` | `method` |
| `routing.request.url` | `url` (append to baseURL) |
| `routing.request.qs.*` | `query_params` |
| `routing.request.body.*` | `body` (inline) or `$content_ref` sidecar if large |
| `routing.request.headers` | merged into `headers` |
| `routing.output.postReceive[].type === 'rootProperty'` | `response_jmespath` |
| `routing.output.postReceive[].type === 'set'` | `response_set` |

Credential token injection uses Jinja2 expressions referencing `credentials.*`:

```json
{
  "headers": {
    "Authorization": "Bearer {{ credentials.slackToken }}"
  }
}
```

Parameter values in the spec use `{{ parameters.<name> }}`. Boolean/numeric parameters that gate request fields should be expressed as Jinja2 conditionals:

```
{% if parameters.include_metadata %},"metadata": true{% endif %}
```

If the assembled spec body exceeds ~200 characters of inline JSON, write it to `templates/body.json.tpl` and use `$content_ref`:

```json
{
  "body": {
    "$content_ref": "templates/body.json.tpl",
    "$content_media_type": "application/json"
  }
}
```

---

## 7. Credential system

DocRouter uses the same three-layer separation as n8n:

| Concept | DocRouter | n8n equivalent |
|---|---|---|
| **Credential kind** | Global type definition: key, auth mode, secret field schema, inject rules. Stored in `schemas/credential-kinds/<key>.json`. | `ICredentialType` in `*.credentials.ts` |
| **Organization credential** | One stored instance per org: kind reference + encrypted field payload. | Saved credential item in the n8n database |
| **Flow node binding** | Per node, maps a slot name → an org credential id. | `credentials: { “<slot>”: “<id>” }` in workflow JSON |

Manifest `credential_slots` (already generated by the porter) names the slots and points each to its kind via `docrouter_binding`. The runtime resolves bindings → decrypts fields → exposes a flat `credentials.*` dict to Jinja2 in `http.spec.json`.

---

### 7.1 N8n credential anatomy

Every n8n credential type is a TypeScript class implementing `ICredentialType`. The relevant fields are:

| Field | Purpose |
|---|---|
| `name` | Stable registry key — this is what nodes reference and what DocRouter uses as the kind key |
| `displayName` | Human-readable label |
| `extends` | Inherit properties from a base type (e.g. `oAuth2Api`) |
| `genericAuth` | `true` on base auth types (e.g. `oAuth2Api`) that n8n knows how to drive automatically |
| `properties` | `INodeProperties[]` — the form fields the user fills in; typed exactly like node parameters |
| `authenticate` | Injection rule: how to attach the decrypted fields to outgoing HTTP requests |
| `test` | Optional test request used to verify the saved credential |

**Example 1 — Slack API (API token)**

Source: [`../n8n/packages/nodes-base/credentials/SlackApi.credentials.ts`](../../n8n/packages/nodes-base/credentials/SlackApi.credentials.ts)

```typescript
export class SlackApi implements ICredentialType {
    name = ‘slackApi’;
    displayName = ‘Slack API’;
    documentationUrl = ‘slack’;

    properties: INodeProperties[] = [
        {
            displayName: ‘Access Token’,
            name: ‘accessToken’,
            type: ‘string’,
            typeOptions: { password: true },
            default: ‘’,
            required: true,
        },
    ];

    authenticate: IAuthenticateGeneric = {
        type: ‘generic’,
        properties: {
            headers: {
                Authorization: ‘=Bearer {{$credentials.accessToken}}’,
            },
        },
    };

    test: ICredentialTestRequest = {
        request: {
            baseURL: ‘https://slack.com’,
            url: ‘/api/users.profile.get’,
        },
    };
}
```

Key observations:
- One field: `accessToken` (password type → encrypted at rest).
- Injection: appends `Authorization: Bearer <token>` header to every request.
- Test: a cheap GET call whose HTTP 200 proves the token is accepted.

**Example 2 — Google OAuth2 (authorization code flow)**

Source: [`../n8n/packages/nodes-base/credentials/OAuth2Api.credentials.ts`](../../n8n/packages/nodes-base/credentials/OAuth2Api.credentials.ts) (base) + [`../n8n/packages/nodes-base/credentials/GoogleOAuth2Api.credentials.ts`](../../n8n/packages/nodes-base/credentials/GoogleOAuth2Api.credentials.ts) (extension)

The base `oAuth2Api` type defines the generic OAuth2 form:

```typescript
// OAuth2Api.credentials.ts (base — genericAuth = true, driven by n8n’s OAuth engine)
export class OAuth2Api implements ICredentialType {
    name = ‘oAuth2Api’;
    genericAuth = true;   // n8n drives the token exchange and refresh

    properties: INodeProperties[] = [
        { name: ‘grantType’,       type: ‘options’,  default: ‘authorizationCode’ },
        { name: ‘authUrl’,         type: ‘string’,   required: true },
        { name: ‘accessTokenUrl’,  type: ‘string’,   required: true },
        { name: ‘clientId’,        type: ‘string’,   required: true },
        { name: ‘clientSecret’,    type: ‘string’,   typeOptions: { password: true }, required: true },
        { name: ‘scope’,           type: ‘string’,   default: ‘’ },
        { name: ‘authQueryParameters’, type: ‘string’, default: ‘’ },
        { name: ‘authentication’,  type: ‘options’,  default: ‘header’ },
    ];
}
```

`GoogleOAuth2Api` extends this base and hard-codes Google’s endpoints:

```typescript
// GoogleOAuth2Api.credentials.ts
export class GoogleOAuth2Api implements ICredentialType {
    name = ‘googleOAuth2Api’;
    extends = [‘oAuth2Api’];   // inherits all base properties
    displayName = ‘Google OAuth2 API’;

    properties: INodeProperties[] = [
        { name: ‘grantType’,            type: ‘hidden’, default: ‘authorizationCode’ },
        { name: ‘authUrl’,              type: ‘hidden’, default: ‘https://accounts.google.com/o/oauth2/v2/auth’ },
        { name: ‘accessTokenUrl’,       type: ‘hidden’, default: ‘https://oauth2.googleapis.com/token’ },
        { name: ‘authQueryParameters’,  type: ‘hidden’, default: ‘access_type=offline&prompt=consent’ },
        { name: ‘authentication’,       type: ‘hidden’, default: ‘body’ },
    ];
}
```

The `hidden` overrides pin the Google-specific endpoints; the user still sees and fills in `clientId`, `clientSecret`, and `scope`. N8n’s OAuth engine stores the resulting `access_token` and `refresh_token` and injects `Authorization: Bearer <access_token>` automatically for `genericAuth` types.

---

### 7.2 DocRouter credential kind schema

Each credential kind is a JSON file at `schemas/credential-kinds/<key>.json`. The schema is not yet implemented; the design below is what to build.

```
schemas/
└── credential-kinds/
    ├── slackApi.json
    ├── googleOAuth2Api.json
    └── ...
```

**Top-level fields:**

| Field | Type | Purpose |
|---|---|---|
| `key` | string | Stable identifier — must equal n8n’s `name` where possible |
| `display_name` | string | Human-readable label |
| `auth_mode` | enum | `”api_key”`, `”oauth2_authorization_code”`, `”oauth2_client_credentials”`, `”basic_auth”`, `”custom”` |
| `extends` | string? | Key of a base kind whose fields and OAuth config are inherited (mirrors n8n’s `extends`) |
| `secret_schema` | JSON Schema | Fields the org fills in — what is stored encrypted (analogous to n8n `properties` minus `hidden` entries) |
| `oauth2` | object? | OAuth2-specific config: `auth_url`, `token_url`, `auth_query_params`, `token_endpoint_auth_method` |
| `inject` | object? | Header/query injection template using `{{ credentials.<field> }}` (analogous to n8n `authenticate`) |
| `test_request` | object? | `{ method, url }` for credential verification |

`auth_mode` derivation from n8n:

| N8n pattern | `auth_mode` |
|---|---|
| `authenticate.type === ‘generic’` with header/query injection | `”api_key”` |
| `extends [‘oAuth2Api’]`, `grantType` = `authorizationCode` | `”oauth2_authorization_code”` |
| `extends [‘oAuth2Api’]`, `grantType` = `clientCredentials` | `”oauth2_client_credentials”` |
| `authenticate.type === ‘generic’` with `Authorization: Basic ...` | `”basic_auth”` |
| Has `execute()` or non-standard auth | `”custom”` |

---

### 7.3 Example: Slack API (API token)

**DocRouter kind file:** `schemas/credential-kinds/slackApi.json`

```json
{
  “key”: “slackApi”,
  “display_name”: “Slack API”,
  “auth_mode”: “api_key”,
  “secret_schema”: {
    “type”: “object”,
    “additionalProperties”: false,
    “required”: [“accessToken”],
    “properties”: {
      “accessToken”: {
        “type”: “string”,
        “title”: “Access Token”,
        “x-secret”: true,
        “description”: “Slack Bot or User OAuth token (xoxb-… or xoxp-…)”
      }
    }
  },
  “inject”: {
    “headers”: {
      “Authorization”: “Bearer {{ credentials.accessToken }}”
    }
  },
  “test_request”: {
    “method”: “GET”,
    “url”: “https://slack.com/api/users.profile.get”
  }
}
```

**Node manifest slot** (already generated by the porter for any Slack node):

```json
“credential_slots”: [
  {
    “slot”: “slackApi”,
    “label”: “Slack API”,
    “required”: true,
    “docrouter_binding”: “organization_credential_kind:slackApi”
  }
]
```

**`http.spec.json` usage** (declarative Slack node):

```json
{
  “method”: “POST”,
  “url”: “https://slack.com/api/chat.postMessage”,
  “headers”: {
    “Content-Type”: “application/json; charset=utf-8”,
    “Authorization”: “Bearer {{ credentials.accessToken }}”
  },
  “body”: {
    “channel”: “{{ parameters.channel }}”,
    “text”: “{{ parameters.text }}”
  }
}
```

The `credentials.accessToken` key matches the field name in `secret_schema` — the runtime decrypts the stored instance and makes it available under exactly that path.

---

### 7.4 Example: Google OAuth2 (authorization code flow)

Google’s OAuth2 uses a two-level kind hierarchy in n8n (base `oAuth2Api` + `googleOAuth2Api`). DocRouter mirrors this with `extends`.

**Base kind:** `schemas/credential-kinds/oAuth2Api.json`

```json
{
  “key”: “oAuth2Api”,
  “display_name”: “OAuth2 API”,
  “auth_mode”: “oauth2_authorization_code”,
  “secret_schema”: {
    “type”: “object”,
    “additionalProperties”: false,
    “required”: [“clientId”, “clientSecret”],
    “properties”: {
      “clientId”:     { “type”: “string”, “title”: “Client ID” },
      “clientSecret”: { “type”: “string”, “title”: “Client Secret”, “x-secret”: true },
      “scope”:        { “type”: “string”, “title”: “Scope”, “default”: “” }
    }
  },
  “runtime_fields”: {
    “access_token”:  { “x-secret”: true, “description”: “Written by DocRouter after token exchange” },
    “refresh_token”: { “x-secret”: true, “description”: “Written by DocRouter after token exchange” }
  },
  “inject”: {
    “headers”: {
      “Authorization”: “Bearer {{ credentials.access_token }}”
    }
  }
}
```

`runtime_fields` records fields that DocRouter writes (not the user): after the OAuth authorization-code exchange, DocRouter stores `access_token` and `refresh_token` in the encrypted payload alongside the user-supplied `clientId` / `clientSecret`. The refresh loop replaces `access_token` before each execution when it has expired.

**Google extension:** `schemas/credential-kinds/googleOAuth2Api.json`

```json
{
  “key”: “googleOAuth2Api”,
  “display_name”: “Google OAuth2 API”,
  “extends”: “oAuth2Api”,
  “oauth2”: {
    “auth_url”:                   “https://accounts.google.com/o/oauth2/v2/auth”,
    “token_url”:                  “https://oauth2.googleapis.com/token”,
    “auth_query_params”:          “access_type=offline&prompt=consent”,
    “token_endpoint_auth_method”: “client_secret_post”
  }
}
```

The extension inherits all fields and inject rules from `oAuth2Api` and overrides only the OAuth endpoints. The user still fills in `clientId`, `clientSecret`, and optionally `scope` — identical to n8n.

**Scoped sub-kinds** (e.g., Google Sheets, Gmail) narrow the scope but add no new user fields:

```json
{
  “key”: “googleSheetsOAuth2Api”,
  “display_name”: “Google Sheets OAuth2 API”,
  “extends”: “googleOAuth2Api”,
  “oauth2”: {
    “default_scopes”: “https://www.googleapis.com/auth/spreadsheets”
  }
}
```

**Node manifest slot** (generated for a Google Sheets node):

```json
“credential_slots”: [
  {
    “slot”: “googleSheetsOAuth2Api”,
    “label”: “Google Sheets OAuth2 API”,
    “required”: true,
    “docrouter_binding”: “organization_credential_kind:googleSheetsOAuth2Api”
  }
]
```

**`http.spec.json` usage** (inject rule is inherited, so the spec just uses the token):

```json
{
  “method”: “GET”,
  “url”: “https://sheets.googleapis.com/v4/spreadsheets/{{ parameters.spreadsheetId }}/values/{{ parameters.range }}”,
  “headers”: {
    “Authorization”: “Bearer {{ credentials.access_token }}”
  }
}
```

**OAuth2 runtime flow:**

```
1. Org admin creates a credential: kind=googleSheetsOAuth2Api, fills clientId/clientSecret/scope.
2. DocRouter initiates the authorization-code redirect: builds auth_url from kind.oauth2,
   sends user to Google consent screen.
3. Google redirects back with ?code=…; DocRouter POSTs to token_url, stores
   access_token + refresh_token into the encrypted credential payload.
4. At flow execution: runtime checks access_token expiry, calls token_url with
   refresh_token if needed, then builds credentials.* dict and substitutes into http.spec.json.
```

Steps 2–4 are **not yet implemented** — they require the credential storage layer (§12.4) and a token refresh loop. Until then, OAuth nodes can be tested by manually inserting tokens into the encrypted payload.

---

### 7.5 Mapping n8n credentials → DocRouter kinds (automation)

**Phase A (done):** the porter reads `description.credentials` from the node dump and emits `credential_slots` in each manifest. The actual implementation in [`packages/python/analytiq_data/flows/port/converter.py`](../packages/python/analytiq_data/flows/port/converter.py):

```python
def map_credentials(description: dict) -> list[dict]:
    out = []
    for c in description.get(“credentials”) or []:
        name = c.get(“name”)
        if not name:
            continue
        out.append({
            “slot”: name,
            “label”: str(c.get(“displayName”) or name),
            “required”: c.get(“required”) is not False,
            “docrouter_binding”: f”organization_credential_kind:{name}”,
        })
    return out
```

This produces correct slots but cannot fill in `secret_schema`, `auth_mode`, or `inject` — those come from the credential type definition, not the node’s description.

**Phase B (not started) — kind catalog from n8n:** add `tools/dump_credentials.js` parallel to `dump_nodes.js`. It walks compiled `packages/nodes-base/dist/credentials/*.credentials.js`, `require()`s each module, instantiates the class, and emits one JSONL record per type:

```jsonl
{“name”:”slackApi”,”displayName”:”Slack API”,”properties”:[...],”authenticate”:{...},”test”:{...}}
{“name”:”oAuth2Api”,”displayName”:”OAuth2 API”,”genericAuth”:true,”properties”:[...],”extends”:null}
{“name”:”googleOAuth2Api”,”displayName”:”Google OAuth2 API”,”extends”:[“oAuth2Api”],”properties”:[...]}
```

**Phase C (not started) — converter:** `tools/port_credentials.py` reads that JSONL and writes `schemas/credential-kinds/<key>.json` using the mapping rules:

| N8n source | DocRouter kind field |
|---|---|
| `name` | `key` |
| `displayName` | `display_name` |
| `extends[0]` (resolved) | `extends` (inherit base kind) |
| `genericAuth === true` + grantType property | `auth_mode: “oauth2_…”` |
| `authenticate.properties.headers` | `inject.headers` (translate `{{$credentials.x}}` → `{{ credentials.x }}`) |
| `authenticate.properties.qs` | `inject.query_params` |
| Non-hidden `properties[]` | `secret_schema.properties` (same type mapping as §5) |
| `hidden` properties with fixed `default` | `oauth2.*` config values |
| `test.request` | `test_request` |

**Inject expression translation:** n8n uses `=Bearer {{$credentials.accessToken}}`; DocRouter uses `Bearer {{ credentials.accessToken }}`. Strip the leading `=`, replace `{{$credentials.` with `{{ credentials.`.

---

### 7.6 Build phases

| Phase | Scope | Status |
|---|---|---|
| **A — Slot references from nodes** | `credential_slots` in every generated manifest (from `description.credentials`). | **Done** |
| **B — Kind dump from n8n** | `tools/dump_credentials.js`: walk compiled `*.credentials.js`, emit JSONL per type. | **Not started** |
| **C — DocRouter kind files** | `tools/port_credentials.py`: JSONL → `schemas/credential-kinds/<key>.json` with `secret_schema`, `auth_mode`, `inject`. Check in base kinds (`oAuth2Api`, `slackApi`, `googleOAuth2Api`, …) manually for the most important integrations. | **Not started** |
| **D — Storage + API** | Org-scoped encrypted store + CRUD (`POST /orgs/{org}/credentials`, `GET`, `DELETE`). Kind registry validates stored payload against `secret_schema`. | **Not started** |
| **E — Flow bindings** | Flow nodes store `credentials: { “<slot>”: “<credential_id>” }`, validated against `credential_slots`. | **Not started** |
| **F — Frontend** | Per slot, a credential picker filtered by kind from `docrouter_binding`. | **Not started** |
| **G — Runtime injection** | Resolve binding → decrypt → build `credentials.*` dict; call token refresh for OAuth kinds before Jinja substitution. | **Not started** |

**Recommended build order:** **B → C** (kinds must exist before UI can show them), then **D**, then **E + G** together (binding storage + runtime injection are coupled), with **F** in parallel. **Phase A** already unblocks listing credential slots on generated nodes in the UI.

---

### 7.7 Mapping pitfalls (information loss)

- **Without phase B/C**, DocRouter knows slot ids and labels but not the field list for the OAuth/API form — users cannot fill in credentials without manual docs.
- **Jinja keys in `http.spec.json`** (e.g. `{{ credentials.accessToken }}`) must exactly match the field names in `secret_schema`. The kind catalog (phase B/C) plus the expression-translation rule (`$credentials.x` → `credentials.x`) must agree. If a generated `http.spec.json` uses `credentials.accessToken` but the kind schema stores the field as `access_token`, injection silently emits an empty string.
- **Inherited fields:** when `googleOAuth2Api` extends `oAuth2Api`, `clientId` / `clientSecret` live in the base kind’s `secret_schema`. The runtime must merge inherited fields before decryption; the kind loader must resolve `extends` chains.
- **OAuth token refresh:** n8n drives token refresh automatically for `genericAuth` types. DocRouter must replicate this loop (check `exp` in the stored `access_token`, call `token_url` with `refresh_token` when expired) before each execution — otherwise OAuth nodes fail silently after ~1 hour.

---

## 8. Output layout

One directory per ported node under `nodes/`:

```
nodes/
└── ext_slack_post_message/
    ├── node.manifest.json       ← generated
    ├── parameter.schema.json    ← generated
    ├── http.spec.json           ← generated (declarative track only)
    └── templates/
        └── body.json.tpl        ← generated if body is large
```

The CLI defaults to **`packages/python/analytiq_data/flows/port/generated_nodes/`** (`--out`) so stubs are importable as `analytiq_data.flows.port.generated_nodes.<slug>.node_impl`. Pass `--out` elsewhere if needed and adjust **`executor.import`** accordingly.

For `python_class` stubs, also emit a skeleton Python file:

```
nodes/
└── ext_postgres_query/
    ├── node.manifest.json
    ├── parameter.schema.json
    └── node_impl.py             ← stub; behavior must be ported by hand
```

**`node_impl.py` stub template:** (duck-types the **`NodeType`** protocol — do not subclass it; match fields and method signatures like existing nodes, e.g. [`packages/python/analytiq_data/flows/nodes/code.py`](../packages/python/analytiq_data/flows/nodes/code.py).)

```python
from typing import Any

import analytiq_data as ad


class ExtPostgresQueryNode:
    """Upstream Postgres node — stub."""

    key = "ext.postgres_query"
    label = "Postgres"
    description = "Stub: implement execute() for DocRouter."
    category = "Database"
    is_trigger = False
    is_merge = False
    min_inputs = 1
    max_inputs = 1
    outputs = 1
    output_labels = ["main"]
    icon_key = None
    batch_execute_inputs = False
    parameter_schema: dict[str, Any] = {
        "type": "object",
        "properties": {},
        "additionalProperties": False,
    }

    def validate_parameters(self, params: dict[str, Any]) -> list[str]:
        return []

    async def execute(
        self,
        context: ad.flows.ExecutionContext,
        node: dict[str, Any],
        inputs: list[list[ad.flows.FlowItem]],
    ) -> list[list[ad.flows.FlowItem]]:
        raise NotImplementedError("ext.postgres_query: Python stub not implemented")
```

---

## 9. Known gaps and first-pass limitations

| Gap | Impact | Mitigation |
|---|---|---|
| `displayOptions` partial mapping | Only single-key `show` maps to **`x-ui-show-when`**; multi-key / `hide` unchanged | Extend `port/schema.py` or hand-annotate manifests |
| `loadOptions` / `listSearch` methods | Dynamic dropdowns become plain `string` fields | Schema gets `{"type": "string"}`; user types value manually |
| Binary data nodes (files, images) | Cannot be ported declaratively | `python_class` stub; manual Python port |
| Sub-workflow nodes (`ExecuteWorkflow`) | DocRouter has a different sub-flow model | Stub only |
| n8n-specific helpers (`$node`, `$workflow`, `$execution`) | Used in some `execute()` bodies | Manual port only; no equivalent in DocRouter today |
| Multi-output routing (Switch, If) | n8n uses multiple `Main` outputs; DocRouter supports `outputs > 1` | Port is possible but routing logic needs Python |
| Versioned nodes (`VersionedNodeType`, `nodeVersions`) | Multiple `typeVersion` slices; sub-constructor `description` is the source of truth | If sub-constructors fail to instantiate in **`dump_nodes.js`**, JSONL contains only the **base** shell → empty parameter schema in DocRouter. Fix the dumper / environment; re-dump per version key you need; bump **`type_version`** from **`integration_type_version_key`** when present |
| Expression URLs (`=…` prefix on `routing.request.url`) | Leading `=` is stripped in **`http_spec.py`**; remaining string may still be upstream expression syntax | Treat as manual: Jinja/templates in **`http.spec.json`** or **`python_class`** |
| Incomplete declarative extraction | Nodes with `routing` / `requestDefaults` that omit a simple `routing.request` dict fall back to **`python_class`** | Converter prints stderr warnings per slug; inspect upstream `properties` trees |

---

## 10. Validation after generation

**Schema vs semantics:** validating manifests guarantees **syntax** compatible with **`schemas/`** — not that each node matches upstream capabilities. Combine this with **JSONL spot-checks** (§2, “Verifying the JSONL before `flow-node-port`”) so versioned nodes did not collapse to empty **`properties`**.

Run the standard §8 pipeline from [`docrouter_nodes.md`](./docrouter_nodes.md) on every generated package. The PyPI **`jsonschema`** package does not always install a working **`jsonschema` CLI** — use **`check-jsonschema`** ([PyPI](https://pypi.org/project/check-jsonschema/)) or a small Python harness:

```bash
# Manifests (Draft 7 validator; requires: pip install jsonschema)
python <<'PY'
import json, glob, jsonschema

def main():
    with open("schemas/flow-node-manifest-v1.json") as f:
        manifest_schema = json.load(f)
    jsonschema.Draft7Validator.check_schema(manifest_schema)
    mv = jsonschema.Draft7Validator(manifest_schema)
    for path in sorted(glob.glob("packages/python/analytiq_data/flows/port/generated_nodes/*/node.manifest.json")):
        with open(path) as f:
            mv.validate(json.load(f))
        print(path, "ok")

main()
PY

# Parameter schemas (Draft 7 meta-schema check only)
for f in packages/python/analytiq_data/flows/port/generated_nodes/*/parameter.schema.json; do
  python -c "import jsonschema, json; jsonschema.Draft7Validator.check_schema(json.load(open('$f')))"
done

# Declarative specs (when present)
python <<'PY'
import json, glob, jsonschema
with open("schemas/runtimes/http_request_v1.schema.json") as f:
    spec_schema = json.load(f)
jsonschema.Draft7Validator.check_schema(spec_schema)
sv = jsonschema.Draft7Validator(spec_schema)
for path in sorted(glob.glob("packages/python/analytiq_data/flows/port/generated_nodes/*/http.spec.json")):
    with open(path) as f:
        sv.validate(json.load(f))
    print(path, "ok")
PY
```

Alternatively: `check-jsonschema --schemafile schemas/flow-node-manifest-v1.json packages/python/analytiq_data/flows/port/generated_nodes/*/node.manifest.json` (and similarly for **`http.spec.json`**). Add this as a CI step when the dump or converter changes.

---

## 11. Suggested implementation order

**Packaging track (mostly done — dump quality still iterative)**

1. **Upstream:** install **pnpm**, **`pnpm install`** + **`pnpm build`** in the sibling clone so **`dist/**/*.node.js`** exists (§2).
2. ~~**`make flow-node-dump`** → **`tools/flow_node_dump.jsonl`**~~ — **Done** mechanically (§2, §12.7); verify JSONL for **versioned** nodes before trusting bulk output (§2).
3. ~~**`make flow-node-port`** / **`python tools/port_nodes.py --validate`**~~ — **Done** (§12.8).
4. **Ongoing:** run **`pytest packages/python/tests/test_flow_port_converter.py`** when changing the converter or **`http_spec.py`**; re-dump when upstream **`*.node.js`** changes; tighten **`dump_nodes.js`** when **`nodeVersions` instantiation** fails for important nodes.

**To make ported nodes executable**

5. Build **§12.1 → §12.4** in order (resolver → loader → **`http_request_v1`** → credentials) — see **Status** at the **end** of this document for a checklist and recommended order.
6. Expand the generated catalogue; prioritize implementing high-value **`python_class`** stubs manually where declarative mapping is insufficient.
7. Improve declarative **`http.spec.json`** generation using real failures (multi-operation routing, **`response_set`**, templated bodies).

---

## 12. DocRouter prerequisites (runtime + product gaps)

What follows blocks **executing** flows that use generated packages. **§12.7–§12.8** are the **authoring toolchain** (already implemented).

### Blockers — nothing works without these

#### 12.1 `$content_ref` resolver utility

**Implemented.** [`analytiq_data.flows.content_ref.resolve_content_refs`](../packages/python/analytiq_data/flows/content_ref.py) walks dict/list trees, resolves **package-relative** paths (no `..`), and inlines **bare** `{"$content_ref": ...}` objects plus **JSON Schema-style** nodes with `type` in `string|object|array` and `$content_ref` (materializes `default`). JSON sidecars are parsed when unambiguous; files containing Jinja (`{{` / `{%`) stay as text for a later interpolation pass. Tests: [`packages/python/tests/test_content_ref.py`](../packages/python/tests/test_content_ref.py).

The manifest loader (§12.2) and declarative runtime (§12.3) should call this helper after loading `parameter.schema.json` / `http.spec.json` from disk (**not** wired in yet — library only).

#### 12.2 Node manifest loader

Currently all nodes are hardcoded Python classes registered at startup. There is no mechanism to scan a `nodes/` directory, read `node.manifest.json` files, and register them as `NodeType` instances. Needed:

- Walk `nodes/*/node.manifest.json`; resolve `parameter_schema_ref` and run **`analytiq_data.flows.content_ref.resolve_content_refs`** on the loaded parameter schema
- For `python_class` executors: dynamically import the specified module and class
- For `declarative` executors: instantiate the appropriate runtime interpreter with the resolved spec

#### 12.3 Declarative executor runtime (`http_request_v1`)

No generic HTTP request node exists. The declarative track emits `http.spec.json` files that have nothing to run them. The runtime interpreter must:

- Resolve `$content_ref` sidecars in the spec (**`resolve_content_refs`**, §12.1)
- Interpolate Jinja2 `{{ parameters.* }}` and `{{ credentials.* }}` expressions
- Make the HTTP call with the resolved method, URL, headers, and body
- Map the response to output `FlowItem` objects via `response_jmespath`

#### 12.4 Credential storage

Completely absent. No org-level credential store, no `credential_slots` binding, and no injection into the execution context. Most ported SaaS nodes are non-functional without this. Three layers are needed:

| Layer | What is needed |
|---|---|
| Storage | Org-scoped encrypted key-value store (e.g. `credentials` MongoDB collection, values encrypted at rest) |
| API | CRUD endpoints per org (`POST /orgs/{org}/credentials`, `GET`, `DELETE`) |
| Runtime | At execution time, resolve `credential_slots` for the current node and inject as `credentials.*` into the Jinja2 / expression context |

Product-facing **phasing** (kind catalog from n8n, flow bindings, UI) is spelled out in **§7.3**; implement storage/API/runtime here in tandem with those steps.

### Important — most nodes degrade without these

#### 12.5 Frontend parameter rendering gaps

The current frontend handles `string`, `number`, `boolean`, `enum` (select dropdown), `object`/`array` (Monaco editor), and code editors. Missing for n8n parity:

| n8n type | Gap | Interim fallback |
|---|---|---|
| `multiOptions` | Multi-select / checkbox list | Monaco JSON array editor |
| `collection` | Sub-form with add/remove rows | Monaco JSON object editor |
| `fixedCollection` | Keyed sub-object builder | Monaco JSON object editor |
| `notice` | Inline info/warning banner (display-only) | Omit |
| Conditional visibility | Fields shown/hidden based on another field's value | Show all fields unconditionally |

`multiOptions` → `array` of `enum` is the most common case and should be prioritized; the others can fall back to Monaco JSON initially.

#### 12.6 JSON Schema `default` propagation

The engine validates parameters against `parameter_schema` but does not apply `default` values when a parameter is omitted. n8n nodes rely heavily on defaults, particularly `hidden` parameters that carry routing metadata. The engine should apply JSON Schema defaults before calling `execute()`.

### Toolchain — needed to generate the packages

#### 12.7 `tools/dump_nodes.js`

**Implemented** with known limits. Walks compiled `*.node.js` modules, **`require()`**s each file, discovers constructors, **`tryInstantiate`**, and emits JSONL (`source`, `description`, optional `integration_type_version_key`). For **`nodeVersions`**, it emits one record per successfully instantiated sub-class; **failed** `new SubCtor()` attempts are skipped silently today, which can leave only the **base** `description` for that file (see §2). Run **`make flow-node-dump`** (makefile **`UPSTREAM_NODES_ROOT`** / **`FLOW_DUMP_SUBDIRS`**) or §2.

#### 12.8 `packages/python/analytiq_data/flows/port/` + `tools/port_nodes.py`

**Implemented.** Python converter reads the JSONL dump and writes packages under `analytiq_data/flows/port/generated_nodes/<slug>/` (`node.manifest.json`, `parameter.schema.json`, optional `http.spec.json`, `node_impl.py` stubs). CLI: **`python tools/port_nodes.py [jsonl] --validate`**; **`make flow-node-port`**.

### Recommended runtime build order

Shortcut list — full **Status** table and notes are at the **end** of this document §13.

```
✓ Packaging: dump_nodes.js + analytiq_data.flows.port + port_nodes.py  (DONE — §12.7–§12.8)
✓ $content_ref resolver (analytiq_data.flows.content_ref) — §12.1; wire into loader/runtime next

1. Node manifest loader
2. http_request_v1 runtime
3. Credential storage + API + injection at execute time
Then: JSON Schema defaults (§12.6), richer parameter UI (§12.5)
```

---

## 13. Status (what we built vs what runs)

| Area | State | Where |
|------|--------|--------|
| **JSONL dump** from compiled `*.node.js` | **Done** (quality depends on build + `nodeVersions` instantiation) | [`tools/dump_nodes.js`](../tools/dump_nodes.js), `make flow-node-dump` — see §2 |
| **Full `description` for versioned nodes** (`nodeVersions` sub-constructors) | **Partial / fragile** | Silent skip when **`new SubCtor()`** fails → empty **`properties`** in JSONL until dumper improves |
| **Package generator** (manifest, parameter schema, optional `http.spec.json`, `python_class` stubs) | **Done** | [`analytiq_data/flows/port/`](../packages/python/analytiq_data/flows/port/), [`tools/port_nodes.py`](../tools/port_nodes.py), `make flow-node-port` |
| **Manifest / http spec JSON Schemas (stubs)** | **Done** | [`schemas/flow-node-manifest-v1.json`](../schemas/flow-node-manifest-v1.json), [`schemas/runtimes/http_request_v1.schema.json`](../schemas/runtimes/http_request_v1.schema.json) |
| **Unit tests for the converter** | **Done** | [`packages/python/tests/test_flow_port_converter.py`](../packages/python/tests/test_flow_port_converter.py) — `pytest packages/python/tests/test_flow_port_converter.py` |
| **`$content_ref` resolution** (schema + spec) | **Done** (library; not wired into loader/runtime yet) | [`content_ref.py`](../packages/python/analytiq_data/flows/content_ref.py), [`test_content_ref.py`](../packages/python/tests/test_content_ref.py) — §12.1 |
| **Dynamic registration from `node.manifest.json`** | **Not started** | §12.2 — `NodeType`s are still hand-registered at startup |
| **`http_request_v1` executor at runtime** | **Not started** | §12.3 — emitted `http.spec.json` is inert until an interpreter exists |
| **Org credential store + runtime injection** | **Not started** | §12.4 |
| **JSON Schema `default` merge before `execute()`** | **Not started** | §12.6 |
| **Richer frontend for ported parameter shapes** | **Partial / gaps** | §12.5, §9 |

**Partial by design:** the converter classifies from **`description` only** (no inspection of imperative `execute()` in compiled JS yet). **`http.spec.json`** emission is **best-effort** (first usable `routing.request`, limited `postReceive` handling). Large catalogue output expects **review**, not guaranteed drop-in parity.

### What to build next (recommended order)

**Packaging fidelity (alongside runtime work):**

- Harden **`tools/dump_nodes.js`**: surface **`nodeVersions`** instantiation failures (stderr summary per file/version key), optionally stub dependencies or extract descriptions without constructing full upstream classes — so SaaS nodes do not degrade to empty **`properties`**.

Then **runtime**:

1. ~~**`$content_ref` resolver**~~ — **Done** (`analytiq_data.flows.content_ref`); **wire it** into the manifest loader and **`http_request_v1`** when those land.
2. **Manifest loader** — discover packages under `flows/port/generated_nodes/` (or configurable root), validate, register **`NodeType`** instances (`python_class` import + declarative wrapper); run **`resolve_content_refs`** on loaded schema and spec JSON.
3. **`http_request_v1` runtime** — HTTP client + Jinja2 for `parameters.*` / `credentials.*`, response shaping via `response_jmespath`; emit **`FlowItem`** outputs.
4. **Credentials** — persistence + API + **`credential_slots`** wiring into the execution context.
5. **Defaults + UI** — engine applies JSON Schema defaults before execute (§12.6); then **`multiOptions`** / collection editors (§12.5) as needed.

Steps **2–3** (plus wiring **`resolve_content_refs`**) unlock a **declarative** generated node end-to-end without hand-copied Python; step **4** unlocks typical SaaS integrations.

Packaging was implemented **early** so manifests accumulate under `schemas/` validation and **`test_flow_port_converter.py`**; loader + **`http_request_v1`** (**items 2–3** above) are still required before flows can execute generated declarative nodes.
