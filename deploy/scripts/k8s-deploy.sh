#!/bin/bash
# Install or upgrade doc-router on any Kubernetes cluster.
# Idempotent — safe to run on a fresh cluster or an existing deployment.
# Usage: ./deploy/scripts/k8s-deploy.sh <overlay>
#   overlay  — env overlay name, e.g. "eks-test" or "do-test"
#
# Chart version is read from deploy/charts/doc-router/Chart.yaml.
# IMAGE_TAG may be set in the environment; defaults to the current git SHA.
# Required env vars (from overlay): CHART_REGISTRY, CHART_REPO_URL,
#   FRONTEND_IMAGE_REPO, BACKEND_IMAGE_REPO, APP_HOST,
#   AWS_S3_BUCKET_NAME, plus all secret vars (MONGODB_URI, etc.).
# For AWS ECR: also REGION.
# For Digital Ocean DOCR: also CLOUD_PROVIDER=do, DOCR_TOKEN.

set -eo pipefail

OVERLAY=${1:?"Usage: $0 <overlay>"}

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

CHART_VERSION="$(grep '^version:' "$PROJECT_ROOT/deploy/charts/doc-router/Chart.yaml" | awk '{print $2}')"

NAMESPACE="doc-router"
RELEASE="doc-router"

cd "$PROJECT_ROOT"

# --- Load env files ---
set -a
[ -f "$PROJECT_ROOT/.env" ]          && source "$PROJECT_ROOT/.env"
[ -f "$PROJECT_ROOT/.env.$OVERLAY" ] && source "$PROJECT_ROOT/.env.$OVERLAY"
set +a

# Save app runtime AWS credentials before unsetting CLI env vars.
# The unset ensures AWS_PROFILE (SSO) is used for aws/helm/kubectl tooling.
_APP_AWS_ACCESS_KEY_ID="${AWS_ACCESS_KEY_ID}"
_APP_AWS_SECRET_ACCESS_KEY="${AWS_SECRET_ACCESS_KEY}"
unset AWS_ACCESS_KEY_ID AWS_SECRET_ACCESS_KEY AWS_SESSION_TOKEN

: "${CHART_REGISTRY:?".env.$OVERLAY must set CHART_REGISTRY"}"
: "${CHART_REPO_URL:?".env.$OVERLAY must set CHART_REPO_URL"}"
: "${FRONTEND_IMAGE_REPO:?".env.$OVERLAY must set FRONTEND_IMAGE_REPO"}"
: "${BACKEND_IMAGE_REPO:?".env.$OVERLAY must set BACKEND_IMAGE_REPO"}"
: "${APP_HOST:?".env.$OVERLAY must set APP_HOST"}"
: "${AWS_S3_BUCKET_NAME:?".env.$OVERLAY must set AWS_S3_BUCKET_NAME"}"

CLOUD_PROVIDER="${CLOUD_PROVIDER:-aws}"
if [ "$CLOUD_PROVIDER" = "aws" ]; then
    : "${REGION:?".env.$OVERLAY must set REGION for AWS ECR"}"
elif [ "$CLOUD_PROVIDER" = "do" ]; then
    : "${DOCR_TOKEN:?".env.$OVERLAY must set DOCR_TOKEN for Digital Ocean"}"
fi

IMAGE_TAG="${IMAGE_TAG:-$(git rev-parse --short HEAD)}"
echo "Chart version : $CHART_VERSION"
echo "Image tag     : $IMAGE_TAG"
echo "Cluster host  : $APP_HOST"

# --- Namespace (idempotent) ---
echo "Ensuring namespace '$NAMESPACE'..."
kubectl create namespace "$NAMESPACE" --dry-run=client -o yaml | kubectl apply -f -

# --- Create/update the doc-router-secrets Secret (idempotent) ---
echo "Applying doc-router-secrets..."
kubectl create secret generic doc-router-secrets \
  --namespace "$NAMESPACE" \
  --from-literal=NEXTAUTH_SECRET="${NEXTAUTH_SECRET}" \
  --from-literal=MONGODB_URI="${MONGODB_URI}" \
  --from-literal=ADMIN_EMAIL="${ADMIN_EMAIL}" \
  --from-literal=ADMIN_PASSWORD="${ADMIN_PASSWORD}" \
  --from-literal=AWS_ACCESS_KEY_ID="${_APP_AWS_ACCESS_KEY_ID}" \
  --from-literal=AWS_SECRET_ACCESS_KEY="${_APP_AWS_SECRET_ACCESS_KEY}" \
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

# --- Registry login for Helm ---
echo "Logging in to registry ($CHART_REGISTRY)..."
if [ "$CLOUD_PROVIDER" = "do" ]; then
    echo "$DOCR_TOKEN" | helm registry login registry.digitalocean.com \
      --username "$DOCR_TOKEN" --password-stdin
else
    aws ecr get-login-password --region "$REGION" \
      | helm registry login --username AWS --password-stdin "$CHART_REGISTRY"
fi

# --- Helm install/upgrade ---
echo "Running helm upgrade --install..."
helm upgrade --install "$RELEASE" \
  "oci://$CHART_REPO_URL" \
  --version "$CHART_VERSION" \
  --namespace "$NAMESPACE" \
  --set image.frontend.repository="$FRONTEND_IMAGE_REPO" \
  --set image.backend.repository="$BACKEND_IMAGE_REPO" \
  --set image.frontend.tag="$IMAGE_TAG" \
  --set image.backend.tag="$IMAGE_TAG" \
  --set ingress.host="$APP_HOST" \
  --set ingress.className=nginx \
  --set config.environment="${ENV:-prod}" \
  --set config.appBucketName="$AWS_S3_BUCKET_NAME" \
  --set config.region="$REGION" \
  --set config.nextauthUrl="https://$APP_HOST" \
  --atomic \
  --timeout 10m

# --- Restart pods to pick up refreshed Secret ---
# Kubernetes does not restart pods automatically when a Secret changes.
echo "Restarting deployments to pick up refreshed secrets..."
kubectl rollout restart deployment/frontend deployment/backend -n "$NAMESPACE"
kubectl rollout status  deployment/frontend deployment/backend -n "$NAMESPACE" --timeout=5m

echo ""
echo "Deployment complete! Chart $CHART_VERSION, image $IMAGE_TAG."
echo "  Frontend: https://$APP_HOST"
echo "  API docs: https://$APP_HOST/fastapi/docs"
echo "  helm history $RELEASE -n $NAMESPACE"
