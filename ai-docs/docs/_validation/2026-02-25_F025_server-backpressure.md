---
feature_id: "F025"
feature_name: "server-backpressure"
title: "Completion Report: F025 — Server-side Backpressure"
created: "2026-02-25"
author: "AI (Validator)"
type: "completion"
status: "DRAFT"
mode: "quick"
---

# Completion Report: F025 — Server-side Backpressure (DRAFT)

> **DRAFT** — Quick validation mode. QA не выполнено, deploy не произведён.

## 1. Executive Summary

F025 добавляет дифференциацию HTTP-ответов при ошибках в Business API: HTTP 429 (все провайдеры rate-limited) с `Retry-After`, HTTP 503 (сервис недоступен) с `Retry-After`, стандартные `X-RateLimit-*` заголовки. Ранее все ошибки возвращали HTTP 500. Реализация затрагивает 6 файлов, 0 новых зависимостей, 0 миграций БД.

## 2. Реализованные компоненты

### 2.1 Доменные исключения (`app/domain/exceptions.py`)

| Класс | Назначение | Поля |
|-------|-----------|------|
| `AllProvidersRateLimited` | Все провайдеры вернули 429 | `retry_after_seconds`, `attempts`, `providers_tried` |
| `ServiceUnavailable` | Сервис недоступен (нет моделей, CB open, нет ключей) | `retry_after_seconds`, `reason` |

### 2.2 Агрегация ошибок (`app/application/use_cases/process_prompt.py`)

- Добавлены `error_types`, `retry_after_values`, `skipped_by_cb`, `providers_tried`
- Трекинг типа каждой ошибки в fallback loop
- После loop: all RateLimit → `AllProvidersRateLimited`, attempts==0 → `ServiceUnavailable`, mixed → `Exception`
- `raise Exception("No active/configured...")` → `raise ServiceUnavailable(...)`

### 2.3 HTTP responses (`app/api/v1/prompts.py`)

- `AllProvidersRateLimited` → HTTP 429 + `Retry-After` + `ErrorResponse` body
- `ServiceUnavailable` → HTTP 503 + `Retry-After` + `ErrorResponse` body
- `Exception` → HTTP 500 (как прежде, только реальные баги)
- OpenAPI `responses={429: ..., 503: ...}`

### 2.4 ErrorResponse schema (`app/api/v1/schemas.py`)

```
ErrorResponse: error, message, retry_after, attempts, providers_tried, providers_available
```

### 2.5 slowapi (`app/main.py`)

- `headers_enabled=True` — включены `X-RateLimit-*` заголовки
- Кастомный `rate_limit_handler` — возвращает `ErrorResponse` формат

### 2.6 Новые env-переменные

| Переменная | Default | Описание |
|-----------|---------|----------|
| `ALL_RATE_LIMITED_RETRY_AFTER` | 60 | Default Retry-After для 429 |
| `SERVICE_UNAVAILABLE_RETRY_AFTER` | 30 | Default Retry-After для 503 |
| `PROCESS_RATE_LIMIT` | "100/minute" | slowapi лимит на /process |

## 3. Architecture Decision Records (ADR)

### ADR-001: Типизированные исключения вместо HTTP-кодов в use case

**Решение**: Use case бросает доменные исключения (`AllProvidersRateLimited`, `ServiceUnavailable`), API-слой маппит на HTTP-коды.

**Обоснование**: Separation of Concerns — бизнес-логика не знает о HTTP.

### ADR-002: 429 только при ALL RateLimit

**Решение**: HTTP 429 только если ВСЕ ошибки == RateLimitError. Смешанные (часть 429, часть 500) → HTTP 500.

**Обоснование**: Семантически корректно — 429 означает "повтори позже", что имеет смысл только если все провайдеры перегружены.

### ADR-003: slowapi headers_enabled

**Решение**: Включить `X-RateLimit-*` заголовки глобально.

**Обоснование**: Стандартные заголовки, 0 cost, любой HTTP-клиент может использовать.

## 4. Scope Changes

| Компонент | План (PRD) | Факт | Причина |
|-----------|------------|------|---------|
| FR-001: HTTP 429 | В scope | Реализовано | — |
| FR-002: HTTP 503 | В scope | Реализовано | — |
| FR-010: ErrorResponse | В scope | Реализовано | — |
| FR-004: Rate limit /process | В scope | OpenAPI responses добавлены, `@limiter.limit` не добавлен | Требует `Request` первым аргументом — конфликт с текущей сигнатурой |
| FR-021: Debug mode | Should-have | Отложено | YAGNI для MVP |

## 5. Known Limitations

- slowapi in-memory storage — счётчики сбрасываются при рестарте (приемлемо для MVP)
- `X-RateLimit-*` показывают лимит slowapi (клиентский), не лимит LLM-провайдеров
- Telegram Bot не обрабатывает 429/503 специально (показывает generic ошибку — не ломается)
- `providers_available` всегда 0 в error body (для точного значения нужен рефакторинг execute())

## 6. Static Analysis Results

| Инструмент | Результат | Статус |
|-----------|----------|--------|
| ruff | All checks passed | Pass |
| mypy (F025 файлы) | 0 новых ошибок | Pass |
| mypy (весь проект) | 7 pre-existing ошибок в других файлах | N/A |
| bandit | 0 critical/high | Pass |
| pytest | 36/36 passed | Pass |

## 7. Testing

- **Unit tests**: 36 passed, 0 failed
- **New tests (F025)**: 6 тестов в `TestF025Backpressure`
- **Updated tests**: 2 (`test_execute_no_active_models`, `test_execute_no_configured_models`)
- **Coverage**: Skipped (Quick mode)

### Requirements Traceability

| Requirement | Test | Status |
|------------|------|--------|
| TRQ-001: All RateLimit → AllProvidersRateLimited | `test_all_rate_limited_raises_all_providers_rate_limited` | Pass |
| TRQ-002: No models → ServiceUnavailable | `test_no_models_raises_service_unavailable` | Pass |
| TRQ-003: All CB open → ServiceUnavailable | `test_all_cb_open_raises_service_unavailable` | Pass |
| TRQ-004: No API keys → ServiceUnavailable | `test_no_api_keys_raises_service_unavailable` | Pass |
| TRQ-005: Mixed errors → Exception | `test_mixed_errors_raises_exception` | Pass |
| TRQ-007: retry_after = min(values) | `test_rate_limited_retry_after_uses_min` | Pass |

## 8. Validation / Deploy

Skipped (Quick mode).

## 9. Artifacts

| Тип | Путь |
|-----|------|
| PRD | `_analysis/2026-02-25_F025_server-backpressure.md` |
| Research | `_research/2026-02-25_F025_server-backpressure.md` |
| Plan | `_plans/features/2026-02-25_F025_server-backpressure.md` |
| Completion | `_validation/2026-02-25_F025_server-backpressure.md` |

## 10. Files Changed

| Файл | Изменение |
|------|-----------|
| `app/domain/exceptions.py` | +AllProvidersRateLimited, +ServiceUnavailable |
| `app/application/use_cases/process_prompt.py` | Агрегация ошибок, типизированные raise |
| `app/api/v1/prompts.py` | HTTP 429/503 handlers, ErrorResponse |
| `app/api/v1/schemas.py` | +ErrorResponse schema |
| `app/main.py` | headers_enabled=True, custom rate_limit_handler |
| `tests/unit/test_process_prompt_use_case.py` | 2 updated + 6 new tests |
