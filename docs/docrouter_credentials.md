# DocRouter Credentials — Implementation Plan

This document covers how to build the credential system in DocRouter from scratch — kind definitions, org-scoped storage, API, runtime injection, and frontend UI. It is self-contained: it does not depend on n8n credential import tooling (see §7 of [`n8n_port_guide.md`](./n8n_port_guide.md) for that).

---

## 1. Architecture

Three concepts, mirroring the n8n model:

| Concept | Where | Purpose |
|---|---|---|
| **Credential kind** | `schemas/credential-kinds/<key>.json` — loaded at startup | Global type definition: auth mode, fields the org fills in, injection rule |
| **Org credential** | `org_credentials` MongoDB collection | One saved instance per org: kind reference + encrypted field values |
| **Node binding** | `flow_revisions.nodes[*].credentials` field | Maps a node's slot name → a saved org credential id |

Runtime flow: before executing a node, the engine resolves its bindings → decrypts the referenced credential → builds a flat `credentials.*` dict → passes it into the node's execution context for Jinja2 substitution in `http.spec.json`.

---

## 2. Credential kind file format

Kind definitions live in `schemas/credential-kinds/<key>.json`. These are hand-authored for the initial set and later auto-generated from the n8n dump (see `n8n_port_guide.md §7.5`).

**Fields:**

| Field | Type | Required | Purpose |
|---|---|---|---|
| `key` | string | yes | Stable identifier; must match the filename stem and equals n8n's credential `name` where applicable |
| `display_name` | string | yes | Human-readable label shown in the UI |
| `auth_mode` | enum | yes | `"api_key"`, `"oauth2_authorization_code"`, `"oauth2_client_credentials"`, `"basic_auth"`, `"custom"` |
| `extends` | string | no | Key of a base kind; inherits `secret_schema`, `inject`, and `oauth2` config |
| `secret_schema` | JSON Schema object | yes (unless `extends` covers it) | JSON Schema for the fields the org fills in; `"x-secret": true` marks fields that must never appear in API responses |
| `oauth2` | object | oauth2 modes only | `auth_url`, `token_url`, `auth_query_params`, `token_endpoint_auth_method`, `default_scopes` |
| `runtime_fields` | object | oauth2 modes | Fields written by DocRouter at token-exchange time (e.g. `access_token`, `refresh_token`); not in `secret_schema` because the user does not fill them in |
| `inject` | object | no | Describes how to attach decrypted fields to HTTP requests: `inject.headers`, `inject.query_params`. Values are Jinja2 templates using `{{ credentials.<field> }}` |
| `test_request` | object | no | `{ "method": "GET", "url": "…" }` — called by the `/test` endpoint to verify a credential |

**Example — Slack API (API key):**

```json
{
  "key": "slackApi",
  "display_name": "Slack API",
  "auth_mode": "api_key",
  "secret_schema": {
    "type": "object",
    "additionalProperties": false,
    "required": ["accessToken"],
    "properties": {
      "accessToken": {
        "type": "string",
        "title": "Access Token",
        "x-secret": true,
        "description": "Slack Bot or User OAuth token (starts with xoxb- or xoxp-)"
      }
    }
  },
  "inject": {
    "headers": {
      "Authorization": "Bearer {{ credentials.accessToken }}"
    }
  },
  "test_request": {
    "method": "GET",
    "url": "https://slack.com/api/auth.test"
  }
}
```

**Example — OpenAI API (API key):**

```json
{
  "key": "openAiApi",
  "display_name": "OpenAI API",
  "auth_mode": "api_key",
  "secret_schema": {
    "type": "object",
    "additionalProperties": false,
    "required": ["apiKey"],
    "properties": {
      "apiKey": {
        "type": "string",
        "title": "API Key",
        "x-secret": true,
        "description": "OpenAI API key (sk-…)"
      },
      "organizationId": {
        "type": "string",
        "title": "Organization ID",
        "description": "Optional: leave blank to use your default org"
      }
    }
  },
  "inject": {
    "headers": {
      "Authorization": "Bearer {{ credentials.apiKey }}",
      "OpenAI-Organization": "{{ credentials.organizationId }}"
    }
  },
  "test_request": {
    "method": "GET",
    "url": "https://api.openai.com/v1/models"
  }
}
```

**Example — Google OAuth2 base kind (OAuth2, authorization code):**

See §7.4 of `n8n_port_guide.md` for the full Google kind chain. The base `oAuth2Api` kind:

```json
{
  "key": "oAuth2Api",
  "display_name": "OAuth2 API",
  "auth_mode": "oauth2_authorization_code",
  "secret_schema": {
    "type": "object",
    "additionalProperties": false,
    "required": ["clientId", "clientSecret"],
    "properties": {
      "clientId":     { "type": "string", "title": "Client ID" },
      "clientSecret": { "type": "string", "title": "Client Secret", "x-secret": true },
      "scope":        { "type": "string", "title": "Scope", "default": "" }
    }
  },
  "runtime_fields": {
    "access_token":  { "x-secret": true },
    "refresh_token": { "x-secret": true }
  },
  "inject": {
    "headers": {
      "Authorization": "Bearer {{ credentials.access_token }}"
    }
  }
}
```

The Google-specific extension hard-codes the OAuth endpoints:

```json
{
  "key": "googleOAuth2Api",
  "display_name": "Google OAuth2 API",
  "extends": "oAuth2Api",
  "oauth2": {
    "auth_url": "https://accounts.google.com/o/oauth2/v2/auth",
    "token_url": "https://oauth2.googleapis.com/token",
    "auth_query_params": "access_type=offline&prompt=consent",
    "token_endpoint_auth_method": "client_secret_post"
  }
}
```

---

## 3. Python kind registry

**File:** `packages/python/analytiq_data/flows/credential_kind_registry.py`

Loaded once at startup from `schemas/credential-kinds/`. Resolves `extends` chains so callers always get a fully-merged kind.

```python
from __future__ import annotations

import json
import os
from typing import Any

_registry: dict[str, dict[str, Any]] = {}


def load_credential_kinds(kinds_dir: str) -> None:
    """Read all *.json files from kinds_dir into the in-memory registry."""
    global _registry
    _registry = {}
    for fname in os.listdir(kinds_dir):
        if not fname.endswith(".json"):
            continue
        with open(os.path.join(kinds_dir, fname)) as f:
            kind = json.load(f)
        key = kind["key"]
        _registry[key] = kind


def _resolve(key: str, seen: set[str] | None = None) -> dict[str, Any]:
    """Return a fully-merged kind dict (base fields overridden by extension)."""
    seen = seen or set()
    if key in seen:
        raise ValueError(f"Circular extends chain: {key}")
    seen.add(key)

    kind = dict(_registry[key])
    base_key = kind.get("extends")
    if not base_key:
        return kind

    base = _resolve(base_key, seen)

    # Merge secret_schema properties (extension adds to or overrides base)
    merged_schema = dict(base.get("secret_schema") or {})
    ext_schema = kind.get("secret_schema") or {}
    if ext_schema.get("properties"):
        merged_props = dict((merged_schema.get("properties") or {}))
        merged_props.update(ext_schema["properties"])
        merged_schema["properties"] = merged_props
    kind["secret_schema"] = merged_schema

    # Merge runtime_fields
    merged_rf = dict(base.get("runtime_fields") or {})
    merged_rf.update(kind.get("runtime_fields") or {})
    kind["runtime_fields"] = merged_rf

    # Merge inject (extension overrides base per-key)
    merged_inject = dict(base.get("inject") or {})
    for section, vals in (kind.get("inject") or {}).items():
        merged_inject[section] = {**(merged_inject.get(section) or {}), **vals}
    kind["inject"] = merged_inject

    # Merge oauth2 config
    merged_oauth2 = {**(base.get("oauth2") or {}), **(kind.get("oauth2") or {})}
    if merged_oauth2:
        kind["oauth2"] = merged_oauth2

    # auth_mode defaults to base if not set in extension
    if "auth_mode" not in kind:
        kind["auth_mode"] = base.get("auth_mode", "custom")

    return kind


def get_kind(key: str) -> dict[str, Any]:
    if key not in _registry:
        raise KeyError(f"Unknown credential kind: {key}")
    return _resolve(key)


def list_kinds() -> list[dict[str, Any]]:
    return [_resolve(k) for k in sorted(_registry)]


def secret_field_names(kind: dict[str, Any]) -> set[str]:
    """Return field names marked x-secret in the kind's merged schema + runtime_fields."""
    props = (kind.get("secret_schema") or {}).get("properties") or {}
    secret = {k for k, v in props.items() if v.get("x-secret")}
    secret |= set(kind.get("runtime_fields") or {})
    return secret
```

Call `load_credential_kinds` during app startup in `packages/python/app/main.py` after the existing startup block:

```python
import analytiq_data as ad

# Near the top of lifespan() or startup handler:
kinds_dir = os.path.join(os.path.dirname(__file__), "../../../schemas/credential-kinds")
if os.path.isdir(kinds_dir):
    ad.flows.credential_kind_registry.load_credential_kinds(kinds_dir)
```

Expose through the `analytiq_data.flows` namespace by adding to `packages/python/analytiq_data/flows/__init__.py`:

```python
from . import credential_kind_registry
```

---

## 4. `org_credentials` MongoDB collection

One document per saved credential instance:

```python
{
    "_id":             ObjectId,          # credential id
    "organization_id": str,               # org scope
    "kind_key":        str,               # e.g. "slackApi"
    "name":            str,               # user-chosen label, e.g. "Slack – Marketing bot"
    "encrypted_payload": str,             # AES-encrypted JSON blob of all field values
                                          # (both secret and non-secret fields together)
    "created_at":      datetime,
    "created_by":      str,               # user_id
    "updated_at":      datetime,
    "updated_by":      str,
}
```

`encrypted_payload` is `ad.crypto.encrypt_token(json.dumps(fields_dict))`. Decryption returns the full dict; secret fields are stripped before any API response.

**Index:** compound `{ organization_id: 1, kind_key: 1 }` for efficient filtering by org + kind when looking up bindings.

> **Encryption note:** `ad.crypto.encrypt_token` currently uses a fixed IV derived from the secret key, meaning identical plaintext always produces identical ciphertext. For credentials this is acceptable at launch (the payload is a JSON dict whose field ordering varies), but a random-IV variant should be added before storing high-value secrets like OAuth client secrets. Track this as a follow-up.

---

## 5. Backend API

**File:** `packages/python/app/routes/flows_credentials.py`

Credentials are a sub-concern of flows, so the router lives next to `flows.py` and its routes are all prefixed under `/flows/`. Register in `packages/python/app/main.py`:

```python
from app.routes.flows_credentials import flow_credentials_router
app.include_router(flow_credentials_router)
```

### 5.1 Pydantic models

```python
from __future__ import annotations

import json
import logging
from datetime import datetime, UTC
from typing import Any

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

import analytiq_data as ad
from app.auth import get_org_user
from app.models import User

logger = logging.getLogger(__name__)
flow_credentials_router = APIRouter(tags=["flows"])


# ── Request / response models ──────────────────────────────────────────────

class CredentialKindSummary(BaseModel):
    key: str
    display_name: str
    auth_mode: str
    # non-secret property names and their schema (for building the create form)
    fields: list[dict[str, Any]]


class CreateCredentialRequest(BaseModel):
    kind_key: str
    name: str
    fields: dict[str, Any]   # all fields (secret + non-secret); encrypted server-side


class CredentialHeader(BaseModel):
    credential_id: str
    organization_id: str
    kind_key: str
    name: str
    # non-secret field values only (secret fields omitted)
    public_fields: dict[str, Any]
    created_at: datetime
    created_by: str
    updated_at: datetime
    updated_by: str


class ListCredentialsResponse(BaseModel):
    items: list[CredentialHeader]
    total: int


class TestCredentialResponse(BaseModel):
    ok: bool
    status_code: int | None = None
    error: str | None = None
```

### 5.2 Helper: serialize a MongoDB document to `CredentialHeader`

```python
def _to_header(doc: dict, kind: dict) -> CredentialHeader:
    secret_names = ad.flows.credential_kind_registry.secret_field_names(kind)
    try:
        all_fields = json.loads(ad.crypto.decrypt_token(doc["encrypted_payload"]))
    except Exception:
        all_fields = {}
    public_fields = {k: v for k, v in all_fields.items() if k not in secret_names}
    return CredentialHeader(
        credential_id=str(doc["_id"]),
        organization_id=doc["organization_id"],
        kind_key=doc["kind_key"],
        name=doc["name"],
        public_fields=public_fields,
        created_at=doc["created_at"].replace(tzinfo=UTC),
        created_by=doc["created_by"],
        updated_at=doc["updated_at"].replace(tzinfo=UTC),
        updated_by=doc["updated_by"],
    )
```

### 5.3 Routes

**List available kinds** — used to populate the "create credential" kind picker:

```python
@flow_credentials_router.get("/v0/orgs/{organization_id}/flows/credential-kinds")
async def list_credential_kinds(
    organization_id: str,
    current_user: User = Depends(get_org_user),
) -> list[CredentialKindSummary]:
    result = []
    for kind in ad.flows.credential_kind_registry.list_kinds():
        schema_props = (kind.get("secret_schema") or {}).get("properties") or {}
        secret_names = ad.flows.credential_kind_registry.secret_field_names(kind)
        fields = [
            {"name": k, **{fk: fv for fk, fv in v.items() if fk != "x-secret"},
             "is_secret": k in secret_names}
            for k, v in schema_props.items()
        ]
        result.append(CredentialKindSummary(
            key=kind["key"],
            display_name=kind["display_name"],
            auth_mode=kind["auth_mode"],
            fields=fields,
        ))
    return result
```

**Create a credential instance:**

```python
@flow_credentials_router.post("/v0/orgs/{organization_id}/flows/credentials",
                         response_model=CredentialHeader)
async def create_credential(
    organization_id: str,
    req: CreateCredentialRequest,
    current_user: User = Depends(get_org_user),
) -> CredentialHeader:
    try:
        kind = ad.flows.credential_kind_registry.get_kind(req.kind_key)
    except KeyError:
        raise HTTPException(status_code=400, detail=f"Unknown credential kind: {req.kind_key}")

    # Validate req.fields against kind's secret_schema
    schema = kind.get("secret_schema")
    if schema:
        from jsonschema import Draft7Validator, ValidationError
        try:
            Draft7Validator(schema).validate(req.fields)
        except ValidationError as e:
            raise HTTPException(status_code=422, detail=e.message)

    encrypted = ad.crypto.encrypt_token(json.dumps(req.fields))
    now = datetime.now(UTC)
    db = await ad.common.get_async_db()
    res = await db.org_credentials.insert_one({
        "organization_id": organization_id,
        "kind_key": req.kind_key,
        "name": req.name,
        "encrypted_payload": encrypted,
        "created_at": now,
        "created_by": current_user.user_id,
        "updated_at": now,
        "updated_by": current_user.user_id,
    })
    doc = await db.org_credentials.find_one({"_id": res.inserted_id})
    return _to_header(doc, kind)
```

**List credentials for an org** (metadata only, no secrets):

```python
@flow_credentials_router.get("/v0/orgs/{organization_id}/flows/credentials",
                        response_model=ListCredentialsResponse)
async def list_credentials(
    organization_id: str,
    current_user: User = Depends(get_org_user),
) -> ListCredentialsResponse:
    db = await ad.common.get_async_db()
    total = await db.org_credentials.count_documents({"organization_id": organization_id})
    docs = await db.org_credentials.find(
        {"organization_id": organization_id}
    ).sort("updated_at", -1).to_list(1000)
    items = []
    for doc in docs:
        try:
            kind = ad.flows.credential_kind_registry.get_kind(doc["kind_key"])
        except KeyError:
            kind = {"secret_schema": {}, "runtime_fields": {}}
        items.append(_to_header(doc, kind))
    return ListCredentialsResponse(items=items, total=total)
```

**Get a single credential** (metadata only):

```python
@flow_credentials_router.get("/v0/orgs/{organization_id}/flows/credentials/{credential_id}",
                        response_model=CredentialHeader)
async def get_credential(
    organization_id: str,
    credential_id: str,
    current_user: User = Depends(get_org_user),
) -> CredentialHeader:
    db = await ad.common.get_async_db()
    doc = await db.org_credentials.find_one(
        {"_id": ObjectId(credential_id), "organization_id": organization_id}
    )
    if not doc:
        raise HTTPException(status_code=404, detail="Credential not found")
    kind = ad.flows.credential_kind_registry.get_kind(doc["kind_key"])
    return _to_header(doc, kind)
```

**Update credential fields** (re-encrypt; useful when a token rotates):

```python
@flow_credentials_router.put("/v0/orgs/{organization_id}/flows/credentials/{credential_id}",
                        response_model=CredentialHeader)
async def update_credential(
    organization_id: str,
    credential_id: str,
    req: CreateCredentialRequest,
    current_user: User = Depends(get_org_user),
) -> CredentialHeader:
    db = await ad.common.get_async_db()
    doc = await db.org_credentials.find_one(
        {"_id": ObjectId(credential_id), "organization_id": organization_id}
    )
    if not doc:
        raise HTTPException(status_code=404, detail="Credential not found")
    try:
        kind = ad.flows.credential_kind_registry.get_kind(req.kind_key)
    except KeyError:
        raise HTTPException(status_code=400, detail=f"Unknown credential kind: {req.kind_key}")
    encrypted = ad.crypto.encrypt_token(json.dumps(req.fields))
    now = datetime.now(UTC)
    await db.org_credentials.update_one(
        {"_id": ObjectId(credential_id)},
        {"$set": {"encrypted_payload": encrypted, "name": req.name,
                  "updated_at": now, "updated_by": current_user.user_id}},
    )
    doc = await db.org_credentials.find_one({"_id": ObjectId(credential_id)})
    return _to_header(doc, kind)
```

**Delete a credential:**

```python
@flow_credentials_router.delete("/v0/orgs/{organization_id}/flows/credentials/{credential_id}",
                           status_code=204)
async def delete_credential(
    organization_id: str,
    credential_id: str,
    current_user: User = Depends(get_org_user),
) -> None:
    db = await ad.common.get_async_db()
    res = await db.org_credentials.delete_one(
        {"_id": ObjectId(credential_id), "organization_id": organization_id}
    )
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Credential not found")
```

**Test a credential** (for `api_key` kinds with a `test_request`):

```python
@flow_credentials_router.post("/v0/orgs/{organization_id}/flows/credentials/{credential_id}/test",
                         response_model=TestCredentialResponse)
async def test_credential(
    organization_id: str,
    credential_id: str,
    current_user: User = Depends(get_org_user),
) -> TestCredentialResponse:
    import httpx
    from jinja2 import Environment, Undefined

    db = await ad.common.get_async_db()
    doc = await db.org_credentials.find_one(
        {"_id": ObjectId(credential_id), "organization_id": organization_id}
    )
    if not doc:
        raise HTTPException(status_code=404, detail="Credential not found")
    kind = ad.flows.credential_kind_registry.get_kind(doc["kind_key"])
    test_req = kind.get("test_request")
    if not test_req:
        return TestCredentialResponse(ok=True, error="No test_request defined for this kind")

    fields = json.loads(ad.crypto.decrypt_token(doc["encrypted_payload"]))
    inject = kind.get("inject") or {}
    jinja_env = Environment(undefined=Undefined)
    headers = {
        k: jinja_env.from_string(v).render(credentials=fields)
        for k, v in (inject.get("headers") or {}).items()
    }
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.request(
                method=test_req.get("method", "GET"),
                url=test_req["url"],
                headers=headers,
            )
        ok = resp.status_code < 400
        return TestCredentialResponse(ok=ok, status_code=resp.status_code,
                                      error=None if ok else resp.text[:200])
    except Exception as e:
        return TestCredentialResponse(ok=False, error=str(e))
```

---

## 6. Flow node credential bindings

### 6.1 Node document structure

Nodes are stored in `flow_revisions.nodes` as plain dicts. Extend each node dict with an optional `credentials` map:

```json
{
  "id": "node-abc",
  "type": "ext.slack_post_message",
  "name": "Post to Slack",
  "parameters": { "channel": "#general", "text": "Hello" },
  "credentials": {
    "slackApi": "64f3a1b2c3d4e5f6a7b8c9d0"
  }
}
```

Key = slot name from the node type's `credential_slots`; value = `org_credentials._id` as a string.

No schema changes are required: `nodes` is already stored as `list[dict[str, Any]]`. The bindings are validated at execution time, not at save time.

### 6.2 Validation at execution time

Before calling `node_type.execute()`, check that all required slots are bound:

```python
def validate_credential_bindings(
    node: dict,
    node_type,
    bound_ids: dict[str, str],      # slot → cred_id (from node["credentials"])
) -> list[str]:
    """Return a list of error strings; empty means ok."""
    errors = []
    for slot in (node_type.credential_slots or []):
        if slot["required"] and slot["slot"] not in bound_ids:
            errors.append(f"Node '{node.get('name')}': required credential slot '{slot['slot']}' is not bound")
    return errors
```

Add `credential_slots: list[dict] = []` to the `NodeType` protocol (duck-typed attribute on each node class). Generated nodes already have this in their manifests; built-in nodes default to `[]`.

### 6.3 API: update bindings without a full save

Add a lightweight PATCH endpoint for credential bindings so the flow editor can update them without creating a new revision:

```
PATCH /v0/orgs/{org_id}/flows/{flow_id}/revisions/{revid}/nodes/{node_id}/credentials
Body: { "credentials": { "slackApi": "64f3a1b2c3d4e5f6a7b8c9d0" } }
```

This writes `credentials` into the node dict inside the stored revision. Alternatively, bindings can be sent as part of the existing `PUT /v0/orgs/{org_id}/flows/{flow_id}` save payload (simpler: just include `credentials` in each node dict).

The simpler approach — include `credentials` in every `SaveFlowRequest.nodes` entry — is preferred. No extra endpoint needed.

---

## 7. Runtime credential injection

### 7.1 Resolver utility

**File:** `packages/python/analytiq_data/flows/credentials.py`

```python
from __future__ import annotations

import json
import logging
from typing import Any

import analytiq_data as ad

logger = logging.getLogger(__name__)


async def resolve_node_credentials(
    organization_id: str,
    node: dict[str, Any],
    node_type,
) -> dict[str, Any]:
    """
    Return a flat dict of decrypted credential fields for a node.

    Keys are field names from the credential kind's secret_schema and runtime_fields.
    Returns {} if the node has no credential_slots or no bindings.
    """
    credential_slots = getattr(node_type, "credential_slots", [])
    bindings: dict[str, str] = node.get("credentials") or {}
    if not credential_slots or not bindings:
        return {}

    db = await ad.common.get_async_db()
    merged: dict[str, Any] = {}

    for slot_def in credential_slots:
        slot = slot_def["slot"]
        cred_id = bindings.get(slot)
        if not cred_id:
            continue

        from bson import ObjectId
        doc = await db.org_credentials.find_one(
            {"_id": ObjectId(cred_id), "organization_id": organization_id}
        )
        if not doc:
            logger.warning("Credential %s not found for slot %s", cred_id, slot)
            continue

        try:
            fields = json.loads(ad.crypto.decrypt_token(doc["encrypted_payload"]))
        except Exception as e:
            logger.error("Failed to decrypt credential %s: %s", cred_id, e)
            continue

        # Merge all fields; later slots overwrite earlier ones on collision
        merged.update(fields)

    return merged
```

### 7.2 Wiring into the execution engine

`ExecutionContext` currently carries `organization_id` and `analytiq_client` but no credential resolver. Add a `credentials_resolver` field:

```python
# packages/python/analytiq_data/flows/context.py

from typing import Any, Callable, Coroutine, Literal

@dataclass
class ExecutionContext:
    organization_id: str
    execution_id: str
    flow_id: str
    flow_revid: str
    mode: ExecutionMode
    trigger_data: dict[str, Any]
    run_data: dict[str, Any]
    analytiq_client: Any
    stop_requested: bool = False
    logger: Any | None = None
    # New: callable that resolves credentials for a given node
    credentials_resolver: Callable[..., Coroutine] | None = None
```

In `packages/python/analytiq_data/flows/engine.py`, before calling `node_type.execute()`, resolve credentials:

```python
# Inside the node execution loop (wherever execute() is called today):
credentials: dict[str, Any] = {}
if context.credentials_resolver:
    credentials = await context.credentials_resolver(
        organization_id=context.organization_id,
        node=node,
        node_type=node_type,
    )
# Pass credentials into execute() via a keyword arg, OR store on context per-node
```

The cleanest approach: pass `credentials` as an extra keyword arg to `execute()` so nodes can use it directly. Since the `NodeType` protocol is duck-typed, existing built-in nodes just ignore the kwarg if they don't declare it. Add `**_` to existing `execute()` signatures to absorb it silently, or use `inspect` to detect whether the node accepts a `credentials` param.

Alternatively, add `credentials: dict[str, Any]` to the `ExecutionContext` dataclass and set it before each node execution:

```python
context.credentials = credentials   # set per-node before execute()
```

This is simpler and avoids touching all existing node signatures.

### 7.3 Usage in `http_request_v1` executor

When the `http_request_v1` runtime is built (see `n8n_port_guide.md §12.3`), it will read `context.credentials` and use Jinja2 to substitute `{{ credentials.<field> }}` into the spec:

```python
from jinja2 import Environment, StrictUndefined

env = Environment(undefined=StrictUndefined)
url = env.from_string(spec["url"]).render(
    parameters=node_parameters,
    credentials=context.credentials,
)
headers = {
    k: env.from_string(v).render(parameters=node_parameters, credentials=context.credentials)
    for k, v in (spec.get("headers") or {}).items()
}
```

---

## 8. Frontend

### 8.1 Credentials settings page

**Route:** `/settings/organizations/[organizationId]/flows/credentials/`

Credentials are a flows-specific configuration, so the page lives under a `flows/` segment in the org settings — alongside the existing `webhooks/` page which also relates to flows triggers.

**Files to create:**

```
packages/typescript/frontend/src/app/settings/organizations/[organizationId]/flows/credentials/
├── page.tsx          ← list view (table of saved credentials)
└── new/
    └── page.tsx      ← create form (kind picker + dynamic field form)
```

**List page (`page.tsx`):**

- Fetch `GET /v0/orgs/{orgId}/flows/credential-kinds` to populate the "Add credential" kind picker.
- Fetch `GET /v0/orgs/{orgId}/flows/credentials` to list saved instances.
- Table columns: **Name**, **Kind** (display_name), **Created**, **Actions**.
- Actions: **Test** (POST …/test, show ok/error snackbar), **Edit** (navigate to edit form or open inline), **Delete** (confirmation dialog, then DELETE).
- "Add credential" button opens a kind-picker dialog.

**Create form:**

1. Step 1 — Kind picker: dropdown listing all kinds from `GET …/flows/credential-kinds` grouped by `auth_mode`. On select, show the kind's description and field list.
2. Step 2 — Fill fields: render a dynamic form from the kind's `fields` array returned by the API:
   - `is_secret: true` fields → MUI `TextField` with `type="password"` and show/hide toggle.
   - `is_secret: false` fields → plain `TextField`.
   - `description` on a field → `helperText`.
   - Name field (free text) at the top, always present.
3. Submit → `POST /v0/orgs/{orgId}/flows/credentials` → redirect back to list with success snackbar.

**API client additions** (in `packages/typescript/frontend/src/utils/api.ts` or the SDK):

```typescript
// List credential kinds (for the create form)
// GET /v0/orgs/{orgId}/flows/credential-kinds
async function listFlowCredentialKinds(orgId: string): Promise<CredentialKindSummary[]>

// CRUD  — all under /v0/orgs/{orgId}/flows/credentials
async function listFlowCredentials(orgId: string): Promise<ListCredentialsResponse>
async function createFlowCredential(orgId: string, req: CreateCredentialRequest): Promise<CredentialHeader>
async function updateFlowCredential(orgId: string, credId: string, req: CreateCredentialRequest): Promise<CredentialHeader>
async function deleteFlowCredential(orgId: string, credId: string): Promise<void>
async function testFlowCredential(orgId: string, credId: string): Promise<TestCredentialResponse>
```

**Navigation:** add a "Flows" section to the organization settings sidebar (if not already present) and put "Credentials" under it, alongside "Webhooks" (which also belongs to flows).

### 8.2 Flow editor: credential slot binding

In the node configuration panel (the side panel that opens when a node is selected in the React Flow canvas), add a **Credentials** section below the node parameters form.

The section appears only when the selected node type has one or more `credential_slots`.

**Per slot:**

- Label from `slot_def.label`.
- MUI `Select` dropdown:
  - Options: org credentials where `kind_key` matches the slot's `docrouter_binding` (strip the `organization_credential_kind:` prefix to get the kind key).
  - Fetch `GET /v0/orgs/{orgId}/flows/credentials` once and filter client-side by kind key.
  - Option labels: `credential.name` (kind display name shown as subtitle).
  - Placeholder: "Select credential…" for optional slots; "Required — select credential" for required ones.
- "Manage credentials" link → opens `/settings/organizations/{orgId}/flows/credentials/` in a new tab.

**Saving bindings:** include the `credentials` map in the node's data when `PUT /v0/orgs/{orgId}/flows/{flowId}` is called (it is already included in the `nodes` array). No separate API call needed.

**Node type metadata:** the flow editor needs access to each node type's `credential_slots`. The existing `GET /v0/orgs/{orgId}/flows/node-types` endpoint returns node type metadata; extend its response to include `credential_slots` from the node type object.

---

## 9. Starter hand-authored kind files

Check in these files first so the credential UI works end-to-end before any n8n import tooling exists.

**File list:**

```
schemas/credential-kinds/
├── slackApi.json           (see §2 example above)
├── openAiApi.json          (see §2 example above)
├── oAuth2Api.json          (base OAuth2 — see §2 and n8n_port_guide §7.4)
├── googleOAuth2Api.json    (extends oAuth2Api — see n8n_port_guide §7.4)
```

Add more kinds by hand as integrations are prioritized, or auto-generate them via `tools/dump_credentials.js` + `tools/port_credentials.py` (n8n_port_guide §7.5, Phase B/C).

---

## 10. OAuth2 credential flow (deferred)

OAuth2 kinds (`auth_mode: "oauth2_authorization_code"`) require a browser redirect to the provider's consent screen and a server-side callback to exchange the code for tokens. This is different from API-key kinds, which are fully self-contained.

Defer this until the API-key flow is working end-to-end. What is needed:

| Step | What to build |
|---|---|
| **Initiate** | `POST /v0/orgs/{orgId}/flows/credentials/{credId}/oauth/initiate` — build the auth URL from `kind.oauth2.auth_url`, redirect the user's browser there with `state=<signed JWT encoding orgId+credId>` |
| **Callback** | `GET /v0/callback/oauth` — validate `state`, POST to `kind.oauth2.token_url` with the code, store `access_token` + `refresh_token` into `encrypted_payload` alongside existing fields |
| **Refresh** | Before each execution: check `exp` claim on `access_token`; if expired, POST to `token_url` with `refresh_token`, update `encrypted_payload`, continue |
| **Frontend** | "Connect" button in the create form for OAuth2 kinds instead of a text field; polls for completion after redirect |

Until this is built:
- OAuth2 credential instances can be created by manually supplying an `access_token` as a string field (treating it like an API key for testing purposes).
- Mark OAuth2 kinds with `"status": "manual_token_only"` in the kind file so the UI can show a warning.

---

## 11. Build order

Work in this order. Each step is independently testable.

**Phase 1 — Kind registry + stub API (backend only)**

1. Write the starter kind JSON files: `slackApi.json`, `openAiApi.json`.
2. Implement `packages/python/analytiq_data/flows/credential_kind_registry.py` (§3).
3. Call `load_credential_kinds` in `main.py` startup.
4. Create `packages/python/app/routes/flows_credentials.py` with:
   - `GET /v0/orgs/{orgId}/flows/credential-kinds`
   - `POST /v0/orgs/{orgId}/flows/credentials`
   - `GET /v0/orgs/{orgId}/flows/credentials`
   - `DELETE /v0/orgs/{orgId}/flows/credentials/{credId}`
5. Create the MongoDB index on `org_credentials`.
6. Verify with `curl` or the FastAPI `/docs` UI.

**Phase 2 — Test endpoint**

7. Add `POST /v0/orgs/{orgId}/flows/credentials/{credId}/test` (§5.3).
8. Test manually with a real Slack token.

**Phase 3 — Runtime injection**

9. Add `credentials_resolver` field to `ExecutionContext` (§7.2).
10. Implement `packages/python/analytiq_data/flows/credentials.py` (§7.1).
11. Wire the resolver into the engine's node execution loop (§7.2).
12. Add `context.credentials` so it is available to the `http_request_v1` executor when it is built.

**Phase 4 — Flow bindings**

13. Extend `GET /v0/orgs/{orgId}/flows/node-types` to include `credential_slots` per type.
14. Include `credentials` in `SaveFlowRequest.nodes` (already transparent — `nodes` is `list[dict]`).
15. Add binding validation in the execution path (§6.2).

**Phase 5 — Frontend credentials settings page**

16. Create `/settings/organizations/[organizationId]/flows/credentials/page.tsx` — list + delete.
17. Create the create form with kind picker and dynamic field form.
18. Add navigation link in the org settings sidebar.
19. Test end-to-end: create a Slack credential, list it, delete it.

**Phase 6 — Frontend flow editor binding UI**

20. Fetch `credential_slots` alongside node type metadata.
21. Render the per-slot credential picker in the node config panel.
22. Verify bindings survive a save/load round-trip.

**Phase 7 — OAuth2 (separate milestone)**

23. Implement initiate + callback endpoints (§10).
24. Add token refresh loop in the resolver (§7.1).
25. Update the frontend create form for OAuth2 kinds.
