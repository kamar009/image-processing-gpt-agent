# Окружение и воспроизводимость

## Версия Python

- **Рекомендуется:** 3.12 (подходит 3.11–3.13).
- В продакшене и CI зафиксируйте **одинаковую минорную версию** Python, чтобы поведение `numpy`/`opencv`/`onnxruntime` не расходилось.

## Файлы зависимостей

| Файл | Назначение |
|------|------------|
| [`requirements-core.txt`](../requirements-core.txt) | FastAPI, Pillow, OpenCV, OpenAI, базовый стек без сегментации фона |
| [`requirements.txt`](../requirements.txt) | Полный прод-стек: `-r requirements-core.txt` + `rembg` + `onnxruntime` (нужно для `background=white` / `transparent` у product) |
| [`requirements-dev.txt`](../requirements-dev.txt) | CI/разработка без `rembg`/`onnx`: `-r requirements-core.txt` + `pytest` + `httpx` |

**Порядок установки для продакшена:**

```bash
python -m venv .venv
.venv\Scripts\activate   # Windows
pip install -U pip
pip install -r requirements.txt
```

**Для прогонов тестов без тяжёлых пакетов:**

```bash
pip install -r requirements-dev.txt
```

## Закрепление версий (опционально)

После проверки на целевой машине можно сохнать точный набор:

```bash
pip freeze > requirements-lock.txt
```

Развёртывание по lock-файлу: `pip install -r requirements-lock.txt` (внимание: lock привязан к ОС и версии Python).

## Переменные `.env` для продакшена

| Переменная | Обязательность | Описание |
|------------|----------------|----------|
| `OPENAI_API_KEY` | Рекомендуется | Без ключа Vision переходит на эвристический fallback (см. [`gpt_agent/analyze.py`](../gpt_agent/analyze.py)). |
| `OPENAI_MODEL` | Опционально | По умолчанию `gpt-4o`. |
| `OPENAI_STRUCTURED_PARSE` | Опционально | `1` — beta parse + fallback на `json_object`. |
| `OUTPUT_DIR` | Опционально | Каталог результатов (по умолчанию `./outputs`). |
| `MAX_UPLOAD_MB` | Опционально | Лимит загрузки (1–100 МБ). |
| `MAX_PROCESS_SECONDS` | Опционально | Порог логирования «превысили бюджет» (не обрывает запрос). |
| `PUBLIC_BASE_URL` | Опционально | Если задан (например `https://api.example.com`), в ответе будет абсолютный `download_url`. |
| `REMBG_WARMUP` | Опционально | `1` — прогрев `rembg` при старте приложения. |
| `VALIDATION_WARNINGS_AS_ERRORS` | Опционально | `1` — предупреждения валидатора → HTTP 422. |

Шаблон: [`.env.example`](../.env.example).

## Запуск сервера

```bash
uvicorn main:app --host 0.0.0.0 --port 8000
```

Проверка: `GET /health` → `{"status":"ok"}`.

## Batch-отчёт

После `python scripts/real_batch_run.py` файлы `reports/real_batch_report.json` (объект с полями `meta` и `rows`) и `reports/real_batch_report.md` фиксируют прогон QA. QA-заметки: [reports/qa_notes.md](../reports/qa_notes.md).


## Deployment checklist

Перед релизом и после релиза пройдите [docs/DEPLOYMENT_CHECKLIST.md](DEPLOYMENT_CHECKLIST.md).
