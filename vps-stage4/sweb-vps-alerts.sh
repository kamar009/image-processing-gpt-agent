#!/usr/bin/env bash
# Optional Telegram: /etc/sweb-vps/alerts.env (chmod 600):
#   TELEGRAM_BOT_TOKEN=...
#   TELEGRAM_CHAT_ID=...
set -euo pipefail
ENV=/etc/sweb-vps/alerts.env
if [[ -f "$ENV" ]]; then
  # shellcheck disable=SC1090
  set -a
  # shellcheck disable=SC1090
  source "$ENV"
  set +a
fi
send_tg() {
  local msg="$1"
  if [[ -n "${TELEGRAM_BOT_TOKEN:-}" && -n "${TELEGRAM_CHAT_ID:-}" ]]; then
    curl -sS -m 15 -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
      -d "chat_id=${TELEGRAM_CHAT_ID}" \
      -d "parse_mode=HTML" \
      --data-urlencode "text=${msg}" >/dev/null || true
  fi
}
send_tg "$@"
