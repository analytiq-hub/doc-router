# EKS deployment plan

## Goals

- Deploy doc-router to AWS EKS (our own cluster, one or more namespaces).
- Deploy doc-router to a customer's existing Kubernetes cluster (any provider).
- Docker images and Helm chart published to **`ghcr.io/analytiq-hub/`** on stable `vX.Y.Z` git tags — free, no rate limits, no registry credentials required to pull public packages.
- Dev/test builds pushed to ECR with git SHA tags; never published publicly.
- Terraform manages all AWS infrastructure; a **Helm chart** is the single source of truth for Kubernetes packaging.
- The chart is published as an OCI artifact to `ghcr.io` alongside the images — one organization, one set of credentials.
- Installed with `helm upgrade --install` directly — no GitOps controller required.

### Non-Goals
- Customers do not need to adopt our Git workflow; they pin a chart version and run scripts.
- No Argo CD, Flux, or proprietary deployment services required.
- GitHub Actions handles release builds only; dev deploys remain manual shell scripts.

---

## Implementation phases

Build incrementally. Kind already works — migrate it to the Helm chart first, then add EKS on top of a proven chart.

### Phase 1 — Helm chart on Kind ✅ DONE

1. Wrote `deploy/charts/doc-router/`: two Deployments (frontend, backend with embedded worker), MongoDB StatefulSet, Ingress with `/fastapi` rewrite, ConfigMap, PDB.
2. Rewrote `deploy/scripts/deploy-kind.sh` to use `helm upgrade --install` with `values-kind.yaml`.
3. Kept `deploy/scripts/setup-kind.sh` as-is.
4. Deleted `deploy/kubernetes/` (old Kustomize manifests).

Kind works exactly as before but driven by Helm. Kustomize is gone.

### Phase 2 — Harden the chart on Kind ✅ DONE

Goal: prove the chart supports zero-downtime upgrades before adding EKS complexity.

1. **Rolling upgrade strategy** ✅ — `maxUnavailable: 0` and `maxSurge: 1` on both Deployments. Upgrades never take a pod down before a replacement is ready.
2. **Migration Job hook** ✅ — Helm `pre-upgrade`/`pre-install` Job (`deploy/charts/doc-router/templates/migration-job.yaml`) runs `packages/python/migrate.py` before new pods roll out. Same script used by the `migrate` service added to all four docker-compose files (runs and completes before backend starts).
3. **Upgrade test on Kind** — bump `Chart.yaml` version, re-run `make deploy-kind`. Verify:
   - `helm history doc-router -n doc-router` shows two revisions.
   - No downtime: frontend stays reachable throughout the rollout.
   - `helm rollback doc-router 1 -n doc-router` restores the previous revision cleanly.

### Phase 3 — EKS

Goal: deploy the proven chart to AWS EKS using direct `helm upgrade --install` against the OCI chart in ECR.

#### 3a — EKS scripts (in `doc-router/deploy/scripts/`, public)

Add scripts to `deploy/scripts/`:

- **`build-push.sh`** — registry login, `docker build --target runner` (frontend) and `--target backend`, tag `<REPO>:<IMAGE_TAG>` + `:latest`, push both images. `IMAGE_TAG` defaults to current git SHA; set in env to override.
- **`publish-chart.sh`** — reads chart version from `Chart.yaml`, `helm package`, registry login, `helm push oci://CHART_REGISTRY` (helm appends chart name → ECR repo `CHART_REPO_URL`).
- **`k8s-deploy.sh`** — idempotent install-or-upgrade. Sources env overlay, creates namespace, creates/updates `doc-router-secrets` Secret, registry login, runs `helm upgrade --install oci://CHART_REPO_URL --version <from Chart.yaml>` with non-secret values via `--set`, `--atomic --timeout 10m`, then restarts deployments to pick up refreshed secrets.
- **`k8s-rollback.sh`** — runs `helm rollback doc-router <revision> -n doc-router --wait`.
- **`k8s-uninstall.sh`** — removes the Helm release and namespace from the cluster.

All scripts source a gitignored `.env` + overlay (e.g. `.env.eks`) for secrets and cluster-specific values. They contain no hardcoded sensitive values and are safe to commit publicly.

#### 3b — EKS Terraform (in `analytiq-terraform/applications/eks/`)

Add a new application directory to the existing `analytiq-terraform` repo. The existing `applications/docrouter/` (IAM user/role + S3) is **unchanged** — EKS is additive.

```
analytiq-terraform/applications/eks/
  main.tf       # VPC + EKS cluster + ECR repos + Helm add-ons
  providers.tf  # aws + helm providers; s3 backend commented out until first apply
  var.tf        # region, cluster_name, vpc_cidr, environment, letsencrypt_email
  outputs.tf    # cluster_name, frontend_repo_url, backend_repo_url, chart_repo_url
```

`main.tf` provisions:
- **VPC** — `/16` CIDR, 2 public subnets (NAT + NLB) + 2 private subnets (nodes) across 2 AZs, one NAT gateway.
- **EKS cluster** — nodes in private subnets, managed node group (`t3.medium`/`t3.large`, min/desired/max = 2/2/5), OIDC enabled.
- **ECR repos** — `doc-router-frontend`, `doc-router-backend`, `doc-router-chart` (OCI artifacts).
- **Helm releases** — ingress-nginx, cert-manager (`crds.enabled=true`), aws-ebs-csi-driver, metrics-server.
- **ClusterIssuer** — applied via `null_resource` local-exec after cert-manager is ready.

#### 3c — OCI chart publishing

`publish-chart.sh` packages the chart and pushes it as an OCI artifact to ECR:
```bash
helm package deploy/charts/doc-router --version <semver>
helm push doc-router-<semver>.tgz oci://<ECR_REGISTRY>/doc-router-chart
```

The chart itself needs no changes for EKS — only values differ (`gp3` storage class, TLS enabled, ECR image repos, real hostnames).

**cert-manager is EKS-only.** Kind uses `helm upgrade --install` directly with TLS disabled.

---

## Repo structure

Everything lives in the **existing two repositories** — no new private ops repo needed:

| Repo | Visibility | Contains |
|---|---|---|
| `doc-router` | **Public / open source** | App source, Helm chart, all deploy scripts (build/publish/install/upgrade/rollback), env file templates |
| `analytiq-terraform` | **Private** | Existing IAM/S3 infra + new `applications/eks/` for EKS cluster + ECR |

Scripts contain no hardcoded secrets — all sensitive values come from gitignored env files. Env files (`.env`, `.env.eks`, `.env.customer-*`) live gitignored in `doc-router/` root alongside the existing Kind `.env`.

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
            deployment.yaml
            service.yaml
            ingress.yaml    # routes / → frontend, /fastapi → backend (with rewrite)
          backend/
            deployment.yaml
            service.yaml
            hpa.yaml
          mongodb/
            statefulset.yaml  # conditional: rendered only when mongodb.enabled=true
            service.yaml
          migration-job.yaml  # Helm pre-upgrade/pre-install hook
          configmap.yaml
          pdb.yaml
    scripts/
      build-push.sh           # build + push images to registry (ECR or DOCR)
      publish-chart.sh        # package + push OCI chart to registry
      k8s-deploy.sh           # idempotent install-or-upgrade on any cluster
      k8s-rollback.sh         # roll back to a previous Helm revision
      k8s-uninstall.sh        # remove the Helm release and namespace
      deploy-kind.sh          # local Kind deploy (helm upgrade --install)
      setup-kind.sh           # create local Kind cluster
      values-kind.yaml        # committed Kind-specific overrides (no secrets)
  .env                        # gitignored — shared defaults (Kind + EKS)
  .env.eks                    # gitignored — EKS overlay (ECR URLs, cluster name, etc.)
  .env.customer-<name>        # gitignored — per-customer overlay
```

### `deploy/charts/doc-router/values.yaml` (defaults, no secrets)

```yaml
image:
  frontend:
    repository: ghcr.io/analytiq-hub/doc-router-frontend
    tag: ""            # empty = use Chart.appVersion; override for dev/SHA builds
    pullPolicy: IfNotPresent
  backend:
    repository: ghcr.io/analytiq-hub/doc-router-backend
    tag: ""            # empty = use Chart.appVersion; override for dev/SHA builds
    pullPolicy: IfNotPresent
  # worker uses the same image as backend; pullPolicy follows backend

ingress:
  enabled: true
  className: nginx
  host: ""              # required; set per cluster
  tls: true             # set to false for Kind (no cert-manager on local dev)
  clusterIssuer: letsencrypt-prod   # ignored when tls=false

mongodb:
  enabled: true
  storageClassName: standard   # "" for Kind (uses default); gp3 for EKS
  storage: 10Gi

replicaCount:
  frontend: 2
  backend: 2
  worker: 1

resources:
  frontend:
    requests: { cpu: "100m", memory: "256Mi" }
    limits:   { cpu: "500m", memory: "512Mi" }
  backend:
    requests: { cpu: "250m", memory: "512Mi" }
    limits:   { cpu: "1000m", memory: "1Gi" }
  worker:
    requests: { cpu: "250m", memory: "512Mi" }
    limits:   { cpu: "500m", memory: "1Gi" }

# Non-secret config (rendered into ConfigMap by the chart)
config:
  appBucketName: ""
  region: ""
  environment: prod
  nextauthUrl: ""
  fastapiRootPath: "/fastapi"   # must match the ingress rewrite prefix

# Secrets are never in values.yaml.
# All scripts (deploy-kind.sh, k8s-install.sh) create the doc-router-secrets Secret
# directly via kubectl before calling helm upgrade --install. The chart reads secrets
# from that Secret via envFrom — they are never passed as Helm values.
```

### `deploy/scripts/values-kind.yaml` (committed Kind-specific overrides, no secrets)

```yaml
image:
  frontend:
    pullPolicy: Never   # images are kind load-ed, not pulled from a registry
  backend:
    pullPolicy: Never

ingress:
  host: localhost
  tls: false            # no cert-manager on Kind

mongodb:
  storageClassName: ""  # uses Kind's default storage class

replicaCount:
  frontend: 1
  backend: 1
  worker: 1
```

---

## `analytiq-terraform` (private repo)

Existing structure unchanged. Only addition:

```
analytiq-terraform/
  applications/
    docrouter/    # existing — IAM user/role + S3 bucket (unchanged)
    eks/          # NEW — EKS cluster + ECR repos
      main.tf
      providers.tf
      var.tf
      outputs.tf
  modules/        # existing (unchanged)
```

### `applications/eks/providers.tf`

```hcl
terraform {
  # backend "s3" {
  #   bucket         = "analytiq-terraform-state-eks-prod"
  #   key            = "tf-infra/terraform.tfstate"
  #   region         = "us-east-1"
  #   dynamodb_table = "terraform-state-eks-prod-locking"
  #   encrypt        = true
  # }

  required_version = ">=1.9.0"
  required_providers {
    aws  = { source = "hashicorp/aws", version = "~> 5.0" }
    helm = { source = "hashicorp/helm", version = "~> 2.0" }
  }
}

provider "aws" {
  region = var.region
  default_tags {
    tags = { Project = "doc-router", Environment = var.environment }
  }
}

provider "helm" {
  kubernetes {
    host                   = module.eks.cluster_endpoint
    cluster_ca_certificate = base64decode(module.eks.cluster_certificate_authority_data)
    exec {
      api_version = "client.authentication.k8s.io/v1beta1"
      command     = "aws"
      args        = ["eks", "get-token", "--cluster-name", module.eks.cluster_name]
    }
  }
}
```

### Remote state (two-step bootstrap, same pattern as existing modules)

- S3 bucket (`analytiq-terraform-state-eks-prod`): versioning enabled, AES256 SSE, `prevent_destroy`.
- DynamoDB table (`terraform-state-eks-prod-locking`): `PAY_PER_REQUEST`, hash key `LockID`, `prevent_destroy`.

1. `backend "s3"` commented out → `terraform init && terraform apply` (local state, creates S3 + DynamoDB + cluster).
2. Uncomment `backend "s3"` → `terraform init` (migrates state to S3) → `terraform apply`.

### Helm releases installed by Terraform

| Chart | Purpose | Notes |
|---|---|---|
| `ingress-nginx/ingress-nginx` | Ingress controller → AWS NLB | Watches all namespaces |
| `jetstack/cert-manager` | TLS via Let's Encrypt | `crds.enabled = true` required |
| `aws-ebs-csi-driver` | EBS volumes for MongoDB | `serviceAccount.annotations."eks.amazonaws.com/role-arn"` must be set |
| `metrics-server` | Enables HPA | — |

`ClusterIssuer` applied via `null_resource` local-exec after cert-manager is ready.

### Key outputs
- `cluster_name`, `frontend_repo_url`, `backend_repo_url`, `chart_repo_url`

### Manual steps in the AWS console

| Step | Where | Notes |
|---|---|---|
| Enable Bedrock model access | Bedrock → Model access | IAM permissions alone are not enough; models must be explicitly enabled per region. |
| SES production access | SES → Account dashboard | New accounts start in sandbox; request production access or verify sender + recipient addresses. |

---

## Env files (gitignored in `doc-router/`)

All environment and secret values are maintained in **manually created, gitignored** env files. Nothing generates or updates them automatically — they are the single source of truth for scripts.

| File | Used for |
|---|---|
| `.env` | Shared defaults (e.g. `CLUSTER_NAME=doc-router`) |
| `.env.eks` | EKS overlay: `AWS_S3_BUCKET_NAME`, `REGION`, ECR URLs, AWS credentials from `applications/docrouter` outputs |
| `.env.customer-<name>` | Per-customer: their `AWS_S3_BUCKET_NAME`, `CLUSTER_NAME`, `REGION`, `AWS_PROFILE` |

**Variables needed in `.env.eks`:**

Scripts read `AWS_PROFILE` from the overlay and pass it to every `aws` call via `--profile "$AWS_PROFILE"`. The operator never needs to `export AWS_PROFILE`; run `aws sso login --profile <name>` once per session, then build/deploy using the overlay.

| Var | Example | Source |
|---|---|---|
| `AWS_PROFILE` | `analytiq-eks-test` | Named profile used for `aws sso login`; scripts use it for ECR login, `eks update-kubeconfig`, etc. |
| `CLUSTER_NAME` | `doc-router` | Terraform var |
| `REGION` | `us-east-1` | Terraform var |
| `CHART_REGISTRY` | `<account-id>.dkr.ecr.us-east-1.amazonaws.com` | ECR (dev) or `ghcr.io` (release) |
| `FRONTEND_IMAGE_REPO` | `ghcr.io/analytiq-hub/doc-router-frontend` (prod) or ECR URL (dev) | `ghcr.io` for releases; ECR for SHA builds |
| `BACKEND_IMAGE_REPO` | `ghcr.io/analytiq-hub/doc-router-backend` (prod) or ECR URL (dev) | `ghcr.io` for releases; ECR for SHA builds |
| `AWS_S3_BUCKET_NAME` | `docrouter-test` | Existing `applications/docrouter` output |
| `APP_HOST` | `app.example.com` | DNS record you create |
| `STORAGE_CLASS` | `gp3` | EKS standard |
| `AWS_ACCESS_KEY_ID` | — | Existing `applications/docrouter` output |
| `AWS_SECRET_ACCESS_KEY` | — | Existing `applications/docrouter` output |
| `MONGODB_URI` | — | Manual |
| `NEXTAUTH_SECRET` | — | Manual (`openssl rand -base64 32`) |
| `NEXTAUTH_URL` | `https://app.example.com` | DNS record you create |

---

## Helm chart design rules

1. **No hardcoded cluster-specific values** — everything cluster-specific (hostname, ingress class, storage class, image repos, bucket name) comes from Helm values.
2. **Two Deployments** (frontend, backend) in one Helm release, updated together. Worker runs embedded in the backend pod (same as docker-compose / start.sh: `worker.py &` then `uvicorn`). `RollingUpdate` with `maxUnavailable: 0` on both.
3. **MongoDB is opt-in** — `mongodb.enabled: true/false`. When false, `mongodbUri` comes from the values Secret.
4. **No `Namespace` resource in the chart** — the namespace is created by the install script or pre-exists.
5. **PodDisruptionBudget** included — `minAvailable: 1` on each Deployment.

---

## Upgrade stability

### Deployment strategy

Both frontend and backend use `RollingUpdate`. Worker runs embedded in the backend pod and upgrades with it.

```yaml
strategy:
  type: RollingUpdate
  rollingUpdate:
    maxUnavailable: 0
    maxSurge: 1
```

New pods come up and pass readiness before old pods are terminated. Combined with readiness probes, liveness probes, and PDB this prevents any downtime during a rolling upgrade.

### Helm wait

All upgrade and install commands use `--wait --timeout 10m`. Helm polls until all Deployments reach their desired ready count before returning success. On failure the operator sees the error immediately and can inspect pod events; rollback is a manual `helm rollback` or `k8s-rollback.sh`.

### Versioning discipline

`Chart.yaml` carries two version fields:

```yaml
version: 0.3.7       # chart version — bump when chart templates/config change
appVersion: v1.2.3   # application version = image tag
```

Deployment templates default the image tag to `appVersion`:

```yaml
image: "{{ .Values.image.repository }}:{{ .Values.image.tag | default .Chart.AppVersion }}"
```

This means `k8s-deploy.sh` needs **no `--set image.*.tag`** for a release deploy — the chart already knows the correct tag. For dev deploys using a git SHA, override with `IMAGE_TAG=abc1234`.

On every stable release, both `version` and `appVersion` move together. Rollback via `helm rollback` restores the entire previous state atomically — chart config, image tag, and secrets version.

---

## Database and migrations

A Helm hook Job (`pre-upgrade` / `pre-install`) runs the migration script before any pod replacement. Requirements:
- **Idempotent** — safe to re-run on partial failure.
- **Backward-compatible** — only add fields/indexes; never drop or rename what old code reads.

Rollback strategy: MongoDB migrations are forward-only. Rollback means restoring from a backup taken before the upgrade, not running a down-migration.

---

## Deployment scripts

### `build-push.sh`

Builds and pushes both images. Supports AWS ECR (default) and DigitalOcean DOCR (`CLOUD_PROVIDER=do`). For ECR, uses `AWS_PROFILE` from the overlay and runs all `aws` commands with `--profile "$AWS_PROFILE"` (no need to export `AWS_PROFILE` in the shell).

```bash
./deploy/scripts/build-push.sh <overlay>
# e.g. ./deploy/scripts/build-push.sh eks-test
```

Reads `FRONTEND_IMAGE_REPO`, `BACKEND_IMAGE_REPO`, `CHART_REGISTRY`, `REGION` from `.env.$overlay`. Builds `--target runner` (frontend slim image) and `--target backend`. `IMAGE_TAG` defaults to the current git SHA — suitable for dev/test pushes to ECR. Stable releases are built by GitHub Actions when a `vX.Y.Z` tag is pushed, and published to Docker Hub automatically.

### `publish-chart.sh`

Packages the Helm chart and pushes it as an OCI artifact to the registry. For ECR, uses `AWS_PROFILE` from the overlay for registry login (`--profile "$AWS_PROFILE"`).

```bash
./deploy/scripts/publish-chart.sh <overlay>
# e.g. ./deploy/scripts/publish-chart.sh eks-test
```

Reads chart version from `Chart.yaml`. Must be re-run any time `Chart.yaml` version is bumped.

### `k8s-deploy.sh`

Idempotent install-or-upgrade (`helm upgrade --install`). Safe to run on a fresh cluster or an existing deployment. Creates the namespace and `doc-router-secrets` Secret, then deploys the chart from the OCI registry, then restarts pods to pick up any refreshed secrets. Uses `AWS_PROFILE` from the overlay for `aws eks update-kubeconfig` and any other `aws` calls (`--profile "$AWS_PROFILE"`), so the operator does not need to export `AWS_PROFILE`.

```bash
./deploy/scripts/k8s-deploy.sh <overlay>
# e.g. ./deploy/scripts/k8s-deploy.sh eks-test
```

Reads all values from `.env` + `.env.$overlay`. Non-secret config is passed via `--set`; secrets come from the `doc-router-secrets` Secret created by the script.

### `k8s-rollback.sh`

```bash
./deploy/scripts/k8s-rollback.sh <overlay> [revision]
# revision defaults to 0 (= previous revision)
# Run "helm history doc-router -n doc-router" to list available revisions
```

### `k8s-uninstall.sh`

Removes the Helm release and the `doc-router` namespace from the cluster.

```bash
./deploy/scripts/k8s-uninstall.sh <overlay>
```

---

## Image and chart distribution

### Tag conventions

| Tag | Meaning | Published where |
|---|---|---|
| `v1.2.3` | Stable release | `ghcr.io/analytiq-hub/` (images + chart) |
| `v1.2.3-rc.1` | Release candidate | `ghcr.io/analytiq-hub/` (optional) |
| `v1.2.3-beta.1` | Beta | `ghcr.io/analytiq-hub/` (optional) |
| `abc1234` (git SHA) | Dev/test build | ECR only — never published publicly |

Only unqualified `vX.Y.Z` tags are treated as stable. Everything else stays in the private registry.

### Release flow (GitHub Actions on `git tag vX.Y.Z`)

```
git tag v1.2.3 && git push --tags
  → GitHub Actions (GITHUB_TOKEN — no extra secrets needed):
      docker build → push ghcr.io/analytiq-hub/doc-router-frontend:v1.2.3 + :latest
      docker build → push ghcr.io/analytiq-hub/doc-router-backend:v1.2.3  + :latest
      helm package → push ghcr.io/analytiq-hub/doc-router:0.3.7
        (Chart.yaml appVersion: v1.2.3, version: 0.3.7)
```

### Dev/test flow (manual, SHA tag, ECR)

```
./deploy/scripts/build-push.sh eks-test
  → pushes <ECR>/<repo>:<git-sha> to ECR
IMAGE_TAG=<git-sha> ./deploy/scripts/k8s-deploy.sh eks-test
```

---

## Workflow summary

### First-time EKS setup

```bash
# In analytiq-terraform/applications/eks/test/
# Phase 1 — remote state backend (comment out backend "s3" first)
terraform init
terraform apply -target=module.tf_state
# Uncomment backend "s3", then migrate:
terraform init   # answer "yes"

# Phase 2 — VPC + EKS cluster
terraform apply \
  -target=module.eks_cluster.module.vpc \
  -target=module.eks_cluster.module.eks

# Update kubeconfig
aws eks update-kubeconfig --name analytiq-test --region us-east-1

# Phase 3 — Helm add-ons
terraform apply

# Back in doc-router/ — fill in .env.eks-test from terraform outputs
# Build images, publish chart, deploy app
./deploy/scripts/build-push.sh eks-test
./deploy/scripts/publish-chart.sh eks-test
./deploy/scripts/k8s-deploy.sh eks-test
```

### Stable release deploy (from Docker Hub, `vX.Y.Z`)

```bash
# 1. Tag the release — GitHub Actions builds and publishes images + chart automatically
git tag v1.2.3 && git push --tags

# 2. Ensure kubectl is pointing at the right cluster (if needed):
aws eks update-kubeconfig --name analytiq-test --region us-east-1

# 3. Deploy — chart already knows the image tag via appVersion; no IMAGE_TAG needed
./deploy/scripts/k8s-deploy.sh eks-test
```

### Dev/test deploy (SHA build, ECR)

```bash
# Ensure kubectl is pointing at the right cluster (if needed):
aws eks update-kubeconfig --name analytiq-test --region us-east-1

# Build and push SHA-tagged images to ECR, then deploy
./deploy/scripts/build-push.sh eks-test
IMAGE_TAG=$(git rev-parse --short HEAD) ./deploy/scripts/k8s-deploy.sh eks-test
```

### Chart-only update (config/template change, no image rebuild)

```bash
# Bump version and appVersion in deploy/charts/doc-router/Chart.yaml, then:
aws eks update-kubeconfig --name analytiq-test --region us-east-1

./deploy/scripts/publish-chart.sh eks-test
./deploy/scripts/k8s-deploy.sh eks-test
```

### Kind (local dev)

```bash
# In doc-router/ — no Terraform needed
./deploy/scripts/setup-kind.sh    # once
./deploy/scripts/deploy-kind.sh
```

### Onboarding a customer cluster

```bash
# In doc-router/

# 1. Create overlay
cp .env.eks-test .env.customer-acme
# Edit .env.customer-acme: AWS_S3_BUCKET_NAME, CLUSTER_NAME, REGION, AWS_PROFILE, APP_HOST, etc.

# 2. Point kubectl at their cluster
kubectl config use-context <their-cluster-context>

# 3. Install (or upgrade — same script)
./deploy/scripts/k8s-deploy.sh customer-acme

# 4. Subsequent upgrades
./deploy/scripts/k8s-deploy.sh customer-acme
```

### Teardown

```bash
# In analytiq-terraform/applications/eks/test/
terraform destroy -target=module.eks_cluster   # preserves S3 state backend
# or: terraform destroy                        # destroys everything including state backend
```
