# Product license (signed offline key)

Plan for **cryptographically signed, offline product licenses** for self-hosted /
on-prem DocRouter. FastAPI verifies and enforces entitlements; Next.js only
displays status and lets system admins paste/update the license key.

**Primary files (proposed):**

| Area | Path |
|------|------|
| Verifier + claims | `packages/python/analytiq_data/licensing/` (new) |
| Mongo store + cache | `packages/python/analytiq_data/licensing/store.py` (new) |
| FastAPI routes | `packages/python/app/routes/license.py` (new) |
| FastAPI deps | `packages/python/app/licensing.py` (new) or deps in route module |
| Router registration | `packages/python/app/main.py` |
| Public key asset | `packages/python/analytiq_data/licensing/keys/license-public.pem` |
| Issuer (internal only) | `scripts/licensing/` (repo-local; private key never ships) |
| Admin UI | `packages/typescript/frontend/src/app/settings/account/license/` |
| Settings nav | `packages/typescript/frontend/src/components/SettingsLayout.tsx` |
| SDK | `packages/typescript/sdk/src/docrouter-account.ts` (+ types) |
| Frontend API wrapper | `packages/typescript/frontend/src/utils/api.ts` |
| Tests | `packages/python/tests/test_license.py` |

**Related docs:**

- [On-prem installation architecture](./on_prem_installation_architecture.md)
- [Environment variables](./env.md)
- [Authentication](./authentication.md)

**Implementation order:** Phase 1 (format + verify + store + status API) →
Phase 2 (admin UI upload/display) → Phase 3 (feature / limit enforcement hooks) →
Phase 4 (expiration UX + grace policy).

---

## Problem

DocRouter today has **no product license key**. Monetization and gating are:

| Mechanism | Scope | Role |
|-----------|--------|------|
| Stripe + SPU credits | SaaS / connected billing | Usage metering; `402` when over limit |
| Org `experimental_features` | Per organization | Soft UI/API gate for experimental nodes |
| `app/limits.py` | Global | Anti-DoS caps, not commercial entitlements |
| `system_settings` | Deployment | Ops knobs (workers, concurrency) |

Self-hosted / air-gapped customers need a **deployable entitlement** that:

1. Works with **no outbound network** (no license server).
2. Cannot be forged by editing env vars or Mongo alone.
3. Can be **viewed and replaced** by a system admin in the UI.
4. Is checked efficiently (not re-parsed from disk/DB on every request).

---

## Goals

1. **Ed25519-signed license token** (`DRLIC1.<payload>.<signature>`) verified with an
   embedded public key in the FastAPI / worker processes.
2. **Offline only for v1** — no external license server, no check-in, no revocation
   API. Revocation = issue a shorter-lived or replacement license offline.
3. **Deployment-scoped store** in Mongo (singleton), updatable via admin API + UI;
   optional bootstrap from env / file on first start.
4. **In-memory cache of verified claims, TTL 5 minutes** (and invalidate immediately
   on successful `PUT` of a new key).
5. **FastAPI enforces** features/limits; Next.js only presents status and the update form.
6. **Presence-based enforcement** — if a license key is stored in Mongo, its claims are
   always enforced. There is no env flag to disable enforcement while a key remains
   installed. No key in DB → no license gates (SaaS / pre-license deploys).
7. **Clear coexistence with Stripe/SPU** — licensing does not replace SaaS billing in
   hosted mode; see [Relationship to Stripe / SPU](#relationship-to-stripe--spu).
8. **Safe status endpoint** — never return the raw license token to non-admin callers;
   admins may see a masked preview only.

---

## Non-goals

- External / online license activation server (deferred; architecture should not
  preclude a later check-in mode).
- Binding to MAC address, hostname, pod name, or other volatile hardware IDs.
- Symmetric HMAC keys shipped in the product image.
- Feature gating only in Next.js / browser code.
- Permanently locking customers out of their own documents after expiration
  (prefer restricted write/process, keep read/export).
- Per-organization commercial licenses in v1 (deployment-wide license only).
- Replacing Stripe for the hosted SaaS product.
- Encrypting the license payload (signing is sufficient; claims are not secret).
- A runtime `LICENSE_ENFORCEMENT=off` (or similar) switch that ignores an installed key.

---

## Design principles

```
Browser
  → Next.js admin UI (display / paste key)
  → FastAPI /v0/account/license (auth: system admin)
  → Verify Ed25519 + store raw token in Mongo
  → Cache claims 5m

Product API / workers
  → get_cached_license() every call site
  → If no key in DB → skip license gates
  → If key present → verify + enforce features / limits / expiry
  → Business logic
```

**Core rules:**

1. FastAPI (and workers) enforce the license. The UI never decides whether a licensed
   operation is allowed.
2. **License in DB ⇒ enforce it.** No customer-facing switch can keep a stored key and
   skip its constraints. Clearing the key is an intentional ops escape hatch only
   (manual Mongo edit); there is no DELETE API or UI action to remove it.

---

## License format

### Token

```text
DRLIC1.<base64url(canonical_json_payload)>.<base64url(ed25519_signature)>
```

- Prefix `DRLIC1` = version 1 of the DocRouter license envelope.
- Payload bytes are signed **exactly** as stored in the middle segment (canonical JSON
  before base64url).
- Canonical JSON: `json.dumps(..., sort_keys=True, separators=(",", ":"), ensure_ascii=False)`.

### Claims (v1)

```json
{
  "license_id": "lic_01JXYZ123",
  "customer_id": "acme",
  "customer_name": "Acme Corp",
  "product": "docrouter",
  "edition": "enterprise",
  "issued_at": "2026-07-14T00:00:00Z",
  "not_before": "2026-07-14T00:00:00Z",
  "expires_at": "2027-07-14T00:00:00Z",
  "grace_days": 30,
  "features": [
    "flows",
    "knowledge_bases",
    "sso",
    "audit_logs"
  ],
  "limits": {
    "pages_per_year": 5000000,
    "users": 100,
    "organizations": 50
  },
  "deployment": {
    "installation_id": "inst_acme_prod"
  }
}
```

| Field | Notes |
|-------|--------|
| `product` | Must equal `docrouter` (constant in verifier). |
| `edition` | Informational + coarse UI label (`community` / `team` / `enterprise`). |
| `features` | String set checked by `require_feature("flows")` etc. |
| `limits` | Contractual caps; enforcement is separate (atomic counters). `null` / omitted = unlimited. |
| `grace_days` | Days after `expires_at` before hard restrict (default 30 if omitted). |
| `deployment.installation_id` | Optional bind to this deployment’s stable ID. |

### Keys

| Key | Where |
|-----|--------|
| **Private** | Internal only (`scripts/licensing/`, encrypted PEM + passphrase). Never in Docker image, Helm chart, customer `.env`, or git. |
| **Public** | Shipped with the product under `analytiq_data/licensing/keys/license-public.pem`. Override path via `LICENSE_PUBLIC_KEY_PATH` for testing. |

Generate once (internal):

```bash
# scripts/licensing/generate_keys.py — run offline; store private key in secrets manager
```

Issue licenses (internal):

```bash
# scripts/licensing/issue_license.py --claims claims.json
# → prints DRLIC1....
```

Dependency: `cryptography` (already used by `analytiq_data.crypto.encryption`).

---

## Storage model

Prefer **Mongo singleton** over file-only mounts so the admin UI can update the key
without redeploying Kubernetes secrets. Optional file/env remains for bootstrap.

### Collection: `license` (singleton)

```python
{
  "_id": "deployment",
  "license_key": "DRLIC1....",          # raw token; treat as secret-ish
  "installation_id": "inst_...",        # stable; created once if missing
  "updated_at": <datetime>,
  "updated_by_user_id": "<user_id>|null",
  # Denormalized last-verify metadata (optional, for ops):
  "last_verified_at": <datetime>|null,
  "last_verify_error": <str>|null,
}
```

Do **not** store decrypted claims as the source of truth — always re-verify from
`license_key` when the cache refreshes. Denormalized fields are for display/debug only.

### Installation ID

On first license module init / startup:

1. If `license.installation_id` exists → use it.
2. Else if `INSTALLATION_ID` env is set → persist it.
3. Else generate `inst_` + `uuid4().hex`, persist, and log once.

Never derive from hostname / pod / MAC. Optional license claim
`deployment.installation_id` must match when present.

### Bootstrap order for the raw key

1. If Mongo already has `license_key` → use it.
2. Else if `LICENSE_KEY` env is set → verify, store, use.
3. Else if `LICENSE_FILE` path exists → read, verify, store, use.
4. Else → **no license** (status `valid: false`, code `LICENSE_MISSING`).

After bootstrap, **UI/API updates win** (replace via `PUT` only). Env/file are not
re-applied on every restart unless Mongo has no `license_key`. To fully clear a
license and return to ungated mode, an operator must remove/`unset` `license_key` in
Mongo by hand — there is no product API or UI for deletion.

---

## Verification + 5-minute cache

### `LicenseService` (process-local)

```text
get_license() / get_status():
  if cache hit and age < 5 minutes and not invalidated:
      re-check temporal validity (not_before / expires / grace) against now
      return cached claims or status
  load license_key from Mongo (or bootstrap)
  verify signature + claims
  cache (claims, loaded_at, raw fingerprint)
  return
```

| Rule | Behavior |
|------|----------|
| TTL | **5 minutes** (`LICENSE_CACHE_TTL_SECONDS=300`, overridable). |
| Invalidate | On successful `PUT /v0/account/license`; also expose `invalidate_license_cache()` for tests. |
| Workers | Each API / worker process has its own cache (same pattern as `system_settings` Textract/LLM caches). No Redis required. |
| Expiration while cached | Always re-evaluate `now` vs `expires_at` / grace on every `get_*`; a cached document must not stay “valid” past real expiry. |
| Momentary DB blip | If Mongo read fails and cache is still within TTL, serve last verified claims (still subject to temporal checks). After TTL with no successful reload → `LICENSE_UNAVAILABLE`. |
| Tamper / bad signature | Fail immediately; do not keep previous claims once a new key was accepted into the store but fails verify (reject the write). |

Public key load once at service construction (`lru_cache` / module singleton).

---

## FastAPI surface

Register in `main.py` like `system_settings_router`.

### Routes (`/v0/account/license`)

| Method | Path | Auth | Behavior |
|--------|------|------|----------|
| `GET` | `/v0/account/license/status` | Authenticated user (any) **or** admin-only — pick one; recommend **any authenticated user** for banner UX, **no raw key** | Returns safe status JSON; never `403` solely for expired — use `200` + `valid` / `mode`. |
| `GET` | `/v0/account/license` | `get_admin_user` | Status + masked key preview (`DRLIC1.…` last 6 chars) + `installation_id`. |
| `PUT` | `/v0/account/license` | `get_admin_user` | Body `{ "license_key": "DRLIC1..." }`. Verify **before** write. On success: persist, invalidate cache, return status. On failure: `400` with `LICENSE_INVALID` / message; leave previous key unchanged. |

No `DELETE` route. Clearing a license is a manual DB operation (see below).

### Status response (safe)

```json
{
  "valid": true,
  "mode": "licensed",
  "license_id": "lic_01JXYZ123",
  "customer_name": "Acme Corp",
  "edition": "enterprise",
  "issued_at": "...",
  "not_before": "...",
  "expires_at": "...",
  "grace_days": 30,
  "days_remaining": 200,
  "in_grace": false,
  "features": ["flows", "knowledge_bases"],
  "limits": { "pages_per_year": 5000000, "users": 100, "organizations": 50 },
  "installation_id": "inst_...",
  "code": null,
  "message": null
}
```

When invalid / missing:

```json
{
  "valid": false,
  "mode": "unlicensed",
  "features": [],
  "limits": {},
  "installation_id": "inst_...",
  "code": "LICENSE_MISSING",
  "message": "No product license is installed."
}
```

Suggested `mode` values: `licensed` | `grace` | `expired` | `unlicensed` | `invalid`.

### Enforcement helpers

```python
# app/licensing.py (or analytiq_data + thin FastAPI wrappers)

async def require_valid_license(...) -> LicenseClaims
async def require_feature(feature: str) -> Callable  # FastAPI Depends factory
async def require_not_expired_hard(...)  # blocks after grace
```

HTTP mapping:

| Condition | Status | `detail.code` |
|-----------|--------|----------------|
| Missing / invalid signature / wrong product / wrong installation | `403` | `LICENSE_INVALID` |
| Past grace (hard expire) | `403` | `LICENSE_EXPIRED` |
| Feature not in claims | `403` | `FEATURE_NOT_LICENSED` |
| Quantitative limit exceeded | `402` or `403` | `LICENSE_LIMIT_EXCEEDED` (align with SPU’s `402` if we want consistent “quota” UX) |

Apply via `Depends` on specific routers (same style as `get_admin_user`), not a global
middleware in v1.

### When gates fire

```text
if no license_key in Mongo:
    allow  # ungated (hosted SaaS, fresh install, key never installed)
else:
    verify(license_key)
    enforce claims  # features, limits, not_before / expires / grace
```

Helpers should short-circuit when the store has no key (equivalent to “licensing
inactive”), and **must not** ignore a present key.

Invalid / expired-past-grace keys that are still stored continue to **block** gated
operations until an admin replaces them with a valid key via `PUT`, or an operator
clears `license_key` in Mongo by hand.

### Manual license removal (ops only)

To return a deployment to ungated mode (or recover from a bad key without a
replacement):

```js
// Mongo shell / Compass — ops only; not exposed in product UI
db.license.updateOne(
  { _id: "deployment" },
  { $unset: { license_key: "" }, $set: { updated_at: new Date() } }
)
```

Restart or wait for cache TTL (≤ 5m) so processes drop the cached claims. Document
this in on-prem runbooks; do not add a “Remove license” button.

---

## Relationship to Stripe / SPU

| Deployment | License in DB | Behavior | Stripe / SPU |
|------------|---------------|----------|--------------|
| Hosted SaaS | Absent | No license gates | Primary monetization |
| Hosted SaaS | Present (unusual) | Claims enforced | Can still meter if configured |
| Self-hosted | Present | Claims enforced | Typically unset; SPU no-ops without Stripe |
| Self-hosted | Absent | Ungated (same as SaaS) | — |

On-prem packaging should **ship with a customer license installed** (bootstrap via
`LICENSE_KEY` / `LICENSE_FILE` / UI). Do not rely on an env toggle to “turn licensing
on”; installing the key is what turns enforcement on.

---

## Features and limits (v1 catalog)

Start small; strings are stable API contracts.

### Features (examples)

| Feature id | Gates |
|------------|--------|
| `flows` | Flow editor + flow run APIs |
| `knowledge_bases` | KB CRUD / index / chat |
| `sso` | SSO configuration endpoints (when present) |
| `audit_logs` | Audit export APIs (when present) |
| `premium_connectors` | Selected cloud connector packs |

When no license is in the DB, `require_feature` is a no-op (allow). When a license
is present, missing feature ⇒ deny. Product code only calls `require_feature` for
capabilities that are actually licensed.

### Limits

| Limit | Enforcement idea |
|-------|------------------|
| `users` | Count active users on create/invite |
| `organizations` | Count orgs on create (complement `limits.py` DoS caps) |
| `pages_per_year` | Atomic counter in Mongo (year bucket); increment on defined page events |

**Page definition (must be fixed in contract + code):** prefer **OCR-processed pages
successfully stored** (or uploaded PDF page count if OCR skipped). Document the choice
in this file when implementing Phase 3; do not leave it ambiguous.

Atomic reserve pattern (same idea as the starting design):

```python
# find_one_and_update with $expr so check + inc is one round-trip
```

---

## Expiration policy

| Window | Behavior |
|--------|----------|
| \> 30 days remaining | Normal |
| ≤ 30 days | Admin UI warning banner |
| ≤ 7 days | Stronger warning |
| `expires_at` ≤ now &lt; `expires_at + grace_days` | `mode: grace`; allow processing; banner |
| After grace | `mode: expired`; block **new** processing / creates; allow read, download, export |
| Invalid / tampered key still in DB | Block gated ops immediately until replaced via `PUT` or cleared in Mongo by hand |

Optional later claims (`maintenance_expires_at`, `max_product_version`) are **out of v1**
unless needed; keep the schema extensible (ignore unknown fields on verify).

---

## Admin UI

### Navigation

Add under **System** in `SettingsLayout.tsx` (adminOnly), sibling to Users / Development:

- Name: **License**
- Href: `/settings/account/license`
- Id: `system_license`

### Page behavior

1. Load `GET /v0/account/license` (admin).
2. Show customer, edition, expiry, days remaining, features, limits, installation ID,
   mode / validity.
3. **Update license:** textarea (or file picker reading text) + Save.
   - Calls `PUT /v0/account/license` (replace only; no remove).
   - On success: refresh status; toast.
   - On failure: show server message; keep previous license.
4. Masked current key preview only (never full key in DOM after save unless user pastes
   a new one into the form).
5. Optional: download/copy installation ID for license issuance requests.
6. No “Remove license” / clear action in the UI.

Reuse settings typography helpers (`settingsPageTitleClass`, etc.) from
`SettingsLayout.tsx`. Mirror patterns from Development / subscription pages
(client component + `DocRouterAccountApi`).

### Non-admin visibility

Optional thin banner in shell when `GET …/license/status` reports `grace` / `expired`
(authenticated users). Keep copy high-level (“Contact your administrator”).

---

## SDK / frontend client

Extend `@docrouter/sdk` `DocRouterAccount`:

```ts
getLicenseStatus(): Promise<LicenseStatus>
getLicense(): Promise<LicenseAdminView>      // admin
updateLicense(licenseKey: string): Promise<LicenseAdminView>
// no deleteLicense
```

Wire through `DocRouterAccountApi` in `src/utils/api.ts` like other account admin APIs.

Python SDK: add matching methods under account client when TS is done (or same PR).

---

## Env vars

| Variable | Default | Purpose |
|----------|---------|---------|
| `LICENSE_PUBLIC_KEY_PATH` | packaged PEM | Override for tests |
| `LICENSE_KEY` | unset | Bootstrap raw token if Mongo empty |
| `LICENSE_FILE` | unset | Bootstrap from file if Mongo empty |
| `LICENSE_CACHE_TTL_SECONDS` | `300` | In-memory cache TTL |
| `INSTALLATION_ID` | unset | Seed stable installation id once |

No `LICENSE_ENFORCEMENT` (or similar) env var. Enforcement follows DB presence only.

Document in `docs/env.md` when implementing.

---

## Package layout (concrete)

```text
packages/python/analytiq_data/licensing/
  __init__.py
  claims.py          # Pydantic LicenseClaims, Limits, DeploymentBinding
  verifier.py        # Ed25519 verify, temporal + product + installation checks
  store.py           # Mongo get/put, installation_id ensure, bootstrap
  service.py         # CachedLicenseService (5m TTL)
  keys/
    license-public.pem
    README.md        # "public only; private key is not in this repo"

packages/python/app/routes/license.py
packages/python/app/licensing_deps.py   # require_feature, etc.

scripts/licensing/                   # internal; .gitignore private PEMs
  generate_keys.py
  issue_license.py
  .gitignore                         # *.pem except public examples
```

Keep **eager** imports consistent with `analytiq_data/__init__.py` rules — either
export a thin `ad.licensing` facade eagerly or import `analytiq_data.licensing`
directly from app code without lazy `__getattr__` shims.

---

## Phased delivery

### Phase 1 — Core verify + store + status API

- Claims models, verifier, public key asset, Mongo store, 5m cache.
- Bootstrap from env/file.
- `GET` status + admin `GET`/`PUT`.
- Tests: valid / expired / wrong sig / wrong product / wrong installation / cache TTL
  / PUT rejects bad key without clobbering.
- No product route gates yet (helpers exist; call sites land in Phase 3). Absent key ⇒
  helpers no-op so SaaS behavior is unchanged.

### Phase 2 — Admin UI

- Settings nav + license page (display + update).
- SDK methods + frontend wrapper.
- Banner hooks optional.

### Phase 3 — Enforcement hooks

- Pick 1–2 high-value gates first (e.g. `flows`, org/user create limits).
- Wire `require_feature` / limit checks: **no-op if no key in DB; enforce if key present**.
- Worker paths that enqueue licensed work must call the same service (not only HTTP deps).

### Phase 4 — Expiration UX + grace polish

- Banner thresholds (30d / 7d / grace / expired).
- Hard-expire: block new processing; keep read/export.
- Docs for on-prem install: how to request a license (send `installation_id`), how to paste it.

---

## Testing

| Case | Expect |
|------|--------|
| No key in DB | Gated routes allow; status `unlicensed` / ungated |
| Valid key in DB | Status valid; features enforced |
| Feature not in claims | `403 FEATURE_NOT_LICENSED` |
| Expired inside grace | `mode: grace`; processing allowed |
| Expired past grace (key still stored) | Hard restrict |
| Invalid key still in DB | Gated routes blocked until `PUT` or manual Mongo clear |
| Manual `$unset` of `license_key` | Returns to ungated allow (after cache TTL / restart) |
| No DELETE API | Route absent; SDK has no delete helper |
| Bad signature on PUT | `400`; previous key retained |
| Cache | Second `get` within 5m does not re-read Mongo (mock/spy); after TTL re-reads |
| Installation mismatch | Verify fails |
| Non-admin PUT | `401`/`403` |

Use temporary Ed25519 keypair in tests (do not depend on production private key).

---

## Security notes

- Private key never in customer artifacts or CI images used for customer builds.
- Do not put license tokens in `NEXT_PUBLIC_*`.
- Status endpoints must not echo the full `license_key`.
- Audit admin `PUT` (log user id + license_id after verify, not full token).
- Do not expose license deletion in the product; ops clears Mongo by hand if needed.
- Treat Mongo `license_key` like other secrets at rest (same DB trust model as
  `cloud_config`; encryption-at-rest is a separate infra concern).

---

## What not to do (checklist)

- `LICENSED=true` env as the only control.
- `LICENSE_ENFORCEMENT=off` (or any flag) that skips checks while a key remains in Mongo.
- A product API or UI action that deletes/clears the stored license key.
- HMAC secret shipped with the app.
- Frontend-only feature flags for paid capabilities.
- Per-request calls to any external license HTTP API (none in v1 anyway).
- Binding to container/pod identity.
- Encrypt-instead-of-sign.
- Hard wipe of customer documents when the license expires.

---

## Out of scope / later

- Online check-in + revocation lists with multi-day grace for network outage.
- Per-organization entitlement overlays.
- `maintenance_expires_at` / `max_product_version` upgrade gates.
- License-driven disabling of Stripe UI for pure on-prem builds.

When online mode is added later, keep local Ed25519 verification as the source of
runtime trust; any check-in response should itself be a short-lived signed
entitlement, never a bare `allowed: true` from the network.
