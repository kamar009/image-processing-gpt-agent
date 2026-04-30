#!/usr/bin/env bash
# Switch Blue/Green upstream by editing the host-mounted file (nginx conf.d is :ro).
# v2 runs in a separate compose stack; reach it via host port 8001 (see docker-compose.v2.yml).
set -euo pipefail

if [[ $# -ne 1 ]]; then
  echo "Usage: $0 <v1|v2>"
  exit 1
fi

TARGET="$1"
ROOT_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
SWEB_DIR="${ROOT_DIR}/deploy/sweb"
COMPOSE=(docker compose -f "${SWEB_DIR}/docker-compose.yml")
ACTIVE_FILE="${SWEB_DIR}/upstreams/active-upstream.conf"

case "$TARGET" in
  v1) UPSTREAM="http://api:8000" ;;
  v2) UPSTREAM="http://host.docker.internal:8001" ;;
  *)
    echo "Unknown target: $TARGET"
    exit 1
    ;;
esac

if [[ "$TARGET" == "v2" ]]; then
  echo "Pre-check: v2 must answer on host :8001"
  curl -fsS "http://127.0.0.1:8001/health" >/dev/null
fi

printf 'set $api_upstream %s;\n' "${UPSTREAM}" >"${ACTIVE_FILE}"

"${COMPOSE[@]}" exec -T nginx nginx -t
"${COMPOSE[@]}" exec -T nginx nginx -s reload

echo "Active upstream switched to ${TARGET} (${UPSTREAM})"
