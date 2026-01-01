# kind Deployment Guide

This guide covers deploying doc-router to a local Kubernetes cluster using kind (Kubernetes in Docker).

## Prerequisites

1. **Install kind:**
   ```bash
   curl -Lo ./kind https://kind.sigs.k8s.io/dl/v0.20.0/kind-linux-amd64
   chmod +x ./kind
   sudo mv ./kind /usr/local/bin/kind
   ```

2. **Install kubectl:**
   ```bash
   # Ubuntu/Debian
   curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl"
   sudo install -o root -g root -m 0755 kubectl /usr/local/bin/kubectl
   ```

3. **Verify installations:**
   ```bash
   kind version
   kubectl version --client
   ```

## Setup

### 1. Create kind Cluster

Run the setup script:

```bash
cd deploy/kubernetes/scripts
./setup-kind.sh
```

This script will:
- Create a kind cluster named `doc-router`
- Configure port mappings (80, 443, 3000, 8000)
- Install NGINX Ingress Controller
- Set up local registry support

### 2. Configure Secrets

Before deploying, update the secrets file with your actual values:

```bash
cd deploy/kubernetes/base
# Edit secrets.yaml with your actual API keys, etc.
```

**Important**: Never commit actual secrets to git! Use a secrets management tool or environment variables in production.

### 3. Build and Deploy

Use the deployment script:

```bash
cd deploy/kubernetes/scripts
./deploy-kind.sh
```

This script will:
- Build Docker images for frontend and backend
- Load images into the kind cluster
- Deploy all Kubernetes resources using Kustomize

### Manual Deployment

If you prefer to deploy manually:

```bash
# Build images
docker build -t analytiqhub/doc-router-frontend:latest --target frontend -f deploy/shared/docker/Dockerfile .
docker build -t analytiqhub/doc-router-backend:latest --target backend -f deploy/shared/docker/Dockerfile .

# Load into kind
kind load docker-image analytiqhub/doc-router-frontend:latest --name doc-router
kind load docker-image analytiqhub/doc-router-backend:latest --name doc-router

# Deploy
cd deploy/kubernetes/overlays/kind
kubectl apply -k .
```

## Accessing the Application

After deployment, access the application:

- **Frontend**: http://localhost:3000
- **Backend API**: http://localhost:8000
- **Ingress**: http://localhost (if configured)

## Verifying Deployment

Check the status of your deployment:

```bash
# Check all resources
kubectl get all -n doc-router

# Check pods
kubectl get pods -n doc-router

# Check services
kubectl get services -n doc-router

# Check ingress
kubectl get ingress -n doc-router

# View logs
kubectl logs -f deployment/frontend -n doc-router
kubectl logs -f deployment/backend -n doc-router
kubectl logs -f deployment/worker -n doc-router
```

## Troubleshooting

### Pods Not Starting

```bash
# Check pod status
kubectl describe pod <pod-name> -n doc-router

# Check events
kubectl get events -n doc-router --sort-by='.lastTimestamp'
```

### Image Pull Errors

If you see `ImagePullBackOff` errors:

1. Verify images are loaded:
   ```bash
   docker images | grep doc-router
   ```

2. Reload images:
   ```bash
   kind load docker-image analytiqhub/doc-router-frontend:latest --name doc-router
   kind load docker-image analytiqhub/doc-router-backend:latest --name doc-router
   ```

### MongoDB Connection Issues

```bash
# Check MongoDB pod
kubectl get pods -n doc-router | grep mongodb
kubectl logs -f statefulset/mongodb -n doc-router

# Test MongoDB connection
kubectl exec -it mongodb-0 -n doc-router -- mongosh -u admin -p admin
```

### Port Already in Use

If ports 3000 or 8000 are already in use:

1. Modify the kind cluster configuration in `setup-kind.sh`
2. Or use port forwarding:
   ```bash
   kubectl port-forward service/frontend 3000:3000 -n doc-router
   kubectl port-forward service/backend 8000:8000 -n doc-router
   ```

## Updating the Deployment

After making changes:

```bash
# Rebuild images
docker build -t analytiqhub/doc-router-frontend:latest --target frontend -f deploy/shared/docker/Dockerfile .
docker build -t analytiqhub/doc-router-backend:latest --target backend -f deploy/shared/docker/Dockerfile .

# Reload into kind
kind load docker-image analytiqhub/doc-router-frontend:latest --name doc-router
kind load docker-image analytiqhub/doc-router-backend:latest --name doc-router

# Restart deployments
kubectl rollout restart deployment/frontend -n doc-router
kubectl rollout restart deployment/backend -n doc-router
kubectl rollout restart deployment/worker -n doc-router
```

## Cleanup

To remove all resources:

```bash
cd deploy/kubernetes/scripts
./cleanup.sh
```

Or manually:

```bash
# Delete resources
cd deploy/kubernetes/overlays/kind
kubectl delete -k .

# Delete namespace
kubectl delete namespace doc-router

# Delete kind cluster
kind delete cluster --name doc-router
```

## Next Steps

- Review the base Kubernetes manifests in `deploy/kubernetes/base/`
- Customize the kind overlay in `deploy/kubernetes/overlays/kind/`
- Prepare for EKS deployment (see `deploy/shared/docs/eks.md`)
