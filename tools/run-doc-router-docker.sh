#!/usr/bin/env bash
# Run DocRouter (embedded MongoDB) via Docker Compose without cloning the repo.
#
# Prerequisites: Docker Engine + Compose v2 (docker compose) or docker-compose plugin.
#
# Supported: Linux, macOS, Windows/WSL (Git Bash/WSL Ubuntu use this bash script).
#
# Usage:
#   curl -fsSL https://raw.githubusercontent.com/analytiq-hub/doc-router/main/tools/run-doc-router-docker.sh | bash -s -- up
#   ./tools/run-doc-router-docker.sh up
#   ./tools/run-doc-router-docker.sh down
#   ./tools/run-doc-router-docker.sh clean    # stop and remove volumes
#   ./tools/run-doc-router-docker.sh logs -f
#   ./tools/run-doc-router-docker.sh pull
#
# Environment (optional):
#   DOC_ROUTER_REF          Git ref on GitHub for nginx.conf (default: main)
#   DOC_ROUTER_GITHUB_REPO  owner/repo (default: analytiq-hub/doc-router)
#   DOC_ROUTER_STATE_DIR    State dir with compose/nginx/.env (default: ~/.cache/doc-router-docker/run)
#   IMAGE_TAG               GHCR tag for frontend/backend (default: latest)
#   NEXTAUTH_SECRET / NEXTAUTH_URL / ADMIN_EMAIL / ADMIN_PASSWORD — passed into compose .env when set
#

set -euo pipefail

readonly DEFAULT_REPO="analytiq-hub/doc-router"
readonly DEFAULT_REF="${DOC_ROUTER_REF:-main}"
readonly GITHUB_REPO="${DOC_ROUTER_GITHUB_REPO:-$DEFAULT_REPO}"
readonly STATE_DIR="${DOC_ROUTER_STATE_DIR:-"${HOME%/}/.cache/doc-router-docker/run"}"
readonly COMPOSE_PROJECT_NAME="${DOC_ROUTER_COMPOSE_PROJECT:-doc-router-quick}"

cmd_exists() { command -v "$1" >/dev/null 2>&1; }

download() {
  local url="$1" dest="$2"
  mkdir -p "$(dirname "$dest")"
  if cmd_exists curl; then
    curl -fsSL -o "$dest" "$url"
  elif cmd_exists wget; then
    wget -q -O "$dest" "$url"
  else
    echo "Need curl or wget to fetch $url" >&2
    exit 1
  fi
}

docker_compose() {
  if docker compose version >/dev/null 2>&1; then
    docker compose "$@"
  elif cmd_exists docker-compose; then
    docker-compose "$@"
  else
    echo "Docker Compose not found. Install Docker Desktop / docker compose plugin, or docker-compose v1." >&2
    exit 1
  fi
}

write_compose_yaml() {
  local out="$1"
  mkdir -p "$(dirname "$out")"
  # Image-only compose (no build context) — safe to run without a repo checkout.
  cat >"$out" <<'YAML'
services:
  frontend:
    image: ghcr.io/analytiq-hub/doc-router-frontend:${IMAGE_TAG:-latest}
    environment:
      - ENV=${ENV:-dev}
      - MONGODB_URI=mongodb://mongodb:27017/?directConnection=true
      - NEXTAUTH_URL=${NEXTAUTH_URL:-http://localhost:3000}
      - NEXTAUTH_SECRET=${NEXTAUTH_SECRET:-default_secret_for_development}
      - AUTH_GITHUB_ID=${AUTH_GITHUB_ID:-}
      - AUTH_GITHUB_SECRET=${AUTH_GITHUB_SECRET:-}
      - AUTH_GOOGLE_ID=${AUTH_GOOGLE_ID:-}
      - AUTH_GOOGLE_SECRET=${AUTH_GOOGLE_SECRET:-}
    command: node frontend/server.js
    restart: unless-stopped
    networks:
      - doc-router-local-network
    deploy:
      resources:
        limits:
          memory: 1G
        reservations:
          memory: 512M

  migrate:
    image: ghcr.io/analytiq-hub/doc-router-backend:${IMAGE_TAG:-latest}
    environment:
      - ENV=${ENV:-dev}
      - MONGODB_URI=mongodb://mongodb:27017/?directConnection=true
      - ADMIN_EMAIL=${ADMIN_EMAIL:-admin}
      - ADMIN_PASSWORD=${ADMIN_PASSWORD:-admin}
    command: sh -c "cd /app/packages/python && python3 migrate.py"
    networks:
      - doc-router-local-network
    depends_on:
      mongodb:
        condition: service_healthy
    restart: "no"

  backend:
    image: ghcr.io/analytiq-hub/doc-router-backend:${IMAGE_TAG:-latest}
    depends_on:
      migrate:
        condition: service_completed_successfully
    environment:
      - ENV=${ENV:-dev}
      - MONGODB_URI=mongodb://mongodb:27017/?directConnection=true
      - NEXTAUTH_URL=${NEXTAUTH_URL:-http://localhost:3000}
      - NEXTAUTH_SECRET=${NEXTAUTH_SECRET:-default_secret_for_development}
      - FASTAPI_SECRET=${FASTAPI_SECRET:-}
      - FASTAPI_ROOT_PATH=${FASTAPI_ROOT_PATH:-/fastapi}
      - ADMIN_EMAIL=${ADMIN_EMAIL:-admin}
      - ADMIN_PASSWORD=${ADMIN_PASSWORD:-admin}
      - AWS_ACCESS_KEY_ID=${AWS_ACCESS_KEY_ID:-}
      - AWS_SECRET_ACCESS_KEY=${AWS_SECRET_ACCESS_KEY:-}
      - AWS_S3_BUCKET_NAME=${AWS_S3_BUCKET_NAME:-}
      - OPENAI_API_KEY=${OPENAI_API_KEY:-}
      - ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY:-}
      - GEMINI_API_KEY=${GEMINI_API_KEY:-}
      - GROQ_API_KEY=${GROQ_API_KEY:-}
      - MISTRAL_API_KEY=${MISTRAL_API_KEY:-}
      - SES_FROM_EMAIL=${SES_FROM_EMAIL:-}
      - N_WORKERS=${N_WORKERS:-1}
      - CORS_ORIGINS_EXTRA=${CORS_ORIGINS_EXTRA:-}
    command: sh -c "cd /app/packages/python && uvicorn app.main:app --host 0.0.0.0 --port 8000"
    restart: unless-stopped
    ports:
      - "8000:8000"
    networks:
      - doc-router-local-network
    deploy:
      resources:
        limits:
          memory: 2G
        reservations:
          memory: 512M

  mongodb:
    hostname: mongodb
    image: mongodb/mongodb-atlas-local:latest
    environment:
      MONGOT_LOG_FILE: /dev/stdout
      RUNNER_LOG_FILE: /dev/stdout
    ports:
      - "27018:27017"
    networks:
      - doc-router-local-network
    volumes:
      - doc-router-local-mongodb:/data/db
      - doc-router-local-mongodb-configdb:/data/configdb
    restart: always
    healthcheck:
      test: ["CMD", "mongosh", "--quiet", "--eval", "quit(db.adminCommand('hello').isWritablePrimary ? 0 : 1)"]
      interval: 10s
      timeout: 5s
      retries: 30
    deploy:
      resources:
        limits:
          memory: 1G
        reservations:
          memory: 512M

  nginx:
    image: nginx:alpine
    ports:
      - "3000:80"
    volumes:
      - ./nginx.conf:/etc/nginx/conf.d/default.conf:ro
    networks:
      - doc-router-local-network
    depends_on:
      - frontend
      - backend
    restart: unless-stopped
    deploy:
      resources:
        limits:
          memory: 128M
        reservations:
          memory: 64M

networks:
  doc-router-local-network:
    driver: bridge

volumes:
  doc-router-local-mongodb:
  doc-router-local-mongodb-configdb:
YAML
}

sync_files_from_repo_if_present() {
  # If this script lives inside a checkout, prefer local nginx (no network).
  local script_dir
  script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  local maybe_nginx="${script_dir}/../deploy/compose/nginx.conf"
  if [[ -f "$maybe_nginx" ]]; then
    cp -f "$maybe_nginx" "${STATE_DIR}/nginx.conf"
    return 0
  fi
  return 1
}

fetch_nginx_from_github() {
  local ref="${DOC_ROUTER_REF:-$DEFAULT_REF}"
  local url="https://raw.githubusercontent.com/${GITHUB_REPO}/${ref}/deploy/compose/nginx.conf"
  echo "Fetching nginx.conf from ${url}" >&2
  download "$url" "${STATE_DIR}/nginx.conf"
}

ensure_env_file() {
  local env_file="${STATE_DIR}/.env"
  if [[ -f "$env_file" ]]; then
    return 0
  fi
  local secret
  if cmd_exists openssl; then
    secret="$(openssl rand -base64 32)"
  else
    secret="dev-$(date +%s)-change-me"
  fi
  cat >"$env_file" <<EOF
# Generated by run-doc-router-docker.sh — edit or delete to regenerate
IMAGE_TAG=${IMAGE_TAG:-latest}
ENV=${ENV:-dev}
NEXTAUTH_URL=${NEXTAUTH_URL:-http://localhost:3000}
NEXTAUTH_SECRET=${NEXTAUTH_SECRET:-$secret}
ADMIN_EMAIL=${ADMIN_EMAIL:-admin}
ADMIN_PASSWORD=${ADMIN_PASSWORD:-admin}
EOF
  echo "Wrote ${env_file} (set NEXTAUTH_SECRET and credentials for anything beyond local dev)." >&2
}

ghcr_hint() {
  echo >&2
  echo "If image pull failed with 401/403, log in to GHCR:" >&2
  echo "  echo YOUR_GITHUB_TOKEN | docker login ghcr.io -u YOUR_GITHUB_USERNAME --password-stdin" >&2
}

# Read KEY=value from .env (first non-comment match). No shell expansion.
read_dotenv_value() {
  local key="$1" file="$2" line val
  [[ -f "$file" ]] || return 1
  while IFS= read -r line || [[ -n "$line" ]]; do
    [[ "$line" =~ ^[[:space:]]*# ]] && continue
    [[ "$line" =~ ^[[:space:]]*${key}= ]] || continue
    val="${line#*=}"
    val="${val%$'\r'}"
    printf '%s\n' "$val"
    return 0
  done <"$file"
  return 1
}

print_signin_hint() {
  local ef="${STATE_DIR}/.env"
  local admin_email admin_pw
  admin_email="$(read_dotenv_value ADMIN_EMAIL "$ef" || true)"
  admin_pw="$(read_dotenv_value ADMIN_PASSWORD "$ef" || true)"
  admin_email="${admin_email:-admin}"
  admin_pw="${admin_pw:-admin}"
  echo "Credentials sign-in (http://localhost:3000/auth/signin): user ${admin_email} / password ${admin_pw}" >&2
}

do_up() {
  mkdir -p "$STATE_DIR"
  write_compose_yaml "${STATE_DIR}/docker-compose.yml"
  if ! sync_files_from_repo_if_present; then
    fetch_nginx_from_github
  fi
  ensure_env_file

  (
    cd "$STATE_DIR"
    set +e
    docker_compose -p "$COMPOSE_PROJECT_NAME" --env-file .env pull
    pull_rc=$?
    set -e
    if [[ $pull_rc -ne 0 ]]; then
      ghcr_hint
      exit $pull_rc
    fi
    docker_compose -p "$COMPOSE_PROJECT_NAME" --env-file .env up -d
  )

  echo >&2
  echo "DocRouter is starting. Open http://localhost:3000 (API via http://localhost:3000/fastapi , backend :8000)." >&2
  print_signin_hint
  echo "State directory: ${STATE_DIR}" >&2
}

do_down() {
  if [[ ! -f "${STATE_DIR}/docker-compose.yml" ]]; then
    echo "No stack found in ${STATE_DIR}; nothing to stop." >&2
    exit 0
  fi
  (cd "$STATE_DIR" && docker_compose -p "$COMPOSE_PROJECT_NAME" --env-file .env down "$@")
}

do_clean() {
  do_down -v
}

usage() {
  sed -n '2,/^$/p' "$0" | sed 's/^# \{0,1\}//'
}

main() {
  local sub="${1:-up}"
  shift || true

  case "$sub" in
    up|start)
      do_up
      ;;
    down|stop)
      do_down "$@"
      ;;
    clean|down-volumes)
      do_clean
      ;;
    logs|ps|pull)
      if [[ ! -f "${STATE_DIR}/docker-compose.yml" ]]; then
        echo "Run '$0 up' first (missing ${STATE_DIR}/docker-compose.yml)." >&2
        exit 1
      fi
      (cd "$STATE_DIR" && docker_compose -p "$COMPOSE_PROJECT_NAME" --env-file .env "$sub" "$@")
      ;;
    -h|--help|help)
      usage
      ;;
    *)
      echo "Unknown command: $sub" >&2
      usage
      exit 1
      ;;
  esac
}

main "$@"
