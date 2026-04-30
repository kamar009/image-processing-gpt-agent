# Локальная разработка со стеком v2

Тот же код репозитория, что и для v1, но отдельный Compose-файл: отдельные Docker-тома и API на **`127.0.0.1:8001`**. Удобно как основной цикл разработки после разделения v1/v2 на проде.

## Требования

- Docker и Docker Compose v2.
- Файл **`.env` в корне репозитория** (рядом с `Dockerfile`): `deploy/sweb/docker-compose.v2.yml` подключает его как `../../.env` относительно каталога `deploy/sweb`.

## Команды (из корня клона)

```bash
docker compose -f deploy/sweb/docker-compose.v2.yml build
docker compose -f deploy/sweb/docker-compose.v2.yml up -d
bash deploy/sweb/smoke-v2.sh
# или явный URL:
bash deploy/sweb/smoke-v2.sh http://127.0.0.1:8001
```

Проверки вручную:

- `curl -fsS http://127.0.0.1:8001/health`
- `curl -fsS http://127.0.0.1:8001/docs`
- `POST http://127.0.0.1:8001/process-image` (в т.ч. `furniture_portfolio`).

Логи:

```bash
docker compose -f deploy/sweb/docker-compose.v2.yml logs -f api_v2 worker_v2
```

Остановка:

```bash
docker compose -f deploy/sweb/docker-compose.v2.yml down
```

Полный сброс данных v2 (тома outputs/internal для этого стека):

```bash
docker compose -f deploy/sweb/docker-compose.v2.yml down -v
```

## Windows

Запускайте те же команды из **корня репозитория** в PowerShell или Git Bash; пути в compose рассчитаны на расположение файла под `deploy/sweb/`.

## Связь с продом

- Выкладка тестового стека на VPS: **`/opt/app-v2`** и [deploy-sweb-v2 workflow](../.github/workflows/deploy-sweb-v2.yml) — см. [SWEB_V2_DEPLOY_POLICY.md](SWEB_V2_DEPLOY_POLICY.md).
- Публичное переключение трафика на v2 только по [SWEB_BLUE_GREEN_DEPLOY.md](SWEB_BLUE_GREEN_DEPLOY.md) (preflight, gate, rollback).
