#!/bin/bash
# Uninstall the doc-router Helm release from the Kind cluster (keeps the cluster running).
# Usage: ./deploy/scripts/down-kind.sh

set -e

NAMESPACE="doc-router"
RELEASE="doc-router"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

set -a
[ -f "$PROJECT_ROOT/.env" ]      && source "$PROJECT_ROOT/.env"
[ -f "$PROJECT_ROOT/.env.kind" ] && source "$PROJECT_ROOT/.env.kind"
set +a

if helm status "$RELEASE" -n "$NAMESPACE" &>/dev/null; then
    echo "Uninstalling Helm release '$RELEASE' from namespace '$NAMESPACE'..."
    helm uninstall "$RELEASE" -n "$NAMESPACE"
    echo "Done. Kind cluster is still running — use 'make destroy-kind' to delete it."
else
    echo "Helm release '$RELEASE' not found in namespace '$NAMESPACE'"
fi
