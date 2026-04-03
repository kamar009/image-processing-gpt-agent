#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${1:-http://127.0.0.1}"

echo "Checking health endpoints on ${BASE_URL}"
curl -fsS "${BASE_URL}/health" >/dev/null
curl -fsS "${BASE_URL}/internal/health" >/dev/null
echo "Health checks passed"
