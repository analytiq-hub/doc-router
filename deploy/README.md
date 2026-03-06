# Doc-Router Deployment Guide

This directory contains deployment configurations for doc-router across multiple environments:
- **Docker Compose**: Simple local development and single-node deployments
- **Kubernetes (kind)**: Local Kubernetes testing and development
- **AWS EKS**: Production Kubernetes deployments via Helm OCI charts

## Directory Structure

```
deploy/
├── charts/doc-router/    # Helm chart
├── compose/              # Docker Compose configurations
├── scripts/              # Deployment helper scripts
│   ├── build-push.sh     # Build & push Docker images to ECR
│   ├── publish-chart.sh  # Package & push Helm chart to ECR
│   ├── k8s-deploy.sh     # Install or upgrade on any Kubernetes cluster (idempotent)
│   ├── k8s-rollback.sh   # Helm rollback to previous revision
│   ├── k8s-uninstall.sh  # Tear down the release
│   ├── setup-doks.sh     # One-time cluster add-ons for Digital Ocean DOKS
│   ├── setup-kind.sh     # Create a local kind cluster
│   └── deploy-kind.sh    # Build & deploy to local kind cluster
└── shared/               # Shared resources (Dockerfiles, configs)
```

## AWS EKS Deployment

### Prerequisites

- `aws` CLI, configured with access to the target account
- `docker`
- `helm` >= 3.8 (OCI support)
- `kubectl`, configured against the target cluster (`aws eks update-kubeconfig ...`)

### Environment overlay

Create or populate `.env.<overlay>` at the project root (e.g. `.env.eks-test`):

```bash
REGION=us-east-1
CLUSTER_NAME=doc-router-test
CHART_REGISTRY=<account>.dkr.ecr.us-east-1.amazonaws.com
CHART_REPO_URL=<account>.dkr.ecr.us-east-1.amazonaws.com/doc-router-chart-test
FRONTEND_IMAGE_REPO=<account>.dkr.ecr.us-east-1.amazonaws.com/doc-router-frontend-test
BACKEND_IMAGE_REPO=<account>.dkr.ecr.us-east-1.amazonaws.com/doc-router-backend-test
APP_HOST=test.docrouter.ai
AWS_S3_BUCKET_NAME=docrouter-test
# ... secrets (MONGODB_URI, NEXTAUTH_SECRET, API keys, etc.)
```

`NEXTAUTH_URL` and `NEXT_PUBLIC_FASTAPI_FRONTEND_URL` are derived automatically from `APP_HOST`
and do not need to be set in the overlay file.

### Deploying (fresh install or rolling update)

`k8s-deploy.sh` is idempotent — safe to run on both a fresh cluster and an existing deployment:

```bash
# 1. Build and push Docker images (tag = current git SHA)
./deploy/scripts/build-push.sh eks-test

# 2. Install or upgrade into the cluster
./deploy/scripts/k8s-deploy.sh eks-test
```

Publish the Helm chart first only when `deploy/charts/doc-router/` has changed:

```bash
./deploy/scripts/publish-chart.sh eks-test
./deploy/scripts/k8s-deploy.sh eks-test
```

The script:
- Creates the `doc-router` namespace if it doesn't exist
- Creates or updates the `doc-router-secrets` Kubernetes Secret from your overlay env file
- Runs `helm upgrade --install` (installs on first run, upgrades on subsequent runs)
- Runs `kubectl rollout restart` after helm to ensure pods pick up any Secret changes
- Uses `--atomic` for automatic rollback if the upgrade fails

Database migrations run automatically as a Helm pre-install/pre-upgrade hook before pods are updated.

### Rollback

```bash
# Roll back to the previous Helm revision
./deploy/scripts/k8s-rollback.sh eks-test

# Roll back to a specific revision
./deploy/scripts/k8s-rollback.sh eks-test 3
```

View release history:

```bash
helm history doc-router -n doc-router
```

### Uninstall

```bash
./deploy/scripts/k8s-uninstall.sh eks-test
```

---

## Digital Ocean DOKS Deployment

### Prerequisites

- `doctl` CLI, authenticated (`doctl auth init`)
- `docker`
- `helm` >= 3.8 (OCI support)
- `kubectl`, configured against the target cluster (`doctl kubernetes cluster kubeconfig save <cluster-name>`)

### Environment overlay

Create `.env.do-test` at the project root:

```bash
CLOUD_PROVIDER=do
DOCR_TOKEN=dop_v1_...                          # DO personal access token with registry write access
CHART_REGISTRY=registry.digitalocean.com
CHART_REPO_URL=registry.digitalocean.com/<registry-name>
FRONTEND_IMAGE_REPO=registry.digitalocean.com/<registry-name>/doc-router-frontend
BACKEND_IMAGE_REPO=registry.digitalocean.com/<registry-name>/doc-router-backend
APP_HOST=myapp.example.com
LETSENCRYPT_EMAIL=admin@example.com
REGION=us-east-1                               # AWS region for S3 document storage
AWS_S3_BUCKET_NAME=my-docrouter-bucket
# ... secrets (MONGODB_URI, NEXTAUTH_SECRET, AWS keys for S3, API keys, etc.)
```

The same scripts are used as for EKS — `CLOUD_PROVIDER=do` switches the registry login from
`aws ecr get-login-password` to token-based DOCR authentication.

### First-time cluster setup

Run once after provisioning the DOKS cluster to install ingress-nginx, cert-manager, and
metrics-server, and create the Let's Encrypt ClusterIssuer:

```bash
doctl kubernetes cluster kubeconfig save <cluster-name>
./deploy/scripts/setup-doks.sh do-test
```

After it completes, point your DNS A record for `APP_HOST` to the LoadBalancer IP:

```bash
kubectl get svc -n ingress-nginx ingress-nginx-controller
# Add an A record: APP_HOST → EXTERNAL-IP
```

### Deploying

```bash
# 1. Build and push Docker images
./deploy/scripts/build-push.sh do-test

# 2. Publish the Helm chart (only when chart files have changed)
./deploy/scripts/publish-chart.sh do-test

# 3. Install or upgrade into the cluster
./deploy/scripts/k8s-deploy.sh do-test
```

### Rollback / Uninstall

```bash
./deploy/scripts/k8s-rollback.sh do-test
./deploy/scripts/k8s-uninstall.sh do-test
```

---

## Kubernetes (kind) — Local Testing

### Prerequisites

- `docker`
- `kind`
- `helm` >= 3.8
- `kubectl`

### Setup and deploy

```bash
# 1. Create the kind cluster (one-time)
./deploy/scripts/setup-kind.sh

# 2. Build images and deploy (re-run on every code change)
./deploy/scripts/deploy-kind.sh
```

`deploy-kind.sh` builds Docker images locally, loads them into the kind cluster, deploys MongoDB
in the `mongo` namespace (via Bitnami chart), creates the secrets from your `.env` and `.env.kind`
files, and runs `helm upgrade --install`.

### Access

- Frontend: http://localhost
- API docs:  http://localhost/fastapi/docs

### Cleanup

```bash
kind delete cluster --name doc-router
```

---

## Docker Compose

```bash
cd deploy/compose
docker-compose -f docker-compose.embedded.yml up -d
```

---

## Troubleshooting

**Check pod status:**
```bash
kubectl get pods -n doc-router
kubectl describe pod <pod-name> -n doc-router
kubectl logs <pod-name> -n doc-router
kubectl logs -l app=backend -n doc-router --all-containers
```

**Stream logs from all pods:**
```bash
kubectl logs -f -l app=frontend -n doc-router
kubectl logs -f -l app=backend  -n doc-router
```

**kind — images not found in cluster:**
```bash
kind load docker-image analytiq-hub/doc-router-frontend:<tag> --name doc-router
kind load docker-image analytiq-hub/doc-router-backend:<tag>  --name doc-router
```

**Pods not picking up Secret changes:**

Kubernetes does not restart pods automatically when a Secret changes. `k8s-deploy.sh` handles
this with `kubectl rollout restart`. To do it manually:
```bash
kubectl rollout restart deployment/frontend deployment/backend -n doc-router
```

**Docker Compose — port conflicts:**
- Check if ports 3000, 8000, or 27017 are already in use
- Modify port mappings in `docker-compose.yml`
