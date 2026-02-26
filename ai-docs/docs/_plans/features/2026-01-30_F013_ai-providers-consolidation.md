---
feature_id: "F013"
feature_name: "ai-providers-consolidation"
title: "Implementation Plan: AI Providers Consolidation"
created: "2026-01-30"
author: "AI (Architect)"
type: "implementation-plan"
status: "PENDING_APPROVAL"
version: 1

services_affected: 1
files_to_create: 0
files_to_modify: 13
estimated_loc_reduction: 1100
breaking_changes: false
db_migration_required: false
---

# Implementation Plan: AI Providers Consolidation

**Feature ID**: F013
**Дата**: 2026-01-30
**Автор**: AI Agent (Архитектор)
**Статус**: PENDING_APPROVAL

---

## 1. Обзор

### 1.1 Цель

Рефакторинг AI провайдеров для устранения ~1100 строк дублирования:
- Создать `OpenAICompatibleProvider` базовый класс в `base.py`
- Конвертировать 12 OpenAI-совместимых провайдеров в конфигурационные классы
- Добавить валидацию API key в `__init__`
- Обернуть `httpx.HTTPError` в `ProviderError`

### 1.2 Scope

| В scope | Вне scope |
|---------|-----------|
| 12 OpenAI-compatible провайдеров | Cloudflare (не OpenAI-compatible) |
| base.py расширение | Новые провайдеры |
| Существующие тесты | Изменения API контрактов |

### 1.3 Связь с существующим функционалом

- **F011-B**: Использует `system_prompt` и `response_format` — сохраняем поддержку
- **F012**: Использует провайдеры через `ProcessPromptUseCase` — интерфейс не меняется
- **registry.py**: Импорты классов — обновить при необходимости

---

## 2. Анализ существующего кода

### 2.1 Затронутые файлы

| Файл | Строк | Действие |
|------|-------|----------|
| `base.py` | 59 | Расширить: добавить `OpenAICompatibleProvider` |
| `groq.py` | 157 | Упростить до ~20 строк |
| `cerebras.py` | 141 | Упростить до ~15 строк |
| `sambanova.py` | 151 | Упростить до ~15 строк |
| `deepseek.py` | 143 | Упростить до ~15 строк |
| `openrouter.py` | 162 | Упростить до ~20 строк (extra headers) |
| `hyperbolic.py` | 143 | Упростить до ~15 строк |
| `huggingface.py` | 143 | Упростить до ~20 строк (dynamic URL) |
| `github_models.py` | 152 | Упростить до ~20 строк (health check) |
| `fireworks.py` | 143 | Упростить до ~15 строк |
| `novita.py` | 143 | Упростить до ~15 строк |
| `kluster.py` | 143 | Упростить до ~15 строк |
| `scaleway.py` | 143 | Упростить до ~15 строк |

**Итого**: 1820 строк → ~250 строк (~86% сокращение)

### 2.2 Точки интеграции

```
ProcessPromptUseCase
        │
        ▼
ProviderRegistry.get_provider(name)
        │
        ▼
PROVIDER_CLASSES[name]()  ← Возвращает экземпляр провайдера
        │
        ▼
provider.generate(prompt, **kwargs)
```

**Ключевое**: Интерфейс `AIProviderBase` не меняется — `generate()`, `health_check()`, `get_provider_name()`.

### 2.3 Существующие зависимости

```python
# Все провайдеры используют:
import httpx                    # HTTP клиент
import os                       # Environment variables
import logging                  # Логирование
from app.utils.security import sanitize_error_message  # Очистка ошибок
from app.infrastructure.ai_providers.base import AIProviderBase  # Базовый класс
```

---

## 3. План изменений

### 3.1 Этап 1: Расширение base.py

**Файл**: `services/free-ai-selector-business-api/app/infrastructure/ai_providers/base.py`

**Добавить** класс `OpenAICompatibleProvider` (~120 строк):

```python
import logging
import os
from typing import ClassVar, Optional

import httpx

from app.domain.exceptions import ProviderError
from app.utils.security import sanitize_error_message

logger = logging.getLogger(__name__)


class OpenAICompatibleProvider(AIProviderBase):
    """
    Базовый класс для OpenAI-совместимых провайдеров.

    Наследники определяют только class-level конфигурацию.
    Вся логика generate/health_check унифицирована.
    """

    # === Конфигурация (переопределяется в наследниках) ===
    PROVIDER_NAME: ClassVar[str] = ""
    BASE_URL: ClassVar[str] = ""  # chat/completions endpoint
    MODELS_URL: ClassVar[str] = ""  # health check endpoint
    DEFAULT_MODEL: ClassVar[str] = ""
    API_KEY_ENV: ClassVar[str] = ""
    SUPPORTS_RESPONSE_FORMAT: ClassVar[bool] = False
    EXTRA_HEADERS: ClassVar[dict[str, str]] = {}
    TIMEOUT: ClassVar[float] = 30.0

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        """
        Инициализация провайдера с валидацией API key.

        Args:
            api_key: API ключ (или из env)
            model: Модель (или default)

        Raises:
            ValueError: Если API key отсутствует
        """
        self.api_key = api_key or os.getenv(self.API_KEY_ENV, "")
        if not self.api_key:
            raise ValueError(f"{self.API_KEY_ENV} is required")

        self.model = model or self.DEFAULT_MODEL
        self.api_url = self._build_url()
        self.timeout = self.TIMEOUT

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
        """Формирование payload для OpenAI API."""
        # F011-B: Extract system_prompt and response_format
        system_prompt = kwargs.get("system_prompt")
        response_format = kwargs.get("response_format")

        # Build messages array
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": self.model,
            "messages": messages,
            "max_tokens": kwargs.get("max_tokens", 512),
            "temperature": kwargs.get("temperature", 0.7),
            "top_p": kwargs.get("top_p", 0.9),
        }

        # F011-B: Add response_format if supported
        if response_format:
            if self.SUPPORTS_RESPONSE_FORMAT:
                payload["response_format"] = response_format
            else:
                logger.warning(
                    "response_format_not_supported",
                    extra={"provider": self.PROVIDER_NAME, "requested_format": response_format},
                )

        return payload

    def _parse_response(self, result: dict) -> str:
        """Парсинг OpenAI-совместимого ответа."""
        if "choices" in result and len(result["choices"]) > 0:
            message = result["choices"][0].get("message", {})
            content = message.get("content", "")
            if isinstance(content, list):
                content = " ".join(str(item) for item in content)
            return str(content).strip()
        else:
            logger.error(f"Unexpected {self.PROVIDER_NAME} response: {sanitize_error_message(str(result))}")
            raise ValueError(f"Invalid response format from {self.PROVIDER_NAME}")

    async def generate(self, prompt: str, **kwargs) -> str:
        """
        Генерация ответа через OpenAI-совместимый API.

        Args:
            prompt: Пользовательский промпт
            **kwargs: system_prompt, response_format, max_tokens, temperature, top_p

        Returns:
            Сгенерированный текст

        Raises:
            ProviderError: При ошибках API
        """
        headers = self._build_headers()
        payload = self._build_payload(prompt, **kwargs)

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.post(self.api_url, headers=headers, json=payload)
                response.raise_for_status()
                result = response.json()
                return self._parse_response(result)

            except httpx.HTTPError as e:
                logger.error(f"{self.PROVIDER_NAME} API error: {sanitize_error_message(e)}")
                raise ProviderError(f"{self.PROVIDER_NAME} error: {e}") from e

    def _is_health_check_success(self, response: httpx.Response) -> bool:
        """Hook для кастомной проверки успеха (GitHub Models)."""
        return response.status_code == 200

    async def health_check(self) -> bool:
        """Проверка здоровья через GET /models."""
        headers = {"Authorization": f"Bearer {self.api_key}"}

        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                response = await client.get(self.MODELS_URL, headers=headers)
                return self._is_health_check_success(response)
            except Exception as e:
                logger.error(f"{self.PROVIDER_NAME} health check failed: {sanitize_error_message(e)}")
                return False

    def get_provider_name(self) -> str:
        """Имя провайдера для логирования."""
        return self.PROVIDER_NAME

    def _supports_response_format(self) -> bool:
        """Поддержка response_format (F011-B)."""
        return self.SUPPORTS_RESPONSE_FORMAT
```

### 3.2 Этап 2: Простые провайдеры (9 штук)

Конвертировать в конфигурационные классы (~15 строк каждый):

#### groq.py

```python
"""Groq AI Provider — ultra-fast LPU inference."""

from app.infrastructure.ai_providers.base import OpenAICompatibleProvider


class GroqProvider(OpenAICompatibleProvider):
    """Groq API provider (OpenAI-compatible)."""

    PROVIDER_NAME = "Groq"
    BASE_URL = "https://api.groq.com/openai/v1/chat/completions"
    MODELS_URL = "https://api.groq.com/openai/v1/models"
    DEFAULT_MODEL = "llama-3.3-70b-versatile"
    API_KEY_ENV = "GROQ_API_KEY"
    SUPPORTS_RESPONSE_FORMAT = False
```

#### cerebras.py

```python
"""Cerebras AI Provider — wafer-scale inference."""

from app.infrastructure.ai_providers.base import OpenAICompatibleProvider


class CerebrasProvider(OpenAICompatibleProvider):
    """Cerebras API provider (OpenAI-compatible)."""

    PROVIDER_NAME = "Cerebras"
    BASE_URL = "https://api.cerebras.ai/v1/chat/completions"
    MODELS_URL = "https://api.cerebras.ai/v1/models"
    DEFAULT_MODEL = "llama-3.3-70b"
    API_KEY_ENV = "CEREBRAS_API_KEY"
    SUPPORTS_RESPONSE_FORMAT = False
```

#### deepseek.py

```python
"""DeepSeek AI Provider — Chinese LLM."""

from app.infrastructure.ai_providers.base import OpenAICompatibleProvider


class DeepSeekProvider(OpenAICompatibleProvider):
    """DeepSeek API provider (OpenAI-compatible)."""

    PROVIDER_NAME = "DeepSeek"
    BASE_URL = "https://api.deepseek.com/chat/completions"
    MODELS_URL = "https://api.deepseek.com/models"
    DEFAULT_MODEL = "deepseek-chat"
    API_KEY_ENV = "DEEPSEEK_API_KEY"
    SUPPORTS_RESPONSE_FORMAT = False
```

#### fireworks.py

```python
"""Fireworks AI Provider."""

from app.infrastructure.ai_providers.base import OpenAICompatibleProvider


class FireworksProvider(OpenAICompatibleProvider):
    """Fireworks API provider (OpenAI-compatible)."""

    PROVIDER_NAME = "Fireworks"
    BASE_URL = "https://api.fireworks.ai/inference/v1/chat/completions"
    MODELS_URL = "https://api.fireworks.ai/inference/v1/models"
    DEFAULT_MODEL = "accounts/fireworks/models/llama-v3p3-70b-instruct"
    API_KEY_ENV = "FIREWORKS_API_KEY"
    SUPPORTS_RESPONSE_FORMAT = False
```

#### hyperbolic.py

```python
"""Hyperbolic AI Provider."""

from app.infrastructure.ai_providers.base import OpenAICompatibleProvider


class HyperbolicProvider(OpenAICompatibleProvider):
    """Hyperbolic API provider (OpenAI-compatible)."""

    PROVIDER_NAME = "Hyperbolic"
    BASE_URL = "https://api.hyperbolic.xyz/v1/chat/completions"
    MODELS_URL = "https://api.hyperbolic.xyz/v1/models"
    DEFAULT_MODEL = "meta-llama/Llama-3.3-70B-Instruct"
    API_KEY_ENV = "HYPERBOLIC_API_KEY"
    SUPPORTS_RESPONSE_FORMAT = False
```

#### novita.py

```python
"""Novita AI Provider."""

from app.infrastructure.ai_providers.base import OpenAICompatibleProvider


class NovitaProvider(OpenAICompatibleProvider):
    """Novita API provider (OpenAI-compatible)."""

    PROVIDER_NAME = "Novita"
    BASE_URL = "https://api.novita.ai/v3/openai/chat/completions"
    MODELS_URL = "https://api.novita.ai/v3/openai/models"
    DEFAULT_MODEL = "meta-llama/llama-3.1-70b-instruct"
    API_KEY_ENV = "NOVITA_API_KEY"
    SUPPORTS_RESPONSE_FORMAT = False
```

#### kluster.py

```python
"""Kluster AI Provider."""

from app.infrastructure.ai_providers.base import OpenAICompatibleProvider


class KlusterProvider(OpenAICompatibleProvider):
    """Kluster API provider (OpenAI-compatible)."""

    PROVIDER_NAME = "Kluster"
    BASE_URL = "https://api.kluster.ai/v1/chat/completions"
    MODELS_URL = "https://api.kluster.ai/v1/models"
    DEFAULT_MODEL = "klusterai/Meta-Llama-3.3-70B-Instruct-Turbo"
    API_KEY_ENV = "KLUSTER_API_KEY"
    SUPPORTS_RESPONSE_FORMAT = False
```


```python

from app.infrastructure.ai_providers.base import OpenAICompatibleProvider



    DEFAULT_MODEL = "meta-llama/Meta-Llama-3.1-70B-Instruct"
    SUPPORTS_RESPONSE_FORMAT = False
```

#### scaleway.py

```python
"""Scaleway AI Provider."""

from app.infrastructure.ai_providers.base import OpenAICompatibleProvider


class ScalewayProvider(OpenAICompatibleProvider):
    """Scaleway API provider (OpenAI-compatible)."""

    PROVIDER_NAME = "Scaleway"
    BASE_URL = "https://api.scaleway.ai/v1/chat/completions"
    MODELS_URL = "https://api.scaleway.ai/v1/models"
    DEFAULT_MODEL = "llama-3.3-70b-instruct"
    API_KEY_ENV = "SCALEWAY_API_KEY"
    SUPPORTS_RESPONSE_FORMAT = False
```

### 3.3 Этап 3: Провайдеры с response_format (2 штуки)

#### sambanova.py

```python
"""SambaNova AI Provider — supports response_format."""

from app.infrastructure.ai_providers.base import OpenAICompatibleProvider


class SambanovaProvider(OpenAICompatibleProvider):
    """SambaNova API provider (OpenAI-compatible)."""

    PROVIDER_NAME = "SambaNova"
    BASE_URL = "https://api.sambanova.ai/v1/chat/completions"
    MODELS_URL = "https://api.sambanova.ai/v1/models"
    DEFAULT_MODEL = "Meta-Llama-3.1-405B-Instruct"
    API_KEY_ENV = "SAMBANOVA_API_KEY"
    SUPPORTS_RESPONSE_FORMAT = True  # ← Поддерживает response_format
```

#### github_models.py (+ custom health check)

```python
"""GitHub Models AI Provider — supports response_format, custom health check."""

import httpx

from app.infrastructure.ai_providers.base import OpenAICompatibleProvider


class GitHubModelsProvider(OpenAICompatibleProvider):
    """GitHub Models API provider (OpenAI-compatible)."""

    PROVIDER_NAME = "GitHubModels"
    BASE_URL = "https://models.inference.ai.azure.com/chat/completions"
    MODELS_URL = "https://models.inference.ai.azure.com/models"
    DEFAULT_MODEL = "gpt-4o-mini"
    API_KEY_ENV = "GITHUB_TOKEN"
    SUPPORTS_RESPONSE_FORMAT = True  # ← Поддерживает response_format

    def _is_health_check_success(self, response: httpx.Response) -> bool:
        """GitHub Models возвращает < 500 при успехе."""
        return response.status_code < 500
```

### 3.4 Этап 4: Провайдеры с кастомизацией (2 штуки)

#### openrouter.py (extra headers)

```python
"""OpenRouter AI Provider — requires extra headers."""

from app.infrastructure.ai_providers.base import OpenAICompatibleProvider


class OpenRouterProvider(OpenAICompatibleProvider):
    """OpenRouter API provider (OpenAI-compatible with extra headers)."""

    PROVIDER_NAME = "OpenRouter"
    BASE_URL = "https://openrouter.ai/api/v1/chat/completions"
    MODELS_URL = "https://openrouter.ai/api/v1/models"
    DEFAULT_MODEL = "meta-llama/llama-3.3-70b-instruct:free"
    API_KEY_ENV = "OPENROUTER_API_KEY"
    SUPPORTS_RESPONSE_FORMAT = False
    EXTRA_HEADERS = {
        "HTTP-Referer": "https://github.com/free-ai-selector",
        "X-Title": "Free AI Selector",
    }
```

#### huggingface.py (dynamic URL)

```python
"""HuggingFace AI Provider — dynamic URL with model in path."""

from app.infrastructure.ai_providers.base import OpenAICompatibleProvider


class HuggingFaceProvider(OpenAICompatibleProvider):
    """HuggingFace API provider (OpenAI-compatible with dynamic URL)."""

    PROVIDER_NAME = "HuggingFace"
    BASE_URL = "https://api-inference.huggingface.co/models/{model}/v1/chat/completions"
    MODELS_URL = "https://api-inference.huggingface.co/models"
    DEFAULT_MODEL = "meta-llama/Llama-3.3-70B-Instruct"
    API_KEY_ENV = "HUGGINGFACE_API_KEY"
    SUPPORTS_RESPONSE_FORMAT = False

    def _build_url(self) -> str:
        """Динамический URL с моделью в path."""
        return self.BASE_URL.format(model=self.model)
```

### 3.5 Этап 5: Cloudflare (НЕ ТРОГАТЬ)

**Файл**: `cloudflare.py` — остаётся без изменений (180 строк).

**Причина**: Полностью другой API формат:
- Требует `account_id`
- Модель в URL, не в payload
- Другой формат ответа

---

## 4. Влияние на существующие тесты

### 4.1 Существующие тесты провайдеров

```
tests/unit/test_ai_providers/  # Если существует
```

**Ожидаемое поведение**:
- Интерфейс `AIProviderBase` не меняется
- Публичные методы сохраняют сигнатуры
- Тесты должны проходить без изменений

### 4.2 Изменение: ValueError → ProviderError

**До**: `httpx.HTTPError` пробрасывался как есть
**После**: Оборачивается в `ProviderError`

**Влияние**: Тесты, проверяющие конкретные исключения, могут потребовать обновления.

### 4.3 Изменение: Валидация API key в __init__

**До**: `ValueError` только в `generate()` при пустом ключе
**После**: `ValueError` в `__init__`

**Влияние**: Тесты, создающие провайдера без ключа, получат исключение раньше.

---

## 5. Зависимости

### 5.1 Новые импорты в base.py

```python
from app.domain.exceptions import ProviderError  # Существует, добавлен в F012
```

### 5.2 Проверка ProviderError

```bash
grep -r "class ProviderError" services/free-ai-selector-business-api/
```

Если не существует — создать в `app/domain/exceptions.py`:

```python
class ProviderError(Exception):
    """Ошибка AI провайдера."""
    pass
```

---

## 6. План интеграции

| # | Шаг | Зависимости | Тесты |
|---|-----|-------------|-------|
| 1 | Проверить/создать ProviderError | — | — |
| 2 | Расширить base.py | ProviderError | Unit tests |
| 3 | Конвертировать groq.py | base.py | Smoke test |
| 4 | Конвертировать остальные простые (8) | groq.py OK | — |
| 5 | Конвертировать sambanova.py, github_models.py | Этап 4 | — |
| 6 | Конвертировать openrouter.py, huggingface.py | Этап 5 | — |
| 7 | Запустить все тесты | Все этапы | Full suite |
| 8 | Health check всех провайдеров | Этап 7 | Manual |

---

## 7. Риски и митигация

| # | Риск | Вероятность | Влияние | Митигация |
|---|------|-------------|---------|-----------|
| 1 | Изменение поведения | Low | High | Unit tests для каждого провайдера |
| 2 | ProviderError не существует | Low | Med | Создать при необходимости |
| 3 | Тесты ломаются из-за ValueError в __init__ | Med | Low | Обновить тесты |
| 4 | Конфликт с F012 | Med | Med | Выполнять после F012 merge |

---

## 8. Метрики успеха

| Метрика | До | После | Цель |
|---------|-----|-------|------|
| Строк кода (12 провайдеров) | 1820 | ~250 | ≥80% сокращение |
| Дублирование | ~95% | ~5% | <10% |
| Тесты проходят | 100% | 100% | 100% |
| Health checks | 14/14 OK | 14/14 OK | 100% |

---

## 9. Checklist для реализации

- [ ] Проверить наличие ProviderError в domain/exceptions.py
- [ ] Расширить base.py классом OpenAICompatibleProvider
- [ ] Конвертировать groq.py (template)
- [ ] Конвертировать cerebras.py
- [ ] Конвертировать deepseek.py
- [ ] Конвертировать fireworks.py
- [ ] Конвертировать hyperbolic.py
- [ ] Конвертировать novita.py
- [ ] Конвертировать kluster.py
- [ ] Конвертировать scaleway.py
- [ ] Конвертировать sambanova.py (response_format)
- [ ] Конвертировать github_models.py (response_format + health check)
- [ ] Конвертировать openrouter.py (extra headers)
- [ ] Конвертировать huggingface.py (dynamic URL)
- [ ] НЕ ТРОГАТЬ cloudflare.py
- [ ] Запустить unit tests
- [ ] Запустить health checks

---

## Качественные ворота

### PLAN_APPROVED Checklist

- [x] Интеграция с существующим кодом описана
- [x] Файлы для изменения определены (13)
- [x] Breaking changes: НЕТ (API контракты сохранены)
- [x] Миграции БД: НЕ ТРЕБУЮТСЯ
- [x] Риски идентифицированы
- [x] План интеграции составлен
- [ ] **Пользователь утвердил план** ← ТРЕБУЕТСЯ
