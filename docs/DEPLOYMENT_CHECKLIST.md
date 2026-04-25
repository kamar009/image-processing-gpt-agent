# Deployment checklist

## Этап 2 — SpaceWeb, только публичный сценарий

Цель: сервис на VPS SpaceWeb по `deploy/sweb/docker-compose.yml` принимает изображение, обрабатывает и отдаёт файл по HTTPS. Внутренний MVP (Telegram, очередь) можно не включать.

- Пошаговый сценарий с комментариями и галочками: [STAGE2_SPACEWEB_PUBLIC.md](STAGE2_SPACEWEB_PUBLIC.md).
- Минимум в `.env` на сервере: ключи выбранного vision-провайдера (для текущего SWEB-дефолта: `SBER_VISION_AUTH_KEY` или `SBER_VISION_API_KEY`), `PUBLIC_BASE_URL=https://api.ваш-домен`, **`INTERNAL_MODE=0`** для этапа 2.
- После выкладки: `GET /health`, один `POST /process-image`, скачивание по `download_url` или `GET /outputs/{file_id}`; опционально `python scripts/integration_smoke.py --base-url https://api.ваш-домен --image path/to.png --strict`.

## Docker Compose

- Собрать и поднять: `docker compose up --build` из корня репозитория. Переменные см. [`.env.example`](../.env.example); при отсутствии `.env` compose не подхватит ключ (файл опционален, см. `docker-compose.yml`).
- Проверить `GET http://localhost:8080/health` — порт **8080** проброшен сервисом `proxy` (Caddy → `api:8000`).
- Для абсолютных `download_url` в JSON задайте `PUBLIC_BASE_URL` (например `http://localhost:8080` или боевой HTTPS-URL).
- Лимит тела запроса на proxy: **100MB** в [`deploy/Caddyfile`](../deploy/Caddyfile); при необходимости увеличьте и согласуйте с `MAX_UPLOAD_MB` в `.env`.

## Перед релизом

- Проверить `.env` (минимум ключи vision-провайдера, `MAX_UPLOAD_MB`, `OUTPUT_DIR`, `PUBLIC_BASE_URL` при необходимости).
- Убедиться, что установлены прод-зависимости: `pip install -r requirements.txt`.
- Выполнить быстрый smoke: `python scripts/integration_smoke.py --image path/to/image.png --strict`.
- Проверить очистку outputs: `python scripts/cleanup_outputs.py --dry-run`.
- Проверить диск-алерт: `python scripts/check_disk_space.py --path outputs --warn-usage-pct 85 --critical-usage-pct 95`.

## После релиза

- Проверить `GET /health` и `GET /metrics`.
- Сделать минимум 1 реальный `POST /process-image` по каждому `type`.
- Проверить, что в ответах присутствует `request_id` и заголовок `x-request-id`.
- Проверить, что scheduler cleanup активен (Windows Task Scheduler/cron).

## Rollback

- Если растут 5xx или есть деградация качества: откатить на предыдущую версию сервиса.
- После отката прогнать smoke повторно и сверить `/metrics` на снижение ошибок.

## Internal MVP on sweb

- Чеклист env, BotFather, whitelist, cron: [PRODUCTION_GO_LIVE.md](PRODUCTION_GO_LIVE.md).
- После деплоя: `BASE_URL=https://... python scripts/acceptance_remote_smoke.py` (опционально `INTERNAL_BEARER` для `/internal/presets`).
- После обновления репозитория при существующей БД: `python scripts/sync_internal_presets.py` (добавит недостающие `generation_presets`; см. `--dry-run`).
- Включить `INTERNAL_MODE=1`, `TELEGRAM_BOT_TOKEN`, `INTERNAL_ADMIN_IDS` в `.env`.
- Проверить whitelist: `POST /internal/admin/allow-user`.
- Проверить worker: `docker compose -f deploy/sweb/docker-compose.yml ps`.
- Проверить backup: `python scripts/backup_internal_db.py`.
- Выполнить релизный smoke: `bash deploy/sweb/release-smoke.sh https://api.your-domain`.

## Этап 7 — чек-лист релиза (internal MVP)

Использовать после merge в `main` и успешного workflow **Deploy SWEB** (или ручного деплоя по runbook).

- [ ] В GitHub зелёный **CI** на последнем коммите (`dev` / PR / `main`).
- [ ] Секреты `SWEB_*` заданы; при необходимости post-deploy curl — задан `SWEB_PUBLIC_BASE`.
- [ ] `GET /health` и `GET /internal/health` отдают 200; у internal нет `status=degraded`.
- [ ] Telegram: вход Mini App для пользователя из whitelist; при отказе — ожидаемый 403.
- [ ] `POST /internal/jobs` → задача в `queued` → worker доводит до `done`; `download_url` открывается.
- [ ] `GET /internal/jobs?user_id=...` возвращает историю.
- [ ] `docker compose ... logs api worker` — нет лавины ошибок после релиза.
- [ ] Проверка устойчивости: `docker compose -f deploy/sweb/docker-compose.yml restart api worker` (или перезагрузка VPS) — сервисы снова healthy, очередь обрабатывается.
