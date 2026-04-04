# QA по реальным изображениям (фаза 2)

Цель бэклога: **8–12** реальных файлов по основным сценариям без P0-дефектов.

## Шаблон учёта

| # | Файл / пресет | type / preset_key | Результат | Примечание |
|---|----------------|-------------------|----------|------------|
| 1 | | | OK / FAIL | |
| 2 | | | | |

## Как гонять батч локально

```bash
pip install requests
python scripts/real_batch_run.py --image-dir "path/to/photos" --all-in-dir --count 12
```

Отчёты: `reports/real_batch_report.md`, `reports/real_batch_report.json`.

## Публичный API по типам

Минимум по одному вызову `POST /process-image` на каждый `type`: `product`, `category`, `banner`, `portfolio_interior` — см. [INTEGRATION.md](INTEGRATION.md).

## Internal / Mini App

Для каждого активного `preset_key` из `GET /internal/presets`: одна успешная задача `done` и скачивание по `download_url`.

## Ошибки (P0)

Ответы должны содержать понятный `detail` (строка). В Mini App ошибки показываются из тела ответа; при необходимости смотрите `request_id` в JSON.
