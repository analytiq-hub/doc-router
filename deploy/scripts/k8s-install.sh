#!/bin/bash
# First-time install of doc-router into any Kubernetes cluster.
# Usage: ./deploy/scripts/k8s-install.sh <overlay> <chart-version>
#   overlay        — env overlay name, e.g. "eks" or "customer-acme"
#   chart-version  — semver of the OCI chart to install, e.g. "1.0.0"
#
# IMAGE_TAG may be set in the environment; defaults to the current git SHA.
# Required env vars (from overlay): CHART_REGISTRY, FRONTEND_IMAGE_REPO,
#   BACKEND_IMAGE_REPO, REGION, APP_HOST, NEXTAUTH_URL, APP_BUCKET_NAME,
#   STORAGE_CLASS, plus all secret vars (MONGODB_URI, AWS_ACCESS_KEY_ID, etc.).

set -eo pipefail

OVERLAY=${1:?"Usage: $0 <overlay> <chart-version>"}
CHART_VERSION=${2:?"Usage: $0 <overlay> <chart-version>"}

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

NAMESPACE="doc-router"
RELEASE="doc-router"

cd "$PROJECT_ROOT"

# --- Load env files ---
set -a
[ -f "$PROJECT_ROOT/.env" ]          && source "$PROJECT_ROOT/.env"
[ -f "$PROJECT_ROOT/.env.$OVERLAY" ] && source "$PROJECT_ROOT/.env.$OVERLAY"
set +a

: "${CHART_REGISTRY:?".env.$OVERLAY must set CHART_REGISTRY"}"
: "${FRONTEND_IMAGE_REPO:?".env.$OVERLAY must set FRONTEND_IMAGE_REPO"}"
: "${BACKEND_IMAGE_REPO:?".env.$OVERLAY must set BACKEND_IMAGE_REPO"}"
: "${REGION:?".env.$OVERLAY must set REGION"}"
: "${APP_HOST:?".env.$OVERLAY must set APP_HOST"}"
: "${NEXTAUTH_URL:?".env.$OVERLAY must set NEXTAUTH_URL"}"
: "${APP_BUCKET_NAME:?".env.$OVERLAY must set APP_BUCKET_NAME"}"
: "${STORAGE_CLASS:?".env.$OVERLAY must set STORAGE_CLASS"}"

IMAGE_TAG="${IMAGE_TAG:-$(git rev-parse --short HEAD)}"
echo "Chart version : $CHART_VERSION"
echo "Image tag     : $IMAGE_TAG"
echo "Cluster host  : $APP_HOST"

# --- Namespace ---
echo "Creating namespace '$NAMESPACE'..."
kubectl create namespace "$NAMESPACE" --dry-run=client -o yaml | kubectl apply -f -

# --- Create/update the doc-router-secrets Secret ---
echo "Applying doc-router-secrets..."
kubectl create secret generic doc-router-secrets \
  --namespace "$NAMESPACE" \
  --from-literal=NEXTAUTH_SECRET="${NEXTAUTH_SECRET}" \
  --from-literal=MONGODB_URI="${MONGODB_URI}" \
  --from-literal=ADMIN_EMAIL="${ADMIN_EMAIL}" \
  --from-literal=ADMIN_PASSWORD="${ADMIN_PASSWORD}" \
  --from-literal=AWS_ACCESS_KEY_ID="${AWS_ACCESS_KEY_ID}" \
  --from-literal=AWS_SECRET_ACCESS_KEY="${AWS_SECRET_ACCESS_KEY}" \
  --from-literal=AWS_S3_BUCKET_NAME="${APP_BUCKET_NAME}" \
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

# --- ECR login for Helm ---
echo "Logging in to ECR ($CHART_REGISTRY)..."
aws ecr get-login-password --region "$REGION" \
  | helm registry login --username AWS --password-stdin "$CHART_REGISTRY"

# --- Helm install ---
echo "Running helm upgrade --install..."
helm upgrade --install "$RELEASE" \
  "oci://$CHART_REGISTRY/doc-router-chart" \
  --version "$CHART_VERSION" \
  --namespace "$NAMESPACE" \
  --set image.frontend.repository="$FRONTEND_IMAGE_REPO" \
  --set image.backend.repository="$BACKEND_IMAGE_REPO" \
  --set image.frontend.tag="$IMAGE_TAG" \
  --set image.backend.tag="$IMAGE_TAG" \
  --set ingress.host="$APP_HOST" \
  --set ingress.className=nginx \
  --set mongodb.storageClassName="$STORAGE_CLASS" \
  --set config.appBucketName="$APP_BUCKET_NAME" \
  --set config.region="$REGION" \
  --set config.nextauthUrl="$NEXTAUTH_URL" \
  --set config.nextPublicFastapiUrl="https://$APP_HOST/fastapi" \
  --atomic \
  --timeout 10m

echo ""
echo "Deployment complete!"
echo "  kubectl get pods -n $NAMESPACE"
echo "  kubectl get ingress -n $NAMESPACE"
echo "  Frontend: https://$APP_HOST"
echo "  API docs: https://$APP_HOST/fastapi/docs"
