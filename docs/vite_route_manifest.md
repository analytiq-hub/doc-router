# Vite SPA route manifest

Tracks SPA route coverage in `src/router.tsx` (page components under `src/pages/**`).  
**Last updated:** Phase E — branch `vite`, Next App Router tree removed.

## Legend

| Status | Meaning |
|--------|---------|
| ✅ | Wired in `router.tsx` |
| 🔶 | Partial (e.g. org `*` placeholder for rare nested URLs) |
| ❌ | Not in Vite router |

## Auth & marketing

| Path | Vite | Notes |
|-----------|------|-------|
| `/` | ✅ | Marketing home in `Layout` |
| `/auth/signin` | ✅ | |
| `/auth/complete` | ✅ | |
| `/auth/accept-invitation` | ✅ | |
| `/auth/verify-email` | ✅ | |
| `/verify-email` | ✅ | Legacy alias |
| `/dashboard` | ✅ | Org redirect |
| `/feedback` | ✅ | |
| `/admin/feedback` | ✅ | Sysadmin |
| `/system` | ✅ | About / system info |

## Organizations (`/orgs/:organizationId/…`)

| Segment | Status |
|---------|--------|
| `dashboard` | ✅ |
| `docs`, `docs/:id` | ✅ |
| `upload`, `models` | ✅ |
| `cases`, `cases/:caseId`, `…/edit` | ✅ |
| `tags`, `tags/:tagId` | ✅ |
| `schemas`, `schemas/:schemaRevId`, `schemas/by-id/:schemaId` | ✅ |
| `prompts`, `prompts/:promptRevId`, `prompts/by-id/:promptId` | ✅ |
| `forms`, `forms/:formId`, `forms/by-id/:formId` | ✅ |
| `knowledge-bases` | ✅ |
| `flows`, `flows/:flowId` | ✅ |
| Other nested URLs | 🔶 | `OrgPlaceholderPage` |

## Settings (`/settings/…`)

All listed `src/pages/settings/**` routes are ✅ (including `account/development/**`).

| `/oauth/flow-callback` | ✅ | Flow credential OAuth popup (`BroadcastChannel`) |

## Maintenance

When adding a page, create it under `src/pages/`, register the path in `router.tsx` (or lazy org/settings modules), and update this file.
