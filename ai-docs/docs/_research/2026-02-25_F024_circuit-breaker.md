# Research Report: F024 Circuit Breaker для AI-провайдеров

**Feature ID**: F024
**Дата**: 2026-02-25
**Режим**: FEATURE
**Статус**: RESEARCH_DONE

---

## 1. Анализ существующего кода

### 1.1 Failover loop в ProcessPromptUseCase

**Файл**: `app/application/use_cases/process_prompt.py`

Цикл перебора провайдеров (строки 205-249):

```
for model in candidate_models:          # строка 205
    try:                                 # строка 207
        provider = _get_provider_for_model(model)    # строка 208
        response = _generate_with_retry(provider, request, model)  # строка 211-215
        successful_model = model         # строка 218
        break                            # строка 224
    except RateLimitError as e:          # строка 226
        _handle_rate_limit(model, e)     # → set_availability(cooldown)
    except (ServerError, TimeoutError, AuthenticationError,
            ValidationError, ProviderError) as e:  # строка 231
        _handle_transient_error(model, e, start_time)  # → increment_failure()
    except Exception as e:               # строка 242
        classified = classify_error(e)
        # маршрутизация по типу classified
```

**Ключевые наблюдения**:
- Имя провайдера: `model.provider` (тип `str`, e.g. `"Groq"`, `"Scaleway"`)
- Успех записывается в строках 282-291 (`increment_success`)
- Failure записывается внутри `_handle_transient_error` (строки 507-511)
- RateLimitError **не** считается failure для reliability_score

### 1.2 Точки интеграции CB

| Точка | Строка | Действие |
|-------|--------|----------|
| Перед вызовом провайдера | между 205 и 207 | `is_available(model.provider)` → skip если OPEN |
| После успеха | 218 (перед break) | `record_success(model.provider)` |
| В except RateLimitError | 226-229 | Не вызывать `record_failure` (аналогично reliability_score) |
| В except (Server/Auth/...) | 231-240 | `record_failure(model.provider)` |
| В except Exception | 242-249 | `record_failure(model.provider)` |

### 1.3 Конструктор ProcessPromptUseCase

```python
def __init__(self, data_api_client: DataAPIClient):   # строка 77
    self.data_api_client = data_api_client
```

Единственная инжектируемая зависимость. Остальные сервисы (error_classifier, retry_service, ProviderRegistry) импортируются как module-level функции/классы.

### 1.4 Обработка permanent errors (F022/F023)

В `_handle_transient_error` (строки 471-517) уже реализован cooldown для постоянных ошибок:
- `AuthenticationError` → `_set_cooldown_safe(model, AUTH_ERROR_COOLDOWN_SECONDS)` (строки 498-501)
- `ValidationError` → `_set_cooldown_safe(model, VALIDATION_ERROR_COOLDOWN_SECONDS)` (строки 502-505)

Cooldown работает через Data API (`set_availability`), т.е. **требует HTTP-запрос**. CB дополнит это **in-memory** быстрым пропуском.

---

## 2. Архитектурные паттерны проекта

### 2.1 Сервисный слой

| Файл | Паттерн | Состояние |
|------|---------|-----------|
| `error_classifier.py` | Module-level pure functions | Stateless |
| `retry_service.py` | Module-level async functions + constants | Stateless |
| `ProviderRegistry` | Class с `_instances` dict + classmethods | Stateful singleton |

**Вывод**: для CB с состоянием лучший аналог — `ProviderRegistry` (class с classmethods и class-level dict).

### 2.2 Конфигурация

Все параметры через `os.getenv()` на уровне модуля:
```python
MAX_RETRIES = int(os.getenv("MAX_RETRIES", "3"))
RETRY_BASE_DELAY = float(os.getenv("RETRY_BASE_DELAY", "2.0"))
```

### 2.3 Логирование

- Logger: `logger = get_logger(__name__)` из `app.utils.logger` (structlog)
- Конвенция событий: `snake_case` без префикса модуля
- Уровни: `info` (success), `warning` (degradation), `error` (failures), `debug` (skip)
- Стиль: kwargs-based (`logger.warning("event_name", key1=val1, key2=val2)`)

### 2.4 Инстанциация use cases

Ручное inline wiring в endpoint-хендлерах (`app/api/v1/endpoints/prompts.py`, строки 50-54):
```python
data_api_client = DataAPIClient(request_id=request_id)
use_case = ProcessPromptUseCase(data_api_client)
```

CB как module-level singleton не требует изменений в wiring.

---

## 3. Тестовые паттерны

### 3.1 Структура тестов

| Аспект | Конвенция |
|--------|-----------|
| Расположение | `tests/unit/test_{module}.py` |
| Организация | Классы с `@pytest.mark.unit` |
| Async | `async def test_...` (без `@pytest.mark.asyncio`, `asyncio_mode = auto`) |
| Фикстура | `mock_data_api_client` из `conftest.py` |
| Моки | `@patch("...ProviderRegistry")`, `@patch.dict(os.environ, {...})` |
| Assertions | Plain `assert`, `pytest.raises`, `mock.assert_called_*` |
| Docstrings | Английский, со ссылкой на FR: `"""F024: CB opens after N failures."""` |

### 3.2 Мок провайдеров

```python
@patch("app.application.use_cases.process_prompt.ProviderRegistry")
async def test_something(self, mock_registry, mock_data_api_client):
    mock_provider = AsyncMock()
    mock_provider.generate.return_value = "response"
    mock_registry.get_provider.return_value = mock_provider
```

### 3.3 Мок time (для recovery_timeout)

Для тестов CB нужно мокать `time.time()`:
```python
@patch("app.application.services.circuit_breaker.time.time")
def test_recovery(self, mock_time):
    mock_time.return_value = 1000.0
    # record failures → OPEN
    mock_time.return_value = 1061.0  # +61 сек
    assert cb.is_available("Groq") is True  # HALF-OPEN
```

---

## 4. Решения по реализации

### 4.1 Паттерн: Class с classmethods (как ProviderRegistry)

```python
class CircuitBreakerManager:
    _circuits: ClassVar[dict[str, ProviderCircuit]] = {}

    @classmethod
    def is_available(cls, provider_name: str) -> bool: ...

    @classmethod
    def record_success(cls, provider_name: str) -> None: ...

    @classmethod
    def record_failure(cls, provider_name: str) -> None: ...

    @classmethod
    def get_all_statuses(cls) -> dict[str, str]: ...

    @classmethod
    def reset(cls) -> None:
        cls._circuits.clear()  # Для тестов
```

**Обоснование**: соответствует паттерну ProviderRegistry, не требует DI, тестируется через `reset()`.

### 4.2 Интеграция: прямой import (не инъекция)

```python
# В process_prompt.py:
from app.application.services.circuit_breaker import CircuitBreakerManager
```

Не менять сигнатуру `__init__`, не менять wiring в endpoints. CB — module-level singleton.

### 4.3 RateLimitError и CB

RateLimitError **не должен** открывать CB:
- 429 = временное состояние (rate limit reset через N секунд)
- Обработка 429 через `set_availability` уже корректна
- CB должен реагировать только на "серийные" ошибки, а не на throttling

### 4.4 Конфигурация через env

| Переменная | Default | Описание |
|-----------|---------|----------|
| `CB_FAILURE_THRESHOLD` | 5 | Ошибок подряд для CLOSED → OPEN |
| `CB_RECOVERY_TIMEOUT` | 60 | Секунд до OPEN → HALF-OPEN |

---

## 5. Зависимости

### 5.1 Зависимость от F022

CB эффективен только при корректной классификации ошибок:
- Без F022: `httpx.HTTPStatusError` оборачивается в generic `ProviderError`, CB считает все ошибки одинаковыми — работает, но менее точно
- С F022: 402/404 → `AuthenticationError`/`ValidationError` → можно реализовать FR-020 (ускоренное открытие для permanent errors)

**Вывод**: F024 может быть реализован независимо от F022. Но с F022 — точнее.

### 5.2 Зависимость от F023

F023 добавляет cooldown для permanent errors через Data API. CB (F024) работает **параллельно**:
- CB: in-memory, мгновенный пропуск, основан на серии ошибок
- F023 cooldown: через Data API, сохраняется между рестартами, основан на типе ошибки

Не конфликтуют. CB срабатывает первым (in-memory), cooldown через Data API — страховка.

### 5.3 Внешние зависимости

Нет новых зависимостей. Используется только stdlib (`time`, `enum`, `dataclasses`, `os`).

---

## 6. Затрагиваемые файлы

| Файл | Тип изменения | Описание |
|------|---------------|----------|
| `app/application/services/circuit_breaker.py` | **Новый** | CircuitBreakerManager, CircuitState, ProviderCircuit |
| `app/application/use_cases/process_prompt.py` | Модификация | Добавить import CB + 4 точки интеграции в failover loop |
| `tests/unit/test_circuit_breaker.py` | **Новый** | Unit-тесты CB state machine |
| `tests/unit/test_process_prompt_use_case.py` | Модификация | Тесты интеграции CB в failover |

---

## 7. Риски и ограничения

| # | Риск | Митигация |
|---|------|-----------|
| 1 | State не шарится между uvicorn workers | Допустимо — 1 worker в текущей конфигурации |
| 2 | State теряется при рестарте | CB восстанавливает за ~5 запросов на провайдер |
| 3 | Мок CB в существующих тестах | CB как classmethod с `reset()` — мокается через `@patch` или `reset()` в setup |
| 4 | Class-level `_circuits` dict не thread-safe | `asyncio` — single-threaded event loop, не проблема |

---

## 8. Рекомендации

1. **Реализовать CB как classmethod singleton** (паттерн ProviderRegistry) — минимальное отклонение от архитектуры проекта
2. **Не инжектировать в конструктор** — импортировать напрямую в `process_prompt.py`
3. **Не считать RateLimitError** как failure для CB — только ServerError, TimeoutError, AuthenticationError, ValidationError, generic ProviderError
4. **Добавить `reset()`** для тестируемости
5. **Логировать переходы** (`circuit_state_changed`) на уровне `warning` — видно в prod-логах без лишнего шума
