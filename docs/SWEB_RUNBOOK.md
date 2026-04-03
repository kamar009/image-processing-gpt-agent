# SWEB VPS runbook (internal MVP)

## 1) VPS baseline

- Recommended: 2 vCPU, 4 GB RAM, 40+ GB NVMe, Ubuntu 22.04/24.04.
- Point `A` record for `api.your-domain` to VPS public IP.
- Copy project to `/opt/app`.

## 2) Bootstrap host

```bash
sudo APP_USER=deploy APP_DIR=/opt/app bash deploy/sweb/bootstrap-vps.sh
```

Then login as deploy user:

```bash
sudo -iu deploy
cd /opt/app
```

## 3) Configure env

Create `.env` from `.env.example` and fill:

- `OPENAI_API_KEY`
- `PUBLIC_BASE_URL=https://api.your-domain`
- `INTERNAL_MODE=1`
- `INTERNAL_ADMIN_IDS=11111111,22222222`
- `TELEGRAM_BOT_TOKEN=...`
- `INTERNAL_DB_PATH=/data/internal/internal.db`

Optional for Supabase:

- `SUPABASE_URL`
- `SUPABASE_ANON_KEY`
- `SUPABASE_SERVICE_ROLE_KEY`
- `SUPABASE_JWT_SECRET`

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
