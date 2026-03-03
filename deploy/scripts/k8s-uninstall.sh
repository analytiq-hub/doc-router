#!/bin/bash
# Uninstall doc-router from a Kubernetes cluster.
# Removes the Helm release, the doc-router-secrets Secret, and the namespace.
# Usage: ./deploy/scripts/k8s-uninstall.sh <overlay>
#   overlay — env overlay name, e.g. "eks" or "customer-acme"

set -eo pipefail

OVERLAY=${1:?"Usage: $0 <overlay>"}

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

echo "This will remove:"
echo "  - Helm release '$RELEASE'"
echo "  - Namespace '$NAMESPACE' (including all resources and secrets)"
echo ""
read -r -p "Proceed? [y/N] " confirm
[[ "$confirm" =~ ^[Yy]$ ]] || { echo "Aborted."; exit 0; }

helm uninstall "$RELEASE" --namespace "$NAMESPACE" --wait 2>/dev/null || true

kubectl delete namespace "$NAMESPACE" --wait 2>/dev/null || true

echo ""
echo "Uninstall complete."
