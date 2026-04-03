# Политика хранения каталога `outputs`

## Цели

- Не допускать неограниченного роста диска из-за временных файлов обработки.
- Иметь предсказуемый retention и способ аварийной очистки.

## Рекомендуемые параметры (по умолчанию для MVP)

| Параметр | Значение | Примечание |
|----------|----------|------------|
| Retention по времени | **72 часа** | Файлы старше порога удаляются скриптом очистки. |
| Каталог | Из `OUTPUT_DIR` или `./outputs` | Не коммитить содержимое в git. |
| Ручной просмотр перед удалением | `--dry-run` | Всегда сначала dry-run на проде. |

## Команды

Из корня проекта:

```bash
# Показать, что будет удалено
python scripts/cleanup_outputs.py --dry-run

# Удалить файлы старше 72 часов
python scripts/cleanup_outputs.py --max-age-hours 72
```

Другой каталог:

```bash
python scripts/cleanup_outputs.py --dir /var/lib/image-mvp/outputs --max-age-hours 48
```

## Периодический запуск

### Windows (Планировщик заданий)

1. Действие: запуск `python` с аргументами, например:
   - Программа: `C:\path\to\project\.venv\Scripts\python.exe`
   - Аргументы: `C:\path\to\project\scripts\cleanup_outputs.py --max-age-hours 72`
   - Рабочая папка: корень проекта
2. Триггер: ежедневно (или каждые 12 ч при высокой нагрузке).
3. Первый раз выполните вручную с `--dry-run` и проверьте журнал.

### Linux (cron)

Пример записи (ежедневно в 03:15):

```cron
15 3 * * * cd /opt/image-mvp && /opt/image-mvp/.venv/bin/python scripts/cleanup_outputs.py --max-age-hours 72 >> /var/log/image-mvp-cleanup.log 2>&1
```

## Мониторинг и лимиты

- Контролируйте свободное место на томе с `OUTPUT_DIR`.
- Для алерта используйте `python scripts/check_disk_space.py --path outputs --warn-usage-pct 85 --critical-usage-pct 95`.
- При необходимости ужесточите retention (например `--max-age-hours 24`) или добавьте внешний лимит квоты на каталог.

## Исключения

Файлы, которые должны храниться дольше retention, нужно копировать в постоянное хранилище (S3, БД, CMS) на стороне клиента; сервис MVP рассчитан на временные артефакты по `file_id`.
