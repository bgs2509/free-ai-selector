---
feature_id: "F025"
feature_name: "server-backpressure"
title: "Серверная защита от перегрузки: HTTP 429/503 + backpressure"
created: "2026-02-25"
author: "AI (Architect)"
type: "plan"
status: "APPROVED"
version: 1
mode: "FEATURE"
stages: 4
---

# План фичи: F025 — Server-side Backpressure (HTTP 429/503)

## 1. Контекст

Business API возвращает HTTP 500 на все ошибки — клиент не может отличить "провайдеры перегружены" от "сервер сломался". F025 добавляет дифференциацию: HTTP 429 (все rate-limited) + Retry-After, HTTP 503 (сервис недоступен) + Retry-After, стандартные заголовки X-RateLimit-*. Изменения затрагивают 5 файлов в Business API, не требуют новых зависимостей. Ключевая сложность — агрегация типов ошибок в fallback loop `process_prompt.py`.

---

## 2. Содержание

1. Этап 1: Новые доменные исключения
2. Этап 2: Агрегация ошибок в fallback loop
3. Этап 3: HTTP-ответы и заголовки
4. Этап 4: Тесты

---

## 3. Краткая версия плана

### Этап 1: Новые доменные исключения

1. **Проблема** — В `exceptions.py` нет исключений для агрегированных ситуаций "все провайдеры rate-limited" и "сервис недоступен".
2. **Действие** — Добавить `AllProvidersRateLimited` и `ServiceUnavailable` в `app/domain/exceptions.py`, оба наследуют от `ProviderError`.
3. **Результат** — Доменный слой может выражать два новых типа ошибок с полями `retry_after_seconds`, `attempts`, `providers_tried`.
4. **Зависимости** — Нет (первый этап).
5. **Риски** — Минимальные. Новые классы, не ломают существующий код.
6. **Без этого** — Невозможно различить причину ошибки в API-слое (Этап 3 заблокирован).

### Этап 2: Агрегация ошибок в fallback loop

1. **Проблема** — `process_prompt.py` не собирает типы ошибок в fallback loop — хранит только строку `last_error_message`, теряя информацию о типах.
2. **Действие** — Добавить списки `error_types` и `retry_after_values` в fallback loop, заменить `raise Exception(...)` на типизированные `AllProvidersRateLimited` / `ServiceUnavailable` после loop.
3. **Результат** — Use case бросает правильное исключение: все RateLimit → `AllProvidersRateLimited`, нет моделей/все CB open → `ServiceUnavailable`, смешанные → `Exception`.
4. **Зависимости** — Этап 1 (исключения должны существовать).
5. **Риски** — Средние. Изменение логики в ключевом use case. Edge case: CB skip + RateLimit — нужно аккуратно различать.
6. **Без этого** — API-слой получает только `Exception`, не может вернуть 429/503 (Этап 3 бесполезен).

### Этап 3: HTTP-ответы и заголовки

1. **Проблема** — `prompts.py` ловит все исключения как `except Exception` → HTTP 500. slowapi `headers_enabled=False`, rate limit не на `/process`.
2. **Действие** — Заменить catch-all на цепочку except (429/503/500) в `prompts.py`, включить `headers_enabled=True` в `main.py`, добавить `@limiter.limit` на `/process`, добавить `ErrorResponse` схему в `schemas.py`.
3. **Результат** — Клиенты получают правильные HTTP-коды + `Retry-After` + `X-RateLimit-*` + структурированный error body.
4. **Зависимости** — Этап 1 и 2 (исключения и агрегация должны работать).
5. **Риски** — Telegram Bot может получить неожиданный 429/503 вместо 500. По RFC это корректно — любой HTTP-клиент обрабатывает 4xx/5xx как ошибки.
6. **Без этого** — Вся фича не работает. Клиенты продолжают получать HTTP 500 на всё.

### Этап 4: Тесты

1. **Проблема** — 3 существующих теста ловят `Exception` вместо новых типов. Нет тестов для 429/503 ответов.
2. **Действие** — Обновить 3 существующих теста (`pytest.raises(ServiceUnavailable)`), добавить новые тесты для `AllProvidersRateLimited`, `ServiceUnavailable`, структурированного error body.
3. **Результат** — Покрытие ≥ 75%, все TRQ-001..TRQ-007 пройдены.
4. **Зависимости** — Этапы 1-3 (код должен быть написан).
5. **Риски** — Минимальные. Тесты изолированы.
6. **Без этого** — Нет гарантии корректности. Регрессия при будущих изменениях.

---

## 4. Полная версия плана

## Этап 1: Новые доменные исключения

**Файл**: `app/domain/exceptions.py`
**Требования**: FR-001, FR-002

### Новые классы

```python
class AllProvidersRateLimited(ProviderError):
    """F025: Все провайдеры вернули RateLimitError."""

    def __init__(
        self,
        message: str = "All providers are rate limited",
        retry_after_seconds: int = 60,
        attempts: int = 0,
        providers_tried: int = 0,
    ):
        super().__init__(message)
        self.retry_after_seconds = retry_after_seconds
        self.attempts = attempts
        self.providers_tried = providers_tried


class ServiceUnavailable(ProviderError):
    """F025: Сервис недоступен (нет моделей, нет ключей, все CB open)."""

    def __init__(
        self,
        message: str = "Service temporarily unavailable",
        retry_after_seconds: int = 30,
        reason: str = "unknown",
    ):
        super().__init__(message)
        self.retry_after_seconds = retry_after_seconds
        self.reason = reason
```

**Env-переменные** (в `process_prompt.py`):
```python
ALL_RATE_LIMITED_RETRY_AFTER = int(os.getenv("ALL_RATE_LIMITED_RETRY_AFTER", "60"))
SERVICE_UNAVAILABLE_RETRY_AFTER = int(os.getenv("SERVICE_UNAVAILABLE_RETRY_AFTER", "30"))
```

---

## Этап 2: Агрегация ошибок в fallback loop

**Файл**: `app/application/use_cases/process_prompt.py`
**Требования**: FR-001, FR-002, FR-010

### 2.1 Добавить переменные трекинга (после строки 204)

```python
last_error_message: Optional[str] = None
successful_model: Optional[AIModelInfo] = None
response_text: Optional[str] = None
attempts = 0
# F025: агрегация типов ошибок
error_types: list[type] = []
retry_after_values: list[int] = []
skipped_by_cb: int = 0
providers_tried: int = 0
```

### 2.2 Трекинг CB skip (строка ~207-214)

```python
if not CircuitBreakerManager.is_available(model.provider):
    logger.debug("circuit_open_skip", ...)
    skipped_by_cb += 1  # F025
    continue
```

### 2.3 Трекинг типов ошибок в except-блоках

В каждом `except` (RateLimitError, ServerError, TimeoutError, и т.д.) добавить:
```python
error_types.append(type(e))
providers_tried += 1
```

Для `RateLimitError` дополнительно:
```python
if hasattr(e, 'retry_after_seconds') and e.retry_after_seconds:
    retry_after_values.append(e.retry_after_seconds)
```

### 2.4 Заменить raise Exception после loop (строка ~300)

**Было:**
```python
raise Exception(f"All AI providers failed. Last error: {last_error_message}")
```

**Стало:**
```python
# F025: определить причину отказа
if attempts == 0:
    raise ServiceUnavailable(
        message="All providers unavailable (circuit breaker open)",
        retry_after_seconds=SERVICE_UNAVAILABLE_RETRY_AFTER,
        reason="all_circuit_breaker_open",
    )

if error_types and all(t == RateLimitError for t in error_types):
    retry_after = min(retry_after_values) if retry_after_values else ALL_RATE_LIMITED_RETRY_AFTER
    raise AllProvidersRateLimited(
        message=f"All {providers_tried} providers are rate limited",
        retry_after_seconds=retry_after,
        attempts=attempts,
        providers_tried=providers_tried,
    )

raise Exception(f"All AI providers failed. Last error: {last_error_message}")
```

### 2.5 Заменить "No active models" / "No configured models"

**Строка ~131:**
```python
# Было:
raise Exception("No active AI models available")
# Стало:
raise ServiceUnavailable(
    message="No active AI models available",
    retry_after_seconds=SERVICE_UNAVAILABLE_RETRY_AFTER,
    reason="no_active_models",
)
```

**Строка ~141:**
```python
# Было:
raise Exception("No configured AI models available (missing API keys)")
# Стало:
raise ServiceUnavailable(
    message="No configured AI models available (missing API keys)",
    retry_after_seconds=SERVICE_UNAVAILABLE_RETRY_AFTER,
    reason="no_api_keys",
)
```

---

## Этап 3: HTTP-ответы и заголовки

### 3.1 ErrorResponse схема

**Файл**: `app/api/v1/schemas.py`
**Требование**: FR-010

```python
class ErrorResponse(BaseModel):
    """F025: Структурированный ответ при ошибке."""
    error: str
    message: str
    retry_after: Optional[int] = None
    attempts: int = 0
    providers_tried: int = 0
    providers_available: int = 0
```

### 3.2 Exception handlers в prompts.py

**Файл**: `app/api/v1/prompts.py`
**Требования**: FR-001, FR-002, FR-010, FR-011

Заменить строки 81-88 (единый catch-all) на:

```python
except AllProvidersRateLimited as e:
    retry_after = e.retry_after_seconds
    logger.warning(
        "backpressure_applied",
        status=429,
        reason="all_rate_limited",
        retry_after=retry_after,
        attempts=e.attempts,
    )
    return JSONResponse(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        headers={"Retry-After": str(retry_after)},
        content=ErrorResponse(
            error="all_rate_limited",
            message="All AI providers are rate limited. Please retry later.",
            retry_after=retry_after,
            attempts=e.attempts,
            providers_tried=e.providers_tried,
            providers_available=len(candidate_models),
        ).model_dump(),
    )

except ServiceUnavailable as e:
    retry_after = e.retry_after_seconds
    logger.warning(
        "backpressure_applied",
        status=503,
        reason=e.reason,
        retry_after=retry_after,
    )
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        headers={"Retry-After": str(retry_after)},
        content=ErrorResponse(
            error="service_unavailable",
            message=str(e),
            retry_after=retry_after,
        ).model_dump(),
    )

except Exception as e:
    error_type = type(e).__name__
    logger.error(f"Failed to process prompt: {sanitize_error_message(e)}")
    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail=f"Failed to process prompt [{error_type}]: {sanitize_error_message(e)}",
    )
```

**Примечание**: `candidate_models` нужно сохранить в переменную до вызова `use_case.execute()` для использования в `providers_available`. Альтернатива: передать `providers_available` через исключение.

### 3.3 Rate limit на /process и OpenAPI responses

```python
@router.post(
    "/process",
    response_model=ProcessPromptResponse,
    responses={
        429: {"model": ErrorResponse, "description": "All providers rate limited"},
        503: {"model": ErrorResponse, "description": "Service unavailable"},
    },
)
@limiter.limit(PROCESS_RATE_LIMIT)
async def process_prompt(request: Request, body: ProcessPromptRequest):
    ...
```

Env-переменная (в `prompts.py` или `main.py`):
```python
PROCESS_RATE_LIMIT = os.getenv("PROCESS_RATE_LIMIT", "100/minute")
```

### 3.4 Включить headers_enabled в slowapi

**Файл**: `app/main.py`, строка 69

```python
# Было:
limiter = Limiter(key_func=get_remote_address)
# Стало:
limiter = Limiter(key_func=get_remote_address, headers_enabled=True)
```

### 3.5 Кастомный slowapi handler (согласованный формат)

**Файл**: `app/main.py`, строка 143

Заменить стандартный `_rate_limit_exceeded_handler` на кастомный, возвращающий `ErrorResponse`:

```python
async def rate_limit_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    """F025: Кастомный обработчик slowapi rate limit в формате ErrorResponse."""
    retry_after = exc.detail.split(" per ")[0] if exc.detail else "60"
    response = JSONResponse(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        content={
            "error": "client_rate_limited",
            "message": f"Rate limit exceeded: {exc.detail}",
            "retry_after": int(retry_after) if retry_after.isdigit() else 60,
            "attempts": 0,
            "providers_tried": 0,
            "providers_available": 0,
        },
    )
    response = request.app.state.limiter._inject_headers(
        response, request.state.view_rate_limit
    )
    return response

app.add_exception_handler(RateLimitExceeded, rate_limit_handler)
```

---

## Этап 4: Тесты

**Файл**: `tests/unit/test_process_prompt_use_case.py`
**Требования**: TRQ-001..TRQ-007

### 4.1 Обновить существующие тесты

```python
# Было:
with pytest.raises(Exception, match="No active AI models available"):
# Стало:
with pytest.raises(ServiceUnavailable, match="No active AI models available"):
```

Аналогично для `test_execute_no_configured_models`.

### 4.2 Новые тесты (добавить в класс или новый класс TestF025Backpressure)

```python
@pytest.mark.unit
class TestF025Backpressure:
    """F025: Server-side backpressure (HTTP 429/503)."""

    # TRQ-001: Все провайдеры RateLimited → AllProvidersRateLimited
    async def test_all_rate_limited_raises_all_providers_rate_limited(self, ...):
        mock_provider.generate.side_effect = RateLimitError("Rate limited", retry_after_seconds=30)
        with pytest.raises(AllProvidersRateLimited) as exc_info:
            await use_case.execute(request)
        assert exc_info.value.retry_after_seconds == 30
        assert exc_info.value.attempts == 2
        assert exc_info.value.providers_tried == 2

    # TRQ-002: Нет моделей → ServiceUnavailable
    async def test_no_models_raises_service_unavailable(self, ...):
        mock_data_api_client.get_all_models.return_value = []
        with pytest.raises(ServiceUnavailable) as exc_info:
            await use_case.execute(request)
        assert exc_info.value.reason == "no_active_models"

    # TRQ-003: Все CB open → ServiceUnavailable
    async def test_all_cb_open_raises_service_unavailable(self, ...):
        # record_failure для всех провайдеров > threshold
        with pytest.raises(ServiceUnavailable) as exc_info:
            await use_case.execute(request)
        assert exc_info.value.reason == "all_circuit_breaker_open"

    # TRQ-004: Нет API-ключей → ServiceUnavailable
    async def test_no_api_keys_raises_service_unavailable(self, ...):
        # пустой os.environ
        with pytest.raises(ServiceUnavailable) as exc_info:
            await use_case.execute(request)
        assert exc_info.value.reason == "no_api_keys"

    # TRQ-005: Смешанные ошибки → Exception (HTTP 500)
    async def test_mixed_errors_raises_exception(self, ...):
        # Provider1: RateLimitError, Provider2: ServerError
        with pytest.raises(Exception, match="All AI providers failed"):
            await use_case.execute(request)

    # TRQ-007: Структурированный error body
    async def test_error_body_contains_metrics(self, ...):
        mock_provider.generate.side_effect = RateLimitError("Rate limited", retry_after_seconds=45)
        with pytest.raises(AllProvidersRateLimited) as exc_info:
            await use_case.execute(request)
        assert exc_info.value.retry_after_seconds == 45
        assert exc_info.value.providers_tried > 0
```

### 4.3 conftest.py — без изменений

Существующие fixtures достаточны. `reset_circuit_breaker` (autouse) уже обеспечивает изоляцию.

---

## 5. Влияние на существующие тесты

| Тест | Изменение |
|------|-----------|
| `test_execute_no_active_models` | `Exception` → `ServiceUnavailable` |
| `test_execute_no_configured_models` | `Exception` → `ServiceUnavailable` |
| `test_all_providers_fail_raises_exception` | Добавить вариант с `AllProvidersRateLimited` |
| Все остальные (~70 тестов) | Без изменений |

---

## 6. Новые env-переменные

| Переменная | Default | Где используется | Описание |
|-----------|---------|-----------------|----------|
| `PROCESS_RATE_LIMIT` | `"100/minute"` | `prompts.py` | slowapi лимит на /process |
| `ALL_RATE_LIMITED_RETRY_AFTER` | `60` | `process_prompt.py` | Default Retry-After при 429 |
| `SERVICE_UNAVAILABLE_RETRY_AFTER` | `30` | `process_prompt.py` | Default Retry-After при 503 |
| `ENABLE_DEBUG_RESPONSE` | `false` | `prompts.py` | Включение debug-режима (FR-021) |

---

## 7. Breaking changes

- HTTP 429/503 вместо 500 для определённых ситуаций. По RFC это корректно — 4xx/5xx обрабатываются как ошибки любым HTTP-клиентом.
- Telegram Bot и Web UI продолжат работать — они уже обрабатывают HTTP-ошибки generic-способом.
- Миграции БД: **не требуются**.

---

## 8. Риски и митигация

| # | Риск | Вероятность | Митигация |
|---|------|-------------|-----------|
| 1 | Telegram Bot получит 429 вместо 500 | Med | Bot показывает generic ошибку для всех non-200. Работает. |
| 2 | `providers_available` недоступен в except-блоке prompts.py | Med | Передать через исключение или вычислить до вызова execute() |
| 3 | Edge case: 1 RateLimit + 1 ServerError = смешанные → 500 | Low | По дизайну. Только если ВСЕ == RateLimit → 429. |

---

## 9. Порядок реализации

```
Этап 1 → Этап 2 → Этап 3 → Этап 4
  │          │          │          │
  ▼          ▼          ▼          ▼
exceptions  process    prompts    tests
  .py       _prompt     .py
             .py      schemas.py
                      main.py
```

Строго последовательно: каждый этап зависит от предыдущего.
