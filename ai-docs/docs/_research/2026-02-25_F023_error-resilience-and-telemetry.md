---
feature_id: "F023"
feature_name: "error-resilience-and-telemetry"
title: "Research Report: Error Resilience and Telemetry"
created: "2026-02-25"
author: "AI (Researcher)"
type: "research"
status: "RESEARCH_DONE"
version: 1
mode: "FEATURE"
---

# Research Report: F023 Error Resilience and Telemetry

## 1. Анализ текущего кода

### 1.1 Fallback loop (process_prompt.py)

**Файл**: `services/free-ai-selector-business-api/app/application/use_cases/process_prompt.py`

#### Структура метода execute()

Метод `execute()` класса `ProcessPromptUseCase` реализует полный цикл обработки промпта:

1. **Получение моделей** (строка 113): `get_all_models(active_only=True, available_only=True, include_recent=True)` -- фильтрация по `available_only=True` уже исключает модели с cooldown (F012).
2. **Фильтрация по API keys** (строка 124): `_filter_configured_models()` -- через `ProviderRegistry.get_api_key_env()` (F018).
3. **Сортировка** (строка 134): по `effective_reliability_score` (F010).
4. **Build candidate models** (строка 140): если указан `model_id`, модель ставится первой.
5. **Fallback loop** (строка 194): итерация по `candidate_models`.
6. **Генерация с retry** (строка 199): `_generate_with_retry()` вызывает `retry_with_fixed_delay()`.
7. **Обработка ошибок** (строки 214-237): три ветки:
   - `RateLimitError` -> `_handle_rate_limit()` (строка 216)
   - `ServerError | TimeoutError | AuthenticationError | ValidationError | ProviderError` -> `_handle_transient_error()` (строка 227)
   - `Exception` (generic) -> `classify_error()` + dispatch (строка 232)

#### Существующий паттерн cooldown (RateLimitError)

Метод `_handle_rate_limit()` (строка 425):

```python
async def _handle_rate_limit(self, model: AIModelInfo, error: RateLimitError) -> None:
    retry_after = error.retry_after_seconds or RATE_LIMIT_DEFAULT_COOLDOWN  # 3600
    await self.data_api_client.set_availability(model.id, retry_after)
```

Ключевые наблюдения:
- Cooldown устанавливается через `data_api_client.set_availability(model_id, seconds)`
- RateLimitError НЕ вызывает `increment_failure` (graceful degradation)
- Ошибка `set_availability` обрабатывается через try/except (graceful)

#### Обработка AuthenticationError/ValidationError (текущая)

Сейчас `AuthenticationError` и `ValidationError` обрабатываются через `_handle_transient_error()` (строка 456), который ТОЛЬКО вызывает `increment_failure`. Нет вызова `set_availability`. Это означает, что при следующем запросе мёртвый провайдер снова попадёт в candidate_models.

#### Точки вставки для FR-001/FR-002

Есть два подхода:

**Подход A**: Добавить проверку типа ошибки ВНУТРИ `_handle_transient_error()`:

```python
async def _handle_transient_error(self, model, error, start_time):
    # НОВОЕ: cooldown для постоянных ошибок
    if isinstance(error, AuthenticationError):
        await self._set_cooldown_safe(model, AUTH_ERROR_COOLDOWN)
    elif isinstance(error, ValidationError):
        await self._set_cooldown_safe(model, VALIDATION_ERROR_COOLDOWN)
    # Существующее: increment_failure
    await self.data_api_client.increment_failure(...)
```

**Подход B**: Выделить AuthenticationError/ValidationError в отдельные обработчики в fallback loop (по аналогии с RateLimitError).

**Рекомендация**: Подход A предпочтительнее -- минимальные изменения, cooldown добавляется ДО increment_failure. AuthenticationError/ValidationError продолжают считаться failure (в отличие от RateLimitError), но провайдер также получает cooldown.

#### Подсчёт attempts и fallback_used (FR-010)

Для telemetry нужно добавить счётчик в fallback loop:

```python
attempts = 0
first_model = candidate_models[0]

for model in candidate_models:
    attempts += 1
    try:
        # ...generate...
        fallback_used = (model.id != first_model.id)
        break
    except ...:
        continue
```

Значение `attempts` -- количество моделей, которые были пробованы (не retry-попытки внутри одной модели). `fallback_used = True` если успешная модель не первая в списке.

### 1.2 Retry service (retry_service.py)

**Файл**: `services/free-ai-selector-business-api/app/application/services/retry_service.py`

#### Текущая реализация

```python
MAX_RETRIES = int(os.getenv("MAX_RETRIES", "10"))
RETRY_DELAY_SECONDS = int(os.getenv("RETRY_DELAY_SECONDS", "10"))

async def retry_with_fixed_delay(
    func: Callable[[], Awaitable[T]],
    max_retries: int = MAX_RETRIES,
    delay_seconds: int = RETRY_DELAY_SECONDS,
    provider_name: str = "unknown",
    model_name: str = "unknown",
) -> T:
```

Ключевые характеристики:
- Фиксированная задержка: `asyncio.sleep(delay_seconds)` на строке 91
- `max_retries=10` + initial = 11 попыток, максимум 100 сек ожидания
- Retry только для `ServerError` и `TimeoutError` (через `is_retryable()`)
- Non-retryable ошибки (RateLimitError, AuthenticationError, ValidationError) пробрасываются сразу
- Цикл: `for attempt in range(max_retries + 1)` (строка 57)

#### План замены на exponential backoff

Нужно заменить строку 91:

```python
# Было:
await asyncio.sleep(delay_seconds)

# Будет:
delay = min(base_delay * (2 ** attempt), max_delay) + random.uniform(0, jitter)
await asyncio.sleep(delay)
```

Новая сигнатура функции:

```python
async def retry_with_exponential_backoff(
    func: Callable[[], Awaitable[T]],
    max_retries: int = MAX_RETRIES,           # 3 (было 10)
    base_delay: float = RETRY_BASE_DELAY,     # 2.0
    max_delay: float = RETRY_MAX_DELAY,       # 30.0
    jitter: float = RETRY_JITTER,             # 1.0
    provider_name: str = "unknown",
    model_name: str = "unknown",
) -> T:
```

Alias для обратной совместимости:

```python
# deprecated alias
retry_with_fixed_delay = retry_with_exponential_backoff
```

**Важно**: параметр `delay_seconds` (int) заменяется на `base_delay` (float), `max_delay` (float), `jitter` (float). Существующие тесты, передающие `delay_seconds=0`, нужно обновить (или alias должен принимать `delay_seconds` и маппить на `base_delay`).

### 1.3 Domain models и schemas

#### PromptResponse (domain/models.py)

Текущие поля (строки 55-68):

```python
@dataclass
class PromptResponse:
    prompt_text: str
    response_text: str
    selected_model_name: str
    selected_model_provider: str
    response_time: Decimal
    success: bool
    error_message: Optional[str] = None
```

**Для FR-010**: добавить поля с default-значениями для обратной совместимости:

```python
    attempts: int = 1
    fallback_used: bool = False
```

#### ProcessPromptResponse (api/v1/schemas.py)

Текущие поля (строки 40-48):

```python
class ProcessPromptResponse(BaseModel):
    prompt: str
    response: str
    selected_model: str
    provider: str
    response_time_seconds: Decimal
    success: bool
```

**Для FR-011**: добавить:

```python
    attempts: int = Field(1, description="Number of models tried before success")
    fallback_used: bool = Field(False, description="Whether fallback model was used")
```

#### HTTP endpoint маппинг (api/v1/prompts.py)

Строки 69-76 -- маппинг domain -> schema:

```python
return ProcessPromptResponse(
    prompt=response.prompt_text,
    response=response.response_text,
    selected_model=response.selected_model_name,
    provider=response.selected_model_provider,
    response_time_seconds=response.response_time,
    success=response.success,
)
```

**Для FR-011**: добавить:

```python
    attempts=response.attempts,
    fallback_used=response.fallback_used,
```

### 1.4 Error classifier и exceptions

#### Иерархия исключений (domain/exceptions.py)

```
ProviderError (base)
  +-- RateLimitError     (429)         -- retry_after_seconds: Optional[int]
  +-- ServerError        (5xx)         -- pass
  +-- TimeoutError       (timeout)     -- pass
  +-- AuthenticationError (401, 403)   -- pass
  +-- ValidationError    (400, 422)    -- pass
```

**Важный вывод**: у `AuthenticationError` и `ValidationError` НЕТ поля `http_status_code`. Нет способа отличить 401 от 403, или 400 от 404/422, кроме парсинга `message`. Для FR-001/FR-002 это не критично -- cooldown одинаковый для всех кодов одного типа.

Для FR-020 (логирование cooldown с http_status_code) -- если нужен точный HTTP код, придётся либо:
1. Добавить поле `http_status_code` в `ProviderError`
2. Парсить из `message` (ненадёжно)
3. Логировать только тип ошибки без HTTP кода

**Рекомендация**: логировать `error_type=type(error).__name__` (уже есть в `_handle_transient_error`, строка 478). Добавление `http_status_code` -- отдельная задача, не блокирует F023.

#### Error classifier (error_classifier.py)

Текущая классификация (после F022):

| HTTP код | Класс | Retryable |
|----------|-------|-----------|
| 429 | RateLimitError | No (fallback) |
| 500 with "429" | RateLimitError | No (fallback) |
| 5xx | ServerError | Yes |
| 401, 403 | AuthenticationError | No |
| 402 | AuthenticationError | No |
| 400, 422 | ValidationError | No |
| 404 | ValidationError | No |
| timeout | TimeoutError | Yes |
| other | ProviderError | No |

`is_retryable()` возвращает `True` только для `ServerError` и `TimeoutError`. Это корректно -- AuthenticationError и ValidationError не ретраятся в retry_service, а сразу пробрасываются в fallback loop.

### 1.5 Data API client

**Файл**: `services/free-ai-selector-business-api/app/infrastructure/http_clients/data_api_client.py`

#### Метод set_availability

Строки 202-231:

```python
async def set_availability(self, model_id: int, retry_after_seconds: int) -> None:
    response = await self.client.patch(
        f"{self.base_url}/api/v1/models/{model_id}/availability",
        params={"retry_after_seconds": retry_after_seconds},
        headers=self._get_headers(),
    )
    response.raise_for_status()
```

**Ключевые наблюдения**:
- Принимает `model_id: int` и `retry_after_seconds: int`
- HTTP PATCH к `/api/v1/models/{id}/availability`
- Параметр передаётся как query param (не body)
- Ошибки логируются и пробрасываются (raise)
- Используется из `_handle_rate_limit` с try/except -- ошибка не прерывает fallback loop

#### Паттерн вызова из use case

В `_handle_rate_limit()`:

```python
try:
    await self.data_api_client.set_availability(model.id, retry_after)
except Exception as avail_error:
    logger.error("set_availability_failed", ...)
```

Для FR-001/FR-002 нужен аналогичный try/except в `_handle_transient_error()`.

### 1.6 Конфигурация (env-переменные)

#### Текущий паттерн чтения env

В каждом файле env читаются на уровне модуля:

```python
# retry_service.py
MAX_RETRIES = int(os.getenv("MAX_RETRIES", "10"))
RETRY_DELAY_SECONDS = int(os.getenv("RETRY_DELAY_SECONDS", "10"))

# process_prompt.py
RATE_LIMIT_DEFAULT_COOLDOWN = int(os.getenv("RATE_LIMIT_DEFAULT_COOLDOWN", "3600"))
MAX_PROMPT_CHARS = int(os.getenv("MAX_PROMPT_CHARS", "6000"))
```

НЕТ единого `settings.py` или `config.py`. Каждый модуль читает свои env-переменные самостоятельно.

#### Docker-compose

В `docker-compose.yml` (строки 116-118):

```yaml
MAX_RETRIES: ${MAX_RETRIES:-10}
RETRY_DELAY_SECONDS: ${RETRY_DELAY_SECONDS:-10}
RATE_LIMIT_DEFAULT_COOLDOWN: ${RATE_LIMIT_DEFAULT_COOLDOWN:-3600}
```

Для F023 нужно добавить:

```yaml
AUTH_ERROR_COOLDOWN_SECONDS: ${AUTH_ERROR_COOLDOWN_SECONDS:-86400}
VALIDATION_ERROR_COOLDOWN_SECONDS: ${VALIDATION_ERROR_COOLDOWN_SECONDS:-86400}
RETRY_BASE_DELAY: ${RETRY_BASE_DELAY:-2.0}
RETRY_MAX_DELAY: ${RETRY_MAX_DELAY:-30.0}
RETRY_JITTER: ${RETRY_JITTER:-1.0}
```

А также обновить default для `MAX_RETRIES`:

```yaml
MAX_RETRIES: ${MAX_RETRIES:-3}
```

**Примечание**: `RETRY_DELAY_SECONDS` может быть удалён или оставлен для обратной совместимости. Рекомендуется оставить -- если кто-то задал его в `.env`, он должен продолжать работать (через alias).

### 1.7 Health worker

**Файл**: `services/free-ai-selector-health-worker/app/main.py`

Health worker использует `available_only=true` при запросе моделей (строка 325):

```python
response = await client.get(
    f"{DATA_API_URL}/api/v1/models?active_only=true&available_only=true"
)
```

Это означает, что модели с cooldown (RateLimitError, а после F023 -- AuthenticationError/ValidationError) автоматически исключаются из health checks. Это **корректное поведение**: нет смысла проверять здоровье провайдера, который заведомо недоступен.

Через 24 часа cooldown истечёт, модель снова попадёт в health checks, и если провайдер по-прежнему возвращает 401/403/404, cooldown будет установлен снова (при следующем пользовательском запросе через fallback loop).

**Важно**: Health worker НЕ устанавливает cooldown -- он только вызывает `increment_success`/`increment_failure`. Cooldown устанавливается только из Business API при реальных пользовательских запросах.

---

## 2. Архитектурные паттерны

### 2.1 Паттерн cooldown (из F012)

Паттерн уже реализован для RateLimitError:

1. В fallback loop: `except RateLimitError -> _handle_rate_limit()`
2. `_handle_rate_limit()` вызывает `set_availability(model_id, seconds)`
3. Data API устанавливает `available_at = now + seconds` в PostgreSQL
4. При следующем запросе: `get_all_models(available_only=True)` исключает модель
5. Ошибка `set_availability` не прерывает fallback loop (try/except)

**Для Auth/Validation errors**: тот же самый паттерн, но вызов идёт изнутри `_handle_transient_error()` (до `increment_failure`), а не из отдельного обработчика. Разница: Auth/Validation errors ТАКЖЕ записываются как failure (снижают reliability_score), в отличие от RateLimitError.

### 2.2 Паттерн retry

Текущий подход:
- `retry_with_fixed_delay()` -- единственная функция retry
- Вызывается из `_generate_with_retry()` в process_prompt.py
- Retries только для ServerError/TimeoutError
- Non-retryable ошибки пробрасываются в вызывающий код

Что нужно изменить:
1. Добавить расчёт delay: `min(base_delay * 2^attempt, max_delay) + jitter`
2. Изменить default `MAX_RETRIES` с 10 на 3
3. Добавить параметры `base_delay`, `max_delay`, `jitter`
4. Сохранить alias `retry_with_fixed_delay` для обратной совместимости
5. Добавить `import random` для jitter

### 2.3 Паттерн DTO/Response

Данные передаются через 3 слоя:

```
UseCase.execute()
  -> PromptResponse (domain model, dataclass)
    -> prompts.py (HTTP endpoint, маппинг)
      -> ProcessPromptResponse (Pydantic schema, HTTP response)
```

Для telemetry нужно добавить поля на всех 3 уровнях:
1. `PromptResponse` -- `attempts: int = 1`, `fallback_used: bool = False`
2. `ProcessPromptResponse` -- `attempts: int`, `fallback_used: bool`
3. `prompts.py` -- маппинг `response.attempts`, `response.fallback_used`

---

## 3. Зависимости

### 3.1 Зависимость от F022

F023 **критически зависит** от F022 (этапы 1-3):

| F022 компонент | Нужен для F023 | Статус |
|----------------|----------------|--------|
| classify_error: 402 -> AuthenticationError | FR-001 (cooldown для auth errors) | Реализован (error_classifier.py строки 88-92) |
| classify_error: 404 -> ValidationError | FR-002 (cooldown для validation errors) | Реализован (error_classifier.py строки 94-99) |
| HTTPStatusError проброс из провайдеров | Все FR (classify_error получает HTTP-код) | Реализован (base.py строка 203: raise) |
| Payload budget (MAX_PROMPT_CHARS) | Снижение ложных 422 | Реализован (process_prompt.py строки 174-186) |

**Вывод**: F022 этапы 1-3 уже реализованы в текущей кодовой базе (ветка `feature/F022-error-classifier-fix`). F023 может быть реализован на текущей ветке.

### 3.2 Внутренние зависимости между FR

| FR | Зависит от | Описание |
|----|-----------|----------|
| FR-001 (cooldown auth) | -- | Независимый |
| FR-002 (cooldown validation) | -- | Независимый (тот же паттерн что FR-001) |
| FR-003 (exponential backoff) | -- | Независимый |
| FR-004 (MAX_RETRIES=3) | FR-003 | Логически связан, но технически независим |
| FR-010 (PromptResponse telemetry) | -- | Независимый |
| FR-011 (Schema telemetry) | FR-010 | Зависит от FR-010 (маппинг domain -> schema) |
| FR-012 (error_type в 500) | -- | Независимый |
| FR-020 (cooldown logging) | FR-001/FR-002 | Реализуется вместе с cooldown |
| FR-021 (deprecated alias) | FR-003 | Alias для новой функции |

**Порядок реализации**: FR можно реализовывать в три независимые группы:
1. **Cooldown**: FR-001 + FR-002 + FR-020
2. **Backoff**: FR-003 + FR-004 + FR-021
3. **Telemetry**: FR-010 + FR-011 + FR-012

---

## 4. Существующие тесты

### 4.1 Покрытие

| Файл тестов | Что тестирует | Кол-во тест-классов | Кол-во тестов |
|-------------|---------------|---------------------|---------------|
| `test_retry_service.py` | retry_with_fixed_delay: retry, no-retry, delays | 2 класса | 12 тестов |
| `test_process_prompt_use_case.py` | execute(), model selection, F011-B, F014 error handling | 4 класса | 14 тестов |
| `test_error_classifier.py` | classify_error, parse_retry_after, is_retryable | 3 класса | 15 тестов |
| `test_f012_rate_limit_handling.py` | Rate limit handling, filter configured, available_only | 3 класса | 7 тестов |

#### Критические для F023 тесты

**test_retry_service.py**:
- `test_delay_between_retries` -- мокает `asyncio.sleep`, проверяет вызов с `delay_seconds=10`. Нужно обновить для exponential backoff.
- `test_exhausted_retries_raises_last_error` -- `max_retries=2`, проверяет 3 total attempts. Останется валидным.
- Все тесты передают `delay_seconds=0` -- нужно обновить параметр на `base_delay=0`.

**test_process_prompt_use_case.py**:
- `test_handle_transient_error_calls_increment_failure` -- проверяет increment_failure. После F023 нужно добавить проверку `set_availability` для AuthenticationError.
- `test_handle_transient_error_works_with_various_exception_types` -- тестирует все типы ошибок через `_handle_transient_error`. Нужно расширить.

**test_f012_rate_limit_handling.py**:
- `test_rate_limit_triggers_set_availability` -- образец для нового теста cooldown AuthenticationError.
- `test_rate_limit_does_not_reduce_reliability_score` -- для Auth/Validation errors score ДОЛЖЕН снижаться.

### 4.2 Тестовые утилиты

#### Фикстуры (conftest.py)

```python
@pytest.fixture
def mock_data_api_client(monkeypatch):
    mock_client = AsyncMock()
    mock_client.get_all_models.return_value = [...]
    mock_client.increment_success.return_value = None
    mock_client.increment_failure.return_value = None
    mock_client.create_history.return_value = 1
    mock_client.set_availability.return_value = None
    return mock_client
```

`set_availability` уже замокан -- готов для тестов cooldown.

#### Паттерны мокирования

1. **ProviderRegistry**: `@patch("app.application.use_cases.process_prompt.ProviderRegistry")`
2. **asyncio.sleep**: `@patch("app.application.services.retry_service.asyncio.sleep", new_callable=AsyncMock)`
3. **os.environ**: `@patch.dict(os.environ, {"KEY": "value"})`
4. **Provider mock**: `mock_provider = AsyncMock(); mock_provider.generate.return_value = "text"`

---

## 5. Риски и ограничения

### 5.1 Технические риски

| # | Риск | Вероятность | Влияние | Митигация |
|---|------|-------------|---------|-----------|
| 1 | Тесты сломаются при смене сигнатуры retry_with_fixed_delay | Высокая | Средняя | FR-021: alias с обратной совместимостью параметров |
| 2 | MAX_RETRIES=3 default может увеличить частоту fallback | Средняя | Низкая | При 14 моделях fallback loop компенсирует. Env override доступен |
| 3 | Cooldown 24ч для всех ValidationError (включая 400/422) может быть избыточным | Средняя | Средняя | F022 payload budget снижает 422. Отдельная env-переменная позволяет настроить |
| 4 | Telegram-бот парсит HTTP response -- новые поля не сломают | Низкая | Низкая | Telegram-бот использует httpx и парсит только нужные поля |
| 5 | Health worker пропускает модели с cooldown -- не увидит восстановление раньше 24ч | Средняя | Низкая | Через 24ч health worker снова проверит. Ручной reset: `set_availability(id, 0)` |

### 5.2 Обратная совместимость

| Изменение | Breaking? | Митигация |
|-----------|-----------|-----------|
| Новые поля в HTTP response (attempts, fallback_used) | Нет | Аддитивное изменение |
| retry_with_fixed_delay -> retry_with_exponential_backoff | Да (внутренний) | Alias сохраняется |
| MAX_RETRIES default 10 -> 3 | Да (поведение) | Env override, документация в CHANGELOG |
| Новые env-переменные | Нет | Все имеют defaults |
| Cooldown для Auth/Validation errors | Да (поведение) | Env-конфигурируемый cooldown, ручной reset |

---

## 6. Рекомендации

### 6.1 Порядок реализации

Рекомендуемый порядок (3 этапа, могут быть реализованы в одном коммите):

**Этап 1: Cooldown (FR-001, FR-002, FR-020)**
- Модифицировать `_handle_transient_error()` в process_prompt.py
- Добавить env-переменные `AUTH_ERROR_COOLDOWN_SECONDS`, `VALIDATION_ERROR_COOLDOWN_SECONDS`
- Добавить в docker-compose.yml
- Тесты: cooldown для AuthenticationError, cooldown для ValidationError

**Этап 2: Exponential backoff (FR-003, FR-004, FR-021)**
- Создать `retry_with_exponential_backoff()` в retry_service.py
- Изменить default MAX_RETRIES на 3
- Alias `retry_with_fixed_delay`
- Обновить вызов в `_generate_with_retry()`
- Тесты: exponential delays, jitter, max_retries=3

**Этап 3: Telemetry (FR-010, FR-011, FR-012)**
- Добавить поля в PromptResponse (domain)
- Добавить поля в ProcessPromptResponse (schema)
- Обновить маппинг в prompts.py
- Подсчитать attempts и fallback_used в execute()
- Тесты: response содержит attempts и fallback_used

### 6.2 Точки внимания

1. **Alias retry_with_fixed_delay**: Должен принимать старые параметры (`delay_seconds`) и маппить на новые (`base_delay`). Вариант -- сделать `retry_with_fixed_delay` wrapper, который вызывает `retry_with_exponential_backoff` с `base_delay=delay_seconds, max_delay=delay_seconds, jitter=0`.

2. **attempts counter**: считать количество пробованных моделей (не retry-попыток внутри одной модели). Retry-попытки внутри одной модели -- это деталь retry_service, не видимая в telemetry.

3. **error_type в 500 response (FR-012)**: в текущем коде ошибка возвращается как `"All AI providers failed. Last error: ..."`. Можно добавить тип ошибки в это сообщение.

4. **docker-compose.vps.yml**: проверить, нужно ли дублировать новые env-переменные в VPS-конфигурации.

---

## 7. Quality Cascade Checklist (7/7)

### QC-1: DRY

- [x] Найден паттерн cooldown в `_handle_rate_limit()` -- переиспользовать для Auth/Validation
- [x] `data_api_client.set_availability()` уже реализован и протестирован (F012)
- [x] `conftest.py` содержит готовую фикстуру `mock_data_api_client` с `set_availability`
- [x] Тест `test_rate_limit_triggers_set_availability` -- образец для новых тестов
- Рекомендация: переиспользовать существующий `set_availability()`, НЕ создавать новый метод

### QC-2: KISS

- [x] PRD предлагает 10 FR + 2 Could Have. Оценка сложности:
  - FR-001/FR-002: тривиальные -- добавить if/elif + вызов set_availability (примерно 10 строк кода)
  - FR-003: средняя -- замена формулы delay, новые параметры (примерно 15 строк кода)
  - FR-004: тривиальная -- изменение одного default
  - FR-010/FR-011: тривиальные -- добавить 2 поля в dataclass и schema
  - FR-012: тривиальная -- добавить тип ошибки в строку
  - FR-020: тривиальная -- расширить существующее логирование
  - FR-021: средняя -- alias с обратной совместимостью параметров
- [x] FR-021 (deprecated alias) можно упростить: вместо сложного маппинга параметров, оставить старое имя как присваивание
- Рекомендация: все компоненты PRD обоснованы и не содержат избыточной сложности

### QC-3: YAGNI

- [x] Проверен каждый FR:
  - FR-001/FR-002: нужны СЕЙЧАС (108 000+ бесполезных вызовов за 48ч)
  - FR-003/FR-004: нужны СЕЙЧАС (100 сек retry на провайдер)
  - FR-010/FR-011: нужны СЕЙЧАС (диагностика без SSH)
  - FR-012: нужна СЕЙЧАС (error_type для batch-скрипта)
  - FR-020: COULD HAVE, но реализуется вместе с FR-001/FR-002 (2 строки)
  - FR-021: COULD HAVE, но критичен для обратной совместимости тестов
- Рекомендация: все FR оправданы текущими production-проблемами. Исключать нечего.

### QC-4: SoC

- [x] Структура модулей проанализирована:
  - `process_prompt.py` -- orchestration (fallback loop, error dispatch)
  - `retry_service.py` -- retry logic (delay, backoff)
  - `error_classifier.py` -- error classification (HTTP code -> exception type)
  - `data_api_client.py` -- data access (HTTP to Data API)
  - `models.py` -- domain DTOs
  - `schemas.py` -- HTTP schemas
  - `prompts.py` -- HTTP endpoint (маппинг)
- [x] Границы соблюдаются в F023:
  - Cooldown logic в `process_prompt.py` (orchestration)
  - Backoff logic в `retry_service.py` (retry)
  - Telemetry в `models.py` + `schemas.py` + `prompts.py` (DTO chain)
- Рекомендация: не выносить cooldown в отдельный сервис -- это часть orchestration

### QC-5: SSoT

- [x] Файлы конфигурации:
  - Env-переменные: на уровне модуля через `os.getenv()` (нет единого settings.py)
  - Docker: `docker-compose.yml`, `docker-compose.vps.yml`
- [x] Модели/типы:
  - Domain: `app/domain/models.py` (PromptResponse)
  - Schema: `app/api/v1/schemas.py` (ProcessPromptResponse)
  - Exceptions: `app/domain/exceptions.py`
- [x] Константы:
  - retry_service.py: MAX_RETRIES, RETRY_DELAY_SECONDS
  - process_prompt.py: RATE_LIMIT_DEFAULT_COOLDOWN, MAX_PROMPT_CHARS

| Тип данных | Файл-источник |
|------------|---------------|
| Retry параметры | `retry_service.py` (module-level os.getenv) |
| Cooldown параметры | `process_prompt.py` (module-level os.getenv) |
| PromptResponse | `domain/models.py` |
| ProcessPromptResponse | `api/v1/schemas.py` |
| Error types | `domain/exceptions.py` |
| Error classification | `services/error_classifier.py` |

### QC-6: CoC

- [x] Стиль кода:
  - Env-переменные: `UPPER_SNAKE_CASE` на уровне модуля
  - Методы: `_private_method()` с docstring
  - Async: все Data API вызовы async
  - Error handling: try/except с logger.error + sanitize_error_message
  - Logging: structlog (get_logger) с именованными параметрами
- [x] Паттерны проекта:
  - Graceful degradation: ошибка set_availability не прерывает flow
  - Конвенция `_handle_*`: private async методы для обработки ошибок
  - Тесты: `@pytest.mark.unit`, AsyncMock, `@patch.dict(os.environ, ...)`
- Рекомендация: следовать конвенциям -- `_handle_*` для новых обработчиков, `sanitize_error_message` для логов

Примеры конвенций из кода:

```python
# Env-переменная (process_prompt.py:50)
RATE_LIMIT_DEFAULT_COOLDOWN = int(os.getenv("RATE_LIMIT_DEFAULT_COOLDOWN", "3600"))

# Error handling (process_prompt.py:447-454)
try:
    await self.data_api_client.set_availability(model.id, retry_after)
except Exception as avail_error:
    logger.error(
        "set_availability_failed",
        model=model.name,
        error=sanitize_error_message(avail_error),
    )

# Тест (test_f012:33-87)
@patch.dict(os.environ, {"TEST_API_KEY": "test_key"})
@patch("app.application.use_cases.process_prompt.ProviderRegistry")
async def test_rate_limit_triggers_set_availability(
    self, mock_registry, mock_data_api_client
):
```

### QC-7: Security

- [x] `sanitize_error_message()` используется ВЕЗДЕ при логировании ошибок -- продолжать использовать в новых логах
- [x] Cooldown через Data API (HTTP PATCH) -- нет прямого доступа к БД
- [x] Нет sensitive данных в telemetry полях (attempts, fallback_used -- числа и bool)
- [x] error_type в HTTP 500 response: только тип исключения (AuthenticationError), без API key
- Рекомендация: в FR-012 НЕ включать оригинальный message ошибки в HTTP response -- только тип. Message может содержать URL с параметрами.

---

## 8. Итоговые ворота

### RESEARCH_DONE Checklist

- [x] Код проанализирован (FEATURE mode): process_prompt.py, retry_service.py, error_classifier.py, exceptions.py, models.py, schemas.py, prompts.py, data_api_client.py, health worker, conftest.py
- [x] Архитектурные паттерны выявлены: cooldown через set_availability, retry через retry_service, DTO chain (domain -> schema -> endpoint)
- [x] Технические ограничения определены: нет http_status_code в exceptions, нет единого settings.py, alias для обратной совместимости
- [x] Рекомендации сформулированы: 3 этапа реализации, точки внимания
- [x] Риски идентифицированы: 5 технических рисков + митигация
- [x] Quality Cascade Checklist (7/7) включён
- [x] Все 7 проверок пройдены
