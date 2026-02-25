# Research: F022 — Исправление классификации ошибок LLM-провайдеров

**Feature ID**: F022
**Дата**: 2026-02-25
**Статус**: RESEARCH_DONE

---

## 1. Анализ текущего кода

### 1.1 error_classifier.py (144 строки)

**Путь**: `services/free-ai-selector-business-api/app/application/services/error_classifier.py`

**Функция `classify_error()` (строки 31–91)**:
- Входная точка: принимает любой `Exception`, возвращает типизированный `ProviderError`.
- Первая проверка (строка 42): `isinstance(exception, ProviderError)` → возвращает as-is. Это **ключевая проблема** — если провайдер уже обернул `httpx.HTTPStatusError` в `ProviderError`, классификация пропускается.
- HTTP status codes (строки 53–85):

| Код | Ветка | Результат |
|-----|-------|-----------|
| 429 | строка 58 | `RateLimitError` |
| 500 + "429" в body | строка 58 | `RateLimitError` |
| 5xx | строка 67 | `ServerError` |
| 401, 403 | строка 74 | `AuthenticationError` |
| 400, 422 | строка 81 | `ValidationError` |
| **402** | **нет ветки** | **generic `ProviderError`** (строка 88) |
| **404** | **нет ветки** | **generic `ProviderError`** (строка 88) |

**Влияние**: HTTP 402 (DeepSeek, HuggingFace, Hyperbolic) и 404 (Fireworks, Novita, OpenRouter, Cerebras) не классифицируются. Это 7 из 13 провайдеров.

### 1.2 base.py — OpenAICompatibleProvider.generate() (строки 174–203)

```python
# Строки 200-203:
except httpx.HTTPError as e:
    err_msg = sanitize_error_message(e)
    logger.error(f"{self.PROVIDER_NAME} API error: {err_msg}")
    raise ProviderError(f"{self.PROVIDER_NAME} error: {e}") from e
```

**Проблема**: `httpx.HTTPStatusError` является подклассом `httpx.HTTPError`. Поэтому ВСЕ HTTP-ошибки (включая 402, 404, 429) ловятся одним блоком и оборачиваются в generic `ProviderError`. После этого `classify_error()` видит `ProviderError` и возвращает его без изменений (строка 42).

**Цепочка бага**:
```
provider.generate() → httpx.HTTPStatusError(404)
  → except httpx.HTTPError → raise ProviderError("Fireworks error: 404 Not Found")
    → retry_service → classify_error(ProviderError) → return ProviderError as-is
      → process_prompt → _handle_transient_error() → increment_failure()
        → следующая модель (но тип ошибки потерян)
```

**Корректная цепочка (после исправления)**:
```
provider.generate() → httpx.HTTPStatusError(404) → пробрасывается напрямую
  → retry_service → classify_error(HTTPStatusError(404)) → ValidationError
    → non-retryable → пробрасывается немедленно
      → process_prompt → _handle_transient_error(ValidationError)
```

### 1.3 process_prompt.py — Fallback loop (строки 176–219)

Catch-блоки в порядке:
1. `except RateLimitError` (строка 196) → `_handle_rate_limit()`
2. `except (ServerError, TimeoutError, AuthenticationError, ValidationError, ProviderError)` (строки 201–206) → `_handle_transient_error()`
3. `except Exception` (строка 212) → `classify_error()` → маршрутизация

**Критическое наблюдение**: после исправления в `base.py`, `httpx.HTTPStatusError` НЕ будет пойман ни блоком 1 (он не `RateLimitError`), ни блоком 2 (он не `ProviderError`). Он попадёт в блок 3 (`except Exception`), где `classify_error()` правильно классифицирует его. **Это работает корректно без дополнительных изменений**.

Однако для явности и производительности рекомендуется добавить `except httpx.HTTPStatusError` перед `except Exception`:

```python
except httpx.HTTPStatusError as e:
    classified = classify_error(e)
    if isinstance(classified, RateLimitError):
        await self._handle_rate_limit(model, classified)
    else:
        await self._handle_transient_error(model, classified, start_time)
    last_error_message = sanitize_error_message(e)
```

### 1.4 Payload validation (schemas.py + _build_payload)

**Pydantic** (`schemas.py:16`): `prompt: str, min_length=1, max_length=10000`
**_build_payload** (`base.py:126`): передаёт prompt as-is в `messages[0].content`

Нет промежуточного ограничения. Данные диагностики:
- Payload ≥ 7000 символов → 100% ошибок HTTP 422
- Payload < 7000 → 0.16% ошибок HTTP 422

**Оптимальный порог**: 6000 символов (с запасом, учитывая system_prompt + JSON overhead).

---

## 2. Анализ существующих тестов

### 2.1 test_error_classifier.py (221 строка, 20 тестов)

| Класс | Тестов | Покрытие |
|-------|--------|----------|
| `TestClassifyError` | 11 | 429, 500+429body, 500, 502, 503, 401, 403, 400, 422, timeout × 3, unknown |
| `TestParseRetryAfter` | 3 | int, missing, invalid |
| `TestIsRetryable` | 6 | ServerError, TimeoutError, RateLimitError, AuthError, ValidationError, generic |

**Отсутствующие тесты (нужны для F022)**:
- `test_classify_402_as_authentication_error` — HTTP 402 → AuthenticationError
- `test_classify_404_as_validation_error` — HTTP 404 → ValidationError

### 2.2 test_retry_service.py (244 строки, 11 тестов)

Покрывает: успех, retry на ServerError/TimeoutError, no-retry на 429/401/422, exhausted, delay, httpx classification.

**Нет изменений для F022** — retry_service не меняется.

### 2.3 Тесты на ProcessPromptUseCase

**Не найдены**. Файл `test_process_prompt_use_case.py` не существует. Это снижает уверенность в безопасности изменений fallback loop. Рекомендуется добавить хотя бы smoke-тест на HTTPStatusError propagation.

### 2.4 Тесты на OpenAICompatibleProvider.generate()

**Не найдены** отдельные unit-тесты на `base.py`. Провайдеры тестируются через integration.

---

## 3. Зависимости между изменениями

```
                  ┌──────────────────┐
                  │ FR-001: Проброс  │
                  │ HTTPStatusError  │
                  │ из base.py       │
                  └────────┬─────────┘
                           │
              ┌────────────┼────────────┐
              ▼                         ▼
┌──────────────────────┐  ┌──────────────────────┐
│ FR-002/003: Добавить │  │ FR-010: Добавить     │
│ 402/404 в            │  │ except HTTPStatusError│
│ classify_error()     │  │ в fallback loop      │
└──────────────────────┘  └──────────────────────┘
```

**FR-001 (base.py)** должен быть первым — иначе FR-002/003 не имеют эффекта для 12 из 14 провайдеров.

**FR-004 (payload budget)** — полностью независим, можно делать в любом порядке.

---

## 4. Риски и ограничения

### 4.1 Риск: Cloudflare провайдер

Cloudflare (`app/infrastructure/ai_providers/cloudflare.py`) имеет **свой** `generate()` и не наследует `OpenAICompatibleProvider`. Его error handling:

```python
except httpx.HTTPError as e:
    raise ProviderError(f"Cloudflare error: {e}") from e
```

Аналогичная проблема, но Cloudflare стабилен (6 ошибок за 48ч). **Решение**: не трогать Cloudflare в F022 — оставить на P2.

### 4.2 Риск: retry_service ловит Exception

`retry_service.py:29` — `retry_with_fixed_delay()` использует:
```python
except Exception as e:
    classified = classify_error(e)
```

После FR-001, `httpx.HTTPStatusError` будет пойман этим блоком и правильно классифицирован. **Риск отсутствует**.

### 4.3 Ограничение: отсутствие тестов на ProcessPromptUseCase

Нет unit-тестов на fallback loop. Изменение FR-010 нельзя проверить автоматически. Но текущий `except Exception` (строка 212) поймает `httpx.HTTPStatusError` корректно даже без FR-010.

### 4.4 Ограничение: sanitize_error_message

В `base.py:201` вызывается `sanitize_error_message(e)` перед `raise`. После FR-001 (проброс HTTPStatusError) этот лог сохранится — нужно вынести логирование ДО `raise`:

```python
except httpx.HTTPStatusError as e:
    err_msg = sanitize_error_message(e)
    logger.error(f"{self.PROVIDER_NAME} API error: {err_msg}")
    raise  # пробрасываем оригинал
```

---

## 5. Точные изменения по файлам

### 5.1 error_classifier.py

**Строки 80–91** — добавить 2 ветки между `ValidationError` и generic `ProviderError`:

```python
        # Validation errors (400, 422)
        if status_code in (400, 422):
            return ValidationError(...)

        # === НОВОЕ (F022: FR-002) ===
        # Payment required (402) — free tier exhausted
        if status_code == 402:
            return AuthenticationError(
                message=f"Payment required: {str(exception)}",
                original_exception=exception,
            )

        # === НОВОЕ (F022: FR-003) ===
        # Not found (404) — wrong endpoint or model ID
        if status_code == 404:
            return ValidationError(
                message=f"Endpoint or model not found: {str(exception)}",
                original_exception=exception,
            )

    # Unknown exceptions
    return ProviderError(...)
```

### 5.2 base.py

**Строки 200–203** — разделить один except на два:

```python
            # === ИЗМЕНЕНО (F022: FR-001) ===
            except httpx.HTTPStatusError as e:
                err_msg = sanitize_error_message(e)
                logger.error(f"{self.PROVIDER_NAME} API error: {err_msg}")
                raise  # Пробрасываем с HTTP-кодом для classify_error()

            except httpx.HTTPError as e:
                err_msg = sanitize_error_message(e)
                logger.error(f"{self.PROVIDER_NAME} API error: {err_msg}")
                raise ProviderError(f"{self.PROVIDER_NAME} error: {e}") from e
```

### 5.3 process_prompt.py

**Вставка в execute()** — payload budget (после строки ~170, перед fallback loop):

```python
        # === НОВОЕ (F022: FR-004) ===
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

### 5.4 test_error_classifier.py

Добавить 2 теста в `TestClassifyError`:

```python
    def test_classify_402_as_authentication_error(self):
        """F022: HTTP 402 → AuthenticationError (payment required)."""
        request = Request("POST", "https://api.test.com")
        response = Response(402, request=request, content=b"Payment Required")
        exception = httpx.HTTPStatusError("Payment required", request=request, response=response)
        result = classify_error(exception)
        assert isinstance(result, AuthenticationError)
        assert "Payment required" in result.message

    def test_classify_404_as_validation_error(self):
        """F022: HTTP 404 → ValidationError (endpoint not found)."""
        request = Request("POST", "https://api.test.com")
        response = Response(404, request=request, content=b"Not Found")
        exception = httpx.HTTPStatusError("Not found", request=request, response=response)
        result = classify_error(exception)
        assert isinstance(result, ValidationError)
        assert "not found" in result.message.lower()
```

---

## 6. Рекомендации для /aidd-plan-feature

1. **Порядок реализации**: FR-001 (base.py) → FR-002/003 (error_classifier.py) → FR-004 (process_prompt.py) → тесты.
2. **FR-010** (explicit except в fallback) — опционален. `except Exception` на строке 212 уже корректно обработает `httpx.HTTPStatusError`. Добавление FR-010 — улучшение читаемости, не функциональная необходимость.
3. **FR-020** (обрезка по предложению) — отложить. Посимвольная обрезка достаточна для MVP.
4. **Тесты**: обязательны для error_classifier (2 новых). Для base.py и process_prompt.py — желательны, но не блокируют.
