# Вывод internal MVP и Mini App в прод

Краткий чеклист **фазы 1** (прод-конфигурация и Mini App). Подробнее: [SWEB_RUNBOOK.md](SWEB_RUNBOOK.md), [`.env.example`](../.env.example).

## 1. Переменные `.env` на VPS

| Переменная | Обязательно | Примечание |
|------------|-------------|------------|
| `OPENAI_API_KEY` | да | |
| `INTERNAL_MODE` | да | `1` |
| `TELEGRAM_BOT_TOKEN` | да | тот же бот, что в BotFather |
| `INTERNAL_ADMIN_IDS` | да | Telegram id админов через запятую |
| `INTERNAL_JWT_SECRET` | **рекомендуется** | ≥32 символов; без секрета Mini App работает в legacy-режиме с `user_id` |
| `PUBLIC_BASE_URL` | да для ссылок | `https://api.example.com` без `/` в конце |
| `INTERNAL_DB_PATH` | в Docker | например `/data/internal/internal.db` |
| `OUTPUT_DIR` | в Docker | например `/data/outputs` |
| `INTERNAL_CORS_ORIGINS` | если Mini App на **другом** домене | через запятую, точные origin |

Проверка локально (после `copy .env.example .env`):

```bash
python scripts/check_internal_env.py
python scripts/check_internal_env.py --strict
```

## 2. Telegram BotFather

- Создайте/выберите бота, получите token → `TELEGRAM_BOT_TOKEN`.
- **Menu Button / Web App** → URL: **`https://<ваш-домен>/miniapp/`** (тот же API-хост, если статика отдаётся FastAPI).

## 3. Whitelist сотрудников

Из под админа или с сервера (один раз на человека):

```bash
curl -sS -X POST "https://api.example.com/internal/admin/allow-user" \
  -H "Content-Type: application/json" \
  -d "{\"telegram_id\": 123456789, \"comment\": \"employee\"}"
```

`telegram_id` — число из профиля Telegram (через @userinfobot и т.п.).

## 4. Cron на VPS

Скопируйте строки из [deploy/sweb/cron-maintenance.example](../deploy/sweb/cron-maintenance.example) в `crontab -e` пользователя `deploy`. Сначала:

```bash
docker compose -f deploy/sweb/docker-compose.yml exec -T api python scripts/cleanup_outputs.py --dir /data/outputs --dry-run
```

## 5. После деплоя

- Автоматическая проверка доступности (если задан `BASE_URL`):

```bash
set BASE_URL=https://api.example.com
python scripts/acceptance_remote_smoke.py
```

- Ручные чеклисты: [DEPLOYMENT_CHECKLIST.md](DEPLOYMENT_CHECKLIST.md) (internal + этап 7), [INTERNAL_MVP_CHECKLIST.md](INTERNAL_MVP_CHECKLIST.md).

## 6. Наблюдаемость (кратко)

- Периодический опрос **`GET /internal/health`**: при `status=degraded` или `disk_status=critical` — триггер в вашем мониторинге (Uptime Kuma, cron + curl, …).
- Метрики диска также в **`GET /metrics`**.
