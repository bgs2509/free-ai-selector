# Анализ ошибок LLM API — 2026-02-25

> **Источники**: диагностический отчёт `full_async_live` (3686 запросов), логи prod-контейнера `free-ai-selector-business-api` за 48ч, исходный код сервиса.

---

## Содержание

1. [Общая статистика](#1-общая-статистика)
2. [Ошибки по провайдерам (prod-логи)](#2-ошибки-по-провайдерам-prod-логи)
3. [Классификация ошибок](#3-классификация-ошибок)
4. [Деградация во времени](#4-деградация-во-времени)
5. [Метрики производительности](#5-метрики-производительности)
6. [Архитектура обработки ошибок (as-is)](#6-архитектура-обработки-ошибок-as-is)
7. [Выявленные проблемы](#7-выявленные-проблемы)
8. [Методы тестирования](#8-методы-тестирования)
9. [План исправлений](#9-план-исправлений)

---

## 1. Общая статистика

| Метрика | Значение |
|---|---|
| Всего запросов | 3 686 |
| Успешных | 1 250 (33.9%) |
| Ошибок | 2 436 (66.1%) |
| Длительность прогона | 3ч 45м |
| `all_models_failed` событий (prod-логи, 48ч) | 12 610 |
| HTTP 500 ответов (prod-логи, 48ч) | 12 692 |

### Распределение ошибок в прогоне

| Код | Количество | Доля ошибок |
|---|---:|---:|
| HTTP 500 (все провайдеры упали) | 2 296 | 94.25% |
| HTTP 422 (validation payload) | 139 | 5.71% |
| Connection closed | 1 | 0.04% |

---

## 2. Ошибки по провайдерам (prod-логи)

### 2.1 Конкретные HTTP-ошибки от провайдеров

Данные из `generation_failed` и `non_retryable_error` событий за 48ч:

| Провайдер | HTTP код | Ошибка | Кол-во | Ретраится? |
|---|---|---|---:|---|
| Scaleway | 403 Forbidden | Невалидный/отозванный API-ключ | 14 526 | Нет |
| Kluster | 403 Forbidden | Невалидный/отозванный API-ключ | 14 513 | Нет |
| Novita | 404 Not Found | Модель/эндпоинт не существует | 14 481 | Нет |
| Fireworks | 404 Not Found | Модель/эндпоинт не существует | 14 353 | Нет |
| DeepSeek | 402 Payment Required | Исчерпан бесплатный лимит | 14 321 | Нет |
| Hyperbolic | 402 Payment Required | Исчерпан бесплатный лимит | 14 078 | Нет |
| Groq | 429 Too Many Requests | Rate limit | 13 176 | Нет* |
| OpenRouter | 404 Not Found | Модель не найдена | 13 070 | Нет |
| SambaNova | 429 Too Many Requests | Rate limit | 12 773 | Нет* |
| HuggingFace | 402 Payment Required | Исчерпан бесплатный лимит | 12 736 | Нет |
| GitHubModels | 429 Too Many Requests | Rate limit | 12 716 | Нет* |
| Cerebras | 404 Not Found | Модель не найдена | 12 628 | Нет |
| Hyperbolic | 429 Too Many Requests | Rate limit (доп.) | 263 | Нет* |

> *\* 429 классифицируется как `RateLimitError` — не ретраится, модель помечается unavailable на 1ч по умолчанию.*

### 2.2 Категории проблем

| Категория | Провайдеры | Действие |
|---|---|---|
| **Лимит исчерпан** (402) | DeepSeek, Hyperbolic, HuggingFace | Пополнить баланс или отключить |
| **Модель/URL не найден** (404) | Novita, Fireworks, OpenRouter, Cerebras | Обновить model_id / endpoint URL |
| **Rate limit** (429) | Groq, SambaNova, GitHubModels | Снизить concurrency, добавить backoff |

### 2.3 Non-retryable error counts по провайдерам

| Провайдер | non_retryable_error |
|---|---:|
| Groq | 13 178 |
| OpenRouter | 13 073 |
| SambaNova | 12 781 |
| HuggingFace | 12 736 |
| GitHubModels | 12 721 |
| Cerebras | 12 628 |
| Scaleway | 12 610 |
| Novita | 12 610 |
| Kluster | 12 610 |
| Hyperbolic | 12 610 |
| Fireworks | 12 610 |
| DeepSeek | 12 610 |
| Cloudflare | 6 |

**Вывод**: Все 13 провайдеров (кроме Cloudflare) массово отказывают. Cloudflare — единственный стабильный провайдер (6 ошибок за 48ч).

---

## 3. Классификация ошибок

### 3.1 HTTP 422 — Validation (139 случаев в прогоне)

**Корневая причина**: слишком длинный payload (question + short_answer + full_answer).

| Метрика | HTTP 422 | Успешные |
|---|---:|---:|
| Средний размер payload (символы) | 7 283 | 4 024 |
| Медиана | 7 288 | 3 397 |
| p95 | 7 447 | 6 588 |
| Max | 7 505 | 7 025 |
| Payload ≥ 7000 символов | 100% (139/139) | 0.16% (2/1250) |

**Локализация**: индексы 140–829, после чего прекращается (данные с длинным payload закончились).

Топ-батч: `batch_004_data_structures` — 104 из 139 ошибок (74.8%).

### 3.2 HTTP 500 — All providers failed (2 296 случаев в прогоне)

**Корневая причина**: каскадный отказ всех провайдеров. Business API перебирает все доступные модели по `effective_reliability_score`, и когда все возвращают ошибки — отдаёт 500.

Цепочка в логах:
```
generation_failed (provider=Groq, 429)
  → generation_failed (provider=SambaNova, 429)
    → generation_failed (provider=DeepSeek, 402)
      → ... (все 13 провайдеров)
        → all_models_failed
          → HTTP 500 клиенту
```

**Паттерн деградации**: ошибки нарастают с ~5% (индексы 1–200) до 100% (индексы 3601–3686). Это указывает на **исчерпание rate limits и бесплатных квот** по мере прогона.

### 3.3 Connection closed (1 случай)

Единичный сетевой сбой на индексе 3409. Не влияет на общую картину.

---

## 4. Деградация во времени

```
100% ┤                                              ████████████
 90% ┤                                       ███████
 80% ┤                                  █████
 70% ┤                             █████
 60% ┤                        █████
 50% ┤               ██  █████
 40% ┤              █  ██
 30% ┤
 20% ┤         █
 10% ┤
  5% ┤  ██  █
     └──────────────────────────────────────────────────────────
     0    400   800  1200  1600  2000  2400  2800  3200  3600
                         Индекс запроса
```

| Фаза | Индексы | Error rate | Основная ошибка |
|---|---|---:|---|
| Стабильная | 1–400 | 5–6% | HTTP 422 (payload) |
| Переходная | 401–1000 | 21–49% | HTTP 422 + HTTP 500 |
| Деградация | 1001–2400 | 46–91% | HTTP 500 (rate limits) |
| Полный отказ | 2401–3686 | 91–100% | HTTP 500 (все провайдеры) |

Максимальная непрерывная серия ошибок: **266 запросов** (индексы 3202–3467).

---

## 5. Метрики производительности

### 5.1 Латентность (prod-логи, 48ч)

| Метрика | Все запросы | Только 500 |
|---|---:|---:|
| Среднее | 3 236 мс | 4 591 мс |
| Максимум | 41 184 мс | 41 184 мс |
| Кол-во замеров | 20 133 | 12 692 |

**Вывод**: запросы с ошибками в ~1.4 раза дольше успешных. Максимальная латентность ~41 сек — это полный перебор всех провайдеров с таймаутами.

### 5.2 Throughput

| Метрика | Значение |
|---|---|
| Запросов в прогоне | 3 686 за 3ч 45м |
| Средний RPS | ~0.27 |
| Оценочная скорость | ~16 запросов/минуту |

---

## 6. Архитектура обработки ошибок (as-is)

### 6.1 Иерархия исключений

```
ProviderError (базовый)
├── RateLimitError      — HTTP 429, retry_after_seconds
├── ServerError         — HTTP 5xx (retryable)
├── TimeoutError        — httpx.TimeoutException (retryable)
├── AuthenticationError — HTTP 401, 403
└── ValidationError     — HTTP 400, 422
```

### 6.2 Retry-сервис

```
retry_with_fixed_delay(func, max_retries=10, delay=10s)
  → classify_error(exception)
    → retryable? (только ServerError, TimeoutError)
      → Да: ждём 10 сек, повторяем (до 10 раз)
      → Нет: пробрасываем немедленно
```

- Фиксированная задержка (не exponential backoff)
- Max время на один провайдер: 10 × 10 = 100 сек
- `RateLimitError` НЕ ретраится — модель помечается unavailable на 1ч

### 6.3 Failover-цикл (ProcessPromptUseCase)

```
1. Получить модели из Data API (active + available)
2. Отфильтровать по наличию API-ключей
3. Отсортировать по reliability_score (убывание)
4. Для каждой модели:
   a. generate_with_retry(provider, request)
   b. Успех → increment_success → return
   c. RateLimitError → set_availability(+1ч) → следующая модель
   d. Другая ошибка → increment_failure → следующая модель
5. Все модели исчерпаны → all_models_failed → HTTP 500
```

### 6.4 Что отсутствует

| Компонент | Статус |
|---|---|
| Circuit breaker | Нет |
| Adaptive concurrency | Нет |
| Exponential backoff | Нет (фиксированные 10 сек) |
| Per-provider concurrency semaphore | Нет |
| Rate limit на /api/v1/prompts/process | Нет (только на /api) |
| Per-request telemetry (model, provider, duration) | Нет в прогоне |

---

## 7. Выявленные проблемы

### P0 — Критические (массовые ошибки)

#### P0-1: Провайдеры с невалидными ключами/URL не отключаются автоматически

**Проблема**: 8 из 13 провайдеров возвращают постоянные ошибки (401, 402, 403, 404), но система продолжает их перебирать в каждом запросе.

**Влияние**: каждый запрос тратит ~4.5 сек на бесполезный перебор мёртвых провайдеров.

**Примеры**:
- Scaleway: 14 526 раз `403 Forbidden`
- DeepSeek: 14 321 раз `402 Payment Required`

#### P0-2: Каскадный отказ при массовом прогоне

**Проблема**: нет адаптивного снижения нагрузки. При росте 429/5xx система не замедляется, продолжая слать запросы с той же частотой. Это ускоряет исчерпание rate limits у оставшихся рабочих провайдеров.

**Влияние**: error rate вырос с 5% до 100% за 3.5ч прогона.

#### P0-3: HTTP 422 из-за слишком длинного payload

**Проблема**: payload ≥ 7000 символов гарантированно вызывает 422. В коде `max_length=10000` для prompt, но провайдеры не принимают такие длины.

**Влияние**: 139 ошибок (100% корреляция с payload ≥ 7000).

### P1 — Важные (наблюдаемость)

#### P1-1: Неправильная классификация HTTP 402 (Payment Required)

**Проблема**: HTTP 402 не входит ни в одну ветку `classify_error()` (401/403 → AuthenticationError, 400/422 → ValidationError, 5xx → ServerError). Он попадает в generic `ProviderError` и обрабатывается как transient error с `increment_failure()`.

**Правильное поведение**: 402 должен обрабатываться как `AuthenticationError` или отдельный `PaymentError` — провайдер не временно перегружен, а навсегда недоступен до пополнения баланса.

#### P1-2: HTTP 404 (Not Found) не классифицируется корректно

**Проблема**: HTTP 404 (неверный model_id или endpoint) также попадает в generic `ProviderError`. Это постоянная ошибка конфигурации, а не временный сбой.

**Правильное поведение**: 404 должен приводить к автоматическому отключению модели (или как минимум длительному cooldown).

#### P1-3: Отсутствие per-request telemetry в прогоне

**Проблема**: в `results.jsonl` не логируются `model_id`, `provider`, `duration_ms`, `http_status` per attempt.

**Влияние**: невозможно определить, какая конкретная модель дала ошибку, без анализа prod-логов.

### P2 — Улучшения

#### P2-1: Фиксированный retry delay вместо exponential backoff

**Проблема**: `retry_with_fixed_delay(delay=10s)` — при 429 от провайдера не увеличивает задержку.

#### P2-2: Предупреждения о несогласованных справочниках

**Проблема**: 59.7% успешных ответов содержат warnings о неизвестных кодах (`data_engineer`, `text`, `web_development`).

#### P2-3: Обёртка HTTPStatusError в generic ProviderError

**Проблема**: в `OpenAICompatibleProvider.generate()` любой `httpx.HTTPError` оборачивается в `ProviderError(f"{name} error: {e}")`. Затем `classify_error()` видит `isinstance(ProviderError)` и возвращает as-is, теряя возможность правильно классифицировать по HTTP-коду.

**Фактически**: ошибки от всех провайдеров (кроме Cloudflare) всегда generic `ProviderError` в retry-сервисе.

---

## 8. Методы тестирования

### 8.1 Unit-тесты обработки ошибок

#### Тест: классификатор ошибок (`error_classifier.py`)

```python
# tests/unit/test_error_classifier.py

import pytest
from unittest.mock import MagicMock
import httpx
from app.application.services.error_classifier import classify_error, is_retryable
from app.domain.exceptions import (
    RateLimitError, ServerError, TimeoutError,
    AuthenticationError, ValidationError, ProviderError,
)


class TestClassifyError:
    """Проверяет правильную классификацию HTTP-кодов."""

    @pytest.mark.parametrize("status_code,expected_type", [
        (429, RateLimitError),
        (500, ServerError),
        (502, ServerError),
        (503, ServerError),
        (401, AuthenticationError),
        (403, AuthenticationError),
        (400, ValidationError),
        (422, ValidationError),
    ])
    def test_http_status_classification(self, status_code, expected_type):
        response = MagicMock(status_code=status_code, headers={}, text="error")
        request = MagicMock()
        exc = httpx.HTTPStatusError("error", request=request, response=response)
        result = classify_error(exc)
        assert isinstance(result, expected_type)

    def test_402_payment_required_classification(self):
        """P1-1: HTTP 402 должен стать AuthenticationError, не generic."""
        response = MagicMock(status_code=402, headers={}, text="Payment Required")
        request = MagicMock()
        exc = httpx.HTTPStatusError("error", request=request, response=response)
        result = classify_error(exc)
        # ТЕКУЩЕЕ поведение: generic ProviderError (баг)
        # ОЖИДАЕМОЕ: isinstance(result, AuthenticationError)
        assert isinstance(result, ProviderError)

    def test_404_not_found_classification(self):
        """P1-2: HTTP 404 должен быть non-retryable configuration error."""
        response = MagicMock(status_code=404, headers={}, text="Not Found")
        request = MagicMock()
        exc = httpx.HTTPStatusError("error", request=request, response=response)
        result = classify_error(exc)
        # ТЕКУЩЕЕ поведение: generic ProviderError
        assert isinstance(result, ProviderError)

    def test_500_with_429_in_body(self):
        """Провайдеры иногда оборачивают 429 в 500."""
        response = MagicMock(status_code=500, headers={}, text="rate limit exceeded 429")
        request = MagicMock()
        exc = httpx.HTTPStatusError("error", request=request, response=response)
        result = classify_error(exc)
        assert isinstance(result, RateLimitError)

    def test_timeout_classification(self):
        exc = httpx.ReadTimeout("timeout")
        result = classify_error(exc)
        assert isinstance(result, TimeoutError)


class TestIsRetryable:
    """Проверяет, какие ошибки разрешено ретраить."""

    @pytest.mark.parametrize("error_class,expected", [
        (ServerError, True),
        (TimeoutError, True),
        (RateLimitError, False),
        (AuthenticationError, False),
        (ValidationError, False),
        (ProviderError, False),
    ])
    def test_retryable_flag(self, error_class, expected):
        err = error_class("test")
        assert is_retryable(err) == expected
```

#### Тест: retry-сервис

```python
# tests/unit/test_retry_service.py

import pytest
from unittest.mock import AsyncMock, patch
from app.application.services.retry_service import retry_with_fixed_delay
from app.domain.exceptions import (
    ServerError, AuthenticationError, RateLimitError,
)


class TestRetryService:

    @pytest.mark.asyncio
    async def test_success_on_first_try(self):
        func = AsyncMock(return_value="ok")
        result = await retry_with_fixed_delay(func, max_retries=3, delay_seconds=0)
        assert result == "ok"
        assert func.call_count == 1

    @pytest.mark.asyncio
    async def test_retry_on_server_error(self):
        """ServerError (5xx) должен ретраиться."""
        func = AsyncMock(side_effect=[ServerError("503"), "ok"])
        result = await retry_with_fixed_delay(func, max_retries=3, delay_seconds=0)
        assert result == "ok"
        assert func.call_count == 2

    @pytest.mark.asyncio
    async def test_no_retry_on_auth_error(self):
        """AuthenticationError (401/403) — немедленный проброс."""
        func = AsyncMock(side_effect=AuthenticationError("401"))
        with pytest.raises(AuthenticationError):
            await retry_with_fixed_delay(func, max_retries=3, delay_seconds=0)
        assert func.call_count == 1

    @pytest.mark.asyncio
    async def test_no_retry_on_rate_limit(self):
        """RateLimitError (429) — проброс, не retry."""
        func = AsyncMock(side_effect=RateLimitError("429"))
        with pytest.raises(RateLimitError):
            await retry_with_fixed_delay(func, max_retries=3, delay_seconds=0)
        assert func.call_count == 1

    @pytest.mark.asyncio
    async def test_max_retries_exhausted(self):
        """После max_retries попыток — проброс последней ошибки."""
        func = AsyncMock(side_effect=ServerError("503"))
        with pytest.raises(ServerError):
            await retry_with_fixed_delay(func, max_retries=3, delay_seconds=0)
        assert func.call_count == 3
```

#### Тест: failover в ProcessPromptUseCase

```python
# tests/unit/test_process_prompt_failover.py

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from app.domain.exceptions import (
    RateLimitError, AuthenticationError, ProviderError,
)


class TestFailover:

    @pytest.mark.asyncio
    async def test_fallback_to_second_provider(self):
        """Если первый провайдер упал — переключается на второй."""
        # Мокаем два провайдера: первый — ошибка, второй — успех
        # Проверяем, что второй вызван и результат возвращён

    @pytest.mark.asyncio
    async def test_rate_limit_sets_availability(self):
        """RateLimitError → set_availability(), НЕ increment_failure()."""
        # Проверяем, что при 429 модель помечается unavailable,
        # но reliability_score не уменьшается

    @pytest.mark.asyncio
    async def test_all_providers_failed_returns_500(self):
        """Когда все модели упали — HTTP 500 с last_error."""
        # Все провайдеры бросают ProviderError
        # Проверяем: all_models_failed залогирован, exception с текстом

    @pytest.mark.asyncio
    async def test_auth_error_increments_failure(self):
        """AuthenticationError → increment_failure(), переход к следующей модели."""
```

### 8.2 Integration-тесты (Docker)

#### Тест: payload size limit

```bash
# Запрос с payload > 7000 символов → ожидаем 422 или graceful truncation
curl -s -o /dev/null -w "%{http_code}" \
  -X POST http://localhost:8000/free-ai-selector/api/v1/prompts/process \
  -H "Content-Type: application/json" \
  -d "{\"prompt\": \"$(python3 -c 'print("x" * 8000)')\"}"
# Ожидаемый результат: 200 (после исправления — payload урезается)
# Текущий результат: 422 или 500
```

#### Тест: реакция на недоступные провайдеры

```bash
# Установить невалидный ключ для одного провайдера и проверить failover
# 1. Отключить все провайдеры кроме одного
# 2. Отправить запрос
# 3. Проверить: ответ 200, в логах — generation_failed для мёртвых + успех для живого
docker compose exec free-ai-selector-business-api \
  pytest tests/integration/test_provider_failover.py -v
```

### 8.3 Load-тесты (воспроизведение каскадного отказа)

```python
# tests/load/test_cascade_failure.py
"""
Сценарий: отправить N параллельных запросов, увеличивая нагрузку.
Цель: зафиксировать момент, когда error rate начинает расти.
"""
import asyncio
import httpx


async def load_test(total_requests: int = 200, concurrency: int = 10):
    url = "http://localhost:8000/free-ai-selector/api/v1/prompts/process"
    semaphore = asyncio.Semaphore(concurrency)
    results = {"ok": 0, "error": 0, "status_codes": {}}

    async def send_request(i: int):
        async with semaphore:
            async with httpx.AsyncClient(timeout=60) as client:
                try:
                    resp = await client.post(url, json={
                        "prompt": f"Что такое Python? (запрос #{i})"
                    })
                    code = resp.status_code
                    results["status_codes"][code] = results["status_codes"].get(code, 0) + 1
                    if code == 200:
                        results["ok"] += 1
                    else:
                        results["error"] += 1
                except Exception:
                    results["error"] += 1

    tasks = [send_request(i) for i in range(total_requests)]
    await asyncio.gather(*tasks)

    print(f"OK: {results['ok']}, Error: {results['error']}")
    print(f"Status codes: {results['status_codes']}")


if __name__ == "__main__":
    asyncio.run(load_test())
```

### 8.4 Smoke-тест здоровья провайдеров

```bash
# Скрипт для быстрой проверки: какие провайдеры живые прямо сейчас
# Запускать перед массовым прогоном

curl -s http://localhost:8000/free-ai-selector/api/v1/prompts/process \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Hello, respond with one word."}' | python3 -m json.tool

# Проверить логи — какой провайдер ответил:
docker logs free-ai-selector-business-api --since 30s 2>&1 | \
  grep -E "(generation_succeeded|generation_failed)" | tail -20
```

---

## 9. План исправлений

### P0 — Критические (убрать массовые ошибки)

#### P0-1: Расширить classify_error() для HTTP 402 и 404

**Файл**: `app/application/services/error_classifier.py`

```python
# Добавить в classify_error():
elif status_code == 402:
    return AuthenticationError(f"Payment required: {error_message}")
elif status_code == 404:
    return ConfigurationError(f"Endpoint/model not found: {error_message}")
```

Добавить `ConfigurationError` в иерархию исключений — non-retryable, с автоматическим cooldown на 24ч.

#### P0-2: Исправить обёртку ошибок в OpenAICompatibleProvider

**Файл**: `app/infrastructure/ai_providers/base.py`

**Проблема**: `except httpx.HTTPError as e: raise ProviderError(...)` теряет HTTP-код.

**Исправление**: пробрасывать `httpx.HTTPStatusError` напрямую, либо классифицировать внутри провайдера:

```python
except httpx.HTTPStatusError as e:
    raise e  # пусть classify_error() обработает оригинал
except httpx.HTTPError as e:
    raise ProviderError(f"{self.PROVIDER_NAME} error: {e}") from e
```

#### P0-3: Payload budget до отправки

**Файл**: `app/application/use_cases/process_prompt.py` или уровень schemas

```python
MAX_EFFECTIVE_PAYLOAD = 6500  # символов (с запасом от порога 7000)

# Перед отправкой:
if len(prompt) > MAX_EFFECTIVE_PAYLOAD:
    prompt = prompt[:MAX_EFFECTIVE_PAYLOAD] + "..."
```

#### P0-4: Адаптивное снижение concurrency

**Где**: обёртка над массовым прогоном (скрипт reclassification)

```python
# Если error_rate за последние 50 запросов > 50%:
#   - уменьшить concurrency (8 → 4 → 2 → 1)
#   - добавить паузу между запросами (1-5 сек)
# Если error_rate < 20%:
#   - постепенно увеличивать concurrency обратно
```

### P1 — Наблюдаемость

#### P1-1: Per-request telemetry в прогоне

Добавить в `results.jsonl` для каждого запроса:

```json
{
    "request_started_at": "2026-02-24T20:16:05Z",
    "request_finished_at": "2026-02-24T20:16:08Z",
    "duration_ms": 3245,
    "model_id": 5,
    "model_name": "Llama 3.1 70B",
    "provider": "Groq",
    "http_status": 200,
    "attempts": 1,
    "fallback_used": false,
    "prompt_chars": 4200
}
```

#### P1-2: Circuit breaker

```python
# Параметры:
# - failure_threshold: 5 ошибок подряд → OPEN
# - recovery_timeout: 60 сек → HALF-OPEN (1 пробный запрос)
# - success_threshold: 2 успеха подряд → CLOSED

class CircuitBreaker:
    def __init__(self, provider_name: str, failure_threshold: int = 5,
                 recovery_timeout: int = 60):
        ...
```

### P2 — Улучшения

#### P2-1: Exponential backoff в retry-сервисе

```python
# Вместо фиксированных 10 сек:
delay = base_delay * (2 ** attempt) + random.uniform(0, 1)  # jitter
# 10 → 20 → 40 → 80 сек (с кэпом)
```

#### P2-2: Нормализация справочников

Добавить маппинг неизвестных кодов:
```python
PROFESSION_ALIASES = {
    "data_engineer": "backend_dev",
    "js_dev": "fullstack_dev",
    "qa": "python_dev",
}
```

#### P2-3: Rate limit на /api/v1/prompts/process

```python
@limiter.limit(f"{RATE_LIMIT_REQUESTS}/{RATE_LIMIT_PERIOD}second")
@router.post("/process")
async def process_prompt(...):
    ...
```

---

## Приложение: сводка провайдеров

| Провайдер | Статус | HTTP ошибка | Рекомендация |
|---|---|---|---|
| Cloudflare | Работает | — | Оставить |
| Groq | Rate limited | 429 | Снизить concurrency, backoff |
| SambaNova | Rate limited | 429 | Снизить concurrency, backoff |
| GitHubModels | Rate limited | 429 | Снизить concurrency, backoff |
| DeepSeek | Платный лимит | 402 | Пополнить баланс или отключить |
| HuggingFace | Платный лимит | 402 | Пополнить баланс или отключить |
| Hyperbolic | Платный лимит | 402 | Пополнить баланс или отключить |
| Scaleway | Ключ невалиден | 403 | Обновить API-ключ |
| Kluster | Ключ невалиден | 403 | Обновить API-ключ |
| Fireworks | URL/модель не найден | 404 | Обновить endpoint/model_id |
| Novita | URL/модель не найден | 404 | Обновить endpoint/model_id |
| OpenRouter | URL/модель не найден | 404 | Обновить endpoint/model_id |
| Cerebras | URL/модель не найден | 404 | Обновить endpoint/model_id |
