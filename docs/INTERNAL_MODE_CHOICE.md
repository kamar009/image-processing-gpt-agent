# Выбор режима INTERNAL_MODE на проде

Режим задаётся в **`.env`** на сервере (`INTERNAL_MODE=0` или `1`). Docker Compose для SWEB **не** переопределяет это значение — правьте только `.env` и перезапускайте стек.

## Вариант A: только публичный API (`INTERNAL_MODE=0`)

**Когда уместно:** интеграции и веб-форма `POST /process-image`, без очереди и Telegram для сотрудников.

**Минимум:** ключи Vision-провайдера, `PUBLIC_BASE_URL`, см. этап 2 в [DEPLOYMENT_CHECKLIST.md](DEPLOYMENT_CHECKLIST.md).

**Проверка:** `GET /internal/health` может отвечать 200 с `"internal_mode": false` — это ожидаемо.

**Зафиксируйте для команды:** в тикете/вики укажите «прод = этап 2, internal выключен», чтобы не трактовать `internal_mode: false` как инцидент.

## Вариант B: внутренний MVP (`INTERNAL_MODE=1`)

**Когда уместно:** Telegram Mini App, whitelist, очередь `worker`, JWT для `/internal/jobs*`.

**Действия:** полный чеклист — [PRODUCTION_GO_LIVE.md](PRODUCTION_GO_LIVE.md), приёмка — [INTERNAL_MVP_CHECKLIST.md](INTERNAL_MVP_CHECKLIST.md), релиз — §7 [DEPLOYMENT_CHECKLIST.md](DEPLOYMENT_CHECKLIST.md).

**После включения:** `GET /internal/health` должен показывать `internal_mode: true`, без `status=degraded` при исправной БД и томе вывода.

## Переход A → B

1. Заполнить `TELEGRAM_BOT_TOKEN`, `INTERNAL_ADMIN_IDS`, при необходимости `INTERNAL_JWT_SECRET`, `INTERNAL_CORS_ORIGINS`.
2. Выставить `INTERNAL_MODE=1`, перезапустить `api` и `worker`.
3. `sync_internal_presets` (как в runbook).
4. Прогнать whitelist и smoke из [PRODUCTION_GO_LIVE.md](PRODUCTION_GO_LIVE.md).

## Переход B → A (редко)

1. Убедиться, что не нужны активные задачи в очереди или дождаться их завершения.
2. `INTERNAL_MODE=0`, перезапуск. Заранее сохраните бэкап SQLite при необходимости.

## См. также

- [SWEB_RUNBOOK.md](SWEB_RUNBOOK.md) — деплой и `.env` на VPS.
