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
├── kubernetes/           # kind Kubernetes manifests (Kustomize)
│   ├── base/
│   └── overlays/
├── scripts/              # Deployment helper scripts
│   ├── build-push.sh     # Build & push Docker images to ECR
│   ├── publish-chart.sh  # Package & push Helm chart to ECR
│   ├── k8s-install.sh    # First-time Helm install
│   ├── k8s-upgrade.sh    # Helm upgrade (rolling deploy)
│   ├── k8s-rollback.sh   # Helm rollback to previous revision
│   └── k8s-uninstall.sh  # Tear down the release
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
STORAGE_CLASS=gp3
APP_HOST=test.docrouter.ai
NEXTAUTH_URL=https://test.docrouter.ai
AWS_S3_BUCKET_NAME=docrouter-test
# ... secrets (MONGODB_URI, NEXTAUTH_SECRET, API keys, etc.)
```

### First-time deployment

```bash
# 1. Build and push Docker images (tag = current git SHA)
./deploy/scripts/build-push.sh eks-test

# 2. Publish the Helm chart (version from deploy/charts/doc-router/Chart.yaml)
./deploy/scripts/publish-chart.sh eks-test

# 3. Install into the cluster
./deploy/scripts/k8s-install.sh eks-test
```

### Rolling update (existing cluster)

```bash
./deploy/scripts/build-push.sh eks-test
./deploy/scripts/k8s-upgrade.sh eks-test
```

Publish the chart first only when `deploy/charts/doc-router/` has changed:

```bash
./deploy/scripts/publish-chart.sh eks-test
./deploy/scripts/k8s-upgrade.sh eks-test
```

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

## Kubernetes (kind) — Local Testing

1. **Setup kind cluster:**
   ```bash
   ./deploy/kubernetes/scripts/setup-kind.sh
   ```

2. **Deploy application:**
   ```bash
   ./deploy/kubernetes/scripts/deploy-kind.sh
   ```

3. **Access the application:**
   - Frontend: http://localhost:3000
   - Backend API: http://localhost:8000

4. **Cleanup:**
   ```bash
   ./deploy/kubernetes/scripts/cleanup.sh
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
```

**kind — images not loading:**
```bash
kind load docker-image analytiqhub/doc-router-frontend:latest --name doc-router
kind load docker-image analytiqhub/doc-router-backend:latest --name doc-router
```

**Docker Compose — port conflicts:**
- Check if ports 3000, 8000, or 27017 are already in use
- Modify port mappings in `docker-compose.yml`
