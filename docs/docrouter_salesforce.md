# DocRouter Salesforce integration — port plan

Plan to add two Salesforce flow nodes to DocRouter’s flow engine, credentials, and editor: a **Salesforce** action node (REST + SOQL) and a **Salesforce Trigger** polling node (created/updated detection via SOQL).

**Related:** [`n8n_port_guide.md`](./n8n_port_guide.md), [`docrouter_nodes.md`](./docrouter_nodes.md), [`docrouter_credentials.md`](./docrouter_credentials.md), [`docrouter_http_request.md`](./docrouter_http_request.md), [`flows2.md`](./flows2.md).

---

## 1. Scope

### 1.1 In scope

| Node | Proposed DocRouter key | Role |
|------|------------------------|------|
| **Salesforce** | `ext.salesforce` | Action node: REST + SOQL against Salesforce objects |
| **Salesforce Trigger** | `ext.salesforce_trigger` | Polling trigger: created/updated events via SOQL time windows |

Reference material to mine during implementation (auth helpers, resource field matrices, output schemas, workflow fixtures) — not shipped as runtime dependencies.

### 1.2 Out of scope (for this plan)

- **Segment** (or similar) products’ `integrations.salesforce` flags — not a CRM integration.
- **Platform Events / Change Data Capture / Streaming API** — the reference trigger uses SOQL polling, not push subscriptions; real-time CDC is a future enhancement.
- **Marketing Cloud, Commerce Cloud, MuleSoft** — different APIs.
- **Auto-generated `http_request_v1` packages** — Salesforce integration is not a declarative HTTP routing node; see §3.

### 1.3 Parity target

Full behavioral parity with the reference Salesforce nodes for:

- All **resources** and **operations** on the action node (§2.1).
- All **triggerOn** variants on the trigger node (§2.2).
- **OAuth2** and **JWT** authentication paths.
- **Production** and **sandbox** environments.

Acceptable first-pass gaps (document and schedule): dynamic `loadOptions` dropdowns (§9), until a generic options API exists.

---

## 2. Feature inventory

### 2.1 Action node — resources

| Resource | Operations |
|----------|------------|
| Account | create, upsert, delete, get, getAll, getSummary, update, addNote |
| Attachment | create, delete, get, getAll, getSummary, update |
| Case | create, delete, get, getAll, getSummary, update, addComment |
| Contact | create, upsert, delete, get, getAll, getSummary, update, addNote, addToCampaign |
| Custom Object | create, upsert, delete, get, getAll, update |
| Document | upload |
| Flow | getAll, invoke |
| Lead | create, upsert, delete, get, getAll, getSummary, update, addNote, addToCampaign |
| Opportunity | create, upsert, delete, get, getAll, getSummary, update, addNote |
| Search | query (SOQL) |
| Task | create, delete, get, getAll, getSummary, update |
| User | get, getAll |

**Authentication (action node only):** `oAuth2` (default) or `jwt`.

**API base:** `{instance_url}/services/data/v59.0{endpoint}` (reference implementation pins REST **v59.0**).

### 2.2 Trigger node — events

Polling only. OAuth2 only (no JWT on the trigger).

| Event group | `triggerOn` values |
|-------------|-------------------|
| Account | `accountCreated`, `accountUpdated` |
| Attachment | `attachmentCreated`, `attachmentUpdated` |
| Case | `caseCreated`, `caseUpdated` |
| Contact | `contactCreated`, `contactUpdated` |
| Custom Object | `customObjectCreated`, `customObjectUpdated` (+ `customObject` parameter) |
| Lead | `leadCreated`, `leadUpdated` |
| Opportunity | `opportunityCreated`, `opportunityUpdated` |
| Task | `taskCreated`, `taskUpdated` |
| User | `userCreated`, `userUpdated` |

Implementation uses SOQL on `CreatedDate` / `LastModifiedDate`, workflow **static data** (`processedIds`, `lastTimeChecked`), and deduplication of already-emitted record IDs.

### 2.3 Credentials

| Kind | Used by |
|------|---------|
| `salesforceOAuth2Api` | Action (OAuth2), Trigger |
| `salesforceJwtApi` | Action (JWT) only |

DocRouter already has kind JSON stubs:

- [`schemas/credential-kinds/salesforceOAuth2Api.json`](../schemas/credential-kinds/salesforceOAuth2Api.json)
- [`schemas/credential-kinds/salesforceJwtApi.json`](../schemas/credential-kinds/salesforceJwtApi.json)

Both are marked **`experimental: true`** and are not yet wired for Salesforce-specific runtime behavior.

---

## 3. Why automated porting does not apply

Per [`n8n_port_guide.md`](./n8n_port_guide.md) §1–3:

| Signal | Salesforce |
|--------|------------|
| `requestDefaults` / per-field `routing` | **Absent** |
| Custom `execute()` / `poll()` | **Present** (~3k lines action + poll trigger in reference sources) |
| Classifier result | **`python_class`** only |

Running `make flow-node-dump` / `port_nodes.py` against a generic integration dump would emit empty or stub packages without behavior. The port is a **hand-written Python integration** with manifests and schemas built from the reference parameter model (manually or via a one-off extractor).

---

## 4. DocRouter prerequisites (blockers)

These platform gaps must be addressed before or alongside the trigger node.

| Prerequisite | Status ([`flows2.md`](./flows2.md)) | Impact |
|--------------|--------------------------------------|--------|
| **OAuth2 browser connect** with PKCE | Implemented (`flow-oauth` callback) | Action + trigger |
| **Persist `instance_url`** from Salesforce token response | **Not implemented** — callback stores only `oauthAccessToken` / refresh / expiry | All API calls need org-specific host |
| **Environment-specific OAuth URLs** (login vs test.salesforce.com) | Kind has `environment` enum but no computed `authUrl` / `accessTokenUrl` | Connect flow must set URLs from `environment` at initiate time |
| **JWT bearer `pre_auth`** on `salesforceJwtApi` | `pre_auth` runtime exists; kind has no `pre_auth` block | JWT path on action node |
| **Poll / schedule trigger subsystem** | **Not started** (`flows.trigger.schedule`, workflow static data, activation registry) | **Salesforce Trigger** entirely blocked without this |
| **Dynamic `loadOptions`** (custom object picker) | Not implemented | Trigger + Custom Object resource; workaround: free-text API name |
| **Credential `inject` for Salesforce** | Kinds have no `inject.headers` | Nodes call shared client instead of `flows.http_request` credential slots |

**Recommendation:** Ship the **action node** first; treat the **trigger** as Phase 4 gated on poll infrastructure.

---

## 5. Target architecture

### 5.1 Package layout

All Salesforce code lives inside the existing `analytiq_data` package — no new top-level directory is needed.

```
packages/python/analytiq_data/integrations/salesforce/
├── __init__.py
├── client.py              # Auth + HTTP + pagination + SOQL helpers
├── query.py               # get_query, get_conditions, get_default_fields
├── node_impl.py           # ExtSalesforceNode class (key, label, parameter_schema, execute)
└── resources/             # One module per resource (optional split)
    ├── account.py
    ├── lead.py
    └── ...
```

The trigger node (Phase 4) adds `trigger_node_impl.py` in the same package.

**Icon:** Add `salesforce.svg` to the frontend icon registry (same mechanism as existing `icon_key` values). No Python node directory is needed for the icon.

Register the node in [`packages/python/analytiq_data/docrouter_flows/register.py`](../packages/python/analytiq_data/docrouter_flows/register.py) (or a peer `register_salesforce.py` wired from the same place if the import footprint is large):

```python
from analytiq_data.integrations.salesforce.node_impl import ExtSalesforceNode
# from analytiq_data.integrations.salesforce.trigger_node_impl import ExtSalesforceTriggerNode  # Phase 4

def register_salesforce_nodes() -> None:
    ad.flows.register(ExtSalesforceNode())
    # ad.flows.register(ExtSalesforceTriggerNode())  # Phase 4
```

Wire from [`packages/python/app/main.py`](../packages/python/app/main.py) line 179, next to `register_builtin_nodes()` and `register_docrouter_nodes()`.

### 5.2 Node keys (proposed)

| Node | `key` | `is_trigger` | Inputs | Outputs |
|------|-------|:------------:|:------:|:-------:|
| Salesforce | `ext.salesforce` | false | 1 | 1 |
| Salesforce Trigger | `ext.salesforce_trigger` | true | 0 | 1 |

Category: **Sales**. AI-tool wiring for flow nodes is out of scope unless product adds it later.

### 5.3 Executor binding

`ExtSalesforceNode` is a plain Python class with the standard `NodeType` protocol fields (`key`, `label`, `category`, `parameter_schema`, `execute`, …) defined as class attributes — exactly like `DocRouterLlmExtractNode` in [`docrouter_flows/nodes/llm_node.py`](../packages/python/analytiq_data/docrouter_flows/nodes/llm_node.py). No manifest JSON is needed; the class is instantiated and passed directly to `ad.flows.register()`.

The `python_class` executor binding described in [`docrouter_nodes.md`](./docrouter_nodes.md) §6 is a forward-looking manifest format that is not yet implemented in the runtime. Do not author a `node.manifest.json` for Salesforce until a manifest loader exists.

Do **not** attempt `http_request_v1` for the main CRUD surface: URLs are `{instance_url}/services/data/v59.0/...`, bodies vary by resource, and upsert uses external ID paths. A thin internal use of `httpx` inside `client.py` is appropriate (same pattern as credential `pre_auth`).

### 5.4 Credential slots

**Action node** — define on the class:

```python
credential_slots = [
    {"name": "salesforceOAuth2Api", "required": False},
    {"name": "salesforceJwtApi",    "required": False},
]
```

Parameter `authentication`: `oAuth2` | `jwt` with `x-ui-show-when` to expose the correct slot in the credential authentication widget (same pattern as [`docrouter_http_request.md`](./docrouter_http_request.md) §2).

**Trigger node:** `credential_slots = [{"name": "salesforceOAuth2Api", "required": True}]`.

---

## 6. Shared client (`client.py`)

Implement (parity with reference auth/query helpers):

| Function | Responsibility |
|----------|----------------|
| `get_access_token_jwt(fields)` | RS256 JWT assertion → `POST .../services/oauth2/token` |
| `resolve_instance_and_token(org_id, cred_id, auth_mode)` | OAuth: refresh if needed, read `instance_url`; JWT: run `pre_auth` or inline token exchange |
| `salesforce_request(method, path, body, qs, *, instance_url, access_token)` | `httpx` call with SSRF checks via `validate_http_url_allowed_async` |
| `salesforce_request_all_items(property_name, ...)` | Follow `nextRecordsUrl` pagination |
| `sort_options`, `get_value`, `get_conditions`, `get_query` | SOQL / filter builders |

**OAuth instance URL:** Salesforce token responses include `instance_url`. Extend OAuth exchange (or a kind-specific post-exchange hook) to persist:

```json
"instance_url": "https://your-domain.my.salesforce.com"
```

into credential `fields` (add to `runtime_fields` on `salesforceOAuth2Api`). Inject into requests as:

`Authorization: Bearer {{ credentials.oauthAccessToken }}`  
Base URL: `{{ credentials.instance_url }}/services/data/v59.0`

**JWT `pre_auth` block** (add to `salesforceJwtApi.json`):

```json
"pre_auth": {
  "method": "POST",
  "url": "{{ 'https://test.salesforce.com' if credentials.environment == 'sandbox' else 'https://login.salesforce.com' }}/services/oauth2/token",
  "content_type": "application/x-www-form-urlencoded",
  "body": {
    "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
    "assertion": "{{ jwt_assertion }}"
  },
  "access_token_field": "oauthAccessToken",
  "expires_at_field": "oauthExpiresAt",
  "token_json_path": "access_token",
  "extra_fields_json_path": {
    "instance_url": "instance_url"
  }
}
```

If `extra_fields_json_path` is not supported today, extend `credential_runtime.maybe_run_pre_auth` once for Salesforce (narrow special-case acceptable for Phase 0).

**API version:** Make `api_version` a constant (default `v59.0`) in one module; bump in a single place when Salesforce deprecates versions.

---

## 7. Action node — implementation map

`ExtSalesforceNode.execute` structure:

1. Resolve `resource` + `operation` from parameters.
2. Dispatch to resource handler (table below).
3. Map each inbound `FlowItem` → operation (per-item execution like `flows.http_request`).
4. Return `FlowItem` list with `json` = Salesforce record(s) or query result.

| Resource module | Notes |
|-----------------|-------|
| lead | Campaign member, notes |
| contact | addToCampaign, addNote |
| account | addNote |
| opportunity | addNote |
| case | CaseComment for addComment |
| task | Large field surface (recurrence) |
| attachment | Binary upload paths |
| custom_object | Dynamic object name param |
| document | Blob upload |
| flow | Autolaunched flows |
| search | SOQL `query` operation |
| user | Read-only |

**Field mapping:** Encode resource/operation field matrices in `parameter.schema.json` with `x-ui-show-when` for `resource` + `operation` (see [`n8n_port_guide.md`](./n8n_port_guide.md) §5). Use `x-ui-widget: code` for SOQL on Search.

**Upsert:** Use `PATCH` with `externalId` query param; preserve Salesforce REST paths from the reference behavior spec.

**Binary / Document / Attachment:** Use DocRouter `FlowItem.binary` and [`docrouter_binary.md`](./docrouter_binary.md) conventions; confirm BSON size limits for large attachments.

---

## 8. Trigger node — implementation map (Phase 4)

Blocked until DocRouter has:

1. **`is_trigger` poll registration** at flow activation (cron interval from node params or global default).
2. **Workflow static data** persisted per `(flow_id, node_id)` (cursor + dedupe state).
3. **Manual test run** vs production poll (reference behavior: manual fetch returns a single sample row).

Trigger `poll` logic to implement:

- Parse `triggerOn` → resource + `Created` | `Updated`.
- Build SOQL via shared `get_query`.
- On automatic runs: filter `CreatedDate` / `LastModifiedDate` between `lastTimeChecked` and now; dedupe with `processedIds`.
- Emit one item per new/updated record.

**Manifest:** `is_trigger: true`, `min_inputs: 0`, `outputs: 1`, parameters: `triggerOn`, `customObject` (conditional).

---

## 9. Parameter schema and UI

### 9.1 Generation strategy

1. **Preferred:** One-off extractor script that outputs `parameter.schema.json` from a structured field matrix (maintained in-repo or imported once).
2. **Fallback:** Manually author `parameter.schema.json` in slices per resource.

Validate with:

```bash
python tools/port_nodes.py --validate  # manifest harness — see n8n_port_guide §10
```

### 9.2 `loadOptions` gaps

The reference UI loads custom object names and describe metadata at edit time. Until DocRouter exposes `GET /v0/orgs/{orgId}/flows/node-types/{key}/options?...`:

| Parameter | Interim UX |
|-----------|------------|
| `customObject` (trigger + custom resource) | Plain string + docs link to Salesforce object API name |
| Picklists (status, type, …) | Hard-code known enums where fixed; use string for dynamic describe fields |

**Future:** Options endpoint backed by `client.describe_sobject(name)` cached per org.

### 9.3 Expressions

DocRouter uses `=` prefix for per-item expressions ([`flows2.md`](./flows2.md)). Mark ID, SOQL, and URL parameters as expression-capable; engine resolves via `resolve_parameters`.

---

## 10. Credential hardening (Phase 0)

| Task | Detail |
|------|--------|
| **OAuth URLs from environment** | On `oauth/initiate`, if kind is `salesforceOAuth2Api`, set `authUrl` / `accessTokenUrl` from `fields.environment` (production vs sandbox) |
| **PKCE** | Default `grantType` to `pkce` when creating org credentials |
| **Store `instance_url`** | Extend `exchange_authorization_code` (or kind hook) to copy `instance_url` from token JSON into encrypted fields |
| **JWT `pre_auth`** | Add block to `salesforceJwtApi.json`; implement JWT assertion builder in Python if templates cannot sign RS256 |
| **`test_request`** | `GET {{ instance_url }}/services/data/v59.0/sobjects` with bearer token |
| **Experimental flag** | Remove `experimental: true` when E2E tests pass and UX is stable |

---

## 11. Phased rollout

| Phase | Deliverable | Depends on |
|-------|-------------|------------|
| **0** | Credentials: OAuth URLs, `instance_url`, JWT token exchange, test button | Credential runtime |
| **1** | `client.py` + unit tests (auth mock, query builder) | Phase 0 |
| **2** | Action node MVP: **Search (query)**, **Lead**, **Contact**, **Account** CRUD + getAll | Phase 1 |
| **3** | Action node full parity: remaining resources (Case, Task, Opportunity, Attachment, Document, Flow, Custom Object, User) | Phase 2 |
| **4** | Trigger node + poll scheduler + static data | Platform poll support |
| **5** | `loadOptions` API + schema polish | Optional |
| **6** | Promote kinds out of experimental; document in product docs | Phases 2–4 |

Each phase should land with:

- Python tests under `packages/python/tests/integrations/salesforce/`.
- At least one flow E2E in `packages/python/tests/test_flows_e2e.py` or a dedicated file with mocked HTTP.
- Sanitized JSON fixtures under `tests/fixtures/salesforce/` (no live API in CI).

---

## 12. Testing strategy

| Layer | Approach |
|-------|----------|
| Query builder | pytest unit tests for SOQL/filter construction |
| Resource handlers | `respx` / `httpx.MockTransport` against expected REST paths; fixtures per resource/operation |
| Credentials | Sandbox Connected App for manual QA; CI uses recorded mocks only |
| Trigger dedupe | Tests for static-data cursor + `processedIds` once poll runner exists |

**Do not** call live Salesforce in CI.

---

## 13. Security and operations

- All outbound URLs must pass **`validate_http_url_allowed_async`** (instance URLs are user-specific but must still be HTTPS and not RFC1918/metadata targets where policy forbids).
- Encrypt `privateKey` (JWT) and tokens at rest (existing credential encryption).
- Log with f-strings; redact tokens (follow existing flow node logging).
- Document required Salesforce Connected App scopes: OAuth uses `full refresh_token`; JWT needs authorized user + certificate upload.

---

## 14. Acceptance criteria

- [ ] Org can create `salesforceOAuth2Api` / `salesforceJwtApi` credentials (production + sandbox).
- [ ] Action node `ext.salesforce` registered and visible in flow editor (when experimental enabled or flag removed).
- [ ] Every resource/operation in §2.1 works against a sandbox with expected Salesforce REST semantics (shape may differ only where DocRouter normalizes `FlowItem`).
- [ ] Search → SOQL → paginated results matches reference `getAll` pagination behavior.
- [ ] Trigger node fires on create/update with no duplicate IDs across poll cycles (Phase 4).
- [ ] No secrets in logs; credential test_request succeeds.

---

## 15. References

| Topic | Location |
|-------|----------|
| DocRouter credential kinds | [`schemas/credential-kinds/salesforceOAuth2Api.json`](../schemas/credential-kinds/salesforceOAuth2Api.json), [`salesforceJwtApi.json`](../schemas/credential-kinds/salesforceJwtApi.json) |
| Node manifest format | [`docrouter_nodes.md`](./docrouter_nodes.md) |
| Credentials runtime | [`docrouter_credentials.md`](./docrouter_credentials.md) |
| Flow engine | [`flows2.md`](./flows2.md) |
| Salesforce REST | [REST API Developer Guide](https://developer.salesforce.com/docs/atlas.en-us.api_rest.meta/api_rest/) |
| OAuth JWT flow | [OAuth 2.0 JWT Bearer Flow](https://help.salesforce.com/s/articleView?id=sf.remoteaccess_oauth_jwt_flow.htm) |

---

## 16. Effort estimate (rough)

| Area | Size | Notes |
|------|------|-------|
| Phase 0 credentials | S | Mostly schema + small runtime hooks |
| `client.py` | S | Auth, query, pagination |
| Action node handlers | **L** | ~12 resources, many field combinations |
| Parameter schemas | M | Large JSON Schema + `x-ui-show-when` |
| Trigger + platform poll | **L** | Dominated by poll infrastructure, not SOQL |
| Tests | M | Fixtures authored in-repo |

**Total:** large integration; action-only MVP is a medium project; full parity + trigger is a large project.
