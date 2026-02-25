---
feature_id: "F025"
feature_name: "server-backpressure"
title: "Серверная защита от перегрузки: HTTP 429/503 + backpressure"
created: "2026-02-25"
author: "AI (Researcher)"
type: "research"
status: "RESEARCH_DONE"
version: 2
mode: "FEATURE"
---

# Research Report: F025 — Server-side Backpressure (HTTP 429/503)

**Feature ID**: F025
**Дата**: 2026-02-25
**Режим**: FEATURE
**Версия PRD**: 2.0 (серверная защита, не клиентский AC)

---

## 1. Краткое резюме

F025 добавляет дифференциацию HTTP-ответов при ошибках: 429 (все провайдеры rate-limited), 503 (сервис недоступен), 500 (реальный баг). Включает стандартные заголовки `Retry-After` и `X-RateLimit-*`.

**Главные находки исследования:**
1. Все ошибки сейчас → HTTP 500 (единый catch-all в `prompts.py:81-88`)
2. Типы ошибок **не агрегируются** в fallback loop — `last_error_message` хранит только строку последней ошибки
3. slowapi rate limit применён только к `/api`, НЕ к `/api/v1/prompts/process`
4. `headers_enabled=False` — заголовки `X-RateLimit-*` и `Retry-After` отключены
5. Endpoint `POST /process` **не тестируется** через HTTP (только use_case.execute() через моки)

---

## 2. Карта изменений по файлам

### 2.1 `app/domain/exceptions.py` (107 строк)

**Текущая иерархия:**
```
ProviderError (base)
  +-- RateLimitError     (retry_after_seconds)
  +-- ServerError
  +-- TimeoutError
  +-- AuthenticationError
  +-- ValidationError
```

**Что добавить:**
```
  +-- AllProvidersRateLimited  (retry_after_seconds, attempts, providers_tried)
  +-- ServiceUnavailable       (retry_after_seconds, reason)
```

Оба наследуют от `ProviderError`. `RateLimitError.retry_after_seconds` — существующий паттерн для переиспользования.

### 2.2 `app/application/use_cases/process_prompt.py` (569 строк)

**Проблема**: типы ошибок НЕ собираются в fallback loop.

Строки 200-204 — текущие переменные:
```python
last_error_message: Optional[str] = None
successful_model: Optional[AIModelInfo] = None
response_text: Optional[str] = None
attempts = 0
```
Нет `error_types: list[type]`, нет `retry_after_values: list[int]`.

**Что менять:**
1. Добавить `error_types: list[type] = []` и `retry_after_values: list[int] = []`
2. В каждом `except` добавить `error_types.append(type(e))`
3. Добавить `skipped_by_cb: int = 0` для трекинга CB-пропусков
4. После loop определять причину:
   - `attempts == 0` (все CB open) или нет моделей → `raise ServiceUnavailable(...)`
   - Все `error_types == RateLimitError` → `raise AllProvidersRateLimited(retry_after=min(...))`
   - Смешанные ошибки → `raise Exception(...)` (как сейчас → HTTP 500)
5. Заменить `raise Exception("No active AI models available")` → `raise ServiceUnavailable("No active AI models available")`
6. Заменить `raise Exception("No configured AI models available...")` → `raise ServiceUnavailable("No configured AI models available")`

**Важный edge case**: провайдер пропущен по CB (строка 207-214) — `attempts` не увеличивается, но `skipped_by_cb++`. Если ВСЕ пропущены по CB → `attempts == 0`, `skipped_by_cb > 0` → `ServiceUnavailable`.

### 2.3 `app/api/v1/prompts.py` (93 строки)

**Текущий catch-all** (строки 81-88):
```python
except Exception as e:
    raise HTTPException(status_code=500, detail=f"Failed to process prompt [{error_type}]: ...")
```

**Что менять** — заменить на цепочку:
```python
except AllProvidersRateLimited as e:
    → HTTP 429 + Retry-After + структурированный body (FR-001, FR-010)
except ServiceUnavailable as e:
    → HTTP 503 + Retry-After + структурированный body (FR-002, FR-010)
except Exception as e:
    → HTTP 500 (как сейчас, только реальные баги)
```

Добавить `@limiter.limit(...)` декоратор (FR-004).

### 2.4 `app/api/v1/schemas.py` (91 строка)

**Что добавить** — `ErrorResponse` Pydantic-схема для FR-010:
```python
class ErrorResponse(BaseModel):
    error: str                    # "all_rate_limited", "service_unavailable"
    message: str                  # Human-readable
    retry_after: Optional[int]    # Секунды до повтора
    attempts: int                 # Сколько моделей попробовали
    providers_tried: int          # Сколько провайдеров опросили
    providers_available: int      # Сколько доступно всего
```

Использовать `responses={429: {"model": ErrorResponse}, 503: {"model": ErrorResponse}}` в декораторе эндпоинта для OpenAPI.

### 2.5 `app/main.py` (328 строк)

**Строка 69** — изменить:
```python
# Было:
limiter = Limiter(key_func=get_remote_address)
# Стало:
limiter = Limiter(key_func=get_remote_address, headers_enabled=True)
```

**Строка 143** — опционально заменить `_rate_limit_exceeded_handler` на кастомный, возвращающий JSON в формате `ErrorResponse` (для согласованности с FR-010).

### 2.6 Тесты

| Файл | Что менять |
|------|-----------|
| `test_process_prompt_use_case.py` | Обновить `pytest.raises(Exception, match="No active")` → `pytest.raises(ServiceUnavailable)`. Добавить тесты для `AllProvidersRateLimited`. |
| **Новый**: `test_backpressure_responses.py` или расширить `test_process_prompt_use_case.py` | Тесты: все 429 → AllProvidersRateLimited, все CB open → ServiceUnavailable, смешанные → Exception |

**Endpoint-тесты** (через AsyncClient) — желательно, но не обязательно. Существующий паттерн из `test_static_files.py`:
```python
async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
    response = await client.post("/api/v1/prompts/process", json={...})
    assert response.status_code == 429
```

---

## 3. Технические ограничения

| # | Ограничение | Влияние |
|---|------------|---------|
| 1 | `Retry-After` при 429 зависит от `retry_after_seconds` провайдеров — если не возвращают, default 60 сек | Используем default, настраиваемый через env |
| 2 | slowapi in-memory storage — счётчики сбрасываются при рестарте | Приемлемо для MVP |
| 3 | `X-RateLimit-*` показывают лимит slowapi (клиентский), а не лимит LLM-провайдеров | Задокументировать в API docs |
| 4 | Два независимых "rate limit": slowapi (входящий) vs провайдерский (upstream) | Клиент получит 429 от обоих, но с разным `Retry-After` |
| 5 | Смешанные ошибки (часть 429, часть 500) → HTTP 500 | По дизайну: 429 только если ВСЕ ошибки = RateLimit |

---

## 4. Зависимости

**Новые pip-зависимости: НЕ нужны.** Всё из стандартной библиотеки + уже установленные пакеты:
- `slowapi==0.1.9` — уже установлен, `headers_enabled=True` просто включить
- `fastapi==0.115.0` — поддерживает `responses={}` в декораторе
- `pydantic==2.9.2` — для `ErrorResponse` схемы

---

## 5. Существующие тесты — влияние F025

| Тест | Что ловит сейчас | Что будет после F025 | Нужно менять? |
|------|-----------------|---------------------|---------------|
| `test_execute_no_active_models` | `Exception("No active AI models")` | `ServiceUnavailable("No active AI models")` | Да — обновить `pytest.raises` |
| `test_execute_no_configured_models` | `Exception("No configured AI models")` | `ServiceUnavailable("No configured AI models")` | Да — обновить `pytest.raises` |
| `test_all_providers_fail_raises_exception` | `Exception("All AI providers failed")` | Может быть `AllProvidersRateLimited` или `Exception` (зависит от ошибок) | Да — добавить вариант |
| `test_failure_records_to_circuit_breaker` | `Exception("All AI providers failed")` | Без изменений (ServerError → не RateLimit → Exception) | Нет |
| Все остальные тесты | — | Без изменений | Нет |

**Вывод**: только 3 теста нужно обновить. Остальные ~70 тестов не затронуты.

---

## 6. Код для переиспользования

| Модуль | Что использовать |
|--------|-----------------|
| `RateLimitError.retry_after_seconds` | Паттерн для `AllProvidersRateLimited.retry_after_seconds` |
| `CircuitBreakerManager.get_all_statuses()` | Определение "все CB open" |
| `sanitize_error_message()` | Фильтрация секретов в error body |
| `get_logger(__name__)` | structlog логирование backpressure |
| AsyncClient + ASGITransport | Паттерн endpoint-тестов из `test_static_files.py` |

---

## 7. Порядок middleware (важно для F025)

```
Запрос → CORSMiddleware → error_handling_middleware → request_id_middleware
  → Route handler (exception_handlers: RateLimitExceeded)
  → Ответ ←
```

`RateLimitExceeded` (slowapi) обрабатывается exception handler **внутри** route layer, до middleware. Новые `AllProvidersRateLimited` и `ServiceUnavailable` будут обрабатываться **внутри** endpoint function (explicit except), не через exception handlers.

---

## Quality Cascade Checklist (7/7)

### DRY ✅
- [x] `RateLimitError.retry_after_seconds` — переиспользовать паттерн
- [x] `sanitize_error_message()` — для error body
- [x] `CircuitBreakerManager.get_all_statuses()` — для определения "все CB open"
- [x] slowapi уже установлен и настроен — включить `headers_enabled`
→ Рекомендация: переиспользовать существующие, НЕ создавать дубли

### KISS ✅
- [x] 2 новых исключения + 1 Pydantic-схема + правки в 3 файлах
- [x] Нет новых pip-зависимостей
- [x] slowapi уже делает большую часть работы с заголовками — просто включить
→ Рекомендация: минимальные изменения, максимальный эффект

### YAGNI ✅
- [x] FR-020 (X-Providers-Available) — полезно, тривиально, включить
- [x] FR-021 (debug mode) — усложняет, отложить или включить минимально
→ Рекомендация: FR-020 включить, FR-021 на усмотрение

### SoC ✅
- [x] Domain (`exceptions.py`) — типы ошибок
- [x] Application (`process_prompt.py`) — определение ПОЧЕМУ все провайдеры провалились
- [x] API (`prompts.py`) — маппинг исключений на HTTP-коды
- [x] Infrastructure (`main.py`) — rate limiting на уровне сервера
→ Рекомендация: строго разделять — use case бросает доменные исключения, API маппит на HTTP

### SSoT ✅
| Тип данных | Файл-источник |
|-----------|---------------|
| Типы ошибок | `domain/exceptions.py` |
| Error body schema | `api/v1/schemas.py` (ErrorResponse) |
| Rate limit config (slowapi) | `main.py` (env: RATE_LIMIT_*, PROCESS_RATE_LIMIT) |
| Retry-After defaults | `process_prompt.py` (env: SERVICE_UNAVAILABLE_RETRY_AFTER) |
→ Рекомендация: env vars в одном месте (тот файл где используются)

### CoC ✅
- [x] Исключения: `ProviderError` → `AllProvidersRateLimited`, `ServiceUnavailable`
- [x] Тесты: `@pytest.mark.unit`, fixture из conftest, `asyncio_mode = auto`
- [x] Логирование: `logger.info("backpressure_applied", status=429, ...)`
- [x] Env vars: `UPPER_SNAKE_CASE` с defaults
→ Рекомендация: следовать конвенциям проекта

### Security ✅
- [x] Error body: числовые метрики без имён провайдеров (FR-010)
- [x] Debug mode (FR-021): выключен по умолчанию, только через env
- [x] `sanitize_error_message()` для всех логируемых ошибок
- [x] `X-RateLimit-*` — не содержат sensitive данных
→ Рекомендация: НЕ включать `last_error_message` в error body (может содержать URL провайдера)

---

## Риски

| # | Риск | Вероятность | Влияние | Митигация |
|---|------|-------------|---------|-----------|
| 1 | Смешанные ошибки (часть 429, часть 500) — как классифицировать | Med | Low | По дизайну: 429 только если ВСЕ error_types == RateLimitError |
| 2 | CB skip + RateLimit: все доступные вернули 429, остальные в CB | Med | Low | attempts > 0 и все RateLimit → 429. attempts == 0 (все CB) → 503 |
| 3 | Telegram Bot не обрабатывает 429/503 | Med | Med | Bot показывает generic ошибку — не ломается, просто менее информативно |
| 4 | slowapi vs provider 429 — путаница в Retry-After | Low | Low | slowapi 429: клиент шлёт слишком быстро. Provider 429: upstream перегружен. Разные причины, оба корректны |
| 5 | 3 существующих теста сломаются | 100% | Low | Обновить pytest.raises на новые типы исключений |

---

## Качественные ворота RESEARCH_DONE

- [x] Существующий код проанализирован (prompts.py, process_prompt.py, main.py, exceptions.py, schemas.py)
- [x] Архитектурные паттерны выявлены (catch-all → дифференциация, middleware порядок)
- [x] Технические ограничения определены (5 ограничений)
- [x] Зависимости определены (нет новых pip-зависимостей)
- [x] Рекомендации сформулированы (карта изменений по 6 файлам)
- [x] Риски идентифицированы (5 рисков с митигацией)
- [x] Quality Cascade Checklist (7/7) пройден
