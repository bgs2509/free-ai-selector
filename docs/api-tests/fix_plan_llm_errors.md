# План исправления ошибок LLM API

> На основе анализа `llm_api_error_analysis_2026_02_25.md`
> Порядок: от простых к сложным. Каждый этап самодостаточен.

---

## Содержание

1. [Этап 1: Расширить classify_error для HTTP 402 и 404](#этап-1-расширить-classify_error-для-http-402-и-404)
2. [Этап 2: Не оборачивать HTTPStatusError в generic ProviderError](#этап-2-не-оборачивать-httpstatuserror-в-generic-providererror)
3. [Этап 3: Добавить payload budget (защита от HTTP 422)](#этап-3-добавить-payload-budget-защита-от-http-422)
4. [Этап 4: Длительный cooldown для постоянных ошибок (401/402/403/404)](#этап-4-длительный-cooldown-для-постоянных-ошибок-401402403404)
5. [Этап 5: Exponential backoff в retry-сервисе](#этап-5-exponential-backoff-в-retry-сервисе)
6. [Этап 6: Per-request telemetry в прогоне](#этап-6-per-request-telemetry-в-прогоне)
7. [Этап 7: Circuit breaker для провайдеров](#этап-7-circuit-breaker-для-провайдеров)
8. [Этап 8: Адаптивное снижение concurrency в массовом прогоне](#этап-8-адаптивное-снижение-concurrency-в-массовом-прогоне)

---

## Краткая версия

### Этап 1: Расширить classify_error для HTTP 402 и 404

1. **Проблема** — HTTP 402 и 404 от провайдеров попадают в generic `ProviderError`, вместо конкретного типа. Система не знает, что это постоянные ошибки.
2. **Действие** — Добавить ветки `402 → AuthenticationError` и `404 → ValidationError` в функцию `classify_error()` в файле `error_classifier.py`.
3. **Результат** — Ошибки 402/404 правильно классифицируются, не ретраятся, и позволяют failover-циклу быстрее перейти к следующему провайдеру.
4. **Зависимости** — Нет.
5. **Риски** — Минимальные. Может потребоваться обновить тесты на классификатор.
6. **Без этого** — Каждый запрос тратит время на retry мёртвых провайдеров (DeepSeek 402, Novita 404, Fireworks 404 и т.д.).

### Этап 2: Не оборачивать HTTPStatusError в generic ProviderError

1. **Проблема** — `OpenAICompatibleProvider.generate()` ловит `httpx.HTTPError` и заворачивает в `ProviderError`, теряя HTTP-код. После этого `classify_error()` видит `ProviderError` и возвращает его as-is.
2. **Действие** — В `base.py` пробрасывать `httpx.HTTPStatusError` напрямую (без обёртки), а generic `httpx.HTTPError` оборачивать в `ProviderError`.
3. **Результат** — `classify_error()` получает оригинальный `httpx.HTTPStatusError` и корректно классифицирует по HTTP-коду. Этап 1 начинает работать.
4. **Зависимости** — Этап 1 (иначе 402/404 всё равно не классифицируются).
5. **Риски** — Cloudflare использует свой `generate()` и не затронут. Нужно проверить, что `retry_service` и `process_prompt` корректно ловят `httpx.HTTPStatusError`.
6. **Без этого** — Этап 1 не имеет эффекта для провайдеров на `OpenAICompatibleProvider` (12 из 14).

### Этап 3: Добавить payload budget (защита от HTTP 422)

1. **Проблема** — Payload ≥ 7000 символов вызывает 100% ошибок HTTP 422. Pydantic-схема разрешает до 10 000, но провайдеры не принимают такие длины.
2. **Действие** — Добавить truncation prompt до 6500 символов в `ProcessPromptUseCase.execute()` перед отправкой провайдеру.
3. **Результат** — HTTP 422 от провайдеров устраняется полностью (139 ошибок в прогоне).
4. **Зависимости** — Нет.
5. **Риски** — Обрезка длинного промпта может потерять контекст. Нужно обрезать разумно (по границе слова/предложения).
6. **Без этого** — Все запросы с длинным payload (batch_004_data_structures) гарантированно падают.

### Этап 4: Длительный cooldown для постоянных ошибок (401/402/403/404)

1. **Проблема** — Провайдеры с невалидными ключами (401/403) или исчерпанным лимитом (402) перебираются в каждом запросе, хотя заведомо нерабочие.
2. **Действие** — В `_handle_transient_error()` добавить проверку: если ошибка `AuthenticationError` или `ValidationError` с 404, вызывать `set_availability(model_id, cooldown=86400)` (24ч).
3. **Результат** — Мёртвые провайдеры автоматически исключаются на 24 часа. Латентность запросов снижается (не тратим 4.5 сек на перебор 8 нерабочих).
4. **Зависимости** — Этапы 1–2 (чтобы 402/404 правильно классифицировались).
5. **Риски** — Если ключ обновили, провайдер будет недоступен до истечения cooldown. Можно добавить ручной reset.
6. **Без этого** — Каждый запрос перебирает 8 заведомо мёртвых провайдеров (14 526 бесполезных вызовов Scaleway за 48ч).

### Этап 5: Exponential backoff в retry-сервисе

1. **Проблема** — Фиксированная задержка 10 сек между ретраями. При 5xx от перегруженного провайдера это недостаточно и создаёт дополнительную нагрузку.
2. **Действие** — Заменить `asyncio.sleep(delay_seconds)` на `asyncio.sleep(base_delay * 2^attempt + jitter)` с максимальным кэпом.
3. **Результат** — Перегруженные провайдеры получают время на восстановление. Меньше бесполезных retry.
4. **Зависимости** — Нет.
5. **Риски** — Увеличивается максимальное время ожидания на один провайдер (до ~5 мин при max_retries=10). Нужно снизить max_retries до 3–5.
6. **Без этого** — 10 retry × 10 сек = 100 сек ожидания на провайдер, все с одинаковым интервалом (нет адаптации).

### Этап 6: Per-request telemetry в прогоне

1. **Проблема** — В `results.jsonl` нет model_id, provider, duration_ms, http_status. Невозможно диагностировать ошибки без анализа prod-логов.
2. **Действие** — Расширить формат записи в прогоне: добавить поля `model_name`, `provider`, `duration_ms`, `attempts`, `http_status`, `fallback_used`.
3. **Результат** — Полная диагностика из одного файла без SSH на prod. Можно строить графики и автоматические алерты.
4. **Зависимости** — Нет. Но полезнее после этапов 1–2 (телеметрия будет точнее).
5. **Риски** — Увеличение размера `results.jsonl`. Минимальный риск.
6. **Без этого** — Каждая диагностика требует SSH + парсинг docker logs. Невозможно автоматизировать мониторинг.

### Этап 7: Circuit breaker для провайдеров

1. **Проблема** — Нет механизма временной изоляции провайдера после серии ошибок. Каждый запрос пробует все провайдеры заново.
2. **Действие** — Реализовать in-memory circuit breaker с тремя состояниями: CLOSED → OPEN (после N ошибок подряд) → HALF-OPEN (через timeout, 1 пробный запрос) → CLOSED.
3. **Результат** — Провайдеры с серийными ошибками автоматически исключаются без обращения к БД. Быстрый failover.
4. **Зависимости** — Нет. Но логически после этапов 1–2 (правильная классификация ошибок делает CB точнее).
5. **Риски** — In-memory state не шарится между воркерами (если несколько uvicorn workers). Для одного воркера — не проблема.
6. **Без этого** — Даже после этапа 4 (cooldown в БД) есть задержка: нужен HTTP-запрос к Data API чтобы узнать доступность. CB работает мгновенно.

### Этап 8: Адаптивное снижение concurrency в массовом прогоне

1. **Проблема** — Массовый прогон (3686 запросов) не адаптирует скорость отправки. Error rate растёт с 5% до 100% — прогон не замедляется.
2. **Действие** — В скрипте массового прогона: мониторить error rate за скользящее окно (50 запросов), при > 50% снижать concurrency и добавлять паузу, при < 20% восстанавливать.
3. **Результат** — Прогон замедляется вместо того чтобы падать. Вместо 66% ошибок — ожидаемо < 20%.
4. **Зависимости** — Этапы 1–5 (чтобы снизить базовый уровень ошибок). Без них адаптивность не спасёт от 8 мёртвых провайдеров.
5. **Риски** — Прогон будет длиться дольше. Нужна эвристика для определения оптимальных порогов.
6. **Без этого** — Любой массовый прогон с > 1000 запросов приведёт к каскадному отказу.

---

## Полная версия

---

## Этап 1: Расширить classify_error для HTTP 402 и 404

**Сложность**: Низкая (< 30 мин)
**Файлы**: 1 файл + тесты

### Текущее поведение

Файл `error_classifier.py:31` — функция `classify_error()`:

```python
# Строки 56-76: обработка httpx.HTTPStatusError
if status_code == 429:
    return RateLimitError(...)
elif status_code >= 500:
    # Специальная проверка: 500 + "429" в body → RateLimitError
    if "429" in response_text:
        return RateLimitError(...)
    return ServerError(...)
elif status_code in (401, 403):
    return AuthenticationError(...)
elif status_code in (400, 422):
    return ValidationError(...)
# Всё остальное (402, 404, 405, 408, ...) → generic ProviderError
return ProviderError(error_message, original_exception=exception)
```

HTTP 402 (DeepSeek, HuggingFace, Hyperbolic) и 404 (Fireworks, Novita, OpenRouter, Cerebras) проваливаются в generic `ProviderError`.

### Изменения

**Файл**: `services/free-ai-selector-business-api/app/application/services/error_classifier.py`

Добавить перед финальным `return ProviderError(...)`:

```python
elif status_code == 402:
    return AuthenticationError(
        f"Payment required (free tier exhausted): {error_message}",
        original_exception=exception,
    )
elif status_code == 404:
    return ValidationError(
        f"Endpoint or model not found: {error_message}",
        original_exception=exception,
    )
```

### Проверка

```bash
docker compose exec free-ai-selector-business-api \
  pytest tests/unit/test_error_classifier.py -v
```

Добавить тест-кейсы:

```python
def test_402_classified_as_authentication_error(self):
    response = MagicMock(status_code=402, headers={}, text="Payment Required")
    request = MagicMock()
    exc = httpx.HTTPStatusError("error", request=request, response=response)
    result = classify_error(exc)
    assert isinstance(result, AuthenticationError)
    assert "Payment required" in result.message

def test_404_classified_as_validation_error(self):
    response = MagicMock(status_code=404, headers={}, text="Not Found")
    request = MagicMock()
    exc = httpx.HTTPStatusError("error", request=request, response=response)
    result = classify_error(exc)
    assert isinstance(result, ValidationError)
    assert "not found" in result.message.lower()
```

---

## Этап 2: Не оборачивать HTTPStatusError в generic ProviderError

**Сложность**: Низкая (< 30 мин)
**Файлы**: 1 файл + тесты

### Текущее поведение

Файл `base.py:174` — метод `OpenAICompatibleProvider.generate()`:

```python
async def generate(self, prompt: str, **kwargs) -> str:
    ...
    try:
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(self.api_url, headers=headers, json=payload)
            response.raise_for_status()  # Бросает httpx.HTTPStatusError на 4xx/5xx
            ...
    except httpx.HTTPError as e:
        raise ProviderError(f"{self.PROVIDER_NAME} error: {e}") from e
```

Проблема: `httpx.HTTPStatusError` — подкласс `httpx.HTTPError`. Он ловится общим блоком и оборачивается в `ProviderError`, теряя HTTP status code. Затем `classify_error()` видит уже `ProviderError` и возвращает as-is.

### Изменения

**Файл**: `services/free-ai-selector-business-api/app/infrastructure/ai_providers/base.py`

Заменить блок `except` на два:

```python
    except httpx.HTTPStatusError:
        raise  # Пробросить с оригинальным HTTP-кодом для classify_error()
    except httpx.HTTPError as e:
        raise ProviderError(f"{self.PROVIDER_NAME} error: {e}") from e
```

### Проверка

```bash
# Проверить, что retry_service и process_prompt корректно обрабатывают HTTPStatusError
docker compose exec free-ai-selector-business-api pytest tests/ -v -k "provider or retry or prompt"
```

**Критически важно проверить**: `retry_service.py:29` — функция `retry_with_fixed_delay()` вызывает `classify_error(e)` для любого исключения. `classify_error` уже обрабатывает `httpx.HTTPStatusError` (строка 47). Цепочка: `generate()` бросает `httpx.HTTPStatusError` → `retry_with_fixed_delay` ловит `Exception` → `classify_error()` → правильный тип.

Аналогично в `process_prompt.py:196–219`: fallback loop ловит `ProviderError` и подтипы. Нужно добавить `except httpx.HTTPStatusError as e:` перед `except Exception as e:`, или пусть `Exception` обрабатывает через `classify_error()`.

Рекомендация: в `process_prompt.py` добавить в fallback loop:

```python
except httpx.HTTPStatusError as e:
    classified = classify_error(e)
    if isinstance(classified, RateLimitError):
        await self._handle_rate_limit(model, classified)
    else:
        await self._handle_transient_error(model, classified, start_time)
```

---

## Этап 3: Добавить payload budget (защита от HTTP 422)

**Сложность**: Низкая (< 30 мин)
**Файлы**: 1–2 файла

### Текущее поведение

Файл `schemas.py:16` — `ProcessPromptRequest.prompt` допускает до 10 000 символов.
Файл `base.py:126` — `_build_payload()` передаёт prompt as-is в `messages`.
Провайдеры отклоняют payload ≥ 7000 символов с HTTP 422.

### Изменения

**Вариант A** (простой): обрезать в `_build_payload()`.

**Файл**: `services/free-ai-selector-business-api/app/infrastructure/ai_providers/base.py`

В метод `_build_payload()` (строка 126) добавить перед формированием `messages`:

```python
MAX_PROMPT_CHARS = int(os.getenv("MAX_PROMPT_CHARS", "6000"))

def _build_payload(self, prompt: str, **kwargs) -> dict:
    # Защита от слишком длинного payload
    if len(prompt) > MAX_PROMPT_CHARS:
        prompt = prompt[:MAX_PROMPT_CHARS]

    messages = [{"role": "user", "content": prompt}]
    ...
```

**Вариант B** (полнее): обрезать в `ProcessPromptUseCase.execute()` с логированием.

**Файл**: `services/free-ai-selector-business-api/app/application/use_cases/process_prompt.py`

В начале метода `execute()` (после строки 78):

```python
MAX_PROMPT_CHARS = int(os.getenv("MAX_PROMPT_CHARS", "6000"))

if len(request.prompt) > MAX_PROMPT_CHARS:
    logger.warning(
        "prompt_truncated",
        original_length=len(request.prompt),
        max_length=MAX_PROMPT_CHARS,
    )
    request = PromptRequest(
        prompt=request.prompt[:MAX_PROMPT_CHARS],
        model_id=request.model_id,
        user_id=request.user_id,
        system_prompt=request.system_prompt,
        response_format=request.response_format,
    )
```

Рекомендую **вариант B** — видно в логах, когда происходит обрезка.

### Проверка

```bash
# Тест: отправить prompt длиной 8000 символов
curl -s -w "\n%{http_code}" \
  -X POST http://localhost:8000/free-ai-selector/api/v1/prompts/process \
  -H "Content-Type: application/json" \
  -d "{\"prompt\": \"$(python3 -c "print('x' * 8000)")\"}"
# Ожидание: 200 (prompt обрезан), не 422
```

---

## Этап 4: Длительный cooldown для постоянных ошибок (401/402/403/404)

**Сложность**: Средняя (1–2 ч)
**Файлы**: 1 файл + тесты

### Текущее поведение

Файл `process_prompt.py:438` — `_handle_transient_error()`:

```python
async def _handle_transient_error(self, model, error, start_time):
    ...
    await self.data_api_client.increment_failure(model.id, response_time)
```

Вызывает `increment_failure()` для ВСЕХ non-rate-limit ошибок. Модель остаётся доступной (available), просто снижается `reliability_score`. Следующий запрос опять попробует мёртвый провайдер.

### Изменения

**Файл**: `services/free-ai-selector-business-api/app/application/use_cases/process_prompt.py`

Добавить константу:

```python
PERMANENT_ERROR_COOLDOWN = int(os.getenv("PERMANENT_ERROR_COOLDOWN", "86400"))  # 24ч
```

Изменить `_handle_transient_error()`:

```python
async def _handle_transient_error(self, model, error, start_time):
    response_time = time.time() - start_time

    # Постоянные ошибки — длительный cooldown
    if isinstance(error, (AuthenticationError, ValidationError)):
        logger.warning(
            "permanent_error_cooldown",
            model_id=model.id,
            model_name=model.name,
            error_type=type(error).__name__,
            cooldown_seconds=PERMANENT_ERROR_COOLDOWN,
        )
        try:
            await self.data_api_client.set_availability(
                model.id, PERMANENT_ERROR_COOLDOWN
            )
        except Exception as e:
            logger.warning("failed_to_set_cooldown", error=str(e))

    # Всегда фиксируем failure (снижение reliability_score)
    try:
        await self.data_api_client.increment_failure(model.id, response_time)
    except Exception as e:
        logger.warning("failed_to_increment_failure", error=str(e))
```

### Проверка

```bash
# 1. Убедиться, что провайдер с 401 помечается unavailable
docker compose exec free-ai-selector-business-api \
  pytest tests/unit/test_process_prompt_use_case.py -v -k "auth_error"

# 2. Проверить в Data API, что set_availability вызван с 86400
# (mock data_api_client, проверить вызов)
```

---

## Этап 5: Exponential backoff в retry-сервисе

**Сложность**: Средняя (1–2 ч)
**Файлы**: 1 файл + тесты

### Текущее поведение

Файл `retry_service.py:29`:

```python
MAX_RETRIES = int(os.getenv("MAX_RETRIES", "10"))
RETRY_DELAY_SECONDS = int(os.getenv("RETRY_DELAY_SECONDS", "10"))

async def retry_with_fixed_delay(func, max_retries=MAX_RETRIES,
                                  delay_seconds=RETRY_DELAY_SECONDS, ...):
    for attempt in range(1, max_retries + 1):
        try:
            return await func()
        except Exception as e:
            ...
            if is_retryable(classified):
                await asyncio.sleep(delay_seconds)  # Фиксированные 10 сек
            else:
                raise classified
    raise last_error
```

10 попыток × 10 сек = 100 сек максимум на один провайдер.

### Изменения

**Файл**: `services/free-ai-selector-business-api/app/application/services/retry_service.py`

```python
import random

MAX_RETRIES = int(os.getenv("MAX_RETRIES", "3"))           # снизить с 10 до 3
BASE_RETRY_DELAY = float(os.getenv("BASE_RETRY_DELAY", "2.0"))  # базовая задержка 2 сек
MAX_RETRY_DELAY = float(os.getenv("MAX_RETRY_DELAY", "30.0"))   # потолок 30 сек


async def retry_with_exponential_backoff(
    func, max_retries=MAX_RETRIES,
    base_delay=BASE_RETRY_DELAY,
    max_delay=MAX_RETRY_DELAY,
    provider_name="unknown",
    model_name="unknown",
):
    last_error = None
    for attempt in range(1, max_retries + 1):
        try:
            return await func()
        except Exception as e:
            classified = classify_error(e)
            last_error = classified

            if not is_retryable(classified):
                logger.warning("non_retryable_error", ...)
                raise classified

            # Exponential backoff с jitter
            delay = min(base_delay * (2 ** (attempt - 1)), max_delay)
            jitter = random.uniform(0, delay * 0.1)
            actual_delay = delay + jitter

            logger.warning(
                "retryable_error",
                attempt=attempt,
                max_retries=max_retries,
                next_delay_seconds=round(actual_delay, 1),
                ...
            )
            await asyncio.sleep(actual_delay)

    logger.error("all_retries_exhausted", ...)
    raise last_error
```

Задержки при `base_delay=2, max_retries=3`: 2с → 4с → 8с (итого ~14 сек на провайдер, вместо 100).

### Обновить вызов

**Файл**: `process_prompt.py:343` — `_generate_with_retry()`:

Заменить `retry_with_fixed_delay` на `retry_with_exponential_backoff`.

### Обратная совместимость

Оставить `retry_with_fixed_delay` как deprecated alias, если он используется в тестах. Или обновить тесты.

### Проверка

```bash
docker compose exec free-ai-selector-business-api \
  pytest tests/unit/test_retry_service.py -v
```

---

## Этап 6: Per-request telemetry в прогоне

**Сложность**: Средняя (2–3 ч)
**Файлы**: скрипт прогона (вне business-api)

### Текущее поведение

Прогон записывает в `results.jsonl`:
- `index`, `batch`, `question`, `result` (classification), `error`
- Нет: `model`, `provider`, `duration_ms`, `http_status`, `attempts`

### Изменения

Расширить `ProcessPromptResponse` (или endpoint) чтобы возвращать metadata:

**Файл**: `services/free-ai-selector-business-api/app/api/v1/schemas.py`

Уже содержит поля `selected_model`, `provider`, `response_time_seconds` в ответе. Эти данные нужно пробрасывать в `results.jsonl` на стороне скрипта прогона.

На стороне скрипта прогона (reclassification pipeline) — сохранять расширенную запись:

```python
record = {
    "index": i,
    "batch": batch_name,
    "status": "ok" if success else "error",
    "http_status": response.status_code,
    "model_name": data.get("selected_model"),
    "provider": data.get("provider"),
    "duration_ms": round(elapsed * 1000, 1),
    "prompt_chars": len(prompt),
    "error": error_text if not success else None,
    "timestamp": datetime.utcnow().isoformat(),
}
```

### Проверка

Запустить мини-прогон (10 запросов) и проверить, что `results.jsonl` содержит все новые поля.

---

## Этап 7: Circuit breaker для провайдеров

**Сложность**: Высокая (3–5 ч)
**Файлы**: 2 новых файла + интеграция в use case

### Архитектура

```
                CLOSED (рабочий)
                  │
         N ошибок подряд
                  ▼
                OPEN (заблокирован)
                  │
         recovery_timeout
                  ▼
              HALF-OPEN (1 пробный)
              ╱          ╲
         успех             ошибка
           ▼                 ▼
        CLOSED             OPEN
```

### Изменения

**Новый файл**: `services/free-ai-selector-business-api/app/application/services/circuit_breaker.py`

```python
import time
from enum import Enum
from dataclasses import dataclass, field


class CircuitState(Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


@dataclass
class ProviderCircuit:
    failure_count: int = 0
    last_failure_time: float = 0.0
    state: CircuitState = CircuitState.CLOSED


class CircuitBreakerManager:
    """In-memory circuit breaker для всех провайдеров."""

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: int = 60,
        success_threshold: int = 2,
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.success_threshold = success_threshold
        self._circuits: dict[str, ProviderCircuit] = {}

    def is_available(self, provider_name: str) -> bool:
        circuit = self._circuits.get(provider_name)
        if circuit is None:
            return True
        if circuit.state == CircuitState.CLOSED:
            return True
        if circuit.state == CircuitState.OPEN:
            if time.time() - circuit.last_failure_time > self.recovery_timeout:
                circuit.state = CircuitState.HALF_OPEN
                return True  # Разрешаем пробный запрос
            return False
        # HALF_OPEN — разрешаем (один пробный запрос)
        return True

    def record_success(self, provider_name: str) -> None:
        circuit = self._circuits.get(provider_name)
        if circuit is None:
            return
        circuit.failure_count = 0
        circuit.state = CircuitState.CLOSED

    def record_failure(self, provider_name: str) -> None:
        circuit = self._circuits.setdefault(provider_name, ProviderCircuit())
        circuit.failure_count += 1
        circuit.last_failure_time = time.time()
        if circuit.failure_count >= self.failure_threshold:
            circuit.state = CircuitState.OPEN


# Синглтон для всего приложения
circuit_breaker = CircuitBreakerManager()
```

### Интеграция

**Файл**: `process_prompt.py` — в fallback loop (строка ~196):

```python
from app.application.services.circuit_breaker import circuit_breaker

# Перед вызовом провайдера:
if not circuit_breaker.is_available(model.provider):
    logger.debug("circuit_open_skip", provider=model.provider)
    continue  # Пропустить этот провайдер

# После успеха:
circuit_breaker.record_success(model.provider)

# После ошибки:
circuit_breaker.record_failure(model.provider)
```

### Проверка

```bash
docker compose exec free-ai-selector-business-api \
  pytest tests/unit/test_circuit_breaker.py -v
```

Тесты:
- `test_closed_after_init` — все провайдеры доступны
- `test_opens_after_threshold` — после 5 ошибок → OPEN
- `test_half_open_after_timeout` — через 60 сек → HALF-OPEN
- `test_closes_after_success` — успех в HALF-OPEN → CLOSED
- `test_reopens_after_failure_in_half_open` — ошибка в HALF-OPEN → OPEN

---

## Этап 8: Адаптивное снижение concurrency в массовом прогоне

**Сложность**: Высокая (3–5 ч)
**Файлы**: скрипт прогона (вне business-api)

### Архитектура

```
                    ┌─────────────────┐
                    │  Error Monitor  │
                    │ (скользящее окно│
                    │   50 запросов)  │
                    └────────┬────────┘
                             │
              ┌──────────────┼──────────────┐
              ▼              ▼              ▼
        error < 20%    20-50%        error > 50%
              │              │              │
       concurrency++   без изменений  concurrency--
       (до max=8)                     (до min=1)
                                      + пауза 5с
```

### Изменения

На стороне скрипта прогона:

```python
import asyncio
from collections import deque


class AdaptiveConcurrency:
    """Адаптивное управление concurrency на основе error rate."""

    def __init__(
        self,
        initial: int = 8,
        min_concurrency: int = 1,
        max_concurrency: int = 8,
        window_size: int = 50,
        high_error_threshold: float = 0.5,
        low_error_threshold: float = 0.2,
        cooldown_seconds: float = 5.0,
    ):
        self.current = initial
        self.min_concurrency = min_concurrency
        self.max_concurrency = max_concurrency
        self.window = deque(maxlen=window_size)
        self.high_threshold = high_error_threshold
        self.low_threshold = low_error_threshold
        self.cooldown = cooldown_seconds
        self._semaphore = asyncio.Semaphore(initial)

    def record(self, success: bool) -> None:
        self.window.append(success)
        if len(self.window) == self.window.maxlen:
            self._adjust()

    @property
    def error_rate(self) -> float:
        if not self.window:
            return 0.0
        return 1.0 - (sum(self.window) / len(self.window))

    def _adjust(self) -> None:
        rate = self.error_rate
        if rate > self.high_threshold and self.current > self.min_concurrency:
            self.current = max(self.min_concurrency, self.current // 2)
            self._semaphore = asyncio.Semaphore(self.current)
        elif rate < self.low_threshold and self.current < self.max_concurrency:
            self.current = min(self.max_concurrency, self.current + 1)
            self._semaphore = asyncio.Semaphore(self.current)

    async def acquire(self) -> None:
        await self._semaphore.acquire()
        if self.error_rate > self.high_threshold:
            await asyncio.sleep(self.cooldown)

    def release(self) -> None:
        self._semaphore.release()
```

Использование в прогоне:

```python
ac = AdaptiveConcurrency(initial=8)

async def process_one(i, prompt):
    await ac.acquire()
    try:
        result = await send_request(prompt)
        ac.record(success=result.status_code == 200)
        return result
    finally:
        ac.release()
```

### Проверка

Запустить тестовый прогон на 200 запросах и сравнить error rate с прогоном без адаптивности:

```bash
# Без адаптивности:
python3 scripts/run_batch.py --requests 200 --concurrency 8
# С адаптивностью:
python3 scripts/run_batch.py --requests 200 --adaptive
```

---

## Сводная таблица

| # | Этап | Сложность | Время | Файлы | Устраняет |
|---|------|-----------|-------|-------|-----------|
| 1 | classify_error: 402 + 404 | Низкая | 30 мин | 1 | P1-1, P1-2 |
| 2 | Не оборачивать HTTPStatusError | Низкая | 30 мин | 1–2 | P2-3 |
| 3 | Payload budget | Низкая | 30 мин | 1 | HTTP 422 (139 ошибок) |
| 4 | Cooldown для постоянных ошибок | Средняя | 1–2 ч | 1 | P0-1 (8 мёртвых провайдеров) |
| 5 | Exponential backoff | Средняя | 1–2 ч | 1 | P2-1 |
| 6 | Per-request telemetry | Средняя | 2–3 ч | скрипт | P1-3 |
| 7 | Circuit breaker | Высокая | 3–5 ч | 2 новых | P0-1 (дополнение к этапу 4) |
| 8 | Адаптивный concurrency | Высокая | 3–5 ч | скрипт | P0-2 (каскадный отказ) |

**Суммарно**: ~12–18 часов работы. Этапы 1–3 (1.5ч) устраняют ~70% проблем.
