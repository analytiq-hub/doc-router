#!/bin/bash
# Package the Helm chart and push it as an OCI artifact to a container registry.
# Usage: ./deploy/scripts/publish-chart.sh <overlay>
#   overlay  — env overlay name, e.g. "eks-test" or "do-test"
#
# Chart version is read from deploy/charts/doc-router/Chart.yaml.
# Required env vars (from overlay): CHART_REGISTRY, CHART_REPO_URL.
# For AWS ECR: also REGION.
# For Digital Ocean DOCR: also CLOUD_PROVIDER=do, DOCR_TOKEN.

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

# Use AWS_PROFILE for all tooling; drop any static key vars from .env
unset AWS_ACCESS_KEY_ID AWS_SECRET_ACCESS_KEY AWS_SESSION_TOKEN

: "${CHART_REGISTRY:?".env.$OVERLAY must set CHART_REGISTRY"}"
: "${CHART_REPO_URL:?".env.$OVERLAY must set CHART_REPO_URL"}"

CLOUD_PROVIDER="${CLOUD_PROVIDER:-aws}"
if [ "$CLOUD_PROVIDER" = "aws" ]; then
    : "${REGION:?".env.$OVERLAY must set REGION for AWS ECR"}"
elif [ "$CLOUD_PROVIDER" = "do" ]; then
    : "${DOCR_TOKEN:?".env.$OVERLAY must set DOCR_TOKEN for Digital Ocean"}"
fi

CHART_PACKAGE="doc-router-${CHART_VERSION}.tgz"

# --- Package chart ---
echo "Packaging chart version $CHART_VERSION..."
helm package "$CHART_DIR"

# --- Registry login for Helm ---
echo "Logging in to registry ($CHART_REGISTRY)..."
if [ "$CLOUD_PROVIDER" = "do" ]; then
    echo "$DOCR_TOKEN" | helm registry login registry.digitalocean.com \
      --username "$DOCR_TOKEN" --password-stdin
else
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
