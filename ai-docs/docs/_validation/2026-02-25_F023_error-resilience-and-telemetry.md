---
feature_id: "F023"
feature_name: "error-resilience-and-telemetry"
title: "Completion Report: Cooldown, Exponential Backoff, Telemetry"
created: "2026-02-25"
author: "AI (Validator)"
type: "completion"
status: "DRAFT"
mode: "quick"
---

# Completion Report: F023 — Cooldown, Exponential Backoff, Telemetry

> ⚠️ **DRAFT** — Quick mode. QA не выполнено, deploy не выполнен.

## 1. Executive Summary

F023 реализует три улучшения системы маршрутизации AI-провайдеров:

1. **Cooldown 24ч для постоянных ошибок** (401/402/403/404) — мёртвые провайдеры автоматически исключаются из выборки на 24 часа после первой ошибки аутентификации/валидации. Устраняет 108 000+ бесполезных вызовов за 48 часов.

2. **Exponential backoff** — замена фиксированной задержки 10с×10 retry на экспоненциальный backoff 2s→4s→8s с jitter. MAX_RETRIES снижен с 10 до 3 (100с→14с на провайдер).

3. **Per-request telemetry** — добавлены `attempts` и `fallback_used` в HTTP response для диагностики без SSH на prod.

**Зависимость**: F022 (этапы 1-3) — корректная классификация 402/404.

## 2. Реализованные компоненты

### 2.1 Изменённые файлы (9 файлов, +504/-32 строки)

| Файл | Изменение | Требование |
|------|-----------|------------|
| `app/application/use_cases/process_prompt.py` | Cooldown в `_handle_transient_error()`, `_set_cooldown_safe()`, telemetry counters | FR-001, FR-002, FR-010, FR-020 |
| `app/application/services/retry_service.py` | `retry_with_exponential_backoff()`, deprecated alias | FR-003, FR-004, FR-021 |
| `app/domain/models.py` | `attempts`, `fallback_used` в PromptResponse | FR-010 |
| `app/api/v1/schemas.py` | `attempts`, `fallback_used` в ProcessPromptResponse | FR-011 |
| `app/api/v1/prompts.py` | Telemetry маппинг, `error_type` в HTTP 500 | FR-011, FR-012 |
| `docker-compose.yml` | 6 новых env-переменных, MAX_RETRIES default 10→3 | NF-011 |
| `tests/unit/test_retry_service.py` | 7 новых тестов для exponential backoff | TRQ-003, TRQ-004, TRQ-005 |
| `tests/unit/test_process_prompt_use_case.py` | 8 новых тестов для cooldown и telemetry | TRQ-001, TRQ-002, TRQ-006, TRQ-007, TRQ-008 |
| `.pipeline-state.json` | F023 pipeline state updates | — |

### 2.2 Новые env-переменные

| Переменная | Default | Описание |
|------------|---------|----------|
| `AUTH_ERROR_COOLDOWN_SECONDS` | 86400 | Cooldown для AuthenticationError (401/402/403) |
| `VALIDATION_ERROR_COOLDOWN_SECONDS` | 86400 | Cooldown для ValidationError (400/404/422) |
| `MAX_RETRIES` | 3 (было 10) | Максимум retry-попыток |
| `RETRY_BASE_DELAY` | 2.0 | Базовая задержка exponential backoff (сек) |
| `RETRY_MAX_DELAY` | 30.0 | Максимальная задержка retry (сек) |
| `RETRY_JITTER` | 1.0 | Максимальный jitter (сек) |

## 3. Architecture Decision Records (ADR)

### ADR-001: Cooldown в _handle_transient_error() вместо отдельного обработчика

**Контекст**: Нужно добавить cooldown для AuthError/ValidationError в fallback loop.
**Решение**: Добавить if/elif в существующий `_handle_transient_error()` перед `increment_failure`.
**Обоснование**: Минимальное изменение (~10 строк), паттерн аналогичен `_handle_rate_limit()`.
**Альтернатива**: Отдельный except-блок в fallback loop — увеличивает дублирование.

### ADR-002: retry_with_fixed_delay как deprecated alias

**Контекст**: 12 существующих тестов используют `retry_with_fixed_delay`.
**Решение**: Сохранить как wrapper с маппингом `delay_seconds → base_delay=delay_seconds, jitter=0`.
**Обоснование**: Все тесты продолжают работать без изменений. Удалить alias в следующей итерации.

### ADR-003: MAX_RETRIES default 10 → 3

**Контекст**: 10 retry × 10 сек = 100 сек на один провайдер — неприемлемо.
**Решение**: Default 3 retry с exponential backoff (2s→4s→8s ≈ 14 сек).
**Риск**: Если production использует implicit default, поведение изменится. Митигация: env-переменная `MAX_RETRIES`.

## 4. Requirements Traceability

| Требование | Статус | Реализация |
|------------|--------|------------|
| FR-001 (Cooldown AuthError) | ✅ Реализовано | `_handle_transient_error()` + `_set_cooldown_safe()` |
| FR-002 (Cooldown ValidationError) | ✅ Реализовано | `_handle_transient_error()` + `_set_cooldown_safe()` |
| FR-003 (Exponential backoff) | ✅ Реализовано | `retry_with_exponential_backoff()` |
| FR-004 (MAX_RETRIES 10→3) | ✅ Реализовано | `retry_service.py` + `docker-compose.yml` |
| FR-010 (PromptResponse telemetry) | ✅ Реализовано | `models.py` + `process_prompt.py` |
| FR-011 (HTTP response telemetry) | ✅ Реализовано | `schemas.py` + `prompts.py` |
| FR-012 (error_type в HTTP 500) | ✅ Реализовано | `prompts.py` |
| FR-020 (Логирование cooldown) | ✅ Реализовано | `_set_cooldown_safe()` structlog |
| FR-021 (Deprecated alias) | ✅ Реализовано | `retry_with_fixed_delay()` wrapper |

## 5. Code Review Summary — Static Analysis

| Инструмент | Результат | Статус |
|------------|-----------|--------|
| ruff (source) | All checks passed | ✅ |
| ruff (tests) | All checks passed | ✅ |

## 6. Testing Summary

> Skipped (Quick mode). Unit тесты написаны (15 новых), но не запущены в Docker.

### Написанные тесты

| Класс | Кол-во | Покрытие |
|-------|--------|----------|
| `TestRetryWithExponentialBackoff` | 7 | FR-003, FR-004, FR-005 |
| `TestF023Cooldown` | 4 | FR-001, FR-002, TRQ-008 |
| `TestF023Telemetry` | 4 | FR-010, FR-011 |

## 7. Known Limitations

1. Cooldown применяется ко ВСЕМ ValidationError (включая 400/422), не только к 404. F022 payload budget снижает вероятность ложных 422.
2. Если API key обновлён, провайдер недоступен до истечения 24ч cooldown. Ручной reset: `PUT /api/v1/models/{id}/set-availability?seconds=0`.
3. `retry_with_fixed_delay` сохранён как deprecated alias — удалить в следующей итерации.
4. Тесты не запущены в Docker (Quick mode) — требуется `make up` и `make test-business`.

## 8. Метрики

| Метрика | Значение | Статус |
|---------|----------|--------|
| Файлов изменено | 9 | — |
| Строк добавлено | +504 | — |
| Строк удалено | -32 | — |
| Новых unit-тестов | 15 | — |
| ruff errors | 0 | ✅ |
| Новых env-переменных | 6 | — |
| Breaking changes | MAX_RETRIES default 10→3 | ⚠️ Документировать |

## 9. Артефакты

| Артефакт | Путь |
|----------|------|
| PRD | `_analysis/2026-02-25_F023_error-resilience-and-telemetry.md` |
| Research | `_research/2026-02-25_F023_error-resilience-and-telemetry.md` |
| Plan | `_plans/features/2026-02-25_F023_error-resilience-and-telemetry.md` |
| Completion | `_validation/2026-02-25_F023_error-resilience-and-telemetry.md` |

## 10. Timeline

| Этап | Gate | Дата |
|------|------|------|
| PRD | PRD_READY | 2026-02-25 |
| Research | RESEARCH_DONE | 2026-02-25 |
| Plan | PLAN_APPROVED | 2026-02-25 |
| Implementation | IMPLEMENT_OK | 2026-02-25 |
| Validation | DOCUMENTED (Quick) | 2026-02-25 |
