---
# === YAML Frontmatter (машиночитаемые метаданные) ===
feature_id: "F008"
feature_name: "provider-registry-ssot"
title: "Provider Registry SSOT — Единый источник правды для провайдеров"
created: "2025-12-31"
author: "AI (Analyst)"
type: "prd"
status: "PRD_READY"
version: 2

related_features: [F003, F004]
services: [free-ai-selector-business-api, free-ai-selector-health-worker, free-ai-selector-data-postgres-api]
requirements_count: 18
---

# PRD: Provider Registry SSOT — Единый источник правды для провайдеров

**Feature ID**: F008
**Версия**: 2.0
**Дата**: 2025-12-31
**Автор**: AI Agent (Аналитик)
**Статус**: PRD_READY

---

## 1. Обзор

### 1.1 Проблема

Текущая архитектура нарушает принципы **DRY** (Don't Repeat Yourself) и **SSOT** (Single Source of Truth):

**Список провайдеров определён в 8 местах:**

| # | Место | Файл | Строки | Что хранится |
|---|-------|------|--------|--------------|
| 1 | Seed | `data-postgres-api/.../seed.py` | 29-138 | 16 моделей с metadata |
| 2 | ProcessPrompt providers | `business-api/.../process_prompt.py` | 64-85 | 16 provider instances |
| 3 | TestAllProviders providers | `business-api/.../test_all_providers.py` | 64-85 | 16 instances |
| 4 | TestAllProviders model_names | `business-api/.../test_all_providers.py` | 263-285 | 16 маппингов name→display |
| 5 | HealthWorker ENV VAR | `health-worker/main.py` | 49-68 | 16 ENV VAR констант |
| 6 | HealthWorker check_*() | `health-worker/main.py` | 82-556 | 16 функций (~500 строк) |
| 7 | HealthWorker dispatch | `health-worker/main.py` | 562-581 | PROVIDER_CHECK_FUNCTIONS{} |
| 8 | HealthWorker configured | `health-worker/main.py` | 695-729 | configured_providers[] (16 if/elif) |

**Последствия:**
- Добавление нового провайдера требует изменений в **6+ файлах**
- Изменение имени модели требует изменений в **3 местах**
- Высокий риск рассинхронизации между источниками
- `/test` использует hardcoded list, а `/start` и `/stats` — БД (гибридность)

**Конкретный баг:**
- Если добавить новую модель в `seed.py` и БД, она появится в `/start` и `/stats`
- Но НЕ будет тестироваться в `/test` (hardcoded в `test_all_providers.py`)
- И НЕ будет мониториться в health-worker (hardcoded check functions)

### 1.2 Решение: Вариант B — PostgreSQL как SSOT

**Архитектурное решение**: Использовать PostgreSQL (через `seed.py`) как единственный источник правды. Все сервисы получают список провайдеров через Data API.

```
┌─────────────────────────────────────────────────────────────────┐
│                    ТЕКУЩЕЕ СОСТОЯНИЕ (AS-IS)                    │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│   seed.py  ─────────────▶ PostgreSQL (модели/статистика)        │
│       ▲                        ▲                                │
│       │                        │ HTTP GET /models               │
│   hardcoded (16)               │                                │
│                         ┌──────┴──────┐                         │
│                         │ /start      │ ✓ Динамический          │
│                         │ /stats      │ ✓ Динамический          │
│                         └─────────────┘                         │
│                                                                 │
│   process_prompt.py ────▶ hardcoded dict (16 instances)         │
│   test_all_providers.py ▶ hardcoded dict (16) + model_names     │
│   health-worker/main.py ▶ hardcoded functions (16 × 30 строк)   │
│       ├── 16 ENV VAR констант                                   │
│       ├── 16 check_*() функций                                  │
│       ├── PROVIDER_CHECK_FUNCTIONS{} dispatch dict              │
│       └── configured_providers[] (16 if/elif)                   │
│                                                                 │
│   ❌ 8 hardcoded источников, ручная синхронизация               │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                    ЦЕЛЕВОЕ СОСТОЯНИЕ (TO-BE)                    │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│                    ┌────────────────────┐                       │
│                    │      seed.py       │ ← SSOT                │
│                    │   SEED_MODELS[]    │                       │
│                    │ + api_format       │ ← NEW                 │
│                    │ + env_var          │ ← NEW                 │
│                    └─────────┬──────────┘                       │
│                              │                                  │
│                              ▼                                  │
│                    ┌────────────────────┐                       │
│                    │    PostgreSQL      │                       │
│                    │    ai_models       │                       │
│                    │ + api_format       │ ← NEW column          │
│                    │ + env_var          │ ← NEW column          │
│                    └─────────┬──────────┘                       │
│                              │                                  │
│                    ┌─────────┴──────────┐                       │
│                    │     Data API       │                       │
│                    │  GET /api/v1/models│                       │
│                    └─────────┬──────────┘                       │
│                              │ HTTP                             │
│         ┌────────────────────┼────────────────────┐             │
│         │                    │                    │             │
│         ▼                    ▼                    ▼             │
│  ┌─────────────┐     ┌─────────────┐     ┌─────────────┐       │
│  │business-api │     │telegram-bot │     │health-worker│       │
│  │             │     │             │     │             │       │
│  │ProviderReg  │     │ /start      │     │check_prov() │       │
│  │(class map)  │     │ /stats      │     │(universal)  │       │
│  └─────────────┘     └─────────────┘     └─────────────┘       │
│                                                                 │
│  ✓ 1 источник правды (seed.py → PostgreSQL)                    │
│  ✓ Все сервисы берут данные из Data API                        │
│  ✓ telegram-bot уже работает правильно (эталон!)               │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

**Ключевые компоненты решения:**

1. **seed.py** — единственный источник правды (расширяем полями `api_format`, `env_var`)
2. **PostgreSQL** — хранит всю конфигурацию провайдеров
3. **Data API** — предоставляет `/api/v1/models` со всеми полями
4. **ProviderRegistry** (business-api) — маппинг `provider_name` → `ProviderClass`
5. **Универсальный checker** (health-worker) — одна функция вместо 16

### 1.3 Почему Вариант B (DB), а не Вариант A (shared config)?

| Критерий | Вариант A (shared config.py) | Вариант B (DB как SSOT) |
|----------|------------------------------|-------------------------|
| Кол-во источников | 2 (config + seed) | 1 (только seed) |
| Сложность | Средняя (shared модуль) | Простая (уже есть API) |
| Новые зависимости | Docker volumes для shared | Нет новых |
| Соответствие паттерну | Частично | telegram-bot уже так работает |
| Риски | Синхронизация shared | Миграция БД |

**Выбран Вариант B** — проще, чище, следует существующему паттерну telegram-bot.

### 1.4 Целевая аудитория

| Сегмент | Описание | Потребности |
|---------|----------|-------------|
| Разработчики | Добавляют новых провайдеров | Изменение только 1 файла |
| DevOps | Поддерживают инфраструктуру | Предсказуемое поведение |
| Пользователи | Используют /test и /stats | Консистентные данные |

### 1.5 Ценностное предложение

- **SSOT**: seed.py → PostgreSQL → все сервисы (1 источник)
- **DRY**: Добавление провайдера = 2 файла (provider class + seed.py)
- **Меньше кода**: health-worker ~800 строк → ~200 строк
- **Консистентность**: /test и /stats всегда синхронизированы
- **Существующий паттерн**: telegram-bot уже работает так

---

## 2. Функциональные требования

### 2.1 Core Features (Must Have)

| ID | Название | Описание | Критерий приёмки |
|----|----------|----------|------------------|
| FR-001 | Расширение seed.py | Добавить поля `api_format`, `env_var` в SEED_MODELS | seed.py содержит все 16 провайдеров с новыми полями |
| FR-002 | Миграция БД | Добавить колонки `api_format`, `env_var` в `ai_models` | Миграция Alembic создана и применена |
| FR-003 | Data API endpoint | GET /api/v1/models возвращает `api_format`, `env_var` | API возвращает новые поля |
| FR-004 | ProviderRegistry | Класс-маппинг `provider_name` → `ProviderClass` | `get_provider(name)` возвращает инициализированный провайдер |
| FR-005 | Рефакторинг ProcessPrompt | Использует ProviderRegistry вместо hardcoded dict | Удалён hardcoded self.providers |
| FR-006 | Рефакторинг TestAllProviders | Получает провайдеры из API + ProviderRegistry | Удалён hardcoded self.providers и model_names |
| FR-007 | Универсальный health check | Одна функция `check_provider()` для всех провайдеров | Удалены 16 check_*() функций |
| FR-008 | Удаление ENV VAR констант | Удалить 16 hardcoded констант, использовать `os.getenv(model.env_var)` | Нет hardcoded ENV VAR в health-worker |
| FR-009 | Рефакторинг configured_providers | Заменить 16 if/elif на цикл по моделям из API | Удалён hardcoded configured_providers[] |
| FR-010 | Удаление PROVIDER_CHECK_FUNCTIONS | Удалить dispatch dict, использовать `api_format` из БД | Нет hardcoded dispatch dict |

### 2.2 Important Features (Should Have)

| ID | Название | Описание | Критерий приёмки |
|----|----------|----------|------------------|
| FR-011 | Валидация env vars | Логирование warning если API key пустой | Лог при отсутствии ключа |
| FR-012 | Ленивая инициализация | Provider instance создаётся только при использовании | Тесты проходят без API ключей |
| FR-013 | Helper функции для api_format | 4 функции: `_check_openai`, `_check_gemini`, `_check_cohere`, `_check_huggingface` | Dispatch по api_format работает |

### 2.3 Nice to Have (Could Have)

| ID | Название | Описание | Критерий приёмки |
|----|----------|----------|------------------|
| FR-020 | GET /api/v1/providers/configured | Endpoint возвращает список настроенных провайдеров | Новый endpoint работает |

---

## 3. User Stories

### US-001: Добавление нового провайдера

**Как** разработчик
**Я хочу** добавить нового AI провайдера изменив только 2 файла
**Чтобы** не забыть обновить какой-то из 6+ мест

**Критерии приёмки:**
- [ ] Создать класс провайдера в `ai_providers/newprovider.py`
- [ ] Добавить запись в `seed.py` (name, display_name, api_endpoint, api_format, env_var)
- [ ] Провайдер автоматически появляется в `/test` (через Data API)
- [ ] Провайдер автоматически появляется в `/stats` (через Data API)
- [ ] Провайдер автоматически мониторится в health-worker (через Data API)
- [ ] Нет необходимости редактировать process_prompt.py (только если новый provider class)
- [ ] Нет необходимости редактировать test_all_providers.py
- [ ] Нет необходимости редактировать health-worker/main.py

**Связанные требования:** FR-001, FR-004, FR-005, FR-006, FR-007

---

### US-002: Консистентность /test и /stats

**Как** пользователь
**Я хочу** видеть одинаковый список провайдеров в /test и /stats
**Чтобы** не удивляться почему провайдер есть в статистике, но не тестируется

**Критерии приёмки:**
- [ ] Провайдеры в /test и /stats идентичны (оба берут из Data API)
- [ ] Новый провайдер появляется в обоих командах одновременно

**Связанные требования:** FR-003, FR-006

---

## 4. Технические требования

### 4.1 Расширение схемы БД

**Новые колонки в таблице `ai_models`:**

```sql
-- Миграция Alembic
ALTER TABLE ai_models ADD COLUMN api_format VARCHAR(20) DEFAULT 'openai';
ALTER TABLE ai_models ADD COLUMN env_var VARCHAR(50) NOT NULL DEFAULT '';

-- api_format values: 'openai', 'gemini', 'cohere', 'huggingface'
```

### 4.2 Расширение seed.py

```python
# services/free-ai-selector-data-postgres-api/app/infrastructure/database/seed.py

SEED_MODELS = [
    {
        "name": "Gemini 2.5 Flash",
        "provider": "GoogleGemini",
        "api_endpoint": "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent",
        "is_active": True,
        # NEW FIELDS:
        "api_format": "gemini",
        "env_var": "GOOGLE_AI_STUDIO_API_KEY",
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

### 4.3 Маппинг api_format

| api_format | Провайдеры | Особенности |
|------------|------------|-------------|
| `openai` | Groq, Cerebras, SambaNova, DeepSeek, OpenRouter, GitHubModels, Fireworks, Hyperbolic, Novita, Scaleway, Kluster, Nebius | OpenAI-compatible API |
| `gemini` | GoogleGemini | Google Gemini API format |
| `cohere` | Cohere | Cohere API format |
| `huggingface` | HuggingFace | HuggingFace Inference API |
| `cloudflare` | Cloudflare | Cloudflare Workers AI (OpenAI-like but with account_id) |

### 4.4 ProviderRegistry (business-api)

```python
# services/free-ai-selector-business-api/app/infrastructure/ai_providers/registry.py

from typing import Optional
from app.infrastructure.ai_providers.base import AIProviderBase

# Import all provider classes
from app.infrastructure.ai_providers.google_gemini import GoogleGeminiProvider
from app.infrastructure.ai_providers.groq import GroqProvider
# ... остальные 14 импортов

# Маппинг provider_name → ProviderClass (единственное место!)
PROVIDER_CLASSES: dict[str, type[AIProviderBase]] = {
    "GoogleGemini": GoogleGeminiProvider,
    "Groq": GroqProvider,
    "Cerebras": CerebrasProvider,
    # ... остальные 13
}


class ProviderRegistry:
    """Фабрика для получения AI провайдеров."""

    _instances: dict[str, AIProviderBase] = {}

    @classmethod
    def get_provider(cls, name: str) -> Optional[AIProviderBase]:
        """Получить provider instance (ленивая инициализация)."""
        if name not in cls._instances:
            provider_class = PROVIDER_CLASSES.get(name)
            if provider_class:
                cls._instances[name] = provider_class()
        return cls._instances.get(name)

    @classmethod
    def get_all_provider_names(cls) -> list[str]:
        """Получить список всех имён провайдеров."""
        return list(PROVIDER_CLASSES.keys())

    @classmethod
    def has_provider(cls, name: str) -> bool:
        """Проверить наличие класса провайдера."""
        return name in PROVIDER_CLASSES
```

### 4.5 Универсальный health checker

```python
# services/free-ai-selector-health-worker/app/main.py

import os
import time
import httpx

async def check_provider(model: dict) -> tuple[bool, float]:
    """
    Универсальный health check для любого провайдера.

    Args:
        model: Словарь с полями из Data API:
            - provider: str
            - api_endpoint: str
            - api_format: str
            - env_var: str

    Returns:
        tuple[bool, float]: (is_healthy, response_time)
    """
    api_key = os.getenv(model["env_var"], "")
    if not api_key:
        logger.warning("provider_api_key_missing", provider=model["provider"])
        return False, 0.0

    start_time = time.time()
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            api_format = model.get("api_format", "openai")

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
                response = await _check_openai_format(client, model, api_key)

            return response.status_code == 200, time.time() - start_time
    except Exception as e:
        logger.error("health_check_failed", provider=model["provider"], error=sanitize_error_message(e))
        return False, time.time() - start_time


async def run_health_checks():
    """Запуск проверок для всех провайдеров из Data API."""
    # Получаем список моделей из Data API (как telegram-bot)
    models = await data_api_client.get_all_models()

    for model in models:
        is_healthy, response_time = await check_provider(model)
        await data_api_client.update_model_stats(model["id"], is_healthy, response_time)
```

---

## 5. Нефункциональные требования

### 5.1 Производительность

| ID | Метрика | Требование | Измерение |
|----|---------|------------|-----------|
| NF-001 | Время инициализации | < 100ms для всех провайдеров | pytest benchmark |
| NF-002 | Память | Не более +5MB на registry | memory_profiler |

### 5.2 Обратная совместимость

| ID | Требование | Описание |
|----|------------|----------|
| NF-010 | API неизменен | Все публичные API endpoints без изменений |
| NF-011 | Поведение неизменно | Результаты /test, /stats, process_prompt идентичны |

### 5.3 Тестируемость

| ID | Требование | Описание |
|----|------------|----------|
| NF-020 | Unit тесты | ≥90% покрытия для registry.py |
| NF-021 | Моки | Провайдеры легко мокаются в тестах |

---

## 6. Технические ограничения

### 6.1 Обязательные технологии

- **Python 3.11+**: type hints
- **Существующие классы**: Использовать AIProviderBase без изменений
- **HTTP-only**: Архитектура HTTP-only доступа к данным сохраняется
- **Alembic**: Миграции БД через Alembic

### 6.2 Ограничения

| Ограничение | Описание | Причина |
|-------------|----------|---------|
| Нет shared модуля | Каждый сервис независим | Изоляция Docker контейнеров |
| БД как SSOT | Все данные через Data API | Единый источник правды |
| Без изменения provider классов | Существующие провайдеры не меняются | Минимальный риск |

---

## 7. Допущения и риски

### 7.1 Допущения

| # | Допущение | Влияние если неверно |
|---|-----------|---------------------|
| 1 | Все провайдеры имеют одинаковый интерфейс (AIProviderBase) | Потребуется адаптер |
| 2 | Data API доступен при запуске health-worker | Добавить retry logic |
| 3 | Миграция БД не сломает существующие данные | Backup перед миграцией |

### 7.2 Риски

| # | Риск | Вероятность | Влияние | Митигация |
|---|------|-------------|---------|-----------|
| 1 | Миграция БД ломает данные | Низкая | Высокое | Backup, тестовая миграция |
| 2 | Регрессии в /test | Средняя | Высокое | 100% покрытие тестами |
| 3 | Регрессии в health-worker | Средняя | Высокое | Тестирование всех 16 провайдеров |
| 4 | Data API недоступен | Низкая | Среднее | Retry с exponential backoff |

---

## 8. План миграции

### 8.1 Этапы

| Этап | Действие | Риск |
|------|----------|------|
| 1 | Миграция БД: добавить api_format, env_var | Низкий |
| 2 | Обновить seed.py с новыми полями | Нет |
| 3 | Обновить Data API schema | Низкий |
| 4 | Создать registry.py в business-api | Нет (новый файл) |
| 5 | Рефакторинг process_prompt.py | Низкий |
| 6 | Рефакторинг test_all_providers.py | Низкий |
| 7 | Рефакторинг health-worker/main.py | Средний |
| 8 | Удалить старый код | Нет |

### 8.2 Rollback план

Если возникнут проблемы:
- Git revert изменений кода
- Миграция БД обратимая (DROP COLUMN)
- Старый код продолжит работать с новой схемой

---

## 9. Открытые вопросы

| # | Вопрос | Статус | Решение |
|---|--------|--------|---------|
| 1 | Где размещать PROVIDER_CONFIG? | Resolved | В seed.py + PostgreSQL (Вариант B) |
| 2 | Как health-worker получит доступ? | Resolved | Через Data API (как telegram-bot) |
| 3 | Что с configured_providers[]? | Resolved | Заменить на цикл по моделям из API |
| 4 | Что с 16 ENV VAR констант? | Resolved | Удалить, использовать os.getenv(model.env_var) |
| 5 | Нужен ли shared модуль? | Resolved | Нет, используем HTTP API |

---

## 10. Глоссарий

| Термин | Определение |
|--------|-------------|
| SSOT | Single Source of Truth — единственный источник правды |
| DRY | Don't Repeat Yourself — не повторяй себя |
| Provider | AI провайдер (Google, Groq, etc.) |
| Registry | Реестр/фабрика для получения объектов |
| api_format | Формат API провайдера (openai, gemini, cohere, huggingface) |

---

## 11. История изменений

| Версия | Дата | Автор | Изменения |
|--------|------|-------|-----------|
| 1.0 | 2025-12-31 | AI Analyst | Первоначальная версия |
| 2.0 | 2025-12-31 | AI Analyst | Вариант B: БД как SSOT, добавлены FR-008/009/010 |

---

## Качественные ворота

### PRD_READY Checklist

- [x] Все секции заполнены
- [x] Требования имеют уникальные ID (FR-*, NF-*)
- [x] Критерии приёмки определены для каждого требования
- [x] User stories связаны с требованиями
- [x] Нет блокирующих открытых вопросов
- [x] Риски идентифицированы и имеют план митигации
- [x] План миграции определён
- [x] Вариант B (DB как SSOT) выбран и обоснован
- [x] Все 8 hardcoded источников учтены в FR
- [x] configured_providers[] включён в scope (FR-009)
- [x] ENV VAR константы включены в scope (FR-008)
