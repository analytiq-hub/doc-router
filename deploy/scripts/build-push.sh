#!/bin/bash
# Build frontend and backend images and push them to a container registry.
# Usage: ./deploy/scripts/build-push.sh <overlay>
#   overlay  — env overlay name, e.g. "eks-test" or "do-test"
#
# IMAGE_TAG may be set in the environment; defaults to the current git SHA.
# Required env vars (from overlay): CHART_REGISTRY, FRONTEND_IMAGE_REPO,
#   BACKEND_IMAGE_REPO, APP_HOST.
# For AWS ECR: also REGION.
# For Digital Ocean DOCR: also CLOUD_PROVIDER=do, DOCR_TOKEN.

set -eo pipefail

OVERLAY=${1:?"Usage: $0 <overlay>"}

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

cd "$PROJECT_ROOT"

# --- Load env files ---
set -a
[ -f "$PROJECT_ROOT/.env" ]          && source "$PROJECT_ROOT/.env"
[ -f "$PROJECT_ROOT/.env.$OVERLAY" ] && source "$PROJECT_ROOT/.env.$OVERLAY"
set +a

# Use AWS_PROFILE for all tooling; drop any static key vars from .env
unset AWS_ACCESS_KEY_ID AWS_SECRET_ACCESS_KEY AWS_SESSION_TOKEN

: "${CHART_REGISTRY:?".env.$OVERLAY must set CHART_REGISTRY"}"
: "${FRONTEND_IMAGE_REPO:?".env.$OVERLAY must set FRONTEND_IMAGE_REPO"}"
: "${BACKEND_IMAGE_REPO:?".env.$OVERLAY must set BACKEND_IMAGE_REPO"}"
: "${APP_HOST:?".env.$OVERLAY must set APP_HOST"}"

CLOUD_PROVIDER="${CLOUD_PROVIDER:-aws}"
if [ "$CLOUD_PROVIDER" = "aws" ]; then
    : "${REGION:?".env.$OVERLAY must set REGION for AWS ECR"}"
elif [ "$CLOUD_PROVIDER" = "do" ]; then
    : "${DOCR_TOKEN:?".env.$OVERLAY must set DOCR_TOKEN for Digital Ocean"}"
fi

IMAGE_TAG="${IMAGE_TAG:-$(git rev-parse --short HEAD)}"
echo "Image tag: $IMAGE_TAG"

NEXT_PUBLIC_FASTAPI_FRONTEND_URL="https://${APP_HOST}/fastapi"

# --- Registry login ---
echo "Logging in to registry ($CHART_REGISTRY)..."
if [ "$CLOUD_PROVIDER" = "do" ]; then
    echo "$DOCR_TOKEN" | docker login registry.digitalocean.com \
      --username "$DOCR_TOKEN" --password-stdin
else
    aws ecr get-login-password --region "$REGION" \
      | docker login --username AWS --password-stdin "$CHART_REGISTRY"
fi

# --- Build and push frontend ---
echo "Building frontend image..."
docker build \
  --target runner \
  --build-arg NEXT_PUBLIC_FASTAPI_FRONTEND_URL="$NEXT_PUBLIC_FASTAPI_FRONTEND_URL" \
  --build-arg NODE_ENV=production \
  -t "$FRONTEND_IMAGE_REPO:$IMAGE_TAG" \
  -t "$FRONTEND_IMAGE_REPO:latest" \
  -f deploy/shared/docker/Dockerfile .

echo "Pushing frontend image..."
docker push "$FRONTEND_IMAGE_REPO:$IMAGE_TAG"
docker push "$FRONTEND_IMAGE_REPO:latest"

# --- Build and push backend ---
echo "Building backend image..."
docker build \
  --target backend \
  -t "$BACKEND_IMAGE_REPO:$IMAGE_TAG" \
  -t "$BACKEND_IMAGE_REPO:latest" \
  -f deploy/shared/docker/Dockerfile .

echo "Pushing backend image..."
docker push "$BACKEND_IMAGE_REPO:$IMAGE_TAG"
docker push "$BACKEND_IMAGE_REPO:latest"

echo ""
echo "Done. IMAGE_TAG=$IMAGE_TAG"
