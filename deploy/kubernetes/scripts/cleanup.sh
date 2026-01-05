#!/bin/bash
set -e

# Cleanup doc-router resources from Kubernetes

CLUSTER_NAME=${CLUSTER_NAME:-"doc-router"}
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
KIND_OVERLAY="$SCRIPT_DIR/../overlays/kind"

echo "🧹 Cleaning up doc-router resources..."

# Delete resources using kustomize
if [ -d "$KIND_OVERLAY" ]; then
    cd "$KIND_OVERLAY"
    kubectl delete -k . --ignore-not-found=true
fi

# Optionally delete the namespace
read -p "Delete namespace 'doc-router'? (y/N) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    kubectl delete namespace doc-router --ignore-not-found=true
    echo "✅ Namespace deleted"
fi

# Optionally delete the kind cluster
read -p "Delete kind cluster '$CLUSTER_NAME'? (y/N) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    kind delete cluster --name "$CLUSTER_NAME"
    echo "✅ Kind cluster deleted"
fi

echo "✅ Cleanup complete!"
