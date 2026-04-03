#!/usr/bin/env bash
set -euo pipefail

if [[ "${EUID}" -ne 0 ]]; then
  echo "Run as root: sudo bash deploy/sweb/bootstrap-vps.sh"
  exit 1
fi

APP_USER="${APP_USER:-deploy}"
APP_DIR="${APP_DIR:-/opt/app}"
APP_DOMAIN="${APP_DOMAIN:-}"

apt-get update
apt-get install -y ca-certificates curl gnupg ufw fail2ban git

install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
chmod a+r /etc/apt/keyrings/docker.gpg

. /etc/os-release
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
  ${VERSION_CODENAME} stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null

apt-get update
apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

id "${APP_USER}" >/dev/null 2>&1 || adduser --disabled-password --gecos "" "${APP_USER}"
usermod -aG docker "${APP_USER}"

mkdir -p "${APP_DIR}/deploy" "${APP_DIR}/data"
chown -R "${APP_USER}:${APP_USER}" "${APP_DIR}"

ufw allow OpenSSH
ufw allow 80/tcp
ufw allow 443/tcp
ufw --force enable
systemctl enable --now fail2ban

if [[ -n "${APP_DOMAIN}" ]]; then
  echo "Server prepared for domain: ${APP_DOMAIN}"
fi

echo "Bootstrap complete. Re-login to apply docker group for ${APP_USER}."
