# План фичи: F022 — Исправление классификации ошибок LLM-провайдеров

**Feature ID**: F022
**Дата**: 2026-02-25
**Статус**: Ожидает утверждения
**Связанные артефакты**: [PRD](_analysis/2026-02-25_F022_error-classifier-fix.md), [Research](_research/2026-02-25_F022_error-classifier-fix.md)

---

## Контекст

Массовый прогон LLM-запросов показал 66% error rate. Корневая причина — `OpenAICompatibleProvider` оборачивает `httpx.HTTPStatusError` в generic `ProviderError`, после чего `classify_error()` теряет HTTP-код. Дополнительно: HTTP 402 и 404 не классифицируются, а промпты ≥ 7000 символов вызывают 100% ошибок 422. Три точечных исправления в business-api устраняют ~70% ошибок.

---

## Содержание

1. Проброс HTTPStatusError из провайдеров (base.py)
2. Расширение classify_error для HTTP 402 и 404 (error_classifier.py)
3. Payload budget — обрезка промпта (process_prompt.py)
4. Тесты

---

## Краткая версия плана

### Этап 1: Проброс HTTPStatusError из провайдеров

1. **Проблема** — `OpenAICompatibleProvider.generate()` ловит `httpx.HTTPStatusError` общим `except httpx.HTTPError` и оборачивает в generic `ProviderError`, теряя HTTP status code.
2. **Действие** — Разделить один except-блок на два: `except httpx.HTTPStatusError: raise` (проброс) и `except httpx.HTTPError: raise ProviderError(...)` (обёртка сетевых ошибок).
3. **Результат** — `classify_error()` получает оригинальный `httpx.HTTPStatusError` с HTTP-кодом и может правильно классифицировать. Затрагивает все 12 провайдеров на `OpenAICompatibleProvider`.
4. **Зависимости** — Нет. Первый этап.
5. **Риски** — Порядок except критичен: `HTTPStatusError` ПЕРЕД `HTTPError`. Cloudflare не затрагивается (свой generate, уже пробрасывает).
6. **Без этого** — Этапы 2 бесполезен: 402/404 оборачиваются в `ProviderError` до `classify_error()`.

### Этап 2: Расширение classify_error для HTTP 402 и 404

1. **Проблема** — `classify_error()` не обрабатывает HTTP 402 (Payment Required) и 404 (Not Found). Они проваливаются в generic `ProviderError`.
2. **Действие** — Добавить две ветки: `402 → AuthenticationError` и `404 → ValidationError` в функцию `classify_error()` файла `error_classifier.py`.
3. **Результат** — 7 провайдеров (DeepSeek, HuggingFace, Hyperbolic, Fireworks, Novita, OpenRouter, Cerebras) получают правильную классификацию ошибок. Non-retryable, мгновенный failover.
4. **Зависимости** — Этап 1 (иначе HTTP-код теряется для 12/14 провайдеров).
5. **Риски** — Минимальные. Новые ветки не затрагивают существующие.
6. **Без этого** — 402/404 остаются generic `ProviderError`, system не знает что провайдер мёртв навсегда.

### Этап 3: Payload budget — обрезка промпта

1. **Проблема** — Промпты ≥ 7000 символов вызывают 100% ошибок HTTP 422 от провайдеров. Pydantic разрешает до 10 000.
2. **Действие** — Добавить константу `MAX_PROMPT_CHARS` (env, default 6000) и обрезку `request.prompt_text` перед fallback loop в `ProcessPromptUseCase.execute()`.
3. **Результат** — Все 139 ошибок HTTP 422 из прогона устраняются. В логах — warning `prompt_truncated`.
4. **Зависимости** — Нет. Полностью независим от этапов 1–2.
5. **Риски** — Обрезка может потерять контекст длинного промпта. Лимит конфигурируем через env.
6. **Без этого** — Все запросы с payload ≥ 7000 символов гарантированно падают.

### Этап 4: Тесты

1. **Проблема** — Нужно подтвердить корректность новых веток classify_error.
2. **Действие** — Добавить 2 unit-теста в `test_error_classifier.py`: HTTP 402 → AuthenticationError и HTTP 404 → ValidationError.
3. **Результат** — Покрытие classify_error расширяется на 2 новых HTTP-кода. Все 22 теста проходят.
4. **Зависимости** — Этап 2 (тесты проверяют новые ветки).
5. **Риски** — Нет. Существующие 20 тестов не затрагиваются.
6. **Без этого** — Нет автоматической проверки новых веток. Регрессия не будет обнаружена.

---

## Полная версия плана

---

## Этап 1: Проброс HTTPStatusError из провайдеров

### Файл: `app/infrastructure/ai_providers/base.py`

**Строки 200–203** — разделить один except на два.

**Было:**
```python
            except httpx.HTTPError as e:
                err_msg = sanitize_error_message(e)
                logger.error(f"{self.PROVIDER_NAME} API error: {err_msg}")
                raise ProviderError(f"{self.PROVIDER_NAME} error: {e}") from e
```

**Стало:**
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

**Важно**:
- `httpx.HTTPStatusError` ПЕРЕД `httpx.HTTPError` (HTTPStatusError — подкласс HTTPError)
- Логирование через `sanitize_error_message()` сохраняется
- `raise` без аргументов — пробрасывает оригинальный `httpx.HTTPStatusError`
- Cloudflare не затрагивается (свой generate(), уже пробрасывает)

### Путь данных после изменения

```
generate() → httpx.HTTPStatusError(404) → raise (строка 200)
  → retry_service (строка 61): except Exception → classify_error(HTTPStatusError(404))
    → ValidationError → is_retryable(ValidationError) → False
      → raise ValidationError (строка 76)
        → process_prompt (строка 201): except (..., ValidationError, ...) → _handle_transient_error()
```

---

## Этап 2: Расширение classify_error для HTTP 402 и 404

### Файл: `app/application/services/error_classifier.py`

**После строки 85** (после блока 400/422) добавить:

```python
        # F022: Payment required (402) — free tier exhausted
        if status_code == 402:
            return AuthenticationError(
                message=f"Payment required: {str(exception)}",
                original_exception=exception,
            )

        # F022: Not found (404) — wrong endpoint or model ID
        if status_code == 404:
            return ValidationError(
                message=f"Endpoint or model not found: {str(exception)}",
                original_exception=exception,
            )
```

**Обоснование типов**:
- 402 → `AuthenticationError`: провайдер жив, но бесплатный лимит исчерпан. Аналогично 401/403 — проблема с доступом, non-retryable.
- 404 → `ValidationError`: endpoint или model_id неверный. Ошибка конфигурации, non-retryable. Аналогично 400/422 — неверный запрос.

**Обновить docstring** модуля (строка 8): добавить `- 402 → AuthenticationError` и `- 404 → ValidationError`.

---

## Этап 3: Payload budget — обрезка промпта

### Файл: `app/application/use_cases/process_prompt.py`

**Шаг 3a**: Добавить константу на уровне модуля (строка ~51, рядом с `RATE_LIMIT_DEFAULT_COOLDOWN`):

```python
MAX_PROMPT_CHARS = int(os.getenv("MAX_PROMPT_CHARS", "6000"))
```

**Шаг 3b**: Добавить обрезку после строки ~173 (перед `for model in candidate_models:`):

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

**Критические нюансы**:
- Поле называется **`prompt_text`**, не `prompt` (dataclass `PromptRequest` в `domain/models.py`)
- `PromptRequest` — `@dataclass` без `frozen=True`, без `__post_init__`. Безопасно создавать новый экземпляр
- `os` уже импортирован (строка 24)
- `PromptRequest` уже импортирован (строка 39)
- Константа на уровне модуля — аналогично существующему паттерну `RATE_LIMIT_DEFAULT_COOLDOWN` на строке 50

---

## Этап 4: Тесты

### Файл: `tests/unit/test_error_classifier.py`

Добавить 2 теста в класс `TestClassifyError` (после строки 139, после `test_classify_422_as_validation_error`):

```python
    def test_classify_402_as_authentication_error(self):
        """F022: HTTP 402 → AuthenticationError (payment required)."""
        request = Request("POST", "https://api.test.com")
        response = Response(402, request=request)
        exception = httpx.HTTPStatusError(
            "Payment required", request=request, response=response
        )

        result = classify_error(exception)

        assert isinstance(result, AuthenticationError)
        assert "Payment required" in result.message

    def test_classify_404_as_validation_error(self):
        """F022: HTTP 404 → ValidationError (endpoint not found)."""
        request = Request("POST", "https://api.test.com")
        response = Response(404, request=request)
        exception = httpx.HTTPStatusError(
            "Not found", request=request, response=response
        )

        result = classify_error(exception)

        assert isinstance(result, ValidationError)
        assert "not found" in result.message.lower()
```

**Паттерн**: идентичен существующим тестам (test_classify_401, test_classify_400 и т.д.).

### Запуск тестов

```bash
docker compose exec free-ai-selector-business-api pytest tests/unit/test_error_classifier.py -v
docker compose exec free-ai-selector-business-api pytest tests/unit/test_retry_service.py -v
```

---

## Сводка изменений

### Новые компоненты

Нет новых файлов.

### Модификации существующего кода

| Файл | Строки | Тип | Описание |
|------|--------|-----|----------|
| `app/infrastructure/ai_providers/base.py` | 200–203 | modify | Разделить except на HTTPStatusError + HTTPError |
| `app/application/services/error_classifier.py` | 85+ | add | Добавить ветки 402 → AuthError, 404 → ValidationError |
| `app/application/services/error_classifier.py` | 1–14 | modify | Обновить docstring |
| `app/application/use_cases/process_prompt.py` | ~51 | add | Константа MAX_PROMPT_CHARS |
| `app/application/use_cases/process_prompt.py` | ~174 | add | Payload budget (обрезка prompt_text) |
| `tests/unit/test_error_classifier.py` | 140+ | add | 2 теста: HTTP 402 и 404 |

### Новые зависимости

Нет.

### Breaking changes

Нет. HTTP-контракт `/api/v1/prompts/process` не меняется.

---

## Влияние на существующие тесты

| Файл тестов | Тестов | Сломается? | Причина |
|-------------|--------|------------|---------|
| `test_error_classifier.py` | 20 | Нет | Новые ветки не затрагивают существующие |
| `test_retry_service.py` | 11 | Нет | retry_service.py не изменяется |
| Integration tests | — | Нет | HTTP-контракт не меняется |

---

## План интеграции

| # | Шаг | Файл | Зависимости |
|---|------|------|-------------|
| 1 | Разделить except в generate() | base.py:200–203 | — |
| 2 | Добавить 402/404 в classify_error() | error_classifier.py:85+ | Шаг 1 |
| 3 | Обновить docstring classify_error | error_classifier.py:1–14 | Шаг 2 |
| 4 | Добавить MAX_PROMPT_CHARS | process_prompt.py:~51 | — |
| 5 | Добавить payload budget | process_prompt.py:~174 | Шаг 4 |
| 6 | Добавить 2 теста | test_error_classifier.py:140+ | Шаг 2 |
| 7 | Запустить все тесты | — | Шаги 1–6 |

---

## Риски и митигация

| Риск | Вероятность | Митигация |
|------|-------------|-----------|
| Порядок except-блоков в base.py перепутан | Low | HTTPStatusError ПЕРЕД HTTPError, review перед коммитом |
| Поле prompt вместо prompt_text | Low | Исследование подтвердило: prompt_text. Тест через запуск |
| Обрезка ухудшает качество ответа AI | Med | MAX_PROMPT_CHARS конфигурируем через env |
