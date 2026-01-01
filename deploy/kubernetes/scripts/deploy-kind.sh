#!/bin/bash
set -e

# Deploy doc-router to kind cluster
# This script builds images, loads them into kind, and deploys the application

CLUSTER_NAME=${CLUSTER_NAME:-"doc-router"}
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
KIND_OVERLAY="$SCRIPT_DIR/../overlays/kind"

echo "🚀 Deploying doc-router to kind cluster: $CLUSTER_NAME"

# Check if kind cluster exists
if ! kind get clusters | grep -q "^${CLUSTER_NAME}$"; then
    echo "❌ Cluster $CLUSTER_NAME does not exist. Run setup-kind.sh first."
    exit 1
fi

# Check if kubectl is configured
if ! kubectl cluster-info &> /dev/null; then
    echo "❌ kubectl is not configured or cluster is not accessible"
    exit 1
fi

# Build images
echo "🔨 Building Docker images..."
cd "$PROJECT_ROOT"

echo "Building frontend image..."
docker build -t analytiqhub/doc-router-frontend:latest \
  --target frontend \
  --build-arg NEXT_PUBLIC_FASTAPI_FRONTEND_URL=http://localhost:8000 \
  --build-arg NODE_ENV=production \
  -f deploy/shared/docker/Dockerfile .

echo "Building backend image..."
docker build -t analytiqhub/doc-router-backend:latest \
  --target backend \
  -f deploy/shared/docker/Dockerfile .

# Load images into kind
echo "📦 Loading images into kind cluster..."
kind load docker-image analytiqhub/doc-router-frontend:latest --name "$CLUSTER_NAME"
kind load docker-image analytiqhub/doc-router-backend:latest --name "$CLUSTER_NAME"

# Apply secrets (user should customize these)
echo "⚠️  Note: Make sure to update secrets.yaml with your actual secrets before deploying"
read -p "Continue with deployment? (y/N) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Aborted. Update secrets and run again."
    exit 1
fi

# Deploy using kustomize
echo "🚀 Deploying to Kubernetes..."
cd "$KIND_OVERLAY"
kubectl apply -k .

echo ""
echo "⏳ Waiting for deployments to be ready..."
kubectl wait --namespace doc-router \
  --for=condition=available \
  --timeout=300s \
  deployment/frontend deployment/backend deployment/worker

echo ""
echo "✅ Deployment complete!"
echo ""
echo "Check status:"
echo "  kubectl get pods -n doc-router"
echo "  kubectl get services -n doc-router"
echo "  kubectl get ingress -n doc-router"
echo ""
echo "Access the application:"
echo "  Frontend: http://localhost:3000"
echo "  Backend API: http://localhost:8000"
echo ""
