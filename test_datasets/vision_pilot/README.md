# Набор для пилота Vision

Здесь удобно держать тестовые изображения по сценариям (`banner`, `category`, `product`, `portfolio_interior` и т.д.).

## Политика git

Файлы `*.jpg`, `*.png` и т.п. в этой ветке каталога **не коммитятся** (см. корневой `.gitignore`), чтобы не раздувать репозиторий. Скопируйте набор локально или храните в общем архиве/хранилище команды.

Методология и итог решения по провайдеру: [docs/VISION_PILOT_REPO_POLICY.md](../../docs/VISION_PILOT_REPO_POLICY.md), [docs/VISION_PROVIDER_DECISION.md](../../docs/VISION_PROVIDER_DECISION.md).

## Структура (пример)

- `banner/` — кадры для баннеров  
- `category/` — обложки категорий  
- `product/` — карточки товара  
- `portfolio_interior/` — интерьеры  
- `furniture_portfolio/` — мебель на объекте  

Имена файлов должны быть стабильными, чтобы сводные таблицы пилота ссылались на те же пути.
