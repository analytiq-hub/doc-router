#!/bin/bash
# Roll back a doc-router release to a previous Helm revision.
# Usage: ./deploy/scripts/k8s-rollback.sh <overlay> [revision]
#   overlay   — env overlay name, e.g. "eks" or "customer-acme"
#   revision  — Helm revision number to roll back to (default: 0 = previous revision)
#
# Run "helm history doc-router -n doc-router" to list available revisions.

set -eo pipefail

OVERLAY=${1:?"Usage: $0 <overlay> [revision]"}
REVISION=${2:-0}

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

NAMESPACE="doc-router"
RELEASE="doc-router"

cd "$PROJECT_ROOT"

# --- Load env files (needed for any future secret refresh, and consistent with other scripts) ---
set -a
[ -f "$PROJECT_ROOT/.env" ]          && source "$PROJECT_ROOT/.env"
[ -f "$PROJECT_ROOT/.env.$OVERLAY" ] && source "$PROJECT_ROOT/.env.$OVERLAY"
set +a

echo "Rolling back '$RELEASE' in namespace '$NAMESPACE'..."
[ "$REVISION" -eq 0 ] && echo "Target: previous revision" \
                       || echo "Target: revision $REVISION"

helm rollback "$RELEASE" "$REVISION" \
  --namespace "$NAMESPACE" \
  --wait \
  --timeout 5m

echo ""
echo "Rollback complete."
echo "  helm history $RELEASE -n $NAMESPACE"
