# Org permissions and roles (phase 3)

Platform-wide authorization for DocRouter tenants. Applies to **all org-scoped REST** (documents, cases, prompts, flows, etc.), not cases alone. Case-specific behavior (e.g. cascade delete, case LLM runs) follows the same org roles—see [`document_case_plan.md`](document_case_plan.md).

## Goal

Replace today’s coarse model (`users.role` admin/user + org `members.role` admin/user) with:

- Optional **`users.system_role`** for platform staff.
- Org member **`role`** personas: `viewer` | `operator` | `builder` | `admin`.

**Storage in v1 is personas only** (one `members[].role` per org). **Enforcement uses a shared capability resolver** so routes, UI, and MCP do not compare role strings ad hoc. Later we can add Hyperscience-style permission groups and flags **behind the same resolver** without rewriting every endpoint. **Per-case ACL** is deferred.

## Two layers

Use different field names so “role” is not overloaded:

| Layer | Where | Field | v1 values |
|-------|--------|--------|-----------|
| **Platform** | `users` document | **`system_role`** (optional) | `sysadmin` — omit field when the user has no platform role |
| **Organization** | `organizations.members[]` | **`role`** (org member role) | `viewer` \| `operator` \| `builder` \| `admin` |

**Why two layers:** Platform staff (sysadmin) can manage cross-org account APIs; org roles govern tenant data and config. Most users have **only** org roles; sysadmin is rare. Future platform roles (support, billing ops, etc.) extend **`system_role`** without changing org enums.

**Terminology in UI/docs:** **“system role”** vs **“org role”** (or “member role”)—never bare “role” without context.

## Capability resolver (enforcement layer)

All org authorization goes through a **single resolver** (e.g. `member_has_capability(org_id, user_id, capability) -> bool`). FastAPI dependencies, the frontend, and phase-4 MCP tools call the resolver (or thin wrappers), not raw `members[].role` comparisons scattered in handlers.

### Capabilities (v1 catalog)

Stable string identifiers; route and UI checks refer to these names.

| Capability | Covers (examples) |
|------------|-------------------|
| **`documents.read`** | List/get documents and cases |
| **`documents.write`** | Upload, PUT, bulk doc ops, assign/remove case, delete document |
| **`runs.execute`** | OCR, doc LLM, case LLM (`POST .../cases/{id}/runs`), bulk analyze, flow trigger from UI/API |
| **`config.read`** | Read tags, schemas, prompts, forms, flow definitions |
| **`config.write`** | CRUD on tags, schemas, prompts, forms; author/edit flow definitions (including assign-to-case node—see [`document_case_plan.md`](document_case_plan.md)) |
| **`org.admin`** | Members, billing, org settings, cascade case delete |

Flow **execution** in the worker runs as system; human/API **trigger** and **definition edit** still use `runs.execute` and `config.write` respectively.

### Persona → capabilities (v1)

The resolver derives effective capabilities from **`members[].role`** (tier is inclusive: higher roles include lower):

| Org role | Capabilities |
|----------|----------------|
| **viewer** | `documents.read`, `config.read` |
| **operator** | viewer + `documents.write`, `runs.execute` |
| **builder** | operator + `config.write` |
| **admin** | builder + `org.admin` |

**Tier order (for UI sugar only):** `viewer` < `operator` < `builder` < `admin`. Authorization logic should prefer **`member_has_capability`**, not ordinal role compare, except inside the resolver implementation.

### API surface (implementation)

- **Primary:** `require_capability("documents.write")` (or equivalent) on org routes.
- **Optional sugar:** `require_org_operator` implemented as “member has all capabilities operator tier grants” (delegates to the resolver).
- **Route-table regression test:** every org route declares **required capability(ies)**; the test fails if a route bypasses the resolver.
- **Frontend:** one hook/helper that loads the member’s org role (or cached capability set from an API) and gates buttons by capability name, aligned with backend.

### Later: permission groups without route churn

When we add org **permission groups** and named flags (Hyperscience-style), the resolver **unions** permissions from group membership into the same capability set (or a superset catalog). Built-in groups seeded from the four personas preserve behavior for migrated orgs. **`members[].role`** may become a display default or sync from a primary group; routes stay on **`require_capability`**.

Resource **scope** (flow-specific group access, tag/case restrictions) belongs in the resolver as an extra dimension after v1—not in the persona enum.

## Platform: `users.system_role`

- Replace today’s `users.role` (`admin` \| `user`) with optional **`system_role`**.
- **Migration:** `users.role == "admin"` → `system_role: "sysadmin"`; `users.role == "user"` → **unset** `system_role` (and remove legacy `role` when safe).
- **`is_system_admin`:** `user.get("system_role") == "sysadmin"`. Additional `system_role` values may be added later; each gets explicit checks (no generic “any system role” superuser unless intended).
- Sysadmin does **not** replace org membership; org routes still go through the **capability resolver** unless a route is account-level and sysadmin-only. (Define break-glass support access explicitly when implementing.)

## Organization: `members[].role` (persona matrix)

Human-readable summary of the same rules as the capability table above:

| Org role | Documents & cases | Runs (OCR, doc LLM, case LLM, bulk analyze, flow *trigger* from UI/API) | Config CRUD (tags, schemas, prompts, forms, flow *definitions*) | Org admin (members, billing, settings, cascade case delete) |
|----------|-------------------|---------------------------------------------------------------------------|------------------------------------------------------------------|----------------------------------------------------------------|
| **viewer** | Read/list/get | No | Read only | No |
| **operator** | Read + write (upload, PUT, bulk, assign/remove case, delete doc) | Yes | Read only | No |
| **builder** | Same as operator | Yes | Yes | No |
| **admin** | Same as builder | Yes | Yes | Yes |

**Notes:**

- **API tokens** inherit the user’s effective capabilities in that org (from membership role in v1); sysadmin only applies to account/platform routes the token user has.
- **Case LLM:** requires **`runs.execute`** (operator, builder, or admin).

## Migration & defaults

- **Users:** `role: admin` → `system_role: sysadmin`; drop `role: user` in favor of absent `system_role`.
- **Org members:** `members.role: admin` → **`admin`**; `members.role: user` → **`builder`** (preserves today’s full-member access).
- **New org members:** default **`operator`** unless an org **admin** sets viewer or builder.

## Enforcement

- Org routes: **`require_capability(...)`** via the shared resolver; avoid duplicating persona matrices in route files.
- Account/platform routes: sysadmin (or specific `system_role`) as today.
- Route-table regression test: org routes declare **capabilities**, not ad hoc role checks.
- **Phase 4:** MCP/agent tools use the same resolver (+ sysadmin on platform tools if any).

## Later extensions (not v1)

- Org permission groups, custom groups, LDAP/SAML auth-group mapping, flow/tag-scoped access—each extends the **resolver**, not per-route role logic.
- Built-in groups equivalent to the four personas for migration and small teams.
- Extra capabilities (reporting, KB admin) added to the catalog and group editor when needed.

## Phases (cross-reference)

| Phase | Permissions work |
|-------|-------------------|
| **3** | `system_role`, org member roles, **capability resolver** + route capability table on all REST (see [`document_case_plan.md`](document_case_plan.md) for assign-to-case flow node in the same phase) |
| **3+** | Permission groups / HS-style flags and scope (resolver backend only) |
| **4** | MCP/agent use resolver; optional webhook events |

## Open questions

1. Sysadmin break-glass: org API access without membership vs must be invited to org (and whether break-glass grants capabilities without org role).
2. KB: dedicated capability vs folded under `config.write` / `org.admin` only.
3. Automation identity: audit attribution for flow worker writes vs human operator.

## Deferred

Per-case ACL; access audit log for role changes and destructive actions.
