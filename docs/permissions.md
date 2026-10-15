# Org permissions and roles (phase 3)

Platform-wide authorization for DocRouter tenants. Applies to **all org-scoped REST** (documents, cases, prompts, flows, etc.), not cases alone. Case-specific behavior (e.g. cascade delete, case LLM runs) follows the same capability rules—see [`document_case_plan.md`](document_case_plan.md).

## Goal

Replace today’s coarse model (`users.role` admin/user + org `members.role` admin/user) with:

- Optional **`users.system_role`** for platform staff (never assigned from customer IdP).
- Org authorization via **permission groups** and a **shared capability resolver**.

**Phase 3 storage:** each member has **`members[].permission_group_ids[]`** referencing **built-in org groups** only (four personas). **Enforcement** always goes through **`member_has_capability(...)`**—routes, UI, and MCP do not scatter ad hoc checks. **Custom groups**, Hyperscience-style flags, and resource scope come later on the same resolver. **Per-case ACL** is deferred.

## Two layers

| Layer | Where | Field | Values |
|-------|--------|--------|--------|
| **Platform** | `users` document | **`system_role`** (optional) | `sysadmin` — omit when the user has no platform role |
| **Organization** | `organizations.members[]` | **`permission_group_ids`** | One or more ids of **built-in** groups in that org (phase 3); custom group ids later |

**Personas (built-in group names):** **Viewer**, **Operator**, **Builder**, **Admin** — stable labels in UI/docs. Do **not** store a separate authoritative **`members[].role`** enum; the API may expose a **display persona** derived from assigned built-in groups (e.g. highest tier) for convenience.

**Terminology:** **“system role”** (platform) vs **“permission groups”** / **“persona”** (org)—avoid bare “role” without context.

**Why two layers:** Platform staff (`sysadmin`) use cross-org account APIs; org capabilities govern tenant data and config. Customer **Microsoft Entra** (and other IdPs) map **only** to org **permission group ids**, never to `system_role`.

## Built-in permission groups (phase 3)

Each org seeds **four non-deletable built-in groups** (on org create and migration). Each group has a fixed capability set. Ids are org-scoped (e.g. stored on the org document or a small `organization_permission_groups` collection).

| Built-in group (persona) | Capabilities |
|--------------------------|--------------|
| **Viewer** | `documents.read`, `config.read` |
| **Operator** | Viewer + `documents.write`, `runs.execute` |
| **Builder** | Operator + `config.write` |
| **Admin** | Builder + `org.admin` |

**Tier order (UI only):** Viewer < Operator < Builder < Admin. For these four groups, **union of capabilities** equals **highest assigned persona** (nested tiers). The resolver should still implement **union** so custom groups later do not require new merge rules.

**Human-readable matrix** (same rules as above):

| Persona | Documents & cases | Runs (OCR, doc LLM, case LLM, bulk, flow *trigger*) | Config CRUD | Org admin |
|---------|-------------------|------------------------------------------------------|-------------|-----------|
| **Viewer** | Read/list/get | No | Read only | No |
| **Operator** | Read + write | Yes | Read only | No |
| **Builder** | Same as Operator | Yes | Yes | No |
| **Admin** | Same as Builder | Yes | Yes | Yes |

Flow **execution** in the worker runs as system; human/API **trigger** and **definition edit** use `runs.execute` and `config.write`. **Case LLM** requires **`runs.execute`**.

## Capability resolver (enforcement layer)

All org authorization uses a **single resolver** (e.g. `member_has_capability(org_id, user_id, capability) -> bool`):

1. Load member’s **`permission_group_ids`** for that org.
2. Resolve each id to a group’s capability set (built-ins in phase 3).
3. **Union** capabilities; grant if the requested capability is present.

FastAPI, frontend, and phase-4 MCP call the resolver (or `require_capability(...)` wrappers), not group ids or persona names in route handlers.

### Capabilities (catalog)

| Capability | Covers (examples) |
|------------|-------------------|
| **`documents.read`** | List/get documents and cases |
| **`documents.write`** | Upload, PUT, bulk doc ops, assign/remove case, delete document |
| **`runs.execute`** | OCR, doc LLM, case LLM (`POST .../cases/{id}/runs`), bulk analyze, flow trigger from UI/API |
| **`config.read`** | Read tags, schemas, prompts, forms, flow definitions |
| **`config.write`** | CRUD on tags, schemas, prompts, forms; author/edit flow definitions (including assign-to-case node—see [`document_case_plan.md`](document_case_plan.md)) |
| **`org.admin`** | Members, billing, org settings, SSO mapping config, cascade case delete |

### Route mapping notes (phase 3)

The six capabilities above are the **only** org permission flags in phase 3. The route-table regression test and this section assign every org-scoped REST handler to one or more of them (no ad hoc checks). Worker-internal flow steps are out of scope; gates apply to **human/API** callers.

#### Documents and cases

| Routes / behavior | Capability |
|-------------------|------------|
| List/get documents, cases, case runs/results (read) | `documents.read` |
| Upload, PATCH/PUT, bulk doc ops, assign/remove case on doc, delete document | `documents.write` |
| Case LLM `POST .../cases/{id}/runs` | `runs.execute` |
| Delete case **with cascade** | `org.admin` (not `documents.write` alone) |

#### Forms

| Routes / behavior | Capability |
|-------------------|------------|
| CRUD on form definitions, list versions | `config.read` / `config.write` |
| GET form submission for a document | `documents.read` |
| POST/DELETE form submission (human review / HITL on a doc) | `documents.write` |

Form **schemas** are config; **submissions** are document-bound operational data (operators review; viewers read-only).

#### Flows (definitions and publishing)

| Routes / behavior | Capability |
|-------------------|------------|
| List/get flows, revisions, node types, revision pins/blobs (read) | `config.read` |
| Create/patch/save/delete flow, activate/deactivate, import-style saves | `config.write` |
| Flow **credentials** and OAuth connect/callback (org-stored secrets) | `config.write` |
| Editor webhook/batch **test** hooks that only exercise draft/revision state | `config.write` |

#### Flows (executions and runtime)

| Routes / behavior | Capability |
|-------------------|------------|
| List/get executions, execution blobs, run status (read) | `config.read` |
| `…/run`, run-on-document, chat-trigger **production** execution, OCR/doc LLM/bulk analyze | `runs.execute` |
| Stop, resume, delete execution | `runs.execute` |
| **Flow chat** (chat trigger + streaming run) | `runs.execute` |
| Chat/test against **unsaved revision snapshot** in the builder | `config.write` (treat as editor test; use `runs.execute` if the endpoint only runs pinned/active flow) |

#### Config library (non-flow)

| Routes / behavior | Capability |
|-------------------|------------|
| Tags, schemas, prompts — read / write | `config.read` / `config.write` |

#### Knowledge bases

| Routes / behavior | Capability (interim) |
|-------------------|------------------------|
| KB list/get/search (read) | `config.read` |
| KB create/update/delete, ingest, reindex | `config.write` |

Split to **`knowledge_bases.read` / `knowledge_bases.write`** in phase 3+ if KB admin must differ from prompt/schema builders (see open questions).

#### Agent (org agent / extraction sessions)

| Routes / behavior | Capability |
|-------------------|------------|
| Start/continue agent sessions, tool calls that run extraction/LLM | `runs.execute` |
| Read session history / messages | `documents.read` or `config.read` (match route: doc-scoped → `documents.read`) |

Phase 4 MCP/agent tools use the same mapping.

#### Webhooks

| Routes / behavior | Capability |
|-------------------|------------|
| List/get endpoints, deliveries, retry read paths | `config.read` |
| Create/update/delete webhook endpoints, secrets, enable/disable | `org.admin` |

Aligns with today’s stricter admin gate on webhook mutations.

#### Org admin and account (org context)

| Routes / behavior | Capability |
|-------------------|------------|
| Members, invites, org profile/settings, billing, SSO config (phase 3b) | `org.admin` |
| User **API tokens** (account routes, own user) | Not org capabilities — any authenticated user for self; no change in phase 3 unless org-wide service tokens are added |

#### Platform-only

System email, global LLM admin, AWS/GCP/Azure system settings, license — **`system_role`** / existing account admin deps, not the org resolver.

#### Optional splits (phase 3+, not new built-in personas)

If custom permission groups need finer HS-style control, add capabilities **without** changing the four built-ins’ defaults, e.g. `integrations.secrets.write`, `flows.executions.control`, `webhooks.manage`, dedicated KB flags—each maps to a subset of routes above.

### API surface (implementation)

- **Primary:** `require_capability("documents.write")` on org routes.
- **Optional sugar:** `require_org_operator`-style helpers implemented via capability checks on the resolver.
- **Route-table regression test:** every org route declares **required capability(ies)**.
- **Frontend:** load **effective capabilities** (or group ids) from an org API; gate actions by capability name, aligned with backend.
- **API tokens** inherit the user’s effective capabilities in that org; `system_role` applies only to account/platform routes the token user has.

## Platform: `users.system_role`

- Replace today’s `users.role` (`admin` \| `user`) with optional **`system_role`**.
- **Migration:** `users.role == "admin"` → `system_role: "sysadmin"`; `users.role == "user"` → **unset** `system_role` (remove legacy `role` when safe).
- **`is_system_admin`:** `user.get("system_role") == "sysadmin"`. Additional values get explicit checks (no generic “any system role” superuser unless intended).
- Sysadmin does **not** replace org membership; org routes use the **capability resolver** unless a route is account-level and sysadmin-only. (Define break-glass support access when implementing.)

## Migration & defaults

- **Users:** `role: admin` → `system_role: sysadmin`; drop `role: user` in favor of absent `system_role`.
- **Org members:** seed built-in groups on each org; map legacy membership:
  - `members.role: admin` → **`permission_group_ids`** = **[Admin]** (built-in id).
  - `members.role: user` → **[Builder]** (preserves today’s full-member access).
- Remove legacy **`members.role`** when all readers/writers use **`permission_group_ids`**.
- **New org members (manual invite):** default **[Operator]** unless an org admin assigns Viewer or Builder/Admin groups.

## External identity (phase 3b — Microsoft Entra first)

Entra is the **first** enterprise IdP target; **Okta** and **Google Workspace** follow the **same pattern** (per-org OIDC/SAML + group mapping → built-in group ids). Phase 3b is **authentication + membership sync**, not a change to the resolver or capability catalog.

### Per-org SSO config

- Entra **tenant id**, OIDC (SAML if required), allowed **email domains**, join policy (invite-only vs domain).
- **Mapping table:** Entra **group object id** or **app role id** → org **built-in `permission_group_id`** (prefer **app roles** when customers want exactly four tiers; security groups when names match operational teams).
- Do **not** map customer Entra groups to **`users.system_role`**.

### Login-time sync

1. Authenticate via Entra (NextAuth OIDC/SAML or broker).
2. JIT provision/link **`users`**; ensure **`organizations.members[]`** for the target org (invite or domain rule).
3. Read groups/roles from token (or **Microsoft Graph** when groups claim is omitted due to overage).
4. Map external ids → built-in group ids; set **`permission_group_ids`** (see merge policy below).
5. Session/API calls use existing JWT; FastAPI resolves capabilities from stored groups.

### Merge policy (document at implement time)

- **IdP-owned (default for SSO orgs):** each login **replaces** `permission_group_ids` with the mapped set from Entra (minimum one built-in id, or deny login if unmapped).
- **Manual override (optional):** org admin assigns extra groups; define whether next SSO login overwrites or preserves “local” assignments.
- **Multiple Entra assignments:** map each to a built-in id; resolver **unions** capabilities (equivalent to highest persona for built-ins only).

### Later IdP extras (not 3b)

- **SCIM** for offboarding and group changes without login.
- **Custom permission groups** and flow/tag scope (resolver union + scope dimension).
- LDAP/AD direct: usually via Entra or SAML bridge, not a separate membership model.

## Enforcement

- Org routes: **`require_capability(...)`** via the shared resolver.
- Account/platform routes: `system_role` as today.
- Route-table regression test on **capabilities**.
- **Phase 4:** MCP/agent tools use the same resolver (+ sysadmin on platform tools if any).

## Phases (cross-reference)

| Phase | Work |
|-------|------|
| **3** | `system_role`; seed **four built-in groups** per org; **`members[].permission_group_ids`**; **capability resolver** + route capability table on all REST (see [`document_case_plan.md`](document_case_plan.md) for assign-to-case flow node) |
| **3b** | **Microsoft Entra** SSO (OIDC/SAML), per-org mapping → built-in group ids, login sync; same hook pattern for Okta / Google Workspace |
| **3+** | Custom permission groups, HS-style flags, flow/tag-scoped access (extend resolver only) |
| **4** | MCP/agent use resolver; optional webhook events |

## Open questions

1. Sysadmin break-glass: org API access without membership vs must be invited (and whether break-glass grants capabilities without group membership).
2. Entra unmapped user: deny login vs default **Viewer** vs invite-only error.
3. SSO overwrite vs local override on **`permission_group_ids`**.
4. KB: dedicated capability vs `config.write` / Admin group only.
5. Automation identity: audit attribution for flow worker writes vs human operator.

## Deferred

Per-case ACL; access audit log for group/membership changes and destructive actions.
