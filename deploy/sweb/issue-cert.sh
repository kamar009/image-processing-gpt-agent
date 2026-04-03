#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 2 ]]; then
  echo "Usage: $0 <domain> <email>"
  exit 1
fi

DOMAIN="$1"
EMAIL="$2"

docker compose -f deploy/sweb/docker-compose.yml up -d nginx
docker compose -f deploy/sweb/docker-compose.yml run --rm certbot certonly \
  --webroot -w /var/www/certbot \
  --email "${EMAIL}" \
  --agree-tos \
  --no-eff-email \
  -d "${DOMAIN}"

sed -i "s/APP_DOMAIN/${DOMAIN}/g" deploy/sweb/nginx.conf
docker compose -f deploy/sweb/docker-compose.yml up -d nginx

echo "Certificate issued for ${DOMAIN}"
