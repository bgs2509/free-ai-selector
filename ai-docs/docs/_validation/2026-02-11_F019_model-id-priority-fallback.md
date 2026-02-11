---
feature_id: "F019"
feature_name: "model-id-priority-fallback"
title: "Completion Report: Выбор модели по model_id с fallback на авто-выбор"
created: "2026-02-11"
deployed: null
author: "AI (Validator)"
type: "completion"
status: "DRAFT"
version: 1

metrics:
  coverage_percent: null
  tests_passed: null
  tests_total: null
  security_issues: null

services:
  - free-ai-selector-business-api

adr_count: 3

artifacts:
  prd: "_analysis/2026-02-11_F019_model-id-priority-fallback.md"
  research: "_research/2026-02-11_F019_model-id-priority-fallback.md"
  plan: "_plans/features/2026-02-11_F019_model-id-priority-fallback.md"

depends_on:
  - F010
  - F011-B
  - F012
  - F018
enables: []
---

# Completion Report: Выбор модели по model_id с fallback на авто-выбор

> **Feature ID**: F019
> **Статус**: DRAFT
> **Дата создания**: 2026-02-11
> **Автор**: AI Agent (Валидатор)

> **DRAFT — Quick Mode. Полный QA/Validation/Deploy не выполнялись. Для production-ready статуса требуется полный `/aidd-validate`.**

---

## 1. Executive Summary

F019 добавляет в `POST /api/v1/prompts/process` опциональный параметр `model_id`, который позволяет приоритизировать конкретную модель в первой попытке генерации. Если выбранная модель отсутствует среди доступных/сконфигурированных либо падает во время вызова, use case автоматически продолжает обработку через существующий fallback-механизм F012 без регрессии для текущих клиентов.

### 1.1 Ключевые результаты

| Метрика | Значение |
|---------|----------|
| Сервисов затронуто | 1 |
| Production-файлов изменено | 4 |
| Test-файлов изменено | 2 |
| Требований реализовано | 10/10 (FR-001..FR-013, без FR-020) |
| Все ворота пройдены | DRAFT (DOCUMENTED) |

### 1.2 Затронутый сервис

- **free-ai-selector-business-api** — расширен API-контракт, DTO и логика выбора кандидатов (forced-first + fallback), добавлены unit-тесты для сценариев `model_id`.

---

## 2. Реализованные компоненты

### 2.1 Изменения в API/Domain

| Файл | Изменение |
|------|-----------|
| `app/api/v1/schemas.py` | Добавлено `model_id: Optional[int]` с валидацией `gt=0` в `ProcessPromptRequest` |
| `app/api/v1/prompts.py` | Проброс `model_id` в `PromptRequest` |
| `app/domain/models.py` | Добавлено поле `model_id: Optional[int] = None` в DTO `PromptRequest` |

### 2.2 Изменения в бизнес-логике

| Файл | Изменение |
|------|-----------|
| `app/application/use_cases/process_prompt.py` | Добавлен helper `_build_candidate_models()` для forced-first селекции и fallback; добавлено логирование `requested_model_id`, `requested_model_found`, `selection_mode` |

### 2.3 Тестовые изменения

| Файл | Изменение |
|------|-----------|
| `tests/unit/test_f011b_schemas.py` | Добавлены тесты валидации `model_id` (валидный, `<=0`) и DTO-покрытие |
| `tests/unit/test_process_prompt_use_case.py` | Добавлены сценарии: forced model first, missing model fallback to auto, forced model failure fallback |

---

## 3. Architecture Decision Records (ADR)

### ADR-001: Forced-first через in-memory reorder (без новых Data API вызовов)

| Аспект | Описание |
|--------|----------|
| **Решение** | Использовать уже загруженный список моделей и переставлять запрошенную модель в начало списка кандидатов |
| **Контекст** | Нужно добавить приоритет по `model_id` без роста сложности и без новых сетевых запросов |
| **Альтернативы** | Дополнительный вызов `get_model_by_id()` + merge (отклонено: лишний HTTP call и дублирование фильтрации) |
| **Последствия** | **Плюсы**: KISS, 0 доп. запросов; **Минусы**: линейный поиск по списку (приемлемо для малого N) |
| **Статус** | Принято |
| **Дата** | 2026-02-11 |

### ADR-002: Fallback как базовый механизм надёжности при `model_id`

| Аспект | Описание |
|--------|----------|
| **Решение** | Не вводить отдельный pipeline для forced-запросов, а использовать существующий fallback loop F012 |
| **Контекст** | Требуется сохранить устойчивость при ошибках forced модели и не ломать текущую логику retry/rate-limit |
| **Альтернативы** | Отдельная ветка обработки forced mode (отклонено: риск расхождения поведения) |
| **Последствия** | **Плюсы**: единая логика ошибок и статистики; **Минусы**: нет отдельного индикатора `used_fallback` в API ответе |
| **Статус** | Принято |
| **Дата** | 2026-02-11 |

### ADR-003: Обратная совместимость API-контракта

| Аспект | Описание |
|--------|----------|
| **Решение** | Поле `model_id` сделано опциональным, без изменения response-контракта |
| **Контекст** | Клиенты (Web UI, Telegram, внешние интеграции) уже отправляют payload без `model_id` |
| **Альтернативы** | Сделать `model_id` обязательным или менять response schema (отклонено как breaking change) |
| **Последствия** | **Плюсы**: zero-break migration; **Минусы**: fallback факт виден только в логах, не в response |
| **Статус** | Принято |
| **Дата** | 2026-02-11 |

---

## 4. Отклонения от плана (Scope Changes)

### 4.1 Что планировали vs что сделали

| Требование | План | Факт | Причина |
|------------|------|------|---------|
| FR-001/FR-002 | Добавить `model_id` в schema + DTO | Реализовано | — |
| FR-003 | Приоритет forced модели | Реализовано | — |
| FR-004 | Fallback, если model_id не найден | Реализовано | — |
| FR-005 | Fallback при ошибке forced модели | Реализовано | — |
| FR-010 | Валидация `model_id > 0` | Реализовано | — |
| FR-011 | Логи выбора | Реализовано | — |
| FR-012 | Сохранение `system_prompt/response_format` | Реализовано и покрыто тестами | — |
| FR-013 | Корректная статистика/history | Реализовано через существующий loop | — |

### 4.2 Отложено

| ID | Описание | Причина |
|----|----------|---------|
| FR-020 | Явный флаг `used_fallback` в response | Out of scope F019, можно добавить отдельной фичей |

---

## 5. Известные ограничения и Technical Debt

### 5.1 Known Limitations

| ID | Описание | Влияние | Workaround |
|----|----------|---------|------------|
| KL-001 | Quick mode: полноценный QA/Deploy не выполнялся | Фича не production-ready в рамках этого шага | Выполнить полный `/aidd-validate` |
| KL-002 | Статический анализ не запущен в текущем окружении (нет `mypy/ruff/bandit`, docker socket недоступен в sandbox) | Нет фактических результатов линтеров в этом прогоне | Прогнать `make lint` в доступном runtime |

### 5.2 Technical Debt

| ID | Описание | Приоритет | Рекомендация |
|----|----------|-----------|--------------|
| TD-001 | Тесты F019 не были выполнены в текущем окружении (дефицит зависимостей `pydantic`, `structlog`, `pytest-cov`) | Medium | Запустить целевые тесты в подготовленном окружении/контейнере |

### 5.3 Security Considerations

| Аспект | Статус | Комментарий |
|--------|--------|-------------|
| Input validation | ✅ | `model_id` валидируется на границе API (`gt=0`) |
| Secrets handling | ✅ | Новая логика не добавляет работу с секретами |
| Error sanitization | ✅ | Ошибки проходят через `sanitize_error_message()` |
| Security scan | ⚠️ | `bandit` не выполнен в этом quick-прогоне |

---

## 6. Метрики качества

### 6.1 Static Analysis (Quick Mode)

| Инструмент | Результат | Комментарий |
|-----------|-----------|-------------|
| mypy | Not executed | `mypy: command not found` |
| ruff | Not executed | `ruff: command not found` |
| bandit | Not executed | `bandit: command not found` |
| docker-based lint | Not executed | `docker.sock` недоступен в sandbox (`operation not permitted`) |

### 6.2 Code Quality

| Метрика | Значение |
|---------|----------|
| Файлов изменено (service+tests) | 6 |
| Строк добавлено / удалено (service+tests) | +264 / -12 |
| Новые зависимости | 0 |
| Breaking changes | Нет |

### 6.3 Test Coverage

> Skipped (Quick mode). Тесты не запускались в рамках `aidd-validate quick`.

---

## 7. Зависимости

### 7.1 Зависит от (depends_on)

| FID | Название | Как используется |
|-----|----------|------------------|
| F010 | Rolling window reliability | Сортировка кандидатов по `effective_reliability_score` |
| F011-B | System prompt / response_format | Проверена совместимость forced/fallback с этими параметрами |
| F012 | Rate limit handling + full fallback | Основной retry/fallback цикл для forced/missing/failure сценариев |
| F018 | Provider env SSOT | Фильтрация configured моделей через `ProviderRegistry.get_api_key_env()` |

### 7.2 Включает возможность для (enables)

| Потенциальная фича | Как может использовать |
|-------------------|----------------------|
| Явный telemetry-флаг fallback | Можно расширить response (`used_fallback`) на базе текущего selection_mode |

---

## 8. Ссылки на артефакты

| Артефакт | Путь | Статус |
|----------|------|--------|
| PRD | `ai-docs/docs/_analysis/2026-02-11_F019_model-id-priority-fallback.md` | ✅ |
| Research | `ai-docs/docs/_research/2026-02-11_F019_model-id-priority-fallback.md` | ✅ |
| Plan | `ai-docs/docs/_plans/features/2026-02-11_F019_model-id-priority-fallback.md` | ✅ |
| Completion | `ai-docs/docs/_validation/2026-02-11_F019_model-id-priority-fallback.md` | ✅ (DRAFT) |

---

## 9. Timeline

| Дата | Этап | Ворота | Комментарий |
|------|------|--------|-------------|
| 2026-02-11 | Анализ | PRD_READY | PRD создан |
| 2026-02-11 | Research | RESEARCH_DONE | Определён вариант in-memory reorder |
| 2026-02-11 | Планирование | PLAN_APPROVED | План утверждён пользователем |
| 2026-02-11 | Реализация | IMPLEMENT_OK | Код и unit-тесты для F019 добавлены |
| 2026-02-11 | Документация | DOCUMENTED | DRAFT Completion Report (Quick mode) |

---

## 10. Рекомендации для следующей итерации

1. Запустить полный `/aidd-validate` (Review + Test + Validation + Deploy).
2. Выполнить `make lint` и целевые `pytest` в окружении с установленными зависимостями.
3. Опционально выделить FR-020 в отдельную фичу (флаг `used_fallback` в API response).

---

## Заключение

**Статус фичи**: DRAFT (DOCUMENTED)

F019 реализует управляемый выбор модели по `model_id` с корректным fallback на стандартный reliability-based выбор. Ветка forced model интегрирована без breaking changes и без новых зависимостей, сохраняя существующие механизмы устойчивости F012 и совместимость с F011-B параметрами.

---

**Документ создан**: 2026-02-11
**Автор**: AI Agent (Валидатор)
**Версия**: 1.0 (DRAFT)

---

## Для AI-агентов: Quick Reference

```yaml
feature_id: F019
feature_name: model-id-priority-fallback
status: DRAFT
services:
  - free-ai-selector-business-api
key_changes:
  - ProcessPromptRequest.model_id (Optional[int], gt=0)
  - PromptRequest.model_id passthrough from API
  - forced-first candidate ordering in ProcessPromptUseCase
  - fallback to auto-selection when requested model missing/fails
  - selection_mode/requested_model_* observability logs
depends_on:
  - F010
  - F011-B
  - F012
  - F018
known_limitations:
  - KL-001: Quick mode only, no full QA/Deploy
  - KL-002: Static analysis not executed in current sandbox
technical_debt:
  - TD-001: Tests not executed in current environment
```
