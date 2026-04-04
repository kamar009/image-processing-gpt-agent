# Site image processing MVP

Сервис принимает изображение, опционально вызывает **OpenAI Vision**, прогоняет пресеты (`product`, `category`, `banner`, `portfolio_interior`) и отдает WebP/JPEG/PNG под лимиты сайта.

## Быстрый запуск

1. Python 3.11+ (рекомендуется 3.12).
2. Установка зависимостей:

```bash
pip install -r requirements.txt
```

Для разработки и CI без тяжелого стека rembg/onnx:

```bash
pip install -r requirements-dev.txt
```

3. Скопируйте `.env.example` в `.env` и задайте `OPENAI_API_KEY`.
4. Запуск:

```bash
uvicorn main:app --host 0.0.0.0 --port 8000
```

- Интерактивная документация: **http://127.0.0.1:8000/docs**
- Веб-форма (загрузка, пресеты, превью, скачивание): **http://127.0.0.1:8000/ui** (то же самое по `/`)
- Базовые метрики: `GET /metrics`
- Проверка живости: `GET /health`

Пример запроса:

```bash
curl -s -X POST "http://127.0.0.1:8000/process-image" ^
  -F "image=@C:\path\to\photo.jpg" ^
  -F "type=product" ^
  -F "background=keep" ^
  -F "format=webp"
```

## Docker Compose

Сервис `api` (FastAPI) и reverse proxy **Caddy** с лимитом тела запроса **100MB** (файл [deploy/Caddyfile](deploy/Caddyfile); при необходимости согласуйте с `MAX_UPLOAD_MB`). Том Docker `outputs_data` монтируется в каталог `OUTPUT_DIR=/data/outputs` внутри контейнера `api`.

1. Скопируйте `.env.example` в `.env`, задайте `OPENAI_API_KEY`. Для корректных абсолютных ссылок `download_url` с хоста задайте `PUBLIC_BASE_URL` (например `http://localhost:8080`).
2. Запуск:

```bash
docker compose up --build
```

3. В браузере: **http://127.0.0.1:8080/** (UI и API через proxy). Контейнер `api` слушает порт 8000 только внутри сети compose.

Проверка: `GET http://127.0.0.1:8080/health`.

Чеклист и заметки по продакшену: [docs/DEPLOYMENT_CHECKLIST.md](docs/DEPLOYMENT_CHECKLIST.md).

## Internal MVP mode (Telegram + whitelist)

Для внутреннего использования без платежей включите:

- `INTERNAL_MODE=1`
- `TELEGRAM_BOT_TOKEN=<bot_token>`
- `INTERNAL_ADMIN_IDS=11111111,22222222`

Новые endpoint-ы:

- `GET /internal/health` (при `INTERNAL_MODE=1`: `db_ok`, `outputs_writable`; `status=degraded` если БД или каталог вывода недоступны)
- `POST /internal/auth/telegram` (валидация init data)
- `POST /internal/admin/allow-user` (whitelist)
- `GET /internal/presets` (активные сценарии из БД `generation_presets`)
- `POST /internal/jobs` (тело: `user_id`, `preset_key`, `image_base64`; лимит размера как у `MAX_UPLOAD_MB`; не больше `INTERNAL_MAX_CONCURRENT_JOBS_PER_USER` активных задач на пользователя)
- `GET /internal/jobs?user_id=...&limit=50` (история задач пользователя)
- `GET /internal/jobs/{job_id}?user_id=...` (статус `queued` / `processing` / `done` / `failed`; `user_id` обязателен и должен совпадать с владельцем задачи)

Фоновая обработка: воркер читает пресет из БД (`image_type`, `style`) и гоняет тот же пайплайн, что и публичный API. Запуск: `python worker.py`.

После обновления кода на сервере с уже существующей `internal.db` можно добавить недостающие строки пресетов: `python scripts/sync_internal_presets.py` (или `--dry-run` для просмотра).

## SWEB production deploy

Готовый набор для sweb находится в `deploy/sweb/`:

- `docker-compose.yml` (nginx + api + worker + certbot)
- `nginx.conf`
- `bootstrap-vps.sh`
- `issue-cert.sh`

Пошаговый runbook и описание веток **dev/main**, CI и секретов деплоя: [docs/SWEB_RUNBOOK.md](docs/SWEB_RUNBOOK.md).
Supabase SQL схема и RLS политики: `deploy/supabase/schema.sql`, `deploy/supabase/rls.sql`.

## Окружение и воспроизводимость

- Python: 3.11-3.13; в проде и CI фиксируйте одинаковую минорную версию.
- Полный стек: `pip install -r requirements.txt`.
- Dev/CI: `pip install -r requirements-dev.txt`.
- Подробно: [docs/ENVIRONMENT.md](docs/ENVIRONMENT.md).

## Переменные окружения

См. [`.env.example`](.env.example). Основные:

- `OPENAI_API_KEY`, `OPENAI_MODEL`, `OPENAI_STRUCTURED_PARSE`
- `OUTPUT_DIR`, `PUBLIC_BASE_URL`
- `MAX_UPLOAD_MB`, `MAX_PROCESS_SECONDS`
- `REMBG_WARMUP`, `VALIDATION_WARNINGS_AS_ERRORS`
- `DISK_USAGE_WARN_PCT`, `DISK_USAGE_CRITICAL_PCT` — том с `OUTPUT_DIR` в `GET /metrics` и `/internal/health`

В ответе `POST /process-image` доступны метрики этапов: `vision_ms`, `pipeline_wall_ms`, `pipeline_body_ms`, `encode_ms`.

## Минимальный чеклист приемки

Для каждого `type` проверить:

- `POST /process-image` возвращает ожидаемые размеры/формат
- `validation_ok=true`
- размер не превышает лимит пресета
- `GET /outputs/{file_id}` отдает файл

Целевые параметры:

- `product`: `800x800`, до `150 KB`
- `category`: `1200x800`, до `250 KB`
- `banner`: `1920x900`, до `400 KB`
- `portfolio_interior`: `1600x900`, до `350 KB`

Если входной файл больше `MAX_UPLOAD_MB`, ожидается `413`.

## Частые ошибки

- `401 Unauthorized` от OpenAI: проверьте `OPENAI_API_KEY` в `.env`.
- `502 vision/analysis failed`: проблема внешнего Vision этапа (ключ, лимиты, сеть).
- `500` при `background=white/transparent`: проверьте `onnxruntime`.
- `413 image too large`: уменьшите вход или увеличьте `MAX_UPLOAD_MB`.

## Политика хранения outputs

- Политика и расписание: [docs/OUTPUTS_POLICY.md](docs/OUTPUTS_POLICY.md)
- Очистка:

```bash
python scripts/cleanup_outputs.py --dry-run
python scripts/cleanup_outputs.py --max-age-hours 72
python scripts/check_disk_space.py --path outputs --warn-usage-pct 85 --critical-usage-pct 95
```

## Интеграционный smoke

- Интеграция клиента: [docs/INTEGRATION.md](docs/INTEGRATION.md)
- Smoke:

```bash
python scripts/integration_smoke.py --image "path/to/image.png" --strict
```

## Batch QA

```bash
pip install requests
python scripts/real_batch_run.py
```

Для своего каталога:

```bash
python scripts/real_batch_run.py --image-dir "D:/photos" --all-in-dir --count 12
```

Результаты: `reports/real_batch_report.md`, `reports/real_batch_report.json`, `reports/qa_notes.md`.

Приоритеты улучшений: [docs/BACKLOG.md](docs/BACKLOG.md).

Deployment checklist: [docs/DEPLOYMENT_CHECKLIST.md](docs/DEPLOYMENT_CHECKLIST.md).

## Git и GitHub

В репозитории ведутся ветки **`main`** (прод) и **`dev`** (интеграция). Локально после `git init` привяжите remote и отправьте обе ветки:

```bash
git remote add origin https://github.com/kamar009/image-processing-gpt-agent.git
git push -u origin main
git push -u origin dev
```

Репозиторий: [github.com/kamar009/image-processing-gpt-agent](https://github.com/kamar009/image-processing-gpt-agent). Имя и email коммитера при необходимости: `git config user.name "..."` и `git config user.email "..."` (локально в каталоге проекта или `--global`).

Секрет **`SWEB_PUBLIC_BASE`** в GitHub → *Settings → Secrets and variables → Actions* задаётся только в веб-интерфейсе (API-токен с правом на секреты не хранится в проекте). Значение: публичный базовый URL API, например `https://api.example.com` (без завершающего `/`).
