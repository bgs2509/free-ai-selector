---
feature_id: "F013"
feature_name: "ai-providers-consolidation"
title: "Research: AI Providers Consolidation"
created: "2026-01-30"
author: "AI (Researcher)"
type: "research"
status: "RESEARCH_DONE"
version: 1

analyzed_files: 14
openai_compatible: 12
non_compatible: 1
total_lines_before: ~1820
total_lines_after: ~350
reduction: ~80%
---

# Research Report: AI Providers Consolidation

**Feature ID**: F013
**Дата**: 2026-01-30
**Автор**: AI Agent (Исследователь)
**Статус**: RESEARCH_DONE

---

## 1. Executive Summary

Проведён анализ 14 AI провайдеров в `services/free-ai-selector-business-api/app/infrastructure/ai_providers/`. Результаты подтверждают целесообразность рефакторинга:

| Метрика | Значение |
|---------|----------|
| Всего провайдеров | 14 (13 + base.py) |
| OpenAI-совместимых | 12 |
| Исключений | 1 (Cloudflare) |
| Средний размер провайдера | 140-160 строк |
| Дублирования | ~95% кода идентично |
| Ожидаемое сокращение | ~1100 строк → ~120 строк |

---

## 2. Матрица провайдеров

### 2.1 OpenAI-совместимые провайдеры (12)

| Провайдер | Файл | Строк | BASE_URL | DEFAULT_MODEL | ENV_VAR | response_format | extra_headers |
|-----------|------|-------|----------|---------------|---------|-----------------|---------------|
| Groq | `groq.py` | 143 | `api.groq.com/openai/v1/chat/completions` | `llama-3.3-70b-versatile` | `GROQ_API_KEY` | ❌ | ❌ |
| Cerebras | `cerebras.py` | 141 | `api.cerebras.ai/v1/chat/completions` | `llama-3.3-70b` | `CEREBRAS_API_KEY` | ❌ | ❌ |
| SambaNova | `sambanova.py` | 151 | `api.sambanova.ai/v1/chat/completions` | `Meta-Llama-3.1-405B-Instruct` | `SAMBANOVA_API_KEY` | ✅ | ❌ |
| DeepSeek | `deepseek.py` | 143 | `api.deepseek.com/chat/completions` | `deepseek-chat` | `DEEPSEEK_API_KEY` | ❌ | ❌ |
| OpenRouter | `openrouter.py` | 162 | `openrouter.ai/api/v1/chat/completions` | `meta-llama/llama-3.3-70b-instruct:free` | `OPENROUTER_API_KEY` | ❌ | ✅ |
| Hyperbolic | `hyperbolic.py` | 143 | `api.hyperbolic.xyz/v1/chat/completions` | `meta-llama/Llama-3.3-70B-Instruct` | `HYPERBOLIC_API_KEY` | ❌ | ❌ |
| HuggingFace | `huggingface.py` | 143 | `api-inference.huggingface.co/models/{model}/v1/chat/completions` | `meta-llama/Llama-3.3-70B-Instruct` | `HUGGINGFACE_API_KEY` | ❌ | ❌ |
| GitHub Models | `github_models.py` | 152 | `models.inference.ai.azure.com/chat/completions` | `gpt-4o-mini` | `GITHUB_TOKEN` | ✅ | ❌ |
| Fireworks | `fireworks.py` | 143 | `api.fireworks.ai/inference/v1/chat/completions` | `accounts/fireworks/models/llama-v3p3-70b-instruct` | `FIREWORKS_API_KEY` | ❌ | ❌ |
| Novita | `novita.py` | 143 | `api.novita.ai/v3/openai/chat/completions` | `meta-llama/llama-3.1-70b-instruct` | `NOVITA_API_KEY` | ❌ | ❌ |
| Kluster | `kluster.py` | 143 | `api.kluster.ai/v1/chat/completions` | `klusterai/Meta-Llama-3.3-70B-Instruct-Turbo` | `KLUSTER_API_KEY` | ❌ | ❌ |
| Scaleway | `scaleway.py` | 143 | `api.scaleway.ai/v1/chat/completions` | `llama-3.3-70b-instruct` | `SCALEWAY_API_KEY` | ❌ | ❌ |

### 2.2 Исключения (не подлежат рефакторингу)

| Провайдер | Файл | Строк | Причина исключения |
|-----------|------|-------|-------------------|
| Cloudflare | `cloudflare.py` | 180 | Полностью другой API формат |

**Детали Cloudflare:**
- Требует `account_id` помимо `api_token`
- Динамический URL: `{base}/accounts/{account_id}/ai/run/{model}`
- Модель НЕ передаётся в payload (часть URL)
- Другой формат ответа: `result["result"]["response"]`
- Нет `top_p` в payload

---

## 3. Анализ общих паттернов

### 3.1 Структура всех OpenAI-совместимых провайдеров

```python
# Все 12 провайдеров имеют идентичную структуру:

class ProviderNameProvider(AIProviderBase):
    def __init__(self, api_key: str | None = None, model: str | None = None):
        self.api_key = api_key or os.getenv("PROVIDER_API_KEY")
        self.model = model or "default-model-name"
        self.api_url = "https://api.provider.com/v1/chat/completions"
        self.timeout = 60.0
        # ❌ НЕТ валидации api_key в __init__

    async def generate(self, prompt: str, **kwargs) -> str:
        # Идентичный код во всех провайдерах
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": kwargs.get("max_tokens", 4096),
            "temperature": kwargs.get("temperature", 0.7),
            "top_p": kwargs.get("top_p", 0.9),
        }
        # httpx.AsyncClient + response parsing

    async def health_check(self) -> bool:
        # Идентичный код: GET /models с auth header

    def get_provider_name(self) -> str:
        return "provider_name"

    def _supports_response_format(self) -> bool:
        return False  # или True для 2 провайдеров
```

### 3.2 Идентичный код (копируется 12 раз)

| Блок кода | Строки | Описание |
|-----------|--------|----------|
| `__init__` body | ~8 | Инициализация атрибутов |
| `generate()` headers | ~4 | Формирование заголовков |
| `generate()` payload | ~8 | Формирование тела запроса |
| `generate()` httpx call | ~15 | HTTP запрос + error handling |
| `generate()` response parsing | ~10 | Парсинг ответа |
| `health_check()` | ~20 | Проверка здоровья |
| `_supports_response_format()` | ~3 | Флаг поддержки |

**Итого:** ~68 строк идентичного кода × 12 провайдеров = **~816 строк дублирования**

### 3.3 Различия между провайдерами (только конфигурация)

```python
# Различия сводятся к 5-6 константам:
PROVIDER_NAME = "groq"           # Строка для логов
BASE_URL = "https://..."         # URL для chat/completions
MODELS_URL = "https://.../models" # URL для health check
DEFAULT_MODEL = "llama-3.3-70b"  # Модель по умолчанию
API_KEY_ENV = "GROQ_API_KEY"     # Имя env-переменной
SUPPORTS_RESPONSE_FORMAT = False # Флаг
EXTRA_HEADERS = {}               # Только для OpenRouter
```

---

## 4. Особые случаи

### 4.1 OpenRouter — дополнительные заголовки

```python
# openrouter.py:60-66
headers = {
    "Authorization": f"Bearer {self.api_key}",
    "Content-Type": "application/json",
    "HTTP-Referer": "https://github.com/free-ai-selector",  # ← EXTRA
    "X-Title": "Free AI Selector",                          # ← EXTRA
}
```

**Решение:** Hook-метод `_build_headers()` в базовом классе.

### 4.2 HuggingFace — динамический URL

```python
# huggingface.py:35
# URL содержит {model}:
self.api_url = f"https://api-inference.huggingface.co/models/{self.model}/v1/chat/completions"
```

**Решение:** Параметр `url_template` с плейсхолдером `{model}`.

### 4.3 GitHub Models — особый health check

```python
# github_models.py:113
# Успех если статус < 500 (не строго 200):
return response.status_code < 500
```

**Решение:** Параметр `health_check_success_codes` или hook-метод.

### 4.4 Провайдеры с response_format

```python
# github_models.py, sambanova.py
def _supports_response_format(self) -> bool:
    return True
```

**Решение:** Параметр конфигурации `supports_response_format: bool`.

---

## 5. Предлагаемая архитектура

### 5.1 OpenAICompatibleProvider (базовый класс)

```python
# base.py — расширение существующего файла

class OpenAICompatibleProvider(AIProviderBase):
    """Базовый класс для OpenAI-совместимых провайдеров."""

    # Конфигурация (переопределяется в наследниках)
    PROVIDER_NAME: str = ""
    BASE_URL: str = ""
    MODELS_URL: str = ""
    DEFAULT_MODEL: str = ""
    API_KEY_ENV: str = ""
    SUPPORTS_RESPONSE_FORMAT: bool = False
    EXTRA_HEADERS: dict[str, str] = {}

    def __init__(self, api_key: str | None = None, model: str | None = None):
        self.api_key = api_key or os.getenv(self.API_KEY_ENV)
        if not self.api_key:
            raise ValueError(f"{self.API_KEY_ENV} is required")
        self.model = model or self.DEFAULT_MODEL
        self.api_url = self._build_url()
        self.timeout = 60.0

    def _build_url(self) -> str:
        """Hook для динамических URL (HuggingFace)."""
        return self.BASE_URL

    def _build_headers(self) -> dict[str, str]:
        """Hook для дополнительных заголовков (OpenRouter)."""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        headers.update(self.EXTRA_HEADERS)
        return headers

    def _build_payload(self, prompt: str, **kwargs) -> dict:
        """Hook для кастомизации payload."""
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": kwargs.get("max_tokens", 4096),
            "temperature": kwargs.get("temperature", 0.7),
            "top_p": kwargs.get("top_p", 0.9),
        }
        if self.SUPPORTS_RESPONSE_FORMAT and kwargs.get("response_format"):
            payload["response_format"] = kwargs["response_format"]
        return payload

    async def generate(self, prompt: str, **kwargs) -> str:
        """Единая реализация для всех OpenAI-совместимых провайдеров."""
        headers = self._build_headers()
        payload = self._build_payload(prompt, **kwargs)

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    self.api_url, headers=headers, json=payload
                )
                response.raise_for_status()
                result = response.json()
                return result["choices"][0]["message"]["content"]
        except httpx.HTTPError as e:
            raise ProviderError(f"{self.PROVIDER_NAME} error: {e}") from e

    async def health_check(self) -> bool:
        """Проверка здоровья через GET /models."""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    self.MODELS_URL,
                    headers={"Authorization": f"Bearer {self.api_key}"}
                )
                return self._is_health_check_success(response)
        except Exception:
            return False

    def _is_health_check_success(self, response: httpx.Response) -> bool:
        """Hook для кастомной проверки успеха (GitHub Models)."""
        return response.status_code == 200

    def get_provider_name(self) -> str:
        return self.PROVIDER_NAME

    def _supports_response_format(self) -> bool:
        return self.SUPPORTS_RESPONSE_FORMAT
```

### 5.2 Пример конфигурационного провайдера

```python
# groq.py — после рефакторинга (~15 строк вместо 143)

from .base import OpenAICompatibleProvider

class GroqProvider(OpenAICompatibleProvider):
    """Groq AI provider."""

    PROVIDER_NAME = "groq"
    BASE_URL = "https://api.groq.com/openai/v1/chat/completions"
    MODELS_URL = "https://api.groq.com/openai/v1/models"
    DEFAULT_MODEL = "llama-3.3-70b-versatile"
    API_KEY_ENV = "GROQ_API_KEY"
```

### 5.3 OpenRouter (с extra headers)

```python
# openrouter.py — после рефакторинга (~20 строк)

from .base import OpenAICompatibleProvider

class OpenRouterProvider(OpenAICompatibleProvider):
    """OpenRouter AI provider."""

    PROVIDER_NAME = "openrouter"
    BASE_URL = "https://openrouter.ai/api/v1/chat/completions"
    MODELS_URL = "https://openrouter.ai/api/v1/models"
    DEFAULT_MODEL = "meta-llama/llama-3.3-70b-instruct:free"
    API_KEY_ENV = "OPENROUTER_API_KEY"
    EXTRA_HEADERS = {
        "HTTP-Referer": "https://github.com/free-ai-selector",
        "X-Title": "Free AI Selector",
    }
```

### 5.4 HuggingFace (динамический URL)

```python
# huggingface.py — после рефакторинга (~20 строк)

from .base import OpenAICompatibleProvider

class HuggingFaceProvider(OpenAICompatibleProvider):
    """HuggingFace AI provider."""

    PROVIDER_NAME = "huggingface"
    BASE_URL = "https://api-inference.huggingface.co/models/{model}/v1/chat/completions"
    MODELS_URL = "https://api-inference.huggingface.co/models"
    DEFAULT_MODEL = "meta-llama/Llama-3.3-70B-Instruct"
    API_KEY_ENV = "HUGGINGFACE_API_KEY"

    def _build_url(self) -> str:
        return self.BASE_URL.format(model=self.model)
```

### 5.5 GitHub Models (особый health check)

```python
# github_models.py — после рефакторинга (~20 строк)

from .base import OpenAICompatibleProvider

class GitHubModelsProvider(OpenAICompatibleProvider):
    """GitHub Models AI provider."""

    PROVIDER_NAME = "github_models"
    BASE_URL = "https://models.inference.ai.azure.com/chat/completions"
    MODELS_URL = "https://models.inference.ai.azure.com/models"
    DEFAULT_MODEL = "gpt-4o-mini"
    API_KEY_ENV = "GITHUB_TOKEN"
    SUPPORTS_RESPONSE_FORMAT = True

    def _is_health_check_success(self, response) -> bool:
        return response.status_code < 500
```

---

## 6. Зависимости и риски

### 6.1 Зависимости

| Зависимость | Тип | Описание |
|-------------|-----|----------|
| F012 | Feature | Rate limit handling использует провайдеры |
| ProcessPromptUseCase | Code | Импортирует провайдеры |
| registry.py | Code | Регистрирует провайдеры |
| Тесты | Code | Unit-тесты провайдеров |

### 6.2 Риски

| # | Риск | Вероятность | Влияние | Митигация |
|---|------|-------------|---------|-----------|
| 1 | Изменение поведения | Low | High | 100% coverage unit-тестами |
| 2 | Пропуск edge case | Med | Med | Code review + integration tests |
| 3 | httpx.HTTPError не обёрнут | Low | Med | Единообразный try/except в base |
| 4 | Конфликт с F012 | Med | Med | Выполнять после F012 merge |

### 6.3 Блокеры

- **Нет критических блокеров**
- F012 (rate limit) должен быть завершён первым для избежания конфликтов

---

## 7. План реализации

### Этап 1: Создание базового класса
1. Добавить `OpenAICompatibleProvider` в `base.py`
2. Реализовать hook-методы: `_build_url()`, `_build_headers()`, `_build_payload()`
3. Добавить валидацию API key в `__init__`
4. Обернуть `httpx.HTTPError` в `ProviderError`

### Этап 2: Миграция провайдеров (по одному)
1. `groq.py` — template для остальных
3. `sambanova.py` — с `SUPPORTS_RESPONSE_FORMAT = True`
4. `openrouter.py` — с `EXTRA_HEADERS`
5. `huggingface.py` — с `_build_url()` override
6. `github_models.py` — с `_is_health_check_success()` override

### Этап 3: Cloudflare
- **НЕ ТРОГАТЬ** — остаётся как есть

### Этап 4: Тестирование
1. Запустить существующие unit-тесты
2. Проверить health check всех провайдеров
3. Integration test с реальными API (manual)

---

## 8. Метрики успеха

| Метрика | До | После | Цель |
|---------|-----|-------|------|
| Строк кода (12 провайдеров) | ~1700 | ~200 | ≥80% сокращение |
| Дублирование | ~95% | ~5% | <10% |
| Cyclomatic complexity (generate) | 8-10 | 4-5 | <6 |
| Тесты проходят | 100% | 100% | 100% |

---

## 9. Выводы

1. **Рефакторинг целесообразен** — 12 из 13 провайдеров OpenAI-совместимы
2. **Cloudflare исключён** — принципиально другой API
3. **Hook-методы покрывают все различия** — `_build_url()`, `_build_headers()`, `_is_health_check_success()`
4. **Ожидаемое сокращение ~1100 строк** — соответствует PRD
5. **Риски управляемы** — митигация через тесты и code review

---

## Качественные ворота

### RESEARCH_DONE Checklist

- [x] Все провайдеры проанализированы (14 файлов)
- [x] Матрица конфигурации составлена
- [x] Общие паттерны выявлены
- [x] Различия классифицированы
- [x] Hook-методы определены
- [x] Риски идентифицированы
- [x] План реализации составлен
- [x] Cloudflare исключение задокументировано
