# Research: F022 — Исправление классификации ошибок LLM-провайдеров

**Feature ID**: F022
**Дата**: 2026-02-25
**Статус**: RESEARCH_DONE
**Версия**: 2 (углублённое исследование)

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

**Но важный нюанс**: `retry_with_fixed_delay()` внутри ловит `Exception`, классифицирует через `classify_error()`, и если non-retryable — пробрасывает **уже классифицированный** тип (`ValidationError`, `AuthenticationError`). Поэтому в fallback loop на строке 201–206 `httpx.HTTPStatusError` **НЕ дойдёт** — вместо него придёт уже `ValidationError` или `AuthenticationError`. Они будут пойманы блоком 2.

### 1.4 Payload validation (schemas.py + _build_payload)

**Pydantic** (`schemas.py:16`): `prompt: str, min_length=1, max_length=10000`
**_build_payload** (`base.py:126`): передаёт prompt as-is в `messages[0].content`

Нет промежуточного ограничения. Данные диагностики:
- Payload ≥ 7000 символов → 100% ошибок HTTP 422
- Payload < 7000 → 0.16% ошибок HTTP 422

**Оптимальный порог**: 6000 символов (с запасом, учитывая system_prompt + JSON overhead).

---

## 2. Полная матрица провайдеров

### 2.1 Наследование и error handling

| Провайдер | Базовый класс | Свой generate()? | Error handling | Переопределённые методы |
|-----------|---------------|------------------|----------------|------------------------|
| Groq | `OpenAICompatibleProvider` | Нет | base.py | — |
| Cerebras | `OpenAICompatibleProvider` | Нет | base.py | — |
| SambaNova | `OpenAICompatibleProvider` | Нет | base.py | — |
| HuggingFace | `OpenAICompatibleProvider` | Нет | base.py | — |
| DeepSeek | `OpenAICompatibleProvider` | Нет | base.py | — |
| OpenRouter | `OpenAICompatibleProvider` | Нет | base.py | `_build_headers()` (EXTRA_HEADERS) |
| GitHubModels | `OpenAICompatibleProvider` | Нет | base.py | `_is_health_check_success()` |
| Fireworks | `OpenAICompatibleProvider` | Нет | base.py | — |
| Hyperbolic | `OpenAICompatibleProvider` | Нет | base.py | — |
| Novita | `OpenAICompatibleProvider` | Нет | base.py | — |
| Scaleway | `OpenAICompatibleProvider` | Нет | base.py | — |
| Kluster | `OpenAICompatibleProvider` | Нет | base.py | — |
| Nebius | `OpenAICompatibleProvider` | Нет | base.py | — |
| **Cloudflare** | **`AIProviderBase`** | **Да** (строки 51–141) | **Собственный** | Все 3 метода |

**Вывод**: 12 из 14 провайдеров используют единственный `generate()` из `base.py:174–203`. Исправление в одном месте автоматически фиксит все 12 провайдеров.

### 2.2 Cloudflare — отдельный анализ

```python
# cloudflare.py строки 139-141:
except httpx.HTTPError as e:
    logger.error(f"Cloudflare Workers AI API error: {sanitize_error_message(e)}")
    raise  # ← ПРОБРАСЫВАЕТ оригинал, НЕ оборачивает в ProviderError
```

Cloudflare **уже** пробрасывает `httpx.HTTPStatusError` напрямую. `classify_error()` уже получает оригинал от Cloudflare. **F022 не затрагивает Cloudflare**.

### 2.3 ProviderRegistry (F008 SSOT)

**Файл**: `app/infrastructure/ai_providers/registry.py`

- `PROVIDER_CLASSES: dict[str, type[AIProviderBase]]` — статический dict (14 провайдеров)
- `get_provider(name)` — ленивая инициализация, Singleton-паттерн через `_instances`
- `get_api_key_env(name)` — получение env-переменной без создания экземпляра
- `reset()` — очистка кэша (для тестов)

---

## 3. Domain models — PromptRequest

### 3.1 Определение

**Файл**: `app/domain/models.py`

```python
@dataclass
class PromptRequest:
    user_id: str
    prompt_text: str              # ← ВНИМАНИЕ: поле называется prompt_text, НЕ prompt
    model_id: Optional[int] = None
    system_prompt: Optional[str] = None
    response_format: Optional[dict] = None
```

> **КРИТИЧЕСКИЙ НЮАНС**: поле `PromptRequest` называется **`prompt_text`**, не `prompt`.
> В Pydantic-схеме API (`ProcessPromptRequest`) поле называется `prompt`.
> В domain-модели (`PromptRequest`) — `prompt_text`.

### 3.2 Подтверждение из process_prompt.py

- Строка 375: `request.prompt_text` — используется при вызове `provider.generate()`
- Строка ~103: `PromptRequest` конструируется в `prompts.py` роутере

### 3.3 Создание нового экземпляра

`@dataclass` без `frozen=True`, без `__post_init__`. Безопасно создавать:

```python
request = PromptRequest(
    user_id=request.user_id,
    prompt_text=request.prompt_text[:MAX_PROMPT_CHARS],  # prompt_text, не prompt!
    model_id=request.model_id,
    system_prompt=request.system_prompt,
    response_format=request.response_format,
)
```

---

## 4. Domain exceptions — иерархия и конструкторы

**Файл**: `app/domain/exceptions.py` (107 строк)

| Класс | Строки | Свой `__init__`? | Параметры |
|-------|--------|-----------------|-----------|
| `ProviderError` | 19–36 | Да (строка 26) | `message: str`, `original_exception: Optional[Exception] = None` |
| `RateLimitError` | 39–62 | Да (строка 47) | `message`, `retry_after_seconds: Optional[int] = None`, `original_exception` |
| `ServerError` | 65–73 | Нет (pass) | Наследует конструктор `ProviderError` |
| `TimeoutError` | 76–84 | Нет (pass) | Наследует конструктор `ProviderError` |
| `AuthenticationError` | 87–95 | Нет (pass) | Наследует конструктор `ProviderError` |
| `ValidationError` | 98–106 | Нет (pass) | Наследует конструктор `ProviderError` |

**Для FR-002/003** — конструкторы единообразны:

```python
AuthenticationError(message="...", original_exception=exception)
ValidationError(message="...", original_exception=exception)
```

---

## 5. retry_service.py — детальный анализ пути httpx.HTTPStatusError

**Файл**: `app/application/services/retry_service.py` (106 строк)

### 5.1 Единственный except-блок (строка 61)

```python
except Exception as e:                          # строка 61
    classified_error = classify_error(e)        # строка 63
    if not is_retryable(classified_error):      # строка 66
        raise classified_error                  # строка 76 — пробрасывает КЛАССИФИЦИРОВАННЫЙ тип
    last_error = classified_error               # строка 78 — сохраняет для следующей итерации
```

### 5.2 Путь httpx.HTTPStatusError(404) через retry_service (после FR-001)

1. `generate()` бросает `httpx.HTTPStatusError(404)`
2. `except Exception` ловит
3. `classify_error(HTTPStatusError(404))` → `ValidationError("Endpoint or model not found: ...")`
4. `is_retryable(ValidationError)` → `False`
5. `raise ValidationError(...)` — пробрасывается немедленно (без retry, без sleep)
6. В `process_prompt.py` fallback loop: `except (ServerError, ... ValidationError, ProviderError)` ловит `ValidationError` на строке 201–206

**Вывод**: `httpx.HTTPStatusError` трансформируется в `ValidationError`/`AuthenticationError` ВНУТРИ retry_service, до попадания в fallback loop. Блок `except Exception` на строке 212 process_prompt.py **НЕ будет задействован** для этих ошибок. FR-010 не нужен функционально.

### 5.3 Побочные эффекты при пробросе — нет

Тест `test_http_status_error_classified_and_handled` (`test_retry_service.py:185`) уже проверяет, что `httpx.HTTPStatusError(503)` правильно классифицируется как `ServerError` и ретраится. Этот тест **НЕ сломается** — retry_service.py не изменяется.

---

## 6. Анализ существующих тестов

### 6.1 test_error_classifier.py (221 строка, 20 тестов)

| Класс | Тестов | Покрытие |
|-------|--------|----------|
| `TestClassifyError` | 11 | 429, 500+429body, 500, 502, 503, 401, 403, 400, 422, timeout × 3, unknown |
| `TestParseRetryAfter` | 3 | int, missing, invalid |
| `TestIsRetryable` | 6 | ServerError, TimeoutError, RateLimitError, AuthError, ValidationError, generic |

**Отсутствующие тесты (нужны для F022)**:
- `test_classify_402_as_authentication_error` — HTTP 402 → AuthenticationError
- `test_classify_404_as_validation_error` — HTTP 404 → ValidationError

### 6.2 test_retry_service.py (244 строки, 11 тестов)

| Тест | Что проверяет | Сломается? |
|------|---------------|------------|
| `test_success_on_first_attempt` | Успешный вызов | Нет |
| `test_retry_on_server_error` | Retry при ServerError | Нет |
| `test_retry_on_timeout_error` | Retry при TimeoutError | Нет |
| `test_no_retry_on_rate_limit_error` | No-retry при 429 | Нет |
| `test_no_retry_on_authentication_error` | No-retry при 401 | Нет |
| `test_no_retry_on_validation_error` | No-retry при 422 | Нет |
| `test_exhausted_retries_raises_last_error` | Exhausted | Нет |
| `test_mixed_errors_retry_only_retryable` | Mix errors | Нет |
| `test_delay_between_retries` | asyncio.sleep | Нет |
| `test_http_status_error_classified_and_handled` | HTTPStatusError(503) | Нет |
| `test_max_retries_zero_means_single_attempt` | max_retries=0 | Нет |

**Вывод**: ни один тест не сломается. retry_service.py не изменяется в F022.

### 6.3 Тесты на ProcessPromptUseCase

**Не найдены**. Нет файла `test_process_prompt*.py`. Покрытие use case — через интеграционные тесты.

### 6.4 Тесты на OpenAICompatibleProvider.generate()

**Не найдены** отдельные unit-тесты. Провайдеры тестируются интеграционно.

---

## 7. Зависимости между изменениями

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
│ FR-002/003: Добавить │  │ FR-010 (optional):   │
│ 402/404 в            │  │ explicit except в    │
│ classify_error()     │  │ fallback loop        │
└──────────────────────┘  └──────────────────────┘

┌──────────────────────┐
│ FR-004: Payload      │  ← ПОЛНОСТЬЮ НЕЗАВИСИМ
│ budget               │
└──────────────────────┘
```

**Порядок реализации**: FR-001 (base.py) → FR-002/003 (error_classifier.py) → FR-004 (process_prompt.py) → тесты.

---

## 8. Риски и ограничения

### 8.1 Риск: порядок except-блоков в base.py

`httpx.HTTPStatusError` — подкласс `httpx.HTTPError`. Если перепутать порядок, `HTTPStatusError` будет перехвачен широким блоком. **Правильный порядок**: `except httpx.HTTPStatusError` ПЕРЕД `except httpx.HTTPError`.

### 8.2 Риск: Cloudflare провайдер

Cloudflare уже пробрасывает `httpx.HTTPError` напрямую. **F022 его не затрагивает** — не нужно менять.

### 8.3 Ограничение: sanitize_error_message в base.py

В `base.py:201` вызывается `sanitize_error_message(e)` + логирование перед raise. Это **нужно сохранить** при разделении except:

```python
except httpx.HTTPStatusError as e:
    err_msg = sanitize_error_message(e)
    logger.error(f"{self.PROVIDER_NAME} API error: {err_msg}")
    raise  # пробрасываем оригинал с HTTP-кодом
```

### 8.4 Ограничение: отсутствие тестов на ProcessPromptUseCase

Нет unit-тестов на fallback loop. Изменения FR-004 нельзя проверить unit-тестами без mock'ов DataAPIClient.

### 8.5 Ограничение: `import httpx` в process_prompt.py

`httpx` не импортирован в `process_prompt.py`. Если реализовывать FR-010, нужно добавить `import httpx`. Но FR-010 не обязателен функционально.

---

## 9. Точные изменения по файлам

### 9.1 error_classifier.py

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

### 9.2 base.py

**Строки 200–203** — разделить один except на два:

```python
            except httpx.HTTPStatusError as e:
                err_msg = sanitize_error_message(e)
                logger.error(f"{self.PROVIDER_NAME} API error: {err_msg}")
                raise  # Пробрасываем с HTTP-кодом для classify_error()

            except httpx.HTTPError as e:
                err_msg = sanitize_error_message(e)
                logger.error(f"{self.PROVIDER_NAME} API error: {err_msg}")
                raise ProviderError(f"{self.PROVIDER_NAME} error: {e}") from e
```

### 9.3 process_prompt.py

**Строка ~51** (уровень модуля, рядом с `RATE_LIMIT_DEFAULT_COOLDOWN`):
```python
MAX_PROMPT_CHARS = int(os.getenv("MAX_PROMPT_CHARS", "6000"))
```

**После строки ~173** (перед `for model in candidate_models:`):
```python
        # F022: Payload budget — обрезка промпта для предотвращения HTTP 422
        if len(request.prompt_text) > MAX_PROMPT_CHARS:
            logger.warning(
                "prompt_truncated",
                original_length=len(request.prompt_text),
                max_length=MAX_PROMPT_CHARS,
            )
            request = PromptRequest(
                user_id=request.user_id,
                prompt_text=request.prompt_text[:MAX_PROMPT_CHARS],
                model_id=request.model_id,
                system_prompt=request.system_prompt,
                response_format=request.response_format,
            )
```

> **ВНИМАНИЕ**: поле называется `prompt_text`, не `prompt`.

### 9.4 test_error_classifier.py

Добавить 2 теста в класс `TestClassifyError` (после строки 139):

```python
    def test_classify_402_as_authentication_error(self):
        """F022: HTTP 402 → AuthenticationError (payment required)."""
        request = Request("POST", "https://api.test.com")
        response = Response(402, request=request)
        exception = httpx.HTTPStatusError("Payment required", request=request, response=response)
        result = classify_error(exception)
        assert isinstance(result, AuthenticationError)
        assert "Payment required" in result.message

    def test_classify_404_as_validation_error(self):
        """F022: HTTP 404 → ValidationError (endpoint not found)."""
        request = Request("POST", "https://api.test.com")
        response = Response(404, request=request)
        exception = httpx.HTTPStatusError("Not found", request=request, response=response)
        result = classify_error(exception)
        assert isinstance(result, ValidationError)
        assert "not found" in result.message.lower()
```

---

## 10. Quality Cascade Checklist

### DRY
- `classify_error()` — единственная функция классификации. Расширяем, не дублируем.
- `sanitize_error_message()` — уже используется в error handling. Сохраняем.
- Паттерн `os.getenv("X", "default")` — уже используется на строке 50 process_prompt.py.
- `MAX_PROMPT_CHARS` вынести на уровень модуля (аналогично `RATE_LIMIT_DEFAULT_COOLDOWN`).

### KISS
- FR-001: одна строка `raise` вместо `raise ProviderError(...)`.
- FR-002, FR-003: два `if status_code == X: return Y(...)`.
- FR-004: 8 строк кода, нет новых зависимостей.
- FR-010, FR-020: **не реализуем** — YAGNI.

### SoC
- Классификация ошибок: только в `error_classifier.py`.
- Transport-level exceptions: до границы `classify_error` не конвертируются.
- Payload validation: в use case слое (`process_prompt.py`), не в провайдере.

### SSoT
| Тип данных | Файл-источник |
|------------|---------------|
| HTTP code → error type | `error_classifier.py:classify_error()` |
| Retryable error types | `error_classifier.py:is_retryable()` |
| Provider names | `registry.py:PROVIDER_CLASSES` |
| Exception hierarchy | `domain/exceptions.py` |
| MAX_PROMPT_CHARS | `process_prompt.py` (модульная константа) |

### Security
- `sanitize_error_message()` сохраняется при логировании в изменённом `base.py`.
- При проброске `raise` логирование происходит ДО, не после.
- `prompt_text[:N]` — безопасная строковая операция.

---

## 11. Рекомендации для /aidd-plan-feature

1. **Порядок**: FR-001 (base.py) → FR-002/003 (error_classifier.py) → FR-004 (process_prompt.py) → тесты.
2. **FR-010** — не реализовывать. `retry_service` уже трансформирует `httpx.HTTPStatusError` в типизированные `ProviderError`-подклассы до fallback loop.
3. **FR-020** — отложить. Посимвольная обрезка достаточна.
4. **FR-011** — не нужен. Имя провайдера уже логируется в `base.py:202` до raise.
5. **Тесты**: обязательны 2 новых для error_classifier. Для base.py и process_prompt.py — через integration.
6. **Поле `prompt_text`** — не `prompt`. Критически важно для FR-004.
