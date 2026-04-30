# SWEB Blue/Green deploy (v1 + v2)

Цель: держать **v1** (основной стек в `/opt/app`, `docker-compose.yml`) и **v2** (параллельный API в `/opt/app-v2`, `docker-compose.v2.yml`) на одном VPS и переключать трафик **без пересборки**, с мгновенным rollback на v1.

## Архитектура и сеть

- **nginx** из основного compose проксирует на переменную `$api_upstream`, задаваемую в `deploy/sweb/upstreams/active-upstream.conf`.
- **v1**: `http://api:8000` (сервис в том же compose, что и nginx).
- **v2**: отдельный compose, публикация **`127.0.0.1:8001:8000`**. Контейнер nginx **не** в одной Docker-сети с `api_v2`, поэтому upstream для v2 — **`http://host.docker.internal:8001`** (в `deploy/sweb/docker-compose.yml` уже задано `extra_hosts: host.docker.internal:host-gateway`).

## Инцидент (include `active-upstream.conf`, падение 443) — RCA

1. Каталог **`deploy/sweb/upstreams`** смонтирован в nginx как **`/etc/nginx/conf.d` только для чтения (`:ro`)**. Скрипт, который писал `active-upstream.conf` **внутри контейнера** через `exec`, либо получал ошибку записи, либо не обновлял реальный файл на хосте — в результате nginx мог уйти в неконсистентное состояние при reload или стартовать без валидного include.
2. Имя вида **`sweb-api_v2-1:8000`** не гарантировано доступно из контейнера nginx, если v2 поднят **отдельным** `docker compose` (другая default-сеть).

**Текущее исправление:** `deploy/sweb/switch-upstream.sh` обновляет **`deploy/sweb/upstreams/active-upstream.conf` на хосте**, затем выполняет **`nginx -t`** и **`nginx -s reload`**. Для v2 используется **`host.docker.internal:8001`**.

## 1) Freeze v1

```bash
cd /opt/app
bash deploy/sweb/freeze-v1.sh "prod-v1-freeze-$(date +%Y%m%d)" /opt/app-v1
```

Проверки:

- `git -C /opt/app rev-parse HEAD` и tag SHA совпадают.
- `curl -fsS http://127.0.0.1/health`.

## 2) Поднять v2 рядом

```bash
git clone <repo-url> /opt/app-v2
cd /opt/app-v2
bash deploy/sweb/init-env-from-example.sh
nano /opt/app-v2/.env
docker compose -f deploy/sweb/docker-compose.v2.yml build
docker compose -f deploy/sweb/docker-compose.v2.yml up -d
bash deploy/sweb/smoke-v2.sh
```

Проверки:

- `docker compose -f deploy/sweb/docker-compose.v2.yml ps`
- `curl -fsS http://127.0.0.1:8001/health`

## 3) Preflight перед cutover на v2

Выполнять **до** переключения трафика (порядок обязателен):

| Шаг | Команда / действие |
|-----|---------------------|
| v2 жив | `curl -fsS http://127.0.0.1:8001/health` и при необходимости `/internal/health` |
| v1 стабилен | `curl -fsS http://127.0.0.1/health` |
| Синтаксис nginx | после обновления репозитория на `/opt/app`: `docker compose -f deploy/sweb/docker-compose.yml exec -T nginx nginx -t` |

При **любой** ошибке на preflight — трафик **не** переключать; при уже включённом v2 на проде — немедленно **rollback** (§5).

## 4) Переключение трафика (cutover)

Рабочая копия для скриптов — репозиторий **`/opt/app`** (там же лежит основной `docker-compose.yml` с nginx).

**v1** (по умолчанию после деплоя из git, если не меняли `active-upstream.conf`):

```bash
cd /opt/app
bash deploy/sweb/switch-upstream.sh v1
```

**v2**:

```bash
cd /opt/app
bash deploy/sweb/switch-upstream.sh v2
```

Скрипт сам проверяет `http://127.0.0.1:8001/health` перед переключением на v2, пишет **`deploy/sweb/upstreams/active-upstream.conf` на хосте**, затем `nginx -t` и reload.

Проверки **сразу после** switch:

- `curl -fsS https://<PUBLIC_API_HOST>/health`
- `curl -fsS https://<PUBLIC_API_HOST>/internal/health`
- выборочный `POST /process-image` (в т.ч. `furniture_portfolio`)

При сбое **443** или **health** — rollback (§5), не отлаживать «на живом» трафике.

## 5) Rollback (мгновенно на v1)

```bash
cd /opt/app
bash deploy/sweb/switch-upstream.sh v1
```

Затем снова проверить HTTPS `/health` и `/internal/health`.

После rollback **v2 можно оставить запущенным** для диагностики: `docker compose -f /opt/app-v2/deploy/sweb/docker-compose.v2.yml logs`, повторный `smoke-v2.sh`.

## 6) `git pull` на `/opt/app` и upstream

Файл `deploy/sweb/upstreams/active-upstream.conf` **в репозитории** задаёт дефолт **v1**. После `git pull` при конфликте или сбросе файла проверьте активный upstream и при необходимости снова выполните `switch-upstream.sh v1|v2`.

## 7) CI/CD

- Деплой **v1**: [`.github/workflows/deploy-sweb.yml`](../.github/workflows/deploy-sweb.yml)
- Деплой **v2**: [`.github/workflows/deploy-sweb-v2.yml`](../.github/workflows/deploy-sweb-v2.yml)
- Ручное переключение трафика: [`.github/workflows/switch-sweb-traffic.yml`](../.github/workflows/switch-sweb-traffic.yml)

## 8) Операционный чеклист релизного окна (кратко)

**До окна**

- [ ] На `/opt/app` актуальный `main`, `docker compose ... ps` зелёный, `/health` OK.
- [ ] На `/opt/app-v2` нужный коммит, `smoke-v2.sh` OK.
- [ ] Запасной план: дежурный с SSH `deploy`, ключ как в [SWEB_RUNBOOK.md](SWEB_RUNBOOK.md).

**В окне (cutover v2)**

- [ ] Preflight из §3.
- [ ] `bash deploy/sweb/switch-upstream.sh v2`.
- [ ] HTTPS `/health`, `/internal/health`, смоук бизнес-запроса.
- [ ] 10–15 мин мониторинг логов nginx/API при необходимости.

**При деградации 443/health**

- [ ] Немедленно `switch-upstream.sh v1`, проверка HTTPS health.
- [ ] Оставить v2 для разбора; не повторять cutover до устранения причины.

**После окна**

- [ ] Зафиксировать в тикете: время switch, версии SHA v1/v2, инциденты.
- [ ] Если остаётесь на v2: убедиться, что следующий `git pull` в `/opt/app` не перезапишет upstream без осознанного выбора (§6).
