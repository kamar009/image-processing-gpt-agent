# Этап 1: проверка модуля 2 (публичный API) на ноутбуке разработчика

Модуль 2: синхронный `POST /process-image`, `GET /health`, `GET /metrics`, `GET /outputs/{file_id}`, веб-форма `/` и `/ui`. Режим без internal: **`INTERNAL_MODE=0`** или переменная не задана.

## 1. Окружение

```bash
cd /path/to/image-processing-gpt-agent
pip install -r requirements-dev.txt
```

Для **реального** Vision при ручном прогоне без моков установите полный стек: `pip install -r requirements.txt` и ключи выбранного провайдера в `.env` (например **`OPENAI_API_KEY`**, или Sber / Yandex — см. `.env.example` и [INTEGRATION.md](INTEGRATION.md)). При ошибке провайдера возможен **fallback** или поля `vision_fallback_*` в ответе — `process-image` может завершиться успешно, но без полноценного анализа Vision.

Задайте **`PUBLIC_BASE_URL=http://127.0.0.1:8000`** для осмысленных абсолютных `download_url` в JSON (при прокси — порт прокси).

## 2. Автотесты (pytest)

```bash
pytest tests/test_api_smoke.py tests/test_metrics_disk.py tests/test_upload_limit.py -q
pytest tests/test_all_image_types.py tests/test_product_background_mock.py -q
pytest tests/test_furniture_portfolio_api.py tests/test_analyze_furniture_prompt.py tests/test_presets.py -q
```

## 3. Ручной прогон (uvicorn)

```bash
set INTERNAL_MODE=0
python -m uvicorn main:app --host 127.0.0.1 --port 8000
```

Проверки:

- `GET http://127.0.0.1:8000/health` → `{"status":"ok"}`
- `GET http://127.0.0.1:8000/metrics` → JSON со счётчиками и диском
- Браузер: `http://127.0.0.1:8000/` — форма загрузки
- Пример `POST /process-image` — см. [README.md](../README.md)

Интеграция по четырём базовым типам + опционально **`furniture_portfolio`**:

```bash
python scripts/integration_smoke.py --image path/to/photo.png --base-url http://127.0.0.1:8000 --strict
python scripts/integration_smoke.py --image path/to/photo.png --base-url http://127.0.0.1:8000 --strict --include-furniture
```

Второй вызов добавляет сценарий мебели с синтетическим PNG (минимум по длинной стороне) и `vision_provider=fallback`.

## 4. Docker Compose (опционально, ближе к прод-стеку)

```bash
docker compose up --build
```

Базовый URL: **`http://127.0.0.1:8080`**, в `.env` для контейнера: **`PUBLIC_BASE_URL=http://127.0.0.1:8080`**.

## Критерий готовности этапа 1

- Зелёные перечисленные pytest по публичному API.
- Локально: `/health`, `/metrics`, успешный `process-image` и скачивание по `/outputs/{file_id}` (или через `download_url`).

См. также [документация/модули-системы.md](../документация/модули-системы.md) (модуль 2).
