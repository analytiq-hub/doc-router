# EKS deployment plan

## Goals

- Deploy doc-router to AWS EKS (our own cluster, one or more namespaces).
- Deploy doc-router to a customer's existing Kubernetes cluster (any provider).
- Docker images built from the existing multi-stage Dockerfile, stored in ECR.
- Terraform manages all AWS infrastructure; a **Helm chart** is the single source of truth for Kubernetes packaging.
- The chart is published as an OCI artifact to ECR and installed with `helm upgrade --install` directly — no GitOps controller required.

### Non-Goals
- Customers do not need to adopt our Git workflow; they pin a chart version and run scripts.
- No GitHub Actions, Argo CD, Flux, or proprietary deployment services required.

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

Add five scripts to `deploy/scripts/`:

- **`build-push.sh`** — ECR login, `docker build --target frontend/backend`, tag `<ECR_URL>:<git-sha>` + `:latest`, push both images.
- **`publish-chart.sh`** — `helm package deploy/charts/doc-router --version <semver>`, ECR login, `helm push` OCI artifact to `doc-router/chart` ECR repo.
- **`k8s-install.sh`** — first-time install. Sources env overlay, creates namespace, creates `doc-router-secrets` Secret, runs `helm upgrade --install oci://... --version <semver>` with non-secret values via `--set`, waits with `--wait --timeout 10m`.
- **`k8s-upgrade.sh`** — upgrades a running release. Updates the `doc-router-secrets` Secret if any secret values changed, then runs `helm upgrade oci://... --version <semver> --reuse-values --set image.*.tag=<new-tag> --wait`.
- **`k8s-rollback.sh`** — runs `helm rollback doc-router <revision> -n doc-router --wait`.

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
- **ECR repos** — `doc-router-frontend`, `doc-router-backend`, `doc-router/chart` (OCI artifacts).
- **Helm releases** — ingress-nginx, cert-manager (`crds.enabled=true`), aws-ebs-csi-driver, metrics-server.
- **ClusterIssuer** — applied via `null_resource` local-exec after cert-manager is ready.

#### 3c — OCI chart publishing

`publish-chart.sh` packages the chart and pushes it as an OCI artifact to ECR:
```bash
helm package deploy/charts/doc-router --version <semver>
helm push doc-router-<semver>.tgz oci://<ECR_REGISTRY>/doc-router/chart
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
      build-push.sh           # build + push images to ECR
      publish-chart.sh        # package + push OCI chart to ECR
      k8s-install.sh          # first-time install into any cluster
      k8s-upgrade.sh          # upgrade to a new chart version
      k8s-rollback.sh         # roll back to a previous chart version
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
    repository: analytiqhub/doc-router-frontend
    tag: latest
    pullPolicy: IfNotPresent
  backend:
    repository: analytiqhub/doc-router-backend
    tag: latest
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
| `.env.eks` | EKS overlay: `APP_BUCKET_NAME`, `REGION`, ECR URLs, AWS credentials from `applications/docrouter` outputs |
| `.env.customer-<name>` | Per-customer: their `APP_BUCKET_NAME`, `CLUSTER_NAME`, `REGION`, `AWS_PROFILE` |

**Variables needed in `.env.eks`:**

| Var | Example | Source |
|---|---|---|
| `CLUSTER_NAME` | `doc-router` | Terraform var |
| `REGION` | `us-east-1` | Terraform var |
| `CHART_REGISTRY` | `<account-id>.dkr.ecr.us-east-1.amazonaws.com` | `chart_repo_url` output |
| `FRONTEND_IMAGE_REPO` | `<account-id>.dkr.ecr.us-east-1.amazonaws.com/doc-router-frontend` | `frontend_repo_url` output |
| `BACKEND_IMAGE_REPO` | `<account-id>.dkr.ecr.us-east-1.amazonaws.com/doc-router-backend` | `backend_repo_url` output |
| `APP_BUCKET_NAME` | `docrouter-test` | Existing `applications/docrouter` output |
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

One semver version ties together the chart version (`Chart.yaml`) and both container image tags. The upgrade script sets all three atomically. Rollback patches all three back via `helm rollback`.

---

## Database and migrations

A Helm hook Job (`pre-upgrade` / `pre-install`) runs the migration script before any pod replacement. Requirements:
- **Idempotent** — safe to re-run on partial failure.
- **Backward-compatible** — only add fields/indexes; never drop or rename what old code reads.

Rollback strategy: MongoDB migrations are forward-only. Rollback means restoring from a backup taken before the upgrade, not running a down-migration.

---

## Deployment scripts

### `build-push.sh`

```bash
# Sources .env + overlay for ECR URLs
set -a; source .env; source ".env.${1:?overlay required}"; set +a
IMAGE_TAG=${2:?image tag required}   # e.g. git sha or semver

aws ecr get-login-password --region "$REGION" \
  | docker login --username AWS --password-stdin "$CHART_REGISTRY"

docker build --target frontend -t "$FRONTEND_IMAGE_REPO:$IMAGE_TAG" \
  -t "$FRONTEND_IMAGE_REPO:latest" -f deploy/shared/docker/Dockerfile .
docker push "$FRONTEND_IMAGE_REPO:$IMAGE_TAG"
docker push "$FRONTEND_IMAGE_REPO:latest"

docker build --target backend -t "$BACKEND_IMAGE_REPO:$IMAGE_TAG" \
  -t "$BACKEND_IMAGE_REPO:latest" -f deploy/shared/docker/Dockerfile .
docker push "$BACKEND_IMAGE_REPO:$IMAGE_TAG"
docker push "$BACKEND_IMAGE_REPO:latest"
```

### `publish-chart.sh`

```bash
# Sources .env + overlay for CHART_REGISTRY
set -a; source .env; source ".env.${1:?overlay required}"; set +a
CHART_VERSION=${2:?chart version required}   # semver

helm package deploy/charts/doc-router --version "$CHART_VERSION"
aws ecr get-login-password --region "$REGION" \
  | helm registry login --username AWS --password-stdin "$CHART_REGISTRY"
helm push "doc-router-${CHART_VERSION}.tgz" "oci://${CHART_REGISTRY}/doc-router/chart"
rm "doc-router-${CHART_VERSION}.tgz"
```

### `k8s-install.sh`

```bash
set -a; source .env; source ".env.${1:?overlay required}"; set +a
CHART_VERSION=${2:?chart version required}

kubectl create namespace doc-router --dry-run=client -o yaml | kubectl apply -f -

kubectl create secret generic doc-router-secrets \
  --from-literal=MONGODB_URI="$MONGODB_URI" \
  --from-literal=AWS_ACCESS_KEY_ID="$AWS_ACCESS_KEY_ID" \
  --from-literal=AWS_SECRET_ACCESS_KEY="$AWS_SECRET_ACCESS_KEY" \
  --from-literal=NEXTAUTH_SECRET="$NEXTAUTH_SECRET" \
  --namespace doc-router --dry-run=client -o yaml | kubectl apply -f -

aws ecr get-login-password --region "$REGION" \
  | helm registry login --username AWS --password-stdin "$CHART_REGISTRY"

helm upgrade --install doc-router \
  "oci://${CHART_REGISTRY}/doc-router/chart" \
  --version "$CHART_VERSION" \
  --namespace doc-router \
  --set ingress.host="$APP_HOST" \
  --set ingress.className=nginx \
  --set mongodb.storageClassName="$STORAGE_CLASS" \
  --set image.frontend.repository="$FRONTEND_IMAGE_REPO" \
  --set image.backend.repository="$BACKEND_IMAGE_REPO" \
  --set image.frontend.tag="$IMAGE_TAG" \
  --set image.backend.tag="$IMAGE_TAG" \
  --set config.appBucketName="$APP_BUCKET_NAME" \
  --set config.region="$REGION" \
  --set config.nextauthUrl="$NEXTAUTH_URL" \
  --wait --timeout 10m
```

### `k8s-upgrade.sh`

```bash
set -a; source .env; source ".env.${1:?overlay required}"; set +a
CHART_VERSION=${2:?chart version required}

# Refresh secrets in case any values changed
kubectl create secret generic doc-router-secrets \
  --from-literal=MONGODB_URI="$MONGODB_URI" \
  --from-literal=AWS_ACCESS_KEY_ID="$AWS_ACCESS_KEY_ID" \
  --from-literal=AWS_SECRET_ACCESS_KEY="$AWS_SECRET_ACCESS_KEY" \
  --from-literal=NEXTAUTH_SECRET="$NEXTAUTH_SECRET" \
  --namespace doc-router --dry-run=client -o yaml | kubectl apply -f -

aws ecr get-login-password --region "$REGION" \
  | helm registry login --username AWS --password-stdin "$CHART_REGISTRY"

helm upgrade doc-router \
  "oci://${CHART_REGISTRY}/doc-router/chart" \
  --version "$CHART_VERSION" \
  --namespace doc-router \
  --reuse-values \
  --set image.frontend.tag="$IMAGE_TAG" \
  --set image.backend.tag="$IMAGE_TAG" \
  --wait --timeout 10m
```

### `k8s-rollback.sh`

```bash
set -a; source .env; source ".env.${1:?overlay required}"; set +a
REVISION=${2:-0}   # 0 = previous revision; pass explicit number to target a specific one

helm rollback doc-router "$REVISION" --namespace doc-router --wait
```

---

## Workflow summary

### First-time EKS setup

```bash
# In analytiq-terraform/applications/eks/
# (backend "s3" commented out in providers.tf)
terraform init && terraform apply

# Migrate state to S3: uncomment backend "s3", then:
terraform init   # answer "yes"
terraform apply

# Update kubeconfig
aws eks update-kubeconfig --name doc-router --region us-east-1

# Back in doc-router/ — fill in .env and .env.eks from terraform outputs
# Build images + publish first chart version
./deploy/scripts/build-push.sh eks <git-sha>
./deploy/scripts/publish-chart.sh eks 1.0.0

# Install app
./deploy/scripts/k8s-install.sh eks 1.0.0
```

### Per-deployment

```bash
# In doc-router/
./deploy/scripts/build-push.sh eks <git-sha>
./deploy/scripts/publish-chart.sh eks 1.5.0
./deploy/scripts/k8s-upgrade.sh eks 1.5.0
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
cp .env.eks .env.customer-acme
# Edit .env.customer-acme: APP_BUCKET_NAME, CLUSTER_NAME, REGION, AWS_PROFILE, APP_HOST, etc.

# 2. Point kubectl at their cluster
kubectl config use-context <their-cluster-context>

# 3. Install
./deploy/scripts/k8s-install.sh customer-acme 1.4.0

# 4. Subsequent upgrades
./deploy/scripts/k8s-upgrade.sh customer-acme 1.5.0
```

### Teardown

```bash
# In analytiq-terraform/applications/eks/
terraform destroy
```
