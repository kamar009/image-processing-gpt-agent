# QA-заметки (batch и ручная приёмка)

Обновляйте этот файл после прогонов `scripts/real_batch_run.py` и ручных тестов на **реальных** фото.

## Последний прогон

- Дата: 2026-03-30
- Источник изображений: каталог `outputs` (10 webp-файлов), команда `python scripts/real_batch_run.py --image-dir outputs --all-in-dir --count 10`.
- Отчёт: [real_batch_report.md](real_batch_report.md) — все 10 запросов **200**, `validation_ok=true`; предупреждения: низкая резкость на очень простых/плоских кадрах, highlight clipping для одного `product`.

## Edge cases и приоритеты

| Наблюдение | type | Серьёзность | Действие |
|------------|------|-------------|----------|
| Низкая резкость (`laplacian_var` около 0..3) на плоских сценах | banner / portfolio / category | P1 | Смягчить порог резкости для широких форматов |
| Пример: артефакты rembg | product / white | P1 | Постобработка маски |
| `possible_highlight_clipping` на `product` с белым фоном | product | P1 | Ослабить порог near_white для product/category |

_Добавляйте строки по мере нахождения проблем._

## Предупреждения из `validation_warnings`

Сводку см. в колонке `warnings` отчёта `real_batch_report.md`. Типичные эвристики:

- `low_sharpness_heuristic` — возможен «мягкий» исходник; при необходимости усилить резкость в пайплайне или ослабить порог.

## Критерий закрытия QA-итерации

- Нет открытых **P0** по [docs/BACKLOG.md](../docs/BACKLOG.md).
- Все целевые `type` дают 200 + `validation_ok=true` на репрезентативном наборе (8–12 файлов).
