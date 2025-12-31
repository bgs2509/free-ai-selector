---
feature_id: "F008"
feature_name: "provider-registry-ssot"
title: "Research: Provider Registry SSOT"
created: "2025-12-31"
author: "AI (Researcher)"
type: "research"
status: "RESEARCH_DONE"
version: 2
---

# Research Report: Provider Registry SSOT

## Executive Summary

Полное сканирование проекта выявило **8 hardcoded источников** провайдеров в 4 файлах. Анализ показал, что **telegram-bot уже работает правильно** (через Data API), и это паттерн для рефакторинга остальных сервисов.

**Выбранное решение: Вариант B — PostgreSQL как SSOT**
- seed.py расширяется полями `api_format` и `env_var`
- Все сервисы получают конфигурацию через Data API
- Нет shared модуля — используем существующий HTTP паттерн

---

## 1. Полная карта hardcoded источников

### 1.1 Таблица всех 8 hardcoded источников

| # | Файл | Строки | Что хранится | FR |
|---|------|--------|--------------|-----|
| 1 | `data-api/seed.py` | 29-138 | `SEED_MODELS[]` — 16 записей | FR-001 |
| 2 | `business-api/process_prompt.py` | 64-85 | `self.providers{}` — 16 instances | FR-005 |
| 3 | `business-api/test_all_providers.py` | 64-85 | `self.providers{}` — 16 instances | FR-006 |
| 4 | `business-api/test_all_providers.py` | 263-285 | `model_names{}` — 16 маппингов | FR-006 |
| 5 | `health-worker/main.py` | 49-68 | 16 ENV VAR констант | FR-008 |
| 6 | `health-worker/main.py` | 82-556 | 16 `check_*()` функций (~500 строк) | FR-007 |
| 7 | `health-worker/main.py` | 562-581 | `PROVIDER_CHECK_FUNCTIONS{}` dispatch | FR-010 |
| 8 | `health-worker/main.py` | 695-729 | `configured_providers[]` (16 if/elif) | FR-009 |

### 1.2 telegram-bot — эталонная реализация

**telegram-bot НЕ содержит hardcoded провайдеров!** Это эталон для рефакторинга:

```python
# telegram-bot/main.py - ПРАВИЛЬНО!

async def start_command(message):
    # Получаем статистику из API (динамически!)
    stats = await data_api_client.get_models_stats()

    text = "Привет! Я помогу выбрать лучшую AI модель.\n\n"
    text += f"Сейчас доступно {len(stats)} провайдеров:\n"
    for model in stats:
        text += f"• {model['provider']}: {model['name']}\n"

    await message.answer(text)
```

### 1.3 Диаграмма AS-IS: источники данных

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         ТЕКУЩЕЕ СОСТОЯНИЕ (AS-IS)                       │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌──────────────┐                                                       │
│  │   seed.py    │──────────────▶ PostgreSQL (ai_models)                 │
│  │  16 моделей  │               ┌───────────────────┐                   │
│  │  [SSOT #1]   │               │ name, provider,   │                   │
│  └──────────────┘               │ api_endpoint,     │                   │
│                                 │ is_active,        │                   │
│                                 │ success_count...  │                   │
│                                 └─────────┬─────────┘                   │
│                                           │                             │
│                                           ▼                             │
│                                 ┌───────────────────┐                   │
│                                 │     Data API      │                   │
│                                 │  GET /api/v1/...  │                   │
│                                 └─────────┬─────────┘                   │
│                                           │                             │
│                    ┌──────────────────────┼──────────────────────┐      │
│                    │                      │                      │      │
│                    ▼                      ▼                      ▼      │
│           ┌──────────────┐      ┌──────────────┐      ┌──────────────┐ │
│           │ telegram-bot │      │ business-api │      │health-worker │ │
│           │              │      │              │      │              │ │
│           │ ✅ DYNAMIC   │      │ ❌ HARDCODED │      │ ❌ HARDCODED │ │
│           │ uses API     │      │ 2 places     │      │ 4 places     │ │
│           └──────────────┘      └──────────────┘      └──────────────┘ │
│                                                                         │
│  Проблема: business-api и health-worker не используют Data API          │
│            для получения списка провайдеров                             │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Детальный анализ каждого hardcoded источника

### 2.1 seed.py (data-api) — SEED_MODELS[]

**Файл:** `services/free-ai-selector-data-postgres-api/app/infrastructure/database/seed.py`
**Строки:** 29-138
**Тип:** Массив словарей

```python
SEED_MODELS = [
    {
        "name": "Gemini 2.5 Flash",
        "provider": "GoogleGemini",
        "api_endpoint": "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent",
        "is_active": True,
    },
    # ... ещё 15 провайдеров
]
```

**Проблема:** Нет полей `api_format` и `env_var`, которые нужны health-worker.

**Решение (FR-001):** Расширить SEED_MODELS новыми полями:
```python
SEED_MODELS = [
    {
        "name": "Gemini 2.5 Flash",
        "provider": "GoogleGemini",
        "api_endpoint": "...",
        "is_active": True,
        "api_format": "gemini",       # NEW
        "env_var": "GOOGLE_AI_STUDIO_API_KEY",  # NEW
    },
    # ...
]
```

---

### 2.2 process_prompt.py (business-api) — self.providers{}

**Файл:** `services/free-ai-selector-business-api/app/application/use_cases/process_prompt.py`
**Строки:** 22-37 (imports), 64-85 (dict)
**Тип:** Hardcoded dict с instances

```python
# 16 imports
from app.infrastructure.ai_providers.google_gemini import GoogleGeminiProvider
from app.infrastructure.ai_providers.groq import GroqProvider
# ... ещё 14 imports

class ProcessPromptUseCase:
    def __init__(self, data_api_client: DataAPIClient):
        self.data_api_client = data_api_client
        self.providers = {
            "GoogleGemini": GoogleGeminiProvider(),
            "Groq": GroqProvider(),
            # ... ещё 14 hardcoded instances
        }
```

**Проблема:**
- Если добавить провайдера в БД, но не в этот dict → `KeyError`
- 16 импортов + 16 строк dict = 32 строки дублирования

**Решение (FR-005):** Использовать ProviderRegistry:
```python
from app.infrastructure.ai_providers.registry import ProviderRegistry

class ProcessPromptUseCase:
    async def execute(self, request):
        best_model = await self._select_best_model()
        provider = ProviderRegistry.get_provider(best_model.provider)
        if not provider:
            raise ValueError(f"Provider {best_model.provider} not configured")
```

---

### 2.3 test_all_providers.py — self.providers{} + model_names{}

**Файл:** `services/free-ai-selector-business-api/app/application/use_cases/test_all_providers.py`
**Строки:** 64-85 (providers), 263-285 (model_names)
**Тип:** Два hardcoded dict

```python
# Hardcoded dict #1 — providers instances
self.providers = {
    "GoogleGemini": GoogleGeminiProvider(),
    "Groq": GroqProvider(),
    # ... 16 instances
}

# Hardcoded dict #2 — model names (!)
model_names = {
    "GoogleGemini": "Gemini 2.5 Flash",
    "Groq": "Llama 3.3 70B Versatile",
    # ... 16 маппингов
}
```

**Проблема:**
- Дублирует seed.py (name уже есть в БД)
- /test тестирует hardcoded список, а /stats берёт из БД
- При добавлении провайдера в БД — не появится в /test

**Решение (FR-006):** Получать провайдеров из Data API:
```python
async def execute(self):
    # Получаем список моделей из API (как telegram-bot)
    models = await self.data_api_client.get_all_models()

    results = []
    for model in models:
        provider = ProviderRegistry.get_provider(model.provider)
        if provider:
            result = await self._test_provider(model.provider, provider, model.name)
            results.append(result)
    return results
```

---

### 2.4 health-worker/main.py — 4 hardcoded секции

**Файл:** `services/free-ai-selector-health-worker/app/main.py`

#### 2.4.1 ENV VAR константы (строки 49-68)

```python
# 16 hardcoded констант
GOOGLE_AI_STUDIO_API_KEY = os.getenv("GOOGLE_AI_STUDIO_API_KEY", "")
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
CEREBRAS_API_KEY = os.getenv("CEREBRAS_API_KEY", "")
# ... ещё 13
```

**Решение (FR-008):** Удалить константы, использовать `os.getenv(model["env_var"])` динамически.

---

#### 2.4.2 check_*() функции (строки 82-556)

```python
# 16 функций × ~30 строк = ~480 строк кода!

async def check_google_gemini(endpoint: str) -> tuple[bool, float]:
    """Проверка Google Gemini провайдера."""
    if not GOOGLE_AI_STUDIO_API_KEY:
        logger.warning("google_gemini_api_key_missing")
        return False, 0.0

    start_time = time.time()
    # ... Gemini-specific HTTP call (~25 строк)

async def check_groq(endpoint: str) -> tuple[bool, float]:
    """Проверка Groq провайдера."""
    if not GROQ_API_KEY:
        logger.warning("groq_api_key_missing")
        return False, 0.0

    start_time = time.time()
    # ... OpenAI-compatible HTTP call (~25 строк)

# ... ещё 14 функций с похожим кодом
```

**Проблема:**
- 480 строк дублированного кода
- Все функции делают почти одно и то же
- Различаются только форматом API (openai/gemini/cohere/huggingface)

**Решение (FR-007):** Одна универсальная функция + 4 helper по api_format:
```python
async def check_provider(model: dict) -> tuple[bool, float]:
    api_key = os.getenv(model["env_var"], "")
    if not api_key:
        return False, 0.0

    if model["api_format"] == "openai":
        return await _check_openai_format(model, api_key)
    elif model["api_format"] == "gemini":
        return await _check_gemini_format(model, api_key)
    # ...
```

---

#### 2.4.3 PROVIDER_CHECK_FUNCTIONS{} (строки 562-581)

```python
PROVIDER_CHECK_FUNCTIONS = {
    "GoogleGemini": check_google_gemini,
    "Groq": check_groq,
    "Cerebras": check_cerebras,
    "SambaNova": check_sambanova,
    "HuggingFace": check_huggingface,
    "Cloudflare": check_cloudflare,
    "DeepSeek": check_deepseek,
    "Cohere": check_cohere,
    "OpenRouter": check_openrouter,
    "GitHubModels": check_github_models,
    "Fireworks": check_fireworks,
    "Hyperbolic": check_hyperbolic,
    "Novita": check_novita,
    "Scaleway": check_scaleway,
    "Kluster": check_kluster,
    "Nebius": check_nebius,
}
```

**Решение (FR-010):** Удалить. Dispatch по `model["api_format"]` из БД.

---

#### 2.4.4 configured_providers[] (строки 695-729)

```python
# 16 if/elif блоков!
configured_providers = []

if GOOGLE_AI_STUDIO_API_KEY:
    configured_providers.append("GoogleGemini")
if GROQ_API_KEY:
    configured_providers.append("Groq")
if CEREBRAS_API_KEY:
    configured_providers.append("Cerebras")
# ... ещё 13 if блоков

logger.info(f"Configured providers: {configured_providers}")
```

**Решение (FR-009):** Цикл по моделям из API:
```python
models = await data_api_client.get_all_models()
configured_providers = []
for model in models:
    if os.getenv(model["env_var"]):
        configured_providers.append(model["provider"])
```

---

## 3. Архитектура решения: Вариант B (DB как SSOT)

### 3.1 Почему Вариант B?

| Критерий | Вариант A (shared config) | Вариант B (DB как SSOT) |
|----------|---------------------------|-------------------------|
| Источников данных | 2 (config + seed) | 1 (seed.py) |
| Дополнительные зависимости | Docker volumes | Нет |
| Существующий паттерн | Нет | telegram-bot |
| Сложность | Средняя | Низкая |

**Вывод:** Вариант B проще и следует существующему паттерну.

### 3.2 Диаграмма TO-BE

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         ЦЕЛЕВОЕ СОСТОЯНИЕ (TO-BE)                       │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌──────────────┐                                                       │
│  │   seed.py    │──────────────▶ PostgreSQL (ai_models)                 │
│  │  16 моделей  │               ┌───────────────────┐                   │
│  │  [SSOT]      │               │ name, provider,   │                   │
│  │              │               │ api_endpoint,     │                   │
│  │ + api_format │               │ api_format,       │ ← NEW             │
│  │ + env_var    │               │ env_var,          │ ← NEW             │
│  │              │               │ is_active...      │                   │
│  └──────────────┘               └─────────┬─────────┘                   │
│                                           │                             │
│                                           ▼                             │
│                                 ┌───────────────────┐                   │
│                                 │     Data API      │                   │
│                                 │  GET /api/v1/...  │                   │
│                                 └─────────┬─────────┘                   │
│                                           │                             │
│                    ┌──────────────────────┼──────────────────────┐      │
│                    │                      │                      │      │
│                    ▼                      ▼                      ▼      │
│           ┌──────────────┐      ┌──────────────┐      ┌──────────────┐ │
│           │ telegram-bot │      │ business-api │      │health-worker │ │
│           │              │      │              │      │              │ │
│           │ ✅ DYNAMIC   │      │ ✅ DYNAMIC   │      │ ✅ DYNAMIC   │ │
│           │ (уже готов)  │      │ + Registry   │      │ + universal  │ │
│           │              │      │ (class map)  │      │   checker    │ │
│           └──────────────┘      └──────────────┘      └──────────────┘ │
│                                                                         │
│  ✓ 1 источник правды: seed.py → PostgreSQL                             │
│  ✓ Все сервисы получают данные через Data API                          │
│  ✓ business-api: ProviderRegistry для маппинга name→class              │
│  ✓ health-worker: 1 функция check_provider() вместо 16                 │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### 3.3 Маппинг api_format

| api_format | Провайдеры | Количество |
|------------|------------|------------|
| `openai` | Groq, Cerebras, SambaNova, DeepSeek, OpenRouter, GitHubModels, Fireworks, Hyperbolic, Novita, Scaleway, Kluster, Nebius | 12 |
| `gemini` | GoogleGemini | 1 |
| `cohere` | Cohere | 1 |
| `huggingface` | HuggingFace | 1 |
| `cloudflare` | Cloudflare | 1 |

### 3.4 ProviderRegistry (business-api only)

```python
# services/free-ai-selector-business-api/app/infrastructure/ai_providers/registry.py

# Единственное место с импортами классов провайдеров
PROVIDER_CLASSES: dict[str, type[AIProviderBase]] = {
    "GoogleGemini": GoogleGeminiProvider,
    "Groq": GroqProvider,
    "Cerebras": CerebrasProvider,
    # ... 16 записей
}

class ProviderRegistry:
    _instances: dict[str, AIProviderBase] = {}

    @classmethod
    def get_provider(cls, name: str) -> Optional[AIProviderBase]:
        if name not in cls._instances:
            provider_class = PROVIDER_CLASSES.get(name)
            if provider_class:
                cls._instances[name] = provider_class()
        return cls._instances.get(name)
```

**Почему это не дублирование?**
- PROVIDER_CLASSES содержит только маппинг name → class
- Не содержит metadata (name, endpoint, env_var) — это в БД
- Нужен только в business-api (где живут классы провайдеров)
- health-worker не нуждается в классах — ему нужен только HTTP

---

## 4. Процесс добавления провайдера

### 4.1 AS-IS (6+ файлов)

```
┌─────────────────────────────────────────────────────────────────────────┐
│  ТЕКУЩИЙ ПРОЦЕСС (6+ файлов, ~150 строк кода)                           │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  1. Создать ai_providers/newprovider.py       (~50 строк)              │
│  2. Добавить в process_prompt.py providers{}  (2 строки: import+dict)  │
│  3. Добавить в test_all_providers.py          (4 строки)               │
│     - import                                                            │
│     - providers{}                                                       │
│     - model_names{}                                                     │
│  4. Добавить в seed.py SEED_MODELS[]          (6 строк)                │
│  5. Добавить в health-worker/main.py          (~40 строк)              │
│     - ENV VAR константу                                                 │
│     - check_newprovider() функцию (~30 строк)                          │
│     - PROVIDER_CHECK_FUNCTIONS{}                                        │
│     - configured_providers if-block                                     │
│  6. Добавить в docker-compose.yml             (2 строки)               │
│  7. Добавить в .env.example                   (2 строки)               │
│                                                                         │
│  ⚠️ Риск: Забыть один из 6 файлов = баг                                 │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### 4.2 TO-BE (2-3 файла)

```
┌─────────────────────────────────────────────────────────────────────────┐
│  ЦЕЛЕВОЙ ПРОЦЕСС (2-3 файла, ~60 строк)                                 │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  1. Создать ai_providers/newprovider.py       (~50 строк)              │
│                                                                         │
│  2. Добавить в seed.py SEED_MODELS[]          (8 строк)                │
│     {                                                                   │
│         "name": "New Model Name",                                       │
│         "provider": "NewProvider",                                      │
│         "api_endpoint": "https://...",                                  │
│         "is_active": True,                                              │
│         "api_format": "openai",    # или gemini/cohere/huggingface     │
│         "env_var": "NEW_PROVIDER_API_KEY",                             │
│     }                                                                   │
│                                                                         │
│  3. Добавить в registry.py PROVIDER_CLASSES   (2 строки)               │
│     - import NewProviderClass                                           │
│     - "NewProvider": NewProviderClass                                   │
│                                                                         │
│  4. docker-compose.yml + .env.example         (2 строки)               │
│                                                                         │
│  ✅ Автоматически появляется в:                                         │
│     - /test (через Data API + ProviderRegistry)                         │
│     - /stats (через Data API)                                           │
│     - health-worker (через Data API + api_format)                       │
│     - telegram-bot /start (через Data API)                              │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 5. Метрики успеха

| Метрика | До (AS-IS) | После (TO-BE) |
|---------|------------|---------------|
| Hardcoded источников | 8 мест | 1 (seed.py) + 1 (registry class map) |
| Файлов для добавления провайдера | 6+ | 2-3 |
| Строк в health-worker/main.py | ~800 | ~200 |
| Риск рассинхронизации | Высокий | Нулевой (SSOT) |
| Время добавления провайдера | ~30 мин | ~5 мин |

---

## 6. Checklist всех проблем и решений

| # | Проблема | Файл | Строки | Решение | FR |
|---|----------|------|--------|---------|-----|
| 1 | seed.py без api_format/env_var | data-api/seed.py | 29-138 | Добавить поля | FR-001 |
| 2 | hardcoded self.providers | process_prompt.py | 64-85 | ProviderRegistry | FR-005 |
| 3 | hardcoded self.providers | test_all_providers.py | 64-85 | Data API + Registry | FR-006 |
| 4 | hardcoded model_names{} | test_all_providers.py | 263-285 | Data API (model.name) | FR-006 |
| 5 | 16 ENV VAR констант | health-worker/main.py | 49-68 | os.getenv(model.env_var) | FR-008 |
| 6 | 16 check_*() функций | health-worker/main.py | 82-556 | 1 universal checker | FR-007 |
| 7 | PROVIDER_CHECK_FUNCTIONS{} | health-worker/main.py | 562-581 | Dispatch по api_format | FR-010 |
| 8 | configured_providers[] | health-worker/main.py | 695-729 | Цикл по моделям из API | FR-009 |

**Все 8 проблем учтены в PRD v2.0**

---

## 7. Качественные ворота

### RESEARCH_DONE Checklist

- [x] Полное сканирование проекта выполнено
- [x] Все 8 hardcoded источников идентифицированы с номерами строк
- [x] telegram-bot идентифицирован как эталон (уже использует API)
- [x] Архитектура SSOT спроектирована (Вариант B — DB)
- [x] Маппинг api_format определён для всех 16 провайдеров
- [x] Процесс добавления провайдера до/после задокументирован
- [x] Метрики успеха определены
- [x] Все проблемы связаны с FR в PRD
