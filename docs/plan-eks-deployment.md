# EKS deployment plan

## Goals

- Deploy doc-router to AWS EKS (our own cluster, one or more namespaces).
- Deploy doc-router to a customer's existing Kubernetes cluster (any provider).
- Docker images built from the existing multi-stage Dockerfile, stored in ECR.
- Terraform manages all AWS infrastructure; a **Helm chart** is the single source of truth for Kubernetes packaging.
- Flux delivers the chart via **HelmRelease** (OCI-sourced) and continuously reconciles cluster state.
- **Single source of config:** all deployment and app config comes from `.env` plus an overlay per environment (e.g. `.env.eks`, `.env.customer-acme`). Each customer deployment can target a different AWS account.

---

## Goals and Non-Goals

### Goals
- **Single source of truth** for Kubernetes packaging: one Helm chart, versioned with semver.
- **Two deployment scenarios**:
  1. Customer installs into an existing Kubernetes cluster using our scripts.
  2. We run SaaS on EKS (cluster we provision), using the same chart + Flux.
- **Safe upgrades**: old pods stay up until new ones are ready; migrations are orchestrated safely.
- **GitOps-style reconciliation** via Flux, without CI/CD pipelines — deploy and upgrade with shell commands.

### Non-Goals
- Customers do not need to adopt our Git workflow; they pin a chart version and run scripts.
- No GitHub Actions, Argo CD, or proprietary deployment services required.

---

## Config from .env and overlays

All configuration is driven by **`.env`** plus an **overlay file** per deployment:

| Overlay file           | Used for               | AWS account / cluster      |
|------------------------|------------------------|----------------------------|
| `.env`                 | Shared defaults        | —                          |
| `.env.kind`            | Local Kind cluster     | —                          |
| `.env.eks`             | Our hosted EKS         | One of our accounts        |
| `.env.customer-<name>` | Customer deployment    | Any account (per customer) |

- **Cluster name:** Set `CLUSTER_NAME=doc-router` in `.env` (or overlay); the same name can be used in every account.
- **Bucket name:** Set `APP_BUCKET_NAME` in `.env` or the overlay (e.g. `APP_BUCKET_NAME=doc-router-data-prod`). Terraform uses it to create the bucket and IAM policy; the deploy scripts render it into Helm values so the running app knows which bucket to use.
- **Different AWS account per customer:** Set `AWS_PROFILE` when sourcing the overlay. Each customer can have its own Terraform state directory and overlay file.
- **Helm values:** non-secret config is rendered into a `values-<overlay>.yaml` file (gitignored) by the deploy script and passed to Flux as a `values:` stanza in the HelmRelease (or as a ConfigMap/Secret `valuesFrom`). Secrets (API keys, DB URI, AWS credentials) are rendered into a Kubernetes Secret (`doc-router-secrets`) and referenced via `valuesFrom` in the HelmRelease.

Terraform does **not** use `terraform.tfvars`. A script sources `.env` and the overlay, exports `TF_VAR_*` for Terraform, then runs `terraform apply`.

---

## Tool versions and deploy tasks (mise)

All deployment scripts are run via **mise** so that Terraform, AWS CLI, kubectl, helm, and flux versions are pinned and consistent. Install [mise](https://mise.jdx.dev/), then from the repo root run `mise install`.

**`.mise.toml`** at repo root:

```toml
[tools]
terraform = "~1.9"
awscli    = "latest"
kubectl   = "latest"
helm      = "latest"
flux2     = "latest"

[tasks.apply-terraform]
description = "Run Terraform apply with vars from .env + overlay"
run = "./deploy/scripts/apply-terraform.sh"
# Usage: mise run apply-terraform -- <overlay> <terraform-dir>
# Example: mise run apply-terraform -- eks deploy/terraform/analytiq-prod

[tasks.build-push]
description = "Build and push frontend/backend images to ECR"
run = "./deploy/scripts/build-push.sh"

[tasks.publish-chart]
description = "Package and push the Helm chart as an OCI artifact to ECR"
run = "./deploy/scripts/publish-chart.sh"

[tasks.k8s-install]
description = "Install Flux + HelmRelease into a cluster (first time)"
run = "./deploy/scripts/k8s-install.sh"
# Usage: mise run k8s-install -- <overlay> <chart-version>
# Example: mise run k8s-install -- eks 1.4.0

[tasks.k8s-upgrade]
description = "Upgrade to a new chart version via Flux HelmRelease"
run = "./deploy/scripts/k8s-upgrade.sh"
# Usage: mise run k8s-upgrade -- <overlay> <chart-version>

[tasks.k8s-rollback]
description = "Roll back the HelmRelease to a previous chart version"
run = "./deploy/scripts/k8s-rollback.sh"
# Usage: mise run k8s-rollback -- <overlay> <chart-version>

[tasks.deploy-eks]
description = "Build images, publish chart, upgrade EKS HelmRelease"
depends = ["build-push", "publish-chart"]
run = "./deploy/scripts/k8s-upgrade.sh"

[tasks.deploy-kind]
description = "Deploy to local Kind cluster"
run = "./deploy/scripts/deploy-kind.sh"

[tasks.setup-kind]
description = "Create Kind cluster (run once)"
run = "./deploy/scripts/setup-kind.sh"

[tasks.update-kubeconfig]
description = "Update kubeconfig for EKS"
run = "aws eks update-kubeconfig --name ${CLUSTER_NAME:-doc-router} --region ${REGION}"
```

Before running any EKS/customer task that needs AWS or kubectl, set `AWS_PROFILE` (or source `.env` and the overlay) so the correct account is used. Scripts source `.env` and the overlay for app config; they do not set `AWS_PROFILE`.

---

## Repository layout

```
doc-router/
  .mise.toml        # tool versions + deploy tasks
  charts/
    doc-router/     # Helm chart — single source of truth for K8s packaging
      Chart.yaml
      values.yaml              # defaults; never real secrets
      templates/
        frontend/
          deployment.yaml
          service.yaml
          ingress.yaml
        backend/
          deployment.yaml
          service.yaml
          hpa.yaml
        mongodb/
          statefulset.yaml     # conditional: enabled by values.mongodb.enabled
          service.yaml
        migration-job.yaml     # runs as pre-upgrade/pre-install Helm hook
        configmap.yaml
        pdb.yaml
  deploy/
    scripts/
      apply-terraform.sh       # sources .env + overlay, exports TF_VAR_*, runs terraform
      build-push.sh            # builds images, pushes to ECR
      publish-chart.sh         # packages and pushes chart OCI artifact to ECR
      k8s-install.sh           # first-time install: Flux + OCIRepository + HelmRelease + Secret
      k8s-upgrade.sh           # patches HelmRelease chart version, reconciles
      k8s-rollback.sh          # patches version back to previous, reconciles
      deploy-kind.sh           # local Kind deploy (helm upgrade --install)
      setup-kind.sh            # create Kind cluster
    terraform/
      analytiq-prod/           # our production account
      analytiq-test/           # our test/staging account
      customer-<name>/         # if we provision EKS for a customer
      .gitignore               # .terraform/, terraform.tfstate*
    flux/
      eks/                     # Flux OCIRepository + HelmRelease (applied once per cluster)
        ocirepository.yaml
        helmrelease.yaml
      customer-example/        # template for customer clusters
        ocirepository.yaml
        helmrelease.yaml
```

Each directory under `deploy/terraform/` is an independent root module for one AWS account. State files are gitignored. Variable values come from `.env` and overlays; deploy scripts export `TF_VAR_*` before running Terraform.

Customer clusters with a ready-made Kubernetes environment only need the Flux manifests and a values Secret — no Terraform.

---

## Terraform (`deploy/terraform/<account>/`)

Each account directory is self-contained: its own `providers.tf` with a hardcoded backend for that account's S3 bucket.

**Variables:** All inputs are defined in `variables.tf` and supplied at apply time via **environment variables** `TF_VAR_<name>`. The deploy script sources `.env` and the overlay, then exports the corresponding `TF_VAR_*`. You do **not** create or commit `terraform.tfvars`.

```
deploy/terraform/analytiq-prod/
  main.tf           # VPC + EKS + ECR + IAM + Helm releases + S3/DynamoDB for tf state
  providers.tf      # aws + helm providers; backend "s3" commented out until first apply
  variables.tf      # region, cluster_name, app_bucket_name, vpc_cidr, environment, etc.
  outputs.tf
```

Adding a new account: `cp -r analytiq-prod <new-account>`, update `providers.tf` (bucket/table names for state only).

### Remote state

S3 bucket and DynamoDB table defined directly in `main.tf`:

- S3 bucket (`analytiq-terraform-state-eks-<account>`): versioning enabled, AES256 SSE, `prevent_destroy`.
- DynamoDB table (`terraform-state-eks-<account>-locking`): `PAY_PER_REQUEST`, hash key `LockID`, `prevent_destroy`.

**Two-step process (first time only):**

1. `backend "s3"` commented out → `terraform init && terraform apply` (local state, creates S3 + DynamoDB + cluster).
2. Uncomment `backend "s3"` → `terraform init` (migrates state to S3) → `terraform apply`.

**`providers.tf`**:

```hcl
terraform {
  # Step 1: comment out backend, run init/apply to create S3 bucket + DynamoDB.
  # Step 2: uncomment backend, run terraform init to migrate state to S3.
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
    tags = {
      Project     = "doc-router"
      Environment = var.environment
    }
  }
}

# Helm provider uses aws eks get-token at runtime (exec plugin).
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

Use `terraform-aws-modules/vpc/aws`:

- `/16` CIDR.
- 2 public subnets (NGINX Ingress LoadBalancer, NAT gateway) across 2 AZs.
- 2 private subnets (worker nodes) across 2 AZs.
- One NAT gateway.

### EKS

Use `terraform-aws-modules/eks/aws`:

- Cluster and nodes in private subnets.
- Managed node group: `t3.medium` or `t3.large`, min/desired/max = 2/2/5.
- OIDC provider enabled (for IRSA, e.g. External Secrets Operator).

### ECR (inline in `main.tf`)

Three `aws_ecr_repository` resources:

- `doc-router-frontend`, `doc-router-backend` — app images.
- `doc-router/chart` — Helm chart OCI artifacts (one per release, lifecycle policy keeps last N).

Flux pulls the chart from ECR using the node instance profile (`AmazonEC2ContainerRegistryReadOnly`), so no separate IRSA is needed for Flux.

### S3 app bucket (inline in `main.tf`)

One `aws_s3_bucket` for document storage. Bucket name comes from `var.app_bucket_name` (set via `TF_VAR_app_bucket_name`). The deploy script also renders this name into Helm values / the values Secret so the running app knows which bucket to use. Bucket has AES256 SSE and is separate from the Terraform state bucket.

### IAM (inline in `main.tf`)

**EKS node group role:**
- `AmazonEKSWorkerNodePolicy`, `AmazonEKS_CNI_Policy`, `AmazonEC2ContainerRegistryReadOnly`.
- EBS CSI IRSA role with the EBS CSI controller policy (required for MongoDB PVCs).

**App IAM user + role** (same pattern as `analytiq-terraform/modules/docrouter`):

- `aws_iam_user` (`doc-router-app-user`) + `aws_iam_access_key` — credentials injected into the `doc-router-secrets` Kubernetes Secret as `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY`.
- `aws_iam_role` (`doc-router-app-role`) assumed by the user, with:
  - `AmazonTextractFullAccess`
  - `AmazonSESFullAccess`
  - Inline S3 policy: `PutObject`, `GetObject`, `ListBucket`, `DeleteObject` on the app bucket.
- `aws_s3_bucket_policy` granting `s3:*` to the app role principal.
- Bedrock `InvokeModel` / `InvokeModelWithResponseStream` on `arn:aws:bedrock:*::foundation-model/*` and `arn:aws:bedrock:*:*:inference-profile/*` attached **directly to the user** — Bedrock is called using the user's access key directly, not through role assumption.

Access key ID and secret are Terraform outputs (sensitive). Copy them into your `.env.eks` after the first Terraform apply.

### Helm releases (inline in `main.tf`)

| Chart | Purpose | Notable config |
|---|---|---|
| `ingress-nginx/ingress-nginx` | Ingress controller, exposes an AWS NLB/ELB | Watches all namespaces by default |
| `jetstack/cert-manager` | TLS certificate automation via Let's Encrypt | `crds.enabled = true` — required or ClusterIssuer will fail |
| `aws-ebs-csi-driver` | EBS volumes for MongoDB PVCs | `serviceAccount.annotations."eks.amazonaws.com/role-arn"` must be set to the EBS CSI IRSA role ARN |
| `metrics-server` | Enables HPA | — |
| `fluxcd-community/flux2` | GitOps reconciliation — pulls Helm chart from ECR and applies HelmRelease; self-heals on drift | Installed via Helm after cluster is ready; no `flux bootstrap` or GitHub access needed |

A single `ClusterIssuer` for Let's Encrypt is applied via a `null_resource` local-exec with `depends_on = [helm_release.cert_manager]`. Add `LETSENCRYPT_EMAIL` to `.env` or the overlay and include it in the `TF_VAR_*` exports.

### Key outputs

- `cluster_name`, `frontend_repo_url`, `backend_repo_url`, `chart_repo_url`
- `app_user_access_key_id`, `app_user_secret_access_key` (sensitive)
- `app_bucket_name`, `app_role_arn`

### Manual steps in the AWS console

| Step | Where | Notes |
|---|---|---|
| Enable Bedrock model access | Bedrock → Model access | Request access to each model per region. IAM permissions alone are not enough. |
| SES production access | SES → Account dashboard | New accounts start in sandbox mode. Request production access or verify sender + recipient addresses. |

---

## Env files (all manual)

All environment and secret values are maintained in **manually created** env files. Nothing generates or updates these files automatically.

| File | Used by | Notes |
|------|---------|--------|
| `.env` | All overlays | Shared defaults (e.g. `CLUSTER_NAME=doc-router`); gitignored. |
| `.env.kind` | Kind overlay | Kind-specific overrides; gitignored. |
| `.env.eks` | EKS overlay | EKS-specific: `APP_BUCKET_NAME`, `REGION`, ECR URLs, app IAM keys from Terraform outputs; gitignored. |
| `.env.customer-<name>` | Customer overlay | Customer-specific; can target a different AWS account; gitignored. |

**Variables that drive Terraform** (exported as `TF_VAR_<name>` before `terraform apply`):

| Env var | Terraform variable | Example |
|---|---|---|
| `CLUSTER_NAME` | `cluster_name` | `doc-router` |
| `APP_BUCKET_NAME` | `app_bucket_name` | `doc-router-data-prod` |
| `REGION` | `region` | `us-east-1` |
| `VPC_CIDR` | `vpc_cidr` | `10.0.0.0/16` |
| `ENVIRONMENT` | `environment` | `prod` |
| `LETSENCRYPT_EMAIL` | `letsencrypt_email` | required by ACME |

Deploy scripts only **read** env files: they export `TF_VAR_*` for Terraform and render Helm values / Kubernetes Secrets. After the first Terraform apply, copy the app user access key ID and secret from Terraform outputs into the overlay (e.g. `.env.eks`).

---

## Helm chart (`charts/doc-router/`)

The Helm chart is the **single source of truth** for all Kubernetes resources. It replaces the previous Kustomize base + overlays approach.

### Chart design rules

1. **No hardcoded cluster-specific values** — everything cluster-specific comes from Helm values (hostname, ingress class, storage class, image tags, etc.).
2. **Separate Deployments for frontend and backend** — both are part of one Helm release and updated together. Use `RollingUpdate` with `maxUnavailable: 0` on both.
3. **MongoDB is opt-in** — controlled by `mongodb.enabled` in values. Clusters using an external MongoDB set `mongodb.enabled: false` and provide `mongodbUri` in the values Secret.
4. **No `Namespace` resource in the chart** — the namespace is created by the install script (or pre-exists in the customer cluster). Chart resources are scoped to the namespace set in the HelmRelease.
5. **PodDisruptionBudget** — included in the chart to prevent voluntary disruptions from dropping below a floor during upgrades.

### `charts/doc-router/values.yaml` (defaults, no secrets)

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

ingress:
  enabled: true
  className: nginx
  host: ""           # required; set in overlay values
  tls: true
  clusterIssuer: letsencrypt-prod

mongodb:
  enabled: true
  storageClassName: standard    # override per cluster (e.g. gp3 on EKS)
  storage: 10Gi

replicaCount:
  frontend: 2
  backend: 2

resources:
  frontend:
    requests: { cpu: "100m", memory: "256Mi" }
    limits:   { cpu: "500m", memory: "512Mi" }
  backend:
    requests: { cpu: "250m", memory: "512Mi" }
    limits:   { cpu: "1000m", memory: "1Gi" }

# Non-secret config (rendered into ConfigMap by the chart)
config:
  appBucketName: ""
  region: ""
  environment: prod
  nextauthUrl: ""

# Secret values — reference an existing Kubernetes Secret created by the install script
# The HelmRelease uses valuesFrom to merge these into the release.
# secretName: doc-router-secrets
```

### Migration job

`templates/migration-job.yaml` runs as a Helm `pre-upgrade` / `pre-install` hook. It is idempotent (MongoDB schema migrations use up/down scripts that check state). The app Deployments include an `initContainer` that waits for the migration Job's completion marker (a ConfigMap or a readiness endpoint) before the app containers start accepting traffic.

---

## Upgrade stability

### Deployment strategy (must-have)

Both frontend and backend Deployments:

```yaml
strategy:
  type: RollingUpdate
  rollingUpdate:
    maxUnavailable: 0
    maxSurge: 1
```

This guarantees Kubernetes brings up new pods first and only retires old ones after they are ready.

### Health gates (must-have)

- **Readiness probes** on both containers — new pods don't receive traffic until truly ready.
- **Liveness probes** — self-heal on deadlock situations.
- **PodDisruptionBudget** — `minAvailable: 1` on each Deployment; prevents node drains from fully evicting the app.

### Flux HelmRelease health checks (recommended)

```yaml
install:
  remediation:
    retries: 3
upgrade:
  remediation:
    retries: 3
    remediateLastFailure: true
rollback:
  timeout: 5m
```

### Versioning discipline

A single semver version ties together:
- The Helm chart version (in `Chart.yaml`)
- Both container image tags

The deploy workflow builds images tagged `<git-sha>`, publishes the chart at the new semver, and the upgrade script patches the HelmRelease to that version. Rollback patches the version back to the previous release.

---

## Database and migrations

Migrations are the #1 place upgrades break.

### Approach: backward-compatible migrations

1. Migrations only **add** (new fields, indexes, collections) — never drop or rename fields that old code still uses.
2. Deploy the new app version (pods roll safely with mixed-version pods possible during rollout).
3. Optional cleanup migrations run in a later release.

### How migrations run

A dedicated **Helm hook Job** (`pre-upgrade` / `pre-install`) runs the migration script before any pod replacement begins. Requirements:
- The Job must be **idempotent** — safe to re-run on partial failure.
- The app Deployments should not accept traffic until the Job succeeds (enforced via readiness probes and the Flux `upgrade.remediation` policy).

Rollback strategy: MongoDB migrations are forward-only in normal operation. If a rollback is needed, restore from a backup taken before the upgrade.

---

## Flux setup (HelmRelease delivery)

### Chart source: OCI registry

The Helm chart is published as an OCI artifact to ECR (`doc-router/chart`). Flux pulls it using an `OCIRepository` and applies it with a `HelmRelease`.

**Why OCI:**
- Enterprise-friendly: container registries are commonly allowed even when Git hosts are blocked.
- Immutable artifacts: pin exact chart versions.
- Aligns chart distribution with how container images are already distributed.

### `deploy/flux/eks/ocirepository.yaml`

Uses shell variable syntax (`${ECR_ACCOUNT_ID}`, `${REGION}`) filled in via `envsubst` at bootstrap time:

```yaml
apiVersion: source.toolkit.fluxcd.io/v1beta2
kind: OCIRepository
metadata:
  name: doc-router-chart
  namespace: flux-system
spec:
  interval: 1m
  url: oci://${ECR_ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com/doc-router/chart
  ref:
    semver: ">=1.0.0"
  provider: aws
```

### `deploy/flux/eks/helmrelease.yaml`

```yaml
apiVersion: helm.toolkit.fluxcd.io/v2
kind: HelmRelease
metadata:
  name: doc-router
  namespace: doc-router
spec:
  interval: 5m
  chart:
    spec:
      chart: doc-router
      version: "1.4.0"    # pinned; updated by k8s-upgrade.sh
      sourceRef:
        kind: OCIRepository
        name: doc-router-chart
        namespace: flux-system
  values:
    ingress:
      host: app.example.com
      className: nginx
    mongodb:
      storageClassName: gp3
    image:
      frontend:
        repository: ${ECR_ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com/doc-router-frontend
        tag: "abc1234"
      backend:
        repository: ${ECR_ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com/doc-router-backend
        tag: "abc1234"
    config:
      appBucketName: doc-router-data-prod
      region: us-east-1
      environment: prod
      nextauthUrl: https://app.example.com
  valuesFrom:
    - kind: Secret
      name: doc-router-secrets    # created by k8s-install.sh from .env + overlay
  install:
    remediation:
      retries: 3
  upgrade:
    remediation:
      retries: 3
      remediateLastFailure: true
  rollback:
    timeout: 5m
```

The `doc-router-secrets` Kubernetes Secret contains sensitive values rendered by the install/upgrade script from `.env` and the overlay (MongoDB URI, AWS credentials, NextAuth secret, API keys). It is **not** stored in the OCI artifact or committed to the repo.

`prune: true` in the Kustomization that manages the HelmRelease enables self-healing: resources drifted or deleted manually are restored on the next reconcile.

Customer clusters get their own `flux/customer-<name>/` with an `OCIRepository` (same chart registry, or theirs) and a `HelmRelease` pointing at their values.

---

## Deployment scripts

Deploy workflows are invoked via **`mise run <task>`**.

### `deploy/scripts/apply-terraform.sh`

1. Takes two arguments: **overlay name** and **Terraform directory**.
2. Sources `.env` and `.env.<overlay>`, exports `TF_VAR_region`, `TF_VAR_cluster_name`, `TF_VAR_app_bucket_name`, `TF_VAR_vpc_cidr`, `TF_VAR_environment` (and others).
3. Optionally sets `AWS_PROFILE` from the overlay.
4. Runs `terraform init` (if needed) and `terraform apply`.

### `deploy/scripts/build-push.sh`

1. Read AWS account ID (`aws sts get-caller-identity`) and region.
2. Construct ECR URLs for frontend and backend.
3. Log in to ECR: `aws ecr get-login-password | docker login --username AWS --password-stdin`.
4. `docker build --target frontend` and `--target backend` using the multi-stage Dockerfile.
5. Tag with `<ECR_URL>:<git-sha>` (and `:latest`).
6. `docker push` both images.

### `deploy/scripts/publish-chart.sh`

1. Bump `version` in `charts/doc-router/Chart.yaml` to the new semver (or accept it as an argument).
2. Set `appVersion` to the current git SHA.
3. `helm package charts/doc-router` → produces `doc-router-<version>.tgz`.
4. Log in to ECR.
5. `helm push doc-router-<version>.tgz oci://<account>.dkr.ecr.<region>.amazonaws.com/doc-router/chart`

### `deploy/scripts/k8s-install.sh`

First-time install for a cluster. Takes overlay name and chart version as arguments. Assumes Flux is already running (installed by Terraform).

1. Source `.env` + overlay.
2. Create namespace if it doesn't exist.
3. Create (or update) the `doc-router-secrets` Kubernetes Secret from env vars (MongoDB URI, AWS credentials, NextAuth secret, API keys, etc.).
4. Fill in `deploy/flux/<overlay>/ocirepository.yaml` and `helmrelease.yaml` via `envsubst` (ECR account ID, region, image tags, hostname, chart version).
5. `kubectl apply -f` the filled-in OCIRepository and HelmRelease.
6. Wait: `flux reconcile helmrelease doc-router -n doc-router --with-source --timeout=5m`

### `deploy/scripts/k8s-upgrade.sh`

1. Source `.env` + overlay.
2. Build + push images (or accept pre-built tags).
3. Publish new chart version to ECR.
4. (Re-)create/update `doc-router-secrets` if any secret values changed.
5. Patch the HelmRelease `.spec.chart.spec.version` to the new chart version and update image tags in `.spec.values`.
6. `flux reconcile helmrelease doc-router -n doc-router --with-source`
7. Watch: `flux get helmreleases -n doc-router --watch`

### `deploy/scripts/k8s-rollback.sh`

1. Takes overlay name and the previous chart version as arguments.
2. Patch the HelmRelease `.spec.chart.spec.version` back to the previous version and image tags back to the corresponding images.
3. `flux reconcile helmrelease doc-router -n doc-router --with-source`

### Kind (local dev)

`deploy/scripts/deploy-kind.sh` — uses `helm upgrade --install` directly (no Flux required for local dev):

1. Source `.env` + `.env.kind`.
2. Build images locally; `kind load docker-image` both.
3. Create namespace + `doc-router-secrets` Secret.
4. `helm upgrade --install doc-router charts/doc-router -n doc-router --values <rendered-values-file>`

---

## Secrets and configuration

The app is open source; secrets are never stored in the chart repo or OCI artifacts.

Options for managing the `doc-router-secrets` Kubernetes Secret per cluster:

| Option | How |
|---|---|
| **Script-created Secret** (default) | `k8s-install.sh` / `k8s-upgrade.sh` render the Secret from `.env` + overlay and apply it with `kubectl apply`. Simplest path. |
| **External Secrets Operator** | Map values from AWS Secrets Manager or Parameter Store into the Secret. Best for production; requires ESO installed in the cluster (add as a Helm release in Terraform). |
| **SOPS / KSOPS** | Encrypt the values file with customer-managed keys; Flux decrypts on reconcile. Good for customers who want GitOps for secrets too. |

---

## Workflow summary

### First-time setup for a new AWS account

```bash
mise install

export AWS_PROFILE=<account-profile>

# 1. First apply — backend "s3" commented out; creates S3 + DynamoDB + cluster
mise run apply-terraform -- eks deploy/terraform/analytiq-prod

# 2. Uncomment backend "s3" in providers.tf, migrate state to S3
cd deploy/terraform/analytiq-prod
terraform init      # answer "yes" to copy local state → S3
# Re-source .env + overlay and export TF_VAR_*, then:
terraform apply

# 3. Update kubeconfig
set -a; source .env; source .env.eks; set +a
mise run update-kubeconfig

# 4. Build images + publish first chart version
mise run build-push
mise run publish-chart    # creates e.g. 1.0.0

# 5. Bootstrap Flux app (Flux itself installed by Terraform)
mise run k8s-install -- eks 1.0.0
```

### Per-deployment (our EKS)

```bash
export AWS_PROFILE=<account-profile>
mise run deploy-eks    # build-push + publish-chart + k8s-upgrade
```

### Adding a second AWS account

```bash
cp -r deploy/terraform/analytiq-prod deploy/terraform/analytiq-test
# Edit providers.tf: update bucket + dynamodb_table names for state.
# Create .env.eks-test with APP_BUCKET_NAME, REGION, CLUSTER_NAME=doc-router, etc.
# Run first-time setup with the new directory and overlay.
```

### Kind (local dev)

```bash
mise run setup-kind    # once
# Create .env and .env.kind
mise run deploy-kind
```

### Onboarding a customer cluster

1. Copy `deploy/flux/customer-example` to `deploy/flux/customer-<name>`.
2. Create `.env.customer-<name>` with `APP_BUCKET_NAME`, `CLUSTER_NAME`, `REGION`, and any AWS account vars.
3. Point `kubectl` at their cluster.
4. `mise run k8s-install -- customer-<name> <chart-version>`
5. For subsequent upgrades: `mise run k8s-upgrade -- customer-<name> <new-chart-version>`

If provisioning their EKS with Terraform, copy `deploy/terraform/analytiq-prod` to `deploy/terraform/customer-<name>`, update `providers.tf`, and run `mise run apply-terraform -- customer-<name> deploy/terraform/customer-<name>` first.

### Teardown

```bash
export AWS_PROFILE=<account-profile>
cd deploy/terraform/analytiq-prod
terraform destroy
```

### Manual steps in the AWS console

| Step | Where | Notes |
|---|---|---|
| Enable Bedrock model access | Bedrock → Model access | Request access to each model per region. IAM permissions alone are not enough. |
| SES production access | SES → Account dashboard | New accounts start in sandbox mode. Request production access or verify addresses. |
