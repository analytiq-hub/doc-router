# Org permissions and roles (phase 3)

Platform-wide authorization for DocRouter tenants. Applies to **all org-scoped REST** (documents, cases, prompts, flows, etc.), not cases alone. Case-specific behavior (e.g. cascade delete, case LLM runs) follows the same org roles—see [`document_case_plan.md`](document_case_plan.md).

## Goal

Replace today’s coarse model (`users.role` admin/user + org `members.role` admin/user) with:

- Optional **`users.system_role`** for platform staff.
- Org member **`role`** personas: `viewer` | `operator` | `builder` | `admin`.

v1 uses **personas**, not a per-resource read/write matrix. Later: named permission groups, flow/tag scope, fine-grained flags (Hyperscience-style). **Per-case ACL** is deferred.

## Two layers

Use different field names so “role” is not overloaded:

| Layer | Where | Field | v1 values |
|-------|--------|--------|-----------|
| **Platform** | `users` document | **`system_role`** (optional) | `sysadmin` — omit field when the user has no platform role |
| **Organization** | `organizations.members[]` | **`role`** (org member role) | `viewer` \| `operator` \| `builder` \| `admin` |

**Why two layers:** Platform staff (sysadmin) can manage cross-org account APIs; org roles govern tenant data and config. Most users have **only** org roles; sysadmin is rare. Future platform roles (support, billing ops, etc.) extend **`system_role`** without changing org enums.

**Terminology in UI/docs:** **“system role”** vs **“org role”** (or “member role”)—never bare “role” without context.

## Platform: `users.system_role`

- Replace today’s `users.role` (`admin` \| `user`) with optional **`system_role`**.
- **Migration:** `users.role == "admin"` → `system_role: "sysadmin"`; `users.role == "user"` → **unset** `system_role` (and remove legacy `role` when safe).
- **`is_system_admin`:** `user.get("system_role") == "sysadmin"`. Additional `system_role` values may be added later; each gets explicit checks (no generic “any system role” superuser unless intended).
- Sysadmin does **not** replace org membership; org routes still require org **`role`** unless a route is account-level and sysadmin-only. (Define break-glass support access explicitly when implementing.)

## Organization: `members[].role`

| Org role | Documents & cases | Runs (OCR, doc LLM, case LLM, bulk analyze, flow *trigger* from UI/API) | Config CRUD (tags, schemas, prompts, forms, flow *definitions*) | Org admin (members, billing, settings, cascade case delete) |
|----------|-------------------|---------------------------------------------------------------------------|------------------------------------------------------------------|----------------------------------------------------------------|
| **viewer** | Read/list/get | No | Read only | No |
| **operator** | Read + write (upload, PUT, bulk, assign/remove case, delete doc) | Yes | Read only | No |
| **builder** | Same as operator | Yes | Yes | No |
| **admin** | Same as builder | Yes | Yes | Yes |

**Notes:**

- **Read config** is allowed for all org members (viewer and above).
- **Flow execution** in the worker runs as system; **builder** (or **admin**) required to **author/edit** flow definitions (including nodes that assign documents to cases—see [`document_case_plan.md`](document_case_plan.md) assign-to-case node).
- **API tokens** inherit the user’s **org role** in that org (from membership); sysadmin only applies to account/platform routes the token user has.
- **UI** disables actions above the member’s org role.

**Tier order (for helpers):** `viewer` < `operator` < `builder` < `admin`.

**Case LLM:** `POST .../cases/{id}/runs` requires **operator**, **builder**, or **admin** (not viewer).

## Migration & defaults

- **Users:** `role: admin` → `system_role: sysadmin`; drop `role: user` in favor of absent `system_role`.
- **Org members:** `members.role: admin` → **`admin`**; `members.role: user` → **`builder`** (preserves today’s full-member access).
- **New org members:** default **`operator`** unless an org **admin** sets viewer or builder.

## Enforcement

- Org routes: dependencies on minimum org role (`require_org_viewer`, `require_org_operator`, `require_org_builder`, `require_org_admin`).
- Account/platform routes: sysadmin (or specific `system_role`) as today.
- Route-table regression test so new org routes declare a minimum role.
- **Phase 4:** MCP/agent tools respect org role (+ sysadmin on platform tools if any).

## Later extensions (not v1)

- Multiple org permission groups per user, LDAP sync, flow/tag-scoped access, extra capabilities (reporting, KB admin as its own scope vs builder-only).
- Org **`role`** remains the default template for small teams.

## Phases (cross-reference)

| Phase | Permissions work |
|-------|-------------------|
| **3** | `system_role` + org member roles on all REST (see [`document_case_plan.md`](document_case_plan.md) for assign-to-case flow node in the same phase) |
| **4** | MCP/agent respect org role; optional webhook events |

## Open questions

1. Sysadmin break-glass: org API access without membership vs must be invited to org.
2. KB: dedicated permission vs folded under builder **admin** only.
3. Automation identity: audit attribution for flow worker writes vs human operator.

## Deferred

Per-case ACL; access audit log for role changes and destructive actions.
