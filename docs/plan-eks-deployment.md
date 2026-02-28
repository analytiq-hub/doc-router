# EKS deployment plan

## Goals

- Deploy doc-router to AWS EKS (our own cluster, one or more namespaces).
- Deploy doc-router to a customer's existing Kubernetes cluster (any provider).
- Docker images built from the existing multi-stage Dockerfile, stored in ECR.
- Terraform manages all AWS infrastructure; Kustomize overlays manage all Kubernetes resources.

---

## Repository layout

```
doc-router/
  deploy/
    terraform/
      analytiq-prod/     # our production account
      analytiq-test/     # our test/staging account
      customer-<name>/   # if we ever provision EKS for a customer
      .gitignore         # *.tfvars, .terraform/, terraform.tfstate*
    kubernetes/
      base/              # shared, cluster-agnostic app manifests
      overlays/
        kind/            # local dev (existing)
        eks/             # our hosted EKS instance(s)
        customer-example/ # template — copy per customer cluster
```

Each directory under `deploy/terraform/` is an independent root module for one AWS account. `terraform.tfvars` and state files are gitignored so account IDs, CIDRs, and secrets never reach the public repo.

Customer clusters with a ready-made Kubernetes environment only need a Kustomize overlay — no Terraform.

---

## Terraform (`deploy/terraform/<account>/`)

Each account directory is self-contained: its own `providers.tf` with a hardcoded backend for that account's S3 bucket. No flags to remember, no risk of applying to the wrong account.

```
deploy/terraform/analytiq-prod/
  main.tf           # VPC + EKS + ECR + IAM + Helm releases + S3/DynamoDB for tf state
  providers.tf      # aws + helm providers; backend "s3" commented out until first apply
  variables.tf
  outputs.tf
  terraform.tfvars  # gitignored — region, CIDR, cluster name, etc.
```

Adding a new account: `cp -r analytiq-prod <new-account>`, update `providers.tf` (bucket/table names) and `terraform.tfvars`.

### Remote state (same pattern as `analytiq-terraform`)

S3 bucket and DynamoDB table defined directly in `main.tf` alongside all other resources:

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
# Evaluated lazily — works in the same apply as the cluster creation.
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
- 2 public subnets (Traefik LoadBalancer, NAT gateway) across 2 AZs.
- 2 private subnets (worker nodes) across 2 AZs.
- One NAT gateway.

### EKS

Use `terraform-aws-modules/eks/aws`:

- Cluster and nodes in private subnets.
- Managed node group: `t3.medium` or `t3.large`, min/desired/max = 2/2/5.
- OIDC provider enabled (for future IRSA use, e.g. External Secrets Operator).

### ECR (inline in `main.tf`)

Two `aws_ecr_repository` resources: `doc-router-frontend`, `doc-router-backend`. Optional lifecycle policy to keep the last N images.

### IAM (inline in `main.tf`)

Node group role: `AmazonEKSWorkerNodePolicy`, `AmazonEKS_CNI_Policy`, `AmazonEC2ContainerRegistryReadOnly`.

No EBS CSI driver or IRSA role needed — MongoDB is external and there are no in-cluster PVCs.

### Helm releases (inline in `main.tf`)

| Chart | Purpose |
|---|---|
| `traefik/traefik` | Ingress controller, exposes an AWS NLB |
| `jetstack/cert-manager` | TLS certificate automation via Let's Encrypt |
| `metrics-server` | Enables HPA |

Traefik watches all namespaces by default — no extra config needed per namespace.

A single `ClusterIssuer` for Let's Encrypt is applied via a `null_resource` local-exec with `depends_on = [helm_release.cert_manager]` and a readiness check before applying the issuer YAML.

### Key outputs

- `cluster_name`, `frontend_repo_url`, `backend_repo_url`

---

## Kubernetes manifests (`deploy/kubernetes/`)

### Design rules for multi-namespace support

1. **`base/` owns no `Namespace` resource** — each overlay provides its own `namespace.yaml`.
2. **`base/` sets no `ingressClassName`, `host`, or TLS** in the Ingress — overlays own those.
3. **`base/` does not include `configmap.yaml` or `secrets.yaml`** — each overlay generates and includes its own.
4. Each overlay sets `namespace:` in its `kustomization.yaml`; Kustomize rewrites all resource namespaces automatically.
5. Use `labels:` (not `commonLabels:`) in overlays — `commonLabels` also mutates pod selectors and breaks rolling updates on existing Deployments.

### `deploy/kubernetes/base/`

- No `namespace.yaml`, no `configmap.yaml`, no `secrets.yaml`.
- `base/frontend/ingress.yaml`: path rules only, no `ingressClassName`/`host`/`tls`.
- `base/mongodb/` deleted — MongoDB is external; `MONGODB_URI` comes from each overlay's `secrets.yaml`.

### `deploy/kubernetes/overlays/eks/`

```
overlays/eks/
  kustomization.yaml
  namespace.yaml
  ingress-patch.yaml
  configmap.yaml    # gitignored — generated by deploy-eks.sh
  secrets.yaml      # gitignored — generated by deploy-eks.sh
```

**`kustomization.yaml`**:

```yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization

namespace: doc-router

resources:
  - ../../base
  - namespace.yaml
  - configmap.yaml
  - secrets.yaml

patches:
  - path: ingress-patch.yaml
    target:
      kind: Ingress
      name: frontend-ingress

images:
  - name: analytiqhub/doc-router-frontend
    newName: <ECR_FRONTEND_URL>
    newTag: <TAG>
  - name: analytiqhub/doc-router-backend
    newName: <ECR_BACKEND_URL>
    newTag: <TAG>

labels:
  - pairs:
      environment: eks
    includeSelectors: false
```

**`ingress-patch.yaml`**: sets `ingressClassName: traefik`, real hostname, TLS spec, and `cert-manager.io/cluster-issuer: letsencrypt-prod` annotation.

### `deploy/kubernetes/overlays/customer-example/`

```
overlays/customer-example/
  kustomization.yaml
  namespace.yaml       # name: doc-router (or doc-router-<customer>)
  ingress-patch.yaml   # their ingress class, hostname, TLS secret
  configmap.yaml       # gitignored — generated by deploy-customer.sh
  secrets.yaml         # gitignored — generated by deploy-customer.sh
```

**`kustomization.yaml`**:

```yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization

namespace: doc-router

resources:
  - ../../base
  - namespace.yaml
  - configmap.yaml
  - secrets.yaml

patches:
  - path: ingress-patch.yaml
    target:
      kind: Ingress
      name: frontend-ingress

images:
  - name: analytiqhub/doc-router-frontend
    newName: <REGISTRY>/doc-router-frontend
    newTag: <TAG>
  - name: analytiqhub/doc-router-backend
    newName: <REGISTRY>/doc-router-backend
    newTag: <TAG>

labels:
  - pairs:
      customer: example
    includeSelectors: false
```

`ingress-patch.yaml` sets the customer's ingress class (`nginx`, `traefik`, `alb`, `gce`, etc.) and hostname. `MONGODB_URI` in `secrets.yaml` points to their MongoDB instance.

---

## Deployment scripts

### `deploy/kubernetes/scripts/build-push-eks.sh`

1. Read AWS account ID (`aws sts get-caller-identity`) and region.
2. Construct ECR URLs for frontend and backend.
3. Log in to ECR: `aws ecr get-login-password | docker login --username AWS --password-stdin <account>.dkr.ecr.<region>.amazonaws.com`.
4. `docker build --target frontend` and `--target backend` using `deploy/shared/docker/Dockerfile`.
5. Tag with `<ECR_URL>:<git-sha>` (and `:latest`).
6. `docker push` both images.

### `deploy/kubernetes/scripts/deploy-eks.sh`

Assumes Terraform has run and `kubectl` context points at the cluster.

1. Merge `.env` + `.env.eks`.
2. Run `generate-k8s-config.sh` with output directory set to `deploy/kubernetes/overlays/eks/` to generate `configmap.yaml` and `secrets.yaml` there.
3. `kustomize edit set image` in `overlays/eks/kustomization.yaml` to pin image tags.
4. `kubectl apply -k deploy/kubernetes/overlays/eks`
5. `kubectl rollout status deployment/frontend -n doc-router`
6. `kubectl rollout status deployment/backend -n doc-router`
7. `kubectl rollout status deployment/worker -n doc-router`

### `deploy/kubernetes/scripts/deploy-customer.sh`

Takes overlay name as argument (e.g. `customer-acme`).

1. Merge `.env` + `.env.customer-<name>`.
2. Run `generate-k8s-config.sh` with output directory set to `deploy/kubernetes/overlays/<overlay-name>/`.
3. Optionally update image tags in that overlay's kustomization.
4. `kubectl apply -k deploy/kubernetes/overlays/<overlay-name>`.
5. `kubectl rollout status` for frontend, backend, and worker in that namespace.

---

## Workflow summary

### First-time setup for a new AWS account

```bash
export AWS_PROFILE=<account-profile>

# 1. First apply — backend "s3" commented out; creates S3 + DynamoDB + cluster
cd deploy/terraform/analytiq-prod
terraform init && terraform apply

# 2. Uncomment backend "s3" in providers.tf, then migrate state to S3
terraform init      # answer "yes" to copy local state → S3
terraform apply

# 3. Update kubeconfig
aws eks update-kubeconfig --name doc-router --region <region>
```

### Adding a second AWS account

```bash
cp -r deploy/terraform/analytiq-prod deploy/terraform/analytiq-test
# Edit providers.tf: update bucket + dynamodb_table names
# Edit terraform.tfvars: update region, CIDR, cluster name, etc.
# Then run the first-time setup above with the new directory and AWS_PROFILE
```

### Per-deployment (our EKS)

```bash
export AWS_PROFILE=<account-profile>
deploy/kubernetes/scripts/build-push-eks.sh
deploy/kubernetes/scripts/deploy-eks.sh
```

### Onboarding a customer cluster

1. Copy `overlays/customer-example` to `overlays/customer-<name>`.
2. Fill in `namespace.yaml` and `ingress-patch.yaml`.
3. Create `.env.customer-<name>` locally (gitignored).
4. Point `kubectl` at their cluster.
5. `./deploy-customer.sh customer-<name>`

### Teardown

```bash
export AWS_PROFILE=<account-profile>
cd deploy/terraform/analytiq-prod
terraform destroy
```
