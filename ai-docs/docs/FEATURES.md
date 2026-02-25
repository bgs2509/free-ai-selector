# Реестр фич проекта

> Последнее обновление: 2026-02-25
> Автоматически обновляется при создании/завершении фич.

---

## Статистика

| Метрика | Значение |
|---------|----------|
| Всего фич | 8 |
| Deployed | 1 |
| In Progress | 6 |
| Archived | 0 |

---

## Активные фичи

| FID | Название | Статус | Дата | Сервисы | Артефакты |
|-----|----------|--------|------|---------|-----------|
| F012 | Rate Limit Handling для AI Провайдеров | IN_PROGRESS | 2026-01-29 | free-ai-selector-business-api | [PRD](_analysis/2026-01-29_F012_rate-limit-handling.md) |
| F019 | Выбор модели по model_id с fallback на авто-выбор | IN_PROGRESS | 2026-02-11 | free-ai-selector-business-api | [PRD](_analysis/2026-02-11_F019_model-id-priority-fallback.md) |
| F021 | Два независимых compose-файла: make nginx/make loc с корректным root_path | IMPLEMENT_OK | 2026-02-13 | free-ai-selector-business-api, free-ai-selector-data-postgres-api, free-ai-selector-telegram-bot, free-ai-selector-health-worker | [PRD](_analysis/2026-02-13_F021_compose-nginx-local-modes.md), [Research](_research/2026-02-13_F021_compose-nginx-local-modes.md), [Plan](_plans/features/2026-02-13_F021_compose-nginx-local-modes.md) |
| F022 | Исправление классификации ошибок LLM-провайдеров | IN_PROGRESS | 2026-02-25 | free-ai-selector-business-api | [PRD](_analysis/2026-02-25_F022_error-classifier-fix.md) |
| F023 | Cooldown для постоянных ошибок, exponential backoff и per-request telemetry | IN_PROGRESS | 2026-02-25 | free-ai-selector-business-api | [PRD](_analysis/2026-02-25_F023_error-resilience-and-telemetry.md) |
| F024 | Circuit Breaker для AI-провайдеров | IN_PROGRESS | 2026-02-25 | free-ai-selector-business-api | [PRD](_analysis/2026-02-25_F024_circuit-breaker.md) |
| F025 | Адаптивный Concurrency для массового прогона | IN_PROGRESS | 2026-02-25 | free-ai-selector-business-api | [PRD](_analysis/2026-02-25_F025_adaptive-concurrency.md) |

---

## Завершённые фичи

| FID | Название | Deployed | Сервисы | Артефакты |
|-----|----------|----------|---------|-----------|
| F001 | Аудит и очистка проекта | 2025-12-23 | — | [PRD](_analysis/2025-12-23_F001_project-cleanup-audit.md), [Research](_research/2025-12-23_F001_project-cleanup-audit.md), [Plan](_plans/features/2025-12-23_F001_project-cleanup.md), [Review](_validation/2025-12-23_F001_project-cleanup-review-report.md), [QA](_validation/2025-12-23_F001_project-cleanup-qa-report.md), [Validation](_validation/2025-12-23_F001_project-cleanup-validation-report.md), [RTM](rtm.md) |

---

## Архивные фичи

| FID | Название | Причина архивации | Дата |
|-----|----------|-------------------|------|
| — | — | — | — |

---

## Легенда статусов

| Статус | Описание | Этап пайплайна |
|--------|----------|----------------|
| `IN_PROGRESS` | Фича в разработке | 1-4 |
| `PLAN_APPROVED` | План утверждён | 3 |
| `IMPLEMENT_OK` | Код написан и передан в review | 4 |
| `IMPLEMENTED` | Код написан | 4 |
| `REVIEW_OK` | Код проверен | 5 |
| `QA_PASSED` | Тесты пройдены | 6 |
| `VALIDATED` | Все ворота пройдены | 7 |
| `DEPLOYED` | В продакшене | 8 |
| `ARCHIVED` | Отменена/устарела | — |

---

**Формат именования**: `{YYYY-MM-DD}_{FID}_{slug}-{type}.md`
**Спецификация**: См. `.aidd/docs/artifact-naming.md`
