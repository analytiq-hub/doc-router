#!/bin/bash
# Deploy doc-router to a local Kind cluster using Helm.
# Usage: ./deploy/scripts/deploy-kind.sh
# Reads .env and .env.kind from the repo root for build args and secrets.

set -e

CLUSTER_NAME=${CLUSTER_NAME:-"doc-router"}
NAMESPACE="doc-router"
RELEASE="doc-router"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
CHART_DIR="$PROJECT_ROOT/deploy/charts/doc-router"
VALUES_KIND="$SCRIPT_DIR/values-kind.yaml"

cd "$PROJECT_ROOT"

# --- Preflight checks ---
if ! kind get clusters 2>/dev/null | grep -q "^${CLUSTER_NAME}$"; then
    echo "Cluster '$CLUSTER_NAME' not found. Run ./deploy/scripts/setup-kind.sh first."
    exit 1
fi

if ! kubectl cluster-info &>/dev/null; then
    echo "kubectl cannot reach the cluster. Check your kubeconfig."
    exit 1
fi

# --- Load env files ---
# .env.kind values override .env values (sourced second).
set -a
[ -f "$PROJECT_ROOT/.env" ]      && source "$PROJECT_ROOT/.env"
[ -f "$PROJECT_ROOT/.env.kind" ] && source "$PROJECT_ROOT/.env.kind"
set +a
#
# IMAGE_TAG can be provided from the environment (e.g. IMAGE_TAG=abc123 make deploy-kind).
# If not provided, default to a timestamp-based tag so every deploy gets a unique image tag.
IMAGE_TAG="${IMAGE_TAG:-$(date +%Y%m%d%H%M%S)}"
echo "Using image tag: $IMAGE_TAG"

# --- Build images ---
echo "Building frontend image..."
docker build -t analytiqhub/doc-router-frontend:"$IMAGE_TAG" \
  --target runner \
  --build-arg NODE_ENV=production \
  -f deploy/shared/docker/Dockerfile .

echo "Building backend image..."
docker build -t analytiqhub/doc-router-backend:"$IMAGE_TAG" \
  --target backend \
  -f deploy/shared/docker/Dockerfile .

# --- Load images into Kind ---
echo "Loading images into Kind cluster '$CLUSTER_NAME'..."
kind load docker-image analytiqhub/doc-router-frontend:"$IMAGE_TAG" --name "$CLUSTER_NAME"
kind load docker-image analytiqhub/doc-router-backend:"$IMAGE_TAG"  --name "$CLUSTER_NAME"

# --- MongoDB (in its own namespace, no auth for local dev) ---
echo "Deploying MongoDB in 'mongo' namespace..."
helm repo add bitnami https://charts.bitnami.com/bitnami 2>/dev/null || true
helm repo update bitnami
helm upgrade --install mongodb bitnami/mongodb \
  --namespace mongo --create-namespace \
  --set auth.enabled=false \
  --set persistence.size=1Gi \
  --wait --timeout 3m
MONGODB_URI="mongodb://mongodb.mongo.svc.cluster.local:27017/"

# --- Namespace ---
kubectl create namespace "$NAMESPACE" --dry-run=client -o yaml | kubectl apply -f -

# --- Create/update the doc-router-secrets Secret ---
# All sensitive values come from .env + .env.kind. Nothing sensitive is passed to Helm.
echo "Applying doc-router-secrets..."
kubectl create secret generic doc-router-secrets \
  --namespace "$NAMESPACE" \
  --from-literal=NEXTAUTH_SECRET="${NEXTAUTH_SECRET}" \
  --from-literal=MONGODB_URI="${MONGODB_URI}" \
  --from-literal=ADMIN_EMAIL="${ADMIN_EMAIL}" \
  --from-literal=ADMIN_PASSWORD="${ADMIN_PASSWORD}" \
  --from-literal=AWS_ACCESS_KEY_ID="${AWS_ACCESS_KEY_ID}" \
  --from-literal=AWS_SECRET_ACCESS_KEY="${AWS_SECRET_ACCESS_KEY}" \
  --from-literal=AWS_S3_BUCKET_NAME="${AWS_S3_BUCKET_NAME}" \
  --from-literal=OPENAI_API_KEY="${OPENAI_API_KEY}" \
  --from-literal=ANTHROPIC_API_KEY="${ANTHROPIC_API_KEY}" \
  --from-literal=GEMINI_API_KEY="${GEMINI_API_KEY}" \
  --from-literal=GROQ_API_KEY="${GROQ_API_KEY}" \
  --from-literal=MISTRAL_API_KEY="${MISTRAL_API_KEY}" \
  --from-literal=SES_FROM_EMAIL="${SES_FROM_EMAIL}" \
  --from-literal=STRIPE_SECRET_KEY="${STRIPE_SECRET_KEY}" \
  --from-literal=STRIPE_WEBHOOK_SECRET="${STRIPE_WEBHOOK_SECRET}" \
  --from-literal=STRIPE_PRODUCT_TAG="${STRIPE_PRODUCT_TAG}" \
  --from-literal=AUTH_GITHUB_ID="${AUTH_GITHUB_ID}" \
  --from-literal=AUTH_GITHUB_SECRET="${AUTH_GITHUB_SECRET}" \
  --from-literal=AUTH_GOOGLE_ID="${AUTH_GOOGLE_ID}" \
  --from-literal=AUTH_GOOGLE_SECRET="${AUTH_GOOGLE_SECRET}" \
  --dry-run=client -o yaml | kubectl apply -f -

# --- Helm deploy ---
echo "Running helm upgrade --install..."
helm upgrade --install "$RELEASE" "$CHART_DIR" \
  --namespace "$NAMESPACE" \
  --values "$VALUES_KIND" \
  --set image.frontend.tag="$IMAGE_TAG" \
  --set image.backend.tag="$IMAGE_TAG" \
  --atomic \
  --timeout 5m \
  --wait

echo ""
echo "Deployment complete!"
echo "  kubectl get pods -n $NAMESPACE"
echo "  kubectl get ingress -n $NAMESPACE"
echo "  Frontend: http://localhost"
echo "  API docs: http://localhost/fastapi/docs"
