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

# NEXT_PUBLIC_FASTAPI_FRONTEND_URL is baked into the Next.js build at build time.
NEXT_PUBLIC_FASTAPI_FRONTEND_URL="${NEXT_PUBLIC_FASTAPI_FRONTEND_URL:-http://localhost/fastapi}"

# --- Build images ---
echo "Building frontend image..."
docker build -t analytiqhub/doc-router-frontend:latest \
  --target frontend \
  --build-arg NEXT_PUBLIC_FASTAPI_FRONTEND_URL="$NEXT_PUBLIC_FASTAPI_FRONTEND_URL" \
  --build-arg NODE_ENV=production \
  -f deploy/shared/docker/Dockerfile .

echo "Building backend image..."
docker build -t analytiqhub/doc-router-backend:latest \
  --target backend \
  -f deploy/shared/docker/Dockerfile .

# --- Load images into Kind ---
echo "Loading images into Kind cluster '$CLUSTER_NAME'..."
kind load docker-image analytiqhub/doc-router-frontend:latest --name "$CLUSTER_NAME"
kind load docker-image analytiqhub/doc-router-backend:latest  --name "$CLUSTER_NAME"

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
  --atomic \
  --timeout 5m \
  --wait

echo ""
echo "Deployment complete!"
echo "  kubectl get pods -n $NAMESPACE"
echo "  kubectl get ingress -n $NAMESPACE"
echo "  Frontend: http://localhost"
echo "  API docs: http://localhost/fastapi/docs"
