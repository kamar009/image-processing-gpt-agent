# Политика выкладки после разделения v1 / v2

После того как на VPS подняты параллельно **`/opt/app` (v1)** и **`/opt/app-v2` (v2)**, договорённость по умолчанию:

## Разработка и фичи → v2

- Новый код вливается в **`main`** (или согласованную ветку) и проверяется локально через [`docker-compose.v2.yml`](../deploy/sweb/docker-compose.v2.yml) — см. [LOCAL_V2_DEV.md](LOCAL_V2_DEV.md).
- Деплой на сервер для проверки «как на проде»: только каталог **`/opt/app-v2`**, workflow **[`deploy-sweb-v2.yml`](../.github/workflows/deploy-sweb-v2.yml)** (`git pull`, `compose.v2` build/up, `smoke-v2.sh`).
- Публичный домен остаётся на **v1**, пока не пройден **cutover gate** и не выполнен `switch-upstream.sh v2` по [SWEB_BLUE_GREEN_DEPLOY.md](SWEB_BLUE_GREEN_DEPLOY.md).

## v1 (`/opt/app`) — ограниченные изменения

- Деплой v1: **`deploy-sweb.yml`** — использовать для **горячих исправлений**, безопасности и срочных правок стабильной линии.
- Не смешивать крупные фичи с v1 без явного решения «откатываемся на v1 как единственный прод».
- После каждого `git pull` в `/opt/app` проверять upstream: `bash deploy/sweb/check-active-upstream.sh` (см. §6 Blue/Green).

## Краткая схема

| Цель | Где код на сервере | Workflow |
|------|-------------------|----------|
| Новая функциональность | `/opt/app-v2` | Deploy SWEB v2 |
| Стабильный публичный трафик (по умолчанию) | `/opt/app` + nginx | Deploy SWEB (v1) |
| Переключить домен на новую линию | `switch-upstream.sh` из `/opt/app` | вручную / `switch-sweb-traffic` |

## См. также

- [SWEB_BLUE_GREEN_DEPLOY.md](SWEB_BLUE_GREEN_DEPLOY.md) — preflight, gate, rollback.
- [V2_BACKLOG_PRIORITIES.md](V2_BACKLOG_PRIORITIES.md) — приоритеты продукта на горизонте v2.
