# Интеграция клиента с API

## Базовый вызов

`POST /process-image` — `multipart/form-data`:

- `image` — файл
- `type` — `product` | `category` | `banner` | `portfolio_interior` | `furniture_portfolio` (детали и поля: [FURNITURE_PORTFOLIO_API.md](FURNITURE_PORTFOLIO_API.md))
- `background` — опционально (`keep`, `white`, ...)
- `format` — опционально (`webp`, `jpeg`, `png`)

Для **`type=furniture_portfolio`** дополнительно (обязательны):

- `furniture_scene` — enum, см. §3 в [FURNITURE_PORTFOLIO_API.md](FURNITURE_PORTFOLIO_API.md)
- `output_target` — enum (`site`, `banner`, `social_vk`, `social_telegram`, `social_max`), размеры выхода — §4 того же файла

Опционально: `enhanced` — усиленная **программная** обработка v1 (шум/резкость и т.п.; см. `operations`: `furniture_enhanced_software_v1`). Значения «вкл»: `1` / `true` / `on` (регистр не важен). Включается **только** флагом в запросе (форма/API). Автоудаление людей **не** выполняется.

Минимальный размер **входа** для `furniture_portfolio`: длинная сторона **≥ 1200 px** после EXIF-ориентации (константа `FURNITURE_PORTFOLIO_MIN_INPUT_LONG_SIDE_PX` в коде); иначе **422** с текстом в `detail`.

Успех: обычно **200** с телом JSON; при проблемах валидации выхода — **422** (см. `validation_ok`, `validation_errors`).

## Поля ответа, которые стоит обработать

| Поле | Назначение |
|------|------------|
| `file_id` | Идентификатор для `GET /outputs/{file_id}` |
| `download_url` | Относительный путь или абсолютный URL, если задан `PUBLIC_BASE_URL` |
| `validation_ok` | Итог проверок размера/качества |
| `validation_warnings` | Не фатально, если не включен `VALIDATION_WARNINGS_AS_ERRORS` |
| `validation_errors` | Причины 422 |
| `processing_time_ms`, `vision_ms`, ... | Диагностика производительности |

Дополнительно для **`furniture_portfolio`** (если тип выбран): `furniture_scene`, `output_target`, `enhanced_requested`, `enhanced_applied`, `people_detected` (оценка Vision), предупреждение о людях в кадре может дублироваться в `validation_warnings` (обработка при этом может завершиться успешно).

## Коды ошибок HTTP

| Код | Типичная причина | Действие клиента |
|-----|------------------|------------------|
| **400** | Неверный `type` / enum, пустой файл, битое изображение | Исправить запрос; показать `detail` |
| **413** | Файл больше `MAX_UPLOAD_MB` | Сжать или увеличить лимит в `.env` |
| **422** | Не прошла валидация результата (`validation_ok=false`), неверные поля `furniture_portfolio`, слишком маленький вход | Показать `detail` и/или `validation_errors`; исправить параметры или исходник |
| **502** | Ошибка этапа Vision/анализа (внешний сервис) | Повтор с backoff; проверить ключ и квоты OpenAI |
| **500** | Внутренняя ошибка пайплайна (в т.ч. `rembg` без `onnxruntime`) | Логировать; проверить зависимости и логи сервера |

Контракт ошибки: JSON вида `{"detail": "...", "request_id": "..."}`; `request_id` дублируется в заголовке `x-request-id`.

## Smoke-тест из репозитория

С поднятым сервером:

```bash
python scripts/integration_smoke.py --image path/to/file.png --strict
```

`--strict` завершает процесс с ненулевым кодом, если любой из сценариев не вернул 200.

По умолчанию четыре типа (`product`, `category`, `banner`, `portfolio_interior`) используют **один** переданный файл. Для проверки **`furniture_portfolio`** добавьте флаг **`--include-furniture`**: скрипт сгенерирует PNG с длинной стороной 1200 px (минимум по спеке) и вызовет API с `furniture_scene` / `output_target` и `vision_provider=fallback`.

## Базовая телеметрия

- `GET /metrics` — JSON-сводка счетчиков (`requests_total`, `status_4xx`, `status_5xx`) и среднего времени `process_image_avg_ms`.
- Клиентам обычно не нужно вызывать `/metrics`; endpoint предназначен для мониторинга и диагностики.

## Проверка доступности

Перед серией запросов:

```http
GET /health
```

Ожидается `{"status":"ok"}`.
