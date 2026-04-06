#!/usr/bin/env bash
# One-time: create /opt/app/.env from .env.example if missing (run on VPS as root or deploy).
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
cd "${ROOT_DIR}"

if [[ -f .env ]]; then
  echo ".env already exists at ${ROOT_DIR}/.env — edit with: nano ${ROOT_DIR}/.env"
  exit 0
fi

if [[ ! -f .env.example ]]; then
  echo "ERROR: ${ROOT_DIR}/.env.example not found."
  exit 1
fi

cp .env.example .env
chmod 600 .env
echo "Created ${ROOT_DIR}/.env from .env.example"
echo "Edit required variables (INTERNAL_MODE=1, keys, JWT, Telegram, PUBLIC_BASE_URL):"
echo "  nano ${ROOT_DIR}/.env"
echo "Then: docker compose -f deploy/sweb/docker-compose.yml up -d"
