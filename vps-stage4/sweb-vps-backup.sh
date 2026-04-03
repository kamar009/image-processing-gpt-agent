#!/usr/bin/env bash
set -euo pipefail
STAMP="$(date +%Y%m%d_%H%M%S)"
DEST=/var/backups/sweb-vps
OUT="${DEST}/sweb-vps-backup_${STAMP}.tar.zst"
TMP="$(mktemp -d)"
trap 'rm -rf "${TMP}"' EXIT
mkdir -p "${TMP}/backup"
cp -aL /etc/ssh "${TMP}/backup/" 2>/dev/null || true
cp -aL /etc/ufw "${TMP}/backup/" 2>/dev/null || true
cp -aL /etc/fail2ban "${TMP}/backup/" 2>/dev/null || true
mkdir -p "${TMP}/backup/sudoers.d"
cp -aL /etc/sudoers.d/90-ops-nopasswd "${TMP}/backup/sudoers.d/" 2>/dev/null || true
if [[ -f /etc/sweb-vps/alerts.env ]]; then
  echo "(redacted) alerts.env present" >"${TMP}/backup/alerts-readme.txt"
fi
ufw status verbose >"${TMP}/backup/ufw-status.txt" 2>/dev/null || true
dpkg --get-selections >"${TMP}/backup/dpkg-selections.txt" 2>/dev/null || true
systemctl list-unit-files --state=enabled >"${TMP}/backup/systemd-enabled.txt" 2>/dev/null || true
tar -C "${TMP}" -cf - backup | zstd -19 -T0 -o "${OUT}"
ls -1t "${DEST}"/sweb-vps-backup_*.tar.zst 2>/dev/null | tail -n +15 | xargs -r rm -f
/usr/bin/logger -t sweb-vps-backup "created ${OUT}"
