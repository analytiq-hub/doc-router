# Simple product license (periodic check + feature gates)

Plan for an **Ed25519-signed offline license**, checked by a **background task**,
that **disables the HTTP API** when invalid or expired — while **always allowing**
system admins to view status and upload / replace the key in the UI.

When a valid license is installed, it also gates two product capabilities via
claims: **`documents`** and **`flows`**. Quantitative caps (**max users**,
**max workspaces**) are reserved in the schema for a later phase.

**Primary files (proposed):**

| Area | Path |
|------|------|
| Verifier + claims | `packages/python/analytiq_data/licensing/` (new) |
| Mongo store | `packages/python/analytiq_data/licensing/store.py` (new) |
| Periodic checker | `packages/python/analytiq_data/licensing/checker.py` (new) |
| FastAPI routes | `packages/python/app/routes/license.py` (new) |
| Expiry middleware | `packages/python/app/licensing_gate.py` (new) |
| Feature deps | `packages/python/app/licensing_deps.py` (new) — `require_feature` |
| Router / startup | `packages/python/app/main.py`, `packages/python/app/startup.py` |
| Public key | `packages/python/analytiq_data/licensing/keys/license-public.pem` |
| Issuer (internal) | `scripts/licensing/` |
| Admin UI | `packages/typescript/frontend/src/app/settings/account/license/` |
| Settings nav | `packages/typescript/frontend/src/components/SettingsLayout.tsx` |
| SDK | `packages/typescript/sdk/src/docrouter-account.ts` (+ types) |
| Frontend API | `packages/typescript/frontend/src/utils/api.ts` |
| Tests | `packages/python/tests/test_simple_license.py` |

**Related docs:**

- [On-prem installation architecture](./on_prem_installation_architecture.md)
- [Environment variables](./env.md)

**Implementation order:** Phase 1 (format + store + verify + status/PUT API) →
Phase 2 (periodic checker + expiry middleware) →
Phase 3 (`documents` / `flows` feature gates) →
Phase 4 (admin UI + banner) →
Phase 5 (docs / on-prem packaging) →
Later: max users / max workspaces limits.

---

## Problem

Self-hosted / air-gapped customers need a deployable entitlement that:

1. Works with **no outbound network**.
2. Cannot be forged by editing env vars alone (signed key).
3. Can be **uploaded and replaced** by a system admin in the UI even when the
   product is otherwise disabled by expiry.
4. Can turn **documents** and **flows** on or off per license.
5. Stays simple to operate — expiry is one global API gate; features are a small
   fixed set of route dependencies (not a large entitlement matrix).

Stripe/SPU remain the monetization path for hosted SaaS. This plan does not
replace them.

---

## Goals

1. **Ed25519-signed token** (`DRLIC1.<payload>.<signature>`) verified with a
   public key shipped in the product.
2. **Offline only** — no license server; revoke by issuing a replacement or
   shorter-lived key.
3. **Mongo singleton** stores the raw key; optional bootstrap from
   `LICENSE_KEY` / `LICENSE_FILE` when Mongo has no key.
4. **Background checker** periodically verifies the key and updates a
   deployment **license state** (`ok` / `disabled` + reason).
5. **Expiry middleware** — when state is disabled, block normal HTTP API traffic.
   Workers do **not** check the license and keep processing already-queued work.
6. **Feature gates (v1):** `documents` and `flows` — when a license key is
   present and `state=ok`, APIs for those areas require the matching feature
   string in claims.
7. **Allowlist** so auth + license status/upload routes always work, so an admin
   can paste a new key and recover without Mongo shell access.
8. **Immediate recovery on PUT** — successful license replace sets state to `ok`
   without waiting for the next poll.
9. **No key in DB → ungated** (SaaS / fresh install). Installing a key turns
   enforcement on. No `LICENSE_ENFORCEMENT=off` switch.
10. **Safe status** — never return the full raw token to non-admin callers;
    status includes the granted `features` (and later `limits`).
11. **Forward-compatible limits** — claims may include `limits.users` /
    `limits.workspaces` later; ignore unknown/unused limit keys in v1.

---

## Non-goals

- Per-feature or per-limit commercial entitlements beyond `documents` / `flows`.
- Enforcing **max users / max workspaces** in v1 (schema reserved; see Later).
- Online activation / revocation lists.
- Hardware / hostname / pod binding.
- Frontend-only gating.
- Hard wipe of customer documents on expiry.
- DELETE license API or “Remove license” UI (ops may `$unset` in Mongo by hand).
- Encrypting the payload (signing is enough).
- Stopping or gating **workers** on expiry — they intentionally keep running.

---

## Design principles

```
Browser
  → License settings page (always reachable for system admin)
  → GET/PUT /v0/account/license  (allowlisted)
  → Verify + store key; on success set license state = ok

Background checker (API process only)
  → Every N minutes: load key → verify → set license state ok|disabled

HTTP API (middleware — expiry / invalid)
  → If no key in DB → allow (ungated)
  → If key present and state disabled → reject (except allowlist)
  → If state ok → continue

HTTP API (route Depends — features)
  → If no key in DB → allow
  → If key present → require "documents" or "flows" on matching routers

Workers
  → Never read license state; continue processing as usual
```

**Core rules:**

1. FastAPI enforces (middleware + a few `require_feature` deps). The UI only
   displays and uploads. Workers ignore licensing.
2. **Key present ⇒ subject to API checks.** Missing key ⇒ no license gate.
3. Disabled (expired/invalid) product must still accept a valid replacement key
   via UI/API.
4. Feature strings are the authoritative capability list; do not invent a
   separate `edition` enum for enforcement.

---

## Design notes (kept simple on purpose)

| Concern | Choice |
|---------|--------|
| Enforcement | Expiry middleware + `documents` / `flows` feature deps |
| Workers | Unaffected; never check license |
| Check cadence | Periodic API background task (+ immediate on PUT) |
| Expiry UX | API disabled after expiry (optional short grace) |
| Feature catalog | `documents`, `flows` (+ later user/workspace caps) |

---

## License format

### Token

```text
DRLIC1.<base64url(canonical_json_payload)>.<base64url(ed25519_signature)>
```

Same envelope as the fuller plan so keys / tooling can evolve later.

Canonical JSON:

```python
json.dumps(..., sort_keys=True, separators=(",", ":"), ensure_ascii=False)
```

### Claims (v1)

```json
{
  "license_id": "lic_01JXYZ123",
  "customer_id": "acme",
  "customer_name": "Acme Corp",
  "product": "docrouter",
  "issued_at": "2026-07-14T00:00:00Z",
  "not_before": "2026-07-14T00:00:00Z",
  "expires_at": "2027-07-14T00:00:00Z",
  "grace_days": 7,
  "features": ["documents", "flows"],
  "limits": {},
  "deployment": {
    "installation_id": "inst_acme_prod"
  }
}
```

| Field | Notes |
|-------|--------|
| `product` | Must equal `docrouter`. |
| `expires_at` | After this (+ optional `grace_days`), checker sets disabled. |
| `grace_days` | Optional; default **7** if omitted. During grace: still `ok`, status reports `in_grace`. |
| `features` | String set. v1 recognized ids: `documents`, `flows`. Unknown ids ignored. |
| `limits` | Object reserved for later. v1: accept and return in status; **do not enforce**. |
| `deployment.installation_id` | Optional; when present must match this deployment’s ID. |

Ignore unknown top-level fields on verify (schema stays extensible).

### Features (v1 catalog)

| Feature id | Gates (HTTP API) |
|------------|------------------|
| `documents` | Document upload / list / get / delete, OCR trigger, LLM-on-document, tags-on-docs, and related document routers |
| `flows` | Flow CRUD, flow run / executions APIs, flow editor save paths |

Rules:

- No key in DB → `require_feature` is a **no-op** (allow).
- Key present + `state=ok` + feature missing → `403 FEATURE_NOT_LICENSED`.
- Key present + `state=disabled` → middleware blocks first (except allowlist);
  feature deps do not matter until a valid key restores `ok`.
- A license may grant one or both features (e.g. documents-only).

UI may hide nav for missing features using status `features[]`, but **API
enforcement is authoritative**.

### Limits (later — schema only in v1)

Reserved keys (do not enforce yet):

| Limit | Meaning | Future enforcement |
|-------|---------|-------------------|
| `limits.users` | Max active users in the deployment | Block invite/create when at cap |
| `limits.workspaces` | Max workspaces (organizations) | Block org create when at cap |

Example future claims fragment:

```json
{
  "features": ["documents", "flows"],
  "limits": {
    "users": 50,
    "workspaces": 10
  }
}
```

`null` / omitted limit key = unlimited once enforcement exists. Until then,
status may echo `limits` for display but create/invite paths stay uncapped by
license.

### Keys

| Key | Where |
|-----|--------|
| Private | Internal only (`scripts/licensing/`). Never in image, Helm, customer `.env`, or git. |
| Public | `analytiq_data/licensing/keys/license-public.pem`. Override via `LICENSE_PUBLIC_KEY_PATH` for tests. |

```bash
# scripts/licensing/generate_keys.py
# scripts/licensing/issue_license.py --claims claims.json
```

Dependency: `cryptography` (already used by the repo).

---

## Storage model

### Collection: `license` (singleton)

```python
{
  "_id": "deployment",
  "license_key": "DRLIC1....",       # raw token; treat like other secrets at rest
  "installation_id": "inst_...",     # stable; created once
  "state": "ok",                     # "ok" | "disabled"
  "state_code": null,                # e.g. LICENSE_EXPIRED, LICENSE_INVALID, …
  "state_message": null,
  "checked_at": <datetime>|null,
  "updated_at": <datetime>,
  "updated_by_user_id": "<user_id>|null",
}
```

**Source of truth for expiry allow/deny** is `state` (maintained by checker + PUT).
**Source of truth for features** is always re-verified from `license_key` (or a
short cache of verified claims invalidated on PUT). Do not store claims as
authoritative denormalized truth.

### Installation ID

On first init:

1. Existing `installation_id` → use it.
2. Else `INSTALLATION_ID` env → persist.
3. Else generate `inst_` + `uuid4().hex`, persist once.

Use Mongo `$setOnInsert` / upsert so concurrent startups do not race two IDs.
Never derive from hostname / pod / MAC.

### Bootstrap order for the raw key

1. Mongo already has `license_key` → use it.
2. Else `LICENSE_KEY` env → verify, store, set `state` from verify result.
3. Else `LICENSE_FILE` → same.
4. Else → **no license** (`state` may be unset / irrelevant; gates off).

After bootstrap, **UI/API `PUT` wins**. Env/file are not re-applied every restart
unless Mongo has no `license_key`.

---

## Periodic checker

### Where it runs

Run the check loop in the **API process only** (started from `startup.py`).
Workers do not run the checker and do not read license state.

### Loop

```text
every LICENSE_CHECK_INTERVAL_SECONDS (default 300):
  load singleton from Mongo
  if no license_key:
      ensure gates treat deployment as ungated; set state unused / clear codes
      continue
  verify signature + product + not_before + installation bind
  if verify fails → state=disabled, code=LICENSE_INVALID
  elif now > expires_at + grace → state=disabled, code=LICENSE_EXPIRED
  else → state=ok, clear codes
  set checked_at = now
```

The checker validates the **envelope and expiry**, not which features are
granted. Feature membership is enforced at request time via `require_feature`.

| Rule | Behavior |
|------|----------|
| Interval | Default **5 minutes** (`LICENSE_CHECK_INTERVAL_SECONDS=300`). |
| PUT success | Re-verify immediately; set `state=ok` (or `disabled` if the new key is already bad); do **not** wait for the next tick. |
| Clock | Offline expiry trusts host time (accepted for v1; document in on-prem runbook). |
| DB blip | If Mongo read fails, leave previous `state` unchanged; log error. Do not flip to `ok` on failure. |

Optional in-process cache of `{state, claims}` with short TTL (e.g. 30s) to avoid
a Mongo read on every HTTP request; always invalidate that cache on PUT.

---

## Expiry middleware (global disable)

### When the middleware fires

```text
if no license_key in Mongo:
    allow          # ungated (SaaS / never licensed)
else if state == "ok":
    allow          # feature deps may still deny specific routers
else:
    deny           # disabled — except allowlisted routes
```

### HTTP behavior when disabled

| Condition | Status | `detail.code` |
|-----------|--------|----------------|
| Invalid / wrong product / bad signature / bad installation | `403` | `LICENSE_INVALID` |
| Past grace | `403` | `LICENSE_EXPIRED` |
| Checker has not run yet after key install | Prefer treat as disabled until first successful check, **or** verify inline once on first request — pick one in implementation; recommend **inline verify on first read if `checked_at` is null** so new installs are not stuck for up to one interval. |

Response body should include a short message pointing admins to **Settings → License**.

### Allowlist (always permitted)

These must work even when `state == disabled`:

| Path / area | Why |
|-------------|-----|
| Auth / session / login | Admin must sign in |
| `GET /v0/account/license/status` | Banners / health of license |
| `GET /v0/account/license` | Admin status + masked key |
| `PUT /v0/account/license` | Upload / replace key |
| Liveness / readiness health endpoints | Orchestration |
| Static / NextAuth callbacks as required for the settings page | So the license UI can load |

When disabled, block the rest of the **HTTP API**. Worker processes are not gated.

Implement as **middleware** for expiry/invalid. Feature checks stay as
`Depends(require_feature(...))` on document and flow routers — not a giant
path→feature map in middleware.

### Feature enforcement helpers

```python
# app/licensing_deps.py

async def require_feature(feature: str) -> Callable:  # FastAPI Depends factory
    ...
```

| Condition | Status | `detail.code` |
|-----------|--------|----------------|
| Feature not in claims (key present, state ok) | `403` | `FEATURE_NOT_LICENSED` |

Apply on:

- Document-related routers → `Depends(require_feature("documents"))`
- Flow-related routers → `Depends(require_feature("flows"))`

Do **not** put `require_feature` on license, auth, health, or unrelated account
admin routes.

### Workers

Workers **do not check the license**. After expiry they keep draining the queue
(OCR, LLM, flows, etc.). Enforcement is API-only: new work is hard to enqueue
from the UI/API while disabled or missing a feature, but in-flight /
already-queued jobs finish.

Do not add license reads to `worker.py` or worker loops.

### What “disabled” means for data

- **Block (HTTP, expiry):** nearly all API routes except allowlist.
- **Block (HTTP, missing feature):** only the routers tagged with that feature
  (e.g. no `flows` ⇒ flow APIs 403; documents may still work if granted).
- **Prefer allow if cheap while expired:** read/download/export of existing
  documents (optional stretch; default is full API block except allowlist).

---

## FastAPI surface

### Routes (`/v0/account/license`)

| Method | Path | Auth | Behavior |
|--------|------|------|----------|
| `GET` | `/v0/account/license/status` | Any authenticated user | Safe status JSON; no raw key. Always `200` with `valid` / `mode` / `features`. |
| `GET` | `/v0/account/license` | `get_admin_user` | Status + masked key preview + `installation_id`. |
| `PUT` | `/v0/account/license` | `get_admin_user` | Body `{ "license_key": "DRLIC1..." }`. Verify before write. Persist, set `state` from verify result, return status. Bad key → `400`, leave previous key unchanged. |

No `DELETE` route.

### Status response (safe)

```json
{
  "valid": true,
  "mode": "licensed",
  "license_id": "lic_01JXYZ123",
  "customer_name": "Acme Corp",
  "issued_at": "...",
  "not_before": "...",
  "expires_at": "...",
  "grace_days": 7,
  "days_remaining": 200,
  "in_grace": false,
  "features": ["documents", "flows"],
  "limits": {},
  "installation_id": "inst_...",
  "state": "ok",
  "checked_at": "...",
  "code": null,
  "message": null
}
```

When missing / disabled:

```json
{
  "valid": false,
  "mode": "unlicensed",
  "features": [],
  "limits": {},
  "installation_id": "inst_...",
  "state": "disabled",
  "code": "LICENSE_MISSING",
  "message": "No product license is installed."
}
```

Suggested `mode` values: `licensed` | `grace` | `expired` | `unlicensed` | `invalid`.

Note: `mode: unlicensed` with **no key** means ungated. `mode: expired|invalid`
with a key present means API gated off (except allowlist).

### Manual license removal (ops only)

```js
db.license.updateOne(
  { _id: "deployment" },
  { $unset: { license_key: "" }, $set: { state: "ok", updated_at: new Date() } }
)
```

After unset, gates become inactive (no key). Document in on-prem runbooks; no UI
remove button.

---

## Relationship to Stripe / SPU

| Deployment | License in DB | Behavior | Stripe / SPU |
|------------|---------------|----------|--------------|
| Hosted SaaS | Absent | Ungated | Primary monetization |
| Hosted SaaS | Present (unusual) | Checker + expiry + feature gates apply | Can still meter |
| Self-hosted | Present | Enforced | Typically unset |
| Self-hosted | Absent | Ungated | — |

On-prem packaging should **ship with a customer license installed** (bootstrap
via `LICENSE_KEY` / `LICENSE_FILE` / UI). Do not rely on an env toggle to turn
licensing on.

---

## Admin UI

### Navigation

Under **System** in `SettingsLayout.tsx` (adminOnly):

- Name: **License**
- Href: `/settings/account/license`
- Id: `system_license`

### Page behavior

1. Load admin `GET /v0/account/license`.
2. Show customer, expiry, days remaining, mode, granted **features**, `limits`
   (even if not yet enforced), `installation_id`, last checked.
3. **Update license:** textarea (or file picker) + Save → `PUT`.
4. On success: refresh; toast. On failure: show server message; keep previous key.
5. Masked key preview only; never echo full token after save.
6. Copy `installation_id` for license issuance requests.
7. No remove/clear action.

When the product is disabled by expiry, this page (and login) must still load —
that is the recovery path.

### Banner

Optional shell banner when status is `grace` / `expired` / `invalid` for
authenticated users: “Contact your administrator” / link to License for admins.

Optional: hide Documents / Flows nav when the corresponding feature is absent
(status-driven); API still enforces.

---

## SDK / frontend client

```ts
getLicenseStatus(): Promise<LicenseStatus>
getLicense(): Promise<LicenseAdminView>
updateLicense(licenseKey: string): Promise<LicenseAdminView>
// no deleteLicense
```

Wire through `DocRouterAccountApi` in `src/utils/api.ts`.

---

## Env vars

| Variable | Default | Purpose |
|----------|---------|---------|
| `LICENSE_PUBLIC_KEY_PATH` | packaged PEM | Override for tests |
| `LICENSE_KEY` | unset | Bootstrap raw token if Mongo empty |
| `LICENSE_FILE` | unset | Bootstrap from file if Mongo empty |
| `LICENSE_CHECK_INTERVAL_SECONDS` | `300` | Background checker interval |
| `INSTALLATION_ID` | unset | Seed stable installation id once |

No `LICENSE_ENFORCEMENT` env var.

Document in `docs/env.md` when implementing.

---

## Package layout

```text
packages/python/analytiq_data/licensing/
  __init__.py
  claims.py
  verifier.py
  store.py
  checker.py          # evaluate key → state; used by loop + PUT
  keys/
    license-public.pem
    README.md

packages/python/app/routes/license.py
packages/python/app/licensing_gate.py   # expiry middleware / allowlist
packages/python/app/licensing_deps.py   # require_feature("documents"|"flows")

scripts/licensing/
  generate_keys.py
  issue_license.py
  .gitignore
```

Keep **eager** imports consistent with `analytiq_data/__init__.py` rules — no
lazy `__getattr__` shims.

---

## Phased delivery

### Phase 1 — Format + store + admin API

- Claims (including `features` + empty/optional `limits`), verifier, public key,
  Mongo store, installation id upsert.
- Bootstrap from env/file.
- `GET` status + admin `GET`/`PUT` (PUT sets `state` immediately; status returns
  `features`).
- Tests: valid / expired / bad sig / wrong product / wrong installation /
  PUT rejects without clobbering.

### Phase 2 — Checker + expiry middleware

- Background loop in API startup only.
- Middleware allowlist + `403` when disabled.
- No worker changes.
- Tests: disabled blocks normal routes; allowlist still works; PUT recovers
  without waiting for interval; no key ⇒ ungated; workers unaffected.

### Phase 3 — Feature gates

- `require_feature("documents")` on document routers.
- `require_feature("flows")` on flow routers.
- Tests: documents-only key blocks flows; flows-only blocks documents; both
  allow; no key ⇒ both allow.

### Phase 4 — Admin UI

- Settings nav + license page (show features / limits).
- SDK + frontend wrapper.
- Optional banner + optional nav hiding.

### Phase 5 — Packaging docs

- On-prem: how to request a license (`installation_id`, which features), how to
  paste it, what disabled / feature-denied looks like, manual Mongo clear.
- Update `docs/env.md`.

### Later — Max users / max workspaces

- Enforce `limits.users` on invite/create user.
- Enforce `limits.workspaces` on create organization (product “workspace”).
- Status already carries `limits`; add `LICENSE_LIMIT_EXCEEDED` (`402` or `403`).
- No token format change required if v1 already accepts the `limits` object.

---

## Testing

| Case | Expect |
|------|--------|
| No key in DB | Product works; status `unlicensed` / ungated |
| Valid key with both features | `state=ok`; documents + flows APIs work |
| Valid key, `features: ["documents"]` only | Documents OK; flows → `403 FEATURE_NOT_LICENSED` |
| Valid key, `features: ["flows"]` only | Flows OK; documents → `403 FEATURE_NOT_LICENSED` |
| Expired past grace | `state=disabled`; normal API `403`; license routes work |
| Invalid key still stored | Same as disabled |
| PUT valid key while disabled | Immediate `state=ok`; product recovers |
| PUT bad key | `400`; previous key + state unchanged |
| Checker tick after expiry | Flips `ok` → `disabled` |
| Manual `$unset` of key | Returns to ungated |
| Worker with disabled state | Continues processing (no license check) |
| Non-admin PUT | `401`/`403` |
| `limits` present in token (v1) | Echoed in status; create/invite not capped yet |

Use a temporary Ed25519 keypair in tests.

---

## Security notes

- Private key never in customer artifacts or CI images for customer builds.
- Do not put license tokens in `NEXT_PUBLIC_*`.
- Status endpoints must not echo the full `license_key`.
- Audit admin `PUT` (user id + `license_id` + features, not full token).
- Treat Mongo `license_key` like other secrets at rest.
- Allowlist must stay minimal — do not accidentally exempt all of `/v0/account/*`.

---

## What not to do

- `LICENSED=true` as the only control.
- `LICENSE_ENFORCEMENT=off` while a key remains installed.
- Product DELETE / “Remove license” UI.
- HMAC secret shipped with the app.
- Frontend-only enforcement of `documents` / `flows`.
- Gating or pausing workers on expiry.
- Per-request calls to an external license server.
- Binding to container/pod identity.
- Expanding the feature catalog before product needs it.
- Enforcing `limits.users` / `limits.workspaces` before the Later phase is
  explicitly scheduled (but do accept them in the token).

---

## Out of scope / later

- **Max users / max workspaces** enforcement (schema reserved above).
- Additional feature ids beyond `documents` / `flows`.
- Online check-in + revocation.
- Read/export carve-outs while expired (if not done in v1).
- Public key rotation procedure.
- Clock watermark against rolling the host clock back.
- Page-per-year or other usage quotas.

When extending later, keep local Ed25519 verification as the trust root; any
future online check-in should return a short-lived signed entitlement, never a
bare `allowed: true` from the network.
