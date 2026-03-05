#!/bin/bash
# Upgrade a running doc-router release to a new chart version.
# Usage: ./deploy/scripts/k8s-upgrade.sh <overlay>
#   overlay  — env overlay name, e.g. "eks" or "customer-acme"
#
# Chart version is read from deploy/charts/doc-router/Chart.yaml.
# IMAGE_TAG may be set in the environment; defaults to the current git SHA.
# Required env vars (from overlay): CHART_REGISTRY, CHART_REPO_URL,
#   FRONTEND_IMAGE_REPO, BACKEND_IMAGE_REPO, REGION, AWS_S3_BUCKET_NAME, plus all secret vars.

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
: "${REGION:?".env.$OVERLAY must set REGION"}"
: "${APP_HOST:?".env.$OVERLAY must set APP_HOST"}"
: "${AWS_S3_BUCKET_NAME:?".env.$OVERLAY must set AWS_S3_BUCKET_NAME"}"

IMAGE_TAG="${IMAGE_TAG:-$(git rev-parse --short HEAD)}"
echo "Chart version : $CHART_VERSION"
echo "Image tag     : $IMAGE_TAG"

# --- Refresh the doc-router-secrets Secret ---
# Re-applies all secrets in case any values changed since the last deploy.
echo "Refreshing doc-router-secrets..."
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

# --- ECR login for Helm ---
echo "Logging in to ECR ($CHART_REGISTRY)..."
aws ecr get-login-password --region "$REGION" \
  | helm registry login --username AWS --password-stdin "$CHART_REGISTRY"

# --- Helm upgrade ---
echo "Running helm upgrade..."
helm upgrade "$RELEASE" \
  "oci://$CHART_REPO_URL" \
  --version "$CHART_VERSION" \
  --namespace "$NAMESPACE" \
  --reuse-values \
  --set image.frontend.repository="$FRONTEND_IMAGE_REPO" \
  --set image.backend.repository="$BACKEND_IMAGE_REPO" \
  --set image.frontend.tag="$IMAGE_TAG" \
  --set image.backend.tag="$IMAGE_TAG" \
  --set config.environment="${ENV:-prod}" \
  --set ingress.host="${APP_HOST}" \
  --set config.nextauthUrl="https://${APP_HOST}" \
  --set config.nextPublicFastapiUrl="https://${APP_HOST}/fastapi" \
  --atomic \
  --timeout 10m

# Force pods to pick up the refreshed Secret (Kubernetes does not restart pods on Secret changes)
echo "Restarting deployments to pick up refreshed secrets..."
kubectl rollout restart deployment/frontend deployment/backend -n "$NAMESPACE"
kubectl rollout status deployment/frontend deployment/backend -n "$NAMESPACE" --timeout=5m

echo ""
echo "Upgrade complete! Chart $CHART_VERSION, image $IMAGE_TAG."
echo "  helm history $RELEASE -n $NAMESPACE"
