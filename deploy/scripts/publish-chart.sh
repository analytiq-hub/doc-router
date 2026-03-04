#!/bin/bash
# Package the Helm chart and push it as an OCI artifact to ECR.
# Usage: ./deploy/scripts/publish-chart.sh <overlay> <chart-version>
#   overlay        — env overlay name, e.g. "eks" (sources .env + .env.<overlay>)
#   chart-version  — semver, e.g. "1.5.0"
#
# Required env vars (from overlay): CHART_REGISTRY, CHART_REPO_URL, REGION.

set -eo pipefail

OVERLAY=${1:?"Usage: $0 <overlay> <chart-version>"}
CHART_VERSION=${2:?"Usage: $0 <overlay> <chart-version>"}

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
CHART_DIR="$PROJECT_ROOT/deploy/charts/doc-router"

cd "$PROJECT_ROOT"

# --- Load env files ---
set -a
[ -f "$PROJECT_ROOT/.env" ]          && source "$PROJECT_ROOT/.env"
[ -f "$PROJECT_ROOT/.env.$OVERLAY" ] && source "$PROJECT_ROOT/.env.$OVERLAY"
set +a

: "${CHART_REGISTRY:?".env.$OVERLAY must set CHART_REGISTRY"}"
: "${CHART_REPO_URL:?".env.$OVERLAY must set CHART_REPO_URL"}"
: "${REGION:?".env.$OVERLAY must set REGION"}"

CHART_PACKAGE="doc-router-${CHART_VERSION}.tgz"

# --- Package chart ---
echo "Packaging chart version $CHART_VERSION..."
helm package "$CHART_DIR" --version "$CHART_VERSION"

# --- ECR login for Helm ---
echo "Logging in to ECR ($CHART_REGISTRY)..."
aws ecr get-login-password --region "$REGION" \
  | helm registry login --username AWS --password-stdin "$CHART_REGISTRY"

# --- Push OCI artifact ---
echo "Pushing chart to oci://$CHART_REPO_URL..."
helm push "$CHART_PACKAGE" "oci://$CHART_REPO_URL"

rm -f "$CHART_PACKAGE"

echo ""
echo "Done. Chart $CHART_VERSION published to oci://$CHART_REPO_URL."
