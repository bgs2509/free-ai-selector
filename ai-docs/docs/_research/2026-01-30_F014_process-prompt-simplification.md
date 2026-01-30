---
feature_id: "F014"
feature_name: "process-prompt-simplification"
title: "ProcessPromptUseCase: Error Handling Consolidation Research"
created: "2026-01-30"
author: "AI (Researcher)"
type: "research"
status: "RESEARCH_DONE"
version: 1
mode: "FEATURE"
related_features: [F012, F013]
services: [free-ai-selector-business-api]
---

# Research Report: F014 ProcessPromptUseCase Simplification

**Feature ID**: F014
**Версия**: 1.0
**Дата**: 2026-01-30
**Автор**: AI Agent (Исследователь)
**Статус**: RESEARCH_DONE

---

## 1. Анализ существующего кода

### 1.1 Целевой файл

| Параметр | Значение |
|----------|----------|
| Файл | `services/free-ai-selector-business-api/app/application/use_cases/process_prompt.py` |
| Строк | 464 |
| Метод `execute()` | строки 77-370 (~294 строки) |
| Error handling | строки 177-301 (~125 строк) |

### 1.2 Структура except блоков

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

### 1.3 Выявленное дублирование

| Блок except | Строки | Действия | Уникальность |
|-------------|--------|----------|--------------|
| `RateLimitError` | 177-195 (19 строк) | set_availability + log | **Уникальная логика A** |
| `(ServerError, TimeoutError)` | 197-218 (22 строки) | increment_failure + log | Логика B |
| `(AuthenticationError, ValidationError)` | 220-240 (21 строка) | increment_failure + log | **Дубль логики B** |
| `ProviderError` | 242-262 (21 строка) | increment_failure + log | **Дубль логики B** |
| `Exception` | 264-301 (38 строк) | classify → A или B | Dispatches to A/B |

**Итого дублирования**: ~64 строки (3 блока × ~21 строка)

### 1.4 Цикломатическая сложность

Примерная оценка `execute()`:

| Элемент | Добавляет к CC |
|---------|----------------|
| 1 for loop | +1 |
| 5 except блоков | +5 |
| 1 if в except Exception | +1 |
| 1 if (successful_model is None) | +1 |
| try/except в каждом блоке (×6) | +6 |
| if not models | +1 |
| if not configured_models | +1 |
| **Итого** | ~**17-20** |

Рекомендуемое значение: < 10. Текущее: **~17-20**.

---

## 2. Зависимости и связи

### 2.1 Импорты

```python
# Из domain/exceptions.py (F012)
from app.domain.exceptions import (
    AuthenticationError,
    ProviderError,
    RateLimitError,
    ServerError,
    TimeoutError,
    ValidationError,
)

# Из services/ (F012)
from app.application.services.error_classifier import classify_error
from app.application.services.retry_service import retry_with_fixed_delay

# Утилиты
from app.utils.security import sanitize_error_message
from app.utils.log_helpers import log_decision
```

### 2.2 Иерархия исключений (exceptions.py)

```
ProviderError (base)
├── RateLimitError     # 429 — НЕ failure
├── ServerError        # 5xx — failure, retryable
├── TimeoutError       # timeout — failure, retryable
├── AuthenticationError # 401/403 — failure, non-retryable
└── ValidationError    # 400/422 — failure, non-retryable
```

### 2.3 Существующие сервисы (можно использовать)

| Сервис | Назначение | Статус |
|--------|------------|--------|
| `error_classifier.py` | classify_error() + is_retryable() | ✅ Используется |
| `retry_service.py` | retry_with_fixed_delay() | ✅ Используется |
| `sanitize_error_message()` | Очистка sensitive data из ошибок | ✅ Используется |
| `log_decision()` | Структурированное логирование решений | ✅ Используется |

---

## 3. Quality Cascade Checklist (7/7)

### QC-1: DRY ✅

**Найдено дублирование:**
- 3 блока с идентичной "Логикой B" (increment_failure + log + continue)
- Каждый блок ~21 строка
- Общее дублирование: ~64 строки

**Код для переиспользования:**
- `sanitize_error_message()` — уже используется
- `log_decision()` — уже используется
- `error_classifier.classify_error()` — уже используется
- `retry_service.retry_with_fixed_delay()` — уже используется

→ **Рекомендация**: Вынести "Логику B" в приватный метод `_handle_transient_error()`

---

### QC-2: KISS ✅

**Анализ сложности PRD:**

| Компонент PRD | Оценка | Комментарий |
|---------------|--------|-------------|
| `_handle_rate_limit()` | Простой | Необходим — уникальная логика |
| `_handle_transient_error()` | Простой | Консолидация 3 блоков |
| Объединение except | Простой | Один except вместо трёх |

**Цикломатическая сложность после рефакторинга:**
- Текущая: ~17-20
- Целевая: ~12-15

→ **Рекомендация**: PRD предлагает минимальный scope, дополнительного упрощения не требуется

---

### QC-3: YAGNI ✅

**Проверка scope:**

| Компонент | Нужен сейчас? | Решение |
|-----------|---------------|---------|
| `_handle_rate_limit()` | ✅ Да | Включить |
| `_handle_transient_error()` | ✅ Да | Включить |
| Новые типы ошибок | ❌ Нет | НЕ добавлять |
| Изменение retry логики | ❌ Нет | НЕ изменять |
| Новые параметры | ❌ Нет | НЕ добавлять |

→ **Рекомендация**: Scope ограничен консолидацией существующего кода, никаких "на будущее"

---

### QC-4: SoC (Separation of Concerns) ✅

**Текущее разделение ответственностей:**

| Модуль | Ответственность | Статус |
|--------|-----------------|--------|
| `process_prompt.py` | Оркестрация prompt processing | ⚠️ Смешан с error handling |
| `error_classifier.py` | Классификация ошибок | ✅ Чистый |
| `retry_service.py` | Механизм retry | ✅ Чистый |
| `exceptions.py` | Определение типов ошибок | ✅ Чистый |

**После рефакторинга:**
- `execute()` — оркестрация (main flow)
- `_handle_rate_limit()` — логика rate limit (SRP)
- `_handle_transient_error()` — логика transient errors (SRP)

→ **Рекомендация**: Приватные методы улучшают SRP в пределах одного класса

---

### QC-5: SSoT (Single Source of Truth) ✅

| Тип данных | Файл-источник | Статус |
|------------|---------------|--------|
| Exception types | `domain/exceptions.py` | ✅ SSoT |
| Error classification | `error_classifier.py` | ✅ SSoT |
| Retry configuration | `retry_service.py` (env vars) | ✅ SSoT |
| Cooldown default | `process_prompt.py:RATE_LIMIT_DEFAULT_COOLDOWN` | ✅ SSoT |

→ **Рекомендация**: НЕ дублировать конфигурацию, использовать существующие источники

---

### QC-6: CoC (Convention over Configuration) ✅

**Выявленные конвенции проекта:**

| Паттерн | Пример | Следовать |
|---------|--------|-----------|
| Приватные методы | `_filter_configured_models()`, `_generate_with_retry()` | ✅ Да |
| Async/await | Все I/O операции | ✅ Да |
| Type hints | Полные для всех методов | ✅ Да |
| Docstrings | Google-style | ✅ Да |
| Logging | structlog + log_decision() | ✅ Да |
| Error sanitization | sanitize_error_message() | ✅ Да |

→ **Рекомендация**: Новые методы должны следовать существующим конвенциям

---

### QC-7: Security ✅

**Существующие практики безопасности:**

| Практика | Реализация | Статус |
|----------|------------|--------|
| Error message sanitization | `sanitize_error_message()` | ✅ Используется |
| No secrets in logs | SensitiveDataFilter (F009) | ✅ Активен |
| API key validation | `_filter_configured_models()` | ✅ Работает |

**Security-риски F014:**
- ❌ Нет новых рисков — рефакторинг не меняет security логику
- ✅ Продолжать использовать `sanitize_error_message()` в новых методах

→ **Рекомендация**: Сохранить использование `sanitize_error_message()` во всех новых методах

---

## 4. Точки интеграции

### 4.1 Файлы для изменения

| Файл | Действие | Описание |
|------|----------|----------|
| `process_prompt.py` | Modify | Добавить 2 приватных метода, рефакторинг execute() |

### 4.2 Файлы НЕ изменяемые

| Файл | Причина |
|------|---------|
| `error_classifier.py` | Не требует изменений |
| `retry_service.py` | Не требует изменений |
| `exceptions.py` | Не требует изменений |
| `data_api_client.py` | Не требует изменений |

### 4.3 Тесты

| Файл | Действие | Описание |
|------|----------|----------|
| `test_process_prompt_use_case.py` | Modify | Добавить тесты для приватных методов |

**Существующее покрытие:**
- `test_execute_success` — ✅ проверяет happy path
- `test_execute_no_active_models` — ✅ проверяет edge case
- `test_execute_no_configured_models` — ✅ проверяет F012 FR-8
- `TestF011BSystemPromptsAndResponseFormat` — ✅ проверяет F011-B

**Нужно добавить:**
- `test_handle_rate_limit_calls_set_availability`
- `test_handle_transient_error_calls_increment_failure`

---

## 5. Рекомендации по реализации

### 5.1 Предлагаемая структура кода

```python
class ProcessPromptUseCase:

    async def execute(self, request: PromptRequest) -> PromptResponse:
        # ... основной код ...

        for model in sorted_models:
            try:
                response_text = await self._generate_with_retry(...)
                successful_model = model
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

        # ... остальной код ...

    async def _handle_rate_limit(
        self,
        model: AIModelInfo,
        error: RateLimitError
    ) -> None:
        """Handle rate limit error: set availability cooldown."""
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

    async def _handle_transient_error(
        self,
        model: AIModelInfo,
        error: Exception,
        start_time: float,
    ) -> None:
        """Handle transient error: log and record failure."""
        response_time = Decimal(str(time.time() - start_time))
        logger.error(
            "generation_failed",
            model=model.name,
            provider=model.provider,
            error_type=type(error).__name__,
            error=sanitize_error_message(error),
        )
        try:
            await self.data_api_client.increment_failure(
                model_id=model.id,
                response_time=float(response_time)
            )
        except Exception as stats_error:
            logger.error(
                "stats_update_failed",
                model=model.name,
                error=sanitize_error_message(stats_error),
            )
```

### 5.2 Метрики до/после

| Метрика | До | После |
|---------|-----|-------|
| Строк в execute() | ~294 | ~200 |
| Error handling строк | ~125 | ~50 |
| Цикломатическая сложность | ~17-20 | ~12-15 |
| Количество except блоков | 5 | 3 |
| Дублирование | ~64 строки | 0 строк |

---

## 6. Риски

| # | Риск | Вероятность | Влияние | Митигация |
|---|------|-------------|---------|-----------|
| 1 | Изменение поведения | Low | High | 100% покрытие тестами, regression tests |
| 2 | Log messages изменятся | Low | Low | Сохранить ключевые event names |
| 3 | Конфликт с F012 изменениями | Med | Med | Выполнять после F012 полного merge |

---

## 7. Зависимости с другими фичами

| Фича | Статус | Связь |
|------|--------|-------|
| F012 (Rate Limit Handling) | IMPLEMENT | Добавил error handling код, который рефакторим |
| F013 (Providers Consolidation) | VALIDATED | Не влияет на F014 |
| F011-B (System Prompts) | REVIEW | Не влияет на F014 |

→ **Рекомендация**: Выполнять F014 после merge F012, чтобы не решать конфликты

---

## 8. Качественные ворота RESEARCH_DONE

### Checklist

- [x] 🔴 Существующий код проанализирован
- [x] 🔴 Зависимости определены
- [x] 🔴 Research отчёт создан в `_research/`
- [x] 🟡 Риски идентифицированы
- [x] 🟡 Технические ограничения описаны
- [x] ✅ Quality Cascade Checklist (7/7) включён

---

## 9. Следующий шаг

```bash
/aidd-plan-feature  # Создать план реализации
```

---

**Версия документа**: 1.0
**Обновлён**: 2026-01-30
