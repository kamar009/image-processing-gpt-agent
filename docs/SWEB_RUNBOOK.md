# SWEB VPS runbook (internal MVP)

**Этап 2 — только публичный API** (загрузка → обработка → скачивание, без обязательного Telegram/internal): пошаговая инструкция с контрольными точками для руководителя и исполнителя — [STAGE2_SPACEWEB_PUBLIC.md](STAGE2_SPACEWEB_PUBLIC.md). Режим **`INTERNAL_MODE`** на сервере задаётся в **`/opt/app/.env`** (в Docker Compose не переопределяется).

## 1) VPS baseline

- Recommended: 2 vCPU, 4 GB RAM, 40+ GB NVMe, Ubuntu 22.04/24.04.
- Point `A` record for `api.your-domain` to VPS public IP.
- Copy project to `/opt/app`.

## 2) Bootstrap host

```bash
sudo APP_USER=deploy APP_DIR=/opt/app bash deploy/sweb/bootstrap-vps.sh
```

Если после этого `git pull` под **root** пишет `dubious ownership` (каталог принадлежит `deploy`), один раз:

```bash
git config --global --add safe.directory /opt/app
```

Then login as deploy user:

```bash
sudo -iu deploy
cd /opt/app
```

## 2b) SSH с рабочей машины (агент / разработчик)

Для ручного входа на VPS и деплоя (`git pull`, `docker compose` в `/opt/app`) используйте:

| Параметр | Значение |
|----------|----------|
| Пользователь SSH | **`deploy`** |
| Приватный ключ (локально) | **`~/.ssh/sweb_deploy_github2`** (файл ключа с именем `sweb_deploy_github2`) |

Пример:

```bash
ssh -i ~/.ssh/sweb_deploy_github2 deploy@<SWEB_HOST>
```

Рекомендуется запись в `~/.ssh/config`: `Host`, `HostName`, `User deploy`, `IdentityFile ~/.ssh/sweb_deploy_github2`, `IdentitiesOnly yes`.

**Важно:** пользователь **`ops`** (или другой без прав на `/opt/app/.git`) может получить `Permission denied` при `git pull` — выполняйте обновление кода от **`deploy`** или через `sudo -iu deploy`.

Для агентов Cursor в репозитории зафиксировано то же правило: [`.cursor/rules/sweb-ssh-deploy.mdc`](../.cursor/rules/sweb-ssh-deploy.mdc).

## 3) Configure env

Краткий чеклист вывода Mini App в прод: [PRODUCTION_GO_LIVE.md](PRODUCTION_GO_LIVE.md).

Первый файл окружения на VPS (после `git clone` в `/opt/app`):

```bash
cd /opt/app
bash deploy/sweb/init-env-from-example.sh
nano /opt/app/.env
```

Секреты в репозиторий не коммитить. Для случайного `INTERNAL_JWT_SECRET` (≥32 символа): `openssl rand -base64 48`.

Create `.env` from `.env.example` and fill:

- `SBER_VISION_AUTH_KEY` (preferred) or `SBER_VISION_API_KEY`
- `PUBLIC_BASE_URL=https://api.your-domain`
- `INTERNAL_MODE=1`
- `INTERNAL_ADMIN_IDS=11111111,22222222`
- `TELEGRAM_BOT_TOKEN=...`
- `INTERNAL_DB_PATH=/data/internal/internal.db`
- `INTERNAL_JWT_SECRET` — случайная строка ≥32 символов (Bearer для Mini App).
- `INTERNAL_CORS_ORIGINS` — если Web App на другом домене, перечислите origins через запятую.

Production default for `deploy/sweb/docker-compose.yml` is now:

- `VISION_PROVIDER=sber`
- `SBER_VISION_MODEL=GigaChat-2-Max`

These defaults are set in compose for SWEB only and do not change local defaults.
If needed, override on server with:

- `PROD_VISION_PROVIDER=...`
- `PROD_SBER_VISION_MODEL=...`

Mini App: после деплоя URL вида `https://api.your-domain/miniapp/` — его указывают в BotFather как Web App.

Optional for Supabase:

- `SUPABASE_URL`
- `SUPABASE_ANON_KEY`
- `SUPABASE_SERVICE_ROLE_KEY`
- `SUPABASE_JWT_SECRET`

## 3b) После успешного `git pull` на VPS

1. Код актуален: `cd /opt/app && git pull` (при необходимости `git config --global --add safe.directory /opt/app` — см. §2).
2. Если файла **`.env` ещё нет**: `bash deploy/sweb/init-env-from-example.sh`, затем `nano /opt/app/.env` и заполните переменные (§3).
3. Сборка и запуск:

```bash
cd /opt/app
docker compose -f deploy/sweb/docker-compose.yml build
docker compose -f deploy/sweb/docker-compose.yml up -d
```

4. Проверка **API** через nginx на **порту 80** (до выпуска сертификата `deploy/sweb/nginx.conf` по умолчанию только HTTP; HTTPS включается после `issue-cert.sh`):

```bash
curl -fsS http://127.0.0.1/health
```

Либо напрямую в контейнер `api` (если с хоста порт 80 закрыт):

```bash
docker compose -f deploy/sweb/docker-compose.yml exec -T api python -c "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:8000/health').read().decode())"
```

5. Синхронизация пресетов (как в GitHub Actions):

```bash
docker compose -f deploy/sweb/docker-compose.yml exec -T api python scripts/sync_internal_presets.py --db /data/internal/internal.db
```

6. Автодеплой из репозитория: **Actions → Deploy SWEB → Run workflow** (или push в `main`).

**Примечание:** до `issue-cert.sh` в репозитории используется **HTTP-only** `nginx.conf` (порт 80, прокси на API + webroot для Certbot). После выпуска сертификата скрипт подставляет конфиг из `nginx.tls.template`. Если nginx всё ещё в `Restarting`, проверьте логи: `docker compose -f deploy/sweb/docker-compose.yml logs nginx --tail 50`.

## 4) First deploy

```bash
docker compose -f deploy/sweb/docker-compose.yml build
docker compose -f deploy/sweb/docker-compose.yml up -d
```

Issue certificate:

```bash
bash deploy/sweb/issue-cert.sh api.your-domain devops@your-domain
```

## 5) Smoke checks

- `curl -fsS https://api.your-domain/health`
- `curl -fsS https://api.your-domain/internal/health`
- Open `https://api.your-domain/docs`

## 5b) Ветки и CI/CD (этап 7)

- **`dev`** — интеграция и превью; на push/PR запускается [`.github/workflows/ci.yml`](../.github/workflows/ci.yml) (pytest на Python 3.11/3.12 + сборка Docker-образа без push в registry).
- **`main`** / **`master`** — прод; merge из `dev` после зелёного CI. На push в `main`/`master` дополнительно запускается [`.github/workflows/deploy-sweb.yml`](../.github/workflows/deploy-sweb.yml) (SSH на VPS: `git pull`, `docker compose build && up`, затем `sync_internal_presets` в контейнере `api` с ретраями).

Секреты репозитория GitHub (Settings → Secrets):

| Secret | Назначение |
|--------|------------|
| `SWEB_HOST` | IP или hostname VPS |
| `SWEB_USER` | SSH-пользователь (например `deploy`) |
| `SWEB_SSH_KEY` | приватный ключ SSH (полный PEM) |
| `SWEB_PUBLIC_BASE` | опционально: `https://api.your-domain` — после деплоя runner выполнит `curl` на `/health` и `/internal/health` |

Ручной деплой: кнопка **Actions → Deploy SWEB → Run workflow**.

Чек-лист перед/после релиза: раздел **«Этап 7 — чек-лист релиза»** в [DEPLOYMENT_CHECKLIST.md](DEPLOYMENT_CHECKLIST.md).

## 6) Operations

- Update app:

```bash
git pull
docker compose -f deploy/sweb/docker-compose.yml build
docker compose -f deploy/sweb/docker-compose.yml up -d
```

- Check logs (ротация json-file: ~20 MB × 4 файла на контейнер, см. `deploy/sweb/docker-compose.yml`):

```bash
docker compose -f deploy/sweb/docker-compose.yml logs -f api
docker compose -f deploy/sweb/docker-compose.yml logs -f worker
```

- Мониторинг доступности: `GET /health` и `GET /internal/health` (последний при `INTERNAL_MODE=1` проверяет SQLite и запись в `OUTPUT_DIR`; при проблемах `status=degraded`).

- Backup db file:

```bash
cp /var/lib/docker/volumes/imageprocessinggptagent_internal_data/_data/internal.db "/opt/app/data/internal-$(date +%F).db"
```

## 7) Обслуживание диска и retention

- Метрики тома в ответах **`GET /metrics`** и **`GET /internal/health`** (`disk_volume_used_pct`, `disk_volume_free_gb`). Пороги: переменные **`DISK_USAGE_WARN_PCT`** / **`DISK_USAGE_CRITICAL_PCT`** в `.env` (по умолчанию 85 / 95); при критическом заполнении internal health — **`status=degraded`**.
- Пример **cron** (cleanup + проверка диска через `docker compose exec`): [deploy/sweb/cron-maintenance.example](../deploy/sweb/cron-maintenance.example).
