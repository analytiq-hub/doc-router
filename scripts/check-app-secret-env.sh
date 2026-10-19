#!/usr/bin/env bash
# Fail if .env still uses NEXTAUTH_SECRET or omits APP_SECRET (local dev + compose deploy).
set -euo pipefail

env_file="${1:-.env}"

if [[ ! -f "$env_file" ]]; then
  echo "ERROR: Missing ${env_file}" >&2
  exit 1
fi

if grep -qE '^NEXTAUTH_SECRET=' "$env_file" 2>/dev/null; then
  echo "ERROR: Rename NEXTAUTH_SECRET to APP_SECRET in .env" >&2
  exit 1
fi

if ! grep -qE '^APP_SECRET=' "$env_file" 2>/dev/null; then
  echo "ERROR: APP_SECRET is required in .env" >&2
  exit 1
fi
