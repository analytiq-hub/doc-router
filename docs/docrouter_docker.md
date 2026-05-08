# DocRouter Docker: current support and plan

This document summarizes what DocRouter already provides for Docker, how it compares to a single-command `docker run` workflow, and a concrete implementation plan—including embedded MongoDB using the **same image as backend CI**.

## Goal (user experience)

Rough parity with:

1. **Ephemeral / try-it**: one short command from a clean checkout, teardown removes containers (optional: discard DB data too).
2. **Persistent**: same stack with durable MongoDB data (and documented host paths or named volumes).

DocRouter is a **multi-service** app (Next.js frontend, FastAPI backend, nginx, migrations, MongoDB). A literal single-container `docker run` is possible only with a deliberately designed “fat” image (process supervisor + all services)—**not what we ship today**. The practical analogue to n8n’s one-liners is **`docker compose`** with predictable files, ports, and copy-paste commands (optionally backed by `-f`/`--env-file` and make targets).

## What we already support

### Images and Dockerfile

| Item | Location / detail |
|------|-------------------|
| Multi-stage build | `deploy/shared/docker/Dockerfile` — `runner` (Node 24, Next standalone on port 3000), `backend` (Python 3.12 slim, LibreOffice, uv-installed deps, port 8000) |
| Published tags (typical) | `ghcr.io/analytiq-hub/doc-router-frontend:${IMAGE_TAG}` and `doc-router-backend:${IMAGE_TAG}` (see repo `makefile` `REGISTRY` / `IMAGE_TAG`) |

### Compose: external MongoDB

- **File**: `deploy/compose/docker-compose.yml`
- **Services**: `migrate` (one-shot `migrate.py`), `backend` (uvicorn `:8000`), `frontend` (Next standalone), `nginx` (maps host **3000 → 80**).
- **MongoDB**: not included; **`MONGODB_URI`** defaults to `mongodb://YOUR_HOST_IP:27017`—you must supply a reachable server.

### Compose: embedded MongoDB (Atlas Local + mongot)

- **File**: `deploy/compose/docker-compose.embedded.yml`
- **MongoDB image**: `mongodb/mongodb-atlas-local:latest` — **same choice as CI** (`.github/workflows/backend-tests.yml`), including optional `MONGOT_LOG_FILE` / `RUNNER_LOG_FILE` to stdout.
- **Internal URI** (between app containers): `mongodb://mongodb:27017/?directConnection=true`
- **Host port**: `27018:27017` (Mongo listens on **localhost:27018** from the host).
- **Persistence**: named volumes `doc-router-local-mongodb` and `doc-router-local-mongodb-configdb`.
- **Ordering**: `migrate` `depends_on` Mongo with `service_healthy`; healthcheck uses `mongosh` + writable primary check.

### Make targets (build + run)

From repo root `makefile`:

- **`make deploy-compose`** — merges root `.env` with `.env.compose` (see below) into `deploy/compose/.env`, then `docker compose -f docker-compose.yml ... up -d --build`.
- **`make deploy-compose-embedded`** — same with `.env.compose.embedded` and `docker-compose.embedded.yml`.
- **`make down-compose`** / **`make down-compose-clean`** — stop stacks; **clean** removes volumes (and attempts removal of a legacy volume name).

**Note:** `.env.compose` and `.env.compose.embedded` are **gitignored**; users are expected to maintain them locally (overrides for compose-specific variables).

### Documentation (current gaps)

- `docs/INSTALL.docker.md` refers to `--profile with-mongodb` / `default`, but **no such profiles exist** in the current compose files (only separate YAML files).
- `docs/INSTALL.dockerhub.md` references **`docker-compose.dockerhub.embedded.yml`**, which **does not exist** under `deploy/compose/` (only `docker-compose.yml` and `docker-compose.embedded.yml`). Treat that as **doc drift** to fix separately.

### Known intentional omissions today

- **Background worker** (`packages/python/worker/worker.py`) is **not** part of compose; queue-heavy features may require running the worker separately or extending compose.

---

## Implementation plan

### Phase 1 — Documented “single command” flows (Compose as the `docker run` equivalent)

Add a prominent **Quickstart** section (this file plus a short pointer from `CLAUDE.md` or `INSTALL.docker.md`) with copy-paste blocks.

**Embedded Mongo (persistent Mongo volumes by default)**

```bash
cd /path/to/doc-router
cp .env.example .env   # then edit secrets and keys
# Create deploy/compose overrides if needed: .env.compose.embedded (gitignored)
make deploy-compose-embedded
```

Access: frontend **http://localhost:3000**, API **http://localhost:8000/docs**, Mongo from host **`mongodb://localhost:27018/?directConnection=true`**.

**Embedded Mongo — ephemeral DB (delete data on teardown)**

Standard compose down **without** `-v` keeps volumes; for n8n-like “throwaway DB”, document:

```bash
cd deploy/compose
docker compose -f docker-compose.embedded.yml down -v
```

Optionally add a **`make down-compose-embedded-clean`** (or enhance `down-compose-clean`) that **only** targets `docker-compose.embedded.yml` with `-v` so users do not accidentally wipe external-DB volumes from the non-embedded file.

**External Mongo (no embedded container)**

```bash
export MONGODB_URI='mongodb://host:27017/?directConnection=true'
make deploy-compose
```

### Phase 2 — Optional: pre-built images without `--build`

For users who only want to **pull** (closer to `docker run` speed):

- Document `IMAGE_TAG=... docker compose -f docker-compose.embedded.yml pull && ... up -d` **without** `--build`, when tags exist in GHCR.
- Align any Docker Hub / GHCR quickstart docs with **actual** compose filenames.

### Phase 3 — Optional: root-level `compose.yaml` (ergonomics)

Add a **thin** `compose.yaml` at repo root that `include:`s `deploy/compose/docker-compose.embedded.yml` (or uses `extends` / duplicate `include` per Compose v2 capabilities), so users can run:

```bash
docker compose up -d
```

from the repository root without `cd deploy/compose`. Validate with the Compose version you support in CI/docs.

### Phase 4 — Only if product requires true `docker run` (single container)

Treat as a **separate deliverable**:

- New image with a supervisor (e.g. s6, supervisord) running `mongod` (or embedded sidecar—harder with Atlas Local), `uvicorn`, `node`, `nginx`, and migration on start.
- Tradeoffs: image size, signal handling, healthchecks, upgrade path, and duplication with compose.

**Recommendation:** defer unless there is a strong distribution requirement; compose-based quickstart covers most “n8n-style” expectations for a multi-tier app.

### Phase 5 — CI / local parity checks

- Keep **one canonical Mongo image line**: `mongodb/mongodb-atlas-local:latest` in both `.github/workflows/backend-tests.yml` and `docker-compose.embedded.yml` (document that changing one should change the other).
- Optionally document a one-liner to run **pytest** against the embedded compose Mongo on **27018** using `MONGODB_URI=mongodb://localhost:27018/?directConnection=true` for developers who do not run Mongo on the host.

---

## Success criteria

- A new contributor can run DocRouter with **one documented command** (via `make` or `docker compose`) using **embedded MongoDB** with the **same image as unit tests**.
- Clear distinction between **persistent** (default named volumes) and **ephemeral** (`down -v`) workflows.
- Worker and doc drift (profiles, missing dockerhub compose file) are either **fixed** or **explicitly called out** in user-facing install docs.

---

## References (in-repo)

| Topic | Path |
|------|------|
| Embedded stack | `deploy/compose/docker-compose.embedded.yml` |
| External-DB stack | `deploy/compose/docker-compose.yml` |
| Image build | `deploy/shared/docker/Dockerfile` |
| Compose how-to | `deploy/shared/docs/compose.md` |
| CI Mongo service | `.github/workflows/backend-tests.yml` |
| Deploy make targets | `makefile` (`deploy-compose`, `deploy-compose-embedded`, `down-compose*`) |
