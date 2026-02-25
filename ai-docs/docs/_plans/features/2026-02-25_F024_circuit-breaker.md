# План фичи: F024 — Circuit Breaker для AI-провайдеров

**Feature ID**: F024
**Дата**: 2026-02-25
**Статус**: Ожидает утверждения
**Связанные артефакты**: [PRD](../../_analysis/2026-02-25_F024_circuit-breaker.md), [Research](../../_research/2026-02-25_F024_circuit-breaker.md)

---

## Контекст

В массовом прогоне (3686 запросов) 8 из 13 провайдеров возвращали постоянные ошибки, но система продолжала обращаться к ним в каждом запросе — перебор мёртвых провайдеров добавлял ~4.5 сек латентности. Нужен in-memory Circuit Breaker, который мгновенно исключает провайдера после серии ошибок и автоматически восстанавливает через пробный запрос. CB реализуется как classmethod singleton (паттерн ProviderRegistry), интегрируется в failover loop через прямой import без изменения DI.

---

## Содержание

1. Модуль CircuitBreakerManager (новый файл)
2. Интеграция CB в failover loop (process_prompt.py)
3. Unit-тесты CB + интеграционные тесты в process_prompt

---

## Краткая версия плана

### Этап 1: Модуль CircuitBreakerManager

1. **Проблема** — Нет механизма in-memory блокировки провайдеров после серии ошибок. Текущий cooldown работает через HTTP к Data API и только для 429.
2. **Действие** — Создать файл `app/application/services/circuit_breaker.py` с классом `CircuitBreakerManager` (classmethods + class-level dict `_circuits`), enum `CircuitState` (CLOSED/OPEN/HALF_OPEN) и dataclass `ProviderCircuit`. Конфигурация через env: `CB_FAILURE_THRESHOLD=5`, `CB_RECOVERY_TIMEOUT=60`.
3. **Результат** — Модуль с 4 публичными методами: `is_available(provider)`, `record_success(provider)`, `record_failure(provider)`, `get_all_statuses()`. Полная state machine с переходами.
4. **Зависимости** — Нет. Полностью автономный модуль.
5. **Риски** — State теряется при рестарте (допустимо — восстановление за ~5 запросов). Не thread-safe (допустимо — asyncio single-threaded).
6. **Без этого** — Этап 2 невозможен — нечего интегрировать.

### Этап 2: Интеграция CB в failover loop

1. **Проблема** — Failover loop в `ProcessPromptUseCase.execute()` перебирает все модели, включая заведомо нерабочие.
2. **Действие** — Добавить import `CircuitBreakerManager` и 4 точки вызова: (a) `is_available()` перед вызовом провайдера со `skip` + `continue`, (b) `record_success()` после успеха, (c) `record_failure()` в except-блоках ServerError/Auth/Validation/ProviderError, (d) НЕ считать RateLimitError как CB failure.
3. **Результат** — Провайдер в OPEN пропускается за < 1 мс. Через 60 сек получает пробный запрос (HALF-OPEN). При успехе — полностью восстанавливается.
4. **Зависимости** — Этап 1.
5. **Риски** — Нужно проверить, что skip по CB не нарушает подсчёт `attempts` и логику `all_models_failed`.
6. **Без этого** — CB-модуль существует, но не используется. Провайдеры по-прежнему перебираются.

### Этап 3: Тесты

1. **Проблема** — Нужно подтвердить корректность state machine и интеграции.
2. **Действие** — Создать `tests/unit/test_circuit_breaker.py` с 7 тестами state machine. Добавить 2 теста в `test_process_prompt_use_case.py` для интеграции CB (skip OPEN, восстановление через HALF-OPEN).
3. **Результат** — Покрытие CB >= 90%. Все переходы состояний проверены. Интеграция в failover подтверждена.
4. **Зависимости** — Этапы 1–2.
5. **Риски** — Нужно мокать `time.time()` для тестов recovery_timeout. Нужно вызывать `CircuitBreakerManager.reset()` в setup каждого теста.
6. **Без этого** — Нет защиты от регрессии. Изменения не верифицированы.

---

## Полная версия плана

---

## Этап 1: Модуль CircuitBreakerManager

### Новый файл: `app/application/services/circuit_breaker.py`

```python
"""
Circuit Breaker Manager for AI Providers.

F024: In-memory circuit breaker для мгновенного исключения нерабочих провайдеров.
Паттерн: CLOSED → OPEN (после N ошибок) → HALF-OPEN (через timeout) → CLOSED (при успехе).

Configuration:
    CB_FAILURE_THRESHOLD: Ошибок подряд для CLOSED → OPEN (default: 5)
    CB_RECOVERY_TIMEOUT: Секунд до OPEN → HALF-OPEN (default: 60)
"""

import os
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import ClassVar

from app.utils.logger import get_logger

logger = get_logger(__name__)

CB_FAILURE_THRESHOLD = int(os.getenv("CB_FAILURE_THRESHOLD", "5"))
CB_RECOVERY_TIMEOUT = int(os.getenv("CB_RECOVERY_TIMEOUT", "60"))


class CircuitState(Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


@dataclass
class ProviderCircuit:
    state: CircuitState = CircuitState.CLOSED
    failure_count: int = 0
    last_failure_time: float = 0.0
    success_count_in_half_open: int = 0


class CircuitBreakerManager:
    """In-memory circuit breaker для всех провайдеров.

    Использует class-level dict (паттерн ProviderRegistry).
    Thread-safe в asyncio (single-threaded event loop).
    """

    _circuits: ClassVar[dict[str, ProviderCircuit]] = {}

    @classmethod
    def is_available(cls, provider_name: str) -> bool:
        circuit = cls._circuits.get(provider_name)
        if circuit is None:
            return True  # Новый провайдер — CLOSED по умолчанию

        if circuit.state == CircuitState.CLOSED:
            return True

        if circuit.state == CircuitState.OPEN:
            elapsed = time.time() - circuit.last_failure_time
            if elapsed >= CB_RECOVERY_TIMEOUT:
                old_state = circuit.state
                circuit.state = CircuitState.HALF_OPEN
                circuit.success_count_in_half_open = 0
                logger.warning(
                    "circuit_state_changed",
                    provider=provider_name,
                    old_state=old_state.value,
                    new_state=circuit.state.value,
                    reason="recovery_timeout_elapsed",
                )
                return True  # Разрешить пробный запрос
            return False

        # HALF_OPEN — разрешить (пробный запрос)
        return True

    @classmethod
    def record_success(cls, provider_name: str) -> None:
        circuit = cls._circuits.get(provider_name)
        if circuit is None:
            return

        if circuit.state == CircuitState.HALF_OPEN:
            old_state = circuit.state
            circuit.state = CircuitState.CLOSED
            circuit.failure_count = 0
            logger.warning(
                "circuit_state_changed",
                provider=provider_name,
                old_state=old_state.value,
                new_state=circuit.state.value,
                reason="probe_success",
            )
        elif circuit.state == CircuitState.CLOSED:
            circuit.failure_count = 0  # Сброс счётчика при успехе

    @classmethod
    def record_failure(cls, provider_name: str) -> None:
        circuit = cls._circuits.setdefault(
            provider_name, ProviderCircuit()
        )

        if circuit.state == CircuitState.HALF_OPEN:
            old_state = circuit.state
            circuit.state = CircuitState.OPEN
            circuit.last_failure_time = time.time()
            logger.warning(
                "circuit_state_changed",
                provider=provider_name,
                old_state=old_state.value,
                new_state=circuit.state.value,
                reason="probe_failed",
            )
            return

        # CLOSED: считаем ошибки подряд
        circuit.failure_count += 1
        circuit.last_failure_time = time.time()

        if circuit.failure_count >= CB_FAILURE_THRESHOLD:
            old_state = circuit.state
            circuit.state = CircuitState.OPEN
            logger.warning(
                "circuit_state_changed",
                provider=provider_name,
                old_state=old_state.value,
                new_state=circuit.state.value,
                reason=f"failure_threshold_reached ({circuit.failure_count})",
            )

    @classmethod
    def get_all_statuses(cls) -> dict[str, str]:
        return {
            name: circuit.state.value
            for name, circuit in cls._circuits.items()
        }

    @classmethod
    def reset(cls) -> None:
        """Сброс всех circuit breakers. Для тестов."""
        cls._circuits.clear()
```

### Обоснование решений

| Решение | Альтернатива | Почему выбрано |
|---------|-------------|----------------|
| Classmethods + class dict | Инстанс в DI | Соответствует паттерну ProviderRegistry, не требует изменений wiring |
| `time.time()` для таймеров | `asyncio.get_event_loop().time()` | Проще, мокается стандартно |
| `reset()` для тестов | Фикстуры с monkeypatch | Явный и простой, аналогично ProviderRegistry |
| `warning` для переходов | `info` / `debug` | Достаточно видимо в prod, не шумно |

---

## Этап 2: Интеграция CB в failover loop

### Файл: `app/application/use_cases/process_prompt.py`

**Шаг 2a**: Добавить import (строка ~35, рядом с error_classifier):

```python
from app.application.services.circuit_breaker import CircuitBreakerManager
```

**Шаг 2b**: Добавить проверку CB в начале цикла (строка 205, внутри `for model in candidate_models:`):

```python
        for model in candidate_models:
            # F024: Circuit breaker — пропуск провайдера в OPEN
            if not CircuitBreakerManager.is_available(model.provider):
                logger.debug(
                    "circuit_open_skip",
                    model=model.name,
                    provider=model.provider,
                )
                continue

            attempts += 1
            # ... остальной код без изменений
```

**Важно**: `continue` идёт ДО `attempts += 1` — пропущенные по CB провайдеры не считаются попытками.

**Шаг 2c**: Запись успеха (строка ~218, после `successful_model = model`):

```python
                successful_model = model

                # F024: Circuit breaker — запись успеха
                CircuitBreakerManager.record_success(model.provider)

                break
```

**Шаг 2d**: Запись failure в except-блоках.

В except #2 (строки 231-240, ServerError/Auth/Validation/ProviderError):
```python
            except (ServerError, TimeoutError, AuthenticationError,
                    ValidationError, ProviderError) as e:
                # F024: Circuit breaker — запись ошибки
                CircuitBreakerManager.record_failure(model.provider)

                await self._handle_transient_error(model, e, start_time)
                last_error_message = sanitize_error_message(e)
```

В except #3 (строки 242-249, generic Exception):
```python
            except Exception as e:
                classified = classify_error(e)
                if isinstance(classified, RateLimitError):
                    await self._handle_rate_limit(model, classified)
                    # F024: RateLimitError НЕ считается failure для CB
                else:
                    # F024: Circuit breaker — запись ошибки
                    CircuitBreakerManager.record_failure(model.provider)
                    await self._handle_transient_error(model, classified, start_time)
                last_error_message = sanitize_error_message(e)
```

В except #1 (строки 226-229, RateLimitError):
```python
            except RateLimitError as e:
                await self._handle_rate_limit(model, e)
                # F024: RateLimitError НЕ считается failure для CB (временное состояние)
                last_error_message = sanitize_error_message(e)
```

**Шаг 2e**: Логирование при all_models_failed (строка ~257):

```python
        if successful_model is None:
            # F024: Добавить статусы CB в лог all_models_failed
            cb_statuses = CircuitBreakerManager.get_all_statuses()
            logger.error(
                "all_models_failed",
                attempts=attempts,
                last_error=last_error_message,
                circuit_breaker_statuses=cb_statuses,
            )
```

### Путь данных после интеграции

```
for model in candidate_models:
  │
  ├─ CB.is_available(model.provider)?
  │   └─ False → debug("circuit_open_skip") → continue (skip)
  │   └─ True ↓
  │
  ├─ generate_with_retry()
  │   ├─ success → CB.record_success() → break
  │   ├─ RateLimitError → _handle_rate_limit() (CB НЕ записывает failure)
  │   ├─ Server/Auth/Validation → CB.record_failure() → _handle_transient_error()
  │   └─ Exception → classify → CB.record_failure() (если не RateLimit)
  │
  └─ all exhausted → all_models_failed (с CB statuses в логе)
```

---

## Этап 3: Тесты

### Новый файл: `tests/unit/test_circuit_breaker.py`

```python
"""Tests for F024: Circuit Breaker Manager."""

import os
import time
from unittest.mock import patch

import pytest

from app.application.services.circuit_breaker import (
    CB_FAILURE_THRESHOLD,
    CB_RECOVERY_TIMEOUT,
    CircuitBreakerManager,
    CircuitState,
)


@pytest.mark.unit
class TestCircuitBreakerManager:
    """F024: Circuit breaker state machine tests."""

    def setup_method(self):
        CircuitBreakerManager.reset()

    def test_new_provider_is_available(self):
        """F024: Unknown provider defaults to CLOSED (available)."""
        assert CircuitBreakerManager.is_available("NewProvider") is True

    def test_closed_after_single_failure(self):
        """F024: Single failure doesn't open circuit."""
        CircuitBreakerManager.record_failure("Groq")
        assert CircuitBreakerManager.is_available("Groq") is True

    def test_opens_after_threshold_failures(self):
        """F024: Circuit opens after CB_FAILURE_THRESHOLD consecutive failures."""
        for _ in range(CB_FAILURE_THRESHOLD):
            CircuitBreakerManager.record_failure("Groq")
        assert CircuitBreakerManager.is_available("Groq") is False

    def test_success_resets_failure_count(self):
        """F024: Success in CLOSED resets failure counter."""
        for _ in range(CB_FAILURE_THRESHOLD - 1):
            CircuitBreakerManager.record_failure("Groq")
        CircuitBreakerManager.record_success("Groq")
        # Одна ошибка после reset — не открывает
        CircuitBreakerManager.record_failure("Groq")
        assert CircuitBreakerManager.is_available("Groq") is True

    @patch("app.application.services.circuit_breaker.time.time")
    def test_half_open_after_recovery_timeout(self, mock_time):
        """F024: OPEN → HALF-OPEN after recovery_timeout seconds."""
        mock_time.return_value = 1000.0
        for _ in range(CB_FAILURE_THRESHOLD):
            CircuitBreakerManager.record_failure("Groq")
        assert CircuitBreakerManager.is_available("Groq") is False

        mock_time.return_value = 1000.0 + CB_RECOVERY_TIMEOUT + 1
        assert CircuitBreakerManager.is_available("Groq") is True
        statuses = CircuitBreakerManager.get_all_statuses()
        assert statuses["Groq"] == "half_open"

    @patch("app.application.services.circuit_breaker.time.time")
    def test_closes_after_success_in_half_open(self, mock_time):
        """F024: HALF-OPEN → CLOSED after successful probe."""
        mock_time.return_value = 1000.0
        for _ in range(CB_FAILURE_THRESHOLD):
            CircuitBreakerManager.record_failure("Groq")
        mock_time.return_value = 1000.0 + CB_RECOVERY_TIMEOUT + 1
        CircuitBreakerManager.is_available("Groq")  # → HALF-OPEN

        CircuitBreakerManager.record_success("Groq")
        assert CircuitBreakerManager.get_all_statuses()["Groq"] == "closed"

    @patch("app.application.services.circuit_breaker.time.time")
    def test_reopens_after_failure_in_half_open(self, mock_time):
        """F024: HALF-OPEN → OPEN after failed probe."""
        mock_time.return_value = 1000.0
        for _ in range(CB_FAILURE_THRESHOLD):
            CircuitBreakerManager.record_failure("Groq")
        mock_time.return_value = 1000.0 + CB_RECOVERY_TIMEOUT + 1
        CircuitBreakerManager.is_available("Groq")  # → HALF-OPEN

        CircuitBreakerManager.record_failure("Groq")
        assert CircuitBreakerManager.is_available("Groq") is False
        assert CircuitBreakerManager.get_all_statuses()["Groq"] == "open"

    def test_get_all_statuses_empty(self):
        """F024: Empty statuses for fresh manager."""
        assert CircuitBreakerManager.get_all_statuses() == {}

    def test_get_all_statuses_multiple_providers(self):
        """F024: Statuses reflect each provider independently."""
        for _ in range(CB_FAILURE_THRESHOLD):
            CircuitBreakerManager.record_failure("DeadProvider")
        CircuitBreakerManager.record_failure("AliveProvider")

        statuses = CircuitBreakerManager.get_all_statuses()
        assert statuses["DeadProvider"] == "open"
        assert statuses["AliveProvider"] == "closed"
```

### Модификация: `tests/unit/test_process_prompt_use_case.py`

Добавить класс `TestF024CircuitBreaker` (в конец файла):

```python
@pytest.mark.unit
class TestF024CircuitBreaker:
    """F024: Circuit breaker integration in failover loop."""

    def setup_method(self):
        CircuitBreakerManager.reset()

    @patch.dict(os.environ, {"GROQ_API_KEY": "key1"})
    @patch("app.application.use_cases.process_prompt.ProviderRegistry")
    async def test_open_circuit_skips_provider(
        self, mock_registry, mock_data_api_client
    ):
        """F024: Provider with OPEN circuit is skipped in failover."""
        # Открыть CB для Provider1
        for _ in range(CB_FAILURE_THRESHOLD):
            CircuitBreakerManager.record_failure("Provider1")

        # Настроить 2 модели: Provider1 (OPEN) и Provider2 (CLOSED)
        mock_data_api_client.get_all_models.return_value = [
            AIModelInfo(id=1, name="M1", provider="Provider1", ...),
            AIModelInfo(id=2, name="M2", provider="Provider2", ...),
        ]
        mock_provider2 = AsyncMock()
        mock_provider2.generate.return_value = "response"
        mock_registry.get_provider.return_value = mock_provider2

        use_case = ProcessPromptUseCase(mock_data_api_client)
        response = await use_case.execute(request)

        assert response.success is True
        # Provider1 не вызывался (OPEN)
        # Provider2 вызвался и успешно ответил

    @patch.dict(os.environ, {"GROQ_API_KEY": "key1"})
    @patch("app.application.use_cases.process_prompt.ProviderRegistry")
    async def test_success_records_to_circuit_breaker(
        self, mock_registry, mock_data_api_client
    ):
        """F024: Successful generation records success in CB."""
        mock_provider = AsyncMock()
        mock_provider.generate.return_value = "response"
        mock_registry.get_provider.return_value = mock_provider
        # ... setup models ...

        use_case = ProcessPromptUseCase(mock_data_api_client)
        await use_case.execute(request)

        statuses = CircuitBreakerManager.get_all_statuses()
        # Провайдер должен быть в CLOSED (failure_count = 0)
```

### Запуск тестов

```bash
docker compose exec free-ai-selector-business-api pytest tests/unit/test_circuit_breaker.py -v
docker compose exec free-ai-selector-business-api pytest tests/unit/test_process_prompt_use_case.py -v -k "F024"
docker compose exec free-ai-selector-business-api pytest tests/ -v  # Все тесты
```

---

## Сводка изменений

### Новые компоненты

| Файл | Описание |
|------|----------|
| `app/application/services/circuit_breaker.py` | CircuitBreakerManager, CircuitState, ProviderCircuit |
| `tests/unit/test_circuit_breaker.py` | 9 unit-тестов state machine |

### Модификации существующего кода

| Файл | Строки | Тип | Описание |
|------|--------|-----|----------|
| `app/application/use_cases/process_prompt.py` | ~35 | add | Import CircuitBreakerManager |
| `app/application/use_cases/process_prompt.py` | 205-206 | add | `is_available()` check + continue |
| `app/application/use_cases/process_prompt.py` | ~218 | add | `record_success()` после успеха |
| `app/application/use_cases/process_prompt.py` | 231-240 | add | `record_failure()` в except блоках |
| `app/application/use_cases/process_prompt.py` | ~257 | modify | CB statuses в лог `all_models_failed` |
| `tests/unit/test_process_prompt_use_case.py` | EOF | add | Класс TestF024CircuitBreaker (2 теста) |

### Новые зависимости

Нет.

### Breaking changes

Нет. HTTP-контракт `/api/v1/prompts/process` не меняется.

---

## Влияние на существующие тесты

| Файл тестов | Тестов | Сломается? | Причина |
|-------------|--------|------------|---------|
| `test_error_classifier.py` | 20+ | Нет | error_classifier.py не изменяется |
| `test_retry_service.py` | 11+ | Нет | retry_service.py не изменяется |
| `test_process_prompt_use_case.py` | 22+ | Возможно | CB singleton может повлиять — нужен `reset()` в conftest |

**Митигация**: добавить в `conftest.py`:
```python
@pytest.fixture(autouse=True)
def reset_circuit_breaker():
    from app.application.services.circuit_breaker import CircuitBreakerManager
    CircuitBreakerManager.reset()
    yield
    CircuitBreakerManager.reset()
```

---

## План интеграции

| # | Шаг | Файл | Зависимости |
|---|------|------|-------------|
| 1 | Создать circuit_breaker.py | `app/application/services/circuit_breaker.py` | — |
| 2 | Создать test_circuit_breaker.py | `tests/unit/test_circuit_breaker.py` | Шаг 1 |
| 3 | Запустить тесты CB | — | Шаг 2 |
| 4 | Добавить import CB в process_prompt | `process_prompt.py:~35` | Шаг 1 |
| 5 | Добавить is_available check | `process_prompt.py:205-206` | Шаг 4 |
| 6 | Добавить record_success | `process_prompt.py:~218` | Шаг 4 |
| 7 | Добавить record_failure в except-блоки | `process_prompt.py:231-249` | Шаг 4 |
| 8 | Добавить CB statuses в all_models_failed | `process_prompt.py:~257` | Шаг 4 |
| 9 | Добавить reset fixture в conftest | `tests/conftest.py` | Шаг 1 |
| 10 | Добавить интеграционные тесты | `test_process_prompt_use_case.py` | Шаги 4-8 |
| 11 | Запустить все тесты | — | Шаги 1-10 |

---

## Риски и митигация

| Риск | Вероятность | Митигация |
|------|-------------|-----------|
| CB singleton влияет на существующие тесты | Med | `autouse=True` fixture с `reset()` в conftest |
| Все провайдеры в OPEN → 500 без попыток | Low | recovery_timeout=60 сек, логирование `all_circuits_open` |
| Skip по CB ломает подсчёт attempts | Low | `continue` перед `attempts += 1` — attempts считает только реальные попытки |
| Поле `model.provider` не соответствует имени | Low | Подтверждено research: `model.provider` = строка, e.g. "Groq" |
