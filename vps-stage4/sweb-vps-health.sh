#!/usr/bin/env bash
set -euo pipefail
HOST="$(hostname -s)"
DATE="$(date -Is)"
ISSUES=()

pcent="$(df -P / | awk 'NR==2 {gsub(/%/,"",$5); print $5}')"
if [[ "${pcent:-0}" -gt 85 ]]; then
  ISSUES+=("disk root ${pcent}%")
fi

if ! systemctl is-active --quiet ssh; then
  ISSUES+=("ssh.service inactive")
fi
if ! systemctl is-active --quiet fail2ban; then
  ISSUES+=("fail2ban inactive")
fi

if ! ufw status 2>/dev/null | grep -q "Status: active"; then
  ISSUES+=("ufw not active")
fi

if [[ "${#ISSUES[@]}" -eq 0 ]]; then
  /usr/bin/logger -t sweb-vps-health -p daemon.info "ok disk=${pcent}%"
  exit 0
fi

LIST=""
for line in "${ISSUES[@]}"; do
  LIST="${LIST}${line}"$'\n'
done
MSG="<b>${HOST}</b> ALERT
<code>${DATE}</code>
<pre>${LIST}</pre>"
/usr/bin/logger -t sweb-vps-health -p daemon.warning "${ISSUES[*]}"
/usr/local/sbin/sweb-vps-alerts.sh "${MSG}" || true
exit 1
