# Интеграция клиента с API

## Базовый вызов

`POST /process-image` — `multipart/form-data`:

- `image` — файл
- `type` — `product` | `category` | `banner` | `portfolio_interior`
- `background` — опционально (`keep`, `white`, ...)
- `format` — опционально (`webp`, `jpeg`, `png`)

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

## Коды ошибок HTTP

| Код | Типичная причина | Действие клиента |
|-----|------------------|------------------|
| **400** | Неверный `type` / enum, пустой файл, битое изображение | Исправить запрос; показать `detail` |
| **413** | Файл больше `MAX_UPLOAD_MB` | Сжать или увеличить лимит в `.env` |
| **422** | Не прошла валидация результата (`validation_ok=false`) | Показать `validation_errors`; при необходимости повторить с другими параметрами |
| **502** | Ошибка этапа Vision/анализа (внешний сервис) | Повтор с backoff; проверить ключ и квоты OpenAI |
| **500** | Внутренняя ошибка пайплайна (в т.ч. `rembg` без `onnxruntime`) | Логировать; проверить зависимости и логи сервера |

Контракт ошибки: JSON вида `{"detail": "...", "request_id": "..."}`; `request_id` дублируется в заголовке `x-request-id`.

## Smoke-тест из репозитория

С поднятым сервером:

```bash
python scripts/integration_smoke.py --image path/to/file.png --strict
```

`--strict` завершает процесс с ненулевым кодом, если любой из четырех вызовов не вернул 200.

## Базовая телеметрия

- `GET /metrics` — JSON-сводка счетчиков (`requests_total`, `status_4xx`, `status_5xx`) и среднего времени `process_image_avg_ms`.
- Клиентам обычно не нужно вызывать `/metrics`; endpoint предназначен для мониторинга и диагностики.

## Проверка доступности

Перед серией запросов:

```http
GET /health
```

Ожидается `{"status":"ok"}`.
