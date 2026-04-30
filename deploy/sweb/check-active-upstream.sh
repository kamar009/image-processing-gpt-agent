#!/usr/bin/env bash
# Print active Blue/Green upstream from the host file (after git pull, verify traffic target).
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
F="${ROOT_DIR}/deploy/sweb/upstreams/active-upstream.conf"

if [[ ! -f "$F" ]]; then
  echo "ERROR: missing $F" >&2
  exit 1
fi

echo "=== deploy/sweb/upstreams/active-upstream.conf ==="
cat "$F"
echo "=== interpretation ==="
if grep -q 'api:8000' "$F"; then
  echo "Traffic target: v1 (http://api:8000)"
elif grep -q 'host.docker.internal:8001' "$F"; then
  echo "Traffic target: v2 (http://host.docker.internal:8001)"
else
  echo "Traffic target: UNKNOWN — edit manually or run: bash deploy/sweb/switch-upstream.sh v1|v2"
  exit 2
fi
