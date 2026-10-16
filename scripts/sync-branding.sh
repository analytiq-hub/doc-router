#!/usr/bin/env bash
# Copy optional APP_FAVICON from repo .env into the Next.js public dir for /branded-favicon.ico.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
ENV_FILE="${PROJECT_ROOT}/.env"
FRONTEND_PUBLIC="${PROJECT_ROOT}/packages/typescript/frontend/public"
DEST="${FRONTEND_PUBLIC}/branded-favicon.ico"

read_env_value() {
  local key="$1"
  if [[ ! -f "${ENV_FILE}" ]]; then
    return 0
  fi
  grep -E "^${key}=" "${ENV_FILE}" 2>/dev/null | head -1 | cut -d'=' -f2- \
    | sed 's/^"\(.*\)"$/\1/' | sed "s/^'\(.*\)'$/\1/"
}

APP_FAVICON="$(read_env_value APP_FAVICON || true)"
APP_FAVICON="${APP_FAVICON:-}"

if [[ -z "${APP_FAVICON}" ]]; then
  rm -f "${DEST}"
  exit 0
fi

if [[ "${APP_FAVICON}" = /* ]]; then
  SOURCE="${APP_FAVICON}"
else
  SOURCE="${PROJECT_ROOT}/${APP_FAVICON}"
fi

if [[ ! -f "${SOURCE}" ]]; then
  echo "sync-branding: APP_FAVICON is set but file not found: ${SOURCE}" >&2
  exit 1
fi

mkdir -p "${FRONTEND_PUBLIC}"
cp "${SOURCE}" "${DEST}"
echo "sync-branding: installed ${DEST} from ${SOURCE}"
