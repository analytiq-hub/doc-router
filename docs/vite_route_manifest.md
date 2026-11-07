# Vite SPA route manifest

Tracks parity between Next App Router (`src/app/**/page.tsx`) and Vite (`src/router.tsx`).  
**Last updated:** branch `vite`.

## Legend

| Status | Meaning |
|--------|---------|
| ✅ | Wired in `router.tsx` |
| 🔶 | Partial (e.g. org `*` placeholder for rare nested URLs) |
| ❌ | Not in Vite router |

## Auth & marketing

| Next path | Vite | Notes |
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

All listed `src/app/settings/**/page.tsx` routes are ✅ (including `account/development/**`).

## Maintenance

When adding a Next `page.tsx`, register the same path in `router.tsx` (or `orgPages.tsx` / `settingsPages.tsx`) and update this file.
