#!/bin/bash
set -e

# Setup kind cluster for doc-router
# This script creates a kind cluster and configures it for local development

CLUSTER_NAME=${CLUSTER_NAME:-"doc-router"}
KIND_VERSION=${KIND_VERSION:-"latest"}

echo "🚀 Setting up kind cluster: $CLUSTER_NAME"

# Check if kind is installed
if ! command -v kind &> /dev/null; then
    echo "❌ kind is not installed. Please install it first:"
    echo "   curl -Lo ./kind https://kind.sigs.k8s.io/dl/v0.20.0/kind-linux-amd64"
    echo "   chmod +x ./kind"
    echo "   sudo mv ./kind /usr/local/bin/kind"
    exit 1
fi

# Check if cluster already exists
if kind get clusters | grep -q "^${CLUSTER_NAME}$"; then
    echo "⚠️  Cluster $CLUSTER_NAME already exists. Delete it first with:"
    echo "   kind delete cluster --name $CLUSTER_NAME"
    read -p "Do you want to delete it and create a new one? (y/N) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        kind delete cluster --name "$CLUSTER_NAME"
    else
        echo "Aborted."
        exit 1
    fi
fi

# Create kind cluster configuration
cat <<EOF | kind create cluster --name "$CLUSTER_NAME" --config=-
kind: Cluster
apiVersion: kind.x-k8s.io/v1alpha4
nodes:
- role: control-plane
  kubeadmConfigPatches:
  - |
    kind: InitConfiguration
    nodeRegistration:
      kubeletExtraArgs:
        node-labels: "ingress-ready=true"
  extraPortMappings:
  - containerPort: 80
    hostPort: 80
    protocol: TCP
  - containerPort: 443
    hostPort: 443
    protocol: TCP
  - containerPort: 3000
    hostPort: 3000
    protocol: TCP
  - containerPort: 8000
    hostPort: 8000
    protocol: TCP
EOF

echo "✅ Kind cluster created: $CLUSTER_NAME"

# Install NGINX Ingress Controller
echo "📦 Installing NGINX Ingress Controller..."
kubectl apply -f https://raw.githubusercontent.com/kubernetes/ingress-nginx/main/deploy/static/provider/kind/deploy.yaml

# Wait for ingress controller to be ready
echo "⏳ Waiting for NGINX Ingress Controller to be ready..."
# Wait for pods to be created first
for i in {1..30}; do
    if kubectl get pods -n ingress-nginx --selector=app.kubernetes.io/component=controller --no-headers 2>/dev/null | grep -q .; then
        break
    fi
    sleep 2
done

# Now wait for them to be ready
kubectl wait --namespace ingress-nginx \
  --for=condition=ready pod \
  --selector=app.kubernetes.io/component=controller \
  --timeout=120s || {
    echo "⚠️  Ingress controller may still be starting. Check with: kubectl get pods -n ingress-nginx"
    echo "Continuing anyway..."
  }

echo "✅ NGINX Ingress Controller setup complete"

# Create local registry (optional, for testing)
echo "📦 Setting up local image registry..."
cat <<EOF | kubectl apply -f -
apiVersion: v1
kind: ConfigMap
metadata:
  name: local-registry-hosting
  namespace: kube-public
data:
  localRegistryHosting.v1: |
    host: "localhost:5000"
    help: "https://kind.sigs.k8s.io/docs/user/local-registry/"
EOF

echo ""
echo "✅ Kind cluster setup complete!"
echo ""
echo "Next steps:"
echo "1. Build and load your images:"
echo "   docker build -t analytiqhub/doc-router-frontend:latest --target frontend ."
echo "   docker build -t analytiqhub/doc-router-backend:latest --target backend ."
echo "   kind load docker-image analytiqhub/doc-router-frontend:latest --name $CLUSTER_NAME"
echo "   kind load docker-image analytiqhub/doc-router-backend:latest --name $CLUSTER_NAME"
echo ""
echo "2. Deploy the application:"
echo "   cd deploy/kubernetes/overlays/kind"
echo "   kubectl apply -k ."
echo ""
echo "3. Check status:"
echo "   kubectl get pods -n doc-router"
echo "   kubectl get services -n doc-router"
echo ""
