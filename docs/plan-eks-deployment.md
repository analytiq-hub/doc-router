# Kubernetes deployment plan

## Goals

- Deploy doc-router to AWS EKS or Digital Ocean DOKS (our own clusters).
- Deploy doc-router to a customer's existing Kubernetes cluster (any provider).
- Docker images and Helm chart published to **`ghcr.io/analytiq-hub/`** on stable `vX.Y.Z` git tags — free, no rate limits, no registry credentials required to pull public packages.
- Terraform manages AWS infrastructure; a **Helm chart** is the single source of truth for Kubernetes packaging.
- The chart is published as an OCI artifact to `ghcr.io` alongside the images — one organization, one registry.
- Installed with `helm upgrade --install` directly — no GitOps controller required.

### Non-Goals
- Customers do not need to adopt our Git workflow; they pin a chart version and run scripts.
- No Argo CD, Flux, or proprietary deployment services required.
- GitHub Actions handles release builds only; dev deploys remain manual shell scripts.

---

## Implementation phases

### Phase 1 — Helm chart on Kind ✅ DONE

1. Wrote `deploy/charts/doc-router/`: two Deployments (frontend, backend with embedded worker), Ingress with `/fastapi` rewrite, ConfigMap, PDB.
2. Rewrote `deploy/scripts/deploy-kind.sh` to use `helm upgrade --install` with `values-kind.yaml`.
3. Kept `deploy/scripts/setup-kind.sh` as-is.
4. Deleted `deploy/kubernetes/` (old Kustomize manifests).

### Phase 2 — Harden the chart on Kind ✅ DONE

1. **Rolling upgrade strategy** — `maxUnavailable: 0` and `maxSurge: 1` on both Deployments.
2. **Migration Job hook** — Helm `pre-upgrade`/`pre-install` Job runs `migrate.py` before new pods roll out.
3. **Upgrade test on Kind** — bump `Chart.yaml` version, re-run `make deploy-kind`. Verified zero-downtime upgrades and clean rollback.

### Phase 3 — EKS ✅ DONE

Deployed to AWS EKS (`analytiq-test` cluster, `us-east-1`). Chart and images published to `ghcr.io/analytiq-hub/`.

### Phase 4 — DOKS ✅ DONE

Deployed to Digital Ocean Kubernetes (`doc-router-dev` cluster). Same chart, same `ghcr.io` images — no registry changes required.

---

## Registry design

Images and Helm chart are published to **ghcr.io/analytiq-hub/** and are public. Clusters pull anonymously — no image pull secret required.

The deploy scripts support three registry providers via `REGISTRY_PROVIDER` in the overlay `.env`:

| `REGISTRY_PROVIDER` | Registry | Auth |
|---|---|---|
| `github` (default) | ghcr.io | Optional — skip login for public packages |
| `aws` | AWS ECR | IAM via `aws ecr get-login-password` |
| `do` | Digital Ocean DOCR | `DOCR_TOKEN` |

`CLOUD_PROVIDER` is separate from `REGISTRY_PROVIDER` — it controls infrastructure decisions (e.g. unsetting static AWS key vars on EKS so `AWS_PROFILE` is used for tooling). They default to each other for backward compatibility.

---

## Repo structure

Everything lives in the **existing two repositories** — no new private ops repo needed:

| Repo | Visibility | Contains |
|---|---|---|
| `doc-router` | **Public / open source** | App source, Helm chart, all deploy scripts, env file templates |
| `analytiq-terraform` | **Private** | AWS IAM/S3 infra + EKS cluster |

Scripts contain no hardcoded secrets — all sensitive values come from gitignored env files. Env files (`.env`, `.env.eks-test`, `.env.do-dev`, `.env.customer-*`) live gitignored in `doc-router/` root.

---

## `doc-router` (public repo)

```
doc-router/
  packages/                 # app source — frontend, backend (unchanged)
  deploy/
    charts/
      doc-router/           # Helm chart — single source of truth for K8s packaging
        Chart.yaml
        values.yaml         # safe defaults only; no secrets, no real URLs or hostnames
        templates/
          frontend/
          backend/
          migration-job.yaml  # Helm pre-upgrade/pre-install hook
          configmap.yaml
          pdb.yaml
    scripts/
      build-push.sh           # build + push images to registry
      publish-chart.sh        # package + push OCI chart to ghcr.io
      k8s-deploy.sh           # idempotent install-or-upgrade on any cluster
      k8s-rollback.sh         # roll back to a previous Helm revision
      k8s-uninstall.sh        # remove the Helm release and namespace
      setup-doks.sh           # install cluster add-ons on DOKS (ingress-nginx, cert-manager)
      deploy-kind.sh          # local Kind deploy
      setup-kind.sh           # create local Kind cluster
  .env                        # gitignored — shared defaults (local dev values)
  .env.eks-test               # gitignored — EKS test overlay
  .env.do-dev                 # gitignored — DOKS dev overlay
  .env.customer-<name>        # gitignored — per-customer overlay
```

---

## Env overlay design

```
.env              # shared defaults (local dev values)
.env.eks-test     # overrides for the test EKS cluster
.env.do-dev       # overrides for the DO dev cluster
.env.eks-prod     # overrides for production
```

Scripts source both files; the overlay takes precedence. A single variable — `APP_HOST` — drives all URL configuration.

### `.env.eks-test` (EKS on AWS, ghcr.io registry)

| Var | Value |
|---|---|
| `CLOUD_PROVIDER` | `aws` |
| `REGISTRY_PROVIDER` | `github` |
| `CLUSTER_NAME` | `analytiq-test` |
| `REGION` | `us-east-1` |
| `CHART_REGISTRY` | `ghcr.io/analytiq-hub` |
| `CHART_REPO_URL` | `ghcr.io/analytiq-hub/doc-router` |
| `FRONTEND_IMAGE_REPO` | `ghcr.io/analytiq-hub/doc-router-frontend` |
| `BACKEND_IMAGE_REPO` | `ghcr.io/analytiq-hub/doc-router-backend` |
| `APP_HOST` | `test.docrouter.ai` |
| `GITHUB_USERNAME` | `andrei-radulescu-banu` |
| `GITHUB_TOKEN` | (for chart publishing only) |

### `.env.do-dev` (DOKS on Digital Ocean, ghcr.io registry)

| Var | Value |
|---|---|
| `CLOUD_PROVIDER` | `do` |
| `REGISTRY_PROVIDER` | `github` |
| `CLUSTER_NAME` | `doc-router-dev` |
| `CHART_REGISTRY` | `ghcr.io/analytiq-hub` |
| `CHART_REPO_URL` | `ghcr.io/analytiq-hub/doc-router` |
| `FRONTEND_IMAGE_REPO` | `ghcr.io/analytiq-hub/doc-router-frontend` |
| `BACKEND_IMAGE_REPO` | `ghcr.io/analytiq-hub/doc-router-backend` |
| `APP_HOST` | `dev.docrouter.ai` |
| `LETSENCRYPT_EMAIL` | `andrei@analytiqhub.com` |

---

## CI/CD pipeline

### Triggers

- **PRs to `main`** → `ci.yml` runs backend tests + frontend build (gate before merge).
- **Semver tags `vX.Y.Z*`** → `release.yml` runs tests first, then builds and pushes Docker images to ghcr.io.

### Image tagging

| Tag | `:latest` updated | Published |
|---|---|---|
| `v1.2.3` (stable) | Yes | `ghcr.io/analytiq-hub/` |
| `v1.2.3-rc.1` (RC) | No | `ghcr.io/analytiq-hub/` |

### Helm chart publishing

Manual — chart version is independent of app version:

```bash
./deploy/scripts/publish-chart.sh eks-test
```

---

## Deployment scripts

### `build-push.sh`

Builds and pushes both images. Supports ghcr.io (default), AWS ECR, and Digital Ocean DOCR.

```bash
./deploy/scripts/build-push.sh <overlay>
```

`IMAGE_TAG` defaults to the current git SHA. Stable releases are built by GitHub Actions.

### `publish-chart.sh`

Packages the Helm chart and pushes it as an OCI artifact to ghcr.io.

```bash
./deploy/scripts/publish-chart.sh <overlay>
```

Reads chart version from `Chart.yaml`. Must be re-run any time `Chart.yaml` version is bumped.

### `setup-doks.sh`

Installs cluster add-ons on a DOKS cluster (run once per cluster after provisioning):
- ingress-nginx (provisions a DO LoadBalancer)
- cert-manager with CRDs
- metrics-server
- `letsencrypt-prod` ClusterIssuer

```bash
doctl kubernetes cluster kubeconfig save <cluster-name>
./deploy/scripts/setup-doks.sh <overlay>
```

### `k8s-deploy.sh`

Idempotent install-or-upgrade. Safe to run on a fresh cluster or an existing deployment. Creates namespace, creates/updates `doc-router-secrets` Secret, deploys chart from ghcr.io, restarts pods to pick up refreshed secrets.

```bash
./deploy/scripts/k8s-deploy.sh <overlay>
```

### `k8s-rollback.sh`

```bash
./deploy/scripts/k8s-rollback.sh <overlay> [revision]
# revision defaults to 0 (= previous revision)
# Run "helm history doc-router -n doc-router" to list available revisions
```

### `k8s-uninstall.sh`

```bash
./deploy/scripts/k8s-uninstall.sh <overlay>
```

---

## Tag conventions

| Tag | Meaning | Published where |
|---|---|---|
| `v1.2.3` | Stable release | `ghcr.io/analytiq-hub/` (images + chart) |
| `v1.2.3-rc.1` | Release candidate | `ghcr.io/analytiq-hub/` |
| `abc1234` (git SHA) | Dev/test build | Local only (build-push.sh, not released) |

---

## Workflow summary

### First-time EKS setup

```bash
# In analytiq-terraform/applications/eks/test/
terraform init
terraform apply -target=module.tf_state
# Uncomment backend "s3", then:
terraform init   # answer "yes"
terraform apply

# Update kubeconfig
aws eks update-kubeconfig --name analytiq-test --region us-east-1 --profile analytiq-test-admin

# In doc-router/ — publish chart, deploy app
./deploy/scripts/publish-chart.sh eks-test
./deploy/scripts/k8s-deploy.sh eks-test
```

### First-time DOKS setup

```bash
# Create cluster in DO console, then:
doctl kubernetes cluster kubeconfig save doc-router-dev

# Install cluster add-ons
./deploy/scripts/setup-doks.sh do-dev

# Point DNS for APP_HOST → LoadBalancer IP
kubectl get svc -n ingress-nginx ingress-nginx-controller

# Deploy
./deploy/scripts/k8s-deploy.sh do-dev
```

### Stable release deploy

```bash
# 1. Tag the release — GitHub Actions builds and publishes images automatically
git tag v1.2.3 && git push --tags

# 2. Publish chart (if chart changed)
./deploy/scripts/publish-chart.sh eks-test

# 3. Deploy — chart already knows the image tag via appVersion; no IMAGE_TAG needed
./deploy/scripts/k8s-deploy.sh eks-test
# or:
./deploy/scripts/k8s-deploy.sh do-dev
```

### RC / dev deploy

```bash
# Deploy a specific RC tag (overrides chart's appVersion)
IMAGE_TAG=v1.2.3-rc.2 ./deploy/scripts/k8s-deploy.sh eks-test
```

### Chart-only update (config/template change, no image rebuild)

```bash
# Bump version in deploy/charts/doc-router/Chart.yaml, then:
./deploy/scripts/publish-chart.sh eks-test
./deploy/scripts/k8s-deploy.sh eks-test
```

### Kind (local dev)

```bash
./deploy/scripts/setup-kind.sh    # once
./deploy/scripts/deploy-kind.sh
```

### Onboarding a customer cluster

```bash
# 1. Create overlay
cp .env.eks-test .env.customer-acme
# Edit .env.customer-acme: APP_HOST, MONGODB_URI, etc.

# 2. Point kubectl at their cluster
kubectl config use-context <their-cluster-context>

# 3. Install (or upgrade — same script)
./deploy/scripts/k8s-deploy.sh customer-acme
```

### Teardown (EKS)

```bash
# In analytiq-terraform/applications/eks/test/
terraform destroy -target=module.eks_cluster   # preserves S3 state backend
# or: terraform destroy                        # destroys everything including state backend
```

---

## Helm chart design rules

1. **No hardcoded cluster-specific values** — everything cluster-specific comes from Helm values.
2. **Two Deployments** (frontend, backend) in one Helm release. Workers run embedded in the backend pod. `RollingUpdate` with `maxUnavailable: 0` on both.
3. **MongoDB is opt-in** — `mongodb.enabled: true/false`. When false, `mongodbUri` comes from the Secret.
4. **No `Namespace` resource in the chart** — the namespace is created by the install script or pre-exists.
5. **PodDisruptionBudget** included — `minAvailable: 1` on each Deployment.

---

## Upgrade stability

Both frontend and backend use `RollingUpdate`:

```yaml
strategy:
  type: RollingUpdate
  rollingUpdate:
    maxUnavailable: 0
    maxSurge: 1
```

All upgrade and install commands use `--atomic --timeout 10m`. On failure the operator sees the error immediately; rollback is `helm rollback` or `k8s-rollback.sh`.

`Chart.yaml` carries two version fields:

```yaml
version: 0.3.7       # chart version — bump when chart templates/config change
appVersion: v1.2.3   # application version = image tag
```

Deployment templates default the image tag to `appVersion` — no `--set image.*.tag` needed for release deploys.

---

## Database and migrations

A Helm hook Job (`pre-upgrade` / `pre-install`) runs the migration script before any pod replacement. Requirements:
- **Idempotent** — safe to re-run on partial failure.
- **Backward-compatible** — only add fields/indexes; never drop or rename what old code reads.

Rollback strategy: MongoDB migrations are forward-only. Rollback means restoring from a backup taken before the upgrade.

---

## MongoDB configuration options

The app connects to MongoDB via the `MONGODB_URI` environment variable. There are two supported configurations:

### Option A — MongoDB Atlas (cloud-managed)

Use an Atlas connection string. This is the simplest option for managed hosting.

Set in the overlay `.env` file:

```bash
MONGODB_URI="mongodb+srv://<user>:<password>@<cluster>.mongodb.net/"
```

No in-cluster MongoDB installation required.

### Option B — Self-hosted MongoDB via `mongodb-atlas-local` chart

Deploy MongoDB directly inside the Kubernetes cluster using the
[`mongodb-atlas-local`](https://github.com/analytiq-hub/analytiq-charts/pkgs/container/mongodb-atlas-local)
Helm chart from [analytiq-hub/charts](https://github.com/analytiq-hub/analytiq-charts).

This chart uses the [MongoDB Kubernetes Operator](https://github.com/mongodb/mongodb-kubernetes-operator)
to manage a `MongoDBCommunity` replica set with optional Atlas Search (vector search via the `mongot` sidecar, requires MongoDB 8.2+).

#### Prerequisites

```bash
# Install the MongoDB Kubernetes Operator (run once per cluster)
kubectl create namespace mongodb
helm repo add mongodb https://mongodb.github.io/helm-charts
helm install community-operator mongodb/community-operator --namespace mongodb
```

#### Install MongoDB

```bash
# Two-phase install: replica set first, then enable search
helm upgrade --install mongodb oci://ghcr.io/analytiq-hub/mongodb-atlas-local \
  --version 2.0.1 \
  --namespace mongodb \
  --set mongodb.adminPassword="<admin-password>" \
  --set mongodb.appUser.password="<app-password>" \
  --set mongodb.storage=20Gi \
  --set mongodb.members=3 \
  --set search.enabled=false   # enable after replica set is Ready

# Wait for all pods Ready
kubectl wait --for=condition=ready pod -l app=mongodb-mongodb-atlas-local \
  -n mongodb --timeout=300s

# Re-enable search
helm upgrade mongodb oci://ghcr.io/analytiq-hub/mongodb-atlas-local \
  --version 2.0.1 \
  --namespace mongodb \
  --reuse-values \
  --set search.enabled=true
```

#### Point doc-router at the in-cluster MongoDB

Set `MONGODB_URI` in the overlay `.env` to use the in-cluster service:

```bash
MONGODB_URI="mongodb://<appUser.username>:<appUser.password>@mongodb-mongodb-atlas-local-svc.mongodb.svc.cluster.local:27017/<database>?authSource=admin"
```

Replace `<appUser.username>`, `<appUser.password>`, and `<database>` with the values used during chart install (defaults: `appuser`, `appdb`).

#### Key chart values

| Value | Default | Notes |
|---|---|---|
| `mongodb.version` | `8.2.0` | MongoDB server version |
| `mongodb.members` | `3` | Replica set size |
| `mongodb.storage` | `20Gi` | PVC size per replica |
| `mongodb.storageClassName` | `""` | Leave empty to use cluster default |
| `mongodb.adminUsername` | `admin` | Admin user |
| `mongodb.adminPassword` | — | Required |
| `mongodb.appUser.username` | `appuser` | App database user |
| `mongodb.appUser.password` | — | Required |
| `mongodb.appUser.database` | `appdb` | App database name |
| `search.enabled` | `true` | Enable Atlas Search (mongot sidecar) |
| `search.resources.requests.cpu` | `250m` | CPU request for mongot container |
| `search.resources.requests.memory` | `250m` | Memory request for mongot container |
| `search.resources.limits.cpu` | `1000m` | CPU limit for mongot container |
| `search.resources.limits.memory` | `1000m` | Memory limit for mongot container |
| `tls.enabled` | `false` | TLS for in-cluster connections |

#### Storage sizing and expansion

Each replica gets its own PVC. At $0.08/GB-month (EBS gp3, `us-east-1`):

| Storage per replica | 1 replica | 3 replicas |
|---|---|---|
| 20 Gi | $1.60/mo | **$4.80/mo** |

PVCs can be expanded online without restarting pods — EBS gp3 supports live resize and the EKS default StorageClass has `allowVolumeExpansion: true`. To expand:

```bash
kubectl patch pvc <pvc-name> -n mongodb \
  -p '{"spec":{"resources":{"requests":{"storage":"60Gi"}}}}'
```

Note: Kubernetes StatefulSet `volumeClaimTemplates` are immutable, so changing `mongodb.storage` via `helm upgrade` will not resize existing PVCs. Patch them directly as above; the operator picks up the new size on the next pod restart.

PVCs cannot be shrunk — only expanded.

Full documentation: [analytiq-hub/analytiq-charts README](https://github.com/analytiq-hub/analytiq-charts)

---

## AWS-specific notes

### Manual steps in the AWS console

| Step | Where | Notes |
|---|---|---|
| Enable Bedrock model access | Bedrock → Model access | IAM permissions alone are not enough; models must be explicitly enabled per region. |
| SES production access | SES → Account dashboard | New accounts start in sandbox; request production access or verify sender + recipient addresses. |

### EBS CSI driver

Required for EBS-backed PersistentVolumes on EKS. Provisioned by Terraform via IRSA role. Not needed on DOKS (DO provides its own CSI driver).
