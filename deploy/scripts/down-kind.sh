#!/bin/bash
# Delete the local Kind cluster for doc-router.
# Usage: ./deploy/scripts/down-kind.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

CLUSTER_NAME=${CLUSTER_NAME:-"doc-router"}

# Source env files so CLUSTER_NAME can be overridden the same way deploy-kind.sh does.
set -a
[ -f "$PROJECT_ROOT/.env" ]      && source "$PROJECT_ROOT/.env"
[ -f "$PROJECT_ROOT/.env.kind" ] && source "$PROJECT_ROOT/.env.kind"
set +a

if kind get clusters 2>/dev/null | grep -q "^${CLUSTER_NAME}$"; then
    echo "Deleting kind cluster: $CLUSTER_NAME"
    kind delete cluster --name "$CLUSTER_NAME"
else
    echo "Kind cluster '$CLUSTER_NAME' does not exist"
fi
