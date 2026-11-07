# Doc Router frontend: Next.js → Vite migration plan

This document outlines a phased approach to port `packages/typescript/frontend` from Next.js (App Router) to Vite, aligned with patterns used in **doc-orchestrator** (`vite.config.ts`, dev proxy to Python, SPA routing).

**Branch for experimentation:** `vite` (create PRs from this branch when implementation starts.)

**Route coverage:** see [`vite_route_manifest.md`](./vite_route_manifest.md).

**Status & full Next removal:** see [`vite_next_elimination_plan.md`](./vite_next_elimination_plan.md). **Phase A (ops): complete** — Vite `runner` in compose/release/Helm; smoke: [`vite_smoke_test_5173.md`](./vite_smoke_test_5173.md). **Next: Phase B** (packaging).

### Implemented on `vite` (backend-first, partial)

- FastAPI sets and clears the **`dr.api-token` httpOnly cookie** on login, OAuth completion, `POST/DELETE /v0/account/auth/session`.
- **`GET /v0/account/auth/session`** returns `{ session }` in the shape expected by `AppSession`.
- **`get_current_user`** accepts the session JWT from the **cookie** (browser) or **Bearer** (API clients).
- Feedback: **`POST /v0/feedback`**, **`GET /v0/admin/feedback`**, **`DELETE /v0/admin/feedback/{id}`** replace Next route handlers (removed from `src/app/api/...`).
- OAuth success redirects to **`return_to`** with the cookie set (no longer depends on `/auth/complete?token=` for happy path).
- **Browser API clients:** axios + `@docrouter/sdk` use **`withCredentials`**; Bearer is added only when **`AppSessionContext`** already has `apiAccessToken`, otherwise the **cookie** authenticates (matches doc-orchestrator “no token in JS” for the common path).
- **`/auth/complete`**: `?token=` optional; refreshes session after OAuth redirect when cookie is already set.
- **Vite spike (parallel to Next):** `index.html`, `vite.config.ts` (`/fastapi` → backend), `npm run dev:vite` on port **5173**, `npm run build:vite` → **`dist-vite/`**. CSS: **`main.tsx`** loads Tailwind prelude → **`formio-tailwind.ts`** → **`formio-custom.css`** → utilities → **`app-theme.css`**; **`formio.full.css`** via `index.html`. Pin **`cookie@1.1.1`** in npm overrides so React Router’s ESM build resolves `parse` (avoid accidental `cookie@2`).
- **`make dev` / `start-all.sh`:** starts FastAPI + Next (**3000**) + Vite (**5173**) together; **`DOCROUTER_DEV_VITE=0`** skips Vite.
- **Vite routes:** **`createBrowserRouter`** in **`src/router.tsx`**; **`/orgs/:id/dashboard`** renders shared **`Dashboard`** inside **`Layout`** via **`OrgLayout`**. Unmigrated org paths → placeholder.
- **Next shims (Vite only):** **`src/shims/next-link.tsx`** and **`next-navigation.ts`** aliased in **`vite.config.ts`** so shared components keep `next/link` and `next/navigation` imports.
- **Org routes in Vite:** hub lists + **detail/edit** (`cases/:id`, `tags/:id`, schema/prompt/form rev routes, `by-id` redirects), **`upload`**, **`models`**, flows editor.
- **Settings in Vite:** **`/settings/**`** inside **`SettingsAppLayout`**; **account/development/** subtree fully wired (AWS/Azure/GCP, worker, LLM manager + provider).
- **`/feedback`**, **`/admin/feedback`** (CSR auth/admin checks, FastAPI APIs).
- **`withRouteParams`** spreads resolved segments and passes **`params={Promise.resolve(...)}`** for Next typing; **`useRouteParams`** reads sync fields on Vite (never **`use(Promise)`** there). Pages that only call **`useParams()`** mount directly. **`next/dynamic`** shim for lazy chunks.
- **`RouterProviders`** must sit under **`RouterProvider`** (org context uses **`usePathname`**). **`FormioProvider`** only under **`OrgLayout`** (not settings/home).
- **`/dashboard`** uses shared **`useDashboardRedirect`** with Next. **`AppProviders`** mirrors root layout providers (minus SSR session). **`vite.config`** loads **`NEXT_PUBLIC_*`** from repo **`.env`**.

### Don't forget: OAuth callbacks (localhost:5173)

While both Next (**3000**) and Vite (**5173**) run in parallel, **Google and GitHub OAuth apps must also allow the 5173 callback URLs** (in addition to any 3000 URLs). Without this, social sign-in from the Vite app fails at the IdP redirect step.

- [ ] **Google Cloud Console** → OAuth client → Authorized redirect URIs:
  - `http://localhost:5173/fastapi/v0/account/auth/google/callback`
- [ ] **GitHub** → OAuth App → Authorization callback URL (add a second app or allow multiple callbacks if your IdP setup requires it):
  - `http://localhost:5173/fastapi/v0/account/auth/github/callback`

Backend start URLs already send **`app_origin=http://localhost:5173`** from Vite (`oauthStartUrl`, `frontend_origins.py`) so, after the callback, the user returns to the **5173** SPA (e.g. `/auth/complete` → dashboard). Details and smoke checks: [`vite_smoke_test_5173.md`](./vite_smoke_test_5173.md).

## Current state (inventory)

| Area | Notes |
|------|--------|
| **Routing** | App Router under `src/app/` — on the order of **50+ `page.tsx` files**, nested dynamic segments (`orgs/[organizationId]/…`). |
| **Layouts** | Nested `layout.tsx` under `settings/`, `orgs/`, etc. |
| **Next-specific APIs** | Broad use of `next/navigation`, `next/image`, etc. across **many** `src/` files (grep: `next/` imports). |
| **Route handlers** | ~~Next `src/app/api/…`~~ **removed** for session + feedback; use FastAPI routes above. |
| **Auth** | **Not NextAuth in code:** login/OAuth and browser session live in FastAPI. **SSR layouts** may still use `getAppServerSession` / **`appSessionFromApiToken`** in Node until migrated. |
| **Build / deploy** | `next.config.mjs`: standalone output, webpack tweaks, `rewrites` for `/fastapi` in dev, monorepo `file:` SDK alias. |
| **Middleware** | No `middleware.ts` in frontend (good — one less Next-only layer). |

## Target architecture

- **Vite** + **React 19** + **TypeScript**.
- **Client-side routing:** React Router v6/v7 or TanStack Router (pick one; doc-orchestrator’s simplicity favors React Router unless you need loaders/types).
- **Dev server:** Proxy API paths to FastAPI (mirror doc-orchestrator: e.g. `/fastapi` → `http://localhost:8000`, or unify on one prefix and document it).
- **Production:** Static `dist/` served by nginx/ingress; same-origin API as today or explicit `VITE_*` base URLs.
- **Remove:** `next`, `eslint-config-next`, App Router file conventions, `next build` / `next start`.

## Reference implementation

- **doc-orchestrator:** `packages/typescript/frontend/vite.config.ts` — `@/` alias, dev `proxy` for `/api`, Vitest block.
- **Doc Router:** Keep **Vitest** and existing tests; add Vite `test` config or reuse orchestrator-style `setupFiles`.

### Backend-first (mirror doc-orchestrator) — do **before** or **in parallel** with the Vite UI

**doc-orchestrator pattern** (see `../doc-orchestrator/packages/python/app/session.py` and `app/routes/account_auth.py`):

- Password login and OAuth callbacks **`Set-Cookie`** an **httpOnly** session JWT (same-origin; SPA never stores the secret in JS).
- **`GET /v0/account/auth/session`** returns the current user (`Depends(get_session_user)` from the cookie).
- **`POST /v0/account/auth/logout`** clears the cookie.

**doc-router today:**

- FastAPI already **mints** the session JWT on `POST /v0/account/auth/login` and OAuth completion, but the browser stores it via **`POST /api/auth/session`** on **Next**, which sets `dr.api-token`. The axios client then sends **`Authorization: Bearer`** from `getCachedSession()` — not orchestrator’s “cookie only” model.
- **`sessionFromApiToken`** in Next (`src/utils/sessionFromToken.ts`) hits **MongoDB from Node** to build `AppSession`; that belongs in FastAPI long-term.

**Recommended backend steps (in order):**

1. **Session cookie in FastAPI** — On login + OAuth success responses, call something equivalent to orchestrator’s `set_session_cookie` (new helper next to `packages/python/app/session_jwt.py`; reuse cookie name **`dr.api-token`** unless you coordinate a rename). Optionally keep returning `token` in JSON for backward compatibility during transition.
2. **Read session from cookie in `get_current_user`** — Extend `packages/python/app/auth.py` so the bearer token can come from the **Authorization header** **or** the **session cookie** when the header is absent (or force cookie-only for browser paths — pick one rule and document it).
3. **`GET /v0/account/auth/session`** — Return the same shape the UI needs (`AppSession`-compatible or a thin `SessionUser` + client maps). Replaces **`GET /api/auth/session`** and removes Node Mongo access.
4. **`POST /v0/account/auth/logout`** — Clear cookie (or reuse existing surface if present). Wire `signOutClient()` to this instead of Next.
5. **OAuth completion** — After cookies are set by FastAPI, `/auth/complete` can become a **static** page that only reads `return_to` and redirects (no `persistSessionToken`).
6. **Feedback routes** — Reimplement `src/app/api/feedback/*.ts` (Mongo `insertOne`) as **FastAPI** routes with `Depends(get_current_user)`; delete Next handlers.

Then the SPA (Next or Vite) only needs **`credentials: 'include'`** on fetch and/or your existing CSRF header story; align with orchestrator’s **`X-Requested-With`** if you adopt the same CSRF rule.

## Phased plan

### Phase 0 — Decision log (short)

- [ ] **Router:** React Router vs TanStack Router.
- [ ] **API prefix:** Keep `/fastapi` in the browser vs single `/api` with nginx stripping (must match FastAPI CORS and CSRF expectations).
- [ ] **Auth transport:** Prefer **httpOnly cookie + `GET …/session`** (orchestrator) vs **Bearer from client memory** (doc-router today); migration can support **both** briefly, then drop Bearer-from-`/api/auth/session`**.

### Phase 1 — Scaffold Vite without deleting Next (parallel run)

- [ ] Add `vite.config.ts`, `index.html` at package root, `src/main.tsx` entry.
- [ ] Move **global styles and providers** (MUI `ThemeRegistry`, etc.) into `main.tsx` + a root `<App />`.
- [ ] Configure path alias `@/` or preserve existing imports via `tsconfig` + Vite `resolve.alias`.
- [ ] Port **webpack-only** concerns from `next.config.mjs`: SDK alias (`@docrouter/sdk` → monorepo path), any PDF/React-Formio constraints → Vite `optimizeDeps` / `ssr.noExternal` if needed.
- [ ] **Scripts:** `vite`, `vite build`, `vite preview` alongside existing `next dev` until cutover.

### Phase 2 — Routing migration

- [ ] Map every App Router URL to a **route table** (flat list first, then code-split with `lazy()`).
- [ ] Replace nested `layout.tsx` with **route layout components** (e.g. `<SettingsLayout />` wrapping child routes).
- [ ] Replace `useParams`, `useRouter`, `usePathname`, `useSearchParams` from `next/navigation` with the chosen router’s hooks.
- [ ] Replace `next/link` with router `Link`.
- [ ] Handle **not found** and **redirects** (client-side `Navigate` or loader redirects).

### Phase 3 — Next.js-specific APIs

- [ ] **`next/image`:** Replace with `<img>` or a small wrapper; for optimized assets, use Vite asset imports or build-time URLs.
- [ ] **Metadata / `<head>`:** Use `react-helmet-async` or router head APIs if required for titles per route.
- [ ] **`next/dynamic`:** Use `React.lazy` + `Suspense`.
- [ ] **Server components:** None in Vite SPA — ensure any assumed server-only code is already client-safe or moved to FastAPI.

### Phase 4 — API routes and FastAPI

- [ ] For each **Next Route Handler**, document behavior and either:
  - **Implement on FastAPI** (preferred for single backend), or
  - **Temporary:** proxy from Vite dev server only (not a long-term substitute for production).
- [ ] Update **`src/utils/session.ts`** and callers to hit the **new session URL** (and cookies/CORS).
- [ ] Re-test **feedback** and **admin feedback** flows if those handlers move.

### Phase 5 — Environment and deployment

- [x] **`vite.config.ts`** defines `NEXT_PUBLIC_*` from repo `.env` for shared modules (no rename required yet).
- [x] **Docker frontend:** `runner` = **`dist-vite/`** + **`nginx-spa.conf`**; compose edge proxies to **frontend:80** (Vite SPA).
- [x] Wire compose/K8s to **Vite `runner`** (`runner-vite`); edge nginx → frontend:**80**. Set OAuth/`return_to` per environment (`NEXTAUTH_URL` on backend/worker).
- [ ] **Local Vite:** register **Google + GitHub** redirect URIs for **`http://localhost:5173`** (see [Don't forget: OAuth callbacks (localhost:5173)](#dont-forget-oauth-callbacks-localhost5173)).
- [ ] Replace `NEXT_PUBLIC_*` with **`VITE_*`** (optional cleanup).
- [ ] Remove **Next standalone** artifacts; align with doc-orchestrator’s static hosting pattern.
- [ ] **ESLint:** Replace `eslint-config-next` with `@eslint/js` + `typescript-eslint` + `eslint-plugin-react-hooks` (or flat config mirroring orchestrator).

### Phase 6 — Cutover and cleanup

- [ ] Delete `next.config.mjs`, App Router tree migration complete → remove `src/app/` structure or leave only non-Next assets if any.
- [ ] Remove `next` dependency; shrink `package.json` scripts.
- [ ] Full regression: auth, org switcher, flows editor, PDF viewer, uploads, settings.
- [ ] Update **CLAUDE.md** / README dev instructions.

## Risks and mitigations

| Risk | Mitigation |
|------|------------|
| **Auth + cookies + cross-origin** | Decide dev/prod origins early; mirror orchestrator’s `changeOrigin: false` style if backend validates `Origin`. |
| **Deep linking / refresh** | SPA requires server fallback to `index.html` for all app routes (nginx `try_files`). |
| **Large refactor surface** | Phase 1–2 behind feature branch; migrate **one vertical slice** (e.g. `/auth/signin` + dashboard) before moving everything. |
| **SDK and Formio** | Validate ESM/CJS boundaries under Vite after Phase 1 scaffold. |

## Suggested first vertical slice (spike)

1. Vite shell + React Router with **two routes**: `/` and `/auth/signin`.
2. Port **session fetch** to FastAPI (or temporary mock).
3. Prove **proxy + env** work end-to-end with FastAPI running.

Successful spike de-risks the rest of Phase 2–4.

## Estimated effort (order of magnitude)

- **Spike + Phase 1:** ~3–7 engineer-days.
- **Full port (routing + API migration + deploy + regression):** commonly **multiple weeks** depending on auth complexity and production hardening — proportional to **50+ routes** and **many** `next/*` touchpoints.

---

*Last updated: migration planning on branch `vite`.*
