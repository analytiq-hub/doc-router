# Doc-Router Deployment Guide

This directory contains deployment configurations for doc-router across multiple environments:
- **Docker Compose**: Simple local development and single-node deployments
- **Kubernetes (kind)**: Local Kubernetes testing and development
- **AWS EKS**: Production Kubernetes deployments (coming soon)

## Directory Structure

```
deploy/
├── compose/              # Docker Compose configurations
├── kubernetes/           # Kubernetes manifests
│   ├── base/            # Base Kustomize configuration
│   ├── overlays/        # Environment-specific overlays
│   └── scripts/         # Deployment helper scripts
└── shared/              # Shared resources (Dockerfiles, configs, docs)
```

## Quick Start

### Docker Compose

```bash
cd deploy/compose
docker-compose -f docker-compose.embedded.yml up -d
```

### Kubernetes (kind)

1. **Setup kind cluster:**
   ```bash
   cd deploy/kubernetes/scripts
   ./setup-kind.sh
   ```

2. **Deploy application:**
   ```bash
   ./deploy-kind.sh
   ```

3. **Access the application:**
   - Frontend: http://localhost:3000
   - Backend API: http://localhost:8000

4. **Cleanup:**
   ```bash
   ./cleanup.sh
   ```

## Prerequisites

### Docker Compose
- Docker
- Docker Compose

### Kubernetes (kind)
- Docker
- kind (Kubernetes in Docker)
- kubectl
- kustomize (usually comes with kubectl)

## Environment Variables

All environment variables are managed through:
- **Docker Compose**: `.env` file or environment variables
- **Kubernetes**: ConfigMaps and Secrets

See `kubernetes/base/configmap.yaml` and `kubernetes/base/secrets.yaml` for configuration options.

**Important**: Update `secrets.yaml` with your actual secrets before deploying to production!

## Documentation

- [Docker Compose Guide](./shared/docs/compose.md)
- [kind Deployment Guide](./shared/docs/kind.md)
- [EKS Deployment Guide](./shared/docs/eks.md) (coming soon)

## Troubleshooting

### kind Issues

**Cluster not starting:**
```bash
kind delete cluster --name doc-router
./setup-kind.sh
```

**Images not loading:**
```bash
kind load docker-image analytiqhub/doc-router-frontend:latest --name doc-router
kind load docker-image analytiqhub/doc-router-backend:latest --name doc-router
```

**Check pod status:**
```bash
kubectl get pods -n doc-router
kubectl describe pod <pod-name> -n doc-router
kubectl logs <pod-name> -n doc-router
```

### Docker Compose Issues

**Port conflicts:**
- Check if ports 3000, 8000, or 27017 are already in use
- Modify port mappings in `docker-compose.yml`

**MongoDB connection issues:**
- Ensure MongoDB is running and accessible
- Check `MONGODB_URI` environment variable

## Next Steps

1. Review and customize `kubernetes/base/secrets.yaml` with your secrets
2. Update ConfigMaps for your environment
3. Deploy to kind for testing
4. Prepare for EKS deployment (see `PLANNING.md`)
