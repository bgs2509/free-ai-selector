---
# === YAML Frontmatter (машиночитаемые метаданные) ===
feature_id: "F008"
feature_name: "provider-registry-ssot"
title: "Feature Plan: Provider Registry SSOT"
created: "2025-12-31"
author: "AI (Architect)"
type: "feature-plan"
status: "PLAN_APPROVED"
version: 2
mode: "FEATURE"

# Ссылки на связанные артефакты
_analysis_ref: "_analysis/2025-12-31_F008_provider-registry-ssot-_analysis.md"
_research_ref: "_research/2025-12-31_F008_provider-registry-ssot-_research.md"

# Затрагиваемые сервисы
affected_services:
  modified:
    - free-ai-selector-data-postgres-api
    - free-ai-selector-business-api
    - free-ai-selector-health-worker
  created: []

related_features: [F003, F004]
approved_by: "user"
approved_at: "2025-12-31"
---

# План интеграции фичи: Provider Registry SSOT (v2.0)

**Feature ID**: F008
**Версия**: 2.0
**Дата**: 2025-12-31
**Автор**: AI Agent (Архитектор)
**Статус**: PLAN_APPROVED
**Режим**: FEATURE
**Связанный PRD**: 2025-12-31_F008_provider-registry-ssot-_analysis.md (v2.0)

---

## 1. Обзор фичи

### 1.1 Цель

Создать единый источник правды (SSOT) для конфигурации AI-провайдеров, используя **PostgreSQL как SSOT** (Вариант B). Все сервисы получают данные о провайдерах через Data API.

**Ключевые метрики:**
- Hardcoded источников: **8 мест → 2** (seed.py + registry class map)
- Файлов для добавления провайдера: **6+ → 2-3**
- Строк кода в health-worker/main.py: **~800 → ~200**

### 1.2 Архитектурный подход: Вариант B — DB как SSOT

```
┌───────────────────────────────────────────────────────────────┐
│                    seed.py (SSOT)                             │
│  - name, provider, api_endpoint                               │
│  - api_format (NEW)                                           │
│  - env_var (NEW)                                              │
└─────────────────────┬─────────────────────────────────────────┘
                      │
                      ▼
┌───────────────────────────────────────────────────────────────┐
│                  PostgreSQL (ai_models)                        │
│  + api_format VARCHAR(20)                                      │
│  + env_var VARCHAR(50)                                         │
└─────────────────────┬─────────────────────────────────────────┘
                      │
                      ▼
┌───────────────────────────────────────────────────────────────┐
│                     Data API                                   │
│  GET /api/v1/models → returns api_format, env_var              │
└─────────────────────┬─────────────────────────────────────────┘
                      │
        ┌─────────────┼─────────────┐
        ▼             ▼             ▼
┌─────────────┐ ┌─────────────┐ ┌─────────────┐
│telegram-bot │ │business-api │ │health-worker│
│ (уже готов) │ │+Registry    │ │+universal   │
│             │ │(class map)  │ │ checker     │
└─────────────┘ └─────────────┘ └─────────────┘
```

### 1.3 Scope

**В scope (все 8 hardcoded источников):**

| # | Источник | Действие | FR |
|---|----------|----------|-----|
| 1 | seed.py SEED_MODELS[] | Добавить api_format, env_var | FR-001 |
| 2 | process_prompt.py self.providers{} | Использовать ProviderRegistry | FR-005 |
| 3 | test_all_providers.py self.providers{} | Использовать Data API + Registry | FR-006 |
| 4 | test_all_providers.py model_names{} | Использовать model.name из Data API | FR-006 |
| 5 | health-worker 16 ENV VAR констант | Удалить, использовать model.env_var | FR-008 |
| 6 | health-worker 16 check_*() функций | Заменить на check_provider() | FR-007 |
| 7 | health-worker PROVIDER_CHECK_FUNCTIONS{} | Удалить, dispatch по api_format | FR-010 |
| 8 | health-worker configured_providers[] | Заменить на цикл по моделям из API | FR-009 |

**Вне scope:**
- Изменение классов провайдеров (`google_gemini.py`, etc.)
- telegram-bot (уже работает правильно)
- Обновление документации (отдельная фича)

---

## 2. Анализ существующей архитектуры

### 2.1 Текущая структура проекта

```
free-ai-selector/
├── services/
│   ├── free-ai-selector-data-postgres-api/  ← Stage 1: DB migration + seed.py
│   │   └── app/
│   │       ├── api/v1/routes/models.py       ← Update response schema
│   │       ├── domain/models.py              ← Add api_format, env_var
│   │       └── infrastructure/database/
│   │           ├── seed.py                   ← Add api_format, env_var
│   │           └── migrations/               ← New migration
│   │
│   ├── free-ai-selector-business-api/       ← Stage 2: ProviderRegistry
│   │   └── app/
│   │       ├── application/use_cases/
│   │       │   ├── process_prompt.py         ← Use ProviderRegistry
│   │       │   └── test_all_providers.py     ← Use Data API + Registry
│   │       └── infrastructure/ai_providers/
│   │           ├── registry.py               ← NEW: ProviderRegistry
│   │           └── ... (16 провайдеров)      ← Без изменений
│   │
│   ├── free-ai-selector-health-worker/      ← Stage 3: Universal checker
│   │   └── app/main.py                       ← Replace 500+ lines
│   │
│   └── free-ai-selector-telegram-bot/       ← Без изменений (эталон!)
│
└── docker-compose.yml                        ← Без изменений
```

### 2.2 Затрагиваемые сервисы

| Сервис | Тип изменения | Stage | Риск |
|--------|---------------|-------|------|
| `free-ai-selector-data-postgres-api` | DB migration + seed | Stage 1 | Низкий |
| `free-ai-selector-business-api` | ProviderRegistry + refactor | Stage 2 | Средний |
| `free-ai-selector-health-worker` | Full refactor | Stage 3 | Высокий |
| `free-ai-selector-telegram-bot` | Без изменений | — | — |

---

## 3. План интеграции по стадиям

### Stage 1: Database — Расширение схемы и seed.py (FR-001, FR-002, FR-003)

**Цель**: Добавить `api_format` и `env_var` в БД и seed.py

**Задачи**:

| # | Задача | Файлы | FR |
|---|--------|-------|-----|
| 1.1 | Создать Alembic миграцию | `migrations/versions/xxx_add_api_format_env_var.py` | FR-002 |
| 1.2 | Обновить domain model | `app/domain/models.py` | FR-002 |
| 1.3 | Обновить seed.py | `app/infrastructure/database/seed.py` | FR-001 |
| 1.4 | Обновить API schema | `app/api/v1/routes/models.py` | FR-003 |
| 1.5 | Обновить HTTP client в business-api | `DataAPIClient`, `AIModelInfo` | FR-003 |

**Миграция Alembic:**

```python
# migrations/versions/xxx_add_api_format_env_var.py

def upgrade():
    op.add_column('ai_models', sa.Column('api_format', sa.String(20), server_default='openai'))
    op.add_column('ai_models', sa.Column('env_var', sa.String(50), server_default=''))

def downgrade():
    op.drop_column('ai_models', 'api_format')
    op.drop_column('ai_models', 'env_var')
```

**seed.py — структура записи:**

```python
SEED_MODELS = [
    {
        "name": "Gemini 2.5 Flash",
        "provider": "GoogleGemini",
        "api_endpoint": "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent",
        "is_active": True,
        "api_format": "gemini",                    # NEW
        "env_var": "GOOGLE_AI_STUDIO_API_KEY",    # NEW
    },
    {
        "name": "Llama 3.3 70B Versatile",
        "provider": "Groq",
        "api_endpoint": "https://api.groq.com/openai/v1/chat/completions",
        "is_active": True,
        "api_format": "openai",
        "env_var": "GROQ_API_KEY",
    },
    # ... остальные 14 провайдеров
]
```

**Маппинг api_format для всех 16 провайдеров:**

| Provider | api_format | env_var |
|----------|------------|---------|
| GoogleGemini | gemini | GOOGLE_AI_STUDIO_API_KEY |
| Groq | openai | GROQ_API_KEY |
| Cerebras | openai | CEREBRAS_API_KEY |
| SambaNova | openai | SAMBANOVA_API_KEY |
| HuggingFace | huggingface | HUGGINGFACE_API_KEY |
| Cloudflare | cloudflare | CLOUDFLARE_API_KEY |
| DeepSeek | openai | DEEPSEEK_API_KEY |
| Cohere | cohere | COHERE_API_KEY |
| OpenRouter | openai | OPENROUTER_API_KEY |
| GitHubModels | openai | GITHUB_TOKEN |
| Fireworks | openai | FIREWORKS_API_KEY |
| Hyperbolic | openai | HYPERBOLIC_API_KEY |
| Novita | openai | NOVITA_API_KEY |
| Scaleway | openai | SCALEWAY_API_KEY |
| Kluster | openai | KLUSTER_API_KEY |

**Критерии завершения Stage 1:**
- [ ] Миграция создана и применена
- [ ] seed.py содержит api_format и env_var для всех 16 провайдеров
- [ ] GET /api/v1/models возвращает api_format и env_var
- [ ] AIModelInfo в business-api обновлён
- [ ] Все существующие тесты проходят

---

### Stage 2: Business API — ProviderRegistry и рефакторинг (FR-004, FR-005, FR-006)

**Цель**: Создать ProviderRegistry и использовать Data API для получения списка провайдеров

**Задачи**:

| # | Задача | Файлы | FR |
|---|--------|-------|-----|
| 2.1 | Создать registry.py | `infrastructure/ai_providers/registry.py` | FR-004 |
| 2.2 | Добавить unit тесты | `tests/unit/test_provider_registry.py` | NF-020 |
| 2.3 | Рефакторинг process_prompt.py | `use_cases/process_prompt.py` | FR-005 |
| 2.4 | Рефакторинг test_all_providers.py | `use_cases/test_all_providers.py` | FR-006 |
| 2.5 | Обновить unit тесты use cases | `tests/unit/test_*.py` | NF-021 |

**registry.py — полная реализация:**

```python
# services/free-ai-selector-business-api/app/infrastructure/ai_providers/registry.py

from typing import Optional

from app.infrastructure.ai_providers.base import AIProviderBase
from app.infrastructure.ai_providers.google_gemini import GoogleGeminiProvider
from app.infrastructure.ai_providers.groq import GroqProvider
from app.infrastructure.ai_providers.cerebras import CerebrasProvider
from app.infrastructure.ai_providers.sambanova import SambanovaProvider
from app.infrastructure.ai_providers.huggingface import HuggingFaceProvider
from app.infrastructure.ai_providers.cloudflare import CloudflareProvider
from app.infrastructure.ai_providers.deepseek import DeepSeekProvider
from app.infrastructure.ai_providers.cohere import CohereProvider
from app.infrastructure.ai_providers.openrouter import OpenRouterProvider
from app.infrastructure.ai_providers.github_models import GitHubModelsProvider
from app.infrastructure.ai_providers.fireworks import FireworksProvider
from app.infrastructure.ai_providers.hyperbolic import HyperbolicProvider
from app.infrastructure.ai_providers.novita import NovitaProvider
from app.infrastructure.ai_providers.scaleway import ScalewayProvider
from app.infrastructure.ai_providers.kluster import KlusterProvider


# Единственное место с маппингом name → class
PROVIDER_CLASSES: dict[str, type[AIProviderBase]] = {
    "GoogleGemini": GoogleGeminiProvider,
    "Groq": GroqProvider,
    "Cerebras": CerebrasProvider,
    "SambaNova": SambanovaProvider,
    "HuggingFace": HuggingFaceProvider,
    "Cloudflare": CloudflareProvider,
    "DeepSeek": DeepSeekProvider,
    "Cohere": CohereProvider,
    "OpenRouter": OpenRouterProvider,
    "GitHubModels": GitHubModelsProvider,
    "Fireworks": FireworksProvider,
    "Hyperbolic": HyperbolicProvider,
    "Novita": NovitaProvider,
    "Scaleway": ScalewayProvider,
    "Kluster": KlusterProvider,
}


class ProviderRegistry:
    """Фабрика для получения AI провайдеров (Singleton с lazy initialization)."""

    _instances: dict[str, AIProviderBase] = {}

    @classmethod
    def get_provider(cls, name: str) -> Optional[AIProviderBase]:
        """
        Получить provider instance (ленивая инициализация).

        Args:
            name: Имя провайдера (например, "GoogleGemini")

        Returns:
            Инициализированный провайдер или None если не найден
        """
        if name not in cls._instances:
            provider_class = PROVIDER_CLASSES.get(name)
            if provider_class:
                cls._instances[name] = provider_class()
        return cls._instances.get(name)

    @classmethod
    def get_all_provider_names(cls) -> list[str]:
        """Получить список всех зарегистрированных имён провайдеров."""
        return list(PROVIDER_CLASSES.keys())

    @classmethod
    def has_provider(cls, name: str) -> bool:
        """Проверить наличие класса провайдера в registry."""
        return name in PROVIDER_CLASSES

    @classmethod
    def reset(cls) -> None:
        """Сбросить кэш instances (для тестов)."""
        cls._instances.clear()
```

**process_prompt.py — БЫЛО:**

```python
# 16 imports
from app.infrastructure.ai_providers.google_gemini import GoogleGeminiProvider
# ... ещё 15 imports

class ProcessPromptUseCase:
    def __init__(self, data_api_client):
        self.data_api_client = data_api_client
        self.providers = {
            "GoogleGemini": GoogleGeminiProvider(),
            "Groq": GroqProvider(),
            # ... 16 hardcoded instances
        }

    async def execute(self, request):
        best_model = await self._select_best_model()
        provider = self.providers.get(best_model.provider)  # KeyError risk!
```

**process_prompt.py — СТАЛО:**

```python
from app.infrastructure.ai_providers.registry import ProviderRegistry

class ProcessPromptUseCase:
    def __init__(self, data_api_client):
        self.data_api_client = data_api_client
        # Нет hardcoded self.providers!

    async def execute(self, request):
        best_model = await self._select_best_model()
        provider = ProviderRegistry.get_provider(best_model.provider)
        if not provider:
            raise ValueError(f"Provider {best_model.provider} not configured in registry")
```

**test_all_providers.py — БЫЛО:**

```python
# 16 imports
# ...

class TestAllProvidersUseCase:
    def __init__(self, data_api_client):
        self.data_api_client = data_api_client
        self.providers = { ... }  # 16 hardcoded

    def _get_model_name(self, provider_name):
        model_names = {
            "GoogleGemini": "Gemini 2.5 Flash",
            # ... 16 hardcoded
        }
        return model_names.get(provider_name)

    async def execute(self):
        for name, provider in self.providers.items():
            # Тестирует только hardcoded провайдеров!
```

**test_all_providers.py — СТАЛО:**

```python
from app.infrastructure.ai_providers.registry import ProviderRegistry

class TestAllProvidersUseCase:
    def __init__(self, data_api_client):
        self.data_api_client = data_api_client
        # Нет hardcoded providers и model_names!

    async def execute(self):
        # Получаем провайдеров из Data API (как telegram-bot)
        models = await self.data_api_client.get_all_models()

        results = []
        for model in models:
            provider = ProviderRegistry.get_provider(model.provider)
            if provider:
                result = await self._test_provider(
                    provider_name=model.provider,
                    provider=provider,
                    model_name=model.name  # Из БД, не hardcoded!
                )
                results.append(result)
            else:
                # Провайдер в БД, но нет класса в registry
                results.append({
                    "provider": model.provider,
                    "model": model.name,
                    "status": "error",
                    "error": "Provider class not found in registry"
                })

        return sorted(results, key=lambda r: (r["status"] != "success", r.get("response_time") or float("inf")))
```

**Критерии завершения Stage 2:**
- [ ] registry.py создан с 16 провайдерами
- [ ] process_prompt.py использует ProviderRegistry
- [ ] test_all_providers.py использует Data API + ProviderRegistry
- [ ] Удалены все hardcoded imports из use cases (кроме registry)
- [ ] `make test-business` — 0 регрессий

---

### Stage 3: Health Worker — Универсальный checker (FR-007, FR-008, FR-009, FR-010)

**Цель**: Заменить ~500 строк hardcoded кода на универсальный checker

**Задачи**:

| # | Задача | Действие | FR |
|---|--------|----------|-----|
| 3.1 | Удалить 16 ENV VAR констант | Строки 49-68 | FR-008 |
| 3.2 | Создать 5 helper функций | `_check_openai_format`, `_check_gemini_format`, etc. | FR-013 |
| 3.3 | Создать `check_provider()` | Универсальный checker | FR-007 |
| 3.4 | Удалить 16 check_*() функций | Строки 82-556 | FR-007 |
| 3.5 | Удалить PROVIDER_CHECK_FUNCTIONS{} | Строки 562-581 | FR-010 |
| 3.6 | Рефакторинг configured_providers | Строки 695-729 | FR-009 |
| 3.7 | Рефакторинг run_health_checks() | Использовать Data API | — |

**health-worker/main.py — БЫЛО (~800 строк):**

```python
# 16 ENV VAR констант (строки 49-68)
GOOGLE_AI_STUDIO_API_KEY = os.getenv("GOOGLE_AI_STUDIO_API_KEY", "")
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
# ... ещё 14

# 16 check_*() функций (строки 82-556, ~480 строк)
async def check_google_gemini(endpoint: str) -> tuple[bool, float]:
    if not GOOGLE_AI_STUDIO_API_KEY:
        return False, 0.0
    # ... ~25 строк Gemini-specific

async def check_groq(endpoint: str) -> tuple[bool, float]:
    if not GROQ_API_KEY:
        return False, 0.0
    # ... ~25 строк OpenAI-compatible
# ... ещё 14 функций

# PROVIDER_CHECK_FUNCTIONS{} (строки 562-581)
PROVIDER_CHECK_FUNCTIONS = {
    "GoogleGemini": check_google_gemini,
    "Groq": check_groq,
    # ... 16 entries
}

# configured_providers[] (строки 695-729)
configured_providers = []
if GOOGLE_AI_STUDIO_API_KEY:
    configured_providers.append("GoogleGemini")
if GROQ_API_KEY:
    configured_providers.append("Groq")
# ... 16 if blocks
```

**health-worker/main.py — СТАЛО (~200 строк):**

```python
import os
import time
import httpx
from app.utils.logger import get_logger
from app.utils.security import sanitize_error_message

logger = get_logger(__name__)


# === Helper функции для разных API форматов ===

async def _check_openai_format(client: httpx.AsyncClient, model: dict, api_key: str) -> httpx.Response:
    """OpenAI-compatible format (Groq, Cerebras, DeepSeek, etc.)."""
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": model.get("default_model", ""),
        "messages": [{"role": "user", "content": "Hi"}],
        "max_tokens": 5
    }
    return await client.post(model["api_endpoint"], headers=headers, json=payload)


async def _check_gemini_format(client: httpx.AsyncClient, model: dict, api_key: str) -> httpx.Response:
    """Google Gemini format."""
    url = f"{model['api_endpoint']}?key={api_key}"
    payload = {
        "contents": [{"parts": [{"text": "Hi"}]}]
    }
    return await client.post(url, json=payload)


async def _check_cohere_format(client: httpx.AsyncClient, model: dict, api_key: str) -> httpx.Response:
    """Cohere format."""
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    payload = {
        "message": "Hi",
        "max_tokens": 5
    }
    return await client.post(model["api_endpoint"], headers=headers, json=payload)


async def _check_huggingface_format(client: httpx.AsyncClient, model: dict, api_key: str) -> httpx.Response:
    """HuggingFace Inference API format."""
    headers = {"Authorization": f"Bearer {api_key}"}
    payload = {"inputs": "Hi"}
    return await client.post(model["api_endpoint"], headers=headers, json=payload)


async def _check_cloudflare_format(client: httpx.AsyncClient, model: dict, api_key: str) -> httpx.Response:
    """Cloudflare Workers AI format."""
    account_id = os.getenv("CLOUDFLARE_ACCOUNT_ID", "")
    headers = {"Authorization": f"Bearer {api_key}"}
    payload = {
        "messages": [{"role": "user", "content": "Hi"}],
        "max_tokens": 5
    }
    endpoint = model["api_endpoint"].replace("{account_id}", account_id)
    return await client.post(endpoint, headers=headers, json=payload)


# === Универсальный health checker ===

async def check_provider(model: dict) -> tuple[bool, float]:
    """
    Универсальный health check для любого провайдера.

    Args:
        model: Словарь с полями из Data API:
            - provider: str (например, "GoogleGemini")
            - api_endpoint: str
            - api_format: str ("openai", "gemini", "cohere", "huggingface", "cloudflare")
            - env_var: str (например, "GOOGLE_AI_STUDIO_API_KEY")

    Returns:
        tuple[bool, float]: (is_healthy, response_time_seconds)
    """
    # Получаем API key динамически
    api_key = os.getenv(model["env_var"], "")
    if not api_key:
        logger.warning("provider_api_key_missing", provider=model["provider"], env_var=model["env_var"])
        return False, 0.0

    start_time = time.time()
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            api_format = model.get("api_format", "openai")

            # Dispatch по api_format из БД
            if api_format == "openai":
                response = await _check_openai_format(client, model, api_key)
            elif api_format == "gemini":
                response = await _check_gemini_format(client, model, api_key)
            elif api_format == "cohere":
                response = await _check_cohere_format(client, model, api_key)
            elif api_format == "huggingface":
                response = await _check_huggingface_format(client, model, api_key)
            elif api_format == "cloudflare":
                response = await _check_cloudflare_format(client, model, api_key)
            else:
                # Fallback to openai format
                response = await _check_openai_format(client, model, api_key)

            elapsed = time.time() - start_time
            is_healthy = response.status_code == 200

            if is_healthy:
                logger.info("health_check_success", provider=model["provider"], response_time=elapsed)
            else:
                logger.warning("health_check_failed_status", provider=model["provider"], status=response.status_code)

            return is_healthy, elapsed

    except Exception as e:
        elapsed = time.time() - start_time
        logger.error("health_check_exception", provider=model["provider"], error=sanitize_error_message(e))
        return False, elapsed


# === Получение configured providers (динамически) ===

async def get_configured_providers(models: list[dict]) -> list[str]:
    """
    Получить список провайдеров с настроенными API ключами.

    Args:
        models: Список моделей из Data API

    Returns:
        Список имён провайдеров с непустыми API ключами
    """
    configured = []
    for model in models:
        env_var = model.get("env_var", "")
        if env_var and os.getenv(env_var):
            configured.append(model["provider"])
    return configured


# === Main health check job ===

async def run_health_checks():
    """Запуск проверок здоровья для всех провайдеров из Data API."""
    # Получаем список моделей из Data API (как telegram-bot)
    models = await data_api_client.get_all_models()

    # Логируем configured providers
    configured = await get_configured_providers(models)
    logger.info("health_check_start", total_models=len(models), configured_count=len(configured))

    for model in models:
        # Проверяем только провайдеров с API ключами
        if model["provider"] not in configured:
            logger.debug("health_check_skip", provider=model["provider"], reason="no_api_key")
            continue

        # Выполняем health check
        is_healthy, response_time = await check_provider(model)

        # Обновляем статистику в БД
        try:
            if is_healthy:
                await data_api_client.increment_success(model["id"], response_time)
            else:
                await data_api_client.increment_failure(model["id"], response_time)
        except Exception as e:
            logger.error("health_check_stats_update_failed", provider=model["provider"], error=str(e))

    logger.info("health_check_complete", total_checked=len(configured))
```

**Критерии завершения Stage 3:**
- [ ] 16 ENV VAR констант удалены
- [ ] 16 check_*() функций заменены на 1 check_provider() + 5 helpers
- [ ] PROVIDER_CHECK_FUNCTIONS{} удалён
- [ ] configured_providers использует цикл по моделям из API
- [ ] health-worker/main.py уменьшился с ~800 до ~200 строк
- [ ] `make health` показывает все провайдеры healthy

---

### Stage 4: Тестирование интеграции

**Цель**: Убедиться что рефакторинг не сломал существующий функционал

**Задачи**:

| # | Задача | Команда |
|---|--------|---------|
| 4.1 | Unit тесты data-api | `make test-data` |
| 4.2 | Unit тесты business-api | `make test-business` |
| 4.3 | Lint проверки | `make lint` |
| 4.4 | Health checks | `make health` |
| 4.5 | Integration test /test endpoint | `curl localhost:8000/api/v1/providers/test` |
| 4.6 | Integration test /stats endpoint | `curl localhost:8000/api/v1/models/stats` |

**Критерии завершения Stage 4:**
- [ ] `make test` — 0 failures
- [ ] `make lint` — 0 errors
- [ ] `make health` — все контейнеры healthy
- [ ] `/test` тестирует все 16 провайдеров
- [ ] `/stats` показывает статистику для всех 16 провайдеров

---

## 4. Трассировка требований

| FR | Stage | Задача | Файл | Тест |
|----|-------|--------|------|------|
| FR-001 | 1 | 1.3 | seed.py | test_seed.py |
| FR-002 | 1 | 1.1, 1.2 | migrations/, models.py | test_models.py |
| FR-003 | 1 | 1.4, 1.5 | routes/models.py, DataAPIClient | test_api.py |
| FR-004 | 2 | 2.1 | registry.py | test_provider_registry.py |
| FR-005 | 2 | 2.3 | process_prompt.py | test_process_prompt.py |
| FR-006 | 2 | 2.4 | test_all_providers.py | test_test_providers.py |
| FR-007 | 3 | 3.3, 3.4 | main.py | integration test |
| FR-008 | 3 | 3.1 | main.py | integration test |
| FR-009 | 3 | 3.6 | main.py | integration test |
| FR-010 | 3 | 3.5 | main.py | integration test |
| FR-011 | 3 | 3.3 | main.py | log verification |
| FR-012 | 2 | 2.1 | registry.py | test_provider_registry.py |
| FR-013 | 3 | 3.2 | main.py | integration test |

---

## 5. Риски интеграции

| Риск | Вероятность | Влияние | Митигация |
|------|-------------|---------|-----------|
| DB миграция ломает данные | Низкая | Высокое | Backup, тестовая миграция |
| Регрессии в /test | Средняя | Высокое | Полное покрытие тестами |
| Регрессии в health-worker | Средняя | Высокое | Тестирование всех 16 провайдеров |
| Data API недоступен | Низкая | Среднее | Retry с exponential backoff |

**Митигации:**
1. **Stage 1 деплоится отдельно** — миграция безопасна, seed.py расширяется
2. **Stage 2 деплоится отдельно** — registry не ломает существующий код
3. **Stage 3 деплоится с тестами** — самый рискованный, требует проверки всех 16 провайдеров
4. **Git rollback** — если что-то пошло не так

---

## 6. Чек-лист перед реализацией

### PLAN_APPROVED Checklist

**Анализ:**
- [x] Все 8 hardcoded источников идентифицированы
- [x] Вариант B (DB как SSOT) выбран и обоснован
- [x] telegram-bot идентифицирован как эталон
- [x] Затрагиваемые сервисы определены (3 из 4)

**Планирование:**
- [x] Все 4 stages определены
- [x] Все 10 FR трассируются к задачам
- [x] Код примеры для ключевых изменений
- [x] Критерии завершения для каждого stage

**Риски:**
- [x] Риски оценены
- [x] Митигации определены

---

## 7. История изменений

| Версия | Дата | Автор | Изменения |
|--------|------|-------|-----------|
| 1.0 | 2025-12-31 | AI Architect | Первоначальная версия (Вариант A: shared config) |
| 2.0 | 2025-12-31 | AI Architect | Вариант B: DB как SSOT. Добавлены FR-008/009/010. Удалено копирование config.py |
