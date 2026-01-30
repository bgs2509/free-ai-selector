---
feature_id: "F014"
feature_name: "process-prompt-simplification"
title: "ProcessPromptUseCase: Error Handling Consolidation"
created: "2026-01-30"
author: "AI (Architect)"
type: "implementation-plan"
status: "PENDING_APPROVAL"
version: 1
mode: "FEATURE"

related_features: [F012, F013]
services: [free-ai-selector-business-api]
---

# План реализации: F014 ProcessPromptUseCase Simplification

**Feature ID**: F014
**Версия**: 1.0
**Дата**: 2026-01-30
**Автор**: AI Agent (Архитектор)
**Статус**: PENDING_APPROVAL

---

## 1. Обзор

### 1.1 Цель рефакторинга

Консолидация 5 except блоков в методе `execute()` класса `ProcessPromptUseCase`
в 2 приватных метода для снижения дублирования и цикломатической сложности.

### 1.2 Связь с существующим функционалом

- **F012** (Rate Limit Handling): Добавил error handling код, который рефакторим
- **F013** (Providers Consolidation): Уже смержен, не влияет на F014

### 1.3 Метрики до/после

| Метрика | До | После |
|---------|-----|-------|
| Строк в execute() | ~294 | ~200 |
| Error handling строк | ~125 | ~50 |
| Цикломатическая сложность | ~17-20 | ~12-15 |
| Количество except блоков | 5 | 3 |
| Дублирование | ~64 строки | 0 строк |

---

## 2. Анализ существующего кода

### 2.1 Целевой файл

| Параметр | Значение |
|----------|----------|
| Файл | `services/free-ai-selector-business-api/app/application/use_cases/process_prompt.py` |
| Строк | 464 |
| Метод `execute()` | строки 77-370 (~294 строки) |
| Error handling | строки 177-301 (~125 строк) |

### 2.2 Текущая структура except блоков

```
execute() {
  for model in sorted_models:
    try:
      result = await _generate_with_retry(...)

    except RateLimitError (строки 177-195):       # Логика A
      → set_availability()
      → НЕ считается failure
      → continue

    except (ServerError, TimeoutError) (197-218): # Логика B
      → increment_failure()
      → log "generation_failed_after_retry"
      → continue

    except (AuthenticationError, ValidationError) (220-240): # Логика B (ДУБЛЬ!)
      → increment_failure()
      → log "generation_failed_non_retryable"
      → continue

    except ProviderError (242-262):              # Логика B (ДУБЛЬ!)
      → increment_failure()
      → log "generation_failed_generic"
      → continue

    except Exception (264-301):                  # Логика A или B
      → classify_error()
      → if RateLimitError: Логика A
      → else: Логика B
}
```

### 2.3 Идентифицированное дублирование

| Блок except | Строки | Уникальность |
|-------------|--------|--------------|
| `RateLimitError` | 177-195 (19) | **Уникальная логика A** |
| `(ServerError, TimeoutError)` | 197-218 (22) | Логика B |
| `(AuthenticationError, ValidationError)` | 220-240 (21) | **Дубль логики B** |
| `ProviderError` | 242-262 (21) | **Дубль логики B** |
| `Exception` | 264-301 (38) | Dispatches to A/B |

**Итого дублирования**: ~64 строки (3 блока × ~21 строка)

---

## 3. План изменений

### 3.1 Новые компоненты

| Компонент | Расположение | Описание |
|-----------|--------------|----------|
| `_handle_rate_limit()` | `process_prompt.py` | Приватный метод для Логики A |
| `_handle_transient_error()` | `process_prompt.py` | Приватный метод для Логики B |

### 3.2 Модификации существующего кода

| Файл | Изменение | Строки | Причина |
|------|-----------|--------|---------|
| `process_prompt.py` | Добавить `_handle_rate_limit()` | +25 | Логика A: set_availability |
| `process_prompt.py` | Добавить `_handle_transient_error()` | +30 | Логика B: increment_failure |
| `process_prompt.py` | Рефакторинг except блоков в execute() | -75 | Замена дублирования на вызовы методов |

### 3.3 Итоговое изменение LOC

| Тип | Строк |
|-----|-------|
| Добавлено | +55 |
| Удалено | -75 |
| **Итого** | **-20** |

---

## 4. Детальный дизайн

### 4.1 Метод `_handle_rate_limit()`

```python
async def _handle_rate_limit(
    self,
    model: AIModelInfo,
    error: RateLimitError,
) -> None:
    """
    Handle rate limit error: set availability cooldown (F012: FR-5).

    Rate limit errors are NOT counted as failures to preserve
    reliability_score for graceful degradation.

    Args:
        model: Model info for logging and API calls
        error: RateLimitError with optional retry_after_seconds
    """
    retry_after = error.retry_after_seconds or RATE_LIMIT_DEFAULT_COOLDOWN
    logger.warning(
        "rate_limit_detected",
        model=model.name,
        provider=model.provider,
        retry_after_seconds=retry_after,
    )
    try:
        await self.data_api_client.set_availability(model.id, retry_after)
    except Exception as avail_error:
        logger.error(
            "set_availability_failed",
            model=model.name,
            error=sanitize_error_message(avail_error),
        )
```

### 4.2 Метод `_handle_transient_error()`

```python
async def _handle_transient_error(
    self,
    model: AIModelInfo,
    error: Exception,
    start_time: float,
    log_event: str = "generation_failed",
) -> None:
    """
    Handle transient error: log and record failure (F012: FR-3, FR-4).

    Transient errors (server, timeout, auth, validation, generic provider)
    are counted as failures for reliability_score calculation.

    Args:
        model: Model info for logging and API calls
        error: Exception that caused the failure
        start_time: Request start time for response_time calculation
        log_event: Event name for structured logging
    """
    response_time = Decimal(str(time.time() - start_time))
    logger.error(
        log_event,
        model=model.name,
        provider=model.provider,
        error_type=type(error).__name__,
        error=sanitize_error_message(error),
    )
    try:
        await self.data_api_client.increment_failure(
            model_id=model.id,
            response_time=float(response_time),
        )
    except Exception as stats_error:
        logger.error(
            "stats_update_failed",
            model=model.name,
            error=sanitize_error_message(stats_error),
        )
```

### 4.3 Рефакторинг except блоков в execute()

**После рефакторинга:**

```python
for model in sorted_models:
    try:
        provider = self._get_provider_for_model(model)
        response_text = await self._generate_with_retry(
            provider=provider,
            request=request,
            model=model,
        )
        successful_model = model
        logger.info(
            "generation_success",
            model=model.name,
            provider=model.provider,
        )
        break

    except RateLimitError as e:
        await self._handle_rate_limit(model, e)
        last_error_message = sanitize_error_message(e)

    except (ServerError, TimeoutError, AuthenticationError,
            ValidationError, ProviderError) as e:
        await self._handle_transient_error(model, e, start_time)
        last_error_message = sanitize_error_message(e)

    except Exception as e:
        classified = classify_error(e)
        if isinstance(classified, RateLimitError):
            await self._handle_rate_limit(model, classified)
        else:
            await self._handle_transient_error(model, classified, start_time)
        last_error_message = sanitize_error_message(e)
```

---

## 5. API контракты

Нет изменений — рефакторинг внутренней реализации.

---

## 6. Влияние на существующие тесты

### 6.1 Существующие тесты (не требуют изменений)

| Тест | Файл | Статус |
|------|------|--------|
| `test_execute_success` | test_process_prompt_use_case.py | ✅ Сохраняется |
| `test_execute_no_active_models` | test_process_prompt_use_case.py | ✅ Сохраняется |
| `test_execute_no_configured_models` | test_process_prompt_use_case.py | ✅ Сохраняется |
| `TestF011BSystemPromptsAndResponseFormat` | test_process_prompt_use_case.py | ✅ Сохраняется |
| F012 rate limit tests | test_f012_rate_limit_handling.py | ✅ Сохраняются |

### 6.2 Новые тесты

| Тест | Описание | Приоритет |
|------|----------|-----------|
| `test_handle_rate_limit_calls_set_availability` | Проверка вызова set_availability | Must |
| `test_handle_rate_limit_logs_warning` | Проверка логирования | Should |
| `test_handle_transient_error_calls_increment_failure` | Проверка вызова increment_failure | Must |
| `test_handle_transient_error_logs_error` | Проверка логирования | Should |

---

## 7. План интеграции

| # | Шаг | Описание | Зависимости |
|---|-----|----------|-------------|
| 1 | Добавить `_handle_rate_limit()` | Создать приватный метод | — |
| 2 | Добавить `_handle_transient_error()` | Создать приватный метод | — |
| 3 | Рефакторинг except блоков | Заменить дублирование на вызовы | Шаги 1, 2 |
| 4 | Запустить существующие тесты | Проверить regression | Шаг 3 |
| 5 | Добавить unit тесты для новых методов | Покрытие новых методов | Шаг 3 |
| 6 | Lint + type check | mypy, ruff | Шаг 5 |

---

## 8. Риски и митигация

| # | Риск | Вероятность | Влияние | Митигация |
|---|------|-------------|---------|-----------|
| 1 | Изменение поведения | Low | High | 100% покрытие тестами, regression tests |
| 2 | Log messages изменятся | Low | Low | Сохранить ключевые event names |
| 3 | Конфликт с F012 | — | — | F012 уже смержен |

---

## 9. Breaking Changes

**Нет breaking changes:**

- [ ] API контракты не изменяются
- [ ] Публичные методы не изменяются
- [ ] Сигнатуры методов не изменяются
- [ ] Логика обработки ошибок сохраняется

---

## 10. Чеклист Quality Cascade

| # | Проверка | Статус |
|---|----------|--------|
| QC-1 | DRY: Устранено ~64 строки дублирования | ✅ |
| QC-2 | KISS: Цикломатическая сложность снижена | ✅ |
| QC-3 | YAGNI: Только необходимые изменения | ✅ |
| QC-4 | SoC: Логика A и B разделены в методы | ✅ |
| QC-5 | SSoT: Используются существующие источники | ✅ |
| QC-6 | CoC: Следуем конвенциям проекта | ✅ |
| QC-7 | Security: sanitize_error_message() сохранён | ✅ |

---

## 11. Ожидаемый результат

### До рефакторинга

```
execute(): ~294 строк
5 отдельных except блоков с ~125 строк error handling
Цикломатическая сложность: ~17-20
```

### После рефакторинга

```
execute(): ~200 строк
3 except блока + 2 приватных метода
Цикломатическая сложность: ~12-15
Дублирование: 0
```

---

## Качественные ворота PLAN_APPROVED

### Checklist

- [x] 🔴 Plan создан в `_plans/features/`
- [x] 🔴 Интеграция с существующим кодом описана
- [ ] 🔴 **Пользователь утвердил план**
- [ ] 🔴 `.pipeline-state.json` обновлён после утверждения
- [x] 🟡 Breaking changes определены (нет)
- [x] 🟡 Миграции БД описаны (не применимо)

---

## Следующий шаг

После утверждения плана пользователем:

```bash
/aidd-code  # Реализация
```

---

**Версия документа**: 1.0
**Обновлён**: 2026-01-30
