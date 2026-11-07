# Doc Router frontend (Vite SPA)

React 18 + TypeScript UI for Smart Document Router. **Vite** dev server on port **5173**; production build → `dist-vite/` served by nginx in Docker/Helm.

## Getting started

From this directory (repo root `make setup` installs deps):

```bash
npm run dev
```

Or from repo root: `make dev` (FastAPI :8000 + Vite :5173).

- App: http://localhost:5173  
- API proxy: `/fastapi` → backend (see `vite.config.ts`)

## Scripts

| Script | Purpose |
|--------|---------|
| `npm run dev` | Vite dev server |
| `npm run build` | Production build (`dist-vite/`) |
| `npm run preview` | Preview production build |
| `npm run typecheck` | `tsc --noEmit` |
| `npm run lint` | ESLint (flat config) |

Routes live in `src/router.tsx` with page components under `src/pages/`. Public env: `VITE_*` via `src/config/publicEnv.ts`.
