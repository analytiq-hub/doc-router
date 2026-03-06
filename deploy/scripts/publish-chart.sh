#!/bin/bash
# Package the Helm chart and push it as an OCI artifact to a container registry.
# Usage: ./deploy/scripts/publish-chart.sh <overlay>
#   overlay  — env overlay name, e.g. "eks-test" or "do-test"
#
# Chart version is read from deploy/charts/doc-router/Chart.yaml.
# Required env vars (from overlay): CHART_REGISTRY, CHART_REPO_URL.
# REGISTRY_PROVIDER controls which registry is used (defaults to CLOUD_PROVIDER, then "github").
# For ghcr.io (default): REGISTRY_PROVIDER=github, GITHUB_TOKEN, GITHUB_USERNAME.
# For AWS ECR:           REGISTRY_PROVIDER=aws, REGION.
# For Digital Ocean DOCR: REGISTRY_PROVIDER=do, DOCR_TOKEN.

set -eo pipefail

OVERLAY=${1:?"Usage: $0 <overlay>"}

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
CHART_DIR="$PROJECT_ROOT/deploy/charts/doc-router"

cd "$PROJECT_ROOT"

CHART_VERSION="$(grep '^version:' "$CHART_DIR/Chart.yaml" | awk '{print $2}')"

# --- Load env files ---
set -a
[ -f "$PROJECT_ROOT/.env" ]          && source "$PROJECT_ROOT/.env"
[ -f "$PROJECT_ROOT/.env.$OVERLAY" ] && source "$PROJECT_ROOT/.env.$OVERLAY"
set +a

: "${CHART_REGISTRY:?".env.$OVERLAY must set CHART_REGISTRY"}"
: "${CHART_REPO_URL:?".env.$OVERLAY must set CHART_REPO_URL"}"

REGISTRY_PROVIDER="${REGISTRY_PROVIDER:-${CLOUD_PROVIDER:-github}}"
if [ "$REGISTRY_PROVIDER" = "aws" ]; then
    : "${REGION:?".env.$OVERLAY must set REGION for AWS ECR"}"
    # Use AWS_PROFILE for tooling; drop any static key vars from .env
    unset AWS_ACCESS_KEY_ID AWS_SECRET_ACCESS_KEY AWS_SESSION_TOKEN
elif [ "$REGISTRY_PROVIDER" = "do" ]; then
    : "${DOCR_TOKEN:?".env.$OVERLAY must set DOCR_TOKEN for Digital Ocean"}"
elif [ "$REGISTRY_PROVIDER" = "github" ]; then
    : "${GITHUB_TOKEN:?".env.$OVERLAY must set GITHUB_TOKEN for ghcr.io"}"
    : "${GITHUB_USERNAME:?".env.$OVERLAY must set GITHUB_USERNAME for ghcr.io"}"
fi

CHART_PACKAGE="/tmp/doc-router-${CHART_VERSION}.tgz"

# --- Package chart ---
echo "Packaging chart version $CHART_VERSION..."
helm package "$CHART_DIR" --destination /tmp

# --- Registry login for Helm ---
if [ "$REGISTRY_PROVIDER" = "github" ]; then
    echo "Logging in to ghcr.io..."
    echo "$GITHUB_TOKEN" | helm registry login ghcr.io \
      --username "$GITHUB_USERNAME" --password-stdin
elif [ "$REGISTRY_PROVIDER" = "do" ]; then
    echo "Logging in to registry.digitalocean.com..."
    echo "$DOCR_TOKEN" | helm registry login registry.digitalocean.com \
      --username "$DOCR_TOKEN" --password-stdin
else
    echo "Logging in to registry ($CHART_REGISTRY)..."
    aws ecr get-login-password --region "$REGION" \
      | helm registry login --username AWS --password-stdin "$CHART_REGISTRY"
fi

# --- Push OCI artifact ---
# helm push appends the chart name to the URL, so push to the registry root:
#   oci://CHART_REGISTRY/<chart-name>:<version>  →  ECR repo = CHART_REPO_URL
echo "Pushing chart to $CHART_REPO_URL..."
helm push "$CHART_PACKAGE" "oci://$CHART_REGISTRY"

rm -f "$CHART_PACKAGE"

echo ""
echo "Done. Chart $CHART_VERSION published to $CHART_REPO_URL."
