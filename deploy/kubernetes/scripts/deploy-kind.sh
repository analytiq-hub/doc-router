#!/bin/bash
set -e

# Deploy doc-router to kind cluster
# This script builds images, loads them into kind, and deploys the application

CLUSTER_NAME=${CLUSTER_NAME:-"doc-router"}
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
KIND_OVERLAY="$SCRIPT_DIR/../overlays/kind"
BASE_DIR="$SCRIPT_DIR/.."

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

# Generate Kubernetes config from .env files
echo "📝 Generating Kubernetes ConfigMap and Secrets from .env files..."
cd "$PROJECT_ROOT"

# Merge .env and .env.kind (if exists) for kind deployment
MERGED_ENV=$(mktemp)
cat .env > "$MERGED_ENV"
if [ -f .env.kind ]; then
    cat .env.kind >> "$MERGED_ENV"
fi

# Generate ConfigMap and Secrets
"$SCRIPT_DIR/generate-k8s-config.sh" "$MERGED_ENV" "$BASE_DIR/base"

# Read NEXT_PUBLIC_FASTAPI_FRONTEND_URL from merged env file for frontend build
NEXT_PUBLIC_FASTAPI_FRONTEND_URL=$(grep "^NEXT_PUBLIC_FASTAPI_FRONTEND_URL=" "$MERGED_ENV" 2>/dev/null | tail -1 | cut -d= -f2- | sed 's/^"//;s/"$//' | sed 's/#.*$//' | xargs)
if [ -z "$NEXT_PUBLIC_FASTAPI_FRONTEND_URL" ]; then
    NEXT_PUBLIC_FASTAPI_FRONTEND_URL="http://localhost:8000"
    echo "⚠️  Warning: NEXT_PUBLIC_FASTAPI_FRONTEND_URL not found in .env files, using default: $NEXT_PUBLIC_FASTAPI_FRONTEND_URL"
fi
rm "$MERGED_ENV"

# Build images
echo "🔨 Building Docker images..."
cd "$PROJECT_ROOT"

echo "Building frontend image with NEXT_PUBLIC_FASTAPI_FRONTEND_URL=$NEXT_PUBLIC_FASTAPI_FRONTEND_URL..."
docker build -t analytiqhub/doc-router-frontend:latest \
  --target frontend \
  --build-arg NEXT_PUBLIC_FASTAPI_FRONTEND_URL="$NEXT_PUBLIC_FASTAPI_FRONTEND_URL" \
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

# Deploy using kustomize
echo "🚀 Deploying to Kubernetes..."
cd "$KIND_OVERLAY"
kubectl apply -k .

# Restart deployments to pick up new images and ConfigMap changes
echo "🔄 Restarting deployments to pick up new images and configuration..."
kubectl rollout restart deployment/frontend deployment/backend deployment/worker -n doc-router

echo ""
echo "⏳ Waiting for deployments to be ready..."
kubectl wait --namespace doc-router \
  --for=condition=available \
  --timeout=300s \
  deployment/frontend deployment/backend deployment/worker || true

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
echo "  Backend API: $NEXT_PUBLIC_FASTAPI_FRONTEND_URL"
echo ""
