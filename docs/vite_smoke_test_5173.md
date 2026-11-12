# Vite smoke test (dev :5173 and compose :3000)

Manual regression on `main`. Re-run after large router, auth, deploy, or UI migration changes.

**Prereqs:** FastAPI :8000 + Vite :5173, signed-in session.

- **Default:** `make dev` → FastAPI + **http://localhost:5173** (Vite only)
- **Docker compose:** edge **http://localhost:3000** → Vite nginx frontend (see `deploy/compose/nginx.conf`). Rebuild **both** `frontend` and `backend` (`docker compose build --no-cache frontend backend`). SPA must use **`/fastapi`** (not `http://localhost:8000`) so session cookies work.

## Session / API

| Check | Result |
|-------|--------|
| `GET /fastapi/v0/account/auth/session` with cookies from 5173 | ✅ 200, user populated |
| Password login sets cookie on 5173 origin (`POST …/session` via proxy) | ✅ (existing flow) |
| OAuth from 5173 uses `app_origin` + callback on `5173/fastapi/…` | ✅ (see `frontend_origins.py`, `oauthStartUrl`) |

Register in Google/GitHub OAuth apps when using Vite:

- `http://localhost:5173/fastapi/v0/account/auth/google/callback`
- `http://localhost:5173/fastapi/v0/account/auth/github/callback`

## Routes (org `679c9a914cfaaaa3640811ed`, logged-in user)

| Path | Result |
|------|--------|
| `/` marketing home | ✅ |
| `/orgs/…/dashboard` | ✅ |
| `/orgs/…/cases` | ✅ list renders |
| `/orgs/…/forms/68efeda87266beaffa355b33` | ✅ Form Builder |
| `/orgs/…/docs` | ✅ |
| `/orgs/…/upload` | ✅ |
| `/orgs/…/flows` | ✅ |
| `/orgs/…/knowledge-bases` | ✅ |
| `/settings`, `/settings/account/users` | ✅ |
| `/feedback`, `/system` | ✅ |

## Production build

| Check | Result |
|-------|--------|
| `make build-vite` (`npm run typecheck` + `npm run build`) | ✅ (CI: `.github/workflows/frontend-build.yml`) |
| `npm run preview:vite` + spot-check a route | manual (serves `dist-vite/`; API still needs FastAPI or proxy) |

Build notes (non-blocking): esbuild CSS nesting warnings from Formio styles; main chunk &gt;500 kB (code-split later).

## Docker Compose (`deploy/compose`, edge :3000)

Compose smoke checklist (rebuild `frontend` + `backend` after image changes).

| Check | Result |
|-------|--------|
| Login + session cookie via `/fastapi` (not direct :8000) | ✅ |
| Org dashboard | ✅ |
| PDF document viewer + pdf.js worker (`.mjs` assets) | ✅ |
| `FRONTEND_PUBLIC_API_URL=/fastapi` baked in SPA | ✅ (see compose build args) |

**Gotchas:** stale GHCR backend → `404` on `/v0/account/auth/session`; rebuild backend. Wrong `PUBLIC_API_URL` in frontend build → login hits :8000 and cookies break on :3000.

## Known gaps

- **Org `*` catch-all:** rare nested URLs → `OrgPlaceholderPage` (see route manifest).
- **OAuth providers:** must allow 5173 callback URLs in IdP console (in addition to 3000 / compose edge).
- **Staging/K8s:** repeat compose checks after first deploy of new frontend image (Phase A sign-off for cloud is per environment).
- **Deferred:** `preview:vite` spot-check; chunk-size optimization.
