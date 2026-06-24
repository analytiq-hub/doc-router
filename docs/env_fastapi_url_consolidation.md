# Plan: Consolidate FastAPI URL Environment Variables

## Problem

`NEXT_PUBLIC_FASTAPI_FRONTEND_URL` is the single `.env` variable operators set to point at the FastAPI server. The name is a Next.js build-time artifact (`NEXT_PUBLIC_*`) that has leaked into operator-facing config. It is also never passed to the Python backend, so `credential_runtime.py` — which builds OAuth `redirect_uri` — falls back to the hardcoded default `http://127.0.0.1:8000` because `PUBLIC_API_URL` is never injected into the backend/worker runtime. This produces redirect URIs that OAuth providers reject in production.

## Approach

Rename `NEXT_PUBLIC_FASTAPI_FRONTEND_URL` → `PUBLIC_API_URL` as the single operator-facing variable. A one-line bridge in `next.config.mjs` maps `PUBLIC_API_URL` → `NEXT_PUBLIC_FASTAPI_FRONTEND_URL` at build time, so no frontend TypeScript code changes. Pass `PUBLIC_API_URL` to backend and worker containers so `credential_runtime.py` picks it up.

## Semantic contract

`PUBLIC_API_URL` must be a full absolute URL in all contexts (e.g. `http://localhost:8000` for local dev, `https://app.docrouter.ai/fastapi` for production). The relative path `/fastapi` must not be used in the backend env — the backend uses the value verbatim in OAuth `redirect_uri`, and a relative path there silently produces broken URIs.

`FASTAPI_BACKEND_URL` (Next.js server-side → backend, always an internal cluster address) and `FASTAPI_ROOT_PATH` (ASGI strip-prefix) are unchanged.

## Files to Change

### 1. `.env` (and `.env.example.local`, `.env.example.mongodb`, `.env.example.aws_lightsail`)

```bash
# Before
NEXT_PUBLIC_FASTAPI_FRONTEND_URL="http://localhost:8000"

# After
PUBLIC_API_URL="http://localhost:8000"
```

For `.env.example.mongodb` and `.env.example.aws_lightsail`, the value is `https://<mydomain>/fastapi`.

### 2. `packages/typescript/frontend/next.config.mjs`

Add an `env` block that maps `PUBLIC_API_URL` to the Next.js-required name. This is the single bridge that makes the rename transparent to all Next.js build contexts (local dev, CI, Docker):

```js
const nextConfig = {
  env: {
    NEXT_PUBLIC_FASTAPI_FRONTEND_URL: process.env.PUBLIC_API_URL || '/fastapi',
  },
  // ... existing config
};
```

With this in place, any build that sets `PUBLIC_API_URL` in the environment will automatically have the correct value baked into the JS bundle. No changes to `NEXT_PUBLIC_FASTAPI_FRONTEND_URL` references in TypeScript.

### 3. `deploy/shared/docker/Dockerfile`

Rename the build arg to match:

```dockerfile
# Before
ARG NEXT_PUBLIC_FASTAPI_FRONTEND_URL=/fastapi
ENV NEXT_PUBLIC_FASTAPI_FRONTEND_URL=${NEXT_PUBLIC_FASTAPI_FRONTEND_URL}

# After
ARG PUBLIC_API_URL=/fastapi
ENV PUBLIC_API_URL=${PUBLIC_API_URL}
```

The `next.config.mjs` bridge (item 2) handles the mapping; no `ENV NEXT_PUBLIC_FASTAPI_FRONTEND_URL` line needed in the Dockerfile.

### 4. `deploy/compose/docker-compose.yml`

Rename the frontend build arg and add `PUBLIC_API_URL` to the backend and worker environment blocks:

```yaml
# frontend build args — before
args:
  - NEXT_PUBLIC_FASTAPI_FRONTEND_URL=${NEXT_PUBLIC_FASTAPI_FRONTEND_URL:-/fastapi}

# frontend build args — after
args:
  - PUBLIC_API_URL=${PUBLIC_API_URL:-/fastapi}

# backend and worker environment — add
- PUBLIC_API_URL=${PUBLIC_API_URL:-http://localhost:8000}
```

Note the intentional difference in defaults: `/fastapi` is a safe same-origin relative path for the frontend build; the backend requires an absolute URL.

### 5. `deploy/compose/docker-compose.embedded.yml`

Same changes as `docker-compose.yml`.

### 6. `makefile`

Rename the variable on line 11 and in the `dockerhub-build-frontend` target (lines 300–304):

```makefile
# Before
NEXT_PUBLIC_FASTAPI_FRONTEND_URL ?= http://localhost:8000
# ...
@echo "Using NEXT_PUBLIC_FASTAPI_FRONTEND_URL=$(NEXT_PUBLIC_FASTAPI_FRONTEND_URL)"
@echo "Note: ... Override with: make dockerhub-build-frontend NEXT_PUBLIC_FASTAPI_FRONTEND_URL=your-url"
--build-arg NEXT_PUBLIC_FASTAPI_FRONTEND_URL=$(NEXT_PUBLIC_FASTAPI_FRONTEND_URL)

# After
PUBLIC_API_URL ?= http://localhost:8000
# ...
@echo "Using PUBLIC_API_URL=$(PUBLIC_API_URL)"
@echo "Note: ... Override with: make dockerhub-build-frontend PUBLIC_API_URL=your-url"
--build-arg PUBLIC_API_URL=$(PUBLIC_API_URL)
```

### 7. `deploy/scripts/build-push.sh`

Add the build arg (currently missing — the Dockerfile default `/fastapi` is baked in). Align with `k8s-deploy.sh` by deriving from `FASTAPI_ROOT_PATH` so the path prefix stays consistent if it ever changes:

```bash
--build-arg PUBLIC_API_URL="https://$APP_HOST${FASTAPI_ROOT_PATH:-/fastapi}" \
```

### 8. `deploy/scripts/k8s-deploy.sh`

Add alongside the existing `--set config.nextauthUrl`:

```bash
--set config.publicApiUrl="https://$APP_HOST${FASTAPI_ROOT_PATH:-/fastapi}" \
```

### 9. `deploy/scripts/deploy-kind.sh`

Add the build arg and the Helm set alongside the existing `--build-arg NODE_ENV=production`:

```bash
--build-arg PUBLIC_API_URL="http://localhost/fastapi" \
```

And pass to Helm (matching `k8s-deploy.sh` pattern):

```bash
--set config.publicApiUrl="http://localhost/fastapi" \
```

### 10. `deploy/scripts/values-kind.yaml`

Add `publicApiUrl` under `config`:

```yaml
config:
  environment: dev
  nextauthUrl: "http://localhost"
  publicApiUrl: "http://localhost/fastapi"
```

### 11. `deploy/charts/doc-router/templates/configmap.yaml`

```yaml
data:
  PUBLIC_API_URL: {{ .Values.config.publicApiUrl | quote }}
  FASTAPI_ROOT_PATH: {{ .Values.config.fastapiRootPath | quote }}
  FASTAPI_BACKEND_URL: {{ printf "http://backend.%s.svc.cluster.local:8000" .Release.Namespace | quote }}
  # ... existing entries
```

### 12. `deploy/charts/doc-router/values.yaml`

```yaml
config:
  publicApiUrl: ""            # required: set by k8s-deploy.sh or override in values overlay
  fastapiRootPath: "/fastapi" # must match ingress path prefix
```

Consider adding a Helm `required` guard in the configmap template to catch empty values at `helm install` time:

```yaml
PUBLIC_API_URL: {{ required "config.publicApiUrl is required" .Values.config.publicApiUrl | quote }}
```

### 13. `.github/workflows/frontend-build.yml`

Rename the env var. The `next.config.mjs` bridge (item 2) handles the mapping to `NEXT_PUBLIC_FASTAPI_FRONTEND_URL`:

```yaml
# Before
NEXT_PUBLIC_FASTAPI_FRONTEND_URL: 'http://localhost:8000'

# After
PUBLIC_API_URL: 'http://localhost:8000'
```

### 14. `packages/python/analytiq_data/flows/credential_runtime.py`

Drop the unused aliases and rename the internal symbol:

```python
# Before
_FLOW_OAUTH_PUBLIC_ORIGIN = (
    os.getenv("FLOW_OAUTH_PUBLIC_ORIGIN")
    or os.getenv("PUBLIC_API_URL")
    or os.getenv("DOCROUTER_API_PUBLIC_ORIGIN")
    or "http://127.0.0.1:8000"
)

# After
_PUBLIC_API_URL = os.getenv("PUBLIC_API_URL", "http://127.0.0.1:8000")
```

Update all references to `_FLOW_OAUTH_PUBLIC_ORIGIN` within the file to `_PUBLIC_API_URL`, and update the `_prefer_localhost_loopback_for_oauth_origin` docstring.

### 15. `packages/python/tests/flows/test_flow_credential_runtime.py`

Three patch targets reference the old symbol name and must be updated:

```python
# Before (three occurrences)
"analytiq_data.flows.credential_runtime._FLOW_OAUTH_PUBLIC_ORIGIN"

# After
"analytiq_data.flows.credential_runtime._PUBLIC_API_URL"
```

### 16. `docs/INSTALL.dockerhub.md`

Update the example command (line ~158):

```bash
# Before
make dockerhub-build NEXT_PUBLIC_FASTAPI_FRONTEND_URL=http://backend:8000

# After
make dockerhub-build PUBLIC_API_URL=https://<mydomain>/fastapi
```

### 17. `docs/env.md`

- Replace the `NEXT_PUBLIC_FASTAPI_FRONTEND_URL` entry with `PUBLIC_API_URL`; note it is mapped to `NEXT_PUBLIC_FASTAPI_FRONTEND_URL` at build time via `next.config.mjs`
- Fix the Docker guidance that incorrectly suggests `http://backend:8000` as the value — it should be `https://<domain>/fastapi` or `/fastapi` for same-origin compose
- Update all example `.env` blocks

### 18. `deploy/README.md`

Fix the stale claim that `NEXT_PUBLIC_FASTAPI_FRONTEND_URL` is "derived automatically from `APP_HOST`" — it is now set explicitly by `k8s-deploy.sh` and `build-push.sh` as `PUBLIC_API_URL`.

## Migration Note

Operators upgrading an existing deployment must rename `NEXT_PUBLIC_FASTAPI_FRONTEND_URL` → `PUBLIC_API_URL` in their `.env` file. No Python-side code depends on the old name.

## Non-Goals

- No changes to frontend TypeScript code — it continues reading `process.env.NEXT_PUBLIC_FASTAPI_FRONTEND_URL`, which `next.config.mjs` populates from `PUBLIC_API_URL`.
- `FASTAPI_BACKEND_URL` is unchanged — always an internal address, only read by NextAuth server-side callbacks.
- `FASTAPI_ROOT_PATH` is unchanged — explicit ASGI strip-prefix, not derived from `PUBLIC_API_URL`.
- `DOCROUTER_API_URL` (MCP server / SDK) is a separate operator-facing variable for external clients; out of scope.
- `API_URL` in `tests-ui/` is test-only; out of scope.
