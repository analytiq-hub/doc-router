# `src/app/` (Next.js App Router stubs)

The **Vite SPA** is the production UI. Implement screens under [`src/pages/`](../pages/) and register routes in [`src/router.tsx`](../router.tsx).

This tree exists only for optional **`DOCROUTER_DEV_NEXT=1`** local dev:

- **`**/page.tsx`** — one-line re-exports from `@/pages/...`
- **`layout.tsx`** — client auth gates (`AuthLayoutGuard`) and root shell
- **`oauth/flow-callback/route.ts`** — flow OAuth popup HTML (Next route handler)

Do not add new UI here; add `src/pages/` + `router.tsx` instead.
