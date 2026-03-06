#!/bin/bash
# Install cluster-level add-ons on a Digital Ocean Kubernetes (DOKS) cluster.
# Run once per cluster after provisioning, before deploying the app.
# Usage: ./deploy/scripts/setup-doks.sh <overlay>
#   overlay — env overlay name, e.g. "do-test" (sources .env + .env.<overlay>)
#
# Required env var (from overlay): LETSENCRYPT_EMAIL
# kubectl must already be configured against the target cluster:
#   doctl kubernetes cluster kubeconfig save <cluster-name>

set -eo pipefail

OVERLAY=${1:?"Usage: $0 <overlay>"}

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# --- Load env files ---
set -a
[ -f "$PROJECT_ROOT/.env" ]          && source "$PROJECT_ROOT/.env"
[ -f "$PROJECT_ROOT/.env.$OVERLAY" ] && source "$PROJECT_ROOT/.env.$OVERLAY"
set +a

: "${LETSENCRYPT_EMAIL:?".env.$OVERLAY must set LETSENCRYPT_EMAIL"}"

# --- ingress-nginx ---
# Digital Ocean provisions a Load Balancer automatically for type=LoadBalancer services.
echo "Installing ingress-nginx..."
helm repo add ingress-nginx https://kubernetes.github.io/ingress-nginx 2>/dev/null || true
helm repo update ingress-nginx
helm upgrade --install ingress-nginx ingress-nginx/ingress-nginx \
  --namespace ingress-nginx --create-namespace \
  --version 4.11.3 \
  --set controller.service.type=LoadBalancer \
  --wait --timeout 5m

# --- cert-manager ---
echo "Installing cert-manager..."
helm repo add jetstack https://charts.jetstack.io 2>/dev/null || true
helm repo update jetstack
helm upgrade --install cert-manager jetstack/cert-manager \
  --namespace cert-manager --create-namespace \
  --version v1.16.2 \
  --set crds.enabled=true \
  --wait --timeout 5m

# --- metrics-server ---
# DOKS ships metrics-server pre-installed; this is a no-op if it already exists.
echo "Installing metrics-server..."
helm repo add metrics-server https://kubernetes-sigs.github.io/metrics-server/ 2>/dev/null || true
helm repo update metrics-server
helm upgrade --install metrics-server metrics-server/metrics-server \
  --namespace kube-system \
  --version 3.12.2 \
  --wait --timeout 3m

# --- Let's Encrypt ClusterIssuer ---
echo "Creating letsencrypt-prod ClusterIssuer..."
kubectl apply -f - <<EOF
apiVersion: cert-manager.io/v1
kind: ClusterIssuer
metadata:
  name: letsencrypt-prod
spec:
  acme:
    server: https://acme-v02.api.letsencrypt.org/directory
    email: ${LETSENCRYPT_EMAIL}
    privateKeySecretRef:
      name: letsencrypt-prod
    solvers:
    - http01:
        ingress:
          ingressClassName: nginx
EOF

echo ""
echo "Cluster add-ons installed."
echo "  kubectl get pods -n ingress-nginx"
echo "  kubectl get pods -n cert-manager"
echo "  kubectl get clusterissuer letsencrypt-prod"
echo ""
echo "Next: point your DNS A record for \$APP_HOST to the ingress-nginx LoadBalancer IP:"
echo "  kubectl get svc -n ingress-nginx ingress-nginx-controller"
echo ""
echo "Then deploy the app:"
echo "  ./deploy/scripts/build-push.sh $OVERLAY"
echo "  ./deploy/scripts/publish-chart.sh $OVERLAY"
echo "  ./deploy/scripts/k8s-deploy.sh $OVERLAY"
