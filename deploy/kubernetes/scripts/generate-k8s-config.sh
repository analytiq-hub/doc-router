#!/bin/bash
# generate-k8s-config.sh - Generate Kubernetes ConfigMap and Secrets from .env files
# Usage: ./generate-k8s-config.sh [.env-file] [output-dir]

set -e

ENV_FILE="${1:-.env}"
OUTPUT_DIR="${2:-deploy/kubernetes/base}"

if [ ! -f "$ENV_FILE" ]; then
    echo "Error: $ENV_FILE not found"
    exit 1
fi

# Separate config (non-sensitive) and secrets (sensitive)
CONFIG_VARS=(
    "ENV"
    "FASTAPI_BACKEND_URL"
    "FASTAPI_ROOT_PATH"
    "NEXTAUTH_URL"
    "NEXT_PUBLIC_FASTAPI_FRONTEND_URL"
    "N_WORKERS"
)

SECRET_VARS=(
    "NEXTAUTH_SECRET"
    "MONGODB_URI"
    "ADMIN_EMAIL"
    "ADMIN_PASSWORD"
    "AWS_ACCESS_KEY_ID"
    "AWS_SECRET_ACCESS_KEY"
    "AWS_S3_BUCKET_NAME"
    "OPENAI_API_KEY"
    "ANTHROPIC_API_KEY"
    "GEMINI_API_KEY"
    "GROQ_API_KEY"
    "MISTRAL_API_KEY"
    "SES_FROM_EMAIL"
    "STRIPE_SECRET_KEY"
    "STRIPE_WEBHOOK_SECRET"
    "STRIPE_PRODUCT_TAG"
    "AUTH_GITHUB_ID"
    "AUTH_GITHUB_SECRET"
    "AUTH_GOOGLE_ID"
    "AUTH_GOOGLE_SECRET"
)

# Generate ConfigMap (overwrite existing)
CONFIGMAP_FILE="$OUTPUT_DIR/configmap.yaml"
cat > "$CONFIGMAP_FILE" <<EOF
apiVersion: v1
kind: ConfigMap
metadata:
  name: doc-router-config
  namespace: doc-router
data:
EOF

for var in "${CONFIG_VARS[@]}"; do
    # Get the LAST occurrence (override from .env.kind takes precedence)
    value=$(grep "^${var}=" "$ENV_FILE" 2>/dev/null | tail -1 | cut -d= -f2- | sed 's/^"//;s/"$//' | sed 's/#.*$//' | xargs)
    if [ -n "$value" ]; then
        # Escape special YAML characters
        value=$(echo "$value" | sed 's/"/\\"/g')
        echo "  ${var}: \"${value}\"" >> "$CONFIGMAP_FILE"
    fi
done

# Generate Secrets (overwrite existing)
SECRETS_FILE="$OUTPUT_DIR/secrets.yaml"
cat > "$SECRETS_FILE" <<EOF
apiVersion: v1
kind: Secret
metadata:
  name: doc-router-secrets
  namespace: doc-router
type: Opaque
stringData:
EOF

for var in "${SECRET_VARS[@]}"; do
    # Get the LAST occurrence (override from .env.kind takes precedence)
    value=$(grep "^${var}=" "$ENV_FILE" 2>/dev/null | tail -1 | cut -d= -f2- | sed 's/^"//;s/"$//' | sed 's/#.*$//' | xargs)
    if [ -n "$value" ]; then
        # Escape special YAML characters
        value=$(echo "$value" | sed 's/"/\\"/g')
        echo "  ${var}: \"${value}\"" >> "$SECRETS_FILE"
    fi
done

echo "Generated ConfigMap: $CONFIGMAP_FILE"
echo "Generated Secrets: $SECRETS_FILE"
