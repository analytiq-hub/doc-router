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

#### 3a — EKS scripts (in `doc-router`, public)

Add three scripts to `deploy/scripts/`:

- **`k8s-install.sh`** — first-time install. Sources env overlay, creates namespace, creates `doc-router-secrets` Secret, runs `helm upgrade --install oci://... --version <semver>` with non-secret values passed via `--set`, waits with `--wait --timeout 10m`.
- **`k8s-upgrade.sh`** — upgrades a running release. Updates the `doc-router-secrets` Secret if any secret values changed, then runs `helm upgrade oci://... --version <semver> --reuse-values --set image.*.tag=<new-tag> --wait`.
- **`k8s-rollback.sh`** — runs `helm rollback doc-router <revision> -n doc-router --wait`.

#### 3b — `doc-router-ops` repo (private)

Create a new private repository with:
- `terraform/` — one root module per AWS account (VPC, EKS, ECR, IAM, S3, Helm add-ons: ingress-nginx, cert-manager, EBS CSI, metrics-server).
- `scripts/` — `apply-terraform.sh`, `build-push.sh`, `publish-chart.sh`.
- `.env`, `.env.eks`, `.env.customer-*` — gitignored secret/config overlays.

#### 3c — OCI chart publishing

`publish-chart.sh` packages the chart and pushes it as an OCI artifact to ECR:
```bash
helm package deploy/charts/doc-router --version <semver>
helm push doc-router-<semver>.tgz oci://<ECR_REGISTRY>/doc-router/chart
```

The chart itself needs no changes for EKS — only values differ (`gp3` storage class, TLS enabled, ECR image repos, real hostnames).

**cert-manager is EKS-only.** Kind uses `helm upgrade --install` directly with TLS disabled.

---

## Two-repo structure

Everything lives across **two repositories**:

| Repo | Visibility | Contains |
|---|---|---|
| `doc-router` | **Public / open source** | App source code, Helm chart, customer-facing install scripts |
| `doc-router-ops` | **Private** | Terraform, operational scripts, env files |

The Helm chart and install scripts are public because customers need them and they contain nothing sensitive. Terraform, our real ECR URLs, cluster-specific values, and env files are private.

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
    scripts/                  # customer-facing; also used by doc-router-ops
      k8s-install.sh          # first-time install into any cluster
      k8s-upgrade.sh          # upgrade to a new chart version
      k8s-rollback.sh         # roll back to a previous chart version
      deploy-kind.sh          # local Kind deploy (helm upgrade --install)
      setup-kind.sh           # create local Kind cluster
      values-kind.yaml        # committed Kind-specific overrides (no secrets)
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

## `doc-router-ops` (private repo)

```
doc-router-ops/
  README.md               # documents scripts and workflow
  scripts/
    apply-terraform.sh    # sources .env + overlay, exports TF_VAR_*, runs terraform
    build-push.sh         # builds images, pushes to ECR
    publish-chart.sh      # packages chart, pushes OCI artifact to ECR
  terraform/
    analytiq-prod/        # our production AWS account — independent root module
    analytiq-test/        # our staging AWS account
    customer-<name>/      # only needed if we provision EKS for a customer
    .gitignore            # .terraform/, terraform.tfstate*
  .env                    # gitignored — shared defaults
  .env.eks                # gitignored — our EKS overlay
  .env.customer-acme      # gitignored — customer-specific overlay
```

**Required tools:** `terraform ~1.9`, `awscli`, `kubectl`, `helm` — install manually or via your preferred version manager. Workflow is documented in `README.md`.

---

## Env files (in `doc-router-ops`, all manual)

All environment and secret values are maintained in **manually created, gitignored** env files in `doc-router-ops`. Nothing generates or updates them automatically — they are the single source of truth for both Terraform and the Kubernetes Secrets.

| File | Used for |
|---|---|
| `.env` | Shared defaults across all overlays (e.g. `CLUSTER_NAME=doc-router`) |
| `.env.eks` | Our EKS: `APP_BUCKET_NAME`, `REGION`, ECR URLs, app IAM keys from Terraform outputs |
| `.env.customer-<name>` | Per-customer: their `APP_BUCKET_NAME`, `CLUSTER_NAME`, `REGION`, `AWS_PROFILE` |

**Variables exported as `TF_VAR_*` before `terraform apply`:**

| Env var | Terraform variable | Example |
|---|---|---|
| `CLUSTER_NAME` | `cluster_name` | `doc-router` |
| `APP_BUCKET_NAME` | `app_bucket_name` | `doc-router-data-prod` |
| `REGION` | `region` | `us-east-1` |
| `VPC_CIDR` | `vpc_cidr` | `10.0.0.0/16` |
| `ENVIRONMENT` | `environment` | `prod` |
| `LETSENCRYPT_EMAIL` | `letsencrypt_email` | required by ACME |

After the first Terraform apply, copy the app user access key ID and secret from Terraform outputs into `.env.eks`.

---

## Terraform (`doc-router-ops/terraform/<account>/`)

Each account directory is a self-contained root module with its own `providers.tf` hardcoded to that account's S3 state backend. No `terraform.tfvars` — all variables come from `TF_VAR_*` exported by `apply-terraform.sh`.

```
terraform/analytiq-prod/
  main.tf       # VPC + EKS + ECR + IAM + Helm releases + S3/DynamoDB for tf state
  providers.tf  # aws + helm providers; backend "s3" commented out until first apply
  variables.tf  # region, cluster_name, app_bucket_name, vpc_cidr, environment, etc.
  outputs.tf
```

Adding a new account: `cp -r analytiq-prod <new-account>`, update `providers.tf` (state bucket + DynamoDB table names only).

### Remote state

- S3 bucket (`analytiq-terraform-state-eks-<account>`): versioning enabled, AES256 SSE, `prevent_destroy`.
- DynamoDB table (`terraform-state-eks-<account>-locking`): `PAY_PER_REQUEST`, hash key `LockID`, `prevent_destroy`.

**Two-step bootstrap (first time only):**
1. `backend "s3"` commented out → `terraform init && terraform apply` (creates S3 + DynamoDB + cluster using local state).
2. Uncomment `backend "s3"` → `terraform init` (migrates state to S3) → `terraform apply`.

**`providers.tf`**:

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

### VPC

`terraform-aws-modules/vpc/aws`: `/16` CIDR, 2 public subnets (NAT + NLB) + 2 private subnets (nodes) across 2 AZs, one NAT gateway.

### EKS

`terraform-aws-modules/eks/aws`: cluster and nodes in private subnets, managed node group (`t3.medium` / `t3.large`, min/desired/max = 2/2/5), OIDC provider enabled.

### ECR (inline in `main.tf`)

Three repositories:
- `doc-router-frontend`, `doc-router-backend` — app images.
- `doc-router/chart` — Helm chart OCI artifacts (lifecycle policy keeps last N).

### S3 app bucket (inline in `main.tf`)

One bucket for document storage. Name from `var.app_bucket_name` (set via `TF_VAR_app_bucket_name` from `.env.eks`). AES256 SSE. Separate from the Terraform state bucket.

### IAM (inline in `main.tf`)

**Node group role:** `AmazonEKSWorkerNodePolicy`, `AmazonEKS_CNI_Policy`, `AmazonEC2ContainerRegistryReadOnly`, EBS CSI IRSA role (required for MongoDB PVCs).

**App user + role** (same pattern as `analytiq-terraform/modules/docrouter`):
- `aws_iam_user` (`doc-router-app-user`) + `aws_iam_access_key` → injected into `doc-router-secrets` as `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY`.
- `aws_iam_role` (`doc-router-app-role`) assumed by the user: `AmazonTextractFullAccess`, `AmazonSESFullAccess`, inline S3 policy on the app bucket.
- `aws_s3_bucket_policy` granting `s3:*` to the app role principal.
- Bedrock `InvokeModel` / `InvokeModelWithResponseStream` attached **directly to the user** (Bedrock is called with the user's access key, not through role assumption).

### Helm releases (inline in `main.tf`)

| Chart | Purpose | Notes |
|---|---|---|
| `ingress-nginx/ingress-nginx` | Ingress controller → AWS NLB | Watches all namespaces |
| `jetstack/cert-manager` | TLS via Let's Encrypt | `crds.enabled = true` required |
| `aws-ebs-csi-driver` | EBS volumes for MongoDB | `serviceAccount.annotations."eks.amazonaws.com/role-arn"` must be set |
| `metrics-server` | Enables HPA | — |

`ClusterIssuer` applied via `null_resource` local-exec after cert-manager is ready. `LETSENCRYPT_EMAIL` comes from `.env` / overlay.

### Key outputs
- `cluster_name`, `frontend_repo_url`, `backend_repo_url`, `chart_repo_url`
- `app_user_access_key_id`, `app_user_secret_access_key` (sensitive)
- `app_bucket_name`, `app_role_arn`

### Manual steps in the AWS console

| Step | Where | Notes |
|---|---|---|
| Enable Bedrock model access | Bedrock → Model access | IAM permissions alone are not enough; models must be explicitly enabled per region. |
| SES production access | SES → Account dashboard | New accounts start in sandbox; request production access or verify sender + recipient addresses. |

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

### In `doc-router/deploy/scripts/` (public — used by customers and by us)

**`k8s-install.sh`** — first-time install into any cluster. Takes overlay name and chart version.

1. Source `.env` + overlay (from `doc-router-ops/`).
2. Create namespace if it doesn't exist.
3. Create `doc-router-secrets` Kubernetes Secret from env vars (MongoDB URI, AWS credentials, NextAuth secret, API keys).
4. `helm upgrade --install doc-router oci://${CHART_REGISTRY}/doc-router/chart --version ${CHART_VERSION} -n doc-router --set ingress.host=... --set image.*.repository=... --set image.*.tag=... --set config.* --wait --timeout 10m`

**`k8s-upgrade.sh`** — upgrades a running cluster.

1. Source `.env` + overlay.
2. Update `doc-router-secrets` if any secret values changed.
3. `helm upgrade doc-router oci://${CHART_REGISTRY}/doc-router/chart --version ${CHART_VERSION} -n doc-router --reuse-values --set image.frontend.tag=${IMAGE_TAG} --set image.backend.tag=${IMAGE_TAG} --wait --timeout 10m`

**`k8s-rollback.sh`** — rolls back to a previous Helm revision.

1. Source `.env` + overlay.
2. `helm rollback doc-router -n doc-router --wait` (rolls back to the previous revision; pass an explicit revision number to target a specific one).

**`deploy-kind.sh`** — local Kind dev; uses `helm upgrade --install` directly against the local chart path.

### In `doc-router-ops/scripts/` (private — our ops only)

**`apply-terraform.sh`** — sources `.env` + overlay, exports `TF_VAR_*`, runs `terraform init && terraform apply` in the given account directory.

**`build-push.sh`** — ECR login, `docker build --target frontend/backend`, tag `<ECR_URL>:<git-sha>` + `:latest`, push both images.

**`publish-chart.sh`** — `helm package deploy/charts/doc-router`, ECR login, `helm push` OCI artifact to `doc-router/chart`.

---

## Workflow summary

All ops work runs from **`doc-router-ops/`** by calling scripts directly.

### First-time setup for a new AWS account

```bash
# In doc-router-ops/
export AWS_PROFILE=<account-profile>

# 1. Create S3 + DynamoDB + EKS cluster (backend "s3" commented out in providers.tf)
./scripts/apply-terraform.sh eks terraform/analytiq-prod

# 2. Migrate Terraform state to S3
#    Uncomment backend "s3" in terraform/analytiq-prod/providers.tf, then:
cd terraform/analytiq-prod
terraform init    # answer "yes" to copy local state → S3
# re-source .env + .env.eks and re-export TF_VAR_*, then:
terraform apply
cd ../..

# 3. Update kubeconfig
set -a; source .env; source .env.eks; set +a
aws eks update-kubeconfig --name "${CLUSTER_NAME:-doc-router}" --region "${REGION}"

# 4. Build images + publish first chart version
./scripts/build-push.sh
./scripts/publish-chart.sh 1.0.0

# 5. Install app into the cluster
../doc-router/deploy/scripts/k8s-install.sh eks 1.0.0
```

### Per-deployment (our EKS)

```bash
# In doc-router-ops/
export AWS_PROFILE=<account-profile>
./scripts/build-push.sh
./scripts/publish-chart.sh 1.5.0
../doc-router/deploy/scripts/k8s-upgrade.sh eks 1.5.0
```

### Adding a second AWS account

```bash
# In doc-router-ops/
cp -r terraform/analytiq-prod terraform/analytiq-test
# Edit terraform/analytiq-test/providers.tf: update state bucket + DynamoDB table names.
# Create .env.eks-test with APP_BUCKET_NAME, REGION, CLUSTER_NAME, etc.
# Run first-time setup steps above with the new directory and overlay.
```

### Kind (local dev)

```bash
# In doc-router/ — no doc-router-ops needed for local dev
./deploy/scripts/setup-kind.sh    # once
# Create .env and .env.kind
./deploy/scripts/deploy-kind.sh
```

### Onboarding a customer cluster

```bash
# In doc-router-ops/

# 1. Create overlay
cp .env.eks .env.customer-acme
# Edit .env.customer-acme: APP_BUCKET_NAME, CLUSTER_NAME, REGION, AWS_PROFILE, APP_HOST, etc.

# 2. Point kubectl at their cluster
kubectl config use-context <their-cluster-context>

# 3. Install
../doc-router/deploy/scripts/k8s-install.sh customer-acme 1.4.0

# 4. Subsequent upgrades
../doc-router/deploy/scripts/k8s-upgrade.sh customer-acme 1.5.0
```

If provisioning their EKS with Terraform first: `cp -r terraform/analytiq-prod terraform/customer-acme`, update `providers.tf`, then `./scripts/apply-terraform.sh customer-acme terraform/customer-acme`.

### Teardown

```bash
# In doc-router-ops/
export AWS_PROFILE=<account-profile>
cd terraform/analytiq-prod && terraform destroy
```
