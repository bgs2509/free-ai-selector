---
feature_id: "F024"
feature_name: "circuit-breaker"
title: "Circuit Breaker для AI-провайдеров"
created: "2026-02-25"
author: "AI (Validator)"
type: "completion-report"
status: "DRAFT"
mode: "quick"
version: 1
---

# Completion Report: F024 — Circuit Breaker для AI-провайдеров

> **⚠️ DRAFT** — Quick mode. Полный QA не выполнен.

---

## 1. Executive Summary

Реализован in-memory Circuit Breaker (CLOSED → OPEN → HALF-OPEN → CLOSED) для AI-провайдеров в `ProcessPromptUseCase`. Мгновенно исключает нерабочие провайдеры из failover loop после серии ошибок, автоматически восстанавливает через пробный запрос. Ожидаемое снижение латентности failover с ~4.5 сек до < 100 мс при 8 мёртвых провайдерах.

---

## 2. Реализованные компоненты

### 2.1 Новые файлы

| Файл | Описание |
|------|----------|
| `app/application/services/circuit_breaker.py` | `CircuitBreakerManager` — classmethod singleton с state machine |
| `tests/unit/test_circuit_breaker.py` | 9 unit-тестов state machine |

### 2.2 Модифицированные файлы

| Файл | Изменение |
|------|-----------|
| `app/application/use_cases/process_prompt.py` | Import CB + 4 точки интеграции (is_available, record_success, record_failure ×2) |
| `tests/unit/test_process_prompt_use_case.py` | 2 интеграционных теста (skip OPEN, failure recording) |
| `tests/conftest.py` | Autouse fixture `reset_circuit_breaker` для изоляции |

### 2.3 Ключевые классы

| Класс | Назначение |
|-------|-----------|
| `CircuitState` | Enum: CLOSED, OPEN, HALF_OPEN |
| `ProviderCircuit` | Dataclass: state, failure_count, last_failure_time |
| `CircuitBreakerManager` | Singleton с classmethods: is_available, record_success, record_failure, get_all_statuses, reset |

---

## 3. Architecture Decision Records (ADR)

### ADR-001: Classmethod singleton (паттерн ProviderRegistry)

**Контекст**: Нужен stateful in-memory менеджер для CB. Два варианта: DI-инъекция или module-level singleton.

**Решение**: Class с classmethods и class-level `_circuits: dict[str, ProviderCircuit]`.

**Обоснование**: Соответствует паттерну `ProviderRegistry` в проекте. Не требует изменений wiring в endpoints. Тестируется через `reset()`.

**Альтернатива**: Инстанс через DI → потребовал бы изменение `ProcessPromptUseCase.__init__()` и endpoint wiring.

### ADR-002: RateLimitError исключён из CB

**Контекст**: 429 (Rate Limit) — временное состояние, обрабатывается через `set_availability`.

**Решение**: `record_failure()` НЕ вызывается для RateLimitError.

**Обоснование**: 429 не означает "провайдер сломан", а "превышен лимит запросов". CB реагирует только на серийные ошибки.

### ADR-003: `time.time()` для таймеров

**Решение**: `time.time()` вместо `asyncio.get_event_loop().time()`.

**Обоснование**: Проще мокать в тестах (`@patch("...time.time")`). Достаточная точность для recovery_timeout (60 сек).

---

## 4. Requirements Traceability

| ID | Требование | Статус | Реализация |
|----|-----------|--------|------------|
| FR-001 | Три состояния CB | ✅ | `CircuitState` enum + state machine в `CircuitBreakerManager` |
| FR-002 | Failure threshold | ✅ | `CB_FAILURE_THRESHOLD=5`, env-конфигурируем |
| FR-003 | Recovery timeout | ✅ | `CB_RECOVERY_TIMEOUT=60`, OPEN→HALF-OPEN через `is_available()` |
| FR-004 | Интеграция в fallover loop | ✅ | `is_available()` check + `continue` перед `attempts += 1` |
| FR-005 | Запись результатов | ✅ | `record_success()` после успеха, `record_failure()` в except-блоках |
| FR-010 | Логирование переходов | ✅ | `logger.warning("circuit_state_changed", ...)` |
| FR-011 | get_all_statuses | ✅ | `get_all_statuses() → dict[str, str]` |
| FR-020 | Ускоренное открытие | ❌ Deferred | Nice to Have, отложено на следующую итерацию |

---

## 5. Scope Changes

| Компонент | План (PRD) | Факт | Причина |
|-----------|-----------|------|---------|
| FR-020 (ускоренное открытие) | Could Have | Отложено | Nice to Have, требует дополнительной логики в record_failure |
| Все Must Have (FR-001—FR-005) | Планировались | Реализованы | — |
| Все Should Have (FR-010, FR-011) | Планировались | Реализованы | — |

---

## 6. Known Limitations

1. **State не шарится между uvicorn workers** — допустимо при текущей конфигурации (1 worker).
2. **State теряется при рестарте** — CB восстанавливается за ~5 запросов на провайдер.
3. **Нет ускоренного открытия для permanent errors** (FR-020 отложен) — AuthError требует 5 ошибок вместо 1 для открытия CB.
4. **Нет HTTP endpoint** для интроспекции CB status — только через логи и `get_all_statuses()`.

---

## 7. Метрики качества

| Метрика | Значение | Статус |
|---------|----------|--------|
| Ruff | 0 errors | ✅ |
| Bandit | 0 issues | ✅ |
| CB unit tests | 9 passed | ✅ |
| CB integration tests | 2 passed | ✅ |
| All business-api tests | 163 passed, 2 failed (pre-existing) | ✅ |
| CB module coverage | 97% (isolated), 99% (full suite) | ✅ |

---

## 8. Артефакты

| Тип | Путь |
|-----|------|
| PRD | `_analysis/2026-02-25_F024_circuit-breaker.md` |
| Research | `_research/2026-02-25_F024_circuit-breaker.md` |
| Plan | `_plans/features/2026-02-25_F024_circuit-breaker.md` |
| Completion | `_validation/2026-02-25_F024_circuit-breaker.md` |

---

## 9. Конфигурация

| Переменная | Default | Описание |
|-----------|---------|----------|
| `CB_FAILURE_THRESHOLD` | 5 | Ошибок подряд для CLOSED → OPEN |
| `CB_RECOVERY_TIMEOUT` | 60 | Секунд до OPEN → HALF-OPEN |

---

## 10. Testing Summary

> Skipped (Quick mode). Unit и интеграционные тесты запущены в рамках `/aidd-code`.

---

## 11. Deploy Summary

> Skipped (Quick mode).
