# Приоритеты бэклога (линия v2)

Документ для согласования с командой и руководителем: что делать после разделения v1/v2. Отмечайте статус и владельца в тикетах; здесь — единая точка входа по ссылкам.

| Приоритет | Тема | Назначение | Документация / артефакты | Статус |
|-----------|------|------------|---------------------------|--------|
| 1 | **furniture_portfolio** | Качество сценария, промпты, контракт API | [FURNITURE_PORTFOLIO_API.md](FURNITURE_PORTFOLIO_API.md), `config/furniture_portfolio_prompts.json` | Заполнить |
| 2 | **INTERNAL_MODE / Mini App** | Нужен ли полный internal на этом хосте; включение и приёмка | [INTERNAL_MODE_CHOICE.md](INTERNAL_MODE_CHOICE.md), [PRODUCTION_GO_LIVE.md](PRODUCTION_GO_LIVE.md), [INTERNAL_MVP_CHECKLIST.md](INTERNAL_MVP_CHECKLIST.md) | Заполнить |
| 3 | **UX** | Веб-форма `/ui`, Mini App — без ломки API | [документация/резюме-для-руководителя.md](../документация/резюме-для-руководителя.md) (этап 3), `static/` | Заполнить |
| 4 | **Vision** | Выбор провайдера по пилоту, бюджет, SLO | [VISION_PROVIDER_DECISION.md](VISION_PROVIDER_DECISION.md), [VISION_PILOT_REPO_POLICY.md](VISION_PILOT_REPO_POLICY.md) | Заполнить |

## Локальный и серверный контур v2

- Разработка: [LOCAL_V2_DEV.md](LOCAL_V2_DEV.md).
- Выкладка фич: [SWEB_V2_DEPLOY_POLICY.md](SWEB_V2_DEPLOY_POLICY.md).

## Cutover на публичный v2

Когда линия v2 готова заменить v1 под доменом — только по gate в [SWEB_BLUE_GREEN_DEPLOY.md](SWEB_BLUE_GREEN_DEPLOY.md) §8 и чеклисту §9.
