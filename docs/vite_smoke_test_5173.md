# Vite dev smoke test (localhost:5173)

Automated/browser pass on branch `vite`. Re-run after large router or auth changes.

**Prereqs:** FastAPI :8000 + Vite :5173, signed-in session.

- Full stack: `make dev`
- **Vite-only (Next off):** `DOCROUTER_DEV_NEXT=0 make dev` — use **http://localhost:5173** only

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
| `make build-vite` (`npm run typecheck` + `npm run build:vite`) | ✅ (CI: `.github/workflows/frontend-build.yml`) |
| `npm run preview:vite` + spot-check a route | manual (serves `dist-vite/`; API still needs FastAPI or proxy) |

Build notes (non-blocking): esbuild CSS nesting warnings from Formio styles; main chunk &gt;500 kB (code-split later).

## Known gaps

- **Org `*` catch-all:** rare nested URLs → `OrgPlaceholderPage` (see route manifest).
- **OAuth providers:** must allow 5173 callback URLs in IdP console (in addition to 3000).
- **Manual (browser):** optional `preview:vite` pass after build; chunk-size optimization deferred.
