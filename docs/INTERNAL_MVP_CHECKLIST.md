# Internal MVP acceptance checklist

## Access and auth

- `INTERNAL_MODE=1` enabled.
- Admin user IDs are configured in `INTERNAL_ADMIN_IDS`.
- `POST /internal/admin/allow-user` adds employee Telegram IDs to whitelist.
- `POST /internal/auth/telegram` returns user profile for allowed IDs.

## Generation flow

- `GET /internal/presets` returns active presets.
- `POST /internal/jobs` returns job ID with `queued` status (лимит активных задач на `user_id`: `INTERNAL_MAX_CONCURRENT_JOBS_PER_USER`).
- Worker picks up job and transitions to `processing` then `done` (параметры пайплайна из строки `generation_presets` по `preset_key`).
- `GET /internal/jobs/{job_id}?user_id=...` returns `download_url` on completion (user_id должен совпадать с владельцем).
- `GET /internal/jobs?user_id=...` — список задач пользователя.

## Runtime and reliability

- `GET /health` and `GET /internal/health` return 200; для internal ответ включает `db_ok`, `outputs_writable`, `disk_status` / `disk_volume_used_pct`; при сбое БД, тома или критическом заполнении диска — `status=degraded`.
- `GET /metrics` содержит те же поля `disk_volume_*` для внешнего мониторинга.
- `docker compose -f deploy/sweb/docker-compose.yml ps` shows healthy `api` and `worker`.
- Backup script runs: `python scripts/backup_internal_db.py`.
- Old outputs are periodically cleaned with `scripts/cleanup_outputs.py`.

## CI/CD

- CI (ветки `main`/`master`/`dev`): тесты + проверочная сборка Docker-образа — [`.github/workflows/ci.yml`](../.github/workflows/ci.yml).
- Прод-деплой по push в `main`/`master` или вручную — [`.github/workflows/deploy-sweb.yml`](../.github/workflows/deploy-sweb.yml); секреты `SWEB_*`, опционально `SWEB_PUBLIC_BASE` для post-deploy curl.
- Ручной деплой на хосте: `docker compose -f deploy/sweb/docker-compose.yml up -d --build`.
